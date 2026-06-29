from __future__ import annotations

from urllib.parse import urlencode


def saved_search_query_string(filters: dict[str, str]) -> str:
    values = {
        key: value
        for key, value in filters.items()
        if value
        and not (key == "availability" and value == "available")
        and not (key == "sort" and value == "curated")
    }
    return urlencode(values)


def saved_search_name(filters: dict[str, str]) -> str:
    parts = []
    if filters.get("q"):
        parts.append(filters["q"])
    for key in ("shop", "category", "material", "designer", "location"):
        if filters.get(key):
            parts.append(filters[key])
    if filters.get("price_min") or filters.get("price_max"):
        parts.append(
            " ".join(
                value
                for value in (filters.get("price_min", ""), filters.get("price_max", ""))
                if value
            )
        )
    if filters.get("availability") and filters["availability"] != "available":
        parts.append(filters["availability"].replace("_", " "))
    return " / ".join(parts)[:120] or "Default browse"
