from __future__ import annotations

import html
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from typing import Any

from flask import g, has_request_context, session

from .identity import current_owner_key

ALLOWED_FILTER_FIELDS = {"category", "materials", "designer"}
ALLOWED_AVAILABILITY = {"available", "sold_out", "all"}
ALLOWED_SORT = {"curated", "newest", "recent_check", "price_low", "price_high", "recent_source"}
EFFECTIVE_AVAILABILITY_SQL = "COALESCE(NULLIF(l.availability_override, ''), l.availability_status)"
EFFECTIVE_CATEGORY_SQL = "COALESCE(NULLIF(l.category_override, ''), l.category)"
CURATED_SOURCE_ORDER_SQL = f"""
CASE
    WHEN s.is_montreal_local = 1 THEN 0
    WHEN s.slug = 'mostly-danish' AND {EFFECTIVE_CATEGORY_SQL} = 'dining chairs' THEN 3
    WHEN s.slug = 'mostly-danish' THEN 2
    ELSE 1
END ASC,
l.first_seen_at DESC
"""
SEARCH_FIELDS = (
    "l.title",
    "l.designer",
    "l.maker",
    "l.materials",
    EFFECTIVE_CATEGORY_SQL,
    "l.source_description",
)
SEARCH_SCORE_FIELDS = (
    ("l.title", 16),
    ("l.designer", 12),
    ("l.maker", 12),
    (EFFECTIVE_CATEGORY_SQL, 10),
    ("l.materials", 8),
    ("l.source_description", 3),
)
SEARCH_SYNONYM_GROUPS = (
    ("teak", "teck"),
    ("rosewood", "palissandre"),
    ("walnut", "noyer"),
    ("sideboard", "sideboards", "buffet", "buffets", "credenza", "credenzas", "enfilade"),
    ("dresser", "dressers", "commode", "commodes"),
    ("chair", "chairs", "chaise", "chaises", "fauteuil", "fauteuils"),
    ("lamp", "lamps", "lampe", "lampes"),
    ("table", "tables"),
    ("dining", "diner", "manger"),
    ("storage", "rangement"),
    ("shelf", "shelves", "etagere", "etageres", "étagère", "étagères"),
)


def normalize_search_token(value: str) -> str:
    stripped = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.lower().strip())
        if not unicodedata.combining(char)
    )
    return stripped.replace("'", "")


