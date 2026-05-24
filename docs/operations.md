# Operations Runbook

This runbook covers the production baseline for Montreal MCM.

## Before Deploy

Run local checks:

```bash
uv run python -m unittest tests.test_app
npm run lint
npm run deploy:dry-run
```

Confirm required Cloudflare secrets exist:

```bash
npx wrangler secret list
```

Required secrets:

- `MCM_SECRET_KEY`
- `D1_BRIDGE_TOKEN`
- `MCM_ADMIN_TOKEN`
- `MCM_MANUAL_REFRESH_TOKEN` for the guarded Worker refresh-now endpoint

Confirm required Cloudflare queues exist:

```bash
npm run cf:queues:list
```

Create them once if they are missing:

```bash
npm run cf:queue:create:refresh
npm run cf:queue:create:refresh-dlq
```

Optional Worker variables:

- `D1_BRIDGE_URL`: override the default Worker-to-D1 bridge URL injected into the container
- `APEX_HOSTNAME`: override the apex hostname used for redirects
- `WWW_HOSTNAME`: override the `www` hostname redirected to the apex hostname

## Deploy

```bash
npm run deploy
```

## Health Checks

Run the production health script:

```bash
npm run prod:health
```

If `MCM_ADMIN_TOKEN` is set in the shell, the script also verifies authenticated deep health. Without
that variable, it still verifies that admin health is not public.

For non-default deployments, override `MCM_BASE_URL`, `MCM_APEX_URL`, `MCM_WWW_URL`, and
`MCM_D1_DATABASE`.

Process health does not require D1 or admin auth:

```bash
curl -fsS https://montreal-mcm.dalaque.workers.dev/healthz
```

Deep health checks D1 and requires the admin token:

```bash
curl -fsS \
  -H "Authorization: Bearer $MCM_ADMIN_TOKEN" \
  https://montreal-mcm.dalaque.workers.dev/admin/healthz
```

Check the public homepage:

```bash
curl -fsS -o /tmp/mcm-home.html https://montreal-mcm.dalaque.workers.dev/
```

Force one source through the same queue-backed refresh path used by the morning cron:

```bash
curl -fsS \
  -X POST \
  -H "Authorization: Bearer $MCM_MANUAL_REFRESH_TOKEN" \
  "https://montreal-mcm.dalaque.workers.dev/internal/refresh-now?source=morceau"
```

Omit `source` to enqueue all active sources.

The apex custom domain should render the app, and `www` should redirect to the apex domain:

```bash
curl -I -fsS https://montrealmcm.ca/
curl -I -fsS https://www.montrealmcm.ca/
```

Check D1 directly:

```bash
npx wrangler d1 execute montreal-mcm --remote --command "SELECT COUNT(*) AS listings FROM listings;"
```

## Backup

Before write-heavy changes or source refresh experiments, export D1:

```bash
mkdir -p backups
npm run d1:backup
```

The `backups/` directory is ignored by git.

## Bad Deploy Recovery

1. Confirm whether `/healthz` or only `/admin/healthz` is failing.
2. Check Worker and container logs in Cloudflare.
3. If D1 is failing but `/healthz` works, verify `D1_BRIDGE_TOKEN` and the D1 binding.
4. Revert to the previous known-good commit and redeploy:

```bash
git revert <bad-commit>
npm run deploy
```

5. Re-run the health checks above.

## Admin Access

Admin routes are public only when `MCM_ADMIN_TOKEN` is unset, which should be local development only.
In production, authenticate with one of:

- `Authorization: Bearer <token>`
- `X-MCM-Admin-Token: <token>`
- HTTP Basic auth using any username and the token as the password

If a production admin token is generated directly into Cloudflare and is not stored in a password
manager, rotate it to a new value that the owner controls:

```bash
openssl rand -hex 32
npx wrangler secret put MCM_ADMIN_TOKEN
npm run deploy
npm run prod:health
```

Store the generated value outside the repository. Do not commit it to `.env`, docs, shell history,
or source files.

## Refresh Behavior

Cloudflare cron enqueues one refresh message per active source. A Queue consumer processes one
message at a time, calls the private Worker-to-container refresh endpoint, and retries failures
before sending exhausted messages to `montreal-mcm-refresh-dlq`.

Each completed source refresh records a row in `refresh_jobs`, plus the existing `crawl_runs` and
`crawl_failures` records. Chunked sources also record `chunk_index` and `entry_url` so monitor logs
and admin status can identify the specific chunk involved.

Conservative source failure behavior is intentional: if a source fetch or parser fails and the shop
already has records, fallback data is not treated as authoritative and existing listings are not
deactivated.

A second cron runs two hours after the daily refresh window and logs a `refresh_job_monitor` event.
It checks D1 for:

- missing daily refresh jobs, including missing chunk rows for chunked sources
- non-success refresh jobs
- jobs still marked `running` after stale-job marking
- suspicious hidden-listing spikes
- unknown source slugs in the refresh ledger

This is log-only monitoring; external alerting can be added later if needed.
