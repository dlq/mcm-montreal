from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from .db import ensure_source_shop_seeded
from .repository import get_shop_by_slug
from .sources import (
    SOURCE_DEFINITIONS,
    SourceDefinition,
    fetch_chez_lamothe_page_listings,
    fetch_le_centerpiece_entry_listings,
    fetch_showroom_entry_listings,
    fetch_source_listings,
)


@dataclass(frozen=True)
class RefreshResult:
    source_name: str
    source_slug: str
    listings_found: int
    new_count: int
    reconciled_count: int
    hidden_count: int
    error: str
    kept_existing: bool


@dataclass(frozen=True)
class RefreshJobRef:
    shop_id: int
    source_slug: str
    started_at: str


@dataclass(frozen=True)
class ShowroomChunkResult:
    result: RefreshResult
    chunk_index: int
    entry_url: str


@dataclass(frozen=True)
class SourceChunkResult:
    result: RefreshResult
    chunk_index: int
    entry_url: str


def refresh_all_sources(
    db: sqlite3.Connection,
    progress: Callable[[str], None] | None = None,
) -> None:
    for source in SOURCE_DEFINITIONS:
        if progress:
            progress(f"Checking {source.name} ...")
        result = refresh_source(db, source)
        if progress:
            summary = (
                f"{result.source_name}: {result.listings_found} listings, {result.new_count} new"
            )
            if result.reconciled_count > 0:
                summary += f", {result.reconciled_count} reconciled"
            if result.hidden_count > 0:
                summary += f", {result.hidden_count} hidden"
            if result.kept_existing:
                summary += ", kept existing listings"
            if result.error:
                summary += f" [warning: {result.error}]"
            progress(summary)
    db.commit()


def refresh_source_by_slug(db: sqlite3.Connection, source_slug: str) -> RefreshResult:
    source = next((source for source in SOURCE_DEFINITIONS if source.slug == source_slug), None)
    if source is None:
        raise ValueError(f"Unknown source slug: {source_slug}")
    result = refresh_source(db, source)
    db.commit()
    return result


