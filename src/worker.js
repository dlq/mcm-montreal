import { Container } from "@cloudflare/containers";

const CONTAINER_INSTANCE_NAME = "web-d1";
const SOURCE_SLUGS = ["morceau", "showroom-montreal", "montreal-moderne", "le-centerpiece"];

export class McmContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "30m";
  pingEndpoint = "/healthz";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      APP_HOST: "0.0.0.0",
      APP_PORT: "8080",
      D1_BRIDGE_URL: "https://montreal-mcm.dalaque.workers.dev/internal/d1/query",
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
    if (url.pathname === "/internal/d1/query") {
      return queryD1(request, env);
    }
    if (url.pathname.startsWith("/internal/")) {
      return new Response("Not found", { status: 404 });
    }
    if (url.pathname.startsWith("/cron/")) {
      return new Response("Not found", { status: 404 });
    }
    return fetchContainer(request, env);
  },

  async scheduled(_controller, env, ctx) {
    for (const sourceSlug of SOURCE_SLUGS) {
      ctx.waitUntil(callContainerCron(env, `/cron/refresh/${sourceSlug}`));
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
