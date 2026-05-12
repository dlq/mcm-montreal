import { Container } from "@cloudflare/containers";

const CONTAINER_INSTANCE_NAME = "web-d1";
const DEFAULT_APEX_HOSTNAME = "montrealmcm.ca";
const DEFAULT_WWW_HOSTNAME = "www.montrealmcm.ca";
const DEFAULT_D1_BRIDGE_URL = "https://montreal-mcm.dalaque.workers.dev/internal/d1/query";
const REFRESH_CRON = "23 9 * * *";
const REFRESH_MONITOR_CRON = "23 11 * * *";
const SOURCE_SLUGS = ["morceau", "showroom-montreal", "montreal-moderne", "le-centerpiece"];
const SHOWROOM_SOURCE_SLUG = "showroom-montreal";
const SHOWROOM_CHUNK_COUNT = 12;
const RETRY_DELAY_SECONDS = 300;
const STALE_REFRESH_JOB_AGE_MS = 90 * 60 * 1000;

export class McmContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "30m";
  pingEndpoint = "/readyz";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      APP_HOST: "0.0.0.0",
      APP_PORT: "8080",
      D1_BRIDGE_URL: env.D1_BRIDGE_URL || DEFAULT_D1_BRIDGE_URL,
      D1_BRIDGE_TOKEN: env.D1_BRIDGE_TOKEN || "",
      MCM_ADMIN_TOKEN: env.MCM_ADMIN_TOKEN || "",
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
  const token = env.MCM_MANUAL_REFRESH_TOKEN || env.MCM_ADMIN_TOKEN || "";
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
  if (sourceSlug === SHOWROOM_SOURCE_SLUG) {
    return Array.from({ length: SHOWROOM_CHUNK_COUNT }, (_value, chunkIndex) =>
      refreshMessageBody(sourceSlug, trigger, chunkIndex),
    );
  }
  return [refreshMessageBody(sourceSlug, trigger)];
}

function refreshMessageBody(sourceSlug, trigger, chunkIndex = null) {
  const body = {
    source_slug: sourceSlug,
    trigger,
    enqueued_at: new Date().toISOString(),
    message_id: crypto.randomUUID(),
  };
  if (chunkIndex !== null) {
    body.chunk_index = chunkIndex;
  }
  return { body };
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
    const cronPath = refreshCronPath(sourceSlug, body.chunk_index);
    const result = await callContainerCron(env, cronPath);
    console.log(
      JSON.stringify({
        event: "refresh_queue_completed",
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
  return `/cron/refresh/${sourceSlug}`;
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
    SELECT source_slug, status, started_at, finished_at, error_message, hidden_count
    FROM refresh_jobs
    WHERE started_at >= ?
    ORDER BY started_at DESC
    `,
  )
    .bind(`${today}T00:00:00`)
    .all();
  const latestJobs = new Map();
  for (const job of result.results || []) {
    if (!latestJobs.has(job.source_slug)) {
      latestJobs.set(job.source_slug, job);
    }
  }

  const warnings = [];
  for (const sourceSlug of SOURCE_SLUGS) {
    const job = latestJobs.get(sourceSlug);
    if (!job) {
      warnings.push({ source_slug: sourceSlug, reason: "missing_refresh_job" });
      continue;
    }
    if (job.status !== "success") {
      warnings.push({
        source_slug: sourceSlug,
        reason: "refresh_job_not_success",
        status: job.status,
        started_at: job.started_at,
        finished_at: job.finished_at,
        error_message: job.error_message,
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
  const response = await container.fetch(request);
  const elapsedMs = Date.now() - started;
  console.log(
    JSON.stringify({
      event: "worker_container_fetch_timing",
      method: request.method,
      path: url.pathname,
      status: response.status,
      elapsed_ms: elapsedMs,
      cf_ray: request.headers.get("cf-ray"),
      colo: request.cf?.colo,
    }),
  );
  const headers = new Headers(response.headers);
  headers.set("X-MCM-Worker-Container-Fetch-Ms", String(elapsedMs));
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
