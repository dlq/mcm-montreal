# Montreal MCM Phase 1

Working MVP for the Phase 1 product in [plan.md](/Users/dlq/Developer/MCM%20Montreal/plan.md), grounded in the launch-source research in [research.md](/Users/dlq/Developer/MCM%20Montreal/research.md).

## Stack

- Python + Flask
- SQLite
- HTMX
- Tailwind CSS
- Native Web Components

## What is implemented

- Browseable listings feed
- Shop index and shop detail pages
- Listing detail pages
- Filters and sorting
- Session-based favourite listings and shops
- Freshness labels and availability badges
- English / French UI
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

It tries live fetches first, then falls back to curated seed data when a source is unreachable or parsing fails. That keeps the MVP usable in restricted or offline environments while still giving us a real ingestion path to iterate on.

The broader research-backed next sources still live in `research.md` and `plan.md`.

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
- The database schema includes user tables, but saved searches, alerts, and a real login flow are not implemented yet.
- The scraper layer is intentionally conservative and stores manual-review-friendly admin notes and overrides because source markup will drift.
