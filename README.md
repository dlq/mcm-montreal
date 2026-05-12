# Montreal MCM

Montreal MCM is a focused discovery site for Montreal-relevant mid-century modern furniture. It
scrapes a small set of direct shop sources, stores listings in SQLite locally, and serves a bilingual
English/French browsing UI with filters, favourites, listing detail pages, shop pages, and admin
review tools.

The product plan lives in [plan.md](plan.md), and source research lives in [research.md](research.md).

## Local Quick Start

Prerequisites:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js + npm for Biome, Wrangler, and frontend checks

Install dependencies:

```bash
uv sync --dev
npm install
```

Create or refresh local listing data:

```bash
uv run app.py refresh
```

Run the local app:

```bash
uv run app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Local development uses `data/mcm.db`. That file is local development data and is ignored by git.

## Useful Local Commands

Refresh all sources:

```bash
uv run app.py refresh
```

Refresh one source:

```bash
uv run app.py refresh morceau
uv run app.py refresh showroom-montreal
uv run app.py refresh montreal-moderne
uv run app.py refresh le-centerpiece
```

Run tests:

```bash
uv run python -m unittest tests.test_app
```

Run lint checks:

```bash
npm run lint
```

Format supported files:

```bash
npm run format
```

Install pre-commit hooks:

```bash
uv run pre-commit install
```

Run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## Project Shape

The app is a small Flask codebase with server-rendered Jinja templates, HTMX interactions, Tailwind
via CDN, and a little native JavaScript. Core Python code lives in `mcm/`, templates live in
`templates/`, static assets live in `static/`, and deployment-specific Worker code lives in `src/`.

For more detail, see:

- [mcm/README.md](mcm/README.md)
- [templates/README.md](templates/README.md)
- [docs/operations.md](docs/operations.md)

## What Is Implemented

- Browseable listings feed with filters and sorting
- Listing detail pages
- Shop index and shop detail pages
- Browser-session favourite listings and shops
- Freshness labels and availability badges
- English/French UI
- Localized parsed price display independent of source language
- Localized first-seen dates and plural-aware listing counts
- Admin dashboard with source health, failed refresh review, listing inspection, manual overrides,
  duplicate candidates, and per-source refresh actions

## Source Ingestion

The active launch sources are:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

The app tries live fetches first, then falls back to curated seed data when a source is unreachable
or parsing fails. Fallback data can bootstrap an empty local database, but source failures do not
deactivate existing inventory for a shop that already has records.

Source additions should stay conservative and review-friendly. Preserve provenance, source URLs,
admin notes, overrides, and parser evidence instead of hand-editing derived listing data.

## UI Notes

- Tailwind is loaded from the CDN for now.
- HTMX handles progressive interactions.
- Native Web Components are used where small client-side components help.
- Favourites are stored in the browser session rather than user accounts.
- Listing cards show image, shop, item name, favourite toggle, localized price or quote fallback,
  category, and first-seen date.
- Detail pages keep fuller provenance: item number, source link, shop, location, category,
  materials, dimensions, designer/maker, era, condition, shipping note, and freshness.

## Tooling

Python uses Ruff, Jinja templates use djLint, and JavaScript/CSS files in `static/` and `src/` use
Biome. The combined npm scripts run the project-standard checks:

```bash
npm run lint
npm run format
```

The individual commands are:

```bash
uv run ruff check .
uv run ruff format .
uv run djlint templates --lint
uv run djlint templates --reformat
npx biome check static src
npx biome check --write static src
```

## Cloudflare Deployment

The included deployment setup runs the Flask app in a Cloudflare Container. The Worker owns a D1
binding and exposes an authenticated internal bridge to the container, so the deployed Flask app
reads and writes D1 instead of local SQLite. The production image intentionally excludes
`data/mcm.db`.

Before deploying your own copy, update `wrangler.jsonc` for your Cloudflare account, Worker name, D1
database, custom domains, and cron schedule. Also review the deployment defaults at the top of
`src/worker.js`, especially the default D1 bridge URL and apex/www hostnames. The checked-in values
are for this project's current production deployment.

Required secrets:

```bash
npx wrangler secret put MCM_SECRET_KEY
npx wrangler secret put D1_BRIDGE_TOKEN
npx wrangler secret put MCM_ADMIN_TOKEN
npx wrangler secret put MCM_MANUAL_REFRESH_TOKEN
```

Use long random values for `D1_BRIDGE_TOKEN` and `MCM_ADMIN_TOKEN`. `D1_BRIDGE_TOKEN` protects the
Worker-to-D1 bridge, and `MCM_ADMIN_TOKEN` protects admin and deep-health routes in production. Do
not commit secret values. `MCM_MANUAL_REFRESH_TOKEN` protects the operations-only Worker endpoint
that forces the same per-source refresh path used by cron.

Apply D1 migrations:

```bash
npx wrangler d1 migrations apply <your-d1-database-name> --remote
```

Create the refresh queues once per Cloudflare account:

```bash
npm run cf:queue:create:refresh
npm run cf:queue:create:refresh-dlq
```

Deploy:

```bash
npm run deploy:dry-run
npm run deploy
```

Verify production:

```bash
npm run prod:health
```

`npm run prod:health` uses the currently configured production URLs and D1 database name in
`scripts/check-production.sh`. Override them with `MCM_BASE_URL`, `MCM_APEX_URL`, `MCM_WWW_URL`, and
`MCM_D1_DATABASE` when checking a different deployment.

Admin routes are open in local development when `MCM_ADMIN_TOKEN` is unset. In production, set
`MCM_ADMIN_TOKEN` and authenticate with HTTP Basic auth using any username and the token as the
password, or send `Authorization: Bearer <token>` / `X-MCM-Admin-Token: <token>`.

Cloudflare cron enqueues one refresh message per launch source. A Queue consumer processes one
message at a time, calls the private Worker-to-container refresh endpoint, and retries failures
before sending exhausted messages to the dead-letter queue. Each source refresh records
`refresh_jobs`, `crawl_runs`, and any `crawl_failures` rows in D1 so the admin dashboard can show
source-level status. A later monitor cron checks whether each source wrote a successful refresh job
and logs warnings for missing or non-success jobs.

To force the same queued path manually, call the guarded endpoint for one source:

```bash
curl -fsS \
  -X POST \
  -H "Authorization: Bearer $MCM_MANUAL_REFRESH_TOKEN" \
  "https://montreal-mcm.dalaque.workers.dev/internal/refresh-now?source=morceau"
```

Omit `source` to enqueue all active launch sources.
