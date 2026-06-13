import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

async function loadWorkerModule() {
  const source = await readFile(new URL("../src/worker.js", import.meta.url), "utf8");
  const module = new vm.SourceTextModule(source, {
    initializeImportMeta(meta) {
      meta.url = new URL("../src/worker.js", import.meta.url).href;
    },
  });
  await module.link(async (specifier) => {
    if (specifier !== "@cloudflare/containers") {
      throw new Error(`Unexpected import: ${specifier}`);
    }
    const containerModule = new vm.SyntheticModule(["Container"], function () {
      this.setExport("Container", class Container {});
    });
    return containerModule;
  });
  await module.evaluate();
  return module.namespace;
}

function makeQueue() {
  return {
    sentBatches: [],
    async sendBatch(messages) {
      this.sentBatches.push(messages);
      return { metadata: { metrics: {} } };
    },
  };
}

function makeEnv(containerResponse = new Response("ok", { status: 200 })) {
  const queue = makeQueue();
  const containerRequests = [];
  const containerStartCalls = [];
  const containerResponses = Array.isArray(containerResponse)
    ? [...containerResponse]
    : [containerResponse];
  return {
    env: {
      REFRESH_QUEUE: queue,
      MCM_MANUAL_REFRESH_TOKEN: "refresh-token",
      MCM_CONTAINER: {
        getByName(name) {
          assert.equal(name, "web-d1-v11");
          return {
            async fetch(request) {
              containerRequests.push(request);
              return containerResponses.shift() || new Response("ok", { status: 200 });
            },
            async startAndWaitForPorts(options) {
              containerStartCalls.push(options);
            },
          };
        },
      },
    },
    queue,
    containerRequests,
    containerStartCalls,
  };
}

function makeEnvWithSecrets(secrets, containerResponse = new Response("ok", { status: 200 })) {
  const context = makeEnv(containerResponse);
  Object.assign(context.env, secrets);
  return context;
}

function makeCtx() {
  const promises = [];
  return {
    promises,
    waitUntil(promise) {
      promises.push(promise);
    },
  };
}

function makeDb(results = [], runChanges = 2) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      const call = { sql, params: [], method: "" };
      calls.push(call);
      return {
        bind(...params) {
          call.params = params;
          return this;
        },
        async all() {
          call.method = "all";
          return { results };
        },
        async run() {
          call.method = "run";
          return { meta: { changes: runChanges } };
        },
      };
    },
  };
}

async function captureConsole(callback) {
  const originalLog = console.log;
  const originalWarn = console.warn;
  const logs = [];
  const warnings = [];
  console.log = (message) => logs.push(message);
  console.warn = (message) => warnings.push(message);
  try {
    await callback();
  } finally {
    console.log = originalLog;
    console.warn = originalWarn;
  }
  return { logs, warnings };
}

function refreshJob(sourceSlug, overrides = {}) {
  return {
    source_slug: sourceSlug,
    status: "success",
    started_at: "2026-05-12T09:24:00+00:00",
    finished_at: "2026-05-12T09:25:00+00:00",
    chunk_index: null,
    entry_url: "",
    error_message: "",
    hidden_count: 0,
    listings_found: 10,
    new_count: 0,
    reconciled_count: 0,
    ...overrides,
  };
}

function refreshJobs(sourceSlug, count, overrides = {}) {
  return Array.from({ length: count }, (_value, index) =>
    refreshJob(sourceSlug, {
      started_at: `2026-05-12T09:${String(24 + index).padStart(2, "0")}:00+00:00`,
      ...overrides,
    }),
  );
}

function refreshChunkJobs(sourceSlug, chunkIndexes, overrides = {}) {
  return chunkIndexes.map((chunkIndex) =>
    refreshJob(sourceSlug, {
      chunk_index: chunkIndex,
      started_at: `2026-05-12T09:${String(24 + chunkIndex).padStart(2, "0")}:00+00:00`,
      ...overrides,
    }),
  );
}

function makeMessage(body, attempts = 1) {
  return {
    body,
    attempts,
    acked: false,
    retried: null,
    ack() {
      this.acked = true;
    },
    retry(options) {
      this.retried = options;
    },
  };
}

