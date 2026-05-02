# Montreal MCM Phase 1

First working attempt for the Phase 1 MVP in `plan.md`, grounded in the launch-source research from `research.md`.

## Stack

- Python + Flask
- SQLite
- HTMX
- Tailwind CSS
- Native Web Components

## What is implemented

- Browseable listings feed
- Launch-source shop pages
- Listing detail pages
- Filters and sorting
- Email-only Phase 1 login
- Favourite listings and shops
- Freshness labels and availability badges
- Admin dashboard with:
  - source list and crawl health
  - failed refresh review
  - listing inspection
  - manual category / availability overrides
  - duplicate candidate queue

## Source ingestion

The app includes source definitions for the four Phase 1 Montreal launch shops:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

It tries live fetches first, then falls back to curated seed data when a source is unreachable or parsing fails. That keeps the Phase 1 product usable in restricted or offline environments while still giving us a real ingestion path to iterate on.

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

## Notes

- Tailwind is loaded from the CDN for this first pass.
- Login is intentionally lightweight: entering an email creates a local session user.
- The scraper layer is intentionally conservative and stores manual-review-friendly admin notes and overrides because source markup will drift.
