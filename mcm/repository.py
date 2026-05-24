from __future__ import annotations

import html
import re
import sqlite3
import unicodedata
from typing import Any

from flask import has_request_context, session

ALLOWED_FILTER_FIELDS = {"category", "materials", "designer"}
ALLOWED_AVAILABILITY = {"available", "sold_out", "all"}
ALLOWED_SORT = {"curated", "newest", "recent_check", "price_low", "price_high", "recent_source"}
EFFECTIVE_AVAILABILITY_SQL = "COALESCE(NULLIF(l.availability_override, ''), l.availability_status)"
PROVEN_SOLD_OUT_SQL = """
(
    NULLIF(l.availability_override, '') = 'sold_out'
    OR EXISTS (
        SELECT 1
        FROM listing_availability_events lae
        WHERE lae.listing_id = l.id
          AND lae.from_status = 'available'
          AND lae.to_status = 'sold_out'
    )
)
"""


def build_listing_filters(args: Any) -> dict[str, str]:
    return {
        "q": args.get("q", "").strip(),
        "shop": args.get("shop", "").strip(),
        "location": args.get("location", "").strip(),
        "category": args.get("category", "").strip(),
        "material": args.get("material", "").strip(),
        "designer": args.get("designer", "").strip(),
        "ships_to_montreal": args.get("ships_to_montreal", ""),
        "availability": sanitize_availability(args.get("availability", "available")),
        "price_min": args.get("price_min", "").strip(),
        "price_max": args.get("price_max", "").strip(),
        "sort": sanitize_sort(args.get("sort", "curated")),
    }


def query_listings(
    db: sqlite3.Connection,
    filters: dict[str, str],
    include_inactive: bool,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses, params = listing_query_parts(filters, include_inactive)
    order_by = {
        "curated": "CASE WHEN s.slug = 'mostly-danish' THEN 1 ELSE 0 END ASC, l.first_seen_at DESC",
        "newest": "l.first_seen_at DESC",
        "recent_check": "l.last_checked_at DESC",
        "price_low": "CASE WHEN l.price_value IS NULL THEN 1 ELSE 0 END, l.price_value ASC",
        "price_high": "CASE WHEN l.price_value IS NULL THEN 1 ELSE 0 END, l.price_value DESC",
        "recent_source": "l.last_seen_at DESC",
    }[sanitize_sort(filters.get("sort", "curated"))]
    page_clause = ""
    page_params: list[Any] = []
    if limit is not None:
        page_clause = "LIMIT ? OFFSET ?"
        page_params = [limit, max(offset, 0)]
    rows = db.execute(
        f"""
        SELECT
            l.*,
            s.slug AS shop_slug,
            s.name AS shop_name,
            s.is_montreal_local
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE {" AND ".join(clauses)}
        ORDER BY {order_by}
        {page_clause}
        """,
        [*params, *page_params],
    ).fetchall()
    return annotate_listing_rows(rows)


def count_listings(
    db: sqlite3.Connection,
    filters: dict[str, str],
    include_inactive: bool,
) -> int:
    clauses, params = listing_query_parts(filters, include_inactive)
    row = db.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE {" AND ".join(clauses)}
        """,
        params,
    ).fetchone()
    return int(row["count"])


def listing_query_parts(
    filters: dict[str, str],
    include_inactive: bool,
) -> tuple[list[str], list[Any]]:
    clauses = ["1=1", "s.active = 1"]
    params: list[Any] = []
    if not include_inactive:
        clauses.append("l.is_active = 1")
        clauses.append(f"{EFFECTIVE_AVAILABILITY_SQL} != 'removed'")
        clauses.append(f"({EFFECTIVE_AVAILABILITY_SQL} != 'sold_out' OR {PROVEN_SOLD_OUT_SQL})")
    if filters.get("q"):
        clauses.append(
            "(l.title LIKE ? OR l.designer LIKE ? OR l.maker LIKE ? OR l.materials LIKE ?)"
        )
        q = f"%{filters['q']}%"
        params.extend([q, q, q, q])
    if filters.get("shop"):
        clauses.append("s.slug = ?")
        params.append(filters["shop"])
    if filters.get("location"):
        clauses.append("l.location_text LIKE ?")
        params.append(f"%{filters['location']}%")
    if filters.get("category"):
        clauses.append("COALESCE(NULLIF(l.category_override, ''), l.category) = ?")
        params.append(filters["category"])
    if filters.get("material"):
        clauses.append("l.materials LIKE ?")
        params.append(f"%{filters['material']}%")
    if filters.get("designer"):
        clauses.append("(l.designer LIKE ? OR l.maker LIKE ?)")
        params.extend([f"%{filters['designer']}%", f"%{filters['designer']}%"])
    if filters.get("ships_to_montreal"):
        clauses.append("l.ships_to_montreal = 1")
    availability = filters.get("availability")
    if availability and availability != "all":
        clauses.append(f"{EFFECTIVE_AVAILABILITY_SQL} = ?")
        params.append(availability)

    price_min = safe_float(filters.get("price_min", ""))
    if price_min is not None:
        clauses.append("l.price_value >= ?")
        params.append(price_min)

    price_max = safe_float(filters.get("price_max", ""))
    if price_max is not None:
        clauses.append("l.price_value <= ?")
        params.append(price_max)
    return clauses, params


def get_listing(db: sqlite3.Connection, listing_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT
            l.*,
            s.slug AS shop_slug,
            s.name AS shop_name,
            s.website AS shop_website,
            s.shipping_summary AS shop_shipping_summary,
            s.is_montreal_local
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE l.id = ?
        """,
        (listing_id,),
    ).fetchone()
    return annotate_listing_row(row) if row else None


