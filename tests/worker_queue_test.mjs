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
  const { env, queue } = makeEnv();
  const ctx = makeCtx();

  await worker.scheduled({ cron: "23 9 * * *" }, env, ctx);
  assert.equal(ctx.promises.length, 1);
  await Promise.all(ctx.promises);

  assert.equal(queue.sentBatches.length, 1);
  const messages = queue.sentBatches[0];
  assert.equal(messages.length, 15);
  assert.deepEqual(
    messages.map((message) => message.body.source_slug),
    [
      "morceau",
      ...Array.from({ length: 12 }, () => "showroom-montreal"),
      "montreal-moderne",
      "le-centerpiece",
    ],
  );
  assert.deepEqual(
    messages
      .filter((message) => message.body.source_slug === "showroom-montreal")
      .map((message) => message.body.chunk_index),
    Array.from({ length: 12 }, (_value, index) => index),
  );
  assert(messages.every((message) => message.body.trigger === "scheduled_refresh"));
  assert(messages.every((message) => message.body.message_id));
  assert(messages.every((message) => message.body.enqueued_at));
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
    new Request("https://montreal-mcm.test/internal/refresh-now", {
      method: "POST",
      headers: { Authorization: "Bearer refresh-token" },
    }),
    env,
  );

  assert.equal(response.status, 202);
  assert.equal(queue.sentBatches.length, 1);
  assert.equal(queue.sentBatches[0].length, 15);
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
  const message = makeMessage({ source_slug: "not-real" });

  await worker.queue({ messages: [message] }, env);

  assert.equal(message.acked, true);
  assert.equal(message.retried, null);
  assert.equal(containerRequests.length, 0);
}

console.log("worker queue tests passed");