const workerModule = await loadWorkerModule();
const worker = workerModule.default;

{
  const container = new workerModule.McmContainer({}, { MCM_EXPOSE_TIMING_HEADERS: "1" });

  assert.equal(container.envVars.MCM_EXPOSE_TIMING_HEADERS, "1");
}

{
  const db = makeDb([
    {
      source_slug: "morceau",
      status: "success",
      started_at: "2026-05-12T09:24:00+00:00",
      finished_at: "2026-05-12T09:25:00+00:00",
      error_message: "",
      hidden_count: 0,
    },
    {
      source_slug: "showroom-montreal",
      status: "success",
      started_at: "2026-05-12T09:26:00+00:00",
      finished_at: "2026-05-12T09:30:00+00:00",
      error_message: "",
      hidden_count: 0,
    },
    {
      source_slug: "montreal-moderne",
      status: "success",
      started_at: "2026-05-12T09:31:00+00:00",
      finished_at: "2026-05-12T09:34:00+00:00",
      error_message: "",
      hidden_count: 0,
    },
    {
      source_slug: "le-centerpiece",
      status: "stale",
      started_at: "2026-05-12T09:35:00+00:00",
      finished_at: "2026-05-12T11:23:00+00:00",
      error_message: "Marked stale",
      hidden_count: 0,
    },
  ]);
  const ctx = makeCtx();

  const captured = await captureConsole(async () => {
    await worker.scheduled({ cron: "23 11 * * *" }, { DB: db }, ctx);
    assert.equal(ctx.promises.length, 1);
    await Promise.all(ctx.promises);
  });

  assert.equal(db.calls.length, 2);
  assert.match(db.calls[0].sql, /UPDATE refresh_jobs/);
  assert.match(db.calls[0].sql, /status = 'stale'/);
  assert.equal(db.calls[0].method, "run");
  assert.equal(db.calls[0].params.length, 3);
  assert.match(db.calls[0].params[1], /Marked stale by refresh monitor/);
  assert.equal(db.calls[1].method, "all");
  assert.match(db.calls[1].sql, /SELECT source_slug/);
  const monitorWarning = captured.warnings
    .map((message) => JSON.parse(message))
    .find((payload) => payload.event === "refresh_job_monitor");
  assert(monitorWarning);
  assert(monitorWarning.warnings.some((warning) => warning.reason === "missing_refresh_jobs"));
  assert(
    monitorWarning.warnings.some(
      (warning) =>
        warning.source_slug === "showroom-montreal" &&
        warning.expected_jobs === 13 &&
        warning.observed_jobs === 1,
    ),
  );
}

{
  const db = makeDb(
    [
      ...refreshJobs("morceau", 1),
      ...refreshJobs("showroom-montreal", 13),
      ...refreshJobs("montreal-moderne", 1),
      ...refreshJobs("le-centerpiece", 8),
      ...refreshJobs("maison-singulier", 1),
      ...refreshJobs("yardsale-vintage", 1),
      ...refreshJobs("chez-lamothe", 21),
      ...refreshJobs("habitat-mobilier", 1),
      ...refreshJobs("green-wall-vintage", 1),
      ...refreshJobs("mostly-danish", 5),
    ],
    0,
  );
  const ctx = makeCtx();

  const captured = await captureConsole(async () => {
    await worker.scheduled({ cron: "23 11 * * *" }, { DB: db }, ctx);
    assert.equal(ctx.promises.length, 1);
    await Promise.all(ctx.promises);
  });

  assert.equal(captured.warnings.length, 0);
  const monitorLog = captured.logs.map((message) => JSON.parse(message))[0];
  assert.equal(monitorLog.event, "refresh_job_monitor");
  assert.deepEqual(monitorLog.warnings, []);
}