SEARCH_SYNONYMS = {
    normalize_search_token(alias): {
        normalize_search_token(candidate)
        for candidate in group
        if normalize_search_token(candidate)
    }
    for group in SEARCH_SYNONYM_GROUPS
    for alias in group
}
DESIGNER_FILTER_ALIASES = {
    "arne hovmand olsen": "Arne Hovmand-Olsen",
    "axel christiansen": "Axel Christensen",
    "borge mogensen": "Børge Mogensen",
    "charles and ray eames": "Charles & Ray Eames",
    "design hans j wegner": "Hans J. Wegner",
    "grethe jalk": "Grete Jalk",
    "hans j wegner of denmark": "Hans J. Wegner",
    "hans wegner": "Hans J. Wegner",
    "henning kjaernulf": "Henning Kjærnulf",
    "henning norgaard": "Henning Nørgaard",
    "ib kofod larsen": "Ib Kofod-Larsen",
    "ib kofodlarsen": "Ib Kofod-Larsen",
    "lella and massimo vignelli": "Lella & Massimo Vignelli",
    "massimo and lella vignelli": "Lella & Massimo Vignelli",
    "massimo lella vignelli": "Lella & Massimo Vignelli",
    "michel ducaroy": "Michel Ducaroy",
    "niels koefoed": "Niels Koefoed",
    "neils koefoed": "Niels Koefoed",
    "orla molgaard nielsen": "Orla Mølgaard-Nielsen",
    "orla molgaardnielsen": "Orla Mølgaard-Nielsen",
    "orla mølgaard nielsen": "Orla Mølgaard-Nielsen",
    "poul m volther": "Poul Volther",
}
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
    clauses, params = listing_query_parts(db, filters, include_inactive)
    sort = sanitize_sort(filters.get("sort", "curated"))
    order_by = {
        "curated": CURATED_SOURCE_ORDER_SQL,
        "newest": "l.first_seen_at DESC",
        "recent_check": "l.last_checked_at DESC",
        "price_low": "CASE WHEN l.price_value IS NULL THEN 1 ELSE 0 END, l.price_value ASC",
        "price_high": "CASE WHEN l.price_value IS NULL THEN 1 ELSE 0 END, l.price_value DESC",
        "recent_source": "l.last_seen_at DESC",
    }[sort]
    order_params: list[Any] = []
    if filters.get("q") and sort == "curated":
        score_sql, order_params = search_score_expression(filters["q"])
        if score_sql:
            order_by = f"{score_sql} DESC, {order_by}"
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
            s.wordmark_text AS shop_wordmark_text,
            s.wordmark_style AS shop_wordmark_style,
            s.is_montreal_local
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE {" AND ".join(clauses)}
        ORDER BY {order_by}
        {page_clause}
        """,
        [*params, *order_params, *page_params],
    ).fetchall()
    return annotate_listing_rows(rows)


def count_listings(
    db: sqlite3.Connection,
    filters: dict[str, str],
    include_inactive: bool,
) -> int:
    clauses, params = listing_query_parts(db, filters, include_inactive)
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
    db: sqlite3.Connection,
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
        search_clause, search_params = search_query_clause(db, filters["q"])
        if search_clause:
            clauses.append(search_clause)
            params.extend(search_params)
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
        aliases = design_entity_filter_query_values(db, filters["designer"])
        if not aliases:
            clauses.append("0=1")
            return clauses, params
        designer_clauses = []
        for alias in aliases:
            designer_clauses.append("(l.designer LIKE ? OR l.maker LIKE ?)")
            params.extend([f"%{alias}%", f"%{alias}%"])
        clauses.append(f"({' OR '.join(designer_clauses)})")
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


def search_query_clause(db: sqlite3.Connection, query: str) -> tuple[str, list[str]]:
    groups = search_term_groups(query)
    entity_aliases = design_entity_filter_query_values(db, query)
    if not groups and not entity_aliases:
        return "", []
    clauses = []
    params: list[str] = []
    if groups:
        group_clauses = []
        for group in groups:
            term_clauses = []
            for term in group:
                for field in SEARCH_FIELDS:
                    term_clauses.append(f"{field} LIKE ?")
                    params.append(f"%{term}%")
            group_clauses.append(f"({' OR '.join(term_clauses)})")
        clauses.append(f"({' AND '.join(group_clauses)})")
    if entity_aliases:
        entity_clauses = []
        for alias in entity_aliases:
            entity_clauses.append("(l.designer LIKE ? OR l.maker LIKE ?)")
            params.extend([f"%{alias}%", f"%{alias}%"])
        clauses.append(f"({' OR '.join(entity_clauses)})")
    return f"({' OR '.join(clauses)})", params


def search_term_groups(query: str) -> list[list[str]]:
    groups = []
    seen_tokens: set[str] = set()
    for raw_token in re.findall(r"[\wÀ-ÿ']+", query):
        token = normalize_search_token(raw_token)
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        terms = sorted(SEARCH_SYNONYMS.get(token, {token}))
        groups.append(terms)
    return groups


def search_score_expression(query: str) -> tuple[str, list[str]]:
    groups = search_term_groups(query)
    if not groups:
        return "", []
    score_parts = []
    params: list[str] = []
    for group in groups:
        for field, weight in SEARCH_SCORE_FIELDS:
            matches = []
            for term in group:
                matches.append(f"{field} LIKE ?")
                params.append(f"%{term}%")
            score_parts.append(f"CASE WHEN {' OR '.join(matches)} THEN {weight} ELSE 0 END")
    return " + ".join(score_parts), params


def get_listing(db: sqlite3.Connection, listing_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT
            l.*,
            s.slug AS shop_slug,
            s.name AS shop_name,
            s.wordmark_text AS shop_wordmark_text,
            s.wordmark_style AS shop_wordmark_style,
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


def list_listing_price_events(db: sqlite3.Connection, listing_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT *
        FROM listing_price_events
        WHERE listing_id = ?
        ORDER BY observed_at DESC, id DESC
        LIMIT 12
        """,
        (listing_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_listing_availability_events(
    db: sqlite3.Connection, listing_id: int
) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT *
        FROM listing_availability_events
        WHERE listing_id = ?
        ORDER BY observed_at DESC, id DESC
        LIMIT 12
        """,
        (listing_id,),
    ).fetchall()
    return [dict(row) for row in rows]


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


def list_sitemap_listings(db: sqlite3.Connection, *, limit: int = 5000) -> list[dict[str, Any]]:
    rows = db.execute(
        f"""
        SELECT
            l.id,
            l.last_checked_at,
            l.last_seen_at,
            l.first_seen_at
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE s.active = 1
          AND l.is_active = 1
          AND {EFFECTIVE_AVAILABILITY_SQL} != 'removed'
        ORDER BY l.last_checked_at DESC, l.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


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
    alias_map = design_entity_alias_map(db)
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
            cleaned = alias_map.get(key, cleaned)
            key = normalized_filter_key(cleaned)
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
        "frais s appliques",
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
    if normalized.endswith("contactez nous") or " contactez nous" in normalized:
        return ""
    if normalized in {"canada", "montreal", "ottawa"}:
        return ""
    if re.search(r"\b(40s|50s|60s|70s|80s|90s|19\d0s|20\d0s)\b", normalized):
        return ""
    if len(cleaned) > 60 or len(cleaned.split()) > 6:
        return ""
    return DESIGNER_FILTER_ALIASES.get(normalized, cleaned)


def designer_filter_query_values(value: str) -> list[str]:
    cleaned = clean_designer_filter_value(value)
    if not cleaned:
        return []
    normalized = normalized_filter_key(cleaned)
    values = {cleaned}
    for alias_key, canonical in DESIGNER_FILTER_ALIASES.items():
        if normalized_filter_key(canonical) == normalized or alias_key == normalized:
            values.add(canonical)
            values.add(alias_key)
    return sorted(values, key=lambda candidate: (normalized_filter_key(candidate), candidate))


def design_entity_filter_query_values(db: sqlite3.Connection, value: str) -> list[str]:
    values = set(designer_filter_query_values(value))
    normalized = normalized_filter_key(value)
    if normalized:
        rows = db.execute(
            """
            SELECT de.canonical_name, dea.alias
            FROM design_entities de
            JOIN design_entity_aliases dea ON dea.entity_id = de.id
            WHERE de.normalized_name = ?
               OR dea.normalized_alias = ?
            """,
            (normalized, normalized),
        ).fetchall()
        for row in rows:
            values.add(str(row["canonical_name"]))
            values.add(str(row["alias"]))
        if rows:
            entity_names = {str(row["canonical_name"]) for row in rows}
            for entity_name in entity_names:
                for alias in design_entity_aliases_for_name(db, entity_name):
                    values.add(alias)
    return sorted(
        {
            value
            for value in values
            if clean_designer_filter_value(value) or normalized_filter_key(value)
        },
        key=lambda candidate: (normalized_filter_key(candidate), candidate),
    )


def design_entity_aliases_for_name(db: sqlite3.Connection, canonical_name: str) -> list[str]:
    normalized = normalized_filter_key(canonical_name)
    rows = db.execute(
        """
        SELECT dea.alias
        FROM design_entities de
        JOIN design_entity_aliases dea ON dea.entity_id = de.id
        WHERE de.normalized_name = ?
        ORDER BY dea.alias
        """,
        (normalized,),
    ).fetchall()
    return [str(row["alias"]) for row in rows]


def design_entity_alias_map(db: sqlite3.Connection) -> dict[str, str]:
    rows = db.execute(
        """
        SELECT dea.normalized_alias, de.canonical_name
        FROM design_entity_aliases dea
        JOIN design_entities de ON de.id = dea.entity_id
        WHERE de.review_status = 'approved'
        """
    ).fetchall()
    return {str(row["normalized_alias"]): str(row["canonical_name"]) for row in rows}


def create_design_entity(
    db: sqlite3.Connection,
    *,
    canonical_name: str,
    entity_type: str = "creator",
    aliases: list[str] | None = None,
    notes: str = "",
) -> int:
    canonical = canonical_name.strip()
    if not canonical:
        raise ValueError("canonical_name is required")
    normalized = normalized_filter_key(canonical)
    now = datetime.now(UTC).isoformat()
    clean_type = (
        entity_type if entity_type in {"creator", "designer", "maker", "brand"} else "creator"
    )
    db.execute(
        """
        INSERT INTO design_entities (
            canonical_name, normalized_name, entity_type, review_status, notes, created_at, updated_at
        ) VALUES (?, ?, ?, 'approved', ?, ?, ?)
        ON CONFLICT(normalized_name) DO UPDATE SET
            canonical_name = excluded.canonical_name,
            entity_type = excluded.entity_type,
            notes = excluded.notes,
            updated_at = excluded.updated_at
        """,
        (canonical, normalized, clean_type, notes.strip(), now, now),
    )
    row = db.execute(
        "SELECT id FROM design_entities WHERE normalized_name = ?",
        (normalized,),
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to create design entity")
    entity_id = int(row["id"])
    for alias in sorted({canonical, *(aliases or [])}, key=normalized_filter_key):
        alias_text = alias.strip()
        alias_key = normalized_filter_key(alias_text)
        if not alias_text or not alias_key:
            continue
        db.execute(
            """
            INSERT INTO design_entity_aliases (
                entity_id, alias, normalized_alias, source, created_at
            ) VALUES (?, ?, ?, 'admin', ?)
            ON CONFLICT(normalized_alias) DO UPDATE SET
                entity_id = excluded.entity_id,
                alias = excluded.alias,
                source = excluded.source
            """,
            (entity_id, alias_text, alias_key, now),
        )
    db.commit()
    return entity_id


def add_listing_design_entity_evidence(
    db: sqlite3.Connection,
    *,
    listing_id: int,
    entity_id: int,
    evidence_role: str,
    source_text: str,
) -> None:
    clean_source = source_text.strip()
    if not clean_source:
        return
    role = evidence_role if evidence_role in {"designer", "maker", "creator"} else "creator"
    now = datetime.now(UTC).isoformat()
    db.execute(
        """
        INSERT INTO listing_design_entity_evidence (
            listing_id, entity_id, evidence_role, source_text, normalized_source_text,
            confidence, review_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 1.0, 'approved', ?, ?)
        ON CONFLICT(listing_id, entity_id, evidence_role, normalized_source_text) DO UPDATE SET
            source_text = excluded.source_text,
            review_status = excluded.review_status,
            updated_at = excluded.updated_at
        """,
        (listing_id, entity_id, role, clean_source, normalized_filter_key(clean_source), now, now),
    )
    db.commit()


def review_design_entity_candidate(
    db: sqlite3.Connection,
    *,
    source_text: str,
    source_role: str,
    review_status: str,
    entity_id: int | None = None,
    notes: str = "",
) -> None:
    clean_text = source_text.strip()
    normalized = normalized_filter_key(clean_text)
    if not clean_text or not normalized:
        return
    clean_role = source_role if source_role in {"designer", "maker"} else "designer"
    clean_status = review_status if review_status in {"approved", "rejected"} else "rejected"
    now = datetime.now(UTC).isoformat()
    db.execute(
        """
        INSERT INTO design_entity_candidate_reviews (
            source_role, source_text, normalized_source_text, review_status, entity_id,
            notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_role, normalized_source_text) DO UPDATE SET
            source_text = excluded.source_text,
            review_status = excluded.review_status,
            entity_id = excluded.entity_id,
            notes = excluded.notes,
            updated_at = excluded.updated_at
        """,
        (
            clean_role,
            clean_text,
            normalized,
            clean_status,
            entity_id,
            notes.strip(),
            now,
            now,
        ),
    )
    db.commit()


def approve_design_entity_candidate(
    db: sqlite3.Connection,
    *,
    source_text: str,
    source_role: str,
    canonical_name: str,
    entity_type: str = "creator",
    aliases: list[str] | None = None,
    notes: str = "",
) -> tuple[int, int]:
    clean_text = source_text.strip()
    clean_role = source_role if source_role in {"designer", "maker"} else "designer"
    entity_aliases = [clean_text, *(aliases or [])]
    entity_id = create_design_entity(
        db,
        canonical_name=canonical_name,
        entity_type=entity_type,
        aliases=entity_aliases,
        notes=notes,
    )
    field = "designer" if clean_role == "designer" else "maker"
    rows = db.execute(
        f"""
        SELECT id
        FROM listings
        WHERE is_active = 1
          AND {field} = ?
        """,
        (clean_text,),
    ).fetchall()
    for row in rows:
        add_listing_design_entity_evidence(
            db,
            listing_id=int(row["id"]),
            entity_id=entity_id,
            evidence_role=clean_role,
            source_text=clean_text,
        )
    review_design_entity_candidate(
        db,
        source_text=clean_text,
        source_role=clean_role,
        review_status="approved",
        entity_id=entity_id,
        notes=notes,
    )
    return entity_id, len(rows)


def list_design_entity_candidates(
    db: sqlite3.Connection, *, limit: int = 20
) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT
            source_text,
            source_role,
            COUNT(*) AS listing_count
        FROM (
            SELECT designer AS source_text, 'designer' AS source_role
            FROM listings
            WHERE designer != ''
              AND is_active = 1
            UNION ALL
            SELECT maker AS source_text, 'maker' AS source_role
            FROM listings
            WHERE maker != ''
              AND is_active = 1
        )
        WHERE source_text != ''
        GROUP BY source_text, source_role
        ORDER BY listing_count DESC, source_text ASC
        LIMIT ?
        """,
        (limit * 4,),
    ).fetchall()
    candidates = []
    alias_map = design_entity_alias_map(db)
    reviewed_rows = db.execute(
        """
        SELECT source_role, normalized_source_text
        FROM design_entity_candidate_reviews
        WHERE review_status IN ('approved', 'rejected')
        """
    ).fetchall()
    reviewed = {
        (str(row["source_role"]), str(row["normalized_source_text"])) for row in reviewed_rows
    }
    for row in rows:
        source_text = str(row["source_text"])
        source_role = str(row["source_role"])
        normalized = normalized_filter_key(source_text)
        if normalized in alias_map:
            continue
        if (source_role, normalized) in reviewed:
            continue
        cleaned = clean_designer_filter_value(source_text)
        if not cleaned:
            continue
        candidates.append(
            {
                "source_text": source_text,
                "source_role": source_role,
                "listing_count": int(row["listing_count"]),
            }
        )
    return candidates[:limit]


def list_design_entities(
    db: sqlite3.Connection, *, query: str = "", limit: int = 100
) -> list[dict[str, Any]]:
    entity_rows = db.execute(
        """
        SELECT
            de.id,
            de.canonical_name,
            de.entity_type,
            de.review_status,
            de.notes,
            COUNT(DISTINCT ldee.id) AS evidence_count,
            COUNT(DISTINCT ldee.listing_id) AS listing_count
        FROM design_entities de
        LEFT JOIN listing_design_entity_evidence ldee ON ldee.entity_id = de.id
        GROUP BY de.id
        ORDER BY de.canonical_name
        """
    ).fetchall()
    alias_rows = db.execute(
        """
        SELECT entity_id, alias
        FROM design_entity_aliases
        ORDER BY alias
        """
    ).fetchall()
    aliases_by_entity: dict[int, list[str]] = {}
    for row in alias_rows:
        aliases_by_entity.setdefault(int(row["entity_id"]), []).append(str(row["alias"]))

    query_key = normalized_filter_key(query)
    entities = []
    for row in entity_rows:
        entity_id = int(row["id"])
        aliases = aliases_by_entity.get(entity_id, [])
        searchable = [str(row["canonical_name"]), *aliases]
        if query_key and not any(query_key in normalized_filter_key(value) for value in searchable):
            continue
        entities.append(
            {
                "id": entity_id,
                "canonical_name": str(row["canonical_name"]),
                "entity_type": str(row["entity_type"]),
                "review_status": str(row["review_status"]),
                "notes": str(row["notes"]),
                "aliases": aliases,
                "evidence_count": int(row["evidence_count"]),
                "listing_count": int(row["listing_count"]),
            }
        )
    return entities[:limit]


def normalized_filter_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", html.unescape(value))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def toggle_favourite_listing(db: sqlite3.Connection, listing_id: int) -> None:
    owner_key = current_owner_key()
    if not owner_key:
        listing_ids = favourite_listing_ids()
        if listing_id in listing_ids:
            listing_ids.remove(listing_id)
        else:
            listing_ids.add(listing_id)
        session["favourite_listing_ids"] = sorted(listing_ids)
        session.modified = True
        return
    if favourite_listing_exists(db, owner_key, listing_id):
        db.execute(
            "DELETE FROM anonymous_favourite_listings WHERE owner_key = ? AND listing_id = ?",
            (owner_key, listing_id),
        )
    else:
        db.execute(
            """
            INSERT OR IGNORE INTO anonymous_favourite_listings (owner_key, listing_id, created_at)
            VALUES (?, ?, ?)
            """,
            (owner_key, listing_id, datetime.now(UTC).isoformat()),
        )
    db.commit()


def toggle_favourite_shop(db: sqlite3.Connection, shop_id: int) -> None:
    owner_key = current_owner_key()
    if not owner_key:
        shop_ids = favourite_shop_ids()
        if shop_id in shop_ids:
            shop_ids.remove(shop_id)
        else:
            shop_ids.add(shop_id)
        session["favourite_shop_ids"] = sorted(shop_ids)
        session.modified = True
        return
    if favourite_shop_exists(db, owner_key, shop_id):
        db.execute(
            "DELETE FROM anonymous_favourite_shops WHERE owner_key = ? AND shop_id = ?",
            (owner_key, shop_id),
        )
    else:
        db.execute(
            """
            INSERT OR IGNORE INTO anonymous_favourite_shops (owner_key, shop_id, created_at)
            VALUES (?, ?, ?)
            """,
            (owner_key, shop_id, datetime.now(UTC).isoformat()),
        )
    db.commit()


def list_favourite_listings(db: sqlite3.Connection) -> list[dict[str, Any]]:
    listing_ids = favourite_listing_list(db)
    if not listing_ids:
        return []
    placeholders = ",".join("?" for _ in listing_ids)
    rows = db.execute(
        f"""
        SELECT
            l.*,
            s.slug AS shop_slug,
            s.name AS shop_name,
            s.wordmark_text AS shop_wordmark_text,
            s.wordmark_style AS shop_wordmark_style,
            s.is_montreal_local
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
    shop_ids = favourite_shop_list(db)
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
        return {"listings": 0, "shops": 0, "searches": 0, "total": 0}
    db = getattr(g, "db", None)
    if db is not None and current_owner_key():
        counts = {
            "listings": len(favourite_listing_list(db)),
            "shops": len(favourite_shop_list(db)),
            "searches": db.execute(
                """
                SELECT COUNT(*) AS count
                FROM anonymous_saved_searches
                WHERE owner_key = ?
                """,
                (current_owner_key(),),
            ).fetchone()["count"],
        }
        counts["total"] = counts["listings"] + counts["shops"] + counts["searches"]
        return counts
    counts = {
        "listings": len(favourite_listing_session_list()),
        "shops": len(favourite_shop_session_list()),
        "searches": 0,
    }
    counts["total"] = counts["listings"] + counts["shops"]
    return counts


def save_search(db: sqlite3.Connection, name: str, query_string: str) -> None:
    owner_key = current_owner_key()
    if not owner_key or not query_string:
        return
    now = datetime.now(UTC).isoformat()
    db.execute(
        """
        INSERT INTO anonymous_saved_searches (
            owner_key, name, query_string, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(owner_key, query_string) DO UPDATE SET
            name = excluded.name,
            updated_at = excluded.updated_at
        """,
        (owner_key, name, query_string, now, now),
    )
    db.commit()


def delete_saved_search(db: sqlite3.Connection, saved_search_id: int) -> None:
    owner_key = current_owner_key()
    if not owner_key:
        return
    db.execute(
        "DELETE FROM anonymous_saved_searches WHERE owner_key = ? AND id = ?",
        (owner_key, saved_search_id),
    )
    db.commit()


def list_saved_searches(db: sqlite3.Connection) -> list[dict[str, Any]]:
    owner_key = current_owner_key()
    if not owner_key:
        return []
    rows = db.execute(
        """
        SELECT id, name, query_string, created_at, updated_at
        FROM anonymous_saved_searches
        WHERE owner_key = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (owner_key,),
    ).fetchall()
    return [dict(row) for row in rows]


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
                SELECT rj.chunk_index
                FROM refresh_jobs rj
                WHERE rj.shop_id = s.id
                ORDER BY rj.started_at DESC, rj.id DESC
                LIMIT 1
            ) AS last_job_chunk_index,
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
    db = getattr(g, "db", None) if has_request_context() else None
    if db is not None and current_owner_key():
        return set(favourite_listing_list(db))
    return set(favourite_listing_session_list())


def favourite_shop_ids() -> set[int]:
    db = getattr(g, "db", None) if has_request_context() else None
    if db is not None and current_owner_key():
        return set(favourite_shop_list(db))
    return set(favourite_shop_session_list())


def favourite_listing_list(db: sqlite3.Connection) -> list[int]:
    owner_key = current_owner_key()
    if not owner_key:
        return favourite_listing_session_list()
    rows = db.execute(
        """
        SELECT listing_id
        FROM anonymous_favourite_listings
        WHERE owner_key = ?
        ORDER BY created_at ASC, listing_id ASC
        """,
        (owner_key,),
    ).fetchall()
    return [int(row["listing_id"]) for row in rows]


def favourite_shop_list(db: sqlite3.Connection) -> list[int]:
    owner_key = current_owner_key()
    if not owner_key:
        return favourite_shop_session_list()
    rows = db.execute(
        """
        SELECT shop_id
        FROM anonymous_favourite_shops
        WHERE owner_key = ?
        ORDER BY created_at ASC, shop_id ASC
        """,
        (owner_key,),
    ).fetchall()
    return [int(row["shop_id"]) for row in rows]


def favourite_listing_exists(db: sqlite3.Connection, owner_key: str, listing_id: int) -> bool:
    row = db.execute(
        """
        SELECT 1
        FROM anonymous_favourite_listings
        WHERE owner_key = ? AND listing_id = ?
        """,
        (owner_key, listing_id),
    ).fetchone()
    return row is not None


def favourite_shop_exists(db: sqlite3.Connection, owner_key: str, shop_id: int) -> bool:
    row = db.execute(
        """
        SELECT 1
        FROM anonymous_favourite_shops
        WHERE owner_key = ? AND shop_id = ?
        """,
        (owner_key, shop_id),
    ).fetchone()
    return row is not None


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
