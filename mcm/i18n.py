from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from flask import g, request, session

from .locales import TRANSLATIONS_EN, TRANSLATIONS_FR

SUPPORTED_LANGS = {"en", "fr"}

TRANSLATIONS: dict[str, dict[str, str]] = {"en": TRANSLATIONS_EN, "fr": TRANSLATIONS_FR}

SHOP_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "morceau": {
        "fr": {
            "shipping_summary": "Livraison internationale offerte pour tous les articles.",
            "notes": "Collection vintage solide de style Shopify.",
            "description": "Boutique montréalaise de design et de vintage avec une forte sélection de mobilier MCM.",
            "style_focus": "Vintage, scandinave, italien, design de collection.",
        }
    },
    "showroom-montreal": {
        "fr": {
            "shipping_summary": "Source locale montréalaise; certains articles demandent un contact direct pour le prix ou la livraison.",
            "notes": "Page Wix de nouveautés avec annonces textuelles détaillées.",
            "description": "Spécialiste montréalais du MCM local axé sur le mobilier moderne scandinave et canadien restauré.",
            "style_focus": "Scandinave, danois, vintage restauré, teck et palissandre.",
        }
    },
    "montreal-moderne": {
        "fr": {
            "shipping_summary": "Source locale montréalaise avec états vendu/disponible visibles sur la page.",
            "notes": "Page Wix de nouveautés avec prix clairs ou mention vendu.",
            "description": "Spécialiste montréalais du mobilier scandinave et MCM établi depuis 2007.",
            "style_focus": "Confort scandinave, mobilier en teck, pièces épurées d’inspiration danoise.",
        }
    },
    "le-centerpiece": {
        "fr": {
            "shipping_summary": "Expédition de Montréal vers le monde; les pièces surdimensionnées peuvent nécessiter une soumission de transport.",
            "notes": "Inventaire vintage haut de gamme avec livraison sur soumission pour les grosses pièces.",
            "description": "Galerie de design montréalaise haut de gamme avec mobilier de collection et objets décoratifs.",
            "style_focus": "Design de collection, mobilier vintage haut de gamme, modernisme européen.",
        }
    },
}

LAUNCH_CATEGORIES = [
    "sideboards / credenzas",
    "dressers / commodes",
    "dining tables",
    "dining chairs",
    "lounge chairs",
    "sofas",
    "coffee tables",
    "desks",
    "bookshelves / wall units",
    "nightstands",
    "beds / bedroom storage",
    "lighting",
    "furniture",
]

MATERIAL_LABELS = {
    "teak": "material.teak",
    "rosewood": "material.rosewood",
    "walnut": "material.walnut",
    "cherry wood": "material.cherry_wood",
    "wood": "material.wood",
    "glass": "material.glass",
    "chrome": "material.chrome",
    "aluminum": "material.aluminum",
    "leather": "material.leather",
    "metal": "material.metal",
    "upholstery": "material.upholstery",
    "wool": "material.wool",
    "steel": "material.steel",
    "ceramic": "material.ceramic",
    "sherpa": "material.sherpa",
}

CONDITION_LABELS = {
    "Restored": "condition.restored",
    "Reupholstered": "condition.reupholstered",
    "Refinished": "condition.refinished",
}

MONTH_NAMES = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "fr": [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ],
}


def normalize_lang(value: str | None) -> str:
    if not value:
        return "en"
    return value if value in SUPPORTED_LANGS else "en"


def resolved_language() -> str:
    requested = request.args.get("lang")
    if requested:
        session["lang"] = normalize_lang(requested)
    return normalize_lang(session.get("lang"))


def translator_for(lang: str) -> Callable[[str], str]:
    def _translate(key: str, **kwargs: Any) -> str:
        return translate(key, lang=lang, **kwargs)

    return _translate


def translate(key: str, lang: str | None = None, **kwargs: Any) -> str:
    active_lang = normalize_lang(lang or getattr(g, "lang", None))
    template = TRANSLATIONS.get(active_lang, {}).get(key) or TRANSLATIONS["en"].get(key) or key
    return template.format(**kwargs) if kwargs else template


def freshness_label(iso_value: str) -> str:
    checked = datetime.fromisoformat(iso_value)
    age = datetime.now(UTC) - checked
    if age <= timedelta(days=1):
        return translate("freshness.today")
    if age <= timedelta(days=7):
        return translate("freshness.week")
    return translate("freshness.stale")


def date_text(iso_value: str) -> str:
    value = datetime.fromisoformat(iso_value)
    lang = normalize_lang(getattr(g, "lang", None))
    month = MONTH_NAMES[lang][value.month - 1]
    if lang == "fr":
        return f"{value.day} {month} {value.year}"
    return f"{month} {value.day}, {value.year}"


def listing_count_text(count: int) -> str:
    key = "listing.count_one" if count == 1 else "listing.count_other"
    return translate(key, count=count)


def status_label(value: str | None) -> str:
    if not value:
        return translate("status.unknown")
    return (
        TRANSLATIONS.get(normalize_lang(getattr(g, "lang", None)), {}).get(f"status.{value}")
        or TRANSLATIONS["en"].get(f"status.{value}")
        or value.replace("_", " ")
    )


