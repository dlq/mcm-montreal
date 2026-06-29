from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class FavouriteTests(AppTestCase):
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

    def test_favourites_page_uses_localized_price_display(self) -> None:
        update_listing_price(self.app, self.listing_id, "3250 $ / paire", 3250)
        self.client.post(f"/favourites/listing/{self.listing_id}")

        response = self.client.get("/favourites?lang=en")

        self.assertIn("$3,250 CAD for pair", response.text)
        self.assertNotIn("3250 $ / paire", response.text)
