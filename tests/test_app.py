from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcm.app import create_app
from mcm.db import get_db
from mcm.refresh import public_item_number, refresh_all_sources
from mcm.sources import (
    _extract_condition,
    _extract_designer_and_maker,
    _extract_materials,
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
            f"/listing/{self.listing_id}",
            "/?lang=fr",
        ]:
            response = self.client.get(path, follow_redirects=True)
            self.assertEqual(response.status_code, 200, path)

    def test_invalid_price_filter_does_not_error(self) -> None:
        response = self.client.get("/?price_min=abc")
        self.assertEqual(response.status_code, 200)

    def test_favourite_toggle_returns_404_for_missing_listing(self) -> None:
        response = self.client.post("/favourites/listing/999999")
        self.assertEqual(response.status_code, 404)

    def test_favourite_toggles_work_for_valid_ids(self) -> None:
        listing_response = self.client.post(f"/favourites/listing/{self.listing_id}")
        shop_response = self.client.post("/favourites/shop/1")
        self.assertEqual(listing_response.status_code, 200)
        self.assertEqual(shop_response.status_code, 200)

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
        response = self.client.get(f"/listing/{self.listing_id}")
        self.assertIn(public_item_number(self.listing_id), response.text)

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


if __name__ == "__main__":
    unittest.main()
