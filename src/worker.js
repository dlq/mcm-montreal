import { Container } from "@cloudflare/containers";

const CONTAINER_INSTANCE_NAME = "web-d1-v11";
const CONTAINER_PORT = 8080;
const DEFAULT_APEX_HOSTNAME = "montrealmcm.ca";
const DEFAULT_WWW_HOSTNAME = "www.montrealmcm.ca";
const DEFAULT_D1_BRIDGE_URL = "https://montreal-mcm.dalaque.workers.dev/internal/d1/query";
const REFRESH_CRON = "23 9 * * *";
const REFRESH_MONITOR_CRON = "23 11 * * *";
const SOURCE_SLUGS = [
  "morceau",
  "showroom-montreal",
  "montreal-moderne",
  "le-centerpiece",
  "maison-singulier",
  "yardsale-vintage",
  "chez-lamothe",
  "habitat-mobilier",
  "green-wall-vintage",
  "mostly-danish",
];
const SHOWROOM_SOURCE_SLUG = "showroom-montreal";
const SHOWROOM_CHUNK_COUNT = 12;
const LE_CENTERPIECE_SOURCE_SLUG = "le-centerpiece";
const LE_CENTERPIECE_CHUNK_COUNT = 7;
const CHEZ_LAMOTHE_SOURCE_SLUG = "chez-lamothe";
const CHEZ_LAMOTHE_CHUNK_COUNT = 20;
const MOSTLY_DANISH_SOURCE_SLUG = "mostly-danish";
const MOSTLY_DANISH_CHUNK_COUNT = 30;
const MOSTLY_DANISH_CHUNKS_PER_REFRESH = 5;
const RECONCILABLE_CHUNKED_SOURCE_SLUGS = new Set([
  SHOWROOM_SOURCE_SLUG,
  LE_CENTERPIECE_SOURCE_SLUG,
  CHEZ_LAMOTHE_SOURCE_SLUG,
]);
const RETRY_DELAY_SECONDS = 300;
const STALE_REFRESH_JOB_AGE_MS = 90 * 60 * 1000;
const HIDDEN_SPIKE_MIN_COUNT = 50;
const HIDDEN_SPIKE_MIN_RATIO = 0.25;
const CONTAINER_START_RETRY_PATTERNS = [
  "container is not running",
  "container suddenly disconnected",
  "network connection lost",
];

export class McmContainer extends Container {
  defaultPort = CONTAINER_PORT;
  sleepAfter = "30m";
  pingEndpoint = "/readyz";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      APP_HOST: "0.0.0.0",
      APP_PORT: "8080",
      D1_BRIDGE_URL: env.D1_BRIDGE_URL || DEFAULT_D1_BRIDGE_URL,
      D1_BRIDGE_TOKEN: env.D1_BRIDGE_TOKEN || "",
      MCM_SECRET_KEY: env.MCM_SECRET_KEY || "",
      MCM_ADMIN_TOKEN: env.MCM_ADMIN_TOKEN || "",
      MCM_EXPOSE_TIMING_HEADERS: env.MCM_EXPOSE_TIMING_HEADERS || "",
    };
  }

  onStart() {
    console.log("MCM container started");
  }

  onStop() {
    console.log("MCM container stopped");
  }

  onError(error) {
    console.error("MCM container error", error);
    throw error;
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const apexHostname = env.APEX_HOSTNAME || DEFAULT_APEX_HOSTNAME;
    const wwwHostname = env.WWW_HOSTNAME || DEFAULT_WWW_HOSTNAME;
    if (url.hostname === wwwHostname) {
      url.hostname = apexHostname;
      return Response.redirect(url.toString(), 301);
    }
    if (url.pathname === "/internal/d1/query") {
      return queryD1(request, env);
    }
    if (url.pathname === "/internal/refresh-now") {
      return refreshNow(request, env, url);
    }
    if (url.pathname.startsWith("/internal/")) {
      return new Response("Not found", { status: 404 });
    }
    if (url.pathname.startsWith("/cron/")) {
      return new Response("Not found", { status: 404 });
    }
    return fetchContainer(request, env);
  },

  async scheduled(controller, env, ctx) {
    if (controller.cron === REFRESH_MONITOR_CRON) {
      ctx.waitUntil(checkRefreshJobs(env));
      return;
    }
    if (controller.cron !== REFRESH_CRON) {
      console.warn(
        JSON.stringify({
          event: "unknown_scheduled_cron",
          cron: controller.cron,
        }),
      );
      return;
    }

    ctx.waitUntil(enqueueRefreshSources(env, SOURCE_SLUGS, "scheduled_refresh"));
  },

  async queue(batch, env) {
    for (const message of batch.messages) {
      await consumeRefreshMessage(message, env);
    }
  },
};

