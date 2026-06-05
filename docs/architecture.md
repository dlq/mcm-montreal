# Architecture Guide

This guide explains how the current Montreal MCM codebase is organized and where new work should
go. It describes the code as it exists today, with notes about the planned `0.3.x` cleanup where the
current shape is still broader than ideal.

## Current Shape

Montreal MCM is a small Flask app with server-rendered Jinja templates, HTMX interactions, Tailwind
loaded from the CDN, native Web Components, local SQLite for development, and Cloudflare Workers plus
D1 for production.

The main directories are:

- `mcm/`: Python application, domain logic, database helpers, source ingestion, and i18n.
- `templates/`: Jinja full-page templates and reusable partials.
- `static/`: browser JavaScript, CSS, service worker, manifest, and icons.
- `src/`: Cloudflare Worker code for production routing, queues, refresh scheduling, and D1 bridge
  access.
- `migrations/`: production D1 schema migrations.
- `tests/`: Python app tests and Worker queue tests.
- `docs/`: operational and contributor-facing documentation.

## Module Map

- `mcm/app.py`: Flask app factory, request lifecycle hooks, route registration, CLI entrypoint,
  admin protection, and small route-level glue.
- `mcm/db.py`: local SQLite schema setup, database connection selection, source/shop seeding, and
  schema-adjacent helpers.
- `mcm/d1.py`: Worker-to-D1 bridge adapter that behaves like a small DB-API-style connection.
- `mcm/repository.py`: current home for listing, shop, favourite, filter, admin, and saved-search
  queries. This is intentionally stable for now, but it is a good candidate for later splitting.
- `mcm/refresh.py`: refresh orchestration, source reconciliation, listing ingest writes, and refresh
  job bookkeeping.
- `mcm/sources.py`: source definitions, source fetch helpers, parser logic, and source-specific
  normalization. It is the largest mixed-concern module and should be split carefully in `0.3.x`.
- `mcm/locations.py`: shop address, map, and directions helpers used by shop-facing views.
- `mcm/i18n.py` and `mcm/locales/`: translation lookup, display formatting, and language-specific
  UI strings.
- `mcm/seed_data.py`: fallback listings and shop data for local development or unavailable sources.
- `templates/base.html`: shared page shell, navigation, language links, and asset includes.
- `templates/_*.html`: partials used by full-page templates and HTMX responses.
- `static/app.js`: Web Components and browser behavior that does not require a frontend build step.
- `src/worker.js`: production edge routing, queue dispatch, cron refresh handling, and container/D1
  integration.

## Shop Versus Source

The public product talks about shops. Ingestion talks about sources.

- A shop is the user-facing entity: name, website, public location, address, shipping summary, map
  links, shop page copy, and active listing count.
- A source is the crawler-facing entity: listing URLs, parser behavior, refresh/chunk settings,
  source notes, and ingestion risk.

Today these are still combined in `SourceDefinition` because the original MVP had one source per
shop. That remains workable, but future cleanup should introduce a `ShopDefinition` and a
`SourceDefinition` linked by `shop_slug` so public display metadata and crawler behavior can evolve
separately.

## Where Does This Belong?

| Change | Put it here today | Notes |
| --- | --- | --- |
| Add or change a source URL | `mcm/sources.py` | Record durable source behavior in `research.md` when evidence matters. |
| Change parser behavior | `mcm/sources.py` | Keep output normalized through `ParsedListing`. Add fixtures once available. |
| Change refresh orchestration | `mcm/refresh.py` | Keep route handlers out of ingestion details. |
| Change database queries | `mcm/repository.py` | Avoid embedding SQL in templates or route handlers. |
| Change local schema setup | `mcm/db.py` and `migrations/` | Keep SQLite setup and D1 migrations in sync. |
| Change shop address or map behavior | `mcm/locations.py` | Planned cleanup may move this into `mcm/shops.py`. |
| Change shop display copy | `mcm/sources.py` and `mcm/locales/` | Public copy should preserve English/French behavior where applicable. |
| Change route behavior | `mcm/app.py` | Keep routes thin and delegate query/refresh/parser work. |
| Change page structure | `templates/` | Use translation keys for user-facing text. |
| Change HTMX partials | `templates/_*.html` | Partials should still make sense when rendered by server routes. |
| Change browser behavior | `static/app.js` | Prefer small Web Components over adding a build pipeline. |
| Change PWA assets | `static/manifest.webmanifest`, `static/service-worker.js`, icons | Verify offline/install behavior when touched. |
| Change Worker queues or production routing | `src/worker.js` | Update `docs/operations.md` when operator behavior changes. |
| Change deployment or secret handling | `docs/operations.md` and Cloudflare config | Never commit secret values. |
| Record source evidence | `research.md` | Use for URLs, commands, parser evidence, caveats, and unresolved source questions. |
| Record roadmap decisions | `plan.md` | Keep it as execution state, not a scratch log. |

## Boundary Rules

- Keep route handlers thin. They should validate request state, call repository or domain helpers,
  and render a template.
- Keep scraping and parsing conservative. Preserve source URLs, provenance, admin notes, overrides,
  and fallback behavior.
- Do not hand-edit `data/mcm.db` for durable facts. Prefer source definitions, seed data, migrations,
  importer logic, or admin overrides.
- Keep templates readable. Avoid moving large business decisions into Jinja conditionals.
- Preserve bilingual behavior when changing user-facing labels, route-adjacent text, or status copy.
- Keep deployment-specific behavior in the Worker or operations docs, not scattered through
  templates.
- Add focused tests around boundaries before splitting modules. The planned `0.3.x` refactor should
  move code without changing behavior.

## Planned Cleanup Direction

The next structural cleanup should make the current concepts easier to find without rewriting the
app:

- Split shop display metadata from crawl source configuration.
- Introduce small view-model shapes for listing cards, listing details, shop cards, and shop details.
- Split repository helpers by concern once there are enough tests to make that safe.
- Split source parsing into source definitions, shared parser helpers, and parser-family modules.
- Move public, favourite, admin, and ops routes out of the single large app module while keeping
  `create_app()` as the composition point.

Until those changes are made, use the table above as the source of truth for where contributor work
should land.
