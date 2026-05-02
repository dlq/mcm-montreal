from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

from .sources import SOURCE_DEFINITIONS, fetch_source_listings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "mcm.db"
SUPPORTED_LANGS = {"en", "fr"}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "nav.listings": "Listings",
        "nav.shops": "Shops",
        "nav.favourites": "Favourites",
        "nav.admin": "Admin",
        "nav.log_in": "Log in",
        "nav.log_out": "Log out",
        "site.tagline": "Montreal-first discovery for vintage and resale mid-century modern furniture.",
        "lang.en": "English",
        "lang.fr": "Français",
        "filters.browse": "Browse",
        "filters.title": "Curated filters",
        "filters.search": "Search",
        "filters.search_placeholder": "teak sideboard, Hans Wegner",
        "filters.shop": "Shop",
        "filters.all_shops": "All shops",
        "filters.min_price": "Min price",
        "filters.max_price": "Max price",
        "filters.category": "Category",
        "filters.all_categories": "All categories",
        "filters.material": "Material",
        "filters.all_materials": "All materials",
        "filters.designer": "Designer / maker",
        "filters.all_designers": "All designers / makers",
        "filters.location": "Location",
        "filters.location_placeholder": "Montreal, Ottawa, Toronto",
        "filters.availability": "Availability",
        "filters.sort": "Sort",
        "filters.available_only": "Available only",
        "filters.unknown": "Unknown",
        "filters.sold_out": "Sold out",
        "filters.all_statuses": "All statuses",
        "filters.newest": "Newest found",
        "filters.recent_check": "Most recently checked",
        "filters.price_low": "Price low to high",
        "filters.price_high": "Price high to low",
        "filters.recent_source": "Recently added by source",
        "filters.ships_to_montreal": "Ships to Montreal",
        "filters.apply": "Apply filters",
        "filters.reset": "Reset",
        "filters.default_summary": "Showing the default curated feed.",
        "listing.count": "{count} listings",
        "listing.image_pending": "Image pending from source",
        "listing.badge.shipping": "Ships to Montreal",
        "listing.badge.local": "Montreal local source",
        "listing.quote_required": "Quote required",
        "listing.default_location": "Canada",
        "listing.no_results": "No listings matched these filters yet.",
        "listing.save": "Save",
        "listing.saved": "Saved",
        "listing.source_notes": "Source notes",
        "listing.view_original": "View original listing",
        "listing.visit_shop": "Visit shop site",
        "listing.shipping_note": "Shipping note",
        "listing.freshness": "Freshness",
        "listing.last_checked": "last checked {value}",
        "listing.shop": "Shop",
        "listing.location": "Location",
        "listing.materials": "Materials",
        "listing.dimensions": "Dimensions",
        "listing.era": "Era",
        "listing.condition": "Condition",
        "listing.uncategorized": "Uncategorized",
        "listing.not_parsed": "Not parsed yet",
        "listing.era_unknown": "Approximate decade unavailable",
        "listing.condition_unknown": "Condition notes unavailable",
        "home.phase": "Phase 1",
        "home.hero": "Live-looking inventory from the Montreal launch sources.",
        "home.current_results": "current results",
        "home.launch_shops": "launch shops",
        "home.daily_value": "daily",
        "home.refresh_target": "refresh target",
        "home.canada_friendly": "Canada-friendly",
        "shops.sources": "Sources",
        "shops.title": "Launch shops",
        "shops.subtitle": "Direct-shop-first profiles with local shipping context, active listing counts, and a quick path back to each seller.",
        "shops.local": "Montreal local",
        "shops.canada_friendly": "Canada-friendly",
        "shops.active_listings": "Active listings",
        "shops.shipping": "Shipping",
        "shops.categories": "Categories",
        "shops.categories_fallback": "Still building",
        "shop.shipping_summary": "Shipping summary",
        "shop.style_focus": "Style focus",
        "shop.source_site": "Source site",
        "shop.notes": "Notes",
        "shop.current_listings": "Current listings",
        "favourites.saved": "Saved",
        "favourites.title": "Your shortlist",
        "favourites.subtitle": "Saved listings and shops stay in this browser using local session storage.",
        "favourites.saved_listings": "Saved listings",
        "favourites.saved_shops": "Saved shops",
        "favourites.no_saved_shops": "No saved shops yet.",
        "shop.save": "Save shop",
        "shop.saved": "Saved shop",
        "admin.title": "Review queue and crawl health",
        "admin.subtitle": "Phase 1 internal tools for source status, failure review, manual overrides, and duplicate inspection.",
        "admin.refresh": "Refresh all launch sources",
        "admin.source_health": "Source list and crawl health",
        "admin.shop": "Shop",
        "admin.status": "Status",
        "admin.listings": "Listings",
        "admin.last_run": "Last run",
        "admin.not_run_yet": "not run yet",
        "admin.pending": "pending",
        "admin.listing_inspection": "Listing inspection",
        "admin.failed_review": "Failed page review",
        "admin.no_failures": "No recent crawl failures.",
        "admin.duplicate_review": "Duplicate review queue",
        "admin.no_duplicates": "No strong duplicate candidates yet.",
        "admin.similarity": "Similarity {score}",
        "admin.parse_confidence": "parse confidence {value}%",
        "admin.source_url": "Source URL",
        "admin.current_status": "Current status",
        "admin.current_category": "Current category",
        "admin.price": "Price",
        "admin.last_seen": "Last seen",
        "admin.last_checked": "Last checked",
        "admin.manual_overrides": "Manual overrides",
        "admin.category_override": "Category override",
        "admin.use_parsed_category": "Use parsed category",
        "admin.availability_override": "Availability override",
        "admin.use_parsed_status": "Use parsed status",
        "admin.featured_listing": "Featured listing",
        "admin.manual_notes": "Manual notes",
        "admin.save_overrides": "Save overrides",
        "freshness.today": "Checked today",
        "freshness.week": "Checked this week",
        "freshness.stale": "Needs refresh",
        "status.available": "Available",
        "status.sold_out": "Sold out",
        "status.unknown": "Unknown",
        "status.removed": "Removed",
        "category.sideboards / credenzas": "sideboards / credenzas",
        "category.dressers / commodes": "dressers / commodes",
        "category.dining tables": "dining tables",
        "category.dining chairs": "dining chairs",
        "category.lounge chairs": "lounge chairs",
        "category.sofas": "sofas",
        "category.coffee tables": "coffee tables",
        "category.desks": "desks",
        "category.bookshelves / wall units": "bookshelves / wall units",
        "category.nightstands": "nightstands",
        "category.beds / bedroom storage": "beds / bedroom storage",
        "category.lighting": "lighting",
        "category.furniture": "furniture",
    },
    "fr": {
        "nav.listings": "Annonces",
        "nav.shops": "Boutiques",
        "nav.favourites": "Favoris",
        "nav.admin": "Admin",
        "nav.log_in": "Connexion",
        "nav.log_out": "Déconnexion",
        "site.tagline": "Découverte montréalaise de mobilier mid-century modern vintage et de revente.",
        "lang.en": "English",
        "lang.fr": "Français",
        "filters.browse": "Parcourir",
        "filters.title": "Filtres choisis",
        "filters.search": "Recherche",
        "filters.search_placeholder": "buffet en teck, Hans Wegner",
        "filters.shop": "Boutique",
        "filters.all_shops": "Toutes les boutiques",
        "filters.min_price": "Prix min.",
        "filters.max_price": "Prix max.",
        "filters.category": "Catégorie",
        "filters.all_categories": "Toutes les catégories",
        "filters.material": "Matériau",
        "filters.all_materials": "Tous les matériaux",
        "filters.designer": "Designer / fabricant",
        "filters.all_designers": "Tous les designers / fabricants",
        "filters.location": "Lieu",
        "filters.location_placeholder": "Montréal, Ottawa, Toronto",
        "filters.availability": "Disponibilité",
        "filters.sort": "Tri",
        "filters.available_only": "Disponibles seulement",
        "filters.unknown": "Inconnue",
        "filters.sold_out": "Vendu",
        "filters.all_statuses": "Tous les statuts",
        "filters.newest": "Ajouts récents",
        "filters.recent_check": "Vérifiés récemment",
        "filters.price_low": "Prix croissant",
        "filters.price_high": "Prix décroissant",
        "filters.recent_source": "Ajoutés récemment par la source",
        "filters.ships_to_montreal": "Livraison à Montréal",
        "filters.apply": "Appliquer les filtres",
        "filters.reset": "Réinitialiser",
        "filters.default_summary": "Affichage du fil sélectionné par défaut.",
        "listing.count": "{count} annonces",
        "listing.image_pending": "Image en attente de la source",
        "listing.badge.shipping": "Livraison à Montréal",
        "listing.badge.local": "Source locale de Montréal",
        "listing.quote_required": "Prix sur demande",
        "listing.default_location": "Canada",
        "listing.no_results": "Aucune annonce ne correspond encore à ces filtres.",
        "listing.save": "Sauvegarder",
        "listing.saved": "Sauvegardé",
        "listing.source_notes": "Notes de source",
        "listing.view_original": "Voir l’annonce d’origine",
        "listing.visit_shop": "Visiter le site de la boutique",
        "listing.shipping_note": "Note de livraison",
        "listing.freshness": "Fraîcheur",
        "listing.last_checked": "dernière vérification {value}",
        "listing.shop": "Boutique",
        "listing.location": "Lieu",
        "listing.materials": "Matériaux",
        "listing.dimensions": "Dimensions",
        "listing.era": "Époque",
        "listing.condition": "État",
        "listing.uncategorized": "Sans catégorie",
        "listing.not_parsed": "Pas encore analysé",
        "listing.era_unknown": "Décennie approximative non disponible",
        "listing.condition_unknown": "Notes d’état non disponibles",
        "home.phase": "Phase 1",
        "home.hero": "Inventaire vivant des sources de lancement montréalaises.",
        "home.current_results": "résultats actuels",
        "home.launch_shops": "boutiques de lancement",
        "home.daily_value": "quotidien",
        "home.refresh_target": "objectif de rafraîchissement",
        "home.canada_friendly": "Montréal + Canada",
        "shops.sources": "Sources",
        "shops.title": "Boutiques de lancement",
        "shops.subtitle": "Profils orientés boutiques directes avec contexte de livraison locale, nombre d’annonces actives et accès rapide à chaque vendeur.",
        "shops.local": "Montréal local",
        "shops.canada_friendly": "Compatible Canada",
        "shops.active_listings": "Annonces actives",
        "shops.shipping": "Livraison",
        "shops.categories": "Catégories",
        "shops.categories_fallback": "En cours",
        "shop.shipping_summary": "Résumé de livraison",
        "shop.style_focus": "Style",
        "shop.source_site": "Site source",
        "shop.notes": "Notes",
        "shop.current_listings": "Annonces actuelles",
        "favourites.saved": "Favoris",
        "favourites.title": "Votre sélection",
        "favourites.subtitle": "Les annonces et boutiques sauvegardées restent dans ce navigateur grâce au stockage de session local.",
        "favourites.saved_listings": "Annonces sauvegardées",
        "favourites.saved_shops": "Boutiques sauvegardées",
        "favourites.no_saved_shops": "Aucune boutique sauvegardée pour le moment.",
        "shop.save": "Sauvegarder la boutique",
        "shop.saved": "Boutique sauvegardée",
        "admin.title": "File de révision et santé du crawl",
        "admin.subtitle": "Outils internes de phase 1 pour l’état des sources, la révision des échecs, les remplacements manuels et l’inspection des doublons.",
        "admin.refresh": "Rafraîchir toutes les sources de lancement",
        "admin.source_health": "Liste des sources et santé du crawl",
        "admin.shop": "Boutique",
        "admin.status": "Statut",
        "admin.listings": "Annonces",
        "admin.last_run": "Dernière exécution",
        "admin.not_run_yet": "jamais exécuté",
        "admin.pending": "en attente",
        "admin.listing_inspection": "Inspection d’annonce",
        "admin.failed_review": "Révision des pages en échec",
        "admin.no_failures": "Aucun échec récent de crawl.",
        "admin.duplicate_review": "File de révision des doublons",
        "admin.no_duplicates": "Aucun doublon probable pour le moment.",
        "admin.similarity": "Similarité {score}",
        "admin.parse_confidence": "confiance d’analyse {value} %",
        "admin.source_url": "URL source",
        "admin.current_status": "Statut actuel",
        "admin.current_category": "Catégorie actuelle",
        "admin.price": "Prix",
        "admin.last_seen": "Dernière présence",
        "admin.last_checked": "Dernière vérification",
        "admin.manual_overrides": "Remplacements manuels",
        "admin.category_override": "Catégorie forcée",
        "admin.use_parsed_category": "Utiliser la catégorie analysée",
        "admin.availability_override": "Disponibilité forcée",
        "admin.use_parsed_status": "Utiliser le statut analysé",
        "admin.featured_listing": "Annonce en vedette",
        "admin.manual_notes": "Notes manuelles",
        "admin.save_overrides": "Enregistrer les remplacements",
        "freshness.today": "Vérifié aujourd’hui",
        "freshness.week": "Vérifié cette semaine",
        "freshness.stale": "À rafraîchir",
        "status.available": "Disponible",
        "status.sold_out": "Vendu",
        "status.unknown": "Inconnu",
        "status.removed": "Retiré",
        "category.sideboards / credenzas": "buffets / crédences",
        "category.dressers / commodes": "commodes",
        "category.dining tables": "tables à manger",
        "category.dining chairs": "chaises de salle à manger",
        "category.lounge chairs": "fauteuils",
        "category.sofas": "sofas",
        "category.coffee tables": "tables basses",
        "category.desks": "bureaux",
        "category.bookshelves / wall units": "bibliothèques / unités murales",
        "category.nightstands": "tables de chevet",
        "category.beds / bedroom storage": "lits / rangement de chambre",
        "category.lighting": "luminaires",
        "category.furniture": "mobilier",
    },
}

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


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("MCM_SECRET_KEY", f"dev-{secrets.token_hex(16)}")
    app.config["DATABASE"] = str(DB_PATH)
    app.jinja_env.globals["freshness_label"] = freshness_label
    app.jinja_env.globals["json_loads"] = json.loads

    DATA_DIR.mkdir(exist_ok=True)

    @app.before_request
    def before_request() -> None:
        g.db = get_db(app)
        g.lang = resolved_language()
        ensure_schema(g.db)
        ensure_shops_seeded(g.db)
        if not has_any_listing(g.db):
            refresh_all_sources(g.db)

    @app.teardown_request
    def teardown_request(exc: BaseException | None) -> None:  # noqa: ARG001
        db = getattr(g, "db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        counts = favourite_counts()
        translator = translator_for(g.lang)
        return {
            "favourite_counts": counts,
            "lang": g.lang,
            "t": translator,
            "status_label": status_label,
            "category_label": category_label,
            "shop_text": shop_text,
            "lang_url_en": language_url("en"),
            "lang_url_fr": language_url("fr"),
            "now_iso": datetime.now(UTC).isoformat(),
        }

    @app.get("/")
    def listings() -> str:
        filters = {
            "q": request.args.get("q", "").strip(),
            "shop": request.args.get("shop", "").strip(),
            "location": request.args.get("location", "").strip(),
            "category": request.args.get("category", "").strip(),
            "material": request.args.get("material", "").strip(),
            "designer": request.args.get("designer", "").strip(),
            "ships_to_montreal": request.args.get("ships_to_montreal", ""),
            "availability": request.args.get("availability", "available"),
            "price_min": request.args.get("price_min", "").strip(),
            "price_max": request.args.get("price_max", "").strip(),
            "sort": request.args.get("sort", "newest"),
        }
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
        return render_template(
            "listing_detail.html", listing=listing, shop=get_shop(g.db, listing["source_shop_id"])
        )

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
        saved_listings = list_favourite_listings(g.db)
        saved_shops = list_favourite_shops(g.db)
        return render_template(
            "favourites.html", saved_listings=saved_listings, saved_shops=saved_shops
        )

    @app.get("/language/<lang_code>")
    def set_language(lang_code: str) -> Any:
        session["lang"] = normalize_lang(lang_code)
        return redirect(request.args.get("next") or url_for("listings"))

    @app.post("/favourites/listing/<int:listing_id>")
    def toggle_listing_favourite(listing_id: int) -> str:
        toggle_favourite_listing(listing_id)
        listing = get_listing(g.db, listing_id)
        return render_template("_favourite_listing_button.html", listing=listing)

    @app.post("/favourites/shop/<int:shop_id>")
    def toggle_shop_favourite(shop_id: int) -> str:
        toggle_favourite_shop(shop_id)
        shop = get_shop(g.db, shop_id)
        return render_template("_favourite_shop_button.html", shop=shop)

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
        ensure_schema(db)
        ensure_shops_seeded(db)
        if len(sys.argv) > 1 and sys.argv[1] == "refresh":
            refresh_all_sources(db)
            print("Refresh complete.")
            return
    app.run(debug=True, port=8000)


def get_db(app: Flask) -> sqlite3.Connection:
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            website TEXT NOT NULL,
            city TEXT NOT NULL,
            province TEXT NOT NULL,
            country TEXT NOT NULL,
            is_montreal_local INTEGER NOT NULL DEFAULT 0,
            shipping_summary TEXT NOT NULL,
            source_type TEXT NOT NULL,
            crawl_priority INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            style_focus TEXT NOT NULL DEFAULT '',
            listing_url TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_shop_id INTEGER NOT NULL,
            source_listing_url TEXT NOT NULL,
            source_listing_key TEXT NOT NULL,
            title TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            price_raw TEXT NOT NULL DEFAULT '',
            price_value REAL,
            currency TEXT NOT NULL DEFAULT 'CAD',
            primary_image_url TEXT NOT NULL DEFAULT '',
            additional_image_urls TEXT NOT NULL DEFAULT '[]',
            availability_status TEXT NOT NULL DEFAULT 'unknown',
            shipping_scope TEXT NOT NULL DEFAULT '',
            ships_to_montreal INTEGER NOT NULL DEFAULT 0,
            shipping_note TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            subcategory TEXT NOT NULL DEFAULT '',
            designer TEXT NOT NULL DEFAULT '',
            maker TEXT NOT NULL DEFAULT '',
            era TEXT NOT NULL DEFAULT '',
            materials TEXT NOT NULL DEFAULT '',
            dimensions_text TEXT NOT NULL DEFAULT '',
            width REAL,
            depth REAL,
            height REAL,
            condition_text TEXT NOT NULL DEFAULT '',
            location_text TEXT NOT NULL DEFAULT '',
            source_description TEXT NOT NULL DEFAULT '',
            ingest_source_type TEXT NOT NULL DEFAULT '',
            parse_confidence REAL NOT NULL DEFAULT 0,
            dedupe_group_id TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            is_featured INTEGER NOT NULL DEFAULT 0,
            manual_notes TEXT NOT NULL DEFAULT '',
            availability_override TEXT NOT NULL DEFAULT '',
            category_override TEXT NOT NULL DEFAULT '',
            UNIQUE(source_shop_id, source_listing_key)
        );
        CREATE TABLE IF NOT EXISTS favourite_listings (
            user_id INTEGER NOT NULL,
            listing_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, listing_id)
        );
        CREATE TABLE IF NOT EXISTS favourite_shops (
            user_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, shop_id)
        );
        CREATE TABLE IF NOT EXISTS crawl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            ran_at TEXT NOT NULL,
            status TEXT NOT NULL,
            listings_found INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS crawl_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT ''
        );
        """
    )
    db.commit()


def ensure_shops_seeded(db: sqlite3.Connection) -> None:
    db.execute("UPDATE shops SET active = 0")
    for source in SOURCE_DEFINITIONS:
        db.execute(
            """
            INSERT INTO shops (
                slug, name, website, city, province, country, is_montreal_local,
                shipping_summary, source_type, crawl_priority, notes, description,
                style_focus, listing_url, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                website = excluded.website,
                city = excluded.city,
                province = excluded.province,
                country = excluded.country,
                is_montreal_local = excluded.is_montreal_local,
                shipping_summary = excluded.shipping_summary,
                source_type = excluded.source_type,
                crawl_priority = excluded.crawl_priority,
                notes = excluded.notes,
                description = excluded.description,
                style_focus = excluded.style_focus,
                listing_url = excluded.listing_url,
                active = 1
            """,
            (
                source.slug,
                source.name,
                source.website,
                source.city,
                source.province,
                source.country,
                1 if source.is_montreal_local else 0,
                source.shipping_summary,
                source.source_type,
                source.crawl_priority,
                source.notes,
                source.description,
                source.style_focus,
                source.listing_urls[0],
            ),
        )
    db.execute(
        """
        UPDATE listings
        SET is_active = 0
        WHERE source_shop_id IN (SELECT id FROM shops WHERE active = 0)
        """
    )
    db.commit()


def has_any_listing(db: sqlite3.Connection) -> bool:
    row = db.execute("SELECT COUNT(*) AS count FROM listings").fetchone()
    return bool(row["count"])


def refresh_all_sources(db: sqlite3.Connection) -> None:
    timestamp = datetime.now(UTC).isoformat()
    for source in SOURCE_DEFINITIONS:
        shop = get_shop_by_slug(db, source.slug)
        listings, error = fetch_source_listings(source)
        seen_keys: set[str] = set()
        for item in listings:
            source_url = item["source_listing_url"]
            key = item.get("source_listing_key") or source_url.rstrip("/").lower()
            seen_keys.add(key)
            existing = db.execute(
                "SELECT id, first_seen_at FROM listings WHERE source_shop_id = ? AND source_listing_key = ?",
                (shop["id"], key),
            ).fetchone()
            first_seen = existing["first_seen_at"] if existing else timestamp
            db.execute(
                """
                INSERT INTO listings (
                    source_shop_id, source_listing_url, source_listing_key, title, normalized_title,
                    price_raw, price_value, currency, primary_image_url, additional_image_urls,
                    availability_status, shipping_scope, ships_to_montreal, shipping_note,
                    last_seen_at, last_checked_at, first_seen_at, category, subcategory, designer,
                    maker, era, materials, dimensions_text, condition_text, location_text,
                    source_description, ingest_source_type, parse_confidence, dedupe_group_id,
                    is_active, is_featured, manual_notes, availability_override, category_override
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_shop_id, source_listing_key) DO UPDATE SET
                    source_listing_url = excluded.source_listing_url,
                    title = excluded.title,
                    normalized_title = excluded.normalized_title,
                    price_raw = excluded.price_raw,
                    price_value = excluded.price_value,
                    currency = excluded.currency,
                    primary_image_url = excluded.primary_image_url,
                    additional_image_urls = excluded.additional_image_urls,
                    availability_status = excluded.availability_status,
                    shipping_scope = excluded.shipping_scope,
                    ships_to_montreal = excluded.ships_to_montreal,
                    shipping_note = excluded.shipping_note,
                    last_seen_at = excluded.last_seen_at,
                    last_checked_at = excluded.last_checked_at,
                    category = excluded.category,
                    designer = excluded.designer,
                    maker = excluded.maker,
                    era = excluded.era,
                    materials = excluded.materials,
                    dimensions_text = excluded.dimensions_text,
                    condition_text = excluded.condition_text,
                    location_text = excluded.location_text,
                    source_description = excluded.source_description,
                    ingest_source_type = excluded.ingest_source_type,
                    parse_confidence = excluded.parse_confidence,
                    is_active = 1
                """,
                (
                    shop["id"],
                    source_url,
                    key,
                    item["title"],
                    normalize_text(item["title"]),
                    item.get("price_raw", ""),
                    item.get("price_value"),
                    item.get("currency", "CAD"),
                    item.get("primary_image_url", ""),
                    json.dumps(item.get("additional_image_urls", [])),
                    item.get("availability_status", "unknown"),
                    item.get("shipping_scope", ""),
                    item.get("ships_to_montreal", 0),
                    item.get("shipping_note", ""),
                    timestamp,
                    timestamp,
                    first_seen,
                    item.get("category", ""),
                    "",
                    item.get("designer", ""),
                    item.get("maker", ""),
                    item.get("era", ""),
                    item.get("materials", ""),
                    item.get("dimensions_text", ""),
                    item.get("condition_text", ""),
                    item.get("location_text", f"{shop['city']}, {shop['province']}"),
                    item.get("source_description", ""),
                    item.get("ingest_source_type", "refresh"),
                    float(item.get("parse_confidence", 0.4)),
                    "",
                    1,
                    0,
                    "",
                    "",
                    "",
                ),
            )
        db.execute(
            "UPDATE listings SET is_active = 0, last_checked_at = ? WHERE source_shop_id = ? AND source_listing_key NOT IN ({})".format(
                ",".join("?" for _ in seen_keys) if seen_keys else "''"
            ),
            [timestamp, shop["id"], *seen_keys],
        )
        if error:
            db.execute(
                "INSERT INTO crawl_failures (shop_id, created_at, error_message) VALUES (?, ?, ?)",
                (shop["id"], timestamp, error),
            )
        db.execute(
            "INSERT INTO crawl_runs (shop_id, ran_at, status, listings_found, error_message) VALUES (?, ?, ?, ?, ?)",
            (shop["id"], timestamp, "warning" if error else "success", len(listings), error or ""),
        )
    db.commit()


def query_listings(
    db: sqlite3.Connection, filters: dict[str, str], include_inactive: bool
) -> list[sqlite3.Row]:
    clauses = ["1=1"]
    params: list[Any] = []
    clauses.append("s.active = 1")
    if not include_inactive:
        clauses.append("l.is_active = 1")
        clauses.append(
            "COALESCE(NULLIF(l.availability_override, ''), l.availability_status) NOT IN ('removed', 'sold_out')"
        )
    if filters.get("q"):
        clauses.append(
            "(l.title LIKE ? OR l.designer LIKE ? OR l.maker LIKE ? OR l.materials LIKE ?)"
        )
        q = f"%{filters['q']}%"
        params.extend([q, q, q, q])
    if filters.get("shop"):
        clauses.append("s.slug = ?")
        params.append(filters["shop"])
    if filters.get("location"):
        clauses.append("l.location_text LIKE ?")
        params.append(f"%{filters['location']}%")
    if filters.get("category"):
        clauses.append("COALESCE(NULLIF(l.category_override, ''), l.category) = ?")
        params.append(filters["category"])
    if filters.get("material"):
        clauses.append("l.materials LIKE ?")
        params.append(f"%{filters['material']}%")
    if filters.get("designer"):
        clauses.append("(l.designer LIKE ? OR l.maker LIKE ?)")
        params.extend([f"%{filters['designer']}%", f"%{filters['designer']}%"])
    if filters.get("ships_to_montreal"):
        clauses.append("l.ships_to_montreal = 1")
    availability = filters.get("availability")
    if availability and availability != "all":
        clauses.append("COALESCE(NULLIF(l.availability_override, ''), l.availability_status) = ?")
        params.append(availability)
    if filters.get("price_min"):
        clauses.append("l.price_value >= ?")
        params.append(float(filters["price_min"]))
    if filters.get("price_max"):
        clauses.append("l.price_value <= ?")
        params.append(float(filters["price_max"]))
    order_by = {
        "newest": "l.first_seen_at DESC",
        "recent_check": "l.last_checked_at DESC",
        "price_low": "CASE WHEN l.price_value IS NULL THEN 1 ELSE 0 END, l.price_value ASC",
        "price_high": "CASE WHEN l.price_value IS NULL THEN 1 ELSE 0 END, l.price_value DESC",
        "recent_source": "l.last_seen_at DESC",
    }.get(filters.get("sort", "newest"), "l.first_seen_at DESC")
    rows = db.execute(
        f"""
        SELECT
            l.*,
            s.slug AS shop_slug,
            s.name AS shop_name,
            s.is_montreal_local
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE {" AND ".join(clauses)}
        ORDER BY {order_by}
        """,
        params,
    ).fetchall()
    return annotate_listing_rows(rows)


def get_listing(db: sqlite3.Connection, listing_id: int) -> sqlite3.Row | None:
    row = db.execute(
        """
        SELECT
            l.*,
            s.slug AS shop_slug,
            s.name AS shop_name,
            s.website AS shop_website,
            s.shipping_summary AS shop_shipping_summary,
            s.is_montreal_local
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE l.id = ?
        """,
        (listing_id,),
    ).fetchone()
    return annotate_listing_row(row) if row else None


def list_shops(db: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = db.execute(
        """
        SELECT
            s.*,
            SUM(
                CASE
                    WHEN l.is_active = 1 AND COALESCE(NULLIF(l.availability_override, ''), l.availability_status) != 'sold_out'
                    THEN 1 ELSE 0
                END
            ) AS active_listing_count,
            GROUP_CONCAT(DISTINCT COALESCE(NULLIF(l.category_override, ''), l.category)) AS categories_carried
        FROM shops s
        LEFT JOIN listings l ON l.source_shop_id = s.id
        WHERE s.active = 1
        GROUP BY s.id
        ORDER BY s.is_montreal_local DESC, s.name ASC
        """
    ).fetchall()
    return annotate_shop_rows(rows)


def get_shop(db: sqlite3.Connection, shop_id: int) -> sqlite3.Row | None:
    row = db.execute("SELECT * FROM shops WHERE id = ? AND active = 1", (shop_id,)).fetchone()
    return annotate_shop_row(row) if row else None


def get_shop_by_slug(db: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    row = db.execute("SELECT * FROM shops WHERE slug = ? AND active = 1", (slug,)).fetchone()
    return annotate_shop_row(row) if row else None


def list_filter_values(db: sqlite3.Connection, field: str) -> list[str]:
    rows = db.execute(
        f"SELECT DISTINCT {field} AS value FROM listings WHERE {field} != '' ORDER BY {field}"
    ).fetchall()
    values = []
    for row in rows:
        for chunk in str(row["value"]).split(","):
            value = chunk.strip()
            if value and value not in values:
                values.append(value)
    return values[:30]


def favourite_listing_ids() -> set[int]:
    return {int(value) for value in session.get("favourite_listing_ids", [])}


def favourite_shop_ids() -> set[int]:
    return {int(value) for value in session.get("favourite_shop_ids", [])}


def annotate_listing_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["is_favourited"] = int(payload["id"]) in favourite_listing_ids()
    return payload


def annotate_listing_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    favourites = favourite_listing_ids()
    annotated: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["is_favourited"] = int(payload["id"]) in favourites
        annotated.append(payload)
    return annotated


def annotate_shop_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["is_favourited"] = int(payload["id"]) in favourite_shop_ids()
    return payload


def annotate_shop_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    favourites = favourite_shop_ids()
    annotated: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["is_favourited"] = int(payload["id"]) in favourites
        annotated.append(payload)
    return annotated


def toggle_favourite_listing(listing_id: int) -> None:
    listing_ids = favourite_listing_ids()
    if listing_id in listing_ids:
        listing_ids.remove(listing_id)
    else:
        listing_ids.add(listing_id)
    session["favourite_listing_ids"] = sorted(listing_ids)
    session.modified = True


def toggle_favourite_shop(shop_id: int) -> None:
    shop_ids = favourite_shop_ids()
    if shop_id in shop_ids:
        shop_ids.remove(shop_id)
    else:
        shop_ids.add(shop_id)
    session["favourite_shop_ids"] = sorted(shop_ids)
    session.modified = True


def list_favourite_listings(db: sqlite3.Connection) -> list[dict[str, Any]]:
    listing_ids = session.get("favourite_listing_ids", [])
    if not listing_ids:
        return []
    placeholders = ",".join("?" for _ in listing_ids)
    rows = db.execute(
        f"""
        SELECT l.*, s.slug AS shop_slug, s.name AS shop_name, s.is_montreal_local
        FROM listings l
        JOIN shops s ON s.id = l.source_shop_id
        WHERE l.id IN ({placeholders})
        """,
        listing_ids,
    ).fetchall()
    ordered_rows = annotate_listing_rows(rows)
    positions = {int(listing_id): index for index, listing_id in enumerate(listing_ids)}
    ordered_rows.sort(key=lambda row: positions.get(int(row["id"]), 0))
    return ordered_rows


def list_favourite_shops(db: sqlite3.Connection) -> list[dict[str, Any]]:
    shop_ids = session.get("favourite_shop_ids", [])
    if not shop_ids:
        return []
    placeholders = ",".join("?" for _ in shop_ids)
    rows = db.execute(
        f"""
        SELECT s.*
        FROM shops s
        WHERE s.id IN ({placeholders}) AND s.active = 1
        """,
        shop_ids,
    ).fetchall()
    ordered_rows = annotate_shop_rows(rows)
    positions = {int(shop_id): index for index, shop_id in enumerate(shop_ids)}
    ordered_rows.sort(key=lambda row: positions.get(int(row["id"]), 0))
    return ordered_rows


def favourite_counts() -> dict[str, int]:
    return {
        "listings": len(session.get("favourite_listing_ids", [])),
        "shops": len(session.get("favourite_shop_ids", [])),
    }


def admin_sources(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT
            s.*,
            MAX(cr.ran_at) AS last_run_at,
            MAX(cr.status) AS last_status,
            MAX(cr.error_message) AS last_error,
            SUM(CASE WHEN l.is_active = 1 THEN 1 ELSE 0 END) AS active_listing_count
        FROM shops s
        LEFT JOIN crawl_runs cr ON cr.shop_id = s.id
        LEFT JOIN listings l ON l.source_shop_id = s.id
        WHERE s.active = 1
        GROUP BY s.id
        ORDER BY s.crawl_priority ASC, s.name ASC
        """
    ).fetchall()


