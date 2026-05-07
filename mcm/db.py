from __future__ import annotations

import sqlite3

from flask import Flask

from .sources import SOURCE_DEFINITIONS


def get_db(app: Flask) -> sqlite3.Connection:
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def initialize_storage(app: Flask) -> None:
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
            city TEXT NOT NULL,
            province TEXT NOT NULL,
            country TEXT NOT NULL,
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
        """
    )
    db.commit()


def ensure_shops_seeded(db: sqlite3.Connection) -> None:
    db.execute("UPDATE shops SET active = 0")
    for source in SOURCE_DEFINITIONS:
        db.execute(
            """
            INSERT INTO shops (
                slug, name, website, city, province, country, is_montreal_local,
                shipping_summary, source_type, crawl_priority, notes, description,
                style_focus, listing_url, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                website = excluded.website,
                city = excluded.city,
                province = excluded.province,
                country = excluded.country,
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
                source.city,
                source.province,
                source.country,
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
    db.execute(
        """
        UPDATE listings
        SET is_active = 0
        WHERE source_shop_id IN (SELECT id FROM shops WHERE active = 0)
        """
    )
    db.commit()
