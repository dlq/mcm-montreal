# Operations Runbook

This runbook covers the production baseline for Montreal MCM.

## Before Deploy

Run local checks:

```bash
uv run python -m unittest tests.test_app
npm run test:worker
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

## Secrets

Secrets are stored in Cloudflare Worker secrets and should also be stored by the owner outside the
repository, such as in a password manager. Do not commit secret values to `.env`, docs, shell
history, source files, screenshots, or issue comments.

Use distinct long random values for each secret:

```bash
openssl rand -hex 32
```

Token inventory:

- `MCM_SECRET_KEY`: Flask signing key for durable anonymous identity cookies. Rotating it signs out
  anonymous browser identities and can orphan existing favourites/saved searches unless a migration
  strategy is added. Rotate only for compromise or a planned identity reset. The Worker must pass
  this secret into the container through `McmContainer.envVars`; Flask D1 mode fails fast when the
  secret is missing so production cannot silently mint per-process anonymous identity cookies.
- `D1_BRIDGE_TOKEN`: private Worker-to-container token used by Flask to call the Worker D1 bridge.
  It is not for humans. Rotate after any suspected exposure, after changing bridge access patterns,
  or during scheduled credential hygiene.
- `MCM_ADMIN_TOKEN`: human/admin token for `/admin` and `/admin/healthz`. It should be separate
  from refresh and bridge tokens. Rotate when a person or machine that had access no longer needs
  it, after any suspected exposure, or during scheduled credential hygiene.
- `MCM_MANUAL_REFRESH_TOKEN`: operations token for the guarded Worker `/internal/refresh-now`
  endpoint. It should be separate from `MCM_ADMIN_TOKEN`; admin credentials must not be sufficient
  to force refreshes. Rotate after manual-refresh automation changes, any suspected exposure, or
  scheduled credential hygiene.

Set or rotate a secret:

```bash
npx wrangler secret put D1_BRIDGE_TOKEN
npm run deploy
npm run prod:health
```

Use the same pattern for `MCM_SECRET_KEY`, `MCM_ADMIN_TOKEN`, or `MCM_MANUAL_REFRESH_TOKEN`. After
rotating `MCM_MANUAL_REFRESH_TOKEN`, verify a single-source manual refresh with the new value:

```bash
curl -fsS \
  -X POST \
  -H "Authorization: Bearer $MCM_MANUAL_REFRESH_TOKEN" \
  "https://montreal-mcm.dalaque.workers.dev/internal/refresh-now?source=morceau"
```

After rotating `MCM_ADMIN_TOKEN`, verify deep health with the new value:

```bash
curl -fsS \
  -H "Authorization: Bearer $MCM_ADMIN_TOKEN" \
  https://montreal-mcm.dalaque.workers.dev/admin/healthz
```

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
- `MCM_EXPOSE_TIMING_HEADERS`: set to `1` only for temporary diagnostics if response timing headers
  are needed; request timings are logged even when these headers are off

## Deploy

```bash
npm run deploy
```

For normal deploys, prefer the full deploy above so Worker code and the Cloudflare Container image
roll forward together. After a successful deploy, run `npm run prod:health` and verify live
container instances:

```bash
npx wrangler containers list --json
npx wrangler containers instances a0332ee8-4188-4133-ab94-266ecfae1c4c --json
```

The current MCM container application id is `a0332ee8-4188-4133-ab94-266ecfae1c4c`, and the current
named production instance is `web-d1-v12`.

If the deploy builds locally but fails while pushing layers to Cloudflare's managed registry with a
transient error such as `tls: bad record MAC`, retry the full deploy first. If the required change is
Worker-only or only changes container environment variables consumed by the already-deployed image,
`npx wrangler deploy --containers-rollout none` can deploy the Worker without rebuilding or updating
the container image. Use this deliberately and document the resulting state, because Python code or
template changes still require a later successful full container rollout.

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

Audit recent refresh reliability:

```bash
npm run prod:refresh-audit
```

By default, this checks the last seven UTC days of `refresh_jobs`, current `running` jobs, recent
non-success jobs, and today's per-source coverage. Override `MCM_REFRESH_AUDIT_SINCE` or
`MCM_REFRESH_AUDIT_TODAY` for a different window.

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
4. If a deploy is correct but production still appears stale, check the named container instance in
   `src/worker.js`. Rotating the name, for example from `web-d1-v11` to `web-d1-v12`, forces a fresh
   container runtime after deployment.
5. Revert to the previous known-good commit and redeploy:

```bash
git revert <bad-commit>
npm run deploy
```

6. Re-run the health checks above.

### 2026-06-17 Deployment State

- Commits `fedce73` and `57de715` are pushed to `main`.
- `fedce73` passes `MCM_SECRET_KEY` from the Worker into the Flask container and adds a Flask
  D1-mode fail-fast guard for missing `MCM_SECRET_KEY`.
- `57de715` rotates the named production container instance to `web-d1-v12`.
- Full container deploy dry-run passed, but three full deploy attempts failed during Cloudflare
  registry layer pushes with `tls: bad record MAC`.
- `npx wrangler deploy --containers-rollout none` successfully deployed the Worker-side fix and
  rotation. Later docs-only Worker deploys may supersede the version id without changing the
  runtime app/container behavior.
- `npm run prod:health` passed after deployment, and an isolated live favourites
  save/read/remove workflow succeeded with a long-lived `mcm_anonymous_id` cookie.
- A future Python/template/container-image change should use a normal full `npm run deploy` once
  Cloudflare registry pushes are healthy again, so the image includes the Flask fail-fast guard in
  production.

## Admin Access

Admin routes are public only when `MCM_ADMIN_TOKEN` is unset, which should be local development only.
In production, authenticate with one of:

- `Authorization: Bearer <token>`
- `X-MCM-Admin-Token: <token>`
- HTTP Basic auth using any username and the token as the password

`MCM_ADMIN_TOKEN` does not authorize `/internal/refresh-now`; that endpoint requires
`MCM_MANUAL_REFRESH_TOKEN`.

## Refresh Behavior

Cloudflare cron enqueues one refresh message per active source. A Queue consumer processes one
message at a time, calls the private Worker-to-container refresh endpoint, and retries failures
before sending exhausted messages to `montreal-mcm-refresh-dlq`.

Each completed source refresh records a row in `refresh_jobs`, plus the existing `crawl_runs` and
`crawl_failures` records. Chunked sources also record `chunk_index` and `entry_url` so monitor logs
and admin status can identify the specific chunk involved.

Showroom Montreal, Le Centerpiece, and Chez Lamothe enqueue one guarded source-wide reconciliation
message after their chunk messages. Reconciliation only deactivates missing inventory when every
expected chunk for that source has a successful job newer than the queue batch timestamp. If any
chunk is missing or failed, reconciliation returns a warning and hides nothing. Mostly Danish is not
source-wide reconciled yet because production intentionally refreshes only 5 of its 30 bounded
chunks per run.

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

As of 2026-05-29 before source-wide reconciliation was added, the recent production refresh audit
showed no currently running jobs. Daily runs from 2026-05-22 through 2026-05-29 reached the then
expected 51 successful jobs. Recent warnings were transient source/network issues: Showroom Montreal
DNS failures on 2026-05-25 and 2026-05-26 later retried successfully, and Montreal Moderne had one
`IncompleteRead` warning on 2026-05-27. After source-wide reconciliation is deployed and BOND
Vintage is removed from the active source set, a normal full daily refresh enqueues 53 messages: 50
refresh messages plus 3 reconciliation messages.
