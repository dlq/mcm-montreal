from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

from .db import get_db, initialize_storage
from .i18n import (
    LAUNCH_CATEGORIES,
    category_label,
    freshness_label,
    language_url,
    normalize_lang,
    resolved_language,
    shop_text,
    status_label,
    translator_for,
)
from .refresh import refresh_all_sources
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
DB_PATH = BASE_DIR / "data" / "mcm.db"


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("MCM_SECRET_KEY", f"dev-{secrets.token_hex(16)}")
    app.config["DATABASE"] = str(DB_PATH)
    if test_config:
        app.config.update(test_config)
    app.jinja_env.globals["freshness_label"] = freshness_label
    app.jinja_env.globals["json_loads"] = json.loads

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
            "category_label": category_label,
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

    @app.get("/listing/<int:listing_id>")
    def listing_detail(listing_id: int) -> str:
        listing = get_listing(g.db, listing_id)
        if not listing:
            abort(404)
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
        )

    @app.post("/favourites/shop/<int:shop_id>")
    def toggle_shop_favourite(shop_id: int) -> str:
        shop = get_shop(g.db, shop_id)
        if not shop:
            abort(404)
        toggle_favourite_shop(shop_id)
        return render_template("_favourite_shop_button.html", shop=get_shop(g.db, shop_id))

    @app.get("/admin")
    def admin_dashboard() -> str:
        return render_template(
            "admin.html",
            sources=admin_sources(g.db),
            failures=list_failures(g.db),
            listings=query_listings(g.db, {"sort": "recent_check"}, include_inactive=True)[:40],
            duplicates=find_duplicate_candidates(g.db),
        )

    @app.post("/admin/refresh")
    def admin_refresh() -> Any:
        refresh_all_sources(g.db)
        return redirect(url_for("admin_dashboard"))

    @app.get("/admin/listings/<int:listing_id>")
    def admin_listing(listing_id: int) -> str:
        listing = get_listing(g.db, listing_id)
        if not listing:
            abort(404)
        return render_template("admin_listing.html", listing=listing, categories=LAUNCH_CATEGORIES)

    @app.post("/admin/listings/<int:listing_id>")
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


def main() -> None:
    app = create_app()
    with app.app_context():
        db = get_db(app)
        try:
            if len(sys.argv) > 1 and sys.argv[1] == "refresh":
                refresh_all_sources(db, progress=lambda message: print(message, flush=True))
                print("Refresh complete.")
                return
        finally:
            db.close()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=8000)