def list_shops(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT
            s.*,
            SUM(
                CASE
                    WHEN l.is_active = 1 AND COALESCE(NULLIF(l.availability_override, ''), l.availability_status) != 'sold_out'
                    THEN 1 ELSE 0
                END
            ) AS active_listing_count,
            GROUP_CONCAT(DISTINCT COALESCE(NULLIF(l.category_override, ''), l.category)) AS categories_carried
        FROM shops s
        LEFT JOIN listings l ON l.source_shop_id = s.id
        WHERE s.active = 1
        GROUP BY s.id
        ORDER BY s.is_montreal_local DESC, s.name ASC
        """
    ).fetchall()
    return annotate_shop_rows(rows)


def get_shop(db: sqlite3.Connection, shop_id: int) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM shops WHERE id = ? AND active = 1", (shop_id,)).fetchone()
    return annotate_shop_row(row) if row else None


def get_shop_by_slug(db: sqlite3.Connection, slug: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM shops WHERE slug = ? AND active = 1", (slug,)).fetchone()
    return annotate_shop_row(row) if row else None


def list_filter_values(db: sqlite3.Connection, field: str) -> list[str]:
    if field not in ALLOWED_FILTER_FIELDS:
        raise ValueError(f"Unsupported filter field: {field}")
    if field == "designer":
        return list_designer_filter_values(db)
    rows = db.execute(
        f"""
        SELECT DISTINCT {field} AS value
        FROM listings
        WHERE {field} != ''
          AND is_active = 1
          AND COALESCE(NULLIF(availability_override, ''), availability_status) != 'removed'
        ORDER BY {field}
        """
    ).fetchall()
    values: list[str] = []
    for row in rows:
        for chunk in str(row["value"]).split(","):
            value = chunk.strip()
            if value and value not in values:
                values.append(value)
    return values[:30]


def list_location_filter_values(db: sqlite3.Connection) -> list[str]:
    rows = db.execute(
        """
        SELECT DISTINCT location_text AS value
        FROM listings
        WHERE location_text != ''
          AND is_active = 1
          AND COALESCE(NULLIF(availability_override, ''), availability_status) != 'removed'
        ORDER BY location_text
        """
    ).fetchall()
    return [str(row["value"]).strip() for row in rows if str(row["value"]).strip()]


def list_designer_filter_values(db: sqlite3.Connection) -> list[str]:
    rows = db.execute(
        """
        SELECT designer, maker
        FROM listings
        WHERE is_active = 1
          AND COALESCE(NULLIF(availability_override, ''), availability_status) != 'removed'
          AND (designer != '' OR maker != '')
        """
    ).fetchall()
    candidates: dict[str, dict[str, Any]] = {}
    for row in rows:
        for value in (row["designer"], row["maker"]):
            cleaned = clean_designer_filter_value(str(value or ""))
            if not cleaned:
                continue
            key = normalized_filter_key(cleaned)
            if not key:
                continue
            payload = candidates.setdefault(key, {"value": cleaned, "count": 0})
            payload["count"] += 1
            if len(cleaned) < len(payload["value"]):
                payload["value"] = cleaned

    minimum_count = 2 if len(candidates) > 30 else 1
    values = [payload for payload in candidates.values() if payload["count"] >= minimum_count]
    values.sort(key=lambda payload: (-payload["count"], normalized_filter_key(payload["value"])))
    return sorted(payload["value"] for payload in values[:24])


def clean_designer_filter_value(value: str) -> str:
    cleaned = html.unescape(value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—,")
    cleaned = re.sub(r"^design\s+", "", cleaned, flags=re.IGNORECASE)
    if not cleaned:
        return ""

    normalized = normalized_filter_key(cleaned)
    boilerplate = (
        "available",
        "based on",
        "checkout",
        "contactez nous",
        "current production",
        "details",
        "dimensions",
        "features",
        "final sale",
        "lead time",
        "les details",
        "materials",
        "more information",
        "on order",
        "policies",
        "shipping",
        "store policies",
    )
    if any(term in normalized for term in boilerplate):
        return ""
    if len(cleaned) > 60 or len(cleaned.split()) > 6:
        return ""
    return cleaned


def normalized_filter_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", html.unescape(value))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def toggle_favourite_listing(listing_id: int) -> None:
    listing_ids = favourite_listing_ids()
    if listing_id in listing_ids:
        listing_ids.remove(listing_id)
    else:
        listing_ids.add(listing_id)
    session["favourite_listing_ids"] = sorted(listing_ids)
    session.modified = True


def toggle_favourite_shop(shop_id: int) -> None:
    shop_ids = favourite_shop_ids()
    if shop_id in shop_ids:
        shop_ids.remove(shop_id)
    else:
        shop_ids.add(shop_id)
    session["favourite_shop_ids"] = sorted(shop_ids)
    session.modified = True


def list_favourite_listings(db: sqlite3.Connection) -> list[dict[str, Any]]:
    listing_ids = favourite_listing_session_list()
    if not listing_ids:
        return []
    placeholders = ",".join("?" for _ in listing_ids)
    rows = db.execute(
        f"""
        SELECT l.*, s.slug AS shop_slug, s.name AS shop_name, s.is_montreal_local
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE l.id IN ({placeholders})
        """,
        listing_ids,
    ).fetchall()
    ordered_rows = annotate_listing_rows(rows)
    positions = {int(listing_id): index for index, listing_id in enumerate(listing_ids)}
    ordered_rows.sort(key=lambda row: positions.get(int(row["id"]), 0))
    return ordered_rows


def list_favourite_shops(db: sqlite3.Connection) -> list[dict[str, Any]]:
    shop_ids = favourite_shop_session_list()
    if not shop_ids:
        return []
    placeholders = ",".join("?" for _ in shop_ids)
    rows = db.execute(
        f"""
        SELECT s.*
        FROM shops s
        WHERE s.id IN ({placeholders}) AND s.active = 1
        """,
        shop_ids,
    ).fetchall()
    ordered_rows = annotate_shop_rows(rows)
    positions = {int(shop_id): index for index, shop_id in enumerate(shop_ids)}
    ordered_rows.sort(key=lambda row: positions.get(int(row["id"]), 0))
    return ordered_rows


def favourite_counts() -> dict[str, int]:
    if not has_request_context():
        return {"listings": 0, "shops": 0}
    return {
        "listings": len(favourite_listing_session_list()),
        "shops": len(favourite_shop_session_list()),
    }


def admin_sources(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT
            s.*,
            (
                SELECT cr.ran_at
                FROM crawl_runs cr
                WHERE cr.shop_id = s.id
                ORDER BY cr.ran_at DESC, cr.id DESC
                LIMIT 1
            ) AS last_run_at,
            (
                SELECT cr.status
                FROM crawl_runs cr
                WHERE cr.shop_id = s.id
                ORDER BY cr.ran_at DESC, cr.id DESC
                LIMIT 1
            ) AS last_status,
            (
                SELECT cr.error_message
                FROM crawl_runs cr
                WHERE cr.shop_id = s.id
                ORDER BY cr.ran_at DESC, cr.id DESC
                LIMIT 1
            ) AS last_error,
            (
                SELECT rj.started_at
                FROM refresh_jobs rj
                WHERE rj.shop_id = s.id
                ORDER BY rj.started_at DESC, rj.id DESC
                LIMIT 1
            ) AS last_job_started_at,
            (
                SELECT rj.finished_at
                FROM refresh_jobs rj
                WHERE rj.shop_id = s.id
                ORDER BY rj.started_at DESC, rj.id DESC
                LIMIT 1
            ) AS last_job_finished_at,
            (
                SELECT rj.status
                FROM refresh_jobs rj
                WHERE rj.shop_id = s.id
                ORDER BY rj.started_at DESC, rj.id DESC
                LIMIT 1
            ) AS last_job_status,
            (
                SELECT rj.new_count
                FROM refresh_jobs rj
                WHERE rj.shop_id = s.id
                ORDER BY rj.started_at DESC, rj.id DESC
                LIMIT 1
            ) AS last_job_new_count,
            (
                SELECT rj.hidden_count
                FROM refresh_jobs rj
                WHERE rj.shop_id = s.id
                ORDER BY rj.started_at DESC, rj.id DESC
                LIMIT 1
            ) AS last_job_hidden_count,
            (
                SELECT COUNT(*)
                FROM listings l
                WHERE l.source_shop_id = s.id
                  AND l.is_active = 1
            ) AS active_listing_count
        FROM shops s
        WHERE s.active = 1
        ORDER BY s.crawl_priority ASC, s.name ASC
        """
    ).fetchall()


