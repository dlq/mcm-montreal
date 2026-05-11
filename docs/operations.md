# Operations Runbook

This runbook covers the `0.1.x` production baseline for Montreal MCM.

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

## Deploy

```bash
npm run deploy
```

## Health Checks

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

## Refresh Behavior

Cloudflare cron triggers one container request per launch source. Each source refresh records a row
in `refresh_jobs`, plus the existing `crawl_runs` and `crawl_failures` records.

Conservative source failure behavior is intentional: if a source fetch or parser fails and the shop
already has records, fallback data is not treated as authoritative and existing listings are not
deactivated.