def refresh_showroom_chunk(db: sqlite3.Connection, chunk_index: int) -> ShowroomChunkResult:
    source = next(
        (source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal"), None
    )
    if source is None:
        raise ValueError("Unknown source slug: showroom-montreal")
    if chunk_index < 0 or chunk_index >= len(source.listing_urls):
        raise ValueError(f"Unknown Showroom chunk index: {chunk_index}")
    entry_url = source.listing_urls[chunk_index]
    listings, error = fetch_showroom_entry_listings(source, entry_url)
    result = _refresh_source_listings(
        db,
        source,
        listings,
        error,
        crawl_is_authoritative=False,
    )
    db.commit()
    return ShowroomChunkResult(result=result, chunk_index=chunk_index, entry_url=entry_url)


def refresh_le_centerpiece_chunk(db: sqlite3.Connection, chunk_index: int) -> SourceChunkResult:
    source = next(
        (source for source in SOURCE_DEFINITIONS if source.slug == "le-centerpiece"), None
    )
    if source is None:
        raise ValueError("Unknown source slug: le-centerpiece")
    if chunk_index < 0 or chunk_index >= len(source.listing_urls):
        raise ValueError(f"Unknown Le Centerpiece chunk index: {chunk_index}")
    entry_url = source.listing_urls[chunk_index]
    listings, error = fetch_le_centerpiece_entry_listings(source, entry_url)
    result = _refresh_source_listings(
        db,
        source,
        listings,
        error,
        crawl_is_authoritative=False,
    )
    db.commit()
    return SourceChunkResult(result=result, chunk_index=chunk_index, entry_url=entry_url)


def refresh_chez_lamothe_chunk(db: sqlite3.Connection, chunk_index: int) -> SourceChunkResult:
    source = next((source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe"), None)
    if source is None:
        raise ValueError("Unknown source slug: chez-lamothe")
    if chunk_index < 0:
        raise ValueError(f"Unknown Chez Lamothe chunk index: {chunk_index}")
    page = chunk_index + 1
    listings, error = fetch_chez_lamothe_page_listings(source, page)
    result = _refresh_source_listings(
        db,
        source,
        listings,
        error,
        crawl_is_authoritative=False,
    )
    db.commit()
    return SourceChunkResult(
        result=result, chunk_index=chunk_index, entry_url=source.listing_urls[0]
    )


def refresh_source(db: sqlite3.Connection, source: SourceDefinition) -> RefreshResult:
    listings, error = fetch_source_listings(source)
    return _refresh_source_listings(
        db,
        source,
        listings,
        error,
        crawl_is_authoritative=error is None,
    )


def _refresh_source_listings(
    db: sqlite3.Connection,
    source: SourceDefinition,
    listings: list[dict[str, object]],
    error: str | None,
    *,
    crawl_is_authoritative: bool,
) -> RefreshResult:
    started_at = datetime.now(UTC).isoformat()
    timestamp = started_at
    ensure_source_shop_seeded(db, source)
    shop = get_shop_by_slug(db, source.slug)
    if not shop:
        raise RuntimeError(f"Missing shop record for source slug: {source.slug}")
    job = start_refresh_job(db, int(shop["id"]), source.slug, started_at)
    existing_listing_count = db.execute(
        "SELECT COUNT(*) AS count FROM listings WHERE source_shop_id = ?",
        (shop["id"],),
    ).fetchone()["count"]
    kept_existing = bool(error and existing_listing_count)
    listings_to_process = [] if kept_existing else listings
    seen_keys: set[str] = set()
    new_count = 0
    reconciled_count = 0
    for item in listings_to_process:
        source_url = item["source_listing_url"]
        key = item.get("source_listing_key") or source_url.rstrip("/").lower()
        seen_keys.add(key)
        existing = db.execute(
            """
            SELECT id, first_seen_at, availability_status, is_active
            FROM listings
            WHERE source_shop_id = ? AND source_listing_key = ?
            """,
            (shop["id"], key),
        ).fetchone()

        if existing and not existing["is_active"]:
            reconciled = find_reconciliation_candidate(
                db,
                int(shop["id"]),
                item,
                seen_keys,
                timestamp,
                key,
            )
            if reconciled and reconciled["id"] != existing["id"]:
                reassign_listing_events(db, int(existing["id"]), int(reconciled["id"]), str(key))
                db.execute("DELETE FROM listings WHERE id = ?", (existing["id"],))
                existing = reconciled
                reconciled_count += 1

        if not existing:
            existing = find_reconciliation_candidate(
                db,
                int(shop["id"]),
                item,
                seen_keys,
                timestamp,
                key,
            )
            if existing:
                reconciled_count += 1

        if (
            existing
            and item.get("availability_status") == "sold_out"
            and existing["availability_status"] == "removed"
            and not existing["is_active"]
        ):
            continue

        if not existing and item.get("availability_status") == "sold_out":
            continue

        first_seen = existing["first_seen_at"] if existing else timestamp
        if existing:
            old_status = str(existing["availability_status"] or "")
            new_status = str(item.get("availability_status", "unknown"))
            db.execute(
                """
                UPDATE listings
                SET source_listing_url = ?,
                    source_listing_key = ?,
                    title = ?,
                    normalized_title = ?,
                    price_raw = ?,
                    price_value = ?,
                    currency = ?,
                    primary_image_url = ?,
                    additional_image_urls = ?,
                    availability_status = ?,
                    shipping_scope = ?,
                    ships_to_montreal = ?,
                    shipping_note = ?,
                    last_seen_at = ?,
                    last_checked_at = ?,
                    category = ?,
                    designer = ?,
                    maker = ?,
                    era = ?,
                    materials = ?,
                    dimensions_text = ?,
                    condition_text = ?,
                    location_text = ?,
                    source_description = ?,
                    ingest_source_type = ?,
                    parse_confidence = ?,
                    is_active = 1
                WHERE id = ?
                """,
                (
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
                    item.get("category", ""),
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
                    existing["id"],
                ),
            )
            if old_status != new_status:
                record_availability_event(
                    db,
                    int(existing["id"]),
                    int(shop["id"]),
                    str(key),
                    old_status,
                    new_status,
                    timestamp,
                    "source_refresh",
                )
            continue

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
        created = db.execute(
            """
            SELECT id
            FROM listings
            WHERE source_shop_id = ? AND source_listing_key = ?
            """,
            (shop["id"], key),
        ).fetchone()
        if created:
            record_availability_event(
                db,
                int(created["id"]),
                int(shop["id"]),
                str(key),
                "",
                str(item.get("availability_status", "unknown")),
                timestamp,
                "discovered",
            )
    deactivated = 0
    if crawl_is_authoritative:
        rows_to_deactivate = db.execute(
            "SELECT id, source_listing_key, availability_status FROM listings WHERE source_shop_id = ? AND source_listing_key NOT IN ({}) AND is_active = 1".format(
                ",".join("?" for _ in seen_keys) if seen_keys else "''"
            ),
            [shop["id"], *seen_keys],
        ).fetchall()
        for row in rows_to_deactivate:
            if row["availability_status"] != "removed":
                record_availability_event(
                    db,
                    int(row["id"]),
                    int(shop["id"]),
                    str(row["source_listing_key"]),
                    str(row["availability_status"] or ""),
                    "removed",
                    timestamp,
                    "source_refresh",
                )
        deactivated = db.execute(
            "UPDATE listings SET is_active = 0, availability_status = 'removed', last_checked_at = ? WHERE source_shop_id = ? AND source_listing_key NOT IN ({})".format(
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
        (
            shop["id"],
            timestamp,
            "warning" if error else "success",
            len(listings_to_process),
            error or "",
        ),
    )
    result = RefreshResult(
        source_name=source.name,
        source_slug=source.slug,
        listings_found=len(listings_to_process),
        new_count=new_count,
        reconciled_count=reconciled_count,
        hidden_count=deactivated,
        error=error or "",
        kept_existing=kept_existing,
    )
    finish_refresh_job(db, job, datetime.now(UTC).isoformat(), result)
    return result


def record_availability_event(
    db: sqlite3.Connection,
    listing_id: int,
    shop_id: int,
    source_listing_key: str,
    from_status: str,
    to_status: str,
    observed_at: str,
    event_type: str,
) -> None:
    db.execute(
        """
        INSERT INTO listing_availability_events (
            listing_id, shop_id, source_listing_key, observed_at,
            from_status, to_status, event_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            listing_id,
            shop_id,
            source_listing_key,
            observed_at,
            from_status,
            to_status,
            event_type,
        ),
    )


def reassign_listing_events(
    db: sqlite3.Connection,
    from_listing_id: int,
    to_listing_id: int,
    source_listing_key: str,
) -> None:
    db.execute(
        """
        UPDATE listing_availability_events
        SET listing_id = ?,
            source_listing_key = ?
        WHERE listing_id = ?
        """,
        (to_listing_id, source_listing_key, from_listing_id),
    )


def start_refresh_job(
    db: sqlite3.Connection,
    shop_id: int,
    source_slug: str,
    started_at: str,
) -> RefreshJobRef:
    db.execute(
        """
        INSERT INTO refresh_jobs (shop_id, source_slug, started_at, status)
        VALUES (?, ?, ?, 'running')
        """,
        (shop_id, source_slug, started_at),
    )
    return RefreshJobRef(shop_id=shop_id, source_slug=source_slug, started_at=started_at)


def finish_refresh_job(
    db: sqlite3.Connection,
    job: RefreshJobRef,
    finished_at: str,
    result: RefreshResult,
) -> None:
    db.execute(
        """
        UPDATE refresh_jobs
        SET finished_at = ?,
            status = ?,
            listings_found = ?,
            new_count = ?,
            reconciled_count = ?,
            hidden_count = ?,
            error_message = ?
        WHERE shop_id = ?
          AND source_slug = ?
          AND started_at = ?
        """,
        (
            finished_at,
            "warning" if result.error else "success",
            result.listings_found,
            result.new_count,
            result.reconciled_count,
            result.hidden_count,
            result.error,
            job.shop_id,
            job.source_slug,
            job.started_at,
        ),
    )


def normalize_text(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else " " for ch in text).strip()


def public_item_number(listing_id: int | str) -> str:
    return f"MCM-{int(listing_id):06d}"


def listing_id_from_item_number(item_number: str) -> int | None:
    normalized = item_number.strip().upper()
    if normalized.isdigit():
        return int(normalized)
    if normalized.startswith("MCM-") and normalized[4:].isdigit():
        return int(normalized[4:])
    return None


def find_reconciliation_candidate(
    db: sqlite3.Connection,
    shop_id: int,
    item: dict[str, object],
    seen_keys: set[str],
    timestamp: str,
    source_listing_key: str,
) -> sqlite3.Row | None:
    normalized_title = normalize_text(str(item["title"]))
    rows = db.execute(
        """
        SELECT
            id, source_listing_key, first_seen_at, availability_status, is_active,
            price_value, primary_image_url, source_description
        FROM listings
        WHERE source_shop_id = ?
          AND normalized_title = ?
        ORDER BY last_checked_at DESC, id DESC
        """,
        (shop_id, normalized_title),
    ).fetchall()

    candidates = [row for row in rows if row["source_listing_key"] not in seen_keys]
    scored = []
    for row in candidates:
        score = reconciliation_score(row, item)
        if score >= 2:
            scored.append((score, row))
    if not scored:
        return None

    scored.sort(key=lambda candidate: candidate[0], reverse=True)
    best_score = scored[0][0]
    best_matches = [row for score, row in scored if score == best_score]
    if len(best_matches) == 1:
        return best_matches[0]

    log_identity_review(
        db,
        shop_id,
        timestamp,
        source_listing_key,
        str(item["title"]),
        [int(row["id"]) for row in best_matches],
        f"Ambiguous source-key reconciliation at score {best_score}",
    )
    return None


def reconciliation_score(row: sqlite3.Row, item: dict[str, object]) -> int:
    score = 0
    item_image = str(item.get("primary_image_url") or "")
    if item_image and item_image == row["primary_image_url"]:
        score += 2

    item_description = normalize_text(str(item.get("source_description") or ""))
    row_description = normalize_text(str(row["source_description"] or ""))
    if item_description and item_description == row_description:
        score += 2

    item_price = item.get("price_value")
    if item_price is not None and item_price == row["price_value"]:
        score += 1

    return score


def log_identity_review(
    db: sqlite3.Connection,
    shop_id: int,
    timestamp: str,
    source_listing_key: str,
    title: str,
    candidate_listing_ids: list[int],
    reason: str,
) -> None:
    existing = db.execute(
        """
        SELECT id
        FROM listing_identity_reviews
        WHERE shop_id = ?
          AND source_listing_key = ?
          AND status = 'open'
        """,
        (shop_id, source_listing_key),
    ).fetchone()
    if existing:
        return

    db.execute(
        """
        INSERT INTO listing_identity_reviews (
            shop_id, created_at, source_listing_key, title, candidate_listing_ids, reason
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            shop_id,
            timestamp,
            source_listing_key,
            title,
            ",".join(str(listing_id) for listing_id in candidate_listing_ids),
            reason,
        ),
    )
