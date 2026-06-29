from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, Required, TypedDict


@dataclass(frozen=True)
class SourceDefinition:
    slug: str
    name: str
    website: str
    wordmark_text: str
    wordmark_style: str
    street_address: str
    city: str
    province: str
    postal_code: str
    country: str
    latitude: float | None
    longitude: float | None
    public_location_note: str
    is_montreal_local: bool
    shipping_summary: str
    source_type: str
    crawl_priority: int
    notes: str
    description: str
    style_focus: str
    listing_urls: tuple[str, ...]
    parser: str


class ParsedListing(TypedDict, total=False):
    """Normalized listing payload emitted by source parsers and ingested by refresh."""

    source_listing_url: Required[str]
    title: Required[str]
    source_listing_key: NotRequired[str]
    price_raw: NotRequired[str]
    price_value: NotRequired[float | None]
    currency: NotRequired[str]
    primary_image_url: NotRequired[str]
    additional_image_urls: NotRequired[list[str]]
    availability_status: NotRequired[str]
    shipping_scope: NotRequired[str]
    ships_to_montreal: NotRequired[int]
    shipping_note: NotRequired[str]
    category: NotRequired[str]
    subcategory: NotRequired[str]
    designer: NotRequired[str]
    maker: NotRequired[str]
    era: NotRequired[str]
    materials: NotRequired[str]
    dimensions_text: NotRequired[str]
    condition_text: NotRequired[str]
    location_text: NotRequired[str]
    source_description: NotRequired[str]
    ingest_source_type: NotRequired[str]
    parse_confidence: NotRequired[float]
