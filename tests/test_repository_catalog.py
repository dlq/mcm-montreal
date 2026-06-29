from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class RepositoryCatalogTests(AppTestCase):
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

    def test_repository_helper_edge_cases_are_explicit(self) -> None:
        self.assertEqual(
            favourite_counts(),
            {"listings": 0, "shops": 0, "searches": 0, "total": 0},
        )
        with self.app.test_request_context("/"):
            self.assertEqual(favourite_listing_session_list(), [])
            self.assertEqual(favourite_shop_session_list(), [])
            toggle_favourite_listing(self.app, self.listing_id)
            toggle_favourite_shop(self.app, 1)
            self.assertEqual(favourite_listing_session_list(), [self.listing_id])
            self.assertEqual(favourite_shop_session_list(), [1])
            toggle_favourite_listing(self.app, self.listing_id)
            toggle_favourite_shop(self.app, 1)
            self.assertEqual(favourite_listing_session_list(), [])
            self.assertEqual(favourite_shop_session_list(), [])
            toggle_favourite_listing(self.app, self.listing_id)
            toggle_favourite_shop(self.app, 1)
            self.assertEqual(
                favourite_counts(),
                {"listings": 1, "shops": 1, "searches": 0, "total": 2},
            )

        with self.app.app_context():
            db = get_db(self.app)
            try:
                self.assertIsNone(get_listing(db, 999999))
                self.assertIsNone(get_shop(db, 999999))
                self.assertIsNone(get_shop_by_slug(db, "missing-shop"))
                with self.assertRaisesRegex(ValueError, "Unsupported filter field"):
                    list_filter_values(db, "not_a_filter")
                self.assertEqual(search_query_clause(db, "   "), ("", []))
                self.assertEqual(search_score_expression("!!!"), ("", []))
                self.assertEqual(list_saved_searches(db), [])
                save_search(db, "No owner", "q=teak")
                delete_saved_search(db, 999999)
                self.assertEqual(
                    count_listings(
                        db,
                        {"designer": "store policies", "availability": "available"},
                        include_inactive=False,
                    ),
                    0,
                )
                self.assertEqual(
                    query_listings(
                        db,
                        {"sort": "newest", "availability": "available"},
                        include_inactive=False,
                        limit=None,
                    )[0]["id"],
                    self.listing_id,
                )
                self.assertEqual(
                    count_listings(
                        db,
                        {
                            "location": "Montreal",
                            "ships_to_montreal": "1",
                            "price_min": "200",
                            "price_max": "300",
                            "availability": "available",
                        },
                        include_inactive=False,
                    ),
                    1,
                )
                update_listing_overrides(
                    db,
                    self.listing_id,
                    "case goods",
                    "reserved",
                    1,
                    "Reviewed for admin coverage.",
                )
                updated = db.execute(
                    """
                        SELECT category_override, availability_override, is_featured, manual_notes
                        FROM listings
                        WHERE id = ?
                        """,
                    (self.listing_id,),
                ).fetchone()
                self.assertIsNotNone(updated)
                assert updated is not None
                self.assertEqual(updated["category_override"], "case goods")
                self.assertEqual(updated["availability_override"], "reserved")
                self.assertEqual(updated["is_featured"], 1)
                self.assertEqual(updated["manual_notes"], "Reviewed for admin coverage.")

                db.execute(
                    """
                        INSERT INTO shops (
                            slug, name, website, city, province, country,
                            shipping_summary, source_type, active
                        ) VALUES (
                            'duplicate-shop', 'Duplicate Shop', 'https://example.com',
                            'Montreal', 'QC', 'Canada', 'Ships to Montreal', 'test', 1
                        )
                        """,
                )
                duplicate_shop_id = db.execute(
                    "SELECT id FROM shops WHERE slug = 'duplicate-shop'"
                ).fetchone()["id"]
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
                        ) SELECT
                            ?, 'https://example.com/duplicate', 'duplicate-key',
                            'Sample Chair', 'sample chair', price_raw, price_value, currency,
                            primary_image_url, additional_image_urls, availability_status,
                            shipping_scope, ships_to_montreal, shipping_note, last_seen_at,
                            last_checked_at, first_seen_at, category, subcategory, designer, maker,
                            era, materials, dimensions_text, width, depth, height, condition_text,
                            location_text, source_description, ingest_source_type, parse_confidence,
                            dedupe_group_id, 1, is_featured, manual_notes, availability_override,
                            category_override
                        FROM listings
                        WHERE id = ?
                        """,
                    (duplicate_shop_id, self.listing_id),
                )
                db.commit()
                duplicates = find_duplicate_candidates(db)
                self.assertEqual(duplicates[0]["left"]["title"], "Sample Chair")
                self.assertEqual(duplicates[0]["right"]["title"], "Sample Chair")

                db.execute(
                    """
                        UPDATE listings
                        SET location_text = ' Montreal, QC '
                        WHERE id = ?
                        """,
                    (self.listing_id,),
                )
                db.commit()
                self.assertEqual(list_location_filter_values(db), ["Montreal, QC"])
            finally:
                db.close()

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