async function queryD1(request, env) {
  const authorization = request.headers.get("authorization") || "";
  if (!env.D1_BRIDGE_TOKEN || authorization !== `Bearer ${env.D1_BRIDGE_TOKEN}`) {
    return new Response("Not found", { status: 404 });
  }
  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  let payload;
  try {
    payload = await request.json();
  } catch (_error) {
    return Response.json({ success: false, error: "Invalid JSON" }, { status: 400 });
  }

  if (typeof payload.sql !== "string" || !Array.isArray(payload.params)) {
    return Response.json({ success: false, error: "Invalid D1 query payload" }, { status: 400 });
  }

  try {
    const result = await env.DB.prepare(payload.sql)
      .bind(...payload.params)
      .all();
    return Response.json({
      success: result.success,
      results: result.results || [],
      changes: result.meta?.changes || 0,
    });
  } catch (error) {
    return Response.json(
      { success: false, error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}

async function refreshNow(request, env, url) {
  const token = env.MCM_MANUAL_REFRESH_TOKEN || "";
  const authorization = request.headers.get("authorization") || "";
  const headerToken = request.headers.get("x-mcm-admin-token") || "";
  if (!token || (authorization !== `Bearer ${token}` && headerToken !== token)) {
    return new Response("Not found", { status: 404 });
  }
  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const sourceSlug = url.searchParams.get("source") || "";
  if (sourceSlug) {
    if (!SOURCE_SLUGS.includes(sourceSlug)) {
      return Response.json({ status: "error", error: "Unknown source" }, { status: 404 });
    }
    const result = await enqueueRefreshSources(env, [sourceSlug], "manual_refresh_now");
    return Response.json({ status: "accepted", ...result }, { status: 202 });
  }

  const result = await enqueueRefreshSources(env, SOURCE_SLUGS, "manual_refresh_now");
  return Response.json({ status: "accepted", ...result }, { status: 202 });
}

async function enqueueRefreshSources(env, sourceSlugs, trigger) {
  if (!env.REFRESH_QUEUE) {
    throw new Error("REFRESH_QUEUE binding is not configured");
  }
  const messages = sourceSlugs.flatMap((sourceSlug) =>
    refreshMessagesForSource(sourceSlug, trigger),
  );
  await env.REFRESH_QUEUE.sendBatch(messages);
  console.log(
    JSON.stringify({
      event: "refresh_sources_enqueued",
      trigger,
      sources: sourceSlugs,
      count: messages.length,
    }),
  );
  return { trigger, sources: sourceSlugs, count: messages.length };
}

function refreshMessagesForSource(sourceSlug, trigger) {
  const enqueuedAt = new Date().toISOString();
  if (sourceSlug === SHOWROOM_SOURCE_SLUG) {
    return withReconcileMessage(
      sourceSlug,
      trigger,
      enqueuedAt,
      Array.from({ length: SHOWROOM_CHUNK_COUNT }, (_value, chunkIndex) =>
        refreshMessageBody(sourceSlug, trigger, enqueuedAt, chunkIndex),
      ),
    );
  }
  if (sourceSlug === LE_CENTERPIECE_SOURCE_SLUG) {
    return withReconcileMessage(
      sourceSlug,
      trigger,
      enqueuedAt,
      Array.from({ length: LE_CENTERPIECE_CHUNK_COUNT }, (_value, chunkIndex) =>
        refreshMessageBody(sourceSlug, trigger, enqueuedAt, chunkIndex),
      ),
    );
  }
  if (sourceSlug === CHEZ_LAMOTHE_SOURCE_SLUG) {
    return withReconcileMessage(
      sourceSlug,
      trigger,
      enqueuedAt,
      Array.from({ length: CHEZ_LAMOTHE_CHUNK_COUNT }, (_value, chunkIndex) =>
        refreshMessageBody(sourceSlug, trigger, enqueuedAt, chunkIndex),
      ),
    );
  }
  if (sourceSlug === MOSTLY_DANISH_SOURCE_SLUG) {
    return mostlyDanishChunkIndexes().map((chunkIndex) =>
      refreshMessageBody(sourceSlug, trigger, enqueuedAt, chunkIndex),
    );
  }
  return [refreshMessageBody(sourceSlug, trigger, enqueuedAt)];
}

function withReconcileMessage(sourceSlug, trigger, enqueuedAt, chunkMessages) {
  if (!RECONCILABLE_CHUNKED_SOURCE_SLUGS.has(sourceSlug)) {
    return chunkMessages;
  }
  return [...chunkMessages, reconcileMessageBody(sourceSlug, trigger, enqueuedAt)];
}

function mostlyDanishChunkIndexes(now = new Date()) {
  const dayIndex = Math.floor(now.getTime() / 86_400_000);
  const startIndex = (dayIndex * MOSTLY_DANISH_CHUNKS_PER_REFRESH) % MOSTLY_DANISH_CHUNK_COUNT;
  return Array.from(
    { length: MOSTLY_DANISH_CHUNKS_PER_REFRESH },
    (_value, offset) => (startIndex + offset) % MOSTLY_DANISH_CHUNK_COUNT,
  );
}

function refreshMessageBody(sourceSlug, trigger, enqueuedAt, chunkIndex = null) {
  const body = {
    action: "refresh",
    source_slug: sourceSlug,
    trigger,
    enqueued_at: enqueuedAt,
    message_id: crypto.randomUUID(),
  };
  if (chunkIndex !== null) {
    body.chunk_index = chunkIndex;
  }
  return { body };
}

function reconcileMessageBody(sourceSlug, trigger, enqueuedAt) {
  return {
    body: {
      action: "reconcile",
      source_slug: sourceSlug,
      trigger,
      enqueued_at: enqueuedAt,
      message_id: crypto.randomUUID(),
    },
  };
}

async function consumeRefreshMessage(message, env) {
  const body = message.body || {};
  const sourceSlug = typeof body.source_slug === "string" ? body.source_slug : "";
  if (!SOURCE_SLUGS.includes(sourceSlug)) {
    console.error(
      JSON.stringify({
        event: "refresh_queue_invalid_message",
        body,
      }),
    );
    message.ack();
    return;
  }

  try {
    const cronPath =
      body.action === "reconcile"
        ? reconcileCronPath(sourceSlug, body.enqueued_at)
        : refreshCronPath(sourceSlug, body.chunk_index);
    const result = await callContainerCron(env, cronPath);
    console.log(
      JSON.stringify({
        event: "refresh_queue_completed",
        action: body.action || "refresh",
        source_slug: sourceSlug,
        chunk_index: body.chunk_index ?? null,
        trigger: body.trigger || "unknown",
        message_id: body.message_id || "",
        attempts: message.attempts,
        ...result,
      }),
    );
    message.ack();
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(
      JSON.stringify({
        event: "refresh_queue_failed",
        action: body.action || "refresh",
        source_slug: sourceSlug,
        chunk_index: body.chunk_index ?? null,
        trigger: body.trigger || "unknown",
        message_id: body.message_id || "",
        attempts: message.attempts,
        error: errorMessage,
      }),
    );
    message.retry({ delaySeconds: RETRY_DELAY_SECONDS });
  }
}

function refreshCronPath(sourceSlug, chunkIndex) {
  if (sourceSlug === SHOWROOM_SOURCE_SLUG) {
    if (!Number.isInteger(chunkIndex) || chunkIndex < 0 || chunkIndex >= SHOWROOM_CHUNK_COUNT) {
      throw new Error(`Invalid Showroom chunk index: ${chunkIndex}`);
    }
    return `/cron/refresh/showroom-montreal/chunk/${chunkIndex}`;
  }
  if (sourceSlug === LE_CENTERPIECE_SOURCE_SLUG) {
    if (
      !Number.isInteger(chunkIndex) ||
      chunkIndex < 0 ||
      chunkIndex >= LE_CENTERPIECE_CHUNK_COUNT
    ) {
      throw new Error(`Invalid Le Centerpiece chunk index: ${chunkIndex}`);
    }
    return `/cron/refresh/le-centerpiece/chunk/${chunkIndex}`;
  }
  if (sourceSlug === CHEZ_LAMOTHE_SOURCE_SLUG) {
    if (!Number.isInteger(chunkIndex) || chunkIndex < 0 || chunkIndex >= CHEZ_LAMOTHE_CHUNK_COUNT) {
      throw new Error(`Invalid Chez Lamothe chunk index: ${chunkIndex}`);
    }
    return `/cron/refresh/chez-lamothe/chunk/${chunkIndex}`;
  }
  if (sourceSlug === MOSTLY_DANISH_SOURCE_SLUG) {
    if (
      !Number.isInteger(chunkIndex) ||
      chunkIndex < 0 ||
      chunkIndex >= MOSTLY_DANISH_CHUNK_COUNT
    ) {
      throw new Error(`Invalid Mostly Danish chunk index: ${chunkIndex}`);
    }
    return `/cron/refresh/mostly-danish/chunk/${chunkIndex}`;
  }
  return `/cron/refresh/${sourceSlug}`;
}

function reconcileCronPath(sourceSlug, enqueuedAt) {
  if (!RECONCILABLE_CHUNKED_SOURCE_SLUGS.has(sourceSlug)) {
    throw new Error(`Source is not chunk-reconcilable: ${sourceSlug}`);
  }
  const params = new URLSearchParams();
  if (typeof enqueuedAt === "string" && enqueuedAt) {
    params.set("since", enqueuedAt);
  }
  const query = params.toString();
  return `/cron/reconcile/${sourceSlug}${query ? `?${query}` : ""}`;
}

async function callContainerCron(env, path) {
  const container = env.MCM_CONTAINER.getByName(CONTAINER_INSTANCE_NAME);
  const response = await container.fetch(
    new Request(`https://montreal-mcm.internal${path}`, {
      method: "POST",
      headers: { "X-Cloudflare-Scheduled": "1" },
    }),
  );
  const text = await response.text();
  if (!response.ok) {
    throw new Error(
      `container cron ${path} returned HTTP ${response.status}: ${text.slice(0, 300)}`,
    );
  }
  console.log(
    JSON.stringify({
      event: "container_cron",
      path,
      status: response.status,
      body: text.slice(0, 500),
    }),
  );
  return { status: response.status, body: text.slice(0, 500) };
}

async function checkRefreshJobs(env) {
  const checkedAt = new Date();
  const today = checkedAt.toISOString().slice(0, 10);
  const staleCutoff = new Date(checkedAt.getTime() - STALE_REFRESH_JOB_AGE_MS).toISOString();
  await markStaleRefreshJobs(env, checkedAt.toISOString(), staleCutoff);
  const result = await env.DB.prepare(
    `
    SELECT source_slug, chunk_index, entry_url, status, started_at, finished_at, error_message
      , hidden_count, listings_found, new_count, reconciled_count
    FROM refresh_jobs
    WHERE started_at >= ?
    ORDER BY started_at DESC
    `,
  )
    .bind(`${today}T00:00:00`)
    .all();
  const jobsBySource = new Map();
  for (const job of result.results || []) {
    const sourceJobs = jobsBySource.get(job.source_slug) || [];
    sourceJobs.push(job);
    jobsBySource.set(job.source_slug, sourceJobs);
  }

  const warnings = [];
  for (const sourceSlug of SOURCE_SLUGS) {
    const sourceJobs = jobsBySource.get(sourceSlug) || [];
    const expectedJobs = expectedRefreshJobCount(sourceSlug);
    if (sourceJobs.length < expectedJobs) {
      const missingChunkIndexes = missingExpectedChunkIndexes(sourceSlug, sourceJobs);
      warnings.push({
        source_slug: sourceSlug,
        reason: "missing_refresh_jobs",
        expected_jobs: expectedJobs,
        observed_jobs: sourceJobs.length,
        ...(missingChunkIndexes.length > 0 ? { missing_chunk_indexes: missingChunkIndexes } : {}),
      });
      continue;
    }

    const nonSuccessJobs = sourceJobs.filter((job) => job.status !== "success");
    if (nonSuccessJobs.length > 0) {
      warnings.push({
        source_slug: sourceSlug,
        reason: "refresh_jobs_not_success",
        count: nonSuccessJobs.length,
        statuses: summarizeJobStatuses(nonSuccessJobs),
        latest_started_at: nonSuccessJobs[0]?.started_at || "",
        latest_finished_at: nonSuccessJobs[0]?.finished_at || "",
        latest_error_message: nonSuccessJobs[0]?.error_message || "",
        affected_chunk_indexes: chunkIndexesForJobs(nonSuccessJobs),
      });
    }

    for (const job of sourceJobs) {
      if (hasSuspiciousHiddenCount(job)) {
        const listingsFound = Number(job.listings_found) || 0;
        const hiddenCount = Number(job.hidden_count) || 0;
        const hiddenRatio = listingsFound > 0 ? hiddenCount / listingsFound : null;
        warnings.push({
          source_slug: sourceSlug,
          reason: "suspicious_hidden_count",
          started_at: job.started_at,
          finished_at: job.finished_at,
          status: job.status,
          listings_found: listingsFound,
          hidden_count: hiddenCount,
          hidden_ratio: hiddenRatio,
        });
      }
    }
  }

  const unknownSourceJobs = Array.from(jobsBySource.keys()).filter(
    (sourceSlug) => !SOURCE_SLUGS.includes(sourceSlug),
  );
  for (const sourceSlug of unknownSourceJobs) {
    warnings.push({
      source_slug: sourceSlug,
      reason: "unknown_refresh_source",
      observed_jobs: jobsBySource.get(sourceSlug)?.length || 0,
    });
  }

  for (const job of result.results || []) {
    if (job.status === "running") {
      warnings.push({
        source_slug: job.source_slug,
        reason: "refresh_job_still_running",
        started_at: job.started_at,
        chunk_index: job.chunk_index ?? null,
      });
    }
  }

  const payload = {
    event: "refresh_job_monitor",
    checked_at: checkedAt.toISOString(),
    refresh_date: today,
    warnings,
  };
  if (warnings.length > 0) {
    console.warn(JSON.stringify(payload));
    return;
  }
  console.log(JSON.stringify(payload));
}

function expectedRefreshJobCount(sourceSlug) {
  if (sourceSlug === SHOWROOM_SOURCE_SLUG) {
    return SHOWROOM_CHUNK_COUNT + 1;
  }
  if (sourceSlug === LE_CENTERPIECE_SOURCE_SLUG) {
    return LE_CENTERPIECE_CHUNK_COUNT + 1;
  }
  if (sourceSlug === CHEZ_LAMOTHE_SOURCE_SLUG) {
    return CHEZ_LAMOTHE_CHUNK_COUNT + 1;
  }
  if (sourceSlug === MOSTLY_DANISH_SOURCE_SLUG) {
    return MOSTLY_DANISH_CHUNKS_PER_REFRESH;
  }
  return 1;
}

function expectedChunkIndexes(sourceSlug) {
  if (sourceSlug === SHOWROOM_SOURCE_SLUG) {
    return Array.from({ length: SHOWROOM_CHUNK_COUNT }, (_value, index) => index);
  }
  if (sourceSlug === LE_CENTERPIECE_SOURCE_SLUG) {
    return Array.from({ length: LE_CENTERPIECE_CHUNK_COUNT }, (_value, index) => index);
  }
  if (sourceSlug === CHEZ_LAMOTHE_SOURCE_SLUG) {
    return Array.from({ length: CHEZ_LAMOTHE_CHUNK_COUNT }, (_value, index) => index);
  }
  return [];
}

function missingExpectedChunkIndexes(sourceSlug, jobs) {
  const expected = expectedChunkIndexes(sourceSlug);
  if (expected.length === 0 || jobs.every((job) => job.chunk_index == null)) {
    return [];
  }
  const observed = new Set(
    jobs
      .map((job) => Number(job.chunk_index))
      .filter((chunkIndex) => Number.isInteger(chunkIndex) && chunkIndex >= 0),
  );
  return expected.filter((chunkIndex) => !observed.has(chunkIndex));
}

function chunkIndexesForJobs(jobs) {
  return jobs
    .map((job) => job.chunk_index)
    .filter((chunkIndex) => chunkIndex !== null && chunkIndex !== undefined);
}

function summarizeJobStatuses(jobs) {
  const counts = {};
  for (const job of jobs) {
    counts[job.status] = (counts[job.status] || 0) + 1;
  }
  return counts;
}

function hasSuspiciousHiddenCount(job) {
  const listingsFound = Number(job.listings_found) || 0;
  const hiddenCount = Number(job.hidden_count) || 0;
  if (hiddenCount < HIDDEN_SPIKE_MIN_COUNT) {
    return false;
  }
  if (listingsFound <= 0) {
    return true;
  }
  return hiddenCount / listingsFound >= HIDDEN_SPIKE_MIN_RATIO;
}

async function markStaleRefreshJobs(env, checkedAt, staleCutoff) {
  const staleMessage = `Marked stale by refresh monitor at ${checkedAt}`;
  const result = await env.DB.prepare(
    `
    UPDATE refresh_jobs
    SET status = 'stale',
        finished_at = ?,
        error_message = CASE
          WHEN error_message = '' THEN ?
          ELSE error_message
        END
    WHERE status = 'running'
      AND started_at < ?
    `,
  )
    .bind(checkedAt, staleMessage, staleCutoff)
    .run();
  const changes = result.meta?.changes || 0;
  if (changes > 0) {
    console.warn(
      JSON.stringify({
        event: "refresh_jobs_marked_stale",
        checked_at: checkedAt,
        stale_cutoff: staleCutoff,
        count: changes,
      }),
    );
  }
}

async function fetchContainer(request, env) {
  const started = Date.now();
  const url = new URL(request.url);
  const container = env.MCM_CONTAINER.getByName(CONTAINER_INSTANCE_NAME);
  const retryRequest = request.clone();
  let retriedAfterStart = false;
  let response = await container.fetch(request);
  if (await shouldRetryAfterContainerStart(response)) {
    retriedAfterStart = true;
    console.warn(
      JSON.stringify({
        event: "worker_container_start_retry",
        method: request.method,
        path: url.pathname,
        cf_ray: request.headers.get("cf-ray"),
        colo: request.cf?.colo,
      }),
    );
    await startContainer(container, retryRequest.signal);
    response = await container.fetch(retryRequest);
  }
  const elapsedMs = Date.now() - started;
  console.log(
    JSON.stringify({
      event: "worker_container_fetch_timing",
      method: request.method,
      path: url.pathname,
      status: response.status,
      elapsed_ms: elapsedMs,
      retried_after_start: retriedAfterStart,
      cf_ray: request.headers.get("cf-ray"),
      colo: request.cf?.colo,
    }),
  );
  const headers = new Headers(response.headers);
  if (env.MCM_EXPOSE_TIMING_HEADERS === "1") {
    headers.set("X-MCM-Worker-Container-Fetch-Ms", String(elapsedMs));
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function shouldRetryAfterContainerStart(response) {
  if (response.status !== 500) {
    return false;
  }
  const body = await response.clone().text();
  const normalizedBody = body.toLowerCase();
  return CONTAINER_START_RETRY_PATTERNS.some((pattern) => normalizedBody.includes(pattern));
}

async function startContainer(container, abortSignal) {
  if (typeof container.startAndWaitForPorts === "function") {
    await container.startAndWaitForPorts({
      ports: [CONTAINER_PORT],
      cancellationOptions: {
        abort: abortSignal,
        instanceGetTimeoutMS: 10_000,
        portReadyTimeoutMS: 30_000,
        waitInterval: 500,
      },
    });
    return;
  }
  if (typeof container.start === "function") {
    await container.start();
  }
}
