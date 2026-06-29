from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class RepositoryDesignTests(AppTestCase):
    def test_repository_design_edge_cases_are_explicit(self) -> None:
        self.assertEqual(clean_designer_filter_value(""), "")
        self.assertEqual(clean_designer_filter_value("Store Policies"), "")
        self.assertEqual(clean_designer_filter_value("1960s Danish designer"), "")
        self.assertEqual(clean_designer_filter_value("Montreal"), "")
        self.assertEqual(clean_designer_filter_value("Hans Wegner"), "Hans J. Wegner")
        self.assertEqual(designer_filter_query_values("shipping details"), [])
        self.assertIn("Hans J. Wegner", designer_filter_query_values("Hans Wegner"))

        with self.app.app_context():
            db = get_db(self.app)
            try:
                self.assertEqual(design_entity_filter_query_values(db, ""), [])
                with self.assertRaisesRegex(ValueError, "canonical_name is required"):
                    create_design_entity(db, canonical_name="")

                entity_id = create_design_entity(
                    db,
                    canonical_name="Fallback Creator",
                    entity_type="invalid",
                    aliases=["", "Fallback Alias"],
                    notes="  stripped notes  ",
                )
                entity = db.execute(
                    "SELECT entity_type, notes FROM design_entities WHERE id = ?",
                    (entity_id,),
                ).fetchone()
                self.assertIsNotNone(entity)
                assert entity is not None
                self.assertEqual(entity["entity_type"], "creator")
                self.assertEqual(entity["notes"], "stripped notes")

                add_listing_design_entity_evidence(
                    db,
                    listing_id=self.listing_id,
                    entity_id=entity_id,
                    evidence_role="invalid",
                    source_text="",
                )
                add_listing_design_entity_evidence(
                    db,
                    listing_id=self.listing_id,
                    entity_id=entity_id,
                    evidence_role="invalid",
                    source_text="Fallback Alias",
                )
                evidence = db.execute(
                    """
                        SELECT evidence_role
                        FROM listing_design_entity_evidence
                        WHERE entity_id = ?
                        """,
                    (entity_id,),
                ).fetchone()
                self.assertIsNotNone(evidence)
                assert evidence is not None
                self.assertEqual(evidence["evidence_role"], "creator")

                review_design_entity_candidate(
                    db,
                    source_text="",
                    source_role="designer",
                    review_status="approved",
                )
                review_design_entity_candidate(
                    db,
                    source_text="Reviewed Candidate",
                    source_role="invalid",
                    review_status="invalid",
                    notes="Skipped parser artifact.",
                )
                review = db.execute(
                    """
                        SELECT source_role, review_status, notes
                        FROM design_entity_candidate_reviews
                        WHERE normalized_source_text = 'reviewed candidate'
                        """,
                ).fetchone()
                self.assertIsNotNone(review)
                assert review is not None
                self.assertEqual(review["source_role"], "designer")
                self.assertEqual(review["review_status"], "rejected")
                self.assertEqual(review["notes"], "Skipped parser artifact.")

                self.assertEqual(list_design_entities(db, query="no such creator"), [])
                self.assertIn(
                    "Fallback Alias",
                    design_entity_filter_query_values(db, "Fallback Creator"),
                )
            finally:
                db.close()

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

    def test_admin_can_bulk_approve_design_entity_candidate(self) -> None:
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
                            ?, 'https://example.com/listing-two', 'sample-key-two', 'Second Sample Chair',
                            'second sample chair', '$300', 300, 'CAD', '', '[]',
                            'available', 'canada', 1, 'Ships to Montreal',
                            '2026-05-06T00:00:00+00:00', '2026-05-06T00:00:00+00:00',
                            '2026-05-06T00:00:00+00:00', 'lounge chairs', '', 'Test Designer',
                            '', '1960s', 'teak', '', NULL, NULL, NULL, 'Good', 'Montreal, QC',
                            'Sample description', 'test', 1.0, '', 1, 0, '', '', ''
                        )
                        """,
                    (shop["id"],),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.post(
            "/admin/design-entity-candidates",
            data={
                "action": "approve",
                "source_text": "Test Designer",
                "source_role": "designer",
                "canonical_name": "Test Designer Studio",
                "entity_type": "creator",
                "aliases": "T. Designer",
                "notes": "Reviewed from bulk candidate queue.",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Test Designer Studio", response.text)
        with self.app.app_context():
            db = get_db(self.app)
            try:
                evidence = db.execute(
                    """
                        SELECT de.canonical_name, ldee.source_text, ldee.evidence_role, COUNT(*) AS count
                        FROM listing_design_entity_evidence ldee
                        JOIN design_entities de ON de.id = ldee.entity_id
                        WHERE ldee.source_text = 'Test Designer'
                        GROUP BY de.canonical_name, ldee.source_text, ldee.evidence_role
                        """
                ).fetchone()
                aliases = db.execute(
                    """
                        SELECT alias
                        FROM design_entity_aliases
                        WHERE normalized_alias IN ('test designer', 't designer')
                        ORDER BY alias
                        """
                ).fetchall()
            finally:
                db.close()

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual("Test Designer Studio", evidence["canonical_name"])
        self.assertEqual("designer", evidence["evidence_role"])
        self.assertEqual(2, evidence["count"])
        self.assertEqual(["T. Designer", "Test Designer"], [row["alias"] for row in aliases])

    def test_admin_can_reject_design_entity_candidate(self) -> None:
        response = self.client.post(
            "/admin/design-entity-candidates",
            data={
                "action": "reject",
                "source_text": "Test Designer",
                "source_role": "designer",
                "notes": "Parser artifact, not a real creator.",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            db = get_db(self.app)
            try:
                candidates = list_design_entity_candidates(db)
                review = db.execute(
                    """
                        SELECT review_status, notes
                        FROM design_entity_candidate_reviews
                        WHERE normalized_source_text = 'test designer'
                          AND source_role = 'designer'
                        """
                ).fetchone()
            finally:
                db.close()

        self.assertNotIn("Test Designer", [candidate["source_text"] for candidate in candidates])
        self.assertIsNotNone(review)
        assert review is not None
        self.assertEqual("rejected", review["review_status"])
        self.assertEqual("Parser artifact, not a real creator.", review["notes"])

    def test_admin_design_entity_index_lists_and_searches_entities(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                entity_id = create_design_entity(
                    db,
                    canonical_name="Test Designer Studio",
                    entity_type="creator",
                    aliases=["Test Designer", "T. Designer"],
                    notes="Reviewed canonical record.",
                )
                db.execute(
                    """
                        INSERT INTO listing_design_entity_evidence (
                            listing_id, entity_id, evidence_role, source_text,
                            normalized_source_text, confidence, review_status,
                            created_at, updated_at
                        ) VALUES (?, ?, 'designer', 'Test Designer', 'test designer', 1.0,
                            'approved', '2026-06-17T00:00:00+00:00', '2026-06-17T00:00:00+00:00')
                        """,
                    (self.listing_id, entity_id),
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get("/admin/design-entities?q=t.%20designer")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Canonical design entities", response.text)
        self.assertIn("Test Designer Studio", response.text)
        self.assertIn("T. Designer", response.text)
        self.assertIn("1 listing", response.text)
