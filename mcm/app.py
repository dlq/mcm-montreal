from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse
from xml.sax.saxutils import escape as xml_escape

from flask import (
    Flask,
    Response,
    abort,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.datastructures import MultiDict

from .db import get_db, initialize_storage
from .i18n import (
    LAUNCH_CATEGORIES,
    category_label,
    category_list_text,
    condition_label,
    date_text,
    era_label,
    filter_summary,
    filter_summary_parts,
    freshness_label,
    language_url,
    listing_count_text,
    material_label,
    normalize_lang,
    price_text,
    resolved_language,
    shipping_note_text,
    shop_text,
    status_label,
    translator_for,
)
from .identity import ensure_anonymous_identity, load_anonymous_identity, persist_anonymous_identity
from .locations import shop_address_lines, shop_apple_maps_url, shop_directions_url, shop_has_map
from .refresh import (
    listing_id_from_item_number,
    public_item_number,
    reconcile_chunked_source,
    refresh_all_sources,
    refresh_chez_lamothe_chunk,
    refresh_le_centerpiece_chunk,
    refresh_mostly_danish_chunk,
    refresh_showroom_chunk,
    refresh_source_by_slug,
)
from .repository import (
    add_listing_design_entity_evidence,
    admin_sources,
    approve_design_entity_candidate,
    build_listing_filters,
    count_listings,
    create_design_entity,
    delete_saved_search,
    favourite_counts,
    find_duplicate_candidates,
    get_listing,
    get_shop,
    get_shop_by_slug,
    list_design_entities,
    list_design_entity_candidates,
    list_failures,
    list_favourite_listings,
    list_favourite_shops,
    list_filter_values,
    list_listing_availability_events,
    list_listing_price_events,
    list_location_filter_values,
    list_saved_searches,
    list_shops,
    list_sitemap_listings,
    query_listings,
    review_design_entity_candidate,
    save_search,
    toggle_favourite_listing,
    toggle_favourite_shop,
    update_listing_overrides,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("MCM_DATABASE", BASE_DIR / "data" / "mcm.db"))
LISTING_PAGE_SIZE = 48
DEFAULT_PUBLIC_BASE_URL = "https://montrealmcm.ca"


def static_asset_version(filename: str) -> int:
    path = BASE_DIR / "static" / filename
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return 0


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


def analytics_page_type(path: str) -> str:
    clean_path = (path or "/").split("?", 1)[0] or "/"
    if clean_path == "/":
        return "home"
    if clean_path == "/shops":
        return "shops"
    if clean_path == "/favourites":
        return "favourites"
    if clean_path.startswith("/listing/"):
        return "listing"
    if clean_path.startswith("/shops/"):
        return "shop"
    if clean_path.startswith("/categories/"):
        return "category"
    return "other"


def analytics_path_key(path: str) -> str:
    clean_path = (path or "/").split("?", 1)[0] or "/"
    return clean_path if clean_path.startswith("/") else f"/{clean_path}"


def should_track_analytics_path(path: str) -> bool:
    clean_path = analytics_path_key(path)
    blocked_prefixes = (
        "/admin",
        "/analytics",
        "/cron",
        "/healthz",
        "/internal",
        "/readyz",
        "/static",
    )
    blocked_paths = {"/manifest.webmanifest", "/robots.txt", "/service-worker.js", "/sitemap.xml"}
    return clean_path not in blocked_paths and not clean_path.startswith(blocked_prefixes)


def request_origin_is_allowed() -> bool:
    origin = request.headers.get("Origin", "")
    if not origin:
        return True
    origin_host = urlparse(origin).hostname or ""
    request_host = request.host.split(":", 1)[0]
    return origin_host in {
        request_host,
        "localhost",
        "127.0.0.1",
        "montrealmcm.ca",
        "www.montrealmcm.ca",
        "montreal-mcm.dalaque.workers.dev",
    }


def record_analytics_pageview(db: Any, path: str, lang: str) -> None:
    if not should_track_analytics_path(path):
        return
    now = datetime.now(UTC)
    clean_lang = normalize_lang(lang)
    page_type = analytics_page_type(path)
    path_key = analytics_path_key(path)
    db.execute(
        """
        INSERT INTO analytics_page_views (
            view_date, page_type, path_key, lang, views, updated_at
        ) VALUES (?, ?, ?, ?, 1, ?)
        ON CONFLICT(view_date, page_type, path_key, lang) DO UPDATE SET
            views = analytics_page_views.views + 1,
            updated_at = excluded.updated_at
        """,
        (now.date().isoformat(), page_type, path_key, clean_lang, now.isoformat()),
    )
    db.commit()


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


def require_scheduled_request() -> None:
    if request.headers.get("X-Cloudflare-Scheduled") != "1":
        abort(404)


def chunk_refresh_payload(chunk: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "source": chunk.result.source_slug,
        "chunk": chunk.chunk_index,
        "entry_url": chunk.entry_url,
        "listings": chunk.result.listings_found,
        "new": chunk.result.new_count,
        "hidden": chunk.result.hidden_count,
        "warning": chunk.result.error,
        "refreshed_at": datetime.now(UTC).isoformat(),
    }


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    secret_key = os.environ.get("MCM_SECRET_KEY", "")
    has_configured_secret_key = bool(secret_key)
    app.config["SECRET_KEY"] = secret_key or f"dev-{secrets.token_hex(16)}"
    app.config["DATABASE"] = str(DB_PATH)
    app.config["D1_BRIDGE_URL"] = os.environ.get("D1_BRIDGE_URL", "")
    app.config["D1_BRIDGE_TOKEN"] = os.environ.get("D1_BRIDGE_TOKEN", "")
    app.config["MCM_ADMIN_TOKEN"] = os.environ.get("MCM_ADMIN_TOKEN", "")
    app.config["MCM_ALLOW_OPEN_ADMIN"] = os.environ.get("MCM_ALLOW_OPEN_ADMIN", "") == "1"
    app.config["MCM_EXPOSE_TIMING_HEADERS"] = os.environ.get("MCM_EXPOSE_TIMING_HEADERS", "") == "1"
    app.config["MCM_PUBLIC_BASE_URL"] = normalized_public_base_url(
        os.environ.get("MCM_PUBLIC_BASE_URL", DEFAULT_PUBLIC_BASE_URL)
    )
    if test_config:
        has_configured_secret_key = has_configured_secret_key or bool(test_config.get("SECRET_KEY"))
        app.config.update(test_config)
    if app.config.get("D1_BRIDGE_URL") and not has_configured_secret_key:
        raise RuntimeError("MCM_SECRET_KEY is required when D1_BRIDGE_URL is configured")
    app.jinja_env.globals["freshness_label"] = freshness_label
    app.jinja_env.globals["json_loads"] = json.loads

    if not app.config.get("D1_BRIDGE_URL"):
        Path(app.config["DATABASE"]).parent.mkdir(exist_ok=True)
    initialize_storage(app)

    @app.before_request
    def open_request_resources() -> None:
        g.request_started_at = time.perf_counter()
        if request.endpoint in {"static", "service_worker", "web_manifest", "robots_txt"}:
            return
        g.db = get_db(app)
        if request.endpoint == "analytics_pageview":
            g.lang = resolved_language()
            return
        load_anonymous_identity(app, g.db)
        g.lang = resolved_language()

    @app.after_request
    def persist_request_resources(response: Response) -> Response:
        if request.endpoint in {"static", "service_worker", "web_manifest", "robots_txt"}:
            return response
        response = persist_anonymous_identity(response)
        started_at = getattr(g, "request_started_at", None)
        if started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            db = getattr(g, "db", None)
            d1_query_count = getattr(db, "query_count", None)
            d1_query_ms = getattr(db, "total_query_ms", None)
            if app.config.get("MCM_EXPOSE_TIMING_HEADERS"):
                response.headers["X-MCM-App-Ms"] = f"{elapsed_ms:.1f}"
                if d1_query_count is not None and d1_query_ms is not None:
                    response.headers["X-MCM-D1-Queries"] = str(d1_query_count)
                    response.headers["X-MCM-D1-Ms"] = f"{d1_query_ms:.1f}"
            app.logger.info(
                "request_timing path=%s status=%s app_ms=%.1f d1_queries=%s d1_ms=%s",
                request.path,
                response.status_code,
                elapsed_ms,
                d1_query_count if d1_query_count is not None else "-",
                f"{d1_query_ms:.1f}" if d1_query_ms is not None else "-",
            )
        return response

    @app.teardown_appcontext
    def close_db(exc: BaseException | None) -> None:  # noqa: ARG001
        db = getattr(g, "db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        canonical_url = absolute_public_url(app.config["MCM_PUBLIC_BASE_URL"], request.path)
        alternate_language_urls = language_alternate_urls(
            app.config["MCM_PUBLIC_BASE_URL"], request.path
        )
        return {
            "favourite_counts": favourite_counts(),
            "lang": g.lang,
            "canonical_url": canonical_url,
            "alternate_language_urls": alternate_language_urls,
            "og_locale": "fr_CA" if g.lang == "fr" else "en_CA",
            "t": translator_for(g.lang),
            "status_label": status_label,
            "category_list_text": category_list_text,
            "category_label": category_label,
            "category_slug": category_slug,
            "condition_label": condition_label,
            "date_text": date_text,
            "era_label": era_label,
            "material_label": material_label,
            "price_text": price_text,
            "listing_count_text": listing_count_text,
            "filter_summary": filter_summary,
            "filter_summary_parts": filter_summary_parts,
            "public_item_number": public_item_number,
            "shipping_note_text": shipping_note_text,
            "shop_text": shop_text,
            "shop_address_lines": shop_address_lines,
            "shop_apple_maps_url": shop_apple_maps_url,
            "shop_directions_url": shop_directions_url,
            "shop_has_map": shop_has_map,
            "static_asset_version": static_asset_version,
            "lang_url_en": language_url("en"),
            "lang_url_fr": language_url("fr"),
            "now_iso": datetime.now(UTC).isoformat(),
            "analytics_page_type": analytics_page_type(request.path),
            "analytics_path_key": analytics_path_key(request.path),
        }

    def listing_context(filters: dict[str, str]) -> dict[str, Any]:
        return {
            "shops": list_shops(g.db),
            "categories": list_filter_values(g.db, "category"),
            "materials": list_filter_values(g.db, "materials"),
            "designers": list_filter_values(g.db, "designer"),
            "locations": list_location_filter_values(g.db),
            "saved_searches": list_saved_searches(g.db),
        }

    @app.get("/")
    def listings() -> str:
        filters = build_listing_filters(request.args)
        offset = max(request.args.get("offset", default=0, type=int) or 0, 0)
        listing_total_count = count_listings(g.db, filters, include_inactive=False)
        rows = query_listings(
            g.db,
            filters,
            include_inactive=False,
            limit=LISTING_PAGE_SIZE,
            offset=offset,
        )
        next_offset = offset + len(rows)
        has_more_listings = next_offset < listing_total_count
        next_page_url = ""
        if has_more_listings:
            next_args = request.args.copy()
            next_args["offset"] = str(next_offset)
            next_page_url = f"{url_for('listings')}?{urlencode(next_args, doseq=True)}"
        template = (
            "_listing_cards.html"
            if request.headers.get("HX-Request") and offset
            else "_listing_grid.html"
            if request.headers.get("HX-Request")
            else "listings.html"
        )
        context = {}
        if not (request.headers.get("HX-Request") and offset):
            context = listing_context(filters)
            page_description = translator_for(g.lang)("site.tagline")
            context["page_description"] = page_description
            context["structured_data"] = [
                base_structured_data(app.config["MCM_PUBLIC_BASE_URL"]),
                collection_structured_data(
                    app.config["MCM_PUBLIC_BASE_URL"],
                    "/",
                    "Montreal MCM",
                    page_description,
                ),
            ]
        return render_template(
            template,
            listings=rows,
            listing_total_count=listing_total_count,
            has_more_listings=has_more_listings,
            next_page_url=next_page_url,
            filters=filters,
            **context,
        )

    @app.get("/categories/<slug>")
    def category_detail(slug: str) -> str:
        category = category_from_slug(slug)
        if category is None:
            abort(404)
        filters = build_listing_filters({"category": category})
        offset = max(request.args.get("offset", default=0, type=int) or 0, 0)
        listing_total_count = count_listings(g.db, filters, include_inactive=False)
        rows = query_listings(
            g.db,
            filters,
            include_inactive=False,
            limit=LISTING_PAGE_SIZE,
            offset=offset,
        )
        next_offset = offset + len(rows)
        has_more_listings = next_offset < listing_total_count
        next_page_url = ""
        if has_more_listings:
            next_args = request.args.copy()
            next_args["offset"] = str(next_offset)
            next_page_url = (
                f"{url_for('category_detail', slug=slug)}?{urlencode(next_args, doseq=True)}"
            )
        template = (
            "_listing_cards.html"
            if request.headers.get("HX-Request") and offset
            else "listings.html"
        )
        context = {}
        if not (request.headers.get("HX-Request") and offset):
            context = listing_context(filters)
            category_name = category_label(category)
            page_title = translator_for(g.lang)("meta.category_title", category=category_name)
            page_description = translator_for(g.lang)(
                "meta.category_description", category=category_name
            )
            context.update(
                {
                    "page_title": page_title,
                    "page_description": page_description,
                    "structured_data": [
                        base_structured_data(app.config["MCM_PUBLIC_BASE_URL"]),
                        collection_structured_data(
                            app.config["MCM_PUBLIC_BASE_URL"],
                            f"/categories/{slug}",
                            page_title,
                            page_description,
                        ),
                    ],
                }
            )
        return render_template(
            template,
            listings=rows,
            listing_total_count=listing_total_count,
            has_more_listings=has_more_listings,
            next_page_url=next_page_url,
            filters=filters,
            **context,
        )

    @app.post("/saved-searches")
    def create_saved_search() -> Any:
        form_data = request.form
        if not any(value.strip() for value in form_data.values()) and request.referrer:
            referrer = urlparse(request.referrer)
            allowed_referrer_hosts = {
                request.host.split(":", 1)[0],
                "montrealmcm.ca",
                "www.montrealmcm.ca",
            }
            if referrer.hostname in allowed_referrer_hosts:
                form_data = MultiDict(parse_qsl(referrer.query, keep_blank_values=True))
        filters = build_listing_filters(form_data)
        query_string = saved_search_query_string(filters)
        if query_string:
            ensure_anonymous_identity(app, g.db)
            save_search(g.db, saved_search_name(filters), query_string)
        return redirect(url_for("favourites"))

    @app.get("/saved-searches")
    def saved_searches() -> Any:
        return redirect(url_for("favourites"))

    @app.post("/analytics/pageview")
    def analytics_pageview() -> tuple[str, int]:
        if not request_origin_is_allowed():
            return "", 204
        payload = request.get_json(silent=True) or {}
        path = payload.get("path") if isinstance(payload, dict) else ""
        lang = payload.get("lang") if isinstance(payload, dict) else ""
        if isinstance(path, str) and path:
            record_analytics_pageview(g.db, path, lang if isinstance(lang, str) else "")
        return "", 204

    @app.post("/saved-searches/<int:saved_search_id>/delete")
    def remove_saved_search(saved_search_id: int) -> Any:
        delete_saved_search(g.db, saved_search_id)
        return redirect(url_for("favourites"))

    @app.get("/healthz")
    def healthz() -> tuple[str, int]:
        return "ok", 200

    @app.get("/readyz")
    def readyz() -> tuple[str, int]:
        return "ok", 200

    @app.get("/manifest.webmanifest")
    def web_manifest() -> Response:
        return Response(
            (BASE_DIR / "static" / "manifest.webmanifest").read_text(),
            content_type="application/manifest+json",
        )

    @app.get("/service-worker.js")
    def service_worker() -> Response:
        response = Response(
            (BASE_DIR / "static" / "service-worker.js").read_text(),
            content_type="application/javascript; charset=utf-8",
        )
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/robots.txt")
    def robots_txt() -> Response:
        sitemap_url = absolute_public_url(app.config["MCM_PUBLIC_BASE_URL"], "/sitemap.xml")
        return Response(
            f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n",
            content_type="text/plain; charset=utf-8",
        )

    @app.get("/sitemap.xml")
    def sitemap_xml() -> Response:
        static_paths = ["/", "/shops"]
        urls = [
            {"loc": absolute_public_url(app.config["MCM_PUBLIC_BASE_URL"], path), "lastmod": ""}
            for path in static_paths
        ]
        urls.extend(
            {
                "loc": absolute_public_url(
                    app.config["MCM_PUBLIC_BASE_URL"],
                    f"/categories/{category_slug(category)}",
                ),
                "lastmod": "",
            }
            for category in list_filter_values(g.db, "category")
        )
        urls.extend(
            {
                "loc": absolute_public_url(
                    app.config["MCM_PUBLIC_BASE_URL"], f"/shops/{shop['slug']}"
                ),
                "lastmod": "",
            }
            for shop in list_shops(g.db)
        )
        urls.extend(
            {
                "loc": absolute_public_url(
                    app.config["MCM_PUBLIC_BASE_URL"],
                    f"/listing/{public_item_number(int(listing['id']))}",
                ),
                "lastmod": str(
                    listing.get("last_checked_at")
                    or listing.get("last_seen_at")
                    or listing.get("first_seen_at")
                    or ""
                )[:10],
            }
            for listing in list_sitemap_listings(g.db)
        )
        url_entries = "\n".join(
            "\n".join(
                (
                    "  <url>",
                    f"    <loc>{xml_escape(url['loc'])}</loc>",
                    f"    <lastmod>{xml_escape(url['lastmod'])}</lastmod>"
                    if url["lastmod"]
                    else "",
                    "  </url>",
                )
            )
            for url in urls
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{url_entries}\n"
            "</urlset>\n"
        )
        return Response(xml, content_type="application/xml; charset=utf-8")

    @app.get("/offline")
    def offline() -> str:
        return render_template("offline.html")

    @app.errorhandler(404)
    def not_found(_error: Exception) -> tuple[str, int]:
        return render_template("404.html"), 404

    @app.get("/admin/healthz")
    @admin_required(app)
    def admin_healthz() -> tuple[dict[str, Any], int]:
        shop_count = g.db.execute("SELECT COUNT(*) AS count FROM shops").fetchone()["count"]
        listing_count = g.db.execute("SELECT COUNT(*) AS count FROM listings").fetchone()["count"]
        return {
            "status": "ok",
            "database": "ok",
            "shops": shop_count,
            "listings": listing_count,
            "checked_at": datetime.now(UTC).isoformat(),
        }, 200

    def cron_refresh_chunk(
        refresh_chunk: Callable[[Any, int], Any],
        chunk_index: int,
    ) -> tuple[dict[str, Any], int]:
        require_scheduled_request()
        try:
            chunk = refresh_chunk(g.db, chunk_index)
        except ValueError:
            abort(404)
        return chunk_refresh_payload(chunk), 502 if chunk.result.error else 200

    @app.post("/cron/refresh")
    def cron_refresh() -> Any:
        require_scheduled_request()
        refresh_all_sources(g.db)
        return {"status": "ok", "refreshed_at": datetime.now(UTC).isoformat()}

    @app.post("/cron/refresh/showroom-montreal/chunk/<int:chunk_index>")
    def cron_refresh_showroom_chunk(chunk_index: int) -> Any:
        return cron_refresh_chunk(refresh_showroom_chunk, chunk_index)

    @app.post("/cron/refresh/le-centerpiece/chunk/<int:chunk_index>")
    def cron_refresh_le_centerpiece_chunk(chunk_index: int) -> Any:
        return cron_refresh_chunk(refresh_le_centerpiece_chunk, chunk_index)

    @app.post("/cron/refresh/chez-lamothe/chunk/<int:chunk_index>")
    def cron_refresh_chez_lamothe_chunk(chunk_index: int) -> Any:
        return cron_refresh_chunk(refresh_chez_lamothe_chunk, chunk_index)

    @app.post("/cron/refresh/mostly-danish/chunk/<int:chunk_index>")
    def cron_refresh_mostly_danish_chunk(chunk_index: int) -> Any:
        return cron_refresh_chunk(refresh_mostly_danish_chunk, chunk_index)

    @app.post("/cron/reconcile/<source_slug>")
    def cron_reconcile_chunked_source(source_slug: str) -> Any:
        require_scheduled_request()
        try:
            result = reconcile_chunked_source(
                g.db,
                source_slug,
                since=request.args.get("since", ""),
            )
        except ValueError:
            abort(404)
        return {
            "status": "warning" if result.error else "ok",
            "source": result.source_slug,
            "listings": result.listings_found,
            "hidden": result.hidden_count,
            "warning": result.error,
            "reconciled_at": datetime.now(UTC).isoformat(),
        }, 409 if result.error else 200

    @app.post("/cron/refresh/<source_slug>")
    def cron_refresh_source(source_slug: str) -> Any:
        require_scheduled_request()
        try:
            result = refresh_source_by_slug(g.db, source_slug)
        except ValueError:
            abort(404)
        return {
            "status": "ok",
            "source": result.source_slug,
            "listings": result.listings_found,
            "new": result.new_count,
            "hidden": result.hidden_count,
            "warning": result.error,
            "refreshed_at": datetime.now(UTC).isoformat(),
        }

    @app.get("/listing/<item_number>")
    def listing_detail(item_number: str) -> Any:
        listing_id = listing_id_from_item_number(item_number)
        if not listing_id:
            abort(404)
        listing = get_listing(g.db, listing_id)
        if not listing:
            abort(404)
        availability = listing["availability_override"] or listing["availability_status"]
        if not listing["is_active"] or availability == "removed":
            abort(404)
        canonical_item_number = public_item_number(listing["id"])
        if item_number.upper() != canonical_item_number:
            return redirect(url_for("listing_detail", item_number=canonical_item_number))
        shop = get_shop(g.db, listing["source_shop_id"])
        if not shop:
            abort(404)
        return render_template(
            "listing_detail.html",
            listing=listing,
            shop=shop,
            price_events=list_listing_price_events(g.db, int(listing["id"])),
            availability_events=list_listing_availability_events(g.db, int(listing["id"])),
            structured_data=[
                listing_structured_data(app.config["MCM_PUBLIC_BASE_URL"], listing, shop)
            ],
        )

    @app.get("/shops")
    def shops() -> str:
        page_description = translator_for(g.lang)("meta.shops_description")
        return render_template(
            "shops.html",
            shops=list_shops(g.db),
            page_description=page_description,
            structured_data=[
                base_structured_data(app.config["MCM_PUBLIC_BASE_URL"]),
                collection_structured_data(
                    app.config["MCM_PUBLIC_BASE_URL"],
                    "/shops",
                    translator_for(g.lang)("nav.shops"),
                    page_description,
                ),
            ],
        )

    @app.get("/shops/<slug>")
    def shop_detail(slug: str) -> str:
        shop = get_shop_by_slug(g.db, slug)
        if not shop:
            abort(404)
        filters = {"shop": slug, "sort": "newest"}
        offset = max(request.args.get("offset", default=0, type=int) or 0, 0)
        listing_total_count = count_listings(g.db, filters, include_inactive=False)
        listings = query_listings(
            g.db,
            filters,
            include_inactive=False,
            limit=LISTING_PAGE_SIZE,
            offset=offset,
        )
        next_offset = offset + len(listings)
        has_more_listings = next_offset < listing_total_count
        next_page_url = ""
        if has_more_listings:
            next_args = request.args.copy()
            next_args["offset"] = str(next_offset)
            next_page_url = (
                f"{url_for('shop_detail', slug=slug)}?{urlencode(next_args, doseq=True)}"
            )
        template = (
            "_listing_cards.html"
            if request.headers.get("HX-Request") and offset
            else "shop_detail.html"
        )
        return render_template(
            template,
            shop=shop,
            listings=listings,
            listing_total_count=listing_total_count,
            has_more_listings=has_more_listings,
            next_page_url=next_page_url,
            structured_data=[
                shop_structured_data(app.config["MCM_PUBLIC_BASE_URL"], shop),
            ]
            if template == "shop_detail.html"
            else [],
        )

    @app.get("/favourites")
    def favourites() -> str:
        return render_template(
            "favourites.html",
            saved_listings=list_favourite_listings(g.db),
            saved_shops=list_favourite_shops(g.db),
            saved_searches=list_saved_searches(g.db),
        )

    @app.get("/language/<lang_code>")
    def set_language(lang_code: str) -> Any:
        session["lang"] = normalize_lang(lang_code)
        return redirect(safe_redirect_target(request.args.get("next")))

    @app.post("/favourites/listing/<int:listing_id>")
    def toggle_listing_favourite(listing_id: int) -> str:
        listing = get_listing(g.db, listing_id)
        if not listing:
            abort(404)
        ensure_anonymous_identity(app, g.db)
        toggle_favourite_listing(g.db, listing_id)
        return render_template(
            "_favourite_listing_button.html", listing=get_listing(g.db, listing_id)
        ) + render_template("_favourite_listing_count.html").replace(
            'id="favourite-count"',
            'id="favourite-count" hx-swap-oob="true"',
        )

    @app.post("/favourites/shop/<int:shop_id>")
    def toggle_shop_favourite(shop_id: int) -> str:
        shop = get_shop(g.db, shop_id)
        if not shop:
            abort(404)
        ensure_anonymous_identity(app, g.db)
        toggle_favourite_shop(g.db, shop_id)
        return render_template(
            "_favourite_shop_button.html", shop=get_shop(g.db, shop_id)
        ) + render_template("_favourite_listing_count.html").replace(
            'id="favourite-count"',
            'id="favourite-count" hx-swap-oob="true"',
        )

    @app.get("/admin")
    @admin_required(app)
    def admin_dashboard() -> str:
        return render_template(
            "admin.html",
            sources=admin_sources(g.db),
            failures=list_failures(g.db),
            listings=query_listings(g.db, {"sort": "recent_check"}, include_inactive=True)[:40],
            duplicates=find_duplicate_candidates(g.db),
            design_entity_candidates=list_design_entity_candidates(g.db),
        )

    @app.get("/admin/design-entities")
    @admin_required(app)
    def admin_design_entities() -> str:
        query = request.args.get("q", "").strip()
        return render_template(
            "admin_design_entities.html",
            entities=list_design_entities(g.db, query=query),
            query=query,
        )

    @app.post("/admin/design-entity-candidates")
    @admin_required(app)
    def admin_design_entity_candidate_update() -> Any:
        source_text = request.form.get("source_text", "").strip()
        source_role = request.form.get("source_role", "").strip()
        action = request.form.get("action", "").strip()
        if not source_text or source_role not in {"designer", "maker"}:
            return redirect(url_for("admin_dashboard"))
        if action == "approve":
            canonical_name = request.form.get("canonical_name", "").strip() or source_text
            aliases = [
                alias.strip()
                for alias in request.form.get("aliases", "").splitlines()
                if alias.strip()
            ]
            approve_design_entity_candidate(
                g.db,
                source_text=source_text,
                source_role=source_role,
                canonical_name=canonical_name,
                entity_type=request.form.get("entity_type", "creator").strip(),
                aliases=aliases,
                notes=request.form.get("notes", "").strip(),
            )
            return redirect(url_for("admin_design_entities", q=canonical_name))
        if action == "reject":
            review_design_entity_candidate(
                g.db,
                source_text=source_text,
                source_role=source_role,
                review_status="rejected",
                notes=request.form.get("notes", "").strip(),
            )
        return redirect(url_for("admin_dashboard"))

    @app.post("/admin/refresh")
    @admin_required(app)
    def admin_refresh() -> Any:
        refresh_all_sources(g.db)
        return redirect(url_for("admin_dashboard"))

    @app.post("/admin/refresh/<source_slug>")
    @admin_required(app)
    def admin_refresh_source(source_slug: str) -> Any:
        try:
            refresh_source_by_slug(g.db, source_slug)
        except ValueError:
            abort(404)
        return redirect(url_for("admin_dashboard"))

    @app.get("/admin/listings/<int:listing_id>")
    @admin_required(app)
    def admin_listing(listing_id: int) -> str:
        listing = get_listing(g.db, listing_id)
        if not listing:
            abort(404)
        return render_template("admin_listing.html", listing=listing, categories=LAUNCH_CATEGORIES)

    @app.post("/admin/listings/<int:listing_id>/design-entity")
    @admin_required(app)
    def admin_listing_design_entity_update(listing_id: int) -> Any:
        listing = get_listing(g.db, listing_id)
        if not listing:
            abort(404)
        canonical_name = request.form.get("canonical_name", "").strip()
        if not canonical_name:
            return redirect(url_for("admin_listing", listing_id=listing_id))
        evidence_role = request.form.get("evidence_role", "").strip()
        source_text = str(
            listing.get("designer") if evidence_role == "designer" else listing.get("maker") or ""
        )
        if not source_text:
            source_text = str(listing.get("designer") or listing.get("maker") or "")
        aliases = [
            alias.strip() for alias in request.form.get("aliases", "").splitlines() if alias.strip()
        ]
        entity_id = create_design_entity(
            g.db,
            canonical_name=canonical_name,
            entity_type=request.form.get("entity_type", "creator").strip(),
            aliases=aliases,
            notes=request.form.get("notes", "").strip(),
        )
        add_listing_design_entity_evidence(
            g.db,
            listing_id=listing_id,
            entity_id=entity_id,
            evidence_role=evidence_role,
            source_text=source_text,
        )
        return redirect(url_for("admin_listing", listing_id=listing_id))

    @app.post("/admin/listings/<int:listing_id>")
    @admin_required(app)
    def admin_listing_update(listing_id: int) -> Any:
        update_listing_overrides(
            g.db,
            listing_id,
            request.form.get("category_override", "").strip(),
            request.form.get("availability_override", "").strip(),
            1 if request.form.get("is_featured") else 0,
            request.form.get("manual_notes", "").strip(),
        )
        return redirect(url_for("admin_listing", listing_id=listing_id))

    return app


def admin_required(app: Flask) -> Any:
    def _decorator(view: Any) -> Any:
        @wraps(view)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            expected_token = app.config.get("MCM_ADMIN_TOKEN", "")
            if expected_token and admin_token_matches(expected_token):
                return view(*args, **kwargs)
            if not expected_token and app.config.get("MCM_ALLOW_OPEN_ADMIN"):
                return view(*args, **kwargs)
            return Response(
                "Admin authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Montreal MCM Admin"'},
            )

        return _wrapped

    return _decorator


def safe_redirect_target(target: str | None) -> str:
    if not target:
        return url_for("listings")
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return url_for("listings")
    return target


def admin_token_matches(expected_token: str) -> bool:
    provided = request.headers.get("X-MCM-Admin-Token", "")
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        provided = auth_header.removeprefix("Bearer ").strip()
    elif request.authorization and request.authorization.password:
        provided = request.authorization.password
    return secrets.compare_digest(provided, expected_token)


def main() -> None:
    app = create_app()
    with app.app_context():
        db = get_db(app)
        try:
            if len(sys.argv) > 1 and sys.argv[1] == "refresh":
                if len(sys.argv) > 2:
                    result = refresh_source_by_slug(db, sys.argv[2])
                    print(
                        f"{result.source_name}: {result.listings_found} listings, "
                        f"{result.new_count} new, {result.hidden_count} hidden"
                    )
                    return
                refresh_all_sources(db, progress=lambda message: print(message, flush=True))
                print("Refresh complete.")
                return
        finally:
            db.close()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=8000)
