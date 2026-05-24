from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


def shop_address_lines(shop: dict[str, Any]) -> list[str]:
    street_address = str(shop.get("street_address") or "").strip()
    city = str(shop.get("city") or "").strip()
    province = str(shop.get("province") or "").strip()
    postal_code = str(shop.get("postal_code") or "").strip()
    country = str(shop.get("country") or "").strip()

    lines = []
    if street_address:
        lines.append(street_address)
    locality = " ".join(part for part in (city, province, postal_code) if part)
    if locality:
        lines.append(locality)
    if country:
        lines.append(country)
    return lines


def shop_directions_url(shop: dict[str, Any]) -> str:
    query = ", ".join(
        part
        for part in (
            str(shop.get("name") or "").strip(),
            str(shop.get("street_address") or "").strip(),
            str(shop.get("city") or "").strip(),
            str(shop.get("province") or "").strip(),
            str(shop.get("postal_code") or "").strip(),
        )
        if part
    )
    if not query:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def shop_apple_maps_url(shop: dict[str, Any]) -> str:
    query = ", ".join(
        part
        for part in (
            str(shop.get("name") or "").strip(),
            str(shop.get("street_address") or "").strip(),
            str(shop.get("city") or "").strip(),
            str(shop.get("province") or "").strip(),
            str(shop.get("postal_code") or "").strip(),
        )
        if part
    )
    if not query:
        return ""
    return f"https://maps.apple.com/?q={quote_plus(query)}"


def shop_has_map(shop: dict[str, Any]) -> bool:
    return bool(shop.get("street_address") and shop.get("latitude") and shop.get("longitude"))
