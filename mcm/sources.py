from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from .seed_data import SEED_LISTINGS

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


@dataclass(frozen=True)
class SourceDefinition:
    slug: str
    name: str
    website: str
    city: str
    province: str
    country: str
    is_montreal_local: bool
    shipping_summary: str
    source_type: str
    crawl_priority: int
    notes: str
    description: str
    style_focus: str
    listing_urls: tuple[str, ...]
    parser: str


SOURCE_DEFINITIONS = [
    SourceDefinition(
        slug="morceau",
        name="Morceau",
        website="https://www.morceau.ca/",
        city="Montreal",
        province="QC",
        country="Canada",
        is_montreal_local=True,
        shipping_summary="International shipping available on all items.",
        source_type="direct_shop",
        crawl_priority=1,
        notes="Strong Shopify-style vintage collection.",
        description="Montreal-based vintage and design shop with a strong MCM furniture mix.",
        style_focus="Vintage, Scandinavian, Italian, collectible design.",
        listing_urls=("https://www.morceau.ca/collections/vintage",),
        parser="shopify_collection",
    ),
    SourceDefinition(
        slug="showroom-montreal",
        name="Showroom Montreal",
        website="https://www.showroommtl.com/",
        city="Montreal",
        province="QC",
        country="Canada",
        is_montreal_local=True,
        shipping_summary="Montreal local source; some items require direct contact for price or shipping.",
        source_type="direct_shop",
        crawl_priority=1,
        notes="Wix-style nouveautes page with detailed text listings.",
        description="Local Montreal MCM specialist focused on restored Scandinavian and Canadian modern furniture.",
        style_focus="Scandinavian, Danish, restored vintage, teak and rosewood.",
        listing_urls=(
            "https://www.showroommtl.com/nouveaute",
            "https://www.showroommtl.com/buffet",
            "https://www.showroommtl.com/table",
            "https://www.showroommtl.com/chaises",
            "https://www.showroommtl.com/sofa",
            "https://www.showroommtl.com/fauteuil",
            "https://www.showroommtl.com/tables-dappoints",
            "https://www.showroommtl.com/bureau",
            "https://www.showroommtl.com/biblio",
            "https://www.showroommtl.com/lits-commodes",
            "https://www.showroommtl.com/luminaire",
            "https://www.showroommtl.com/deco",
        ),
        parser="showroom",
    ),
    SourceDefinition(
        slug="montreal-moderne",
        name="Montreal Moderne",
        website="https://www.montrealmoderne.com/",
        city="Montreal",
        province="QC",
        country="Canada",
        is_montreal_local=True,
        shipping_summary="Montreal local source with sold-out states visible on-page.",
        source_type="direct_shop",
        crawl_priority=1,
        notes="Wix-style nouveautes page with clear price or sold-out text.",
        description="Montreal Scandinavian and MCM furniture specialist established in 2007.",
        style_focus="Scandinavian comfort, teak furniture, clean Danish-inspired pieces.",
        listing_urls=(
            "https://www.montrealmoderne.com/nouveaut%C3%A9s",
            "https://www.montrealmoderne.com/salon",
            "https://www.montrealmoderne.com/salle-%C3%A0-manger",
            "https://www.montrealmoderne.com/chambre",
        ),
        parser="montreal_moderne",
    ),
    SourceDefinition(
        slug="le-centerpiece",
        name="Le Centerpiece",
        website="https://lecenterpiece.com/",
        city="Montreal",
        province="QC",
        country="Canada",
        is_montreal_local=True,
        shipping_summary="Montreal to worldwide; oversized items may require a shipping quote.",
        source_type="direct_shop",
        crawl_priority=1,
        notes="Curated premium vintage inventory with quote-based shipping for large pieces.",
        description="Premium Montreal design gallery with collectible furniture and decorative objects.",
        style_focus="Collectible design, premium vintage furniture, European modernism.",
        listing_urls=(
            "https://lecenterpiece.com/collections/furniture",
            "https://lecenterpiece.com/collections/chairs",
            "https://lecenterpiece.com/collections/storage",
            "https://lecenterpiece.com/collections/kitchen-dining",
            "https://lecenterpiece.com/collections/living-room",
            "https://lecenterpiece.com/collections/office",
            "https://lecenterpiece.com/collections/usm-modular-furniture",
        ),
        parser="shopify_collection",
    ),
]

