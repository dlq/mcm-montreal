# Montreal MCM Phase 1

Working MVP for the Phase 1 product in [plan.md](plan.md), grounded in the launch-source research in [research.md](research.md).

## Stack

- Python + Flask
- SQLite
- HTMX
- Tailwind CSS
- Native Web Components

## Architecture

The codebase is intentionally small and split by responsibility:

- `mcm/app.py`: Flask app factory, request lifecycle, and route handlers
- `mcm/db.py`: SQLite connection, schema setup, and source seeding
- `mcm/repository.py`: listing/shop queries, favourites state, admin queries, and request filter parsing
- `mcm/refresh.py`: source refresh orchestration and ingest writes
- `mcm/i18n.py`: language helpers, localized display formatting, and shared translation utilities
- `mcm/locales/`: per-language UI string dictionaries
- `mcm/sources.py`: source-specific scraping and parsing logic
- `mcm/seed_data.py`: fallback data used when live source fetches fail

The goal is that contributors can read routes first, then follow data access or source ingestion as needed without having to parse one large mixed-purpose module.

## What is implemented

- Browseable listings feed
- Shop index and shop detail pages
- Listing detail pages
- Filters and sorting
- Session-based favourite listings and shops
- Freshness labels and availability badges
- English / French UI
- Localized parsed price display independent of the source language
- Localized first-seen dates and plural-aware listing counts
- Default sans-serif item titles and wordmark, with a restrained utility-focused UI
- Admin dashboard with:
  - source list and crawl health
  - failed refresh review
  - listing inspection
  - manual category / availability overrides
  - duplicate candidate queue

## Source ingestion

The app currently includes active source definitions for four direct-shop sources:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

It tries live fetches first, then falls back to curated seed data when a source is unreachable or parsing fails. Fallback data can bootstrap an empty local database, but source failures do not deactivate existing inventory for a shop that already has records.

The broader research-backed next sources still live in `research.md` and `plan.md`.

## Current UI conventions

- Listing and detail item names use the default sans-serif stack while the display-font direction is reconsidered.
- The wordmark also uses the default sans-serif stack with a restrained green treatment; navigation, filters, metadata, prices, and controls stay utility-focused.
- Listing cards show image, shop, item name, favourite toggle, localized price or quote fallback, category, and first-seen date.
- Repeated Montreal location and availability badges are intentionally omitted from listing cards while all active launch sources are Montreal-local or Montreal-first.
- Detail pages keep fuller provenance: availability badges, item number, shop, location, category, materials, dimensions, designer/maker, era, condition, shipping note, freshness, and source links.
- User-facing prices render from parsed `price_value` and the active UI language. Raw source price strings remain available to admin/provenance flows.
- Known Showroom Montreal price suffixes are normalized for display, for example `/ 6`, `/ 4`, `/ paire`, `ch.`, and `/ l'ens.`.
- Source titles, source notes, dimensions, and designer/maker text remain source-faithful unless we have explicit structured parsing.

## Run

```bash
uv sync --dev
uv run app.py refresh
uv run app.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Lint and format

Python uses Ruff, Jinja templates use djLint, and frontend files in `static/` use Biome.

```bash
uv run ruff check .
uv run ruff format .
uv run djlint templates --lint
uv run djlint templates --reformat
npm install
npm run lint
npm run format
```

## Tests

The fast smoke test suite uses a temporary SQLite database and does not depend on live source fetches.

```bash
uv run python -m unittest tests.test_app
```

`uv` manages the Python environment and dev tools. Biome still lives in the Node ecosystem, so you will need Node.js and `npm` installed for the frontend lint/format commands.

If you want one command per workflow, the `package.json` scripts run all three tools together:

```bash
npm run lint
npm run format
```

## Pre-commit hooks

The repo includes a `.pre-commit-config.yaml` so formatting and linting can run automatically on each commit.

```bash
uv sync --dev
npm install
uv run pre-commit install
uv run pre-commit run --all-files
```

The hooks use the same tools as local development and CI:

- `ruff format`
- `ruff check`
- `djlint --reformat`
- `djlint --lint`
- `biome check --write`

## Notes

- Tailwind is loaded from the CDN for this first pass.
- Favourites are currently stored in the browser session rather than through a full account system.
- The scraper layer is intentionally conservative and stores manual-review-friendly admin notes and overrides because source markup will drift.