def category_label(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip()
    return (
        TRANSLATIONS.get(normalize_lang(getattr(g, "lang", None)), {}).get(f"category.{normalized}")
        or normalized
    )


def category_list_text(value: str | None) -> str:
    categories = []
    for chunk in (value or "").split(","):
        label = category_label(chunk)
        if label and label not in categories:
            categories.append(label)
    return ", ".join(categories)


def material_label(value: str | None) -> str:
    if not value:
        return ""
    pieces = [piece.strip() for piece in value.split(",")]
    labels = []
    for piece in pieces:
        key = MATERIAL_LABELS.get(piece.lower())
        labels.append(translate(key) if key else piece)
    return ", ".join(label for label in labels if label)


def era_label(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip()
    match = re.fullmatch(r"((?:19|20)\d0)s", normalized)
    if not match:
        return normalized
    return translate("era.decade", decade=match.group(1))


def condition_label(value: str | None) -> str:
    if not value:
        return ""
    pieces = [piece.strip() for piece in value.split(",")]
    labels = []
    for piece in pieces:
        key = CONDITION_LABELS.get(piece)
        labels.append(translate(key) if key else piece)
    return ", ".join(label for label in labels if label)


def price_text(listing: sqlite3.Row | dict[str, Any]) -> str:
    price_value = (
        listing["price_value"] if isinstance(listing, sqlite3.Row) else listing.get("price_value")
    )
    raw = listing["price_raw"] if isinstance(listing, sqlite3.Row) else listing.get("price_raw", "")
    currency = (
        listing["currency"] if isinstance(listing, sqlite3.Row) else listing.get("currency", "CAD")
    )
    if price_value is None:
        normalized_raw = (raw or "").lower()
        if "rupture de stock" in normalized_raw or "sold out" in normalized_raw:
            return status_label("sold_out")
        if "contact" in normalized_raw:
            return translate("listing.quote_required")
        return raw or translate("listing.quote_required")

    amount = float(price_value)
    set_suffix = price_set_suffix(raw)
    if normalize_lang(getattr(g, "lang", None)) == "fr":
        formatted_amount = f"{amount:,.0f}".replace(",", " ")
        currency_label = "$ CA" if currency == "CAD" else currency
        return f"{formatted_amount} {currency_label}{set_suffix}"
    currency_prefix = "$" if currency == "CAD" else ""
    currency_suffix = " CAD" if currency == "CAD" else f" {currency}"
    return f"{currency_prefix}{amount:,.0f}{currency_suffix}{set_suffix}"


def price_set_suffix(raw: str | None) -> str:
    numeric_match = re.search(r"/\s*([0-9]+)\b", raw or "")
    if numeric_match:
        return translate("price.for_set", count=numeric_match.group(1))
    raw_value = raw or ""
    if re.search(r"/\s*(paire|pair)\b", raw_value, flags=re.IGNORECASE):
        return translate("price.for_pair")
    if re.search(r"(?:^|[\s/])(ch\.?|chaque|each)(?:\s|$)", raw_value, flags=re.IGNORECASE):
        return translate("price.each")
    if re.search(r"/\s*(l['’]ens\.?|ensemble|set)\b", raw_value, flags=re.IGNORECASE):
        return translate("price.for_whole_set")
    return ""


def filter_summary_parts(filters: dict[str, str]) -> list[str]:
    t = translator_for(normalize_lang(getattr(g, "lang", None)))
    parts = []
    label_keys = {
        "q": "filters.search",
        "shop": "filters.shop",
        "category": "filters.category",
        "material": "filters.material",
        "designer": "filters.designer",
        "location": "filters.location",
        "price_min": "filters.min_price",
        "price_max": "filters.max_price",
    }
    for key, label_key in label_keys.items():
        if filters.get(key):
            value = filters[key]
            if key == "category":
                value = category_label(value)
            elif key == "material":
                value = material_label(value)
            parts.append(f"{t(label_key)}: {value}")
    availability = filters.get("availability", "available")
    if availability != "available":
        parts.append(f"{t('filters.availability')}: {status_label(availability)}")
    sort = filters.get("sort", "newest")
    if sort != "newest":
        sort_labels = {
            "recent_check": "filters.recent_check",
            "price_low": "filters.price_low",
            "price_high": "filters.price_high",
            "recent_source": "filters.recent_source",
        }
        parts.append(f"{t('filters.sort')}: {t(sort_labels[sort])}")
    return parts


def filter_summary(filters: dict[str, str]) -> str:
    return " · ".join(filter_summary_parts(filters))


def shipping_note_text(
    listing: sqlite3.Row | dict[str, Any], shop: sqlite3.Row | dict[str, Any]
) -> str:
    note = (
        listing["shipping_note"]
        if isinstance(listing, sqlite3.Row)
        else listing.get("shipping_note", "")
    )
    shop_summary = (
        shop["shipping_summary"]
        if isinstance(shop, sqlite3.Row)
        else shop.get("shipping_summary", "")
    )
    if not note or note == shop_summary:
        return shop_text(shop, "shipping_summary")
    return note


def shop_text(shop: sqlite3.Row | dict[str, Any], field: str) -> str:
    slug = shop["slug"] if isinstance(shop, sqlite3.Row) else shop.get("slug", "")
    lang = normalize_lang(getattr(g, "lang", None))
    translated = SHOP_TRANSLATIONS.get(slug, {}).get(lang, {}).get(field)
    if translated:
        return translated
    return shop[field] if isinstance(shop, sqlite3.Row) else shop.get(field, "")


def language_url(lang_code: str) -> str:
    params = request.args.to_dict(flat=True)
    params["lang"] = normalize_lang(lang_code)
    query = urlencode(params)
    return f"{request.path}?{query}" if query else request.path
