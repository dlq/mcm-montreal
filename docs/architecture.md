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
- `mcm/analytics.py`: page-view path classification, first-party aggregate page-view writes, and
  analytics date-window helpers.
- `mcm/repository_analytics.py`: analytics summary read helpers for admin reporting.
- `mcm/db.py`: local SQLite setup, database connection selection, source/shop seeding, and
  schema-adjacent compatibility helpers.
- `mcm/schema.sql`: local SQLite schema DDL loaded by `mcm/db.py`; keep it equivalent to the D1
  migration history.
- `mcm/d1.py`: Worker-to-D1 bridge adapter that behaves like a small DB-API-style connection.
- `mcm/repository_design.py`: designer/maker aliasing, design entity, candidate review, and
  evidence helpers.
- `mcm/repository_catalog.py`: current home for listing, shop, favourite, filter, admin, and saved-search
  queries. This is still broader than ideal and should keep shrinking around cohesive domains.
- `mcm/refresh.py`: refresh orchestration, source reconciliation, and listing ingest flow.
- `mcm/repository_refresh.py`: refresh-job and refresh-event persistence helpers.
- `mcm/source_types.py`: public source/listing contracts such as `SourceDefinition` and
  `ParsedListing`.
- `mcm/source_definitions.py`: configured source metadata and listing URLs.
- `mcm/source_utils.py`: shared source parsing helpers for URL fetching, text cleanup, slugging,
  and numeric coercion.
- `mcm/source_enrichment.py`: shared source-derived metadata extraction for materials, dimensions,
  eras, designers/makers, categories, and shipping scope.
- `mcm/sources.py`: source fetch dispatch, parser logic, and source-specific normalization. It is
  still the largest mixed-concern module and should be split carefully in `0.3.x`.
- `mcm/seo.py`: public URL normalization, category slugs, language alternates, and structured data.
- `mcm/saved_searches.py`: saved-search query-string and display-name helpers.
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
| Add or change a source URL | `mcm/source_definitions.py` | Record durable source behavior in `NOTES.md` when evidence matters. |
| Change parser behavior | `mcm/sources.py` | Keep output normalized through `ParsedListing`. Add fixtures once available. |
| Change shared metadata extraction | `mcm/source_enrichment.py` | Covers derived fields such as materials, dimensions, eras, categories, and designer/maker text. |
| Change refresh orchestration | `mcm/refresh.py` | Keep route handlers out of ingestion details. |
| Change refresh job or event persistence | `mcm/repository_refresh.py` | Keep operational SQL behind named helpers instead of embedding it in orchestration flow. |
| Change first-party analytics path rules | `mcm/analytics.py` | Keep raw request handling in routes, but aggregate path classification here. |
| Change analytics summary reporting | `mcm/repository_analytics.py` | Keep admin report SQL separate from request event recording. |
| Change design entity or alias behavior | `mcm/repository_design.py` | Covers creator/designer/maker aliases, candidate review, and listing evidence. |
| Change SEO URL or structured-data behavior | `mcm/seo.py` | Verify canonical URLs, sitemap-adjacent behavior, and JSON-LD tests. |
| Change saved-search naming or query persistence | `mcm/saved_searches.py` | Keep form parsing in routes and pure helper behavior here. |
| Change database queries | `mcm/repository_catalog.py` | Avoid embedding SQL in templates or route handlers. |
| Change local schema setup | `mcm/schema.sql`, `mcm/db.py`, and `migrations/` | Keep SQLite setup and D1 migrations in sync; prefer schema DDL in `schema.sql`, with compatibility helpers in `db.py`. |
| Change shop address or map behavior | `mcm/locations.py` | Planned cleanup may move this into `mcm/shops.py`. |
| Change shop display copy | `mcm/source_definitions.py` and `mcm/locales/` | Public copy should preserve English/French behavior where applicable. |
| Change route behavior | `mcm/app.py` | Keep routes thin and delegate query/refresh/parser work. |
| Change page structure | `templates/` | Use translation keys for user-facing text. |
| Change HTMX partials | `templates/_*.html` | Partials should still make sense when rendered by server routes. |
| Change browser behavior | `static/app.js` | Prefer small Web Components over adding a build pipeline. |
| Change PWA assets | `static/manifest.webmanifest`, `static/service-worker.js`, icons | Verify offline/install behavior when touched. |
| Change Worker queues or production routing | `src/worker.js` | Update `docs/operations.md` when operator behavior changes. |
| Change deployment or secret handling | `docs/operations.md` and Cloudflare config | Never commit secret values. |
| Record source evidence | `NOTES.md` | Use for URLs, commands, parser evidence, caveats, and unresolved source questions. |
| Record roadmap decisions | `PLANS.md` | Keep it as execution state, not a scratch log. |

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