def list_failures(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT cf.*, s.name AS shop_name
        FROM crawl_failures cf
        JOIN shops s ON s.id = cf.shop_id
        ORDER BY cf.created_at DESC
        LIMIT 20
        """
    ).fetchall()


def update_listing_overrides(
    db: sqlite3.Connection,
    listing_id: int,
    category_override: str,
    availability_override: str,
    is_featured: int,
    manual_notes: str,
) -> None:
    db.execute(
        """
        UPDATE listings
        SET category_override = ?, availability_override = ?, is_featured = ?, manual_notes = ?
        WHERE id = ?
        """,
        (category_override, availability_override, is_featured, manual_notes, listing_id),
    )
    db.commit()


def find_duplicate_candidates(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT id, title, normalized_title, source_shop_id
        FROM listings
        WHERE is_active = 1
        ORDER BY normalized_title
        """
    ).fetchall()
    groups: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        for other in rows[idx + 1 : idx + 12]:
            if row["source_shop_id"] == other["source_shop_id"]:
                continue
            score = similarity_score(row["normalized_title"], other["normalized_title"])
            if score >= 0.72:
                groups.append(
                    {
                        "left": get_listing(db, row["id"]),
                        "right": get_listing(db, other["id"]),
                        "score": round(score, 2),
                    }
                )
                if len(groups) >= 12:
                    return groups
    return groups


def normalize_text(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else " " for ch in text).strip()


def similarity_score(a: str, b: str) -> float:
    left = set(a.split())
    right = set(b.split())
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def freshness_label(iso_value: str) -> str:
    checked = datetime.fromisoformat(iso_value)
    age = datetime.now(UTC) - checked
    if age <= timedelta(days=1):
        return translate("freshness.today")
    if age <= timedelta(days=7):
        return translate("freshness.week")
    return translate("freshness.stale")


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