def list_failures(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT cf.*, s.name AS shop_name
        FROM crawl_failures cf
        JOIN shops s ON s.id = cf.shop_id
        ORDER BY cf.created_at DESC
        LIMIT 20
        """
    ).fetchall()


def update_listing_overrides(
    db: sqlite3.Connection,
    listing_id: int,
    category_override: str,
    availability_override: str,
    is_featured: int,
    manual_notes: str,
) -> None:
    db.execute(
        """
        UPDATE listings
        SET category_override = ?, availability_override = ?, is_featured = ?, manual_notes = ?
        WHERE id = ?
        """,
        (category_override, availability_override, is_featured, manual_notes, listing_id),
    )
    db.commit()


def find_duplicate_candidates(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT id, title, normalized_title, source_shop_id
        FROM listings
        WHERE is_active = 1
        ORDER BY normalized_title
        """
    ).fetchall()
    groups: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        for other in rows[idx + 1 : idx + 12]:
            if row["source_shop_id"] == other["source_shop_id"]:
                continue
            score = similarity_score(row["normalized_title"], other["normalized_title"])
            if score >= 0.72:
                groups.append(
                    {
                        "left": get_listing(db, row["id"]),
                        "right": get_listing(db, other["id"]),
                        "score": round(score, 2),
                    }
                )
                if len(groups) >= 12:
                    return groups
    return groups