SHOWROOM_OVERRIDES: dict[str, dict[str, str]] = {
    "unite murale en teck 60s modele cado par poul cadovius": {
        "primary_image_url": "https://static.wixstatic.com/media/fc24cc_da90cc3192de41f8a5bf6f86c7badb30~mv2.jpg/v1/fill/w_250,h_250,al_c,q_90,enc_auto/fc24cc_da90cc3192de41f8a5bf6f86c7badb30~mv2.jpg",
        "source_listing_url": "https://www.showroommtl.com/biblio",
    },
    "lampe en verre et aluminium 60s modele dream island par raak": {
        "primary_image_url": "https://static.wixstatic.com/media/fc24cc_3c6f1680fc2b438fa7d793e695070210~mv2.jpg/v1/fill/w_250,h_250,al_c,q_90,enc_auto/fc24cc_3c6f1680fc2b438fa7d793e695070210~mv2.jpg",
        "source_listing_url": "https://www.showroommtl.com/nouveaute?lightbox=dataItem-mmz4dux33",
    },
    "sofa en cerisier 60s modele 118 par grete jalk": {
        "primary_image_url": "https://static.wixstatic.com/media/fc24cc_d9d7f0ccb8aa44d3a90528690affd6f8~mv2.jpg/v1/fill/w_250,h_250,al_c,q_90,enc_auto/fc24cc_d9d7f0ccb8aa44d3a90528690affd6f8~mv2.jpg",
        "source_listing_url": "https://www.showroommtl.com/sofa",
    },
}


def fetch_source_listings(source: SourceDefinition) -> tuple[list[dict[str, Any]], str | None]:
    try:
        if source.parser == "shopify_collection":
            return _fetch_shopify_collection(source), None
        if source.parser == "showroom":
            return _fetch_showroom(source), None
        if source.parser == "montreal_moderne":
            return _fetch_montreal_moderne(source), None
        raise ValueError(f"Unknown parser: {source.parser}")
    except Exception as exc:  # noqa: BLE001
        return _seed_fallback(source), str(exc)


def fetch_showroom_entry_listings(
    source: SourceDefinition,
    entry_url: str,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        if source.parser != "showroom":
            raise ValueError(f"Source does not use the Showroom parser: {source.slug}")
        if entry_url not in source.listing_urls:
            raise ValueError(f"Unknown Showroom listing URL: {entry_url}")
        return _fetch_showroom_entry(source, entry_url), None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def _seed_fallback(source: SourceDefinition) -> list[dict[str, Any]]:
    seeded = []
    for item in SEED_LISTINGS.get(source.slug, []):
        payload = dict(item)
        payload["parse_confidence"] = 0.45
        payload["ingest_source_type"] = "seed_fallback"
        seeded.append(payload)
    return seeded


def _fetch_shopify_collection(source: SourceDefinition) -> list[dict[str, Any]]:
    listings_by_url: dict[str, dict[str, Any]] = {}
    for entry_url in source.listing_urls:
        for product in _fetch_shopify_collection_products(entry_url):
            try:
                listing = _parse_shopify_collection_product(source, product)
            except ValueError:
                continue
            listings_by_url[listing["source_listing_url"]] = listing

    if listings_by_url:
        return list(listings_by_url.values())[:200]

    product_urls: list[str] = []
    for entry_url in source.listing_urls:
        try:
            html = _fetch_html(entry_url)
        except Exception:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "")
            if "/products/" not in href:
                continue
            absolute = urllib.parse.urljoin(source.website, href.split("?")[0])
            if absolute not in product_urls:
                product_urls.append(absolute)
    listings = []
    for url in product_urls[:200]:
        try:
            listings.append(_parse_shopify_product(source, url))
        except ValueError:
            continue
    if not listings:
        raise ValueError(f"No listings parsed from {source.listing_urls[0]}")
    return listings


def _fetch_shopify_collection_products(entry_url: str) -> list[dict[str, Any]]:
    all_products: list[dict[str, Any]] = []
    for page in range(1, 11):
        products_url = f"{entry_url.rstrip('/')}/products.json?limit=250&page={page}"
        try:
            payload = json.loads(_fetch_html(products_url))
        except (json.JSONDecodeError, urllib.error.URLError):
            break
        products = [product for product in payload.get("products", []) if isinstance(product, dict)]
        if not products:
            break
        all_products.extend(products)
    return all_products


