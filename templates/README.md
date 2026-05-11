# `templates/`

Templates are server-rendered Jinja files used by the Flask app.

General conventions:

- `base.html` owns the shared page shell, navigation, language links, and asset includes.
- Full-page templates extend `base.html`.
- Partial templates use a leading underscore, for example `_listing_grid.html` and
  `_favourite_listing_button.html`.
- HTMX responses should be progressive: the same underlying route should still make sense without
  requiring heavy client-side state.
- User-facing text should use translation keys from `mcm/locales/` rather than hard-coded English or
  French strings.
- Keep source-provenance and admin-review details visible in admin/detail templates where useful.

Tailwind is currently loaded from the CDN, so template classes are written directly in markup. Avoid
introducing a frontend build pipeline unless the project deliberately changes that constraint.
