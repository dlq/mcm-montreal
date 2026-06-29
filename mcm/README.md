# `mcm/`

This package contains the Flask application and the server-side domain logic.

The split is intentionally simple:

- `app.py` wires the Flask app, request lifecycle, routes, admin protection, and CLI entrypoint.
- `analytics.py` contains page-view path classification and first-party aggregate analytics writes.
- `repository_analytics.py` contains analytics summary read helpers for admin reporting.
- `db.py` initializes local SQLite, loads `schema.sql`, seeds shops, and chooses the production
  database connection.
- `repository_design.py` contains designer/maker aliasing, design entity, candidate review, and
  evidence helpers.
- `d1.py` adapts the Worker-to-D1 bridge to a small DB-API-style interface.
- `repository_catalog.py` contains read/write helpers for listings, shops, filters, favourites, and admin
  views.
- `refresh.py` owns source refresh orchestration and listing ingest writes.
- `repository_refresh.py` contains refresh-job and refresh-event persistence helpers.
- `source_types.py` defines the public source/listing contracts.
- `source_definitions.py` contains configured source metadata.
- `source_utils.py` contains shared source parsing helpers for URL fetching, text cleanup, slugging,
  and numeric coercion.
- `source_enrichment.py` contains shared source-derived metadata extraction for materials,
  dimensions, eras, designers/makers, categories, and shipping scope.
- `sources.py` contains source fetch dispatch, parser logic, and source-specific normalization.
- `schema.sql` contains the local SQLite schema DDL used by `db.py`; keep it in sync with D1
  migrations.
- `seo.py` contains public URL, category slug, language alternate, and structured-data helpers.
- `saved_searches.py` contains saved-search naming and query-string helpers.
- `seed_data.py` provides fallback data used when a source cannot be fetched.
- `i18n.py` and `locales/` contain display formatting and UI translations.

Keep route handlers thin where practical. Prefer putting database queries in `repository_catalog.py`, ingest
logic in `refresh.py`, source-specific scraping changes in `sources.py`, shared listing metadata
heuristics in `source_enrichment.py`, SEO helpers in `seo.py`, analytics helpers in `analytics.py`,
saved-search helper logic in `saved_searches.py`, and refresh persistence helpers in
`repository_refresh.py`. Keep analytics summary SQL in `repository_analytics.py` and design-entity
admin SQL in `repository_design.py`.

Source ingestion should stay conservative: preserve source URLs, parser evidence, admin notes,
overrides, and review queues rather than hand-editing derived listing data.
