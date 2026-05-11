# `mcm/`

This package contains the Flask application and the server-side domain logic.

The split is intentionally simple:

- `app.py` wires the Flask app, request lifecycle, routes, admin protection, and CLI entrypoint.
- `db.py` initializes local SQLite and chooses the production database connection.
- `d1.py` adapts the Worker-to-D1 bridge to a small DB-API-style interface.
- `repository.py` contains read/write helpers for listings, shops, filters, favourites, and admin
  views.
- `refresh.py` owns source refresh orchestration and listing ingest writes.
- `sources.py` contains source definitions, fetch helpers, parser logic, and source-specific
  normalization.
- `seed_data.py` provides fallback data used when a source cannot be fetched.
- `i18n.py` and `locales/` contain display formatting and UI translations.

Keep route handlers thin where practical. Prefer putting database queries in `repository.py`, ingest
logic in `refresh.py`, and source-specific scraping changes in `sources.py`.

Source ingestion should stay conservative: preserve source URLs, parser evidence, admin notes,
overrides, and review queues rather than hand-editing derived listing data.