def _parse_shopify_collection_product(
    source: SourceDefinition, product: dict[str, Any]
) -> dict[str, Any]:
    title = _clean_text(product.get("title", ""))
    handle = _clean_text(product.get("handle", ""))
    if _normalize_lookup(title) == "gift card":
        raise ValueError("Skipping Shopify gift card")
    url = urllib.parse.urljoin(source.website, f"/products/{handle}")
    description_text = BeautifulSoup(product.get("body_html") or "", "html.parser").get_text(
        "\n", strip=True
    )
    description = _clean_text(description_text)
    if _is_current_production(description):
        raise ValueError("Skipping current-production Shopify item")
    variants = [variant for variant in product.get("variants", []) if isinstance(variant, dict)]
    images = [
        image.get("src", "")
        for image in product.get("images", [])
        if isinstance(image, dict) and image.get("src")
    ]
    price_value = next(
        (_to_float(str(variant.get("price", ""))) for variant in variants if variant.get("price")),
        None,
    )
    availability = (
        "available" if any(variant.get("available") for variant in variants) else "sold_out"
    )
    designer, maker = _extract_designer_and_maker(title, description)
    materials = _extract_labeled_section(
        description_text, ("materials", "materiaux", "matériaux")
    ) or _extract_materials(f"{title} {description}")
    dimensions = _extract_labeled_section(description_text, ("dimensions",)) or _extract_dimensions(
        description
    )
    return {
        "source_listing_url": url,
        "source_listing_key": url,
        "title": title,
        "price_raw": f"${price_value:,.2f} CAD" if price_value is not None else "",
        "price_value": price_value,
        "currency": "CAD",
        "primary_image_url": images[0] if images else "",
        "additional_image_urls": images[1:6],
        "availability_status": availability,
        "shipping_scope": _shipping_scope_for(source),
        "ships_to_montreal": 1,
        "shipping_note": source.shipping_summary,
        "category": _categorize_listing(title, description),
        "designer": designer,
        "maker": maker,
        "materials": materials,
        "dimensions_text": dimensions,
        "condition_text": _extract_condition(description),
        "source_description": description,
        "location_text": f"{source.city}, {source.province}",
        "era": _extract_era(f"{title} {description}"),
        "parse_confidence": 0.86,
        "ingest_source_type": "live_fetch",
    }


def _parse_shopify_product(source: SourceDefinition, url: str) -> dict[str, Any]:
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    product_data = _extract_product_json_ld(soup) or {}
    offers = product_data.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    title = (
        product_data.get("name")
        or _safe_text(soup.select_one("h1"))
        or _slug_to_title(url.rsplit("/", 1)[-1])
    )
    description_node = soup.select_one(
        '[data-product-description], .product__description, .rte, [itemprop="description"]'
    )
    description_text = (
        BeautifulSoup(str(description_node), "html.parser").get_text("\n", strip=True)
        if description_node
        else _clean_text(str(product_data.get("description") or ""))
    )
    description = _clean_text(product_data.get("description") or description_text)
    if _is_current_production(description):
        raise ValueError("Skipping current-production Shopify item")
    images = product_data.get("image") or []
    if isinstance(images, str):
        images = [images]
    price_value = _to_float(str(offers.get("price") or "") or _extract_price_text(soup))
    availability = _normalize_availability(
        offers.get("availability"),
        soup.get_text(" ", strip=True),
    )
    shipping_scope = _shipping_scope_for(source)
    designer, maker = _extract_designer_and_maker(title, description)
    materials = _extract_labeled_section(
        description_text, ("materials", "materiaux", "matériaux")
    ) or _extract_materials(f"{title} {description}")
    dimensions = _extract_labeled_section(description_text, ("dimensions",)) or _extract_dimensions(
        description
    )
    category = _categorize_listing(title, description)
    return {
        "source_listing_url": url,
        "title": title,
        "price_raw": _extract_price_text(soup)
        or (f"${price_value:,.2f} CAD" if price_value is not None else ""),
        "price_value": price_value,
        "currency": offers.get("priceCurrency", "CAD"),
        "primary_image_url": images[0] if images else "",
        "additional_image_urls": images[1:6],
        "availability_status": availability,
        "shipping_scope": shipping_scope,
        "ships_to_montreal": 1,
        "shipping_note": source.shipping_summary,
        "category": category,
        "designer": designer,
        "maker": maker,
        "materials": materials,
        "dimensions_text": dimensions,
        "condition_text": _extract_condition(description),
        "source_description": description,
        "location_text": f"{source.city}, {source.province}",
        "era": _extract_era(f"{title} {description}"),
        "parse_confidence": 0.82,
        "ingest_source_type": "live_fetch",
    }


