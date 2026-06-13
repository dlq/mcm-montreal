from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from mcm.app import create_app
from mcm.db import ensure_schema, get_db
from mcm.i18n import MATERIAL_LABELS, SHOP_TRANSLATIONS
from mcm.locales import TRANSLATIONS_EN, TRANSLATIONS_FR
from mcm.refresh import (
    RECONCILABLE_CHUNK_COUNTS,
    listing_id_from_item_number,
    public_item_number,
    reconcile_chunked_source,
    refresh_all_sources,
    refresh_source_by_slug,
)
from mcm.repository import (
    create_design_entity,
    list_design_entity_candidates,
    list_filter_values,
    query_listings,
    sanitize_availability,
)
from mcm.seed_data import SEED_LISTINGS
from mcm.sources import (
    SOURCE_DEFINITIONS,
    _extract_condition,
    _extract_designer_and_maker,
    _extract_dimensions,
    _extract_era,
    _extract_materials,
    _extract_showroom_gallery_listings,
    _extract_showroom_siteassets_url,
    _fetch_html,
    _fetch_shopify_collection_entry,
    _fetch_shopify_collection_products,
    _fetch_showroom,
    _parse_cargo_page,
    _parse_shopify_collection_product,
    _parse_square_product_page,
    _parse_square_storefront_product,
    _parse_squarespace_store_item,
    _showroom_source_listing_key,
    _square_product_is_sold_out,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def schema_signature(db: sqlite3.Connection) -> dict[str, Any]:
    tables = [
        row["name"]
        for row in db.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]
    return {
        table: {
            "columns": {
                row["name"]: {
                    "name": row["name"],
                    "type": row["type"],
                    "notnull": row["notnull"],
                    "default": row["dflt_value"],
                    "primary_key": row["pk"],
                }
                for row in db.execute(f"PRAGMA table_info({table})").fetchall()
            },
            "indexes": {
                row["name"]: [
                    column["name"]
                    for column in db.execute(f"PRAGMA index_info({row['name']})").fetchall()
                ]
                for row in db.execute(f"PRAGMA index_list({table})").fetchall()
                if row["origin"] == "c"
            },
        }
        for table in tables
    }


def migrated_schema_signature() -> dict[str, Any]:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    try:
        for path in sorted((PROJECT_ROOT / "migrations").glob("*.sql")):
            db.executescript(path.read_text())
        return schema_signature(db)
    finally:
        db.close()


def seed_listing(app) -> int:
    with app.app_context():
        db = get_db(app)
        try:
            shop = db.execute("SELECT id FROM shops WHERE slug = 'morceau'").fetchone()
            assert shop is not None
            db.execute(
                """
                INSERT INTO listings (
                    source_shop_id, source_listing_url, source_listing_key, title, normalized_title,
                    price_raw, price_value, currency, primary_image_url, additional_image_urls,
                    availability_status, shipping_scope, ships_to_montreal, shipping_note,
                    last_seen_at, last_checked_at, first_seen_at, category, subcategory, designer,
                    maker, era, materials, dimensions_text, width, depth, height, condition_text,
                    location_text, source_description, ingest_source_type, parse_confidence,
                    dedupe_group_id, is_active, is_featured, manual_notes, availability_override,
                    category_override
                ) VALUES (
                    ?, 'https://example.com/listing', 'sample-key', 'Sample Chair', 'sample chair',
                    '$250', 250, 'CAD', 'https://example.com/image.jpg', '[]',
                    'available', 'canada', 1, 'Ships to Montreal',
                    '2026-05-06T00:00:00+00:00', '2026-05-06T00:00:00+00:00', '2026-05-06T00:00:00+00:00',
                    'lounge chairs', '', 'Test Designer', '', '1960s', 'teak', '20 x 20 x 30',
                    NULL, NULL, NULL, 'Good', 'Montreal, QC', 'Sample description', 'test', 1.0,
                    '', 1, 0, '', '', ''
                )
                """,
                (shop["id"],),
            )
            db.commit()
            return int(
                db.execute(
                    "SELECT id FROM listings WHERE source_listing_key = 'sample-key'"
                ).fetchone()["id"]
            )
        finally:
            db.close()


def update_listing_price(app, listing_id: int, raw: str, value: float | None) -> None:
    with app.app_context():
        db = get_db(app)
        try:
            db.execute(
                """
                UPDATE listings
                SET price_raw = ?,
                    price_value = ?,
                    currency = 'CAD'
                WHERE id = ?
                """,
                (raw, value, listing_id),
            )
            db.commit()
        finally:
            db.close()


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.db_path),
                "SECRET_KEY": "test-secret",
                "MCM_ALLOW_OPEN_ADMIN": True,
            }
        )
        self.listing_id = seed_listing(self.app)
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_core_routes_return_success(self) -> None:
        for path in [
            "/",
            "/shops",
            "/favourites",
            "/admin",
            f"/listing/{public_item_number(self.listing_id)}",
            "/?lang=fr",
        ]:
            response = self.client.get(path, follow_redirects=True)
            self.assertEqual(response.status_code, 200, path)

    def test_shop_pages_include_public_addresses_and_directions(self) -> None:
        response = self.client.get("/shops")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<shop-card-map", response.text)
        self.assertIn("Google Maps", response.text)
        self.assertIn("Apple Maps", response.text)
        self.assertIn("https://www.google.com/maps/search/?api=1", response.text)
        self.assertIn("https://maps.apple.com/?q=", response.text)
        self.assertIn(
            "Morceau%2C+4812+rue+Saint-Urbain%2C+Montreal%2C+QC%2C+H2T+2W2", response.text
        )
        self.assertIn('data-latitude="45.5225"', response.text)

        detail_response = self.client.get("/shops/morceau")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("4812 rue Saint-Urbain", detail_response.text)
        self.assertIn("Montreal QC H2T 2W2", detail_response.text)
        self.assertIn("Google Maps", detail_response.text)
        self.assertIn("Apple Maps", detail_response.text)

    def test_shop_directions_are_localized(self) -> None:
        response = self.client.get("/shops/morceau?lang=fr")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Google Maps", response.text)
        self.assertIn("Apple Plans", response.text)

    def test_unlisted_shop_address_uses_location_note(self) -> None:
        response = self.client.get("/shops/yardsale-vintage")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No public street address found", response.text)
        self.assertNotIn("Yardsale+Vintage%2C+Montreal%2C+QC", response.text)

    def test_locale_files_have_matching_keys(self) -> None:
        self.assertEqual(set(TRANSLATIONS_EN), set(TRANSLATIONS_FR))

    def test_local_schema_matches_migrations(self) -> None:
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        try:
            ensure_schema(db)
            local_schema = schema_signature(db)
        finally:
            db.close()

        self.assertEqual(migrated_schema_signature(), local_schema)

    def test_active_shop_metadata_has_french_copy(self) -> None:
        translated_fields = {"description", "style_focus", "shipping_summary", "notes"}
        source_slugs = {source.slug for source in SOURCE_DEFINITIONS}

        self.assertEqual(set(SHOP_TRANSLATIONS), source_slugs)
        for source in SOURCE_DEFINITIONS:
            self.assertGreaterEqual(
                set(SHOP_TRANSLATIONS[source.slug].get("fr", {})),
                translated_fields,
                source.slug,
            )

    def test_process_health_does_not_require_database_or_auth(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")
        self.assertNotIn("X-MCM-App-Ms", response.headers)
        self.assertNotIn("X-MCM-D1-Queries", response.headers)
        self.assertNotIn("X-MCM-D1-Ms", response.headers)

    def test_timing_headers_are_opt_in(self) -> None:
        timing_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(Path(self.temp_dir.name) / "timing.db"),
                "SECRET_KEY": "test-secret",
                "MCM_ALLOW_OPEN_ADMIN": True,
                "MCM_EXPOSE_TIMING_HEADERS": True,
            }
        )
        client = timing_app.test_client()

        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertIn("X-MCM-App-Ms", response.headers)

    def test_admin_health_checks_database(self) -> None:
        response = self.client.get("/admin/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")
        self.assertEqual(response.json["database"], "ok")
        self.assertGreaterEqual(response.json["shops"], 1)
        self.assertGreaterEqual(response.json["listings"], 1)

    def test_admin_routes_require_token_when_configured(self) -> None:
        protected_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(Path(self.temp_dir.name) / "protected.db"),
                "SECRET_KEY": "test-secret",
                "MCM_ADMIN_TOKEN": "admin-secret",
            }
        )
        protected_listing_id = seed_listing(protected_app)
        client = protected_app.test_client()

        self.assertEqual(client.get("/healthz").status_code, 200)

        for path in [
            "/admin",
            "/admin/healthz",
            f"/admin/listings/{protected_listing_id}",
        ]:
            response = client.get(path)
            self.assertEqual(response.status_code, 401, path)

        response = client.get("/admin", headers={"X-MCM-Admin-Token": "admin-secret"})
        self.assertEqual(response.status_code, 200)

        response = client.get("/admin/healthz", headers={"Authorization": "Bearer admin-secret"})
        self.assertEqual(response.status_code, 200)

        response = client.get(
            f"/admin/listings/{protected_listing_id}",
            headers={"Authorization": "Basic YWRtaW46YWRtaW4tc2VjcmV0"},
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_routes_fail_closed_without_token(self) -> None:
        protected_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(Path(self.temp_dir.name) / "fail-closed.db"),
                "SECRET_KEY": "test-secret",
            }
        )
        client = protected_app.test_client()

        self.assertEqual(client.get("/healthz").status_code, 200)
        self.assertEqual(client.get("/admin").status_code, 401)
        self.assertEqual(client.get("/admin/healthz").status_code, 401)

    def test_language_redirect_rejects_external_next_url(self) -> None:
        response = self.client.get("/language/fr?next=https://example.com/phish")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_language_redirect_allows_relative_next_url(self) -> None:
        response = self.client.get("/language/fr?next=/shops")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/shops")

    def test_invalid_price_filter_does_not_error(self) -> None:
        response = self.client.get("/?price_min=abc")
        self.assertEqual(response.status_code, 200)

    def test_static_assets_are_versioned(self) -> None:
        response = self.client.get("/")
        self.assertIn("/static/app.css?v=", response.text)
        self.assertIn("/static/app.js?v=", response.text)

    def test_base_template_exposes_pageview_analytics_metadata(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-analytics-page-type="home"', response.text)
        self.assertIn('data-analytics-path-key="/"', response.text)

    def test_analytics_pageview_records_daily_aggregate(self) -> None:
        response = self.client.post(
            "/analytics/pageview",
            json={"path": "/", "lang": "en"},
            headers={"Origin": "http://localhost"},
        )

        self.assertEqual(response.status_code, 204)
        with self.app.app_context():
            db = get_db(self.app)
            try:
                row = db.execute(
                    """
                    SELECT view_date, page_type, path_key, lang, views
                    FROM analytics_page_views
                    """
                ).fetchone()
            finally:
                db.close()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["view_date"], datetime.now(UTC).date().isoformat())
        self.assertEqual(row["page_type"], "home")
        self.assertEqual(row["path_key"], "/")
        self.assertEqual(row["lang"], "en")
        self.assertEqual(row["views"], 1)

    def test_analytics_pageview_increments_existing_aggregate(self) -> None:
        for _ in range(2):
            response = self.client.post("/analytics/pageview", json={"path": "/shops"})
            self.assertEqual(response.status_code, 204)

        with self.app.app_context():
            db = get_db(self.app)
            try:
                row = db.execute(
                    """
                    SELECT page_type, path_key, views
                    FROM analytics_page_views
                    WHERE path_key = '/shops'
                    """
                ).fetchone()
            finally:
                db.close()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["page_type"], "shops")
        self.assertEqual(row["views"], 2)

    def test_analytics_pageview_skips_internal_routes(self) -> None:
        for path in ["/healthz", "/admin", "/cron/refresh", "/internal/d1/query", "/static/app.js"]:
            response = self.client.post("/analytics/pageview", json={"path": path})
            self.assertEqual(response.status_code, 204, path)

        with self.app.app_context():
            db = get_db(self.app)
            try:
                count = db.execute("SELECT COUNT(*) AS count FROM analytics_page_views").fetchone()[
                    "count"
                ]
            finally:
                db.close()

        self.assertEqual(count, 0)

    def test_static_script_sends_pageview_beacon(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text()

        self.assertIn("navigator.sendBeacon", script)
        self.assertIn("/analytics/pageview", script)
        self.assertIn("analyticsPageType", script)

    def test_primary_navigation_has_accessibility_landmarks(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('class="skip-link"', response.text)
        self.assertIn('href="#main-content"', response.text)
        self.assertIn('id="main-content"', response.text)
        self.assertIn('aria-label="Primary navigation"', response.text)
        self.assertIn('aria-current="page"', response.text)
        self.assertIn('aria-live="polite"', response.text)

    def test_not_found_page_is_branded_and_localized(self) -> None:
        response = self.client.get("/not-a-real-page")
        self.assertEqual(response.status_code, 404)
        self.assertIn("This page is not available", response.text)
        self.assertIn(">Listings<", response.text)
        self.assertIn(">Shops<", response.text)

        fr_response = self.client.get("/not-a-real-page?lang=fr")
        self.assertEqual(fr_response.status_code, 404)
        self.assertIn("Cette page n", fr_response.text)
        self.assertIn(">Annonces<", fr_response.text)

    def test_pwa_manifest_and_service_worker_are_available(self) -> None:
        response = self.client.get("/")
        self.assertIn("/manifest.webmanifest", response.text)
        self.assertIn("apple-mobile-web-app-capable", response.text)
        self.assertIn("viewport-fit=cover", response.text)

        manifest_response = self.client.get("/manifest.webmanifest")
        self.assertEqual(manifest_response.status_code, 200)
        self.assertEqual(manifest_response.content_type, "application/manifest+json")
        self.assertEqual(manifest_response.json["display"], "standalone")
        self.assertEqual(manifest_response.json["scope"], "/")
        self.assertIn(
            "/static/app-icon-512.png",
            {icon["src"] for icon in manifest_response.json["icons"]},
        )
        self.assertIn(
            "/static/app-icon-maskable-512.png",
            {
                icon["src"]
                for icon in manifest_response.json["icons"]
                if icon["purpose"] == "maskable"
            },
        )

        service_worker_response = self.client.get("/service-worker.js")
        self.assertEqual(service_worker_response.status_code, 200)
        self.assertIn("application/javascript", service_worker_response.content_type)
        self.assertEqual(service_worker_response.headers["Service-Worker-Allowed"], "/")
        self.assertIn("/offline", service_worker_response.text)

        offline_response = self.client.get("/offline")
        self.assertEqual(offline_response.status_code, 200)
        self.assertIn("Montreal MCM is offline", offline_response.text)

        offline_fr_response = self.client.get("/offline?lang=fr")
        self.assertEqual(offline_fr_response.status_code, 200)
        self.assertIn("hors ligne", offline_fr_response.text)

    def test_public_discovery_routes_expose_crawlable_urls(self) -> None:
        robots_response = self.client.get("/robots.txt")
        self.assertEqual(robots_response.status_code, 200)
        self.assertEqual(robots_response.content_type, "text/plain; charset=utf-8")
        self.assertIn("User-agent: *", robots_response.text)
        self.assertIn("Allow: /", robots_response.text)
        self.assertIn("Sitemap: https://montrealmcm.ca/sitemap.xml", robots_response.text)

        sitemap_response = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap_response.status_code, 200)
        self.assertEqual(sitemap_response.content_type, "application/xml; charset=utf-8")
        self.assertIn("<loc>https://montrealmcm.ca/</loc>", sitemap_response.text)
        self.assertIn("<loc>https://montrealmcm.ca/shops</loc>", sitemap_response.text)
        self.assertIn("<loc>https://montrealmcm.ca/shops/morceau</loc>", sitemap_response.text)
        self.assertIn(
            f"<loc>https://montrealmcm.ca/listing/{public_item_number(self.listing_id)}</loc>",
            sitemap_response.text,
        )
        self.assertNotIn("/admin", sitemap_response.text)
        self.assertNotIn("/favourites", sitemap_response.text)

    def test_pages_include_canonical_and_description_metadata(self) -> None:
        home_response = self.client.get("/?q=teak&price_max=1000")
        self.assertEqual(home_response.status_code, 200)
        self.assertIn('rel="canonical"', home_response.text)
        self.assertIn('href="https://montrealmcm.ca/"', home_response.text)
        self.assertIn('name="description"', home_response.text)
        self.assertIn("Montreal-first discovery", home_response.text)

        listing_response = self.client.get(f"/listing/{public_item_number(self.listing_id)}")
        self.assertEqual(listing_response.status_code, 200)
        self.assertIn(
            f'href="https://montrealmcm.ca/listing/{public_item_number(self.listing_id)}"',
            listing_response.text,
        )
        self.assertIn("Sample Chair from Morceau", listing_response.text)

        shop_response = self.client.get("/shops/morceau")
        self.assertEqual(shop_response.status_code, 200)
        self.assertIn('href="https://montrealmcm.ca/shops/morceau"', shop_response.text)
        self.assertIn("Browse current listings from Morceau", shop_response.text)

    def test_localized_social_and_language_metadata_render(self) -> None:
        response = self.client.get("/?lang=fr")
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="twitter:card"', response.text)
        self.assertIn('property="og:locale" content="fr_CA"', response.text)
        self.assertIn('hreflang="en"', response.text)
        self.assertIn('href="https://montrealmcm.ca/?lang=en"', response.text)
        self.assertIn('hreflang="fr"', response.text)
        self.assertIn('href="https://montrealmcm.ca/?lang=fr"', response.text)
        self.assertIn("Découverte montréalaise", response.text)

    def test_structured_data_renders_for_core_public_pages(self) -> None:
        home_response = self.client.get("/")
        self.assertEqual(home_response.status_code, 200)
        self.assertIn('type="application/ld+json"', home_response.text)
        self.assertIn('"@type": "WebSite"', home_response.text)
        self.assertIn('"@type": "CollectionPage"', home_response.text)

        listing_response = self.client.get(f"/listing/{public_item_number(self.listing_id)}")
        self.assertEqual(listing_response.status_code, 200)
        self.assertIn('"@type": "Product"', listing_response.text)
        self.assertIn('"name": "Sample Chair"', listing_response.text)
        self.assertIn('"price": 250', listing_response.text)

        shop_response = self.client.get("/shops/morceau")
        self.assertEqual(shop_response.status_code, 200)
        self.assertIn('"@type": "Store"', shop_response.text)
        self.assertIn('"name": "Morceau"', shop_response.text)

    def test_category_landing_pages_are_indexable(self) -> None:
        response = self.client.get("/categories/lounge-chairs")
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="https://montrealmcm.ca/categories/lounge-chairs"', response.text)
        self.assertIn("lounge chairs in Montreal", response.text)
        self.assertIn("Sample Chair", response.text)

        sitemap_response = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap_response.status_code, 200)
        self.assertIn(
            "<loc>https://montrealmcm.ca/categories/lounge-chairs</loc>",
            sitemap_response.text,
        )

    def test_sold_out_filter_requires_available_to_sold_history(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET availability_status = 'sold_out'
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        default_response = self.client.get("/")
        sold_response = self.client.get("/?availability=sold_out")
        all_response = self.client.get("/?availability=all")

        self.assertNotIn("Sample Chair", default_response.text)
        self.assertNotIn("Sample Chair", sold_response.text)
        self.assertNotIn("Sample Chair", all_response.text)

        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    INSERT INTO listing_availability_events (
                        listing_id, shop_id, source_listing_key, observed_at,
                        from_status, to_status, event_type
                    ) VALUES (?, (SELECT id FROM shops WHERE slug = 'morceau'), 'sample-key',
                        '2026-05-07T00:00:00+00:00', 'available', 'sold_out', 'test')
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        sold_response = self.client.get("/?availability=sold_out")
        all_response = self.client.get("/?availability=all")
        self.assertIn("Sample Chair", sold_response.text)
        self.assertIn("Sample Chair", all_response.text)

    def test_unknown_availability_filter_falls_back_to_available(self) -> None:
        self.assertEqual(sanitize_availability("unknown"), "available")
        response = self.client.get("/?availability=unknown")
        self.assertNotIn("Unknown", response.text)
        self.assertIn("Available only", response.text)

    def test_active_filter_summary_renders_with_results_after_apply(self) -> None:
        response = self.client.get("/?availability=sold_out&sort=price_low")
        self.assertIn("0 listings", response.text)
        self.assertIn("Availability: sold out", response.text)
        self.assertIn("Sort: Price low to high", response.text)

    def test_favourite_toggle_returns_404_for_missing_listing(self) -> None:
        response = self.client.post("/favourites/listing/999999")
        self.assertEqual(response.status_code, 404)

    def test_favourite_toggles_work_for_valid_ids(self) -> None:
        listing_response = self.client.post(f"/favourites/listing/{self.listing_id}")
        shop_response = self.client.post("/favourites/shop/1")
        self.assertEqual(listing_response.status_code, 200)
        self.assertEqual(shop_response.status_code, 200)

    def test_listing_favourite_toggle_updates_nav_count(self) -> None:
        response = self.client.post(f"/favourites/listing/{self.listing_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('hx-swap-oob="true"', response.text)
        self.assertIn('id="favourite-count"', response.text)
        self.assertIn("(1)", response.text)

    def test_shop_favourite_toggle_updates_nav_count(self) -> None:
        response = self.client.post("/favourites/shop/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn('hx-swap-oob="true"', response.text)
        self.assertIn('id="favourite-count"', response.text)
        self.assertIn("(1)", response.text)

    def test_saved_search_counts_in_favourites_nav_total(self) -> None:
        response = self.client.post(
            "/saved-searches",
            data={"q": "teak", "category": "lounge chairs"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="favourite-count"', response.text)
        self.assertIn("(1)", response.text)

    def test_favourite_toggle_uses_durable_anonymous_identity(self) -> None:
        response = self.client.post(f"/favourites/listing/{self.listing_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn("mcm_anonymous_id=", response.headers.get("Set-Cookie", ""))
        with self.app.app_context():
            db = get_db(self.app)
            try:
                identity_count = db.execute(
                    "SELECT COUNT(*) AS count FROM anonymous_identities"
                ).fetchone()["count"]
                favourite = db.execute(
                    """
                    SELECT listing_id
                    FROM anonymous_favourite_listings
                    WHERE listing_id = ?
                    """,
                    (self.listing_id,),
                ).fetchone()
                self.assertEqual(identity_count, 1)
                self.assertIsNotNone(favourite)
            finally:
                db.close()

    def test_plain_browse_does_not_create_anonymous_identity(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mcm_anonymous_id=", response.headers.get("Set-Cookie", ""))
        with self.app.app_context():
            db = get_db(self.app)
            try:
                identity_count = db.execute(
                    "SELECT COUNT(*) AS count FROM anonymous_identities"
                ).fetchone()["count"]
                self.assertEqual(identity_count, 0)
            finally:
                db.close()

    def test_session_favourites_migrate_to_anonymous_identity(self) -> None:
        with self.client.session_transaction() as client_session:
            client_session["favourite_listing_ids"] = [self.listing_id]
            client_session["favourite_shop_ids"] = [1]

        response = self.client.get("/favourites")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sample Chair", response.text)
        with self.client.session_transaction() as client_session:
            self.assertNotIn("favourite_listing_ids", client_session)
            self.assertNotIn("favourite_shop_ids", client_session)
        with self.app.app_context():
            db = get_db(self.app)
            try:
                listing_count = db.execute(
                    "SELECT COUNT(*) AS count FROM anonymous_favourite_listings"
                ).fetchone()["count"]
                shop_count = db.execute(
                    "SELECT COUNT(*) AS count FROM anonymous_favourite_shops"
                ).fetchone()["count"]
                self.assertEqual(listing_count, 1)
                self.assertEqual(shop_count, 1)
            finally:
                db.close()

    def test_saved_searches_create_list_and_delete(self) -> None:
        response = self.client.post(
            "/saved-searches",
            data={"q": "teak", "category": "lounge chairs", "sort": "newest"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/favourites")
        searches_response = self.client.get("/favourites")
        self.assertIn("teak / lounge chairs", searches_response.text)
        self.assertIn("Saved searches", searches_response.text)

        with self.app.app_context():
            db = get_db(self.app)
            try:
                saved = db.execute(
                    """
                    SELECT id, query_string
                    FROM anonymous_saved_searches
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIn("q=teak", saved["query_string"])
                self.assertIn("category=lounge+chairs", saved["query_string"])
                self.assertIn("sort=newest", saved["query_string"])
                saved_id = int(saved["id"])
            finally:
                db.close()

        delete_response = self.client.post(
            f"/saved-searches/{saved_id}/delete",
            follow_redirects=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertIn("No saved searches yet.", delete_response.text)

    def test_saved_searches_route_redirects_to_favourites(self) -> None:
        response = self.client.get("/saved-searches")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/favourites")

    def test_saved_searches_do_not_duplicate_same_query(self) -> None:
        for _index in range(2):
            self.client.post(
                "/saved-searches",
                data={"q": "teak", "category": "lounge chairs"},
            )

        with self.app.app_context():
            db = get_db(self.app)
            try:
                count = db.execute(
                    "SELECT COUNT(*) AS count FROM anonymous_saved_searches"
                ).fetchone()["count"]
                self.assertEqual(count, 1)
            finally:
                db.close()

    def test_saved_searches_fall_back_to_same_host_referrer_query(self) -> None:
        response = self.client.post(
            "/saved-searches",
            headers={"Referer": "http://localhost/?price_max=1000"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/?price_max=1000"', response.text)
        self.assertIn("(1)", response.text)

    def test_saved_searches_fall_back_to_apex_referrer_query(self) -> None:
        response = self.client.post(
            "/saved-searches",
            headers={"Referer": "https://montrealmcm.ca/?price_max=1000"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/?price_max=1000"', response.text)
        self.assertIn("(1)", response.text)

    def test_saved_searches_ignore_cross_host_referrer_query(self) -> None:
        response = self.client.post(
            "/saved-searches",
            headers={"Referer": "https://example.com/?price_max=1000"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("No saved searches yet.", response.text)
        self.assertIn("(0)", response.text)

    def test_refresh_runs_without_request_context(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch("mcm.refresh.fetch_source_listings", return_value=([], None)):
                    refresh_all_sources(db, progress=lambda _message: None)
                listing = db.execute(
                    """
                    SELECT is_active, availability_status
                    FROM listings
                    WHERE source_listing_key = 'sample-key'
                    """
                ).fetchone()
                self.assertEqual(listing["is_active"], 0)
                self.assertEqual(listing["availability_status"], "removed")
            finally:
                db.close()

    def test_refresh_records_price_history_changes(self) -> None:
        item = {
            "source_listing_url": "https://example.com/listing",
            "source_listing_key": "sample-key",
            "title": "Sample Chair",
            "price_raw": "$200",
            "price_value": 200,
            "currency": "CAD",
            "primary_image_url": "https://example.com/image.jpg",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "Test Designer",
            "maker": "",
            "era": "1960s",
            "materials": "teak",
            "dimensions_text": "20 x 20 x 30",
            "condition_text": "Good",
            "location_text": "Montreal, QC",
            "source_description": "Sample description",
            "ingest_source_type": "test",
            "parse_confidence": 1.0,
        }

        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch("mcm.refresh.fetch_source_listings", return_value=([item], None)):
                    refresh_source_by_slug(db, "morceau")
                event = db.execute(
                    """
                    SELECT from_price_raw, from_price_value, to_price_raw, to_price_value
                    FROM listing_price_events
                    WHERE listing_id = ?
                    """,
                    (self.listing_id,),
                ).fetchone()
                self.assertEqual(event["from_price_raw"], "$250")
                self.assertEqual(event["from_price_value"], 250)
                self.assertEqual(event["to_price_raw"], "$200")
                self.assertEqual(event["to_price_value"], 200)
            finally:
                db.close()

        response = self.client.get(f"/listing/{public_item_number(self.listing_id)}")
        self.assertIn("History", response.text)
        self.assertIn("$250", response.text)
        self.assertIn("$200", response.text)

    def test_refresh_records_discovered_price_history(self) -> None:
        item = {
            "source_listing_url": "https://example.com/new-listing",
            "source_listing_key": "new-price-key",
            "title": "New Price Chair",
            "price_raw": "$500",
            "price_value": 500,
            "currency": "CAD",
            "primary_image_url": "",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "",
            "maker": "",
            "era": "",
            "materials": "teak",
            "dimensions_text": "",
            "condition_text": "",
            "location_text": "Montreal, QC",
            "source_description": "",
            "ingest_source_type": "test",
            "parse_confidence": 1.0,
        }

        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch("mcm.refresh.fetch_source_listings", return_value=([item], None)):
                    refresh_source_by_slug(db, "morceau")
                event = db.execute(
                    """
                    SELECT from_price_raw, from_price_value, to_price_raw,
                           to_price_value, event_type
                    FROM listing_price_events
                    WHERE source_listing_key = 'new-price-key'
                    """
                ).fetchone()
                self.assertEqual(event["from_price_raw"], "")
                self.assertIsNone(event["from_price_value"])
                self.assertEqual(event["to_price_raw"], "$500")
                self.assertEqual(event["to_price_value"], 500)
                self.assertEqual(event["event_type"], "discovered")
            finally:
                db.close()

    def test_refresh_records_per_source_job_status(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch("mcm.refresh.fetch_source_listings", return_value=([], None)):
                    refresh_all_sources(db, progress=lambda _message: None)
                job = db.execute(
                    """
                    SELECT source_slug, status, listings_found, hidden_count, finished_at
                    FROM refresh_jobs
                    WHERE source_slug = 'morceau'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertEqual(job["source_slug"], "morceau")
                self.assertEqual(job["status"], "success")
                self.assertEqual(job["listings_found"], 0)
                self.assertGreaterEqual(job["hidden_count"], 1)
                self.assertTrue(job["finished_at"])
            finally:
                db.close()

    def test_refresh_seeds_missing_source_shop(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute("DELETE FROM shops WHERE slug = 'chez-lamothe'")
                db.commit()
                with patch("mcm.refresh.fetch_source_listings", return_value=([], None)):
                    refresh_source_by_slug(db, "chez-lamothe")
                shop = db.execute(
                    "SELECT active, name FROM shops WHERE slug = 'chez-lamothe'"
                ).fetchone()
                job = db.execute(
                    """
                    SELECT status
                    FROM refresh_jobs
                    WHERE source_slug = 'chez-lamothe'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(shop)
                self.assertEqual(shop["active"], 1)
                self.assertEqual(shop["name"], "Chez Lamothe")
                self.assertEqual(job["status"], "success")
            finally:
                db.close()

    def test_refresh_skips_new_sold_out_archive_items(self) -> None:
        archive_item = {
            "source_listing_url": "https://example.com/archive-sold",
            "source_listing_key": "archive-sold-key",
            "title": "Already Sold Archive Chair",
            "price_raw": "Sold",
            "price_value": None,
            "currency": "CAD",
            "primary_image_url": "",
            "additional_image_urls": [],
            "availability_status": "sold_out",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "",
            "maker": "",
            "era": "",
            "materials": "",
            "dimensions_text": "",
            "condition_text": "",
            "location_text": "Montreal, QC",
            "source_description": "Archive data",
            "ingest_source_type": "live_fetch",
            "parse_confidence": 0.8,
        }
        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch(
                    "mcm.refresh.fetch_source_listings",
                    return_value=([archive_item], None),
                ):
                    refresh_all_sources(db, progress=lambda _message: None)
                listing = db.execute(
                    "SELECT id FROM listings WHERE source_listing_key = 'archive-sold-key'"
                ).fetchone()
                event = db.execute(
                    """
                    SELECT id
                    FROM listing_availability_events
                    WHERE source_listing_key = 'archive-sold-key'
                    """
                ).fetchone()
                job = db.execute(
                    """
                    SELECT listings_found, new_count
                    FROM refresh_jobs
                    WHERE source_slug = 'morceau'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNone(listing)
                self.assertIsNone(event)
                self.assertEqual(job["listings_found"], 1)
                self.assertEqual(job["new_count"], 0)
            finally:
                db.close()

    def test_refresh_keeps_existing_listing_that_becomes_sold_out(self) -> None:
        sold_item = {
            "source_listing_url": "https://example.com/listing",
            "source_listing_key": "sample-key",
            "title": "Sample Chair",
            "price_raw": "Sold",
            "price_value": None,
            "currency": "CAD",
            "primary_image_url": "",
            "additional_image_urls": [],
            "availability_status": "sold_out",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "Test Designer",
            "maker": "",
            "era": "1960s",
            "materials": "teak",
            "dimensions_text": "20 x 20 x 30",
            "condition_text": "Good",
            "location_text": "Montreal, QC",
            "source_description": "Sample description",
            "ingest_source_type": "live_fetch",
            "parse_confidence": 1.0,
        }
        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch(
                    "mcm.refresh.fetch_source_listings",
                    return_value=([sold_item], None),
                ):
                    refresh_all_sources(db, progress=lambda _message: None)
                listing = db.execute(
                    """
                    SELECT is_active, availability_status, first_seen_at
                    FROM listings
                    WHERE source_listing_key = 'sample-key'
                    """
                ).fetchone()
                event = db.execute(
                    """
                    SELECT from_status, to_status, event_type
                    FROM listing_availability_events
                    WHERE listing_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (self.listing_id,),
                ).fetchone()
                self.assertEqual(listing["is_active"], 1)
                self.assertEqual(listing["availability_status"], "sold_out")
                self.assertEqual(listing["first_seen_at"], "2026-05-06T00:00:00+00:00")
                self.assertEqual(event["from_status"], "available")
                self.assertEqual(event["to_status"], "sold_out")
                self.assertEqual(event["event_type"], "source_refresh")
            finally:
                db.close()

    def test_refresh_does_not_resurrect_removed_sold_archive_items(self) -> None:
        sold_item = {
            "source_listing_url": "https://example.com/listing",
            "source_listing_key": "sample-key",
            "title": "Sample Chair",
            "price_raw": "Sold",
            "price_value": None,
            "currency": "CAD",
            "primary_image_url": "",
            "additional_image_urls": [],
            "availability_status": "sold_out",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "Test Designer",
            "maker": "",
            "era": "1960s",
            "materials": "teak",
            "dimensions_text": "20 x 20 x 30",
            "condition_text": "Good",
            "location_text": "Montreal, QC",
            "source_description": "Sample description",
            "ingest_source_type": "live_fetch",
            "parse_confidence": 1.0,
        }
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET is_active = 0, availability_status = 'removed'
                    WHERE source_listing_key = 'sample-key'
                    """
                )
                db.commit()
                with patch(
                    "mcm.refresh.fetch_source_listings",
                    return_value=([sold_item], None),
                ):
                    refresh_all_sources(db, progress=lambda _message: None)
                listing = db.execute(
                    """
                    SELECT is_active, availability_status
                    FROM listings
                    WHERE source_listing_key = 'sample-key'
                    """
                ).fetchone()
                event = db.execute(
                    """
                    SELECT id
                    FROM listing_availability_events
                    WHERE listing_id = ? AND to_status = 'sold_out'
                    """,
                    (self.listing_id,),
                ).fetchone()
                self.assertEqual(listing["is_active"], 0)
                self.assertEqual(listing["availability_status"], "removed")
                self.assertIsNone(event)
            finally:
                db.close()

    def test_cron_can_refresh_one_source(self) -> None:
        response = self.client.post("/cron/refresh/morceau")
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            "/cron/refresh/not-a-source",
            headers={"X-Cloudflare-Scheduled": "1"},
        )
        self.assertEqual(response.status_code, 404)

        with patch("mcm.refresh.fetch_source_listings", return_value=([], None)):
            response = self.client.post(
                "/cron/refresh/morceau",
                headers={"X-Cloudflare-Scheduled": "1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "morceau")
        self.assertEqual(response.json["listings"], 0)

    def test_cron_can_refresh_one_showroom_chunk_without_deactivating_missing_items(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute(
                    "SELECT id FROM shops WHERE slug = 'showroom-montreal'"
                ).fetchone()
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title, normalized_title,
                        price_raw, price_value, currency, primary_image_url, additional_image_urls,
                        availability_status, shipping_scope, ships_to_montreal, shipping_note,
                        last_seen_at, last_checked_at, first_seen_at, category, subcategory, designer,
                        maker, era, materials, dimensions_text, condition_text, location_text,
                        source_description, ingest_source_type, parse_confidence, dedupe_group_id,
                        is_active, is_featured, manual_notes, availability_override, category_override
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        shop["id"],
                        "https://www.showroommtl.com/nouveaute",
                        "showroom:existing",
                        "Existing Showroom Chair",
                        "existing showroom chair",
                        "$250",
                        250,
                        "CAD",
                        "",
                        "[]",
                        "available",
                        "local_quote",
                        1,
                        "Local quote",
                        "2026-05-06T00:00:00+00:00",
                        "2026-05-06T00:00:00+00:00",
                        "2026-05-06T00:00:00+00:00",
                        "lounge chairs",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "Montreal, QC",
                        "Existing data",
                        "test",
                        1.0,
                        "",
                        1,
                        0,
                        "",
                        "",
                        "",
                    ),
                )
                db.commit()
            finally:
                db.close()

        chunk_item = {
            "source_listing_url": "https://www.showroommtl.com/nouveaute",
            "source_listing_key": "showroom:new",
            "title": "New Showroom Chair",
            "price_raw": "$350",
            "price_value": 350,
            "currency": "CAD",
            "primary_image_url": "",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "local_quote",
            "ships_to_montreal": 1,
            "shipping_note": "Local quote",
            "category": "lounge chairs",
            "designer": "",
            "maker": "",
            "era": "",
            "materials": "",
            "dimensions_text": "",
            "condition_text": "",
            "location_text": "Montreal, QC",
            "source_description": "Chunk data",
            "ingest_source_type": "live_fetch",
            "parse_confidence": 0.9,
        }
        with patch("mcm.refresh.fetch_showroom_entry_listings", return_value=([chunk_item], None)):
            response = self.client.post(
                "/cron/refresh/showroom-montreal/chunk/0",
                headers={"X-Cloudflare-Scheduled": "1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "showroom-montreal")
        self.assertEqual(response.json["chunk"], 0)
        self.assertEqual(response.json["hidden"], 0)

        with self.app.app_context():
            db = get_db(self.app)
            try:
                existing = db.execute(
                    """
                    SELECT is_active, availability_status
                    FROM listings
                    WHERE source_listing_key = 'showroom:existing'
                    """
                ).fetchone()
                created = db.execute(
                    "SELECT id FROM listings WHERE source_listing_key = 'showroom:new'"
                ).fetchone()
                job = db.execute(
                    """
                    SELECT chunk_index, entry_url
                    FROM refresh_jobs
                    WHERE source_slug = 'showroom-montreal'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertEqual(existing["is_active"], 1)
                self.assertEqual(existing["availability_status"], "available")
                self.assertIsNotNone(created)
                self.assertEqual(job["chunk_index"], 0)
                self.assertEqual(job["entry_url"], "https://www.showroommtl.com/nouveaute")
            finally:
                db.close()

    def test_cron_can_refresh_one_le_centerpiece_chunk(self) -> None:
        chunk_item = {
            "source_listing_url": "https://lecenterpiece.com/products/test-chair",
            "source_listing_key": "https://lecenterpiece.com/products/test-chair",
            "title": "Test Chair",
            "price_raw": "$350.00 CAD",
            "price_value": 350,
            "currency": "CAD",
            "primary_image_url": "",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "international",
            "ships_to_montreal": 1,
            "shipping_note": "Local quote",
            "category": "lounge chairs",
            "designer": "",
            "maker": "",
            "era": "",
            "materials": "",
            "dimensions_text": "",
            "condition_text": "",
            "location_text": "Montreal, QC",
            "source_description": "Chunk data",
            "ingest_source_type": "live_fetch",
            "parse_confidence": 0.9,
        }
        with patch(
            "mcm.refresh.fetch_le_centerpiece_entry_listings",
            return_value=([chunk_item], None),
        ):
            response = self.client.post(
                "/cron/refresh/le-centerpiece/chunk/0",
                headers={"X-Cloudflare-Scheduled": "1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "le-centerpiece")
        self.assertEqual(response.json["chunk"], 0)
        self.assertEqual(response.json["hidden"], 0)

    def test_cron_can_refresh_one_chez_lamothe_chunk(self) -> None:
        chunk_item = {
            "source_listing_url": "https://www.chezlamothe.com/product/test-chair/1",
            "source_listing_key": "chez-lamothe:test-chair",
            "title": "Test Chair",
            "price_raw": "$350.00 CAD",
            "price_value": 350,
            "currency": "CAD",
            "primary_image_url": "https://example.com/chair.jpg",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "local_quote",
            "ships_to_montreal": 1,
            "shipping_note": "Local quote",
            "category": "lounge chairs",
            "designer": "",
            "maker": "",
            "era": "",
            "materials": "",
            "dimensions_text": "",
            "condition_text": "",
            "location_text": "Montreal, QC",
            "source_description": "Chunk data",
            "ingest_source_type": "live_fetch",
            "parse_confidence": 0.9,
        }
        with patch(
            "mcm.refresh.fetch_chez_lamothe_page_listings",
            return_value=([chunk_item], None),
        ):
            response = self.client.post(
                "/cron/refresh/chez-lamothe/chunk/0",
                headers={"X-Cloudflare-Scheduled": "1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "chez-lamothe")
        self.assertEqual(response.json["chunk"], 0)
        self.assertEqual(response.json["hidden"], 0)

    def test_chunked_source_reconciliation_requires_all_recent_chunks(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute(
                    "SELECT id FROM shops WHERE slug = 'showroom-montreal'"
                ).fetchone()
                self.assertIsNotNone(shop)
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era,
                        materials, dimensions_text, width, depth, height, condition_text,
                        location_text, source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, 'https://www.showroommtl.com/nouveaute', 'showroom:stale',
                        'Stale Showroom Chair', 'stale showroom chair', '$500', 500, 'CAD',
                        '', '[]', 'available', 'local_quote', 1, 'Local quote',
                        '2026-05-01T00:00:00+00:00', '2026-05-01T00:00:00+00:00',
                        '2026-05-01T00:00:00+00:00', 'lounge chairs', '', '', '', '',
                        'teak', '', NULL, NULL, NULL, '', 'Montreal, QC', '', 'test', 1.0,
                        '', 1, 0, '', '', ''
                    )
                    """,
                    (shop["id"],),
                )
                for chunk_index in range(11):
                    db.execute(
                        """
                        INSERT INTO refresh_jobs (
                            shop_id, source_slug, chunk_index, entry_url, started_at,
                            finished_at, status, listings_found
                        ) VALUES (?, 'showroom-montreal', ?, ?, ?, ?, 'success', 10)
                        """,
                        (
                            shop["id"],
                            chunk_index,
                            f"https://www.showroommtl.com/chunk-{chunk_index}",
                            f"2026-05-29T10:{chunk_index:02d}:00+00:00",
                            f"2026-05-29T10:{chunk_index:02d}:10+00:00",
                        ),
                    )

                result = reconcile_chunked_source(
                    db,
                    "showroom-montreal",
                    since="2026-05-29T09:00:00+00:00",
                )
                listing = db.execute(
                    "SELECT is_active FROM listings WHERE source_listing_key = 'showroom:stale'"
                ).fetchone()

                self.assertIn("Missing successful chunk jobs", result.error)
                self.assertEqual(result.hidden_count, 0)
                self.assertEqual(listing["is_active"], 1)
            finally:
                db.close()

    def test_chunked_source_reconciliation_hides_missing_after_all_chunks(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute(
                    "SELECT id FROM shops WHERE slug = 'showroom-montreal'"
                ).fetchone()
                self.assertIsNotNone(shop)
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era,
                        materials, dimensions_text, width, depth, height, condition_text,
                        location_text, source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, 'https://www.showroommtl.com/nouveaute', 'showroom:stale',
                        'Stale Showroom Chair', 'stale showroom chair', '$500', 500, 'CAD',
                        '', '[]', 'available', 'local_quote', 1, 'Local quote',
                        '2026-05-01T00:00:00+00:00', '2026-05-01T00:00:00+00:00',
                        '2026-05-01T00:00:00+00:00', 'lounge chairs', '', '', '', '',
                        'teak', '', NULL, NULL, NULL, '', 'Montreal, QC', '', 'test', 1.0,
                        '', 1, 0, '', '', ''
                    )
                    """,
                    (shop["id"],),
                )
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era,
                        materials, dimensions_text, width, depth, height, condition_text,
                        location_text, source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, 'https://www.showroommtl.com/nouveaute', 'showroom:fresh',
                        'Fresh Showroom Chair', 'fresh showroom chair', '$700', 700, 'CAD',
                        '', '[]', 'available', 'local_quote', 1, 'Local quote',
                        '2026-05-29T10:06:00+00:00', '2026-05-29T10:06:00+00:00',
                        '2026-05-29T10:06:00+00:00', 'lounge chairs', '', '', '', '',
                        'teak', '', NULL, NULL, NULL, '', 'Montreal, QC', '', 'test', 1.0,
                        '', 1, 0, '', '', ''
                    )
                    """,
                    (shop["id"],),
                )
                for chunk_index in range(12):
                    db.execute(
                        """
                        INSERT INTO refresh_jobs (
                            shop_id, source_slug, chunk_index, entry_url, started_at,
                            finished_at, status, listings_found
                        ) VALUES (?, 'showroom-montreal', ?, ?, ?, ?, 'success', 10)
                        """,
                        (
                            shop["id"],
                            chunk_index,
                            f"https://www.showroommtl.com/chunk-{chunk_index}",
                            f"2026-05-29T10:{chunk_index:02d}:00+00:00",
                            f"2026-05-29T10:{chunk_index:02d}:10+00:00",
                        ),
                    )

                result = reconcile_chunked_source(
                    db,
                    "showroom-montreal",
                    since="2026-05-29T09:00:00+00:00",
                )
                stale = db.execute(
                    """
                    SELECT is_active, availability_status
                    FROM listings
                    WHERE source_listing_key = 'showroom:stale'
                    """
                ).fetchone()
                fresh = db.execute(
                    "SELECT is_active FROM listings WHERE source_listing_key = 'showroom:fresh'"
                ).fetchone()
                event = db.execute(
                    """
                    SELECT event_type, to_status
                    FROM listing_availability_events
                    WHERE source_listing_key = 'showroom:stale'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()

                self.assertEqual(result.error, "")
                self.assertEqual(result.hidden_count, 1)
                self.assertEqual(stale["is_active"], 0)
                self.assertEqual(stale["availability_status"], "removed")
                self.assertEqual(fresh["is_active"], 1)
                self.assertEqual(event["event_type"], "source_reconciliation")
                self.assertEqual(event["to_status"], "removed")
            finally:
                db.close()

    def test_refresh_error_does_not_deactivate_existing_inventory(self) -> None:
        fallback_item = {
            "source_listing_url": "https://example.com/fallback",
            "source_listing_key": "fallback-key",
            "title": "Fallback Chair",
            "price_raw": "$100",
            "price_value": 100,
            "currency": "CAD",
            "primary_image_url": "",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Fallback seed",
            "category": "lounge chairs",
            "designer": "",
            "maker": "",
            "era": "",
            "materials": "",
            "dimensions_text": "",
            "condition_text": "",
            "location_text": "Montreal, QC",
            "source_description": "Fallback data",
            "ingest_source_type": "seed_fallback",
            "parse_confidence": 0.45,
        }
        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch(
                    "mcm.refresh.fetch_source_listings",
                    return_value=([fallback_item], "temporary source failure"),
                ):
                    refresh_all_sources(db, progress=lambda _message: None)
                listing = db.execute(
                    """
                    SELECT is_active, availability_status
                    FROM listings
                    WHERE source_listing_key = 'sample-key'
                    """
                ).fetchone()
                fallback = db.execute(
                    """
                    SELECT l.id
                    FROM listings l
                    JOIN shops s ON s.id = l.source_shop_id
                    WHERE l.source_listing_key = 'fallback-key'
                      AND s.slug = 'morceau'
                    """,
                ).fetchone()
                self.assertEqual(listing["is_active"], 1)
                self.assertEqual(listing["availability_status"], "available")
                self.assertIsNone(fallback)
            finally:
                db.close()

    def test_refresh_reconciles_source_key_drift(self) -> None:
        refreshed_item = {
            "source_listing_url": "https://example.com/listing?lightbox=new-key",
            "source_listing_key": "drifted-key",
            "title": "Sample Chair",
            "price_raw": "$250",
            "price_value": 250,
            "currency": "CAD",
            "primary_image_url": "https://example.com/image.jpg",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "Test Designer",
            "maker": "",
            "era": "1960s",
            "materials": "teak",
            "dimensions_text": "20 x 20 x 30",
            "condition_text": "Good",
            "location_text": "Montreal, QC",
            "source_description": "Sample description",
            "ingest_source_type": "test",
            "parse_confidence": 1.0,
        }
        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch(
                    "mcm.refresh.fetch_source_listings",
                    return_value=([refreshed_item], None),
                ):
                    refresh_all_sources(db, progress=lambda _message: None)
                listing = db.execute(
                    """
                    SELECT id, source_listing_key, first_seen_at, availability_status
                    FROM listings
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                ).fetchone()
                self.assertEqual(listing["source_listing_key"], "drifted-key")
                self.assertEqual(listing["first_seen_at"], "2026-05-06T00:00:00+00:00")
                self.assertEqual(listing["availability_status"], "available")
            finally:
                db.close()

    def test_refresh_reconciles_source_key_drift_with_description_case_change(self) -> None:
        refreshed_item = {
            "source_listing_url": "https://example.com/listing?lightbox=new-key",
            "source_listing_key": "drifted-key",
            "title": "Sample Chair",
            "price_raw": "$250",
            "price_value": 250,
            "currency": "CAD",
            "primary_image_url": "https://example.com/different-image.jpg",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "Test Designer",
            "maker": "",
            "era": "1960s",
            "materials": "teak",
            "dimensions_text": "20 x 20 x 30",
            "condition_text": "Good",
            "location_text": "Montreal, QC",
            "source_description": "sample DESCRIPTION",
            "ingest_source_type": "test",
            "parse_confidence": 1.0,
        }
        with self.app.app_context():
            db = get_db(self.app)
            try:
                with patch(
                    "mcm.refresh.fetch_source_listings",
                    return_value=([refreshed_item], None),
                ):
                    refresh_all_sources(db, progress=lambda _message: None)
                listing = db.execute(
                    """
                    SELECT id, source_listing_key, first_seen_at, primary_image_url
                    FROM listings
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                ).fetchone()
                self.assertEqual(listing["source_listing_key"], "drifted-key")
                self.assertEqual(listing["first_seen_at"], "2026-05-06T00:00:00+00:00")
                self.assertEqual(
                    listing["primary_image_url"], "https://example.com/different-image.jpg"
                )
            finally:
                db.close()

    def test_refresh_logs_ambiguous_source_key_drift(self) -> None:
        ambiguous_item = {
            "source_listing_url": "https://example.com/listing?lightbox=ambiguous-key",
            "source_listing_key": "ambiguous-key",
            "title": "Sample Chair",
            "price_raw": "$250",
            "price_value": 250,
            "currency": "CAD",
            "primary_image_url": "https://example.com/image.jpg",
            "additional_image_urls": [],
            "availability_status": "available",
            "shipping_scope": "canada",
            "ships_to_montreal": 1,
            "shipping_note": "Ships to Montreal",
            "category": "lounge chairs",
            "designer": "Test Designer",
            "maker": "",
            "era": "1960s",
            "materials": "teak",
            "dimensions_text": "20 x 20 x 30",
            "condition_text": "Good",
            "location_text": "Montreal, QC",
            "source_description": "Sample description",
            "ingest_source_type": "test",
            "parse_confidence": 1.0,
        }
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute("SELECT id FROM shops WHERE slug = 'morceau'").fetchone()
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era,
                        materials, dimensions_text, condition_text, location_text,
                        source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, 'https://example.com/listing-2', 'sample-key-2', 'Sample Chair',
                        'sample chair', '$250', 250, 'CAD', 'https://example.com/image.jpg',
                        '[]', 'available', 'canada', 1, 'Ships to Montreal',
                        '2026-05-06T00:00:00+00:00', '2026-05-06T00:00:00+00:00',
                        '2026-05-06T00:00:00+00:00', 'lounge chairs', '', 'Test Designer',
                        '', '1960s', 'teak', '20 x 20 x 30', 'Good', 'Montreal, QC',
                        'Sample description', 'test', 1.0, '', 1, 0, '', '', ''
                    )
                    """,
                    (shop["id"],),
                )
                db.commit()
                with patch(
                    "mcm.refresh.fetch_source_listings",
                    return_value=([ambiguous_item], None),
                ):
                    refresh_all_sources(db, progress=lambda _message: None)
                review = db.execute(
                    """
                    SELECT source_listing_key, candidate_listing_ids, status
                    FROM listing_identity_reviews
                    WHERE source_listing_key = 'ambiguous-key'
                    """
                ).fetchone()
                self.assertIsNotNone(review)
                self.assertEqual(review["status"], "open")
                self.assertIn(str(self.listing_id), review["candidate_listing_ids"])
            finally:
                db.close()

    def test_detail_page_shows_internal_item_number(self) -> None:
        response = self.client.get(f"/listing/{public_item_number(self.listing_id)}")
        self.assertIn(public_item_number(self.listing_id), response.text)

    def test_detail_page_shows_first_seen_date_in_freshness(self) -> None:
        response = self.client.get(f"/listing/{public_item_number(self.listing_id)}")
        self.assertIn("first seen May 6, 2026", response.text)
        self.assertNotIn("last checked 2026-05-06T00:00:00+00:00", response.text)

    def test_detail_page_localizes_first_seen_date(self) -> None:
        response = self.client.get(f"/listing/{public_item_number(self.listing_id)}?lang=fr")
        self.assertIn("première vue 6 mai 2026", response.text)
        self.assertNotIn("May 6, 2026", response.text)

    def test_detail_page_uses_lowercase_freshness_status(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET last_checked_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now(UTC).isoformat(), self.listing_id),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get(f"/listing/{public_item_number(self.listing_id)}")
        self.assertIn("checked today", response.text)
        self.assertNotIn("Checked today", response.text)

    def test_price_display_uses_locale_not_source_format(self) -> None:
        update_listing_price(self.app, self.listing_id, "3500 $ / 6", 3500)

        english_response = self.client.get(
            f"/listing/{public_item_number(self.listing_id)}?lang=en"
        )
        french_response = self.client.get(f"/listing/{public_item_number(self.listing_id)}?lang=fr")

        self.assertIn("$3,500 CAD for set of 6", english_response.text)
        self.assertNotIn("3500 $ / 6", english_response.text)
        self.assertIn("3 500 $ CA pour l’ensemble de 6", french_response.text)

    def test_price_display_localizes_known_showroom_qualifiers(self) -> None:
        cases = [
            ("3250 $ / paire", 3250, "$3,250 CAD for pair", "3 250 $ CA pour la paire"),
            ("550 $ ch.", 550, "$550 CAD each", "550 $ CA chaque"),
            ("425 $ / l'ens.", 425, "$425 CAD for the set", "425 $ CA pour l’ensemble"),
            ("1200 $ / 4", 1200, "$1,200 CAD for set of 4", "1 200 $ CA pour l’ensemble de 4"),
        ]
        for raw, value, expected_en, expected_fr in cases:
            with self.subTest(raw=raw):
                update_listing_price(self.app, self.listing_id, raw, value)
                english_response = self.client.get(
                    f"/listing/{public_item_number(self.listing_id)}?lang=en"
                )
                french_response = self.client.get(
                    f"/listing/{public_item_number(self.listing_id)}?lang=fr"
                )
                self.assertIn(expected_en, english_response.text)
                self.assertIn(expected_fr, french_response.text)

    def test_quote_required_price_fallback_is_localized(self) -> None:
        update_listing_price(self.app, self.listing_id, "Contactez nous pour les details", None)

        english_response = self.client.get(
            f"/listing/{public_item_number(self.listing_id)}?lang=en"
        )
        french_response = self.client.get(f"/listing/{public_item_number(self.listing_id)}?lang=fr")

        self.assertIn("Contact us for details", english_response.text)
        self.assertNotIn("Contactez nous pour les details", english_response.text)
        self.assertIn("Contactez-nous pour les détails", french_response.text)

    def test_favourites_page_uses_localized_price_display(self) -> None:
        update_listing_price(self.app, self.listing_id, "3250 $ / paire", 3250)
        self.client.post(f"/favourites/listing/{self.listing_id}")

        response = self.client.get("/favourites?lang=en")

        self.assertIn("$3,250 CAD for pair", response.text)
        self.assertNotIn("3250 $ / paire", response.text)

    def test_listing_grid_shows_first_seen_date(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET last_checked_at = '2026-05-07T00:00:00+00:00'
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get("/")
        self.assertIn("first seen May 6, 2026", response.text)
        self.assertNotIn("Since May 6, 2026", response.text)
        self.assertNotIn("2026-05-07", response.text)
        self.assertNotIn("Checked today", response.text)

    def test_listing_count_uses_singular_label(self) -> None:
        response = self.client.get("/")
        self.assertIn("1 listing", response.text)
        self.assertNotIn("1 listings", response.text)

    def test_listing_grid_lazy_loads_cards_in_pages(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute("SELECT id FROM shops WHERE slug = 'morceau'").fetchone()
                assert shop is not None
                for index in range(60):
                    db.execute(
                        """
                        INSERT INTO listings (
                            source_shop_id, source_listing_url, source_listing_key, title,
                            normalized_title, price_raw, price_value, currency,
                            primary_image_url, additional_image_urls, availability_status,
                            shipping_scope, ships_to_montreal, shipping_note, last_seen_at,
                            last_checked_at, first_seen_at, category, subcategory, designer,
                            maker, era, materials, dimensions_text, width, depth, height,
                            condition_text, location_text, source_description,
                            ingest_source_type, parse_confidence, dedupe_group_id, is_active,
                            is_featured, manual_notes, availability_override, category_override
                        ) VALUES (
                            ?, ?, ?, ?, ?, '$250', 250, 'CAD', '', '[]', 'available',
                            'canada', 1, 'Ships to Montreal',
                            '2026-05-07T00:00:00+00:00',
                            '2026-05-07T00:00:00+00:00',
                            '2026-05-07T00:00:00+00:00',
                            'lounge chairs', '', '', '', '1960s', 'teak', '',
                            NULL, NULL, NULL, '', 'Montreal, QC', '', 'test', 1.0,
                            '', 1, 0, '', '', ''
                        )
                        """,
                        (
                            shop["id"],
                            f"https://example.com/lazy-{index}",
                            f"lazy-{index}",
                            f"Lazy Chair {index}",
                            f"lazy chair {index}",
                        ),
                    )
                db.commit()
            finally:
                db.close()

        response = self.client.get("/")
        self.assertIn("61 listings", response.text)
        self.assertEqual(response.text.count('class="listing-card group'), 48)
        self.assertIn("Load more listings", response.text)
        self.assertIn("offset=48", response.text)

        next_response = self.client.get("/?offset=48", headers={"HX-Request": "true"})
        self.assertNotIn("listing-results-toolbar", next_response.text)
        self.assertEqual(next_response.text.count('class="listing-card group'), 13)
        self.assertNotIn("Load more listings", next_response.text)
        self.assertNotIn("X-MCM-App-Ms", next_response.headers)

    def test_location_filter_uses_existing_locations(self) -> None:
        response = self.client.get("/")

        self.assertIn('name="location"', response.text)
        self.assertIn('<option value="">All locations</option>', response.text)
        self.assertIn('<option value="Montreal, QC"', response.text)
        self.assertNotIn('placeholder="Montreal, Ottawa, Toronto"', response.text)

    def test_listing_grid_omits_redundant_location(self) -> None:
        response = self.client.get("/")
        self.assertIn("lounge chairs", response.text)
        self.assertNotIn("Montreal, QC · lounge chairs", response.text)

    def test_listing_card_images_are_lazy_loaded(self) -> None:
        response = self.client.get("/")
        self.assertIn('loading="lazy"', response.text)
        self.assertIn('decoding="async"', response.text)

    def test_listing_images_render_unavailable_fallback(self) -> None:
        response = self.client.get("/")

        self.assertIn("data-image-fallback", response.text)
        self.assertIn("onerror=", response.text)
        self.assertIn("Image not available", response.text)

        css = (Path(__file__).parent.parent / "static" / "app.css").read_text()
        self.assertIn("img[data-image-fallback].hidden", css)

    def test_detail_page_localizes_canonical_ingest_values(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute(
                    "SELECT shipping_summary FROM shops WHERE slug = 'morceau'"
                ).fetchone()
                db.execute(
                    """
                    UPDATE listings
                    SET materials = 'teak',
                        condition_text = 'Restored',
                        era = '1960s',
                        shipping_note = ?
                    WHERE id = ?
                    """,
                    (shop["shipping_summary"], self.listing_id),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get(f"/listing/{public_item_number(self.listing_id)}?lang=fr")
        self.assertIn("teck", response.text)
        self.assertIn("Restauré", response.text)
        self.assertIn("années 1960", response.text)
        self.assertNotIn(">1960s<", response.text)
        self.assertIn("Livraison internationale offerte", response.text)
        self.assertNotIn("International shipping available", response.text)

    def test_filter_summary_localizes_material_value(self) -> None:
        response = self.client.get("/?lang=fr&material=teak")
        self.assertIn("Matériau: teck", response.text)

    def test_search_expands_english_material_to_french_source_text(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET title = 'Buffet en teck',
                        normalized_title = 'buffet en teck',
                        materials = '',
                        source_description = ''
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get("/?q=teak")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Buffet en teck", response.text)

    def test_search_expands_french_material_to_english_source_text(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET title = 'Danish teak sideboard',
                        normalized_title = 'danish teak sideboard',
                        materials = '',
                        source_description = ''
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get("/?q=teck")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Danish teak sideboard", response.text)

    def test_search_requires_each_expanded_token_group(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET title = 'Buffet en teck',
                        normalized_title = 'buffet en teck',
                        materials = '',
                        source_description = ''
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        match_response = self.client.get("/?q=teak sideboard")
        miss_response = self.client.get("/?q=teak lamp")

        self.assertIn("Buffet en teck", match_response.text)
        self.assertIn("0 listings", miss_response.text)

    def test_search_ranks_title_matches_before_description_matches(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET title = 'Generic Cabinet',
                        normalized_title = 'generic cabinet',
                        materials = '',
                        source_description = 'A teak sideboard in restored condition.'
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era, materials,
                        dimensions_text, width, depth, height, condition_text, location_text,
                        source_description, ingest_source_type, parse_confidence, dedupe_group_id,
                        is_active, is_featured, manual_notes, availability_override,
                        category_override
                    )
                    SELECT
                        source_shop_id, 'https://example.com/title-match', 'title-match-key',
                        'Teak Sideboard', 'teak sideboard', price_raw, price_value, currency,
                        primary_image_url, additional_image_urls, availability_status,
                        shipping_scope, ships_to_montreal, shipping_note, last_seen_at,
                        last_checked_at, first_seen_at, category, subcategory, designer, maker,
                        era, '', dimensions_text, width, depth, height, condition_text,
                        location_text, '', ingest_source_type, parse_confidence, dedupe_group_id,
                        is_active, is_featured, manual_notes, availability_override,
                        category_override
                    FROM listings
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
                rows = query_listings(
                    db,
                    {"q": "teak sideboard", "sort": "curated", "availability": "available"},
                    include_inactive=False,
                )
                self.assertGreaterEqual(len(rows), 2)
                self.assertEqual(rows[0]["title"], "Teak Sideboard")
                self.assertEqual(rows[1]["title"], "Generic Cabinet")
            finally:
                db.close()

    def test_material_dropdown_localizes_canonical_materials(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET materials = 'wood, metal, upholstery, cherry wood, sherpa'
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get("/?lang=fr")
        self.assertIn("bois", response.text)
        self.assertIn("métal", response.text)
        self.assertIn("revêtement", response.text)
        self.assertIn("bois de cerisier", response.text)
        self.assertIn("sherpa", response.text)

    def test_designer_filter_removes_contact_artifacts_and_canonicalizes_aliases(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute("SELECT id FROM shops WHERE slug = 'morceau'").fetchone()
                self.assertIsNotNone(shop)
                rows = [
                    ("artifact-designer", "Artifact Chair", "Ottawa. Contactez-nous", ""),
                    ("artifact-maker", "Artifact Table", "", "les détails - des frais s’appliques"),
                    ("wegner-alias", "Wegner Chair", "Hans Wegner", ""),
                    ("wegner-canonical", "Wegner Table", "Hans J. Wegner", ""),
                    ("eames-alias", "Eames Chair", "Charles and Ray Eames", ""),
                    ("eames-canonical", "Eames Table", "Charles & Ray Eames", ""),
                ]
                for source_key, title, designer, maker in rows:
                    db.execute(
                        """
                        INSERT INTO listings (
                            source_shop_id, source_listing_url, source_listing_key, title,
                            normalized_title, price_raw, price_value, currency, primary_image_url,
                            additional_image_urls, availability_status, shipping_scope,
                            ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                            first_seen_at, category, subcategory, designer, maker, era, materials,
                            dimensions_text, width, depth, height, condition_text, location_text,
                            source_description, ingest_source_type, parse_confidence,
                            dedupe_group_id, is_active, is_featured, manual_notes,
                            availability_override, category_override
                        ) VALUES (
                            ?, 'https://example.com/designer-test', ?, ?, ?, '$1', 1, 'CAD',
                            '', '[]', 'available', 'canada', 1, '', '2026-05-29T00:00:00+00:00',
                            '2026-05-29T00:00:00+00:00', '2026-05-29T00:00:00+00:00',
                            'furniture', '', ?, ?, '', '', '', NULL, NULL, NULL, '',
                            'Montreal, QC', '', 'test', 1.0, '', 1, 0, '', '', ''
                        )
                        """,
                        (shop["id"], source_key, title, title.lower(), designer, maker),
                    )
                db.commit()

                values = list_filter_values(db, "designer")

                self.assertNotIn("Ottawa. Contactez-nous", values)
                self.assertNotIn("les détails - des frais s’appliques", values)
                self.assertIn("Hans J. Wegner", values)
                self.assertNotIn("Hans Wegner", values)
                self.assertIn("Charles & Ray Eames", values)
                self.assertNotIn("Charles and Ray Eames", values)

                wegner_results = query_listings(
                    db,
                    {
                        "designer": "Hans J. Wegner",
                        "availability": "available",
                        "sort": "newest",
                    },
                    include_inactive=False,
                )
                self.assertEqual(
                    {"Wegner Chair", "Wegner Table"},
                    {listing["title"] for listing in wegner_results},
                )
            finally:
                db.close()

    def test_design_entity_aliases_normalize_designer_filter_and_search(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute("SELECT id FROM shops WHERE slug = 'morceau'").fetchone()
                self.assertIsNotNone(shop)
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era, materials,
                        dimensions_text, width, depth, height, condition_text, location_text,
                        source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, 'https://example.com/vodder', 'vodder-alias', 'Vodder Credenza',
                        'vodder credenza', '$1', 1, 'CAD', '', '[]', 'available', 'canada', 1,
                        '', '2026-05-29T00:00:00+00:00', '2026-05-29T00:00:00+00:00',
                        '2026-05-29T00:00:00+00:00', 'storage', '', 'A. Vodder', '',
                        '', 'rosewood', '', NULL, NULL, NULL, '', 'Montreal, QC', '', 'test',
                        1.0, '', 1, 0, '', '', ''
                    )
                    """,
                    (shop["id"],),
                )
                create_design_entity(
                    db,
                    canonical_name="Arne Vodder",
                    entity_type="creator",
                    aliases=["A. Vodder", "Arne Vodder"],
                    notes="Known Danish designer alias.",
                )

                values = list_filter_values(db, "designer")
                self.assertIn("Arne Vodder", values)
                self.assertNotIn("A. Vodder", values)

                filtered = query_listings(
                    db,
                    {
                        "designer": "Arne Vodder",
                        "availability": "available",
                        "sort": "newest",
                    },
                    include_inactive=False,
                )
                self.assertEqual(["Vodder Credenza"], [listing["title"] for listing in filtered])

                searched = query_listings(
                    db,
                    {"q": "Arne Vodder", "availability": "available", "sort": "curated"},
                    include_inactive=False,
                )
                self.assertIn("Vodder Credenza", [listing["title"] for listing in searched])
            finally:
                db.close()

    def test_admin_listing_can_create_design_entity_from_source_evidence(self) -> None:
        response = self.client.get(f"/admin/listings/{self.listing_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Source designer / maker", response.text)
        self.assertIn("Canonical creator", response.text)
        self.assertIn("Test Designer", response.text)

        response = self.client.post(
            f"/admin/listings/{self.listing_id}/design-entity",
            data={
                "canonical_name": "Test Designer Studio",
                "entity_type": "creator",
                "aliases": "Test Designer\nT. Designer",
                "evidence_role": "designer",
                "notes": "Reviewed from listing source text.",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            db = get_db(self.app)
            try:
                row = db.execute(
                    """
                    SELECT de.canonical_name, dea.alias, ldee.source_text, ldee.evidence_role
                    FROM design_entities de
                    JOIN design_entity_aliases dea ON dea.entity_id = de.id
                    JOIN listing_design_entity_evidence ldee ON ldee.entity_id = de.id
                    WHERE ldee.listing_id = ?
                    ORDER BY dea.alias
                    """,
                    (self.listing_id,),
                ).fetchall()
            finally:
                db.close()

        self.assertEqual({"Test Designer Studio"}, {entry["canonical_name"] for entry in row})
        self.assertIn("Test Designer", {entry["alias"] for entry in row})
        self.assertIn("T. Designer", {entry["alias"] for entry in row})
        self.assertEqual({"Test Designer"}, {entry["source_text"] for entry in row})
        self.assertEqual({"designer"}, {entry["evidence_role"] for entry in row})

    def test_design_entity_candidates_surface_unreviewed_source_names(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                candidates = list_design_entity_candidates(db)
            finally:
                db.close()

        self.assertIn("Test Designer", [candidate["source_text"] for candidate in candidates])

    def test_worker_refresh_source_config_matches_python_sources(self) -> None:
        worker_source = (PROJECT_ROOT / "src" / "worker.js").read_text()
        source_slugs_match = re.search(
            r"const SOURCE_SLUGS = \[(?P<body>.*?)\];",
            worker_source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(source_slugs_match)
        assert source_slugs_match is not None
        worker_source_slugs = re.findall(r'"([^"]+)"', source_slugs_match.group("body"))
        python_source_slugs = [source.slug for source in SOURCE_DEFINITIONS]
        self.assertEqual(python_source_slugs, worker_source_slugs)

        worker_chunk_source_slugs = {
            match.group("name"): match.group("slug")
            for match in re.finditer(
                r'const (?P<name>[A-Z_]+)_SOURCE_SLUG = "(?P<slug>[^"]+)";',
                worker_source,
            )
        }
        worker_chunk_counts = {}
        for match in re.finditer(
            r"const (?P<name>[A-Z_]+)_CHUNK_COUNT = (?P<count>\d+);",
            worker_source,
        ):
            source_slug = worker_chunk_source_slugs[match.group("name")]
            worker_chunk_counts[source_slug] = int(match.group("count"))
        expected_chunk_counts = {
            **RECONCILABLE_CHUNK_COUNTS,
            "mostly-danish": 30,
        }
        self.assertEqual(expected_chunk_counts, worker_chunk_counts)

    def test_seed_materials_use_localized_material_tokens(self) -> None:
        seed_materials = {
            material.strip().lower()
            for listings in SEED_LISTINGS.values()
            for listing in listings
            for material in listing["materials"].split(",")
            if material.strip()
        }

        self.assertTrue(seed_materials)
        self.assertEqual(set(), seed_materials - set(MATERIAL_LABELS))

    def test_default_feed_demotes_mostly_danish_bulk_ingest(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                mostly_danish = db.execute(
                    "SELECT id FROM shops WHERE slug = 'mostly-danish'"
                ).fetchone()
                self.assertIsNotNone(mostly_danish)
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era,
                        materials, dimensions_text, width, depth, height, condition_text,
                        location_text, source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, 'https://mostlydanish.com/products/new-chair', 'mostly-danish:new-chair',
                        'Mostly Danish New Chair', 'mostly danish new chair', '$950', 950, 'CAD',
                        'https://example.com/mostly.jpg', '[]', 'available', 'regional_quote',
                        1, 'Regional source', '2026-05-24T09:00:00+00:00',
                        '2026-05-24T09:00:00+00:00', '2026-05-24T09:00:00+00:00',
                        'lounge chairs', '', '', '', '', 'teak', '', NULL, NULL, NULL, 'Good',
                        'Ingleside, ON', 'Mostly Danish new chair', 'test', 1.0,
                        '', 1, 0, '', '', ''
                    )
                    """,
                    (mostly_danish["id"],),
                )
                db.commit()

                curated_rows = query_listings(
                    db, {"sort": "curated", "availability": "available"}, include_inactive=False
                )
                newest_rows = query_listings(
                    db, {"sort": "newest", "availability": "available"}, include_inactive=False
                )

                self.assertEqual(curated_rows[0]["source_listing_key"], "sample-key")
                self.assertEqual(newest_rows[0]["source_listing_key"], "mostly-danish:new-chair")
            finally:
                db.close()

    def test_curated_feed_keeps_mostly_danish_dining_chairs_below_regional_sources(
        self,
    ) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                mostly_danish = db.execute(
                    "SELECT id FROM shops WHERE slug = 'mostly-danish'"
                ).fetchone()
                green_wall = db.execute(
                    "SELECT id FROM shops WHERE slug = 'green-wall-vintage'"
                ).fetchone()
                self.assertIsNotNone(mostly_danish)
                self.assertIsNotNone(green_wall)
                db.executemany(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era,
                        materials, dimensions_text, width, depth, height, condition_text,
                        location_text, source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, ?, ?, ?, ?, '$950', 950, 'CAD', 'https://example.com/image.jpg',
                        '[]', 'available', 'regional_quote', 1, 'Regional source',
                        '2026-05-24T09:00:00+00:00', '2026-05-24T09:00:00+00:00',
                        ?, ?, '', '', '', '', 'teak', '', NULL, NULL, NULL, 'Good',
                        ?, 'Regional listing', 'test', 1.0, '', 1, 0, '', '', ''
                    )
                    """,
                    (
                        (
                            mostly_danish["id"],
                            "https://mostlydanish.com/products/new-dining-chair",
                            "mostly-danish:new-dining-chair",
                            "Mostly Danish New Dining Chair",
                            "mostly danish new dining chair",
                            "2026-05-24T09:00:00+00:00",
                            "dining chairs",
                            "Ingleside, ON",
                        ),
                        (
                            green_wall["id"],
                            "https://www.greenwallvintage.ca/products/green-wall-desk",
                            "green-wall:new-desk",
                            "Green Wall New Desk",
                            "green wall new desk",
                            "2026-05-23T09:00:00+00:00",
                            "desks",
                            "Ottawa, ON",
                        ),
                    ),
                )
                db.commit()

                curated_keys = [
                    row["source_listing_key"]
                    for row in query_listings(
                        db,
                        {"sort": "curated", "availability": "available"},
                        include_inactive=False,
                    )
                ]
                newest_keys = [
                    row["source_listing_key"]
                    for row in query_listings(
                        db,
                        {"sort": "newest", "availability": "available"},
                        include_inactive=False,
                    )
                ]

                self.assertLess(
                    curated_keys.index("green-wall:new-desk"),
                    curated_keys.index("mostly-danish:new-dining-chair"),
                )
                self.assertEqual(newest_keys[0], "mostly-danish:new-dining-chair")
            finally:
                db.close()

    def test_showroom_detail_uses_source_page_label(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                shop = db.execute(
                    "SELECT id FROM shops WHERE slug = 'showroom-montreal'"
                ).fetchone()
                db.execute(
                    """
                    INSERT INTO listings (
                        source_shop_id, source_listing_url, source_listing_key, title,
                        normalized_title, price_raw, price_value, currency, primary_image_url,
                        additional_image_urls, availability_status, shipping_scope,
                        ships_to_montreal, shipping_note, last_seen_at, last_checked_at,
                        first_seen_at, category, subcategory, designer, maker, era,
                        materials, dimensions_text, condition_text, location_text,
                        source_description, ingest_source_type, parse_confidence,
                        dedupe_group_id, is_active, is_featured, manual_notes,
                        availability_override, category_override
                    ) VALUES (
                        ?, 'https://www.showroommtl.com/nouveaute', 'showroom:dataItem-test',
                        'Showroom Chair', 'showroom chair', '$250', 250, 'CAD',
                        'https://example.com/image.jpg', '[]', 'available', 'local_quote',
                        1, 'Local source', '2026-05-06T00:00:00+00:00',
                        '2026-05-06T00:00:00+00:00', '2026-05-06T00:00:00+00:00',
                        'dining chairs', '', '', '', '', 'teak', '', 'Restored',
                        'Montreal, QC', 'Sample description', 'test', 1.0,
                        '', 1, 0, '', '', ''
                    )
                    """,
                    (shop["id"],),
                )
                db.commit()
                listing_id = db.execute(
                    "SELECT id FROM listings WHERE source_listing_key = 'showroom:dataItem-test'"
                ).fetchone()["id"]
            finally:
                db.close()

        response = self.client.get(f"/listing/{public_item_number(listing_id)}")
        self.assertIn("View source page", response.text)
        self.assertNotIn("View original listing", response.text)

    def test_numeric_listing_url_redirects_to_item_number(self) -> None:
        response = self.client.get(f"/listing/{self.listing_id}")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.headers["Location"].endswith(f"/listing/{public_item_number(self.listing_id)}")
        )

    def test_item_number_parser_accepts_canonical_and_legacy_values(self) -> None:
        self.assertEqual(listing_id_from_item_number("MCM-001912"), 1912)
        self.assertEqual(listing_id_from_item_number("1912"), 1912)
        self.assertIsNone(listing_id_from_item_number("not-an-item"))

    def test_removed_listing_detail_returns_404(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                    UPDATE listings
                    SET is_active = 0, availability_status = 'removed'
                    WHERE id = ?
                    """,
                    (self.listing_id,),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get(f"/listing/{public_item_number(self.listing_id)}")
        self.assertEqual(response.status_code, 404)

    def test_extractors_prefer_french_source_patterns(self) -> None:
        description = (
            "Chaises en teck '60s Arne Hovmand-Olsen pour Onsild Møbelfabrik, "
            "Denmark restaurées 3500 $ / 6"
        )
        self.assertEqual(
            _extract_designer_and_maker("Chaises en teck", description),
            ("Arne Hovmand-Olsen", "Onsild Møbelfabrik"),
        )
        self.assertEqual(_extract_materials(description), "teak")
        self.assertEqual(_extract_condition(description), "Restored")

    def test_extractors_keep_english_by_title_out_of_source_notes(self) -> None:
        description = (
            "Designed by Alessandro Gnocchi, Tiki Parete is based on an "
            "op-art triangular shape. View our store policies for more "
            "information prior to checkout."
        )
        self.assertEqual(
            _extract_designer_and_maker("Tiki Parete by Alessandro Gnocchi", description),
            ("Alessandro Gnocchi", ""),
        )

    def test_extractors_parse_english_by_for_title(self) -> None:
        self.assertEqual(
            _extract_designer_and_maker(
                "Anfibio Folding Sofa Bed by Alessandro Becchi for Giovannetti",
                "Italian convertible sofa bed.",
            ),
            ("Alessandro Becchi", "Giovannetti"),
        )

    def test_extractors_reject_contact_delivery_fragments_as_maker(self) -> None:
        self.assertEqual(
            _extract_designer_and_maker(
                "Dining Chairs",
                "Ottawa. Contactez-nous les détails - des frais s’appliques",
            ),
            ("", ""),
        )

    def test_morceau_source_only_uses_vintage_collection(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        self.assertEqual(source.listing_urls, ("https://www.morceau.ca/collections/vintage",))

    def test_showroom_gallery_items_use_lightbox_url(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_item = {
            "id": "dataItem-test",
            "uri": "fc24cc_test~mv2.jpg",
            "description": "Chaises en teck '60s\nArne Hovmand-Olsen\n3500 $ / 6",
        }
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=[gallery_item]),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(
            listings[0]["source_listing_url"],
            "https://www.showroommtl.com/nouveaute?lightbox=dataItem-test",
        )

    def test_shopify_collection_product_uses_variant_availability(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        listing = _parse_shopify_collection_product(
            source,
            {
                "title": "Large teak mirror",
                "handle": "large-teak-mirror",
                "body_html": (
                    "<p>Large teak frame, 1960s.</p>"
                    "<p><span>MATERIALS</span><br>Teak and mirror</p>"
                    '<p><span>DIMENSIONS</span><br>31"W x 42"H</p>'
                ),
                "variants": [{"available": True, "price": "500.00"}],
                "images": [{"src": "https://cdn.shopify.com/image.jpg"}],
            },
        )

        self.assertEqual(
            listing["source_listing_url"],
            "https://www.morceau.ca/products/large-teak-mirror",
        )
        self.assertEqual(listing["availability_status"], "available")
        self.assertEqual(listing["price_value"], 500)
        self.assertEqual(listing["materials"], "Teak and mirror")
        self.assertEqual(listing["dimensions_text"], '31"W x 42"H')

    def test_shopify_collection_entry_can_skip_sold_out_products(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "le-centerpiece")
        products = [
            {
                "title": "Available Chair",
                "handle": "available-chair",
                "body_html": "<p>Vintage chair.</p>",
                "variants": [{"available": True, "price": "500.00"}],
            },
            {
                "title": "Sold Chair",
                "handle": "sold-chair",
                "body_html": "<p>Vintage chair.</p>",
                "variants": [{"available": False, "price": "400.00"}],
            },
        ]
        with patch("mcm.sources._fetch_shopify_collection_products", return_value=products):
            listings = _fetch_shopify_collection_entry(
                source,
                "https://lecenterpiece.com/collections/chairs",
                include_sold_out=False,
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["title"], "Available Chair")
        self.assertEqual(listings[0]["availability_status"], "available")

    def test_cargo_gallery_page_parses_yardsale_listing(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "yardsale-vintage")
        listing = _parse_cargo_page(
            source,
            {
                "id": "T1320580650",
                "title": "Jean Gillon Copa Sofa in Jacaranda Rosewood - 3800$",
                "purl": "jean-gillon-copa-sofa-3800",
                "content": (
                    "<p>Jean Gillon two seater sofa in Jacaranda Rosewood.</p>"
                    "<p>Dimensions: 58”W x 34”D x 32”H</p>"
                ),
                "thumbnail": {
                    "hash": "H2812705775408123180166743959247",
                    "name": "sofa.jpeg",
                },
            },
        )

        self.assertEqual(listing["source_listing_key"], "yardsale-vintage:T1320580650")
        self.assertEqual(listing["price_value"], 3800)
        self.assertEqual(listing["category"], "sofas")
        self.assertTrue(listing["primary_image_url"].startswith("https://freight.cargo.site/"))

    def test_square_product_page_parses_chez_lamothe_metadata(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe")
        listing = _parse_square_product_page(
            source,
            "https://www.chezlamothe.com/product/buffet-en-teck/2950",
            """
            <html>
              <head>
                <meta property="og:title"
                      content="Buffet en teck par Johannes Andersen | Chez Lamothe">
                <meta property="og:description"
                      content="Buffet en teck, Danemark circa 60. 72&#34;W x 18&#34;D x 31&#34;H. Livraison possible à Montréal.">
                <meta property="og:image"
                      content="https://131647755.cdn6.editmysite.com/uploads/buffet.jpeg">
              </head>
            </html>
            """,
        )

        self.assertEqual(listing["title"], "Buffet en teck par Johannes Andersen")
        self.assertEqual(listing["price_value"], None)
        self.assertEqual(listing["availability_status"], "available")
        self.assertEqual(listing["category"], "sideboards / credenzas")
        self.assertEqual(listing["materials"], "teak")

    def test_square_product_page_marks_chez_lamothe_sold_out_markers(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe")
        listing = _parse_square_product_page(
            source,
            "https://www.chezlamothe.com/product/meuble-audio/123",
            """
            <html>
              <head>
                <meta property="og:title" content="Meuble audio extensible en teck">
                <meta property="og:description" content="Rupture de stock">
                <meta property="og:image"
                      content="https://131647755.cdn6.editmysite.com/uploads/meuble.jpeg">
              </head>
              <body>Article non disponible</body>
            </html>
            """,
        )

        self.assertEqual(listing["availability_status"], "sold_out")
        self.assertTrue(_square_product_is_sold_out("En rupture de stock", ""))

    def test_square_storefront_product_parses_chez_lamothe_price_and_stock(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe")
        listing = _parse_square_storefront_product(
            source,
            {
                "id": "QAGXILITRN353YX2KW4PAOLS",
                "site_product_id": "QAGXILITRN353YX2KW4PAOLS",
                "name": "Système stéréo Clairtone en bois de rose modèle Project G2 T10",
                "short_description": "<p>Console en bois de rose. 78.5&quot;L x 14.75&quot;P x 27&quot;H</p>",
                "absolute_site_link": (
                    "https://www.chezlamothe.com/product/systeme-stereo/QAGXILITRN353YX2KW4PAOLS"
                ),
                "badges": {"out_of_stock": False},
                "inventory": {"all_variations_sold_out": False},
                "price": {"low": 18995, "low_subunits": 1899500},
                "images": {
                    "data": [
                        {
                            "absolute_urls": {
                                "1280": (
                                    "https://131647755.cdn6.editmysite.com/uploads/"
                                    "QAGXILITRN353YX2KW4PAOLS.jpeg?width=1280"
                                )
                            }
                        }
                    ]
                },
            },
        )

        self.assertEqual(listing["source_listing_key"], "chez-lamothe:QAGXILITRN353YX2KW4PAOLS")
        self.assertEqual(listing["price_value"], 18995)
        self.assertEqual(listing["price_raw"], "$18,995.00 CAD")
        self.assertEqual(listing["availability_status"], "available")
        self.assertIn("wood", listing["materials"])

    def test_squarespace_store_item_parses_habitat_listing(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "habitat-mobilier")
        listing = _parse_squarespace_store_item(
            source,
            {
                "id": "habitat-test",
                "title": "Buffet en teck",
                "fullUrl": "/boutique/p/buffet-teck",
                "excerpt": (
                    "<p>Punch Design. Canada. Années 60.</p>"
                    "<p>Entièrement en teck. Largeur : 72” Profondeur : 18”</p>"
                ),
                "assetUrl": "https://images.squarespace-cdn.com/buffet.jpg",
                "items": [
                    {"assetUrl": "https://images.squarespace-cdn.com/buffet-gallery.jpg"},
                    {"assetUrl": "https://images.squarespace-cdn.com/buffet-detail.jpg"},
                ],
                "variants": [
                    {
                        "qtyInStock": 1,
                        "priceMoney": {"currency": "CAD", "value": "1675.00"},
                    }
                ],
            },
        )

        self.assertEqual(listing["source_listing_key"], "habitat-mobilier:habitat-test")
        self.assertEqual(
            listing["source_listing_url"], "https://habitatmobilier.com/boutique/p/buffet-teck"
        )
        self.assertEqual(listing["price_value"], 1675)
        self.assertEqual(listing["availability_status"], "available")
        self.assertEqual(listing["materials"], "teak")
        self.assertEqual(
            listing["primary_image_url"], "https://images.squarespace-cdn.com/buffet-gallery.jpg"
        )
        self.assertEqual(
            listing["additional_image_urls"],
            [
                "https://images.squarespace-cdn.com/buffet-detail.jpg",
                "https://images.squarespace-cdn.com/buffet.jpg",
            ],
        )

    def test_squarespace_store_item_prefers_gallery_images_over_placeholder_asset(
        self,
    ) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "habitat-mobilier")
        listing = _parse_squarespace_store_item(
            source,
            {
                "id": "habitat-bed",
                "title": "Lit queen en teck",
                "fullUrl": "/boutique/p/lit-queen-en-teck-annees-70-mobican",
                "excerpt": "<p>Lit en teck Mobican. Années 70.</p>",
                "assetUrl": (
                    "https://static1.squarespace.com/static/5dc59aa470fe636e786603db/"
                    "5dc59b223056b3048c0c3116/6a174d412fb5d01bb9ef1dcc/1779912256893/"
                ),
                "items": [
                    {
                        "assetUrl": (
                            "https://images.squarespace-cdn.com/content/v1/"
                            "5dc59aa470fe636e786603db/e330ce50-084c-4849-b7b7-bf24e1f95ee7/"
                            "lit_queen_teck_mobican.jpg"
                        )
                    }
                ],
                "variants": [
                    {
                        "qtyInStock": 1,
                        "priceMoney": {"currency": "CAD", "value": "895.00"},
                    }
                ],
            },
        )

        self.assertEqual(
            listing["primary_image_url"],
            (
                "https://images.squarespace-cdn.com/content/v1/"
                "5dc59aa470fe636e786603db/e330ce50-084c-4849-b7b7-bf24e1f95ee7/"
                "lit_queen_teck_mobican.jpg"
            ),
        )

    def test_squarespace_store_item_skips_out_of_stock_habitat_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "habitat-mobilier")
        with self.assertRaises(ValueError):
            _parse_squarespace_store_item(
                source,
                {
                    "id": "habitat-sold",
                    "title": "Fauteuil en teck",
                    "fullUrl": "/boutique/p/fauteuil-teck",
                    "excerpt": "<p>Fauteuil en teck.</p>",
                    "assetUrl": "https://images.squarespace-cdn.com/fauteuil.jpg",
                    "variants": [{"qtyInStock": 0, "priceMoney": {"value": "695.00"}}],
                },
            )

    def test_shopify_collection_product_skips_gift_cards(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        with self.assertRaises(ValueError):
            _parse_shopify_collection_product(
                source,
                {
                    "title": "Gift Card",
                    "handle": "gift-card",
                    "variants": [{"available": True, "price": "100.00"}],
                },
            )

    def test_shopify_collection_product_skips_current_production(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        with self.assertRaises(ValueError):
            _parse_shopify_collection_product(
                source,
                {
                    "title": "Tiki Terra by Alessandro Gnocchi",
                    "handle": "tiki-terra-by-alessandro-gnocchi",
                    "body_html": "<p>Made in Italy, current production, on order.</p>",
                    "variants": [{"available": True, "price": "525.00"}],
                },
            )

    def test_shopify_collection_products_walk_pages_until_empty(self) -> None:
        payloads = [
            json.dumps({"products": [{"handle": "one"}]}),
            json.dumps({"products": [{"handle": "two"}]}),
            json.dumps({"products": []}),
        ]
        with patch("mcm.sources._fetch_html", side_effect=payloads):
            products = _fetch_shopify_collection_products(
                "https://www.morceau.ca/collections/furniture"
            )

        self.assertEqual([product["handle"] for product in products], ["one", "two"])

    def test_showroom_gallery_skips_generated_dataitem_titles(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {"id": "dataItem-header1", "uri": "fc24cc_header1~mv2.jpg", "title": ""},
            {"id": "dataItem-header2", "uri": "fc24cc_header2~mv2.jpg", "title": ""},
            {
                "id": "dataItem-placeholder",
                "uri": "fc24cc_placeholder~mv2.jpg",
                "description": "Contactez nous pour les détails",
            },
            {
                "id": "dataItem-real",
                "uri": "fc24cc_real~mv2.jpg",
                "description": "Chaises en teck '60s\n1200 $ / 4",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(
            listings[0]["source_listing_key"],
            _showroom_source_listing_key(
                "Chaises en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_real~mv2.jpg",
                "Chaises en teck '60s 1200 $ / 4",
            ),
        )

    def test_showroom_french_dimensions_and_era_are_extracted(self) -> None:
        text = (
            "Fauteuils en teck '60s Arne Hovmand Olsen pour P Mikkelsen, Denmark "
            "restaurés, nouveau recouvrement 26''L x 30''P x 29.5''H assise 15'' H "
            "3250 $ / paire"
        )

        self.assertEqual(_extract_era(text), "1960s")
        self.assertEqual(_extract_dimensions(text), "26''L x 30''P x 29.5''H")

    def test_habitat_french_labeled_dimensions_and_era_are_extracted(self) -> None:
        text = (
            "Merton Gershun pour American of Martinsville. États-Unis. Années 60. "
            "En paire. En noyer avec insertions et poignées en aluminium. "
            "Excellente condition. Complètement restaurées avec nouveau fini durable. "
            "Largeur : 20” Profondeur : 16” Hauteur : 24” - Livraison possible partout au Québec."
        )

        self.assertEqual(_extract_era(text), "1960s")
        self.assertEqual(_extract_dimensions(text), "20”L x 16”P x 24”H")

    def test_habitat_french_range_dimensions_are_extracted(self) -> None:
        text = (
            "REFF. Canada. Années 60. Entièrement en bois de rose. "
            "Largeur : 125” Profondeur : 16” Hauteur : 88” à 100” (rails)"
        )

        self.assertEqual(_extract_dimensions(text), "125”L x 16”P x 88”/100”H")

    def test_habitat_prefixed_multi_piece_dimensions_are_extracted(self) -> None:
        text = (
            "Fauteuil: Largeur : 32” Profondeur : 35” Hauteur (assise) : 17” "
            "Hauteur totale : 38” Ottoman: Largeur : 21” Profondeur : 18” Hauteur : 14”"
        )

        self.assertEqual(
            _extract_dimensions(text),
            "Fauteuil: 32”L x 35”P x 38”H; Ottoman: 21”L x 18”P x 14”H",
        )

    def test_chez_lamothe_diameter_dimensions_are_extracted(self) -> None:
        text = (
            "Lampe champignon Space Age en verre blanc et orangé attribuées à Pukeberg, "
            'Suède circa 60 - en parfaite condition d\'origine 8,5"Ø x 9"H '
            "Expédition possible au Canada"
        )

        self.assertEqual(_extract_dimensions(text), '8,5"Ø x 9"H')

    def test_chez_lamothe_diameter_depth_dimensions_are_extracted(self) -> None:
        text = (
            "Petit miroir mid century en acier et laiton, circa 60 - excellente condition "
            'd\'origine 12"Ø x 2,75"P Expédition possible au Canada'
        )

        self.assertEqual(_extract_dimensions(text), '12"Ø x 2,75"P')

    def test_parenthetical_dimension_notes_are_removed(self) -> None:
        text = (
            "Ceramic vase by Scheurich. Made in West Germany, 1980’s. "
            '5,5"D(with handle) x 11”H US/CAD shipping available at checkout.'
        )

        self.assertEqual(_extract_dimensions(text), '5,5"D x 11”H')

    def test_mostly_danish_centimetre_dimensions_are_extracted(self) -> None:
        text = (
            "ITEM# 4024267 MAHOGANY SOFA SET Sofa: Length 190 cm. "
            "Depth 80 cm. Height 77 cm excl. pad. Seat height 45 cm."
        )

        self.assertEqual(_extract_dimensions(text), "190cmL x 80cmD x 77cmH")

    def test_mostly_danish_shorthand_dimensions_are_extracted(self) -> None:
        text = 'Rosewood secretary designed by Ib Kofod-Larsen. H. 56.5" x W. 39.3" x D. 18.25"'

        self.assertEqual(_extract_dimensions(text), '56.5"H x 39.3"W x 18.25"D')

    def test_single_axis_dimensions_are_extracted(self) -> None:
        text = "Vintage EM77 stainless steel vacuum jug. Made in Denmark, 1970’s. 12”H"

        self.assertEqual(_extract_dimensions(text), "12”H")

    def test_seat_and_back_height_are_not_single_axis_dimensions(self) -> None:
        text = (
            "Poul Hundevad pour Vamdrup Stolefabrik. H (dossier) : 31” "
            "H (assise) : 18” Largeur : 19”"
        )

        self.assertEqual(_extract_dimensions(text), "")

    def test_curly_apostrophe_decade_is_extracted(self) -> None:
        text = (
            "Teak wine/ice bucket by Jens Quistgaard for Dansk. "
            'Made in Denmark, 1950’s. Restored. 7,5"D x 15”H'
        )

        self.assertEqual(_extract_era(text), "1950s")

    def test_showroom_gallery_skips_promotional_store_hours_cards(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {
                "id": "dataItem-promo",
                "uri": "fc24cc_promo~mv2.jpg",
                "description": "Joyeuses Pâques!\nOuvert samedi 19 avril 12h à 17h\nFermé dimanche 20 avril",
            },
            {
                "id": "dataItem-real",
                "uri": "fc24cc_real~mv2.jpg",
                "description": "Fauteuil en teck '60s\n1850 $",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(
            listings[0]["source_listing_key"],
            _showroom_source_listing_key(
                "Fauteuil en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_real~mv2.jpg",
                "Fauteuil en teck '60s 1850 $",
            ),
        )

    def test_showroom_gallery_marks_sold_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {
                "id": "dataItem-sold",
                "uri": "fc24cc_sold~mv2.jpg",
                "description": "Buffet en teck '60s\nVendu",
            },
            {
                "id": "dataItem-real",
                "uri": "fc24cc_real~mv2.jpg",
                "description": "Fauteuil en teck '60s\n1850 $",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(len(listings), 2)
        self.assertEqual(
            listings[0]["source_listing_key"],
            _showroom_source_listing_key(
                "Buffet en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_sold~mv2.jpg",
                "Buffet en teck '60s Vendu",
            ),
        )
        self.assertEqual(listings[0]["availability_status"], "sold_out")
        self.assertEqual(
            listings[1]["source_listing_key"],
            _showroom_source_listing_key(
                "Fauteuil en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_real~mv2.jpg",
                "Fauteuil en teck '60s 1850 $",
            ),
        )
        self.assertEqual(listings[1]["availability_status"], "available")

    def test_showroom_gallery_marks_title_overlay_sold_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {
                "id": "dataItem-sold",
                "uri": "fc24cc_sold~mv2.jpg",
                "title": "VENDU SOLD",
                "description": "TINGSTROMS, série Casino\nSWEDEN",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/tables-dappoints",
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["title"], "TINGSTROMS, série Casino SWEDEN")
        self.assertEqual(listings[0]["availability_status"], "sold_out")

    def test_showroom_key_uses_description_before_image(self) -> None:
        title = "Lampes, suspensions en acier '60s Jo Hammerborg pour Fog & Morup, Denmark"
        description = (
            "Lampes, suspensions en acier '60s Jo Hammerborg pour Fog & Morup, Denmark "
            "modèle Corona (Cône) 9.5'' D x 18''H 1500 $ / l'ensemble"
        )

        first_key = _showroom_source_listing_key(
            title,
            "https://static.wixstatic.com/media/fc24cc_first~mv2.jpg",
            description,
        )
        second_key = _showroom_source_listing_key(
            title,
            "https://static.wixstatic.com/media/fc24cc_second~mv2.jpg",
            description.lower(),
        )

        self.assertEqual(first_key, second_key)

    def test_showroom_full_refresh_keeps_all_unique_gallery_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        showroom_listings = [
            {
                "source_listing_key": f"showroom:dataItem-{index}",
                "primary_image_url": f"https://static.wixstatic.com/media/item-{index}.jpg",
            }
            for index in range(241)
        ]

        with patch("mcm.sources._fetch_showroom_entry", return_value=showroom_listings):
            listings = _fetch_showroom(source)

        self.assertEqual(len(listings), 241)

    def test_showroom_full_refresh_merges_same_item_from_nouveaute_and_category(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        duplicate_from_nouveaute = {
            "source_listing_url": "https://www.showroommtl.com/nouveaute?lightbox=dataItem-new",
            "source_listing_key": "showroom:dataItem-new",
            "title": "Commode en teck '60s REFF, Canada",
            "primary_image_url": "https://static.wixstatic.com/media/fc24cc_duplicate.jpg",
            "source_description": "Commode en teck '60s REFF, Canada restaurée 72'' L x 18.75'' P x 27'' H 1350 $",
        }
        duplicate_from_category = {
            **duplicate_from_nouveaute,
            "source_listing_url": "https://www.showroommtl.com/lits-commodes?lightbox=dataItem-category",
            "source_listing_key": "showroom:dataItem-category",
        }

        def fake_fetch_entry(_source: object, entry_url: str) -> list[dict[str, Any]]:
            if entry_url.endswith("/nouveaute"):
                return [duplicate_from_nouveaute]
            if entry_url.endswith("/lits-commodes"):
                return [duplicate_from_category]
            return []

        with patch("mcm.sources._fetch_showroom_entry", side_effect=fake_fetch_entry):
            listings = _fetch_showroom(source)

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["source_listing_key"], "showroom:dataItem-category")
        self.assertIn("/lits-commodes?", listings[0]["source_listing_url"])

    def test_fetch_html_percent_encodes_non_ascii_url_parts(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        captured_url = ""

        def fake_urlopen(request, timeout):  # noqa: ANN001, ARG001
            nonlocal captured_url
            captured_url = request.full_url
            captured_url.encode("ascii")
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.assertEqual(_fetch_html("https://example.com/assets?title=Knoll®"), "ok")

        self.assertEqual(captured_url, "https://example.com/assets?title=Knoll%C2%AE")

    def test_showroom_siteassets_url_preserves_registry_query_parameter(self) -> None:
        html = """
        <html>
          <script>window.firstPageId = 'abc';</script>
          <link id="features_abc" href="https://siteassets.parastorage.com/pages/pages/thunderbolt?x=1&registryLibrariesTopology=%5B%5D">
        </html>
        """

        self.assertEqual(
            _extract_showroom_siteassets_url(html),
            "https://siteassets.parastorage.com/pages/pages/thunderbolt?x=1&registryLibrariesTopology=%5B%5D",
        )


if __name__ == "__main__":
    unittest.main()