{
  const db = makeDb(
    [
      ...refreshJobs("morceau", 1),
      ...refreshChunkJobs(
        "showroom-montreal",
        Array.from({ length: 12 }, (_value, index) => index).filter((index) => index !== 7),
      ),
      refreshJob("showroom-montreal"),
      ...refreshJobs("montreal-moderne", 1),
      ...refreshJobs("le-centerpiece", 8),
      ...refreshJobs("maison-singulier", 1),
      ...refreshJobs("yardsale-vintage", 1),
      ...refreshJobs("chez-lamothe", 21),
      ...refreshJobs("habitat-mobilier", 1),
      ...refreshJobs("green-wall-vintage", 1),
      ...refreshJobs("mostly-danish", 5),
    ],
    0,
  );
  const ctx = makeCtx();

  const captured = await captureConsole(async () => {
    await worker.scheduled({ cron: "23 11 * * *" }, { DB: db }, ctx);
    assert.equal(ctx.promises.length, 1);
    await Promise.all(ctx.promises);
  });

  const monitorWarning = captured.warnings.map((message) => JSON.parse(message))[0];
  const missingWarning = monitorWarning.warnings.find(
    (warning) => warning.source_slug === "showroom-montreal",
  );
  assert.equal(missingWarning.reason, "missing_refresh_jobs");
  assert.deepEqual(missingWarning.missing_chunk_indexes, [7]);
}

{
  const db = makeDb(
    [
      ...refreshJobs("morceau", 1, { listings_found: 100, hidden_count: 50 }),
      ...refreshJobs("showroom-montreal", 13),
      ...refreshJobs("montreal-moderne", 1),
      ...refreshJobs("le-centerpiece", 8),
      ...refreshJobs("maison-singulier", 1),
      ...refreshJobs("yardsale-vintage", 1),
      ...refreshJobs("chez-lamothe", 21),
      ...refreshJobs("habitat-mobilier", 1),
      ...refreshJobs("green-wall-vintage", 1),
      ...refreshJobs("mostly-danish", 5),
    ],
    0,
  );
  const ctx = makeCtx();

  const captured = await captureConsole(async () => {
    await worker.scheduled({ cron: "23 11 * * *" }, { DB: db }, ctx);
    assert.equal(ctx.promises.length, 1);
    await Promise.all(ctx.promises);
  });

  const monitorWarning = captured.warnings.map((message) => JSON.parse(message))[0];
  assert.equal(monitorWarning.event, "refresh_job_monitor");
  assert(
    monitorWarning.warnings.some(
      (warning) =>
        warning.source_slug === "morceau" && warning.reason === "suspicious_hidden_count",
    ),
  );
}

{
  const { env, queue } = makeEnv();
  const ctx = makeCtx();

  await worker.scheduled({ cron: "23 9 * * *" }, env, ctx);
  assert.equal(ctx.promises.length, 1);
  await Promise.all(ctx.promises);

  assert.equal(queue.sentBatches.length, 1);
  const messages = queue.sentBatches[0];
  assert.equal(messages.length, 53);
  assert.deepEqual(
    messages.map((message) => message.body.source_slug),
    [
      "morceau",
      ...Array.from({ length: 12 }, () => "showroom-montreal"),
      "showroom-montreal",
      "montreal-moderne",
      ...Array.from({ length: 7 }, () => "le-centerpiece"),
      "le-centerpiece",
      "maison-singulier",
      "yardsale-vintage",
      ...Array.from({ length: 20 }, () => "chez-lamothe"),
      "chez-lamothe",
      "habitat-mobilier",
      "green-wall-vintage",
      ...Array.from({ length: 5 }, () => "mostly-danish"),
    ],
  );
  assert.deepEqual(
    messages
      .filter((message) => message.body.source_slug === "showroom-montreal")
      .filter((message) => message.body.action === "refresh")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 12 }, (_value, index) => index),
  );
  assert.deepEqual(
    messages
      .filter((message) => message.body.source_slug === "le-centerpiece")
      .filter((message) => message.body.action === "refresh")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 7 }, (_value, index) => index),
  );
  assert.deepEqual(
    messages
      .filter((message) => message.body.source_slug === "chez-lamothe")
      .filter((message) => message.body.action === "refresh")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 20 }, (_value, index) => index),
  );
  const mostlyDanishChunkIndexes = messages
    .filter((message) => message.body.source_slug === "mostly-danish")
    .map((message) => message.body.chunk_index);
  assert.equal(mostlyDanishChunkIndexes.length, 5);
  assert.equal(new Set(mostlyDanishChunkIndexes).size, 5);
  assert(mostlyDanishChunkIndexes.every((chunkIndex) => chunkIndex >= 0 && chunkIndex < 30));
  assert(messages.every((message) => message.body.trigger === "scheduled_refresh"));
  assert(messages.every((message) => message.body.message_id));
  assert(messages.every((message) => message.body.enqueued_at));
  assert.equal(messages.filter((message) => message.body.action === "reconcile").length, 3);
}