def _fetch_showroom(source: SourceDefinition) -> list[dict[str, Any]]:
    listings_by_key: dict[str, dict[str, Any]] = {}
    for entry_url in source.listing_urls:
        for listing in _fetch_showroom_entry(source, entry_url):
            existing = listings_by_key.get(listing["source_listing_key"])
            if existing is None or (
                listing["primary_image_url"] and not existing.get("primary_image_url")
            ):
                listings_by_key[listing["source_listing_key"]] = listing
    listings = list(listings_by_key.values())
    if not listings:
        raise ValueError("No Showroom Montreal gallery items parsed")
    return listings[:240]


def _fetch_showroom_entry(source: SourceDefinition, entry_url: str) -> list[dict[str, Any]]:
    listings_by_key: dict[str, dict[str, Any]] = {}
    for listing in _extract_showroom_gallery_listings(source, entry_url):
        normalized_text = _normalize_lookup(listing["title"])
        for lookup, override in SHOWROOM_OVERRIDES.items():
            if lookup in normalized_text:
                listing.update(override)
                break
        existing = listings_by_key.get(listing["source_listing_key"])
        if existing is None or (
            listing["primary_image_url"] and not existing.get("primary_image_url")
        ):
            listings_by_key[listing["source_listing_key"]] = listing
    listings = list(listings_by_key.values())
    if not listings:
        raise ValueError(f"No Showroom Montreal gallery items parsed from {entry_url}")
    return listings


def _extract_showroom_gallery_listings(
    source: SourceDefinition, entry_url: str
) -> list[dict[str, Any]]:
    html = _fetch_html(entry_url)
    siteassets_url = _extract_showroom_siteassets_url(html)
    if not siteassets_url:
        return _extract_showroom_legacy_headings(source, entry_url, html)
    gallery_items = _extract_showroom_gallery_items(siteassets_url)
    listings: list[dict[str, Any]] = []
    for item in gallery_items:
        item_id = _clean_text(str(item.get("id", "")))
        image_uri = _clean_text(item.get("uri", ""))
        raw_description = (item.get("description") or "").replace("\r", "\n")
        description = _clean_text(raw_description)
        if not description:
            continue
        title = _showroom_title(item)
        if not title or not item_id:
            continue
        normalized_title = _normalize_lookup(title)
        if normalized_title.startswith("dataitem"):
            continue
        if normalized_title.startswith("contactez nous"):
            continue
        if _is_showroom_promotional_item(title, raw_description):
            continue
        price_line = _showroom_price_line(raw_description)
        price_match = re.search(r"(\d[\d\s]*(?:[.,]\d{2})?)\s*\$", price_line)
        price_value = _to_float(price_match.group(1)) if price_match else None
        sold_out = "vendu" in normalized_title or "vendu" in _normalize_lookup(description)
        if sold_out:
            continue
        designer, maker = _extract_designer_and_maker(title, description)
        listings.append(
            {
                "source_listing_url": entry_url,
                "source_listing_key": f"showroom:{item_id}",
                "title": title,
                "price_raw": price_line
                or ("Vendu" if sold_out else "Contactez nous pour les details"),
                "price_value": price_value,
                "currency": "CAD",
                "primary_image_url": _showroom_media_url(image_uri),
                "additional_image_urls": [],
                "availability_status": "available",
                "shipping_scope": "local_quote",
                "ships_to_montreal": 1,
                "shipping_note": source.shipping_summary,
                "category": _categorize_listing(title, description),
                "designer": designer,
                "maker": maker,
                "materials": _extract_materials(f"{title} {description}"),
                "dimensions_text": _extract_dimensions(description),
                "condition_text": "Restored" if "restaur" in _normalize_lookup(description) else "",
                "source_description": description,
                "location_text": f"{source.city}, {source.province}",
                "era": _extract_era(f"{title} {description}"),
                "parse_confidence": 0.9,
                "ingest_source_type": "live_fetch",
            }
        )
    return listings


