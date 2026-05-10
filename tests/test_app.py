from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcm.app import create_app
from mcm.db import get_db
from mcm.i18n import MATERIAL_LABELS
from mcm.locales import TRANSLATIONS_EN, TRANSLATIONS_FR
from mcm.refresh import listing_id_from_item_number, public_item_number, refresh_all_sources
from mcm.repository import sanitize_availability
from mcm.seed_data import SEED_LISTINGS
from mcm.sources import (
    SOURCE_DEFINITIONS,
    _extract_condition,
    _extract_designer_and_maker,
    _extract_dimensions,
    _extract_era,
    _extract_materials,
    _extract_showroom_gallery_listings,
    _fetch_shopify_collection_products,
    _parse_shopify_collection_product,
)


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

    def test_locale_files_have_matching_keys(self) -> None:
        self.assertEqual(set(TRANSLATIONS_EN), set(TRANSLATIONS_FR))

    def test_invalid_price_filter_does_not_error(self) -> None:
        response = self.client.get("/?price_min=abc")
        self.assertEqual(response.status_code, 200)

    def test_sold_out_filter_can_show_active_sold_listings(self) -> None:
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
        self.assertIn("Availability: Sold out", response.text)
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
        self.assertIn('id="favourite-listing-count"', response.text)
        self.assertIn("(1)", response.text)

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
        self.assertIn("Since May 6, 2026", response.text)
        self.assertNotIn("2026-05-07", response.text)
        self.assertNotIn("Checked today", response.text)

    def test_listing_count_uses_singular_label(self) -> None:
        response = self.client.get("/")
        self.assertIn("1 listing", response.text)
        self.assertNotIn("1 listings", response.text)

    def test_listing_grid_omits_redundant_location(self) -> None:
        response = self.client.get("/")
        self.assertIn("lounge chairs", response.text)
        self.assertNotIn("Montreal, QC · lounge chairs", response.text)

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

    def test_morceau_source_only_uses_vintage_collection(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        self.assertEqual(source.listing_urls, ("https://www.morceau.ca/collections/vintage",))

    def test_showroom_gallery_items_use_source_page_url(self) -> None:
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

        self.assertEqual(listings[0]["source_listing_url"], "https://www.showroommtl.com/nouveaute")

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
        self.assertEqual(listings[0]["source_listing_key"], "showroom:dataItem-real")

    def test_showroom_french_dimensions_and_era_are_extracted(self) -> None:
        text = (
            "Fauteuils en teck '60s Arne Hovmand Olsen pour P Mikkelsen, Denmark "
            "restaurés, nouveau recouvrement 26''L x 30''P x 29.5''H assise 15'' H "
            "3250 $ / paire"
        )

        self.assertEqual(_extract_era(text), "1960s")
        self.assertEqual(_extract_dimensions(text), "26''L x 30''P x 29.5''H")

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
        self.assertEqual(listings[0]["source_listing_key"], "showroom:dataItem-real")


if __name__ == "__main__":
    unittest.main()