{
  const { env, queue } = makeEnv();
  const response = await worker.fetch(
    new Request("https://montreal-mcm.test/internal/refresh-now?source=le-centerpiece", {
      method: "POST",
      headers: { Authorization: "Bearer refresh-token" },
    }),
    env,
  );

  assert.equal(response.status, 202);
  assert.equal(queue.sentBatches.length, 1);
  assert.equal(queue.sentBatches[0].length, 8);
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.source_slug),
    Array.from({ length: 8 }, () => "le-centerpiece"),
  );
  assert.deepEqual(
    queue.sentBatches[0]
      .filter((message) => message.body.action === "refresh")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 7 }, (_value, index) => index),
  );
  assert.equal(queue.sentBatches[0].at(-1).body.action, "reconcile");
  assert.equal(queue.sentBatches[0][0].body.trigger, "manual_refresh_now");
}

{
  const { env, queue } = makeEnvWithSecrets({
    MCM_MANUAL_REFRESH_TOKEN: "",
    MCM_ADMIN_TOKEN: "admin-token",
  });
  const response = await worker.fetch(
    new Request("https://montreal-mcm.test/internal/refresh-now?source=morceau", {
      method: "POST",
      headers: { Authorization: "Bearer admin-token" },
    }),
    env,
  );

  assert.equal(response.status, 404);
  assert.equal(queue.sentBatches.length, 0);
}

{
  const { env, queue } = makeEnv();
  const response = await worker.fetch(
    new Request("https://montreal-mcm.test/internal/refresh-now?source=showroom-montreal", {
      method: "POST",
      headers: { Authorization: "Bearer refresh-token" },
    }),
    env,
  );

  assert.equal(response.status, 202);
  assert.equal(queue.sentBatches.length, 1);
  assert.equal(queue.sentBatches[0].length, 13);
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.source_slug),
    Array.from({ length: 13 }, () => "showroom-montreal"),
  );
  assert.deepEqual(
    queue.sentBatches[0]
      .filter((message) => message.body.action === "refresh")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 12 }, (_value, index) => index),
  );
  assert.equal(queue.sentBatches[0].at(-1).body.action, "reconcile");
  assert.equal(queue.sentBatches[0][0].body.trigger, "manual_refresh_now");
}

{
  const { env, queue } = makeEnv();
  const response = await worker.fetch(
    new Request("https://montreal-mcm.test/internal/refresh-now?source=chez-lamothe", {
      method: "POST",
      headers: { Authorization: "Bearer refresh-token" },
    }),
    env,
  );

  assert.equal(response.status, 202);
  assert.equal(queue.sentBatches.length, 1);
  assert.equal(queue.sentBatches[0].length, 21);
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.source_slug),
    Array.from({ length: 21 }, () => "chez-lamothe"),
  );
  assert.deepEqual(
    queue.sentBatches[0]
      .filter((message) => message.body.action === "refresh")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 20 }, (_value, index) => index),
  );
  assert.equal(queue.sentBatches[0].at(-1).body.action, "reconcile");
  assert.equal(queue.sentBatches[0][0].body.trigger, "manual_refresh_now");
}

{
  const { env, queue } = makeEnv();
  const response = await worker.fetch(
    new Request("https://montreal-mcm.test/internal/refresh-now", {
      method: "POST",
      headers: { Authorization: "Bearer refresh-token" },
    }),
    env,
  );

  assert.equal(response.status, 202);
  assert.equal(queue.sentBatches.length, 1);
  assert.equal(queue.sentBatches[0].length, 53);
}

{
  const { env, containerRequests, containerStartCalls } = makeEnv([
    new Response("Error proxying request to container: The container is not running, consider calling start()", {
      status: 500,
    }),
    new Response("started", { status: 200 }),
  ]);
  const response = await worker.fetch(new Request("https://montreal-mcm.test/"), env);

  assert.equal(response.status, 200);
  assert.equal(await response.text(), "started");
  assert.equal(containerRequests.length, 2);
  assert.equal(containerStartCalls.length, 1);
  assert.deepEqual(containerStartCalls[0].ports, [8080]);
}