def _extract_showroom_siteassets_url(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    page_id_match = re.search(r"window\.firstPageId\s*=\s*'([^']+)'", html)
    page_id = page_id_match.group(1) if page_id_match else ""
    if page_id:
        page_link = soup.find("link", id=f"features_{page_id}", href=True)
        if page_link:
            return _clean_showroom_siteassets_url(page_link.get("href", ""))
    for link in soup.find_all("link", href=True):
        href = link.get("href", "")
        if "siteassets.parastorage.com/pages/pages/thunderbolt" not in href:
            continue
        if "module=thunderbolt-features" not in href:
            continue
        return _clean_showroom_siteassets_url(href)
    return ""


def _clean_showroom_siteassets_url(href: str) -> str:
    return href.replace("\\/", "/").replace("®istryLibrariesTopology", "&registryLibrariesTopology")


def _extract_showroom_gallery_items(siteassets_url: str) -> list[dict[str, Any]]:
    payload = json.loads(_fetch_html(siteassets_url))
    structure_components = ((payload.get("structure") or {}).get("components")) or {}
    comp_props = ((((payload.get("props") or {}).get("render")) or {}).get("compProps")) or {}
    for comp_id, comp in structure_components.items():
        if comp.get("componentType") != "Masonry":
            continue
        items = (comp_props.get(comp_id) or {}).get("images") or []
        if items:
            return [item for item in items if isinstance(item, dict)]
    return []


def _extract_showroom_legacy_headings(
    source: SourceDefinition, entry_url: str, html: str
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[dict[str, Any]] = []
    for title_node in soup.find_all("h3"):
        title_text = _clean_text(title_node.get_text(" ", strip=True))
        if not title_text or len(title_text) < 16:
            continue
        maker_node = title_node.find_previous("h2")
        maker = _clean_text(maker_node.get_text(" ", strip=True)) if maker_node else ""
        normalized_text = _normalize_lookup(title_text)
        if normalized_text.startswith("contactez nous"):
            continue
        card_root = title_node.parent
        image = ""
        if card_root:
            image_node = card_root.find_previous("img")
            if image_node:
                image = image_node.get("src", "")
        price_match = re.search(r"(\d[\d\s]*(?:[.,]\d{2})?)\s*\$", title_text)
        price_value = _to_float(price_match.group(1)) if price_match else None
        designer, parsed_maker = _extract_designer_and_maker(title_text, maker)
        listings.append(
            {
                "source_listing_url": entry_url,
                "source_listing_key": f"showroom:{normalized_text}",
                "title": title_text,
                "price_raw": price_match.group(0)
                if price_match
                else "Contactez nous pour les details",
                "price_value": price_value,
                "currency": "CAD",
                "primary_image_url": image,
                "additional_image_urls": [],
                "availability_status": "unknown"
                if "contactez" in title_text.lower()
                else "available",
                "shipping_scope": "local_quote",
                "ships_to_montreal": 1,
                "shipping_note": source.shipping_summary,
                "category": _categorize_listing(title_text, maker),
                "designer": designer,
                "maker": parsed_maker or maker,
                "materials": _extract_materials(title_text),
                "dimensions_text": _extract_dimensions(title_text),
                "condition_text": "Restored" if "restaur" in title_text.lower() else "",
                "source_description": title_text,
                "location_text": f"{source.city}, {source.province}",
                "era": _extract_era(title_text),
                "parse_confidence": 0.7,
                "ingest_source_type": "live_fetch",
            }
        )
    return listings


def _showroom_title(item: dict[str, Any]) -> str:
    description = (item.get("description") or "").replace("\r", "\n")
    lines = [_clean_text(line).strip(" -") for line in description.split("\n") if _clean_text(line)]
    title_lines: list[str] = []
    for line in lines:
        normalized = _normalize_lookup(line)
        if re.search(r"\d+\s*\$", line):
            break
        if "vendu" in normalized and title_lines:
            break
        if re.search(r"\d+(\.\d+)?\s*(?:''|po|cm|h\\b|l\\b|p\\b|w\\b|x)", normalized):
            break
        title_lines.append(line)
        if len(title_lines) >= 2:
            break
    title = " ".join(title_lines)
    return title or _clean_text(item.get("title", "")) or _slug_to_title(str(item.get("id", "")))


def _showroom_price_line(description: str) -> str:
    for line in reversed(
        [_clean_text(line) for line in description.split("\n") if _clean_text(line)]
    ):
        if re.search(r"\d+\s*\$", line):
            return line
        if "vendu" in _normalize_lookup(line):
            return line
    return ""


def _is_showroom_promotional_item(title: str, description: str) -> bool:
    normalized = _normalize_lookup(f"{title} {description}")
    if not normalized:
        return True

    announcement_markers = (
        "joyeuses paques",
        "joyeux noel",
        "bonne annee",
        "horaire",
        "ouvert",
        "ferme",
        "fermee",
        "closed",
        "open",
    )
    if not any(marker in normalized for marker in announcement_markers):
        return False

    inventory_markers = (
        "buffet",
        "table",
        "chaises",
        "chaise",
        "sofa",
        "fauteuil",
        "biblio",
        "bibliotheque",
        "lit",
        "commode",
        "lampe",
        "luminaire",
        "teck",
        "noyer",
        "palissandre",
        "rosewood",
        "danmark",
        "denmark",
        "norway",
        "canada",
        "modele",
        "model",
    )
    return not any(marker in normalized for marker in inventory_markers)


def _showroom_media_url(uri: str) -> str:
    if not uri:
        return ""
    return f"https://static.wixstatic.com/media/{uri}"


def _fetch_montreal_moderne(source: SourceDefinition) -> list[dict[str, Any]]:
    listings_by_key: dict[str, dict[str, Any]] = {}
    for entry_url in source.listing_urls:
        html = _fetch_html(entry_url)
        product_items = _extract_wix_products_json(html)
        if product_items:
            for item in product_items:
                url_part = item.get("urlPart", "")
                if not url_part:
                    continue
                title = _clean_text(item.get("name", ""))
                if not title:
                    continue
                media = item.get("media") or []
                image_urls = [
                    media_item.get("fullUrl", "")
                    for media_item in media
                    if isinstance(media_item, dict) and media_item.get("fullUrl")
                ]
                price_value = item.get("price")
                is_in_stock = bool(item.get("isInStock"))
                formatted_price = _clean_text(item.get("formattedPrice", "")) or "Rupture de stock"
                listing = {
                    "source_listing_url": urllib.parse.urljoin(
                        source.website, f"/product-page/{url_part}"
                    ),
                    "source_listing_key": f"montreal-moderne:{url_part}",
                    "title": title,
                    "price_raw": formatted_price if is_in_stock else "Rupture de stock",
                    "price_value": float(price_value)
                    if isinstance(price_value, (int, float)) and price_value > 0
                    else None,
                    "currency": item.get("currency", "CAD"),
                    "primary_image_url": image_urls[0] if image_urls else "",
                    "additional_image_urls": image_urls[1:6],
                    "availability_status": "available" if is_in_stock else "sold_out",
                    "shipping_scope": "local_quote",
                    "ships_to_montreal": 1,
                    "shipping_note": source.shipping_summary,
                    "category": _categorize_listing(title, ""),
                    "designer": "",
                    "maker": "",
                    "materials": _extract_materials(title),
                    "dimensions_text": "",
                    "condition_text": "",
                    "source_description": title,
                    "location_text": f"{source.city}, {source.province}",
                    "era": _extract_era(title),
                    "parse_confidence": 0.9,
                    "ingest_source_type": "live_fetch",
                }
                listings_by_key[listing["source_listing_key"]] = listing
            continue

    if listings_by_key:
        return list(listings_by_key.values())[:200]

    html = _fetch_html(source.listing_urls[0])
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for anchor in soup.find_all("a"):
        text = _clean_text(anchor.get_text(" ", strip=True))
        if "Prix" not in text and "Rupture de stock" not in text:
            continue
        title = text.split("Prix")[0].split("Rupture de stock")[0].strip(" -")
        if not title:
            continue
        sold_out = "Rupture de stock" in text
        price_match = re.search(r"Prix\s+([\d\s,]+)C\$", text)
        listings.append(
            {
                "source_listing_url": f"{source.listing_urls[0]}#{_slugify(title)}",
                "source_listing_key": f"montreal-moderne:{_slugify(title)}",
                "title": title,
                "price_raw": price_match.group(0) if price_match else "Rupture de stock",
                "price_value": _to_float(price_match.group(1)) if price_match else None,
                "currency": "CAD",
                "primary_image_url": "",
                "additional_image_urls": [],
                "availability_status": "sold_out" if sold_out else "available",
                "shipping_scope": "local_quote",
                "ships_to_montreal": 1,
                "shipping_note": source.shipping_summary,
                "category": _categorize_listing(title, ""),
                "designer": "",
                "maker": "",
                "materials": _extract_materials(title),
                "dimensions_text": "",
                "condition_text": "",
                "source_description": text,
                "location_text": f"{source.city}, {source.province}",
                "era": _extract_era(title),
                "parse_confidence": 0.72,
                "ingest_source_type": "live_fetch",
            }
        )
    if not listings:
        raise ValueError("No Montreal Moderne items parsed")
    return listings[:120]


def _extract_wix_products_json(html: str) -> list[dict[str, Any]]:
    match = re.search(
        r'"productsWithMetaData":\{"list":(\[.*?\]),"totalCount":\d+\}', html, flags=re.DOTALL
    )
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return [item for item in payload if isinstance(item, dict)]


def _fetch_html(url: str) -> str:
    request = urllib.request.Request(_ascii_safe_url(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=18) as response:
        return response.read().decode("utf-8", errors="replace")


def _ascii_safe_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    netloc = parts.netloc.encode("idna").decode("ascii")
    path = urllib.parse.quote(parts.path, safe="/%:@")
    query = urllib.parse.quote(parts.query, safe="/%:@?&=+$,;")
    fragment = urllib.parse.quote(parts.fragment, safe="/%:@?&=+$,;")
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, fragment))


def _extract_product_json_ld(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("@type") == "Product":
                return candidate
    return {}


def _normalize_availability(offer_value: Any, page_text: str) -> str:
    offer_value = str(offer_value or "").lower()
    text = page_text.lower()
    if (
        "sold out" in offer_value
        or "soldout" in offer_value
        or "rupture de stock" in text
        or "sold out" in text
    ):
        return "sold_out"
    if "out of stock" in text:
        return "sold_out"
    return "available"


def _is_current_production(text: str) -> bool:
    normalized = _normalize_lookup(text)
    return "current production" in normalized


def _extract_price_text(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\$[\d,]+(?:\.\d{2})?\s*CAD", text)
    if match:
        return match.group(0)
    match = re.search(r"\$[\d,]+(?:\.\d{2})?", text)
    return match.group(0) if match else ""


def _extract_designer_and_maker(title: str, description: str) -> tuple[str, str]:
    match = re.search(r"(.+?)\s+pour\s+(.+?)(?:$|,|\||\.)", description, flags=re.IGNORECASE)
    if match:
        designer = _last_person_name(match.group(1))
        if designer:
            return designer, _clean_text(match.group(2))

    match = re.search(r"\bby\s+(.+?)(?:\s+for\s+(.+?))?$", title, flags=re.IGNORECASE)
    if match:
        designer = _clean_designer_candidate(match.group(1))
        maker = _clean_maker_candidate(match.group(2) or "")
        if designer:
            return designer, maker

    first_sentence = re.split(r"[.\n|]", description, maxsplit=1)[0]
    match = re.search(
        r"\bdesigned\s+by\s+(.+?)(?:,|\s+for\s+(.+?))?$",
        first_sentence,
        flags=re.IGNORECASE,
    )
    if match:
        designer = _clean_designer_candidate(match.group(1))
        maker = _clean_maker_candidate(match.group(2) or "")
        if designer:
            return designer, maker

    return "", _clean_text(description) if len(description.split()) < 6 else ""


def _clean_designer_candidate(value: str) -> str:
    candidate = _clean_text(value)
    if not candidate or len(candidate.split()) > 5:
        return ""
    if re.search(r"[.;:!?]", candidate):
        return ""
    return candidate


def _clean_maker_candidate(value: str) -> str:
    candidate = _clean_text(value)
    if not candidate:
        return ""
    if len(candidate.split()) > 6:
        return ""
    if re.search(r"\b(more information|details|checkout|shipping|policies)\b", candidate, re.I):
        return ""
    return candidate


def _extract_era(text: str) -> str:
    match = re.search(
        r"(?<!\w)(19[4-9]0[’']?s|20[0-2]0[’']?s|[’']\d0s)(?!\w)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    value = match.group(1)
    if value.startswith(("'", "’")):
        return f"19{value[1:]}"
    return re.sub(r"[’']", "", value)


def _extract_dimensions(text: str) -> str:
    dimension_unit = r"(?:in|\"|''|”|″)"
    dimension_label = r"[WLDHP]"
    dimension_part = (
        r"\d+(?:[.,]\d+)?\s*"
        rf"(?:(?:{dimension_unit})\s*)?"
        rf"{dimension_label}?"
    )
    match = re.search(
        rf"({dimension_part}\s*[xX]\s*{dimension_part}(?:\s*[xX]\s*{dimension_part})?)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return _clean_text(match.group(1))
    match = re.search(r"\d+(?:\.\d+)?\s*[WLDH]\s*x?\s*\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


SECTION_LABELS = {
    "materials",
    "materiaux",
    "dimensions",
    "features",
    "lead time",
    "condition",
    "designer",
    "maker",
    "made in",
    "provenance",
}


def _extract_labeled_section(text: str, labels: tuple[str, ...]) -> str:
    wanted_labels = {_normalize_lookup(label) for label in labels}
    section_labels = {_normalize_lookup(label) for label in SECTION_LABELS}
    lines = [_clean_text(line) for line in (text or "").splitlines()]
    for index, line in enumerate(lines):
        if _normalize_lookup(line) not in wanted_labels:
            continue
        values = []
        for following in lines[index + 1 :]:
            normalized_following = _normalize_lookup(following)
            if not following:
                continue
            if normalized_following in section_labels:
                break
            values.append(following)
        return _clean_text(" ".join(values))
    return ""


def _extract_condition(text: str) -> str:
    lowered = text.lower()
    conditions = []
    if "restaur" in lowered or "restored" in lowered:
        conditions.append("Restored")
    if "recouvrement" in lowered or "reupholstered" in lowered:
        conditions.append("Reupholstered")
    if "refinished" in lowered:
        conditions.append("Refinished")
    return ", ".join(conditions)


def _extract_materials(text: str) -> str:
    material_keywords = [
        ("teak", ["teck", "teak"]),
        ("rosewood", ["palissandre", "rosewood"]),
        ("walnut", ["noyer", "walnut"]),
        ("glass", ["verre", "glass"]),
        ("chrome", ["chrome"]),
        ("aluminum", ["aluminium", "aluminum"]),
        ("leather", ["cuir", "leather"]),
        ("sherpa", ["sherpa"]),
        ("wood", ["bois", "wood"]),
        ("metal", ["metal", "métal"]),
    ]
    found = []
    lowered = text.lower()
    for material, keywords in material_keywords:
        if any(keyword in lowered for keyword in keywords) and material not in found:
            found.append(material)
    return ", ".join(found)


def _last_person_name(text: str) -> str:
    names = re.findall(
        r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+)+",
        text,
    )
    return _clean_text(names[-1]) if names else ""


def _categorize_listing(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    mapping = [
        ("sideboards / credenzas", ["sideboard", "buffet", "credenza"]),
        ("dressers / commodes", ["dresser", "commode", "wardrobe"]),
        ("dining tables", ["dining table", "table a manger", "table en teck"]),
        ("dining chairs", ["dining chair", "chair", "chaises", "tabouret"]),
        ("lounge chairs", ["armchair", "fauteuil", "lounge chair"]),
        ("sofas", ["sofa", "canape"]),
        ("coffee tables", ["coffee table", "table basse"]),
        ("desks", ["desk", "bureau", "pupitre"]),
        (
            "bookshelves / wall units",
            ["bookcase", "bibliotheque", "unite murale", "wall unit", "etagere"],
        ),
        ("nightstands", ["bedside", "chevet", "side table", "table d’appoint", "table d'appoint"]),
        ("beds / bedroom storage", ["bed", "lit"]),
        ("lighting", ["lamp", "lampe", "luminaire", "suspension"]),
    ]
    for category, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            return category
    return "furniture"


def _shipping_scope_for(source: SourceDefinition) -> str:
    summary = source.shipping_summary.lower()
    if "international" in summary or "worldwide" in summary:
        return "worldwide_quote" if "quote" in summary else "international"
    if "canada" in summary and "united states" in summary:
        return "canada_us"
    if "canada" in summary:
        return "canada"
    return "local_quote"


def _slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _safe_text(node: Any) -> str:
    if not node:
        return ""
    return _clean_text(node.get_text(" ", strip=True))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _normalize_lookup(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("'", " ").replace('"', " ")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _to_float(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace("C$", "").replace("$", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if cleaned.count(".") > 1:
        head, tail = cleaned.split(".", 1)
        cleaned = head + "." + tail.replace(".", "")
    try:
        return float(cleaned)
    except ValueError:
        return None