def safe_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sanitize_availability(value: str) -> str:
    return value if value in ALLOWED_AVAILABILITY else "available"


def sanitize_sort(value: str) -> str:
    return value if value in ALLOWED_SORT else "curated"


def favourite_listing_session_list() -> list[int]:
    if not has_request_context():
        return []
    return [int(value) for value in session.get("favourite_listing_ids", [])]


def favourite_shop_session_list() -> list[int]:
    if not has_request_context():
        return []
    return [int(value) for value in session.get("favourite_shop_ids", [])]


def favourite_listing_ids() -> set[int]:
    return set(favourite_listing_session_list())


def favourite_shop_ids() -> set[int]:
    return set(favourite_shop_session_list())


def annotate_listing_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["is_favourited"] = int(payload["id"]) in favourite_listing_ids()
    return payload


def annotate_listing_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    favourites = favourite_listing_ids()
    return [{**dict(row), "is_favourited": int(row["id"]) in favourites} for row in rows]


def annotate_shop_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["is_favourited"] = int(payload["id"]) in favourite_shop_ids()
    return payload


def annotate_shop_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    favourites = favourite_shop_ids()
    return [{**dict(row), "is_favourited": int(row["id"]) in favourites} for row in rows]


def similarity_score(a: str, b: str) -> float:
    left = set(a.split())
    right = set(b.split())
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
