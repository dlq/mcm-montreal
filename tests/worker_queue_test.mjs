import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

async function loadWorker() {
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
  return module.namespace.default;
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
  return {
    env: {
      REFRESH_QUEUE: queue,
      MCM_MANUAL_REFRESH_TOKEN: "refresh-token",
      MCM_CONTAINER: {
        getByName(name) {
          assert.equal(name, "web-d1");
          return {
            async fetch(request) {
              containerRequests.push(request);
              return containerResponse;
            },
          };
        },
      },
    },
    queue,
    containerRequests,
  };
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

function makeDb(results = []) {
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
          return { meta: { changes: 2 } };
        },
      };
    },
  };
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

const worker = await loadWorker();

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

  await worker.scheduled({ cron: "23 11 * * *" }, { DB: db }, ctx);
  assert.equal(ctx.promises.length, 1);
  await Promise.all(ctx.promises);

  assert.equal(db.calls.length, 2);
  assert.match(db.calls[0].sql, /UPDATE refresh_jobs/);
  assert.match(db.calls[0].sql, /status = 'stale'/);
  assert.equal(db.calls[0].method, "run");
  assert.equal(db.calls[0].params.length, 3);
  assert.match(db.calls[0].params[1], /Marked stale by refresh monitor/);
  assert.equal(db.calls[1].method, "all");
  assert.match(db.calls[1].sql, /SELECT source_slug/);
}

{
  const { env, queue } = makeEnv();
  const ctx = makeCtx();

  await worker.scheduled({ cron: "23 9 * * *" }, env, ctx);
  assert.equal(ctx.promises.length, 1);
  await Promise.all(ctx.promises);

  assert.equal(queue.sentBatches.length, 1);
  const messages = queue.sentBatches[0];
  assert.equal(messages.length, 34);
  assert.deepEqual(
    messages.map((message) => message.body.source_slug),
    [
      "morceau",
      ...Array.from({ length: 12 }, () => "showroom-montreal"),
      "montreal-moderne",
      ...Array.from({ length: 7 }, () => "le-centerpiece"),
      "maison-singulier",
      "yardsale-vintage",
      "bond-vintage",
      ...Array.from({ length: 10 }, () => "chez-lamothe"),
    ],
  );
  assert.deepEqual(
    messages
      .filter((message) => message.body.source_slug === "showroom-montreal")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 12 }, (_value, index) => index),
  );
  assert.deepEqual(
    messages
      .filter((message) => message.body.source_slug === "le-centerpiece")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 7 }, (_value, index) => index),
  );
  assert.deepEqual(
    messages
      .filter((message) => message.body.source_slug === "chez-lamothe")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 10 }, (_value, index) => index),
  );
  assert(messages.every((message) => message.body.trigger === "scheduled_refresh"));
  assert(messages.every((message) => message.body.message_id));
  assert(messages.every((message) => message.body.enqueued_at));
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
  assert.equal(queue.sentBatches[0].length, 7);
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.source_slug),
    Array.from({ length: 7 }, () => "le-centerpiece"),
  );
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.chunk_index),
    Array.from({ length: 7 }, (_value, index) => index),
  );
  assert.equal(queue.sentBatches[0][0].body.trigger, "manual_refresh_now");
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
  assert.equal(queue.sentBatches[0].length, 12);
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.source_slug),
    Array.from({ length: 12 }, () => "showroom-montreal"),
  );
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.chunk_index),
    Array.from({ length: 12 }, (_value, index) => index),
  );
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
  assert.equal(queue.sentBatches[0].length, 10);
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.source_slug),
    Array.from({ length: 10 }, () => "chez-lamothe"),
  );
  assert.deepEqual(
    queue.sentBatches[0].map((message) => message.body.chunk_index),
    Array.from({ length: 10 }, (_value, index) => index),
  );
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
  assert.equal(queue.sentBatches[0].length, 34);
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
    chunk_index: 9,
    trigger: "test",
    message_id: "message-7",
  });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 1);
  assert.equal(
    new URL(containerRequests[0].url).pathname,
    "/cron/refresh/chez-lamothe/chunk/9",
  );
}

{
  const { env, containerRequests } = makeEnv();
  const message = makeMessage({
    source_slug: "chez-lamothe",
    chunk_index: 10,
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
