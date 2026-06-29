from __future__ import annotations

import re
from typing import Any

from .i18n import LAUNCH_CATEGORIES, category_label, shop_text
from .refresh import public_item_number

DEFAULT_PUBLIC_BASE_URL = "https://montrealmcm.ca"


def normalized_public_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    return cleaned or DEFAULT_PUBLIC_BASE_URL


def absolute_public_url(base_url: str, path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{normalized_public_base_url(base_url)}{clean_path}"


def category_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized


def category_from_slug(slug: str) -> str | None:
    categories = {category_slug(category): category for category in LAUNCH_CATEGORIES}
    return categories.get(slug)


def language_alternate_urls(base_url: str, path: str) -> dict[str, str]:
    return {
        "en": absolute_public_url(base_url, f"{path}?lang=en"),
        "fr": absolute_public_url(base_url, f"{path}?lang=fr"),
        "x-default": absolute_public_url(base_url, path),
    }


def base_structured_data(base_url: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Montreal MCM",
        "url": normalized_public_base_url(base_url),
        "potentialAction": {
            "@type": "SearchAction",
            "target": absolute_public_url(base_url, "/?q={search_term_string}"),
            "query-input": "required name=search_term_string",
        },
    }


def collection_structured_data(
    base_url: str, path: str, name: str, description: str
) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": name,
        "description": description,
        "url": absolute_public_url(base_url, path),
        "isPartOf": {"@type": "WebSite", "name": "Montreal MCM"},
    }


def shop_structured_data(base_url: str, shop: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Store",
        "name": shop["name"],
        "description": shop_text(shop, "description"),
        "url": absolute_public_url(base_url, f"/shops/{shop['slug']}"),
        "sameAs": shop["website"],
        "address": {
            "@type": "PostalAddress",
            "addressLocality": shop["city"],
            "addressRegion": shop["province"],
            "addressCountry": shop["country"],
        },
    }
    if shop.get("street_address"):
        payload["address"]["streetAddress"] = shop["street_address"]
        payload["address"]["postalCode"] = shop["postal_code"]
    if shop.get("latitude") and shop.get("longitude"):
        payload["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": shop["latitude"],
            "longitude": shop["longitude"],
        }
    return payload


def listing_structured_data(
    base_url: str,
    listing: dict[str, Any],
    shop: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": listing["title"],
        "description": listing.get("source_description") or listing["title"],
        "url": absolute_public_url(base_url, f"/listing/{public_item_number(int(listing['id']))}"),
        "image": listing["primary_image_url"] or None,
        "brand": {"@type": "Brand", "name": listing["shop_name"]},
        "category": category_label(listing["category_override"] or listing["category"]),
        "offers": {
            "@type": "Offer",
            "url": listing["source_listing_url"],
            "priceCurrency": listing["currency"] or "CAD",
            "availability": "https://schema.org/InStock",
            "seller": {"@type": "Store", "name": shop["name"]},
        },
    }
    if listing["price_value"] is not None:
        payload["offers"]["price"] = float(listing["price_value"])
    availability = listing["availability_override"] or listing["availability_status"]
    if availability == "sold_out":
        payload["offers"]["availability"] = "https://schema.org/OutOfStock"
    return {key: value for key, value in payload.items() if value is not None}
