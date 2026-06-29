from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class AnalyticsTests(AppTestCase):
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

    def test_analytics_summary_helpers_aggregate_recent_usage(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.executemany(
                    """
                        INSERT INTO analytics_page_views (
                            view_date, page_type, path_key, lang, views, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                    [
                        ("2026-06-18", "home", "/", "en", 3, "2026-06-18T12:00:00+00:00"),
                        (
                            "2026-06-18",
                            "listing",
                            "/listing/MCM-0001",
                            "en",
                            2,
                            "2026-06-18T12:00:00+00:00",
                        ),
                        (
                            "2026-06-19",
                            "shop",
                            "/shops/morceau",
                            "fr",
                            4,
                            "2026-06-19T12:00:00+00:00",
                        ),
                        ("2026-06-10", "home", "/", "en", 20, "2026-06-10T12:00:00+00:00"),
                    ],
                )
                db.commit()

                daily = list_analytics_daily_totals(db, since_date="2026-06-18")
                page_types = list_analytics_page_type_totals(db, since_date="2026-06-18")
                top_paths = list_analytics_top_paths(db, since_date="2026-06-18")
            finally:
                db.close()

        self.assertEqual(
            [
                {"view_date": "2026-06-19", "views": 4, "path_count": 1},
                {"view_date": "2026-06-18", "views": 5, "path_count": 2},
            ],
            daily,
        )
        self.assertEqual(
            [
                {"page_type": "shop", "views": 4, "path_count": 1},
                {"page_type": "home", "views": 3, "path_count": 1},
                {"page_type": "listing", "views": 2, "path_count": 1},
            ],
            page_types,
        )
        self.assertEqual(
            [
                {
                    "page_type": "shop",
                    "path_key": "/shops/morceau",
                    "lang": "fr",
                    "views": 4,
                },
                {"page_type": "home", "path_key": "/", "lang": "en", "views": 3},
                {
                    "page_type": "listing",
                    "path_key": "/listing/MCM-0001",
                    "lang": "en",
                    "views": 2,
                },
            ],
            top_paths,
        )

    def test_admin_analytics_page_shows_usage_summary(self) -> None:
        with self.app.app_context():
            db = get_db(self.app)
            try:
                db.execute(
                    """
                        INSERT INTO analytics_page_views (
                            view_date, page_type, path_key, lang, views, updated_at
                        ) VALUES ('2026-06-19', 'shop', '/shops/morceau', 'en', 7,
                            '2026-06-19T12:00:00+00:00')
                        """
                )
                db.commit()
            finally:
                db.close()

        response = self.client.get("/admin/analytics?since=2026-06-18")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Analytics and operations", response.text)
        self.assertIn("2026-06-19", response.text)
        self.assertIn("/shops/morceau", response.text)
        self.assertIn("7", response.text)
        self.assertIn("Outbound source clicks: deferred", response.text)

    def test_admin_analytics_page_has_empty_state(self) -> None:
        response = self.client.get("/admin/analytics?since=2026-06-18")

        self.assertEqual(response.status_code, 200)
        self.assertIn("No page-view rows for this window.", response.text)
