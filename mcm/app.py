from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, g, redirect, render_template, request, session, url_for

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
from .refresh import (
    listing_id_from_item_number,
    public_item_number,
    refresh_all_sources,
    refresh_le_centerpiece_chunk,
    refresh_showroom_chunk,
    refresh_source_by_slug,
)
from .repository import (
    admin_sources,
    build_listing_filters,
    favourite_counts,
    find_duplicate_candidates,
    get_listing,
    get_shop,
    get_shop_by_slug,
    list_failures,
    list_favourite_listings,
    list_favourite_shops,
    list_filter_values,
    list_shops,
    query_listings,
    toggle_favourite_listing,
    toggle_favourite_shop,
    update_listing_overrides,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("MCM_DATABASE", BASE_DIR / "data" / "mcm.db"))


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("MCM_SECRET_KEY", f"dev-{secrets.token_hex(16)}")
    app.config["DATABASE"] = str(DB_PATH)
    app.config["D1_BRIDGE_URL"] = os.environ.get("D1_BRIDGE_URL", "")
    app.config["D1_BRIDGE_TOKEN"] = os.environ.get("D1_BRIDGE_TOKEN", "")
    app.config["MCM_ADMIN_TOKEN"] = os.environ.get("MCM_ADMIN_TOKEN", "")
    if test_config:
        app.config.update(test_config)
    app.jinja_env.globals["freshness_label"] = freshness_label
    app.jinja_env.globals["json_loads"] = json.loads

    if not app.config.get("D1_BRIDGE_URL"):
        Path(app.config["DATABASE"]).parent.mkdir(exist_ok=True)
    initialize_storage(app)

    @app.before_request
    def open_request_resources() -> None:
        if request.endpoint == "static":
            return
        g.db = get_db(app)
        g.lang = resolved_language()

    @app.teardown_appcontext
    def close_db(exc: BaseException | None) -> None:  # noqa: ARG001
        db = getattr(g, "db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        return {
            "favourite_counts": favourite_counts(),
            "lang": g.lang,
            "t": translator_for(g.lang),
            "status_label": status_label,
            "category_list_text": category_list_text,
            "category_label": category_label,
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
            "lang_url_en": language_url("en"),
            "lang_url_fr": language_url("fr"),
            "now_iso": datetime.now(UTC).isoformat(),
        }

    @app.get("/")
    def listings() -> str:
        filters = build_listing_filters(request.args)
        rows = query_listings(g.db, filters, include_inactive=False)
        template = "_listing_grid.html" if request.headers.get("HX-Request") else "listings.html"
        return render_template(
            template,
            listings=rows,
            filters=filters,
            shops=list_shops(g.db),
            categories=list_filter_values(g.db, "category"),
            materials=list_filter_values(g.db, "materials"),
            designers=list_filter_values(g.db, "designer"),
        )

    @app.get("/healthz")
    def healthz() -> tuple[str, int]:
        return "ok", 200

    @app.get("/readyz")
    def readyz() -> tuple[str, int]:
        return "ok", 200

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

    @app.post("/cron/refresh")
    def cron_refresh() -> Any:
        if request.headers.get("X-Cloudflare-Scheduled") != "1":
            abort(404)
        refresh_all_sources(g.db)
        return {"status": "ok", "refreshed_at": datetime.now(UTC).isoformat()}

    @app.post("/cron/refresh/showroom-montreal/chunk/<int:chunk_index>")
    def cron_refresh_showroom_chunk(chunk_index: int) -> Any:
        if request.headers.get("X-Cloudflare-Scheduled") != "1":
            abort(404)
        try:
            chunk = refresh_showroom_chunk(g.db, chunk_index)
        except ValueError:
            abort(404)
        payload = {
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
        return payload, 502 if chunk.result.error else 200

    @app.post("/cron/refresh/le-centerpiece/chunk/<int:chunk_index>")
    def cron_refresh_le_centerpiece_chunk(chunk_index: int) -> Any:
        if request.headers.get("X-Cloudflare-Scheduled") != "1":
            abort(404)
        try:
            chunk = refresh_le_centerpiece_chunk(g.db, chunk_index)
        except ValueError:
            abort(404)
        payload = {
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
        return payload, 502 if chunk.result.error else 200

    @app.post("/cron/refresh/<source_slug>")
    def cron_refresh_source(source_slug: str) -> Any:
        if request.headers.get("X-Cloudflare-Scheduled") != "1":
            abort(404)
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
        return render_template("listing_detail.html", listing=listing, shop=shop)

    @app.get("/shops")
    def shops() -> str:
        return render_template("shops.html", shops=list_shops(g.db))

    @app.get("/shops/<slug>")
    def shop_detail(slug: str) -> str:
        shop = get_shop_by_slug(g.db, slug)
        if not shop:
            abort(404)
        listings = query_listings(
            g.db, {"shop": slug, "sort": "recent_check"}, include_inactive=False
        )
        return render_template("shop_detail.html", shop=shop, listings=listings)

    @app.get("/favourites")
    def favourites() -> str:
        return render_template(
            "favourites.html",
            saved_listings=list_favourite_listings(g.db),
            saved_shops=list_favourite_shops(g.db),
        )

    @app.get("/language/<lang_code>")
    def set_language(lang_code: str) -> Any:
        session["lang"] = normalize_lang(lang_code)
        return redirect(request.args.get("next") or url_for("listings"))

    @app.post("/favourites/listing/<int:listing_id>")
    def toggle_listing_favourite(listing_id: int) -> str:
        listing = get_listing(g.db, listing_id)
        if not listing:
            abort(404)
        toggle_favourite_listing(listing_id)
        return render_template(
            "_favourite_listing_button.html", listing=get_listing(g.db, listing_id)
        ) + render_template("_favourite_listing_count.html").replace(
            'id="favourite-listing-count"',
            'id="favourite-listing-count" hx-swap-oob="true"',
        )

    @app.post("/favourites/shop/<int:shop_id>")
    def toggle_shop_favourite(shop_id: int) -> str:
        shop = get_shop(g.db, shop_id)
        if not shop:
            abort(404)
        toggle_favourite_shop(shop_id)
        return render_template("_favourite_shop_button.html", shop=get_shop(g.db, shop_id))

    @app.get("/admin")
    @admin_required(app)
    def admin_dashboard() -> str:
        return render_template(
            "admin.html",
            sources=admin_sources(g.db),
            failures=list_failures(g.db),
            listings=query_listings(g.db, {"sort": "recent_check"}, include_inactive=True)[:40],
            duplicates=find_duplicate_candidates(g.db),
        )

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
            if not expected_token or admin_token_matches(expected_token):
                return view(*args, **kwargs)
            return Response(
                "Admin authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Montreal MCM Admin"'},
            )

        return _wrapped

    return _decorator


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
