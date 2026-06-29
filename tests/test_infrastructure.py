from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class InfrastructureTests(AppTestCase):
    def test_d1_mode_requires_configured_secret_key(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "MCM_SECRET_KEY"),
        ):
            create_app({"TESTING": True, "D1_BRIDGE_URL": "https://example.test/internal/d1/query"})

    def test_d1_mode_get_db_and_initialize_storage_skip_local_schema(self) -> None:
        self.app.config["D1_BRIDGE_URL"] = "https://example.test/internal/d1/query"
        self.app.config["D1_BRIDGE_TOKEN"] = "test-token"

        db = get_db(self.app)

        self.assertIsInstance(db, D1Connection)
        self.assertEqual(db.url, "https://example.test/internal/d1/query")
        self.assertEqual(db.token, "test-token")
        with patch("mcm.db.ensure_schema") as ensure_schema_mock:
            initialize_storage(self.app)
        ensure_schema_mock.assert_not_called()

    def test_legacy_schema_upgrade_helpers_add_missing_columns(self) -> None:
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        try:
            db.executescript(
                """
                    CREATE TABLE shops (
                        id INTEGER PRIMARY KEY,
                        slug TEXT NOT NULL
                    );
                    CREATE TABLE refresh_jobs (
                        id INTEGER PRIMARY KEY,
                        source_slug TEXT NOT NULL,
                        started_at TEXT NOT NULL
                    );
                    """
            )

            ensure_shop_address_columns(db)
            ensure_refresh_job_columns(db)

            shop_columns = {row["name"] for row in db.execute("PRAGMA table_info(shops)")}
            self.assertTrue(
                {
                    "street_address",
                    "wordmark_text",
                    "wordmark_style",
                    "postal_code",
                    "public_location_note",
                    "latitude",
                    "longitude",
                }.issubset(shop_columns)
            )
            refresh_columns = {row["name"] for row in db.execute("PRAGMA table_info(refresh_jobs)")}
            self.assertTrue({"chunk_index", "entry_url"}.issubset(refresh_columns))
        finally:
            db.close()

    def test_invalid_anonymous_identity_cookie_is_ignored(self) -> None:
        with self.app.test_request_context(
            "/",
            headers={"Cookie": f"{ANONYMOUS_COOKIE_NAME}=not-a-valid-signed-token"},
        ):
            self.assertEqual(read_identity_token(self.app), "")

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

    def test_local_schema_sql_lives_in_dedicated_resource(self) -> None:
        schema_sql = load_local_schema_sql()

        self.assertEqual(LOCAL_SCHEMA_PATH, PROJECT_ROOT / "mcm" / "schema.sql")
        self.assertIn("CREATE TABLE IF NOT EXISTS shops", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS listings", schema_sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_listings_source_shop", schema_sql)

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

    def test_public_responses_include_security_headers(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=31536000")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("geolocation=()", response.headers["Permissions-Policy"])
        self.assertIn("camera=()", response.headers["Permissions-Policy"])

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

    def test_i18n_helper_fallback_branches(self) -> None:
        with self.app.test_request_context("/?lang=fr"):
            self.assertEqual(status_label(None), "Unknown")
            self.assertEqual(status_label("custom_status"), "custom status")
            self.assertEqual(material_label(None), "")
            self.assertEqual(era_label(None), "")
            self.assertEqual(era_label("1975"), "1975")
            self.assertEqual(condition_label(None), "")
            self.assertEqual(
                price_text({"price_value": None, "price_raw": "Sold out", "currency": "CAD"}),
                "Sold out",
            )
            self.assertEqual(
                price_text({"price_value": None, "price_raw": "", "currency": "CAD"}),
                "Contact us for details",
            )
            self.assertEqual(filter_summary({}), "")

    def test_freshness_label_week_branch_and_clean_int_values(self) -> None:
        with self.app.test_request_context("/"):
            self.assertEqual(
                freshness_label((datetime.now(UTC).replace(microsecond=0)).isoformat()),
                "checked today",
            )
            self.assertEqual(
                freshness_label(
                    (datetime.now(UTC).replace(microsecond=0) - timedelta(days=3)).isoformat()
                ),
                "checked this week",
            )
            self.assertEqual(
                freshness_label(
                    (datetime.now(UTC).replace(microsecond=0) - timedelta(days=30)).isoformat()
                ),
                "needs refresh",
            )
        self.assertEqual(clean_int_values(["1", None, "bad", 2]), [1, 2])
        self.assertEqual(clean_int_values(("1", "2")), [])


class D1ConnectionTests(unittest.TestCase):
    def test_execute_posts_query_and_returns_cursor_rows(self) -> None:
        captured_request = None
        captured_timeout = None

        def fake_urlopen(request: Any, timeout: int) -> FakeHttpResponse:
            nonlocal captured_request, captured_timeout
            captured_request = request
            captured_timeout = timeout
            return FakeHttpResponse(
                {
                    "success": True,
                    "results": [{"id": 1, "name": "Morceau"}, {"id": 2, "name": "Showroom"}],
                    "changes": 2,
                }
            )

        conn = D1Connection("https://d1.example/query", "secret-token")
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cursor = conn.execute("SELECT * FROM shops WHERE id = ?", [1])

        self.assertEqual(captured_timeout, 30)
        self.assertIsNotNone(captured_request)
        self.assertEqual(captured_request.full_url, "https://d1.example/query")
        self.assertEqual(captured_request.get_method(), "POST")
        self.assertEqual(captured_request.headers["Authorization"], "Bearer secret-token")
        self.assertEqual(captured_request.headers["Content-type"], "application/json")
        self.assertEqual(
            json.loads(captured_request.data.decode()),
            {"sql": "SELECT * FROM shops WHERE id = ?", "params": [1]},
        )
        self.assertEqual(conn.query_count, 1)
        self.assertGreaterEqual(conn.total_query_ms, 0)
        self.assertEqual(cursor.rowcount, 2)
        first_row = cursor.fetchone()
        self.assertIsNotNone(first_row)
        self.assertEqual(first_row["name"], "Morceau")
        self.assertEqual(cursor.fetchall(), [{"id": 2, "name": "Showroom"}])
        self.assertIsNone(cursor.fetchone())

    def test_execute_defaults_missing_parameters_and_changes(self) -> None:
        with patch(
            "urllib.request.urlopen",
            return_value=FakeHttpResponse({"success": True, "results": [{"ok": True}]}),
        ):
            cursor = D1Connection("https://d1.example/query", "token").execute("SELECT 1")

        self.assertEqual(cursor.rowcount, 0)
        self.assertEqual(cursor.fetchall(), [{"ok": True}])

    def test_execute_raises_d1_error_for_http_url_and_unsuccessful_body(self) -> None:
        http_error = urllib.error.HTTPError(
            "https://d1.example/query",
            500,
            "Server Error",
            {},
            FakeErrorBody("bad gateway"),
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(D1Error, "HTTP 500: bad gateway"):
                D1Connection("https://d1.example/query", "token").execute("SELECT 1")
        http_error.close()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ):
            with self.assertRaisesRegex(D1Error, "D1 bridge request failed"):
                D1Connection("https://d1.example/query", "token").execute("SELECT 1")

        with patch("urllib.request.urlopen", return_value=FakeHttpResponse({"success": False})):
            with self.assertRaisesRegex(D1Error, "D1 bridge query failed"):
                D1Connection("https://d1.example/query", "token").execute("SELECT 1")

        with patch(
            "urllib.request.urlopen",
            return_value=FakeHttpResponse({"success": False, "error": "bad SQL"}),
        ):
            with self.assertRaisesRegex(D1Error, "bad SQL"):
                D1Connection("https://d1.example/query", "token").execute("SELECT 1")

    def test_executemany_and_noop_connection_methods(self) -> None:
        conn = D1Connection("https://d1.example/query", "token")
        with patch.object(conn, "execute") as execute:
            conn.executemany("INSERT INTO shops (id) VALUES (?)", [(1,), (2,)])

        self.assertEqual(execute.call_count, 2)
        execute.assert_any_call("INSERT INTO shops (id) VALUES (?)", (1,))
        execute.assert_any_call("INSERT INTO shops (id) VALUES (?)", (2,))
        self.assertIsNone(conn.commit())
        self.assertIsNone(conn.close())

        with self.assertRaisesRegex(D1Error, "Wrangler migrations"):
            conn.executescript("CREATE TABLE example (id INTEGER)")

    def test_cursor_fetches_rows_in_order(self) -> None:
        cursor = D1Cursor([{"id": 1}, {"id": 2}], 10)

        self.assertEqual(cursor.rowcount, 10)
        self.assertEqual(cursor.fetchone(), {"id": 1})
        self.assertEqual(cursor.fetchall(), [{"id": 2}])
        self.assertEqual(cursor.fetchall(), [])


class LocationHelperTests(unittest.TestCase):
    def test_shop_address_lines_compacts_missing_parts(self) -> None:
        self.assertEqual(
            shop_address_lines(
                {
                    "street_address": " 123 Rue Test ",
                    "city": " Montreal ",
                    "province": " QC ",
                    "postal_code": "",
                    "country": " Canada ",
                }
            ),
            ["123 Rue Test", "Montreal QC", "Canada"],
        )
        self.assertEqual(shop_address_lines({}), [])

    def test_shop_map_urls_and_presence_require_address_data(self) -> None:
        shop = {
            "name": "Morceau",
            "street_address": "5235 Saint-Laurent",
            "city": "Montreal",
            "province": "QC",
            "postal_code": "H2T 1S4",
            "latitude": 45.525,
            "longitude": -73.596,
        }

        self.assertEqual(
            shop_directions_url(shop),
            "https://www.google.com/maps/search/?api=1&query=Morceau%2C+5235+Saint-Laurent%2C+Montreal%2C+QC%2C+H2T+1S4",
        )
        self.assertEqual(
            shop_apple_maps_url(shop),
            "https://maps.apple.com/?q=Morceau%2C+5235+Saint-Laurent%2C+Montreal%2C+QC%2C+H2T+1S4",
        )
        self.assertTrue(shop_has_map(shop))

        self.assertEqual(shop_directions_url({}), "")
        self.assertEqual(shop_apple_maps_url({}), "")
        self.assertFalse(shop_has_map({"street_address": "123 Rue Test", "latitude": 0}))


class SourceUtilityTests(unittest.TestCase):
    def test_source_utility_helpers_cover_edge_cases(self) -> None:
        self.assertEqual(_chunks([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
        self.assertEqual(_slug_to_title("mostly-danish_items"), "Mostly Danish Items")
        self.assertEqual(_slugify("Danish Sofa + Teak!"), "danish-sofa-teak")
        self.assertEqual(_clean_text("  one\n two\tthree "), "one two three")
        self.assertEqual(_normalize_lookup("Étagère d'appoint"), "etagere d appoint")

        soup = BeautifulSoup("<p>  Hello <strong> teak </strong> </p>", "html.parser")
        self.assertEqual(_safe_text(soup.p), "Hello teak")
        self.assertEqual(_safe_text(None), "")

        self.assertIsNone(_to_float(None))
        self.assertEqual(_to_float("C$1,250.50"), 1250.50)
        self.assertEqual(_to_float("$1.250.50 CAD"), 1250.50)
        self.assertEqual(_to_float("$1,250 CAD"), 1250)
        self.assertEqual(_to_float("3 500 $"), 3500)
        self.assertEqual(_to_float("1 250,50 $"), 1250.50)
        self.assertIsNone(_to_float("not a price"))
        self.assertIsNone(_to_float("..."))
