from __future__ import annotations

import sqlite3

from flask import Flask

from .d1 import D1Connection
from .sources import SOURCE_DEFINITIONS, SourceDefinition


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


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            website TEXT NOT NULL,
            street_address TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL,
            province TEXT NOT NULL,
            postal_code TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            public_location_note TEXT NOT NULL DEFAULT '',
            is_montreal_local INTEGER NOT NULL DEFAULT 0,
            shipping_summary TEXT NOT NULL,
            source_type TEXT NOT NULL,
            crawl_priority INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            style_focus TEXT NOT NULL DEFAULT '',
            listing_url TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_shop_id INTEGER NOT NULL,
            source_listing_url TEXT NOT NULL,
            source_listing_key TEXT NOT NULL,
            title TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            price_raw TEXT NOT NULL DEFAULT '',
            price_value REAL,
            currency TEXT NOT NULL DEFAULT 'CAD',
            primary_image_url TEXT NOT NULL DEFAULT '',
            additional_image_urls TEXT NOT NULL DEFAULT '[]',
            availability_status TEXT NOT NULL DEFAULT 'unknown',
            shipping_scope TEXT NOT NULL DEFAULT '',
            ships_to_montreal INTEGER NOT NULL DEFAULT 0,
            shipping_note TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            subcategory TEXT NOT NULL DEFAULT '',
            designer TEXT NOT NULL DEFAULT '',
            maker TEXT NOT NULL DEFAULT '',
            era TEXT NOT NULL DEFAULT '',
            materials TEXT NOT NULL DEFAULT '',
            dimensions_text TEXT NOT NULL DEFAULT '',
            width REAL,
            depth REAL,
            height REAL,
            condition_text TEXT NOT NULL DEFAULT '',
            location_text TEXT NOT NULL DEFAULT '',
            source_description TEXT NOT NULL DEFAULT '',
            ingest_source_type TEXT NOT NULL DEFAULT '',
            parse_confidence REAL NOT NULL DEFAULT 0,
            dedupe_group_id TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            is_featured INTEGER NOT NULL DEFAULT 0,
            manual_notes TEXT NOT NULL DEFAULT '',
            availability_override TEXT NOT NULL DEFAULT '',
            category_override TEXT NOT NULL DEFAULT '',
            UNIQUE(source_shop_id, source_listing_key)
        );
        CREATE TABLE IF NOT EXISTS crawl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            ran_at TEXT NOT NULL,
            status TEXT NOT NULL,
            listings_found INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS crawl_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS listing_identity_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            source_listing_key TEXT NOT NULL,
            title TEXT NOT NULL,
            candidate_listing_ids TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open'
        );
        CREATE TABLE IF NOT EXISTS listing_availability_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            source_listing_key TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            from_status TEXT NOT NULL DEFAULT '',
            to_status TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT 'source_refresh'
        );
        CREATE TABLE IF NOT EXISTS listing_price_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            source_listing_key TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            from_price_raw TEXT NOT NULL DEFAULT '',
            from_price_value REAL,
            to_price_raw TEXT NOT NULL DEFAULT '',
            to_price_value REAL,
            currency TEXT NOT NULL DEFAULT 'CAD',
            event_type TEXT NOT NULL DEFAULT 'source_refresh'
        );
        CREATE TABLE IF NOT EXISTS refresh_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            source_slug TEXT NOT NULL,
            chunk_index INTEGER,
            entry_url TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            listings_found INTEGER NOT NULL DEFAULT 0,
            new_count INTEGER NOT NULL DEFAULT 0,
            reconciled_count INTEGER NOT NULL DEFAULT 0,
            hidden_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS anonymous_identities (
            owner_key TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS anonymous_favourite_listings (
            owner_key TEXT NOT NULL,
            listing_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (owner_key, listing_id)
        );
        CREATE TABLE IF NOT EXISTS anonymous_favourite_shops (
            owner_key TEXT NOT NULL,
            shop_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (owner_key, shop_id)
        );
        CREATE TABLE IF NOT EXISTS anonymous_saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_key TEXT NOT NULL,
            name TEXT NOT NULL,
            query_string TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(owner_key, query_string)
        );
        CREATE INDEX IF NOT EXISTS idx_listing_availability_events_listing
            ON listing_availability_events(listing_id, observed_at);
        CREATE INDEX IF NOT EXISTS idx_listing_availability_events_transition
            ON listing_availability_events(listing_id, from_status, to_status);
        CREATE INDEX IF NOT EXISTS idx_listing_price_events_listing
            ON listing_price_events(listing_id, observed_at);
        CREATE INDEX IF NOT EXISTS idx_listing_price_events_change
            ON listing_price_events(listing_id, from_price_value, to_price_value);
        CREATE INDEX IF NOT EXISTS idx_anonymous_favourite_listings_listing
            ON anonymous_favourite_listings(listing_id);
        CREATE INDEX IF NOT EXISTS idx_anonymous_favourite_shops_shop
            ON anonymous_favourite_shops(shop_id);
        CREATE INDEX IF NOT EXISTS idx_anonymous_saved_searches_owner
            ON anonymous_saved_searches(owner_key, updated_at);
        """
    )
    ensure_shop_address_columns(db)
    ensure_refresh_job_columns(db)
    db.commit()


def ensure_shop_address_columns(db: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in db.execute("PRAGMA table_info(shops)").fetchall()}
    if "street_address" not in existing_columns:
        db.execute("ALTER TABLE shops ADD COLUMN street_address TEXT NOT NULL DEFAULT ''")
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
            slug, name, website, street_address, city, province, postal_code,
            country, latitude, longitude, public_location_note, is_montreal_local,
            shipping_summary, source_type, crawl_priority, notes, description,
            style_focus, listing_url, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            website = excluded.website,
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
