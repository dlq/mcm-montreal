from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from .repository import get_shop_by_slug
from .sources import SOURCE_DEFINITIONS, fetch_source_listings


def refresh_all_sources(
    db: sqlite3.Connection,
    progress: Callable[[str], None] | None = None,
) -> None:
    timestamp = datetime.now(UTC).isoformat()
    for source in SOURCE_DEFINITIONS:
        if progress:
            progress(f"Checking {source.name} ...")
        shop = get_shop_by_slug(db, source.slug)
        if not shop:
            raise RuntimeError(f"Missing shop record for source slug: {source.slug}")
        listings, error = fetch_source_listings(source)
        seen_keys: set[str] = set()
        new_count = 0
        for item in listings:
            source_url = item["source_listing_url"]
            key = item.get("source_listing_key") or source_url.rstrip("/").lower()
            seen_keys.add(key)
            existing = db.execute(
                "SELECT id, first_seen_at FROM listings WHERE source_shop_id = ? AND source_listing_key = ?",
                (shop["id"], key),
            ).fetchone()
            first_seen = existing["first_seen_at"] if existing else timestamp
            if not existing:
                new_count += 1
            db.execute(
                """
                INSERT INTO listings (
                    source_shop_id, source_listing_url, source_listing_key, title, normalized_title,
                    price_raw, price_value, currency, primary_image_url, additional_image_urls,
                    availability_status, shipping_scope, ships_to_montreal, shipping_note,
                    last_seen_at, last_checked_at, first_seen_at, category, subcategory, designer,
                    maker, era, materials, dimensions_text, condition_text, location_text,
                    source_description, ingest_source_type, parse_confidence, dedupe_group_id,
                    is_active, is_featured, manual_notes, availability_override, category_override
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_shop_id, source_listing_key) DO UPDATE SET
                    source_listing_url = excluded.source_listing_url,
                    title = excluded.title,
                    normalized_title = excluded.normalized_title,
                    price_raw = excluded.price_raw,
                    price_value = excluded.price_value,
                    currency = excluded.currency,
                    primary_image_url = excluded.primary_image_url,
                    additional_image_urls = excluded.additional_image_urls,
                    availability_status = excluded.availability_status,
                    shipping_scope = excluded.shipping_scope,
                    ships_to_montreal = excluded.ships_to_montreal,
                    shipping_note = excluded.shipping_note,
                    last_seen_at = excluded.last_seen_at,
                    last_checked_at = excluded.last_checked_at,
                    category = excluded.category,
                    designer = excluded.designer,
                    maker = excluded.maker,
                    era = excluded.era,
                    materials = excluded.materials,
                    dimensions_text = excluded.dimensions_text,
                    condition_text = excluded.condition_text,
                    location_text = excluded.location_text,
                    source_description = excluded.source_description,
                    ingest_source_type = excluded.ingest_source_type,
                    parse_confidence = excluded.parse_confidence,
                    is_active = 1
                """,
                (
                    shop["id"],
                    source_url,
                    key,
                    item["title"],
                    normalize_text(item["title"]),
                    item.get("price_raw", ""),
                    item.get("price_value"),
                    item.get("currency", "CAD"),
                    item.get("primary_image_url", ""),
                    json.dumps(item.get("additional_image_urls", [])),
                    item.get("availability_status", "unknown"),
                    item.get("shipping_scope", ""),
                    item.get("ships_to_montreal", 0),
                    item.get("shipping_note", ""),
                    timestamp,
                    timestamp,
                    first_seen,
                    item.get("category", ""),
                    "",
                    item.get("designer", ""),
                    item.get("maker", ""),
                    item.get("era", ""),
                    item.get("materials", ""),
                    item.get("dimensions_text", ""),
                    item.get("condition_text", ""),
                    item.get("location_text", f"{shop['city']}, {shop['province']}"),
                    item.get("source_description", ""),
                    item.get("ingest_source_type", "refresh"),
                    float(item.get("parse_confidence", 0.4)),
                    "",
                    1,
                    0,
                    "",
                    "",
                    "",
                ),
            )
        deactivated = db.execute(
            "UPDATE listings SET is_active = 0, last_checked_at = ? WHERE source_shop_id = ? AND source_listing_key NOT IN ({})".format(
                ",".join("?" for _ in seen_keys) if seen_keys else "''"
            ),
            [timestamp, shop["id"], *seen_keys],
        ).rowcount
        if error:
            db.execute(
                "INSERT INTO crawl_failures (shop_id, created_at, error_message) VALUES (?, ?, ?)",
                (shop["id"], timestamp, error),
            )
        db.execute(
            "INSERT INTO crawl_runs (shop_id, ran_at, status, listings_found, error_message) VALUES (?, ?, ?, ?, ?)",
            (shop["id"], timestamp, "warning" if error else "success", len(listings), error or ""),
        )
        if progress:
            summary = f"{source.name}: {len(listings)} listings, {new_count} new"
            if deactivated > 0:
                summary += f", {deactivated} hidden"
            if error:
                summary += f" [warning: {error}]"
            progress(summary)
    db.commit()


def normalize_text(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else " " for ch in text).strip()
