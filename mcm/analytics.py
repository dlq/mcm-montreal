from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .i18n import normalize_lang


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


def analytics_since_date(raw_value: str, *, default_days: int = 14) -> str:
    if raw_value:
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    return (datetime.now(UTC).date() - timedelta(days=default_days - 1)).isoformat()
