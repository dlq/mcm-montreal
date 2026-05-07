from __future__ import annotations

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
