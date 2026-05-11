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

Core code is intentionally small and split by responsibility:

- `mcm/app.py`: Flask app factory, request lifecycle, and route handlers
- `mcm/db.py`: local SQLite setup and production database connection selection
- `mcm/d1.py`: small DB-API-style client for the production database bridge
- `mcm/repository.py`: listing/shop queries, favourites state, admin queries, and filter parsing
- `mcm/refresh.py`: source refresh orchestration and ingest writes
- `mcm/i18n.py`: language helpers, localized display formatting, and translation utilities
- `mcm/locales/`: English and French UI string dictionaries
- `mcm/sources.py`: source-specific scraping and parsing logic
- `mcm/seed_data.py`: fallback data used when live source fetches fail
- `templates/`: Jinja templates
- `static/`: local JavaScript and CSS
- `tests/`: fast unittest coverage using temporary SQLite databases

Deployment-specific files live at the repository root and in `src/`, `migrations/`, and `docs/`.

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

Production runs the Flask app in a Cloudflare Container. The Worker owns the D1 binding and exposes
an authenticated internal bridge to the container, so the deployed Flask app reads and writes D1
instead of local SQLite. The production image intentionally excludes `data/mcm.db`.

See [docs/operations.md](docs/operations.md) for the deploy checklist, health checks, D1 backup
command, and bad-deploy recovery steps.

Current production resources:

- Worker: `montreal-mcm`
- Container application: `montreal-mcm-mcmcontainer`
- D1 database: `montreal-mcm`
- D1 binding: `DB`
- workers.dev URL: [https://montreal-mcm.dalaque.workers.dev](https://montreal-mcm.dalaque.workers.dev)
- Custom domains configured in `wrangler.jsonc`: `montrealmcm.ca`, `www.montrealmcm.ca`
- Cron: `23 9 * * *`, which is 09:23 UTC daily

Required secrets:

```bash
npx wrangler secret put MCM_SECRET_KEY
npx wrangler secret put D1_BRIDGE_TOKEN
npx wrangler secret put MCM_ADMIN_TOKEN
```

Use long random values for `D1_BRIDGE_TOKEN` and `MCM_ADMIN_TOKEN`. `D1_BRIDGE_TOKEN` protects the
Worker-to-D1 bridge, and `MCM_ADMIN_TOKEN` protects admin and deep-health routes in production. Do
not commit secret values.

Apply D1 migrations:

```bash
npx wrangler d1 migrations apply montreal-mcm --remote
```

Deploy:

```bash
npm run deploy:dry-run
npm run deploy
```

Verify production:

```bash
curl -fsS https://montreal-mcm.dalaque.workers.dev/healthz
curl -fsS -H "Authorization: Bearer $MCM_ADMIN_TOKEN" https://montreal-mcm.dalaque.workers.dev/admin/healthz
curl -fsS -o /tmp/mcm-home.html https://montreal-mcm.dalaque.workers.dev/
npx wrangler d1 execute montreal-mcm --remote --command "SELECT COUNT(*) AS listings FROM listings;"
```

Admin routes are open in local development when `MCM_ADMIN_TOKEN` is unset. In production, set
`MCM_ADMIN_TOKEN` and authenticate with HTTP Basic auth using any username and the token as the
password, or send `Authorization: Bearer <token>` / `X-MCM-Admin-Token: <token>`.

Cloudflare cron triggers one private Worker-to-container refresh request per launch source. Each
source refresh records `refresh_jobs`, `crawl_runs`, and any `crawl_failures` rows in D1 so the
admin dashboard can show source-level status.
