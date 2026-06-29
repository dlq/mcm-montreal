from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class RefreshTests(AppTestCase):
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

    def test_repository_refresh_helpers_record_jobs_and_events(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                job = start_refresh_job(
                    db,
                    1,
                    "morceau",
                    "2026-06-29T06:00:00+00:00",
                    chunk_index=2,
                    entry_url="https://example.com/page",
                )
                finish_refresh_job(
                    db,
                    job,
                    "2026-06-29T06:01:00+00:00",
                    status="success",
                    listings_found=4,
                    new_count=1,
                    reconciled_count=2,
                    hidden_count=3,
                    error_message="",
                )
                record_availability_event(
                    db,
                    self.listing_id,
                    1,
                    "sample-key",
                    "available",
                    "removed",
                    "2026-06-29T06:01:00+00:00",
                    "test",
                )
                record_price_event(
                    db,
                    self.listing_id,
                    1,
                    "sample-key",
                    "$250",
                    250,
                    "$200",
                    200,
                    "CAD",
                    "2026-06-29T06:01:00+00:00",
                    "test",
                )
                reassign_listing_events(db, self.listing_id, self.listing_id + 1000, "new-key")
                db.commit()

                chunk_jobs = latest_successful_chunk_jobs(
                    db,
                    "morceau",
                    3,
                    since="2026-06-29T00:00:00+00:00",
                )
                job_row = db.execute(
                    """
                        SELECT status, listings_found, new_count, reconciled_count,
                               hidden_count, finished_at
                        FROM refresh_jobs
                        WHERE source_slug = 'morceau'
                          AND chunk_index = 2
                        """
                ).fetchone()
                availability_event = db.execute(
                    """
                        SELECT listing_id, source_listing_key
                        FROM listing_availability_events
                        WHERE event_type = 'test'
                        """
                ).fetchone()
                price_event = db.execute(
                    """
                        SELECT listing_id, source_listing_key
                        FROM listing_price_events
                        WHERE event_type = 'test'
                        """
                ).fetchone()
            finally:
                db.close()

        self.assertEqual(job_row["status"], "success")
        self.assertEqual(job_row["listings_found"], 4)
        self.assertEqual(job_row["new_count"], 1)
        self.assertEqual(job_row["reconciled_count"], 2)
        self.assertEqual(job_row["hidden_count"], 3)
        self.assertEqual(job_row["finished_at"], "2026-06-29T06:01:00+00:00")
        self.assertEqual(len(chunk_jobs), 1)
        self.assertEqual(chunk_jobs[0]["chunk_index"], 2)
        self.assertEqual(availability_event["listing_id"], self.listing_id + 1000)
        self.assertEqual(availability_event["source_listing_key"], "new-key")
        self.assertEqual(price_event["listing_id"], self.listing_id + 1000)
        self.assertEqual(price_event["source_listing_key"], "new-key")

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
