from __future__ import annotations

import html
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from typing import Any

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
    alias_candidates: list[str] = [canonical, *(aliases or [])]
    for alias in sorted(set(alias_candidates), key=normalized_filter_key):
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
