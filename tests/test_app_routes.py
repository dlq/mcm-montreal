from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class AppRouteTests(AppTestCase):
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
        self.assertIn("<loc>https://montrealmcm.ca/about</loc>", sitemap_response.text)
        self.assertIn("<loc>https://montrealmcm.ca/shops/morceau</loc>", sitemap_response.text)
        self.assertIn(
            f"<loc>https://montrealmcm.ca/listing/{public_item_number(self.listing_id)}</loc>",
            sitemap_response.text,
        )
        self.assertNotIn("/admin", sitemap_response.text)
        self.assertNotIn("/favourites", sitemap_response.text)

    def test_security_txt_lists_contact_and_policy(self) -> None:
        response = self.client.get("/.well-known/security.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/plain; charset=utf-8")
        self.assertIn("Contact: mailto:darcy.quesnel@gmail.com", response.text)
        self.assertIn("Policy: https://montrealmcm.ca/privacy", response.text)
        self.assertIn("Canonical: https://montrealmcm.ca/.well-known/security.txt", response.text)

    def test_privacy_page_explains_current_analytics_and_cookies(self) -> None:
        response = self.client.get("/privacy")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Privacy", response.text)
        self.assertIn("anonymous favourites", response.text)
        self.assertIn("saved searches", response.text)
        self.assertIn("Cloudflare", response.text)
        self.assertIn("does not store raw IP addresses", response.text)

    def test_about_page_explains_the_project_and_is_discoverable(self) -> None:
        response = self.client.get("/about")

        self.assertEqual(response.status_code, 200)
        self.assertIn("About Montreal MCM", response.text)
        self.assertIn("Montreal-focused vintage/MCM furniture discovery project", response.text)
        self.assertIn("checks local and regional shops daily", response.text)
        self.assertIn(
            "Corrections, shop suggestions, duplicate listings, or feedback", response.text
        )
        self.assertIn('href="mailto:hello@montrealmcm.ca"', response.text)
        self.assertIn("hello@montrealmcm.ca", response.text)
        self.assertIn('href="https://montrealmcm.ca/about"', response.text)

        home_response = self.client.get("/")
        self.assertEqual(home_response.status_code, 200)
        self.assertIn('class="nav-link ', home_response.text)
        self.assertIn('href="/about">About</a>', home_response.text)
        self.assertIn("About", home_response.text)

    def test_about_page_renders_in_french(self) -> None:
        response = self.client.get("/about?lang=fr")

        self.assertEqual(response.status_code, 200)
        self.assertIn("À propos de Montreal MCM", response.text)
        self.assertIn("projet montréalais de découverte de mobilier vintage/MCM", response.text)
        self.assertIn("boutiques locales et régionales chaque jour", response.text)
        self.assertIn(
            "Corrections, suggestions de boutiques, doublons ou commentaires", response.text
        )
        self.assertIn('href="mailto:hello@montrealmcm.ca"', response.text)

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

    def test_app_pure_helpers_have_focused_modules(self) -> None:
        from mcm.analytics import analytics_page_type, analytics_path_key, analytics_since_date
        from mcm.saved_searches import saved_search_name, saved_search_query_string
        from mcm.seo import absolute_public_url, category_slug, listing_structured_data

        self.assertEqual(
            absolute_public_url("https://montrealmcm.ca/", "shops/morceau"),
            "https://montrealmcm.ca/shops/morceau",
        )
        self.assertEqual(category_slug("Sideboards / Credenzas"), "sideboards-credenzas")
        self.assertEqual(analytics_page_type("/listing/MCM-000001"), "listing")
        self.assertEqual(analytics_path_key("shops/morceau?lang=fr"), "/shops/morceau")
        self.assertEqual(
            saved_search_query_string({"q": "teak", "price_max": "1000", "shop": ""}),
            "q=teak&price_max=1000",
        )
        self.assertEqual(saved_search_name({"q": "teak", "price_max": "1000"}), "teak / 1000")
        self.assertEqual(
            saved_search_name({"availability": "sold_out"}),
            "sold out",
        )
        self.assertEqual(analytics_since_date("2026-06-18"), "2026-06-18")
        self.assertRegex(analytics_since_date("not-a-date", default_days=1), r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(analytics_since_date("", default_days=1), r"^\d{4}-\d{2}-\d{2}$")
        with self.app.test_request_context("/"):
            structured_listing = listing_structured_data(
                "https://montrealmcm.ca",
                {
                    "id": 1,
                    "title": "Sold Chair",
                    "source_description": "",
                    "primary_image_url": "",
                    "shop_name": "Morceau",
                    "category_override": "",
                    "category": "lounge chairs",
                    "source_listing_url": "https://example.com/chair",
                    "currency": "CAD",
                    "price_value": None,
                    "availability_override": "",
                    "availability_status": "sold_out",
                },
                {"name": "Morceau"},
            )
        self.assertEqual(
            structured_listing["offers"]["availability"], "https://schema.org/OutOfStock"
        )
        self.assertNotIn("price", structured_listing["offers"])

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