{
  const { env } = makeEnv(new Response("ok", { status: 200 }));
  const response = await worker.fetch(new Request("https://montreal-mcm.test/"), env);

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("X-MCM-Worker-Container-Fetch-Ms"), null);
}

{
  const { env } = makeEnvWithSecrets(
    { MCM_EXPOSE_TIMING_HEADERS: "1" },
    new Response("ok", { status: 200 }),
  );
  const response = await worker.fetch(new Request("https://montreal-mcm.test/"), env);

  assert.equal(response.status, 200);
  assert.match(response.headers.get("X-MCM-Worker-Container-Fetch-Ms"), /^\d+$/);
}

{
  const { env } = makeEnv();
  const response = await worker.fetch(
    new Request("https://montreal-mcm.test/internal/refresh-now?source=not-real", {
      method: "POST",
      headers: { Authorization: "Bearer refresh-token" },
    }),
    env,
  );

  assert.equal(response.status, 404);
}

{
  const { env, containerRequests } = makeEnv(
    new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
  );
  const message = makeMessage({
    source_slug: "morceau",
    trigger: "test",
    message_id: "message-1",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 1);
  assert.equal(new URL(containerRequests[0].url).pathname, "/cron/refresh/morceau");
  assert.equal(containerRequests[0].method, "POST");
  assert.equal(containerRequests[0].headers.get("X-Cloudflare-Scheduled"), "1");
}

{
  const { env } = makeEnv(new Response("upstream failed", { status: 500 }));
  const message = makeMessage({
    source_slug: "showroom-montreal",
    chunk_index: 1,
    trigger: "test",
    message_id: "message-2",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, false);
  assert.deepEqual(message.retried, { delaySeconds: 300 });
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "showroom-montreal",
    chunk_index: 1,
    trigger: "test",
    message_id: "message-3",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 1);
  assert.equal(
    new URL(containerRequests[0].url).pathname,
    "/cron/refresh/showroom-montreal/chunk/1",
  );
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    action: "reconcile",
    source_slug: "showroom-montreal",
    trigger: "test",
    enqueued_at: "2026-05-29T09:23:00.000Z",
    message_id: "message-3b",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 1);
  const requestUrl = new URL(containerRequests[0].url);
  assert.equal(requestUrl.pathname, "/cron/reconcile/showroom-montreal");
  assert.equal(requestUrl.searchParams.get("since"), "2026-05-29T09:23:00.000Z");
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "showroom-montreal",
    chunk_index: 12,
    trigger: "test",
    message_id: "message-4",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, false);
  assert.deepEqual(message.retried, { delaySeconds: 300 });
  assert.equal(containerRequests.length, 0);
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "showroom-montreal",
    trigger: "test",
    message_id: "message-4b",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, false);
  assert.deepEqual(message.retried, { delaySeconds: 300 });
  assert.equal(containerRequests.length, 0);
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "le-centerpiece",
    chunk_index: 6,
    trigger: "test",
    message_id: "message-5",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 1);
  assert.equal(
    new URL(containerRequests[0].url).pathname,
    "/cron/refresh/le-centerpiece/chunk/6",
  );
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "le-centerpiece",
    chunk_index: 7,
    trigger: "test",
    message_id: "message-6",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, false);
  assert.deepEqual(message.retried, { delaySeconds: 300 });
  assert.equal(containerRequests.length, 0);
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "chez-lamothe",
    chunk_index: 19,
    trigger: "test",
    message_id: "message-7",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 1);
  assert.equal(
    new URL(containerRequests[0].url).pathname,
    "/cron/refresh/chez-lamothe/chunk/19",
  );
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "chez-lamothe",
    chunk_index: 20,
    trigger: "test",
    message_id: "message-8",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, false);
  assert.deepEqual(message.retried, { delaySeconds: 300 });
  assert.equal(containerRequests.length, 0);
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({ source_slug: "not-real" });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 0);
}

console.log("worker queue tests passed");
