from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask

from .d1 import D1Connection
from .source_definitions import SOURCE_DEFINITIONS
from .source_types import SourceDefinition

LOCAL_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db(app: Flask) -> sqlite3.Connection | D1Connection:
    if app.config.get("D1_BRIDGE_URL"):
        return D1Connection(app.config["D1_BRIDGE_URL"], app.config["D1_BRIDGE_TOKEN"])
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def initialize_storage(app: Flask) -> None:
    if app.config.get("D1_BRIDGE_URL"):
        return
    with app.app_context():
        db = get_db(app)
        try:
            ensure_schema(db)
            ensure_shops_seeded(db)
        finally:
            db.close()


def load_local_schema_sql() -> str:
    return LOCAL_SCHEMA_PATH.read_text(encoding="utf-8")


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(load_local_schema_sql())
    ensure_shop_address_columns(db)
    ensure_refresh_job_columns(db)
    db.commit()


def ensure_shop_address_columns(db: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in db.execute("PRAGMA table_info(shops)").fetchall()}
    if "street_address" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN street_address TEXT NOT NULL DEFAULT ''")
    if "wordmark_text" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN wordmark_text TEXT NOT NULL DEFAULT ''")
    if "wordmark_style" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN wordmark_style TEXT NOT NULL DEFAULT ''")
    if "postal_code" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN postal_code TEXT NOT NULL DEFAULT ''")
    if "public_location_note" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN public_location_note TEXT NOT NULL DEFAULT ''")
    if "latitude" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN latitude REAL")
    if "longitude" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN longitude REAL")


def ensure_refresh_job_columns(db: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(refresh_jobs)").fetchall()
    }
    if "chunk_index" not in existing_columns:
        db.execute("ALTER TABLE refresh_jobs ADD COLUMN chunk_index INTEGER")
    if "entry_url" not in existing_columns:
        db.execute("ALTER TABLE refresh_jobs ADD COLUMN entry_url TEXT NOT NULL DEFAULT ''")
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_refresh_jobs_source_chunk_started
            ON refresh_jobs(source_slug, chunk_index, started_at)
        """
    )


def ensure_shops_seeded(db: sqlite3.Connection) -> None:
    db.execute("UPDATE shops SET active = 0")
    for source in SOURCE_DEFINITIONS:
        ensure_source_shop_seeded(db, source)
    db.execute(
        """
        UPDATE listings
        SET is_active = 0
        WHERE source_shop_id IN (SELECT id FROM shops WHERE active = 0)
        """
    )
    db.commit()


def ensure_source_shop_seeded(db: sqlite3.Connection, source: SourceDefinition) -> None:
    db.execute(
        """
        INSERT INTO shops (
            slug, name, website, wordmark_text, wordmark_style, street_address, city, province,
            postal_code, country, latitude, longitude, public_location_note, is_montreal_local,
            shipping_summary, source_type, crawl_priority, notes, description, style_focus,
            listing_url, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            website = excluded.website,
            wordmark_text = excluded.wordmark_text,
            wordmark_style = excluded.wordmark_style,
            street_address = excluded.street_address,
            city = excluded.city,
            province = excluded.province,
            postal_code = excluded.postal_code,
            country = excluded.country,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            public_location_note = excluded.public_location_note,
            is_montreal_local = excluded.is_montreal_local,
            shipping_summary = excluded.shipping_summary,
            source_type = excluded.source_type,
            crawl_priority = excluded.crawl_priority,
            notes = excluded.notes,
            description = excluded.description,
            style_focus = excluded.style_focus,
            listing_url = excluded.listing_url,
            active = 1
        """,
        (
            source.slug,
            source.name,
            source.website,
            source.wordmark_text,
            source.wordmark_style,
            source.street_address,
            source.city,
            source.province,
            source.postal_code,
            source.country,
            source.latitude,
            source.longitude,
            source.public_location_note,
            1 if source.is_montreal_local else 0,
            source.shipping_summary,
            source.source_type,
            source.crawl_priority,
            source.notes,
            source.description,
            source.style_focus,
            source.listing_urls[0],
        ),
    )
