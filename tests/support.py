from __future__ import annotations

# ruff: noqa: F401,I001

import json
import os
import re
import sqlite3
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from bs4 import BeautifulSoup

import mcm.sources as sources_module
from mcm.app import create_app
from mcm.d1 import D1Connection, D1Cursor, D1Error
from mcm.db import (
    LOCAL_SCHEMA_PATH,
    ensure_refresh_job_columns,
    ensure_schema,
    ensure_shop_address_columns,
    get_db,
    initialize_storage,
    load_local_schema_sql,
)
from mcm.i18n import (
    MATERIAL_LABELS,
    SHOP_TRANSLATIONS,
    condition_label,
    era_label,
    filter_summary,
    freshness_label,
    material_label,
    price_text,
    status_label,
)
from mcm.identity import ANONYMOUS_COOKIE_NAME, clean_int_values, read_identity_token
from mcm.locales import TRANSLATIONS_EN, TRANSLATIONS_FR
from mcm.locations import (
    shop_address_lines,
    shop_apple_maps_url,
    shop_directions_url,
    shop_has_map,
)
from mcm.refresh import (
    RECONCILABLE_CHUNK_COUNTS,
    listing_id_from_item_number,
    public_item_number,
    reconcile_chunked_source,
    refresh_all_sources,
    refresh_source_by_slug,
)
from mcm.repository_analytics import (
    list_analytics_daily_totals,
    list_analytics_page_type_totals,
    list_analytics_top_paths,
)
from mcm.repository_catalog import (
    count_listings,
    delete_saved_search,
    favourite_counts,
    favourite_listing_session_list,
    favourite_shop_session_list,
    find_duplicate_candidates,
    get_listing,
    get_shop,
    get_shop_by_slug,
    list_filter_values,
    list_location_filter_values,
    list_saved_searches,
    query_listings,
    sanitize_availability,
    save_search,
    search_query_clause,
    search_score_expression,
    toggle_favourite_listing,
    toggle_favourite_shop,
    update_listing_overrides,
)
from mcm.repository_design import (
    add_listing_design_entity_evidence,
    clean_designer_filter_value,
    create_design_entity,
    design_entity_filter_query_values,
    designer_filter_query_values,
    list_design_entities,
    list_design_entity_candidates,
    review_design_entity_candidate,
)
from mcm.repository_refresh import (
    finish_refresh_job,
    latest_successful_chunk_jobs,
    reassign_listing_events,
    record_availability_event,
    record_price_event,
    start_refresh_job,
)
from mcm.seed_data import SEED_LISTINGS
from mcm.source_utils import (
    _chunks,
    _clean_text,
    _normalize_lookup,
    _safe_text,
    _slug_to_title,
    _slugify,
    _to_float,
)
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
    _source_listing_limit,
    _square_product_is_sold_out,
    fetch_chez_lamothe_page_listings,
    fetch_le_centerpiece_entry_listings,
    fetch_shopify_collection_page_listings,
    fetch_showroom_entry_listings,
    fetch_source_listings,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeHttpResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self.body = json.dumps(body).encode()

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class FakeErrorBody:
    def __init__(self, body: str) -> None:
        self.body = body.encode()

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        return None


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


class AppTestCase(unittest.TestCase):
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


__all__ = [name for name in globals() if not name.startswith("__")]
