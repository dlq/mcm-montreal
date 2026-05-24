from __future__ import annotations

from typing import Any

SHOP_MAP_LOCATIONS = {
    ("montreal", "qc"): {
        "x": 133,
        "y": 73,
        "label": "Montreal",
    },
    ("west brome", "qc"): {
        "x": 168,
        "y": 88,
        "label": "West Brome",
    },
    ("ottawa", "on"): {
        "x": 63,
        "y": 55,
        "label": "Ottawa",
    },
    ("ingleside", "on"): {
        "x": 88,
        "y": 66,
        "label": "Ingleside",
    },
}


def shop_map_data(shop: dict[str, Any]) -> dict[str, Any]:
    key = (
        str(shop.get("city", "")).strip().lower(),
        str(shop.get("province", "")).strip().lower(),
    )
    location = SHOP_MAP_LOCATIONS.get(key)
    if not location:
        return {
            "x": 133,
            "y": 73,
            "label": str(shop.get("city") or shop.get("name") or ""),
            "is_exact": False,
        }
    return {**location, "is_exact": True}
