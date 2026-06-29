from __future__ import annotations

import sqlite3
from typing import Any


def list_analytics_daily_totals(
    db: sqlite3.Connection, *, since_date: str, limit: int = 30
) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT
            view_date,
            SUM(views) AS views,
            COUNT(*) AS path_count
        FROM analytics_page_views
        WHERE view_date >= ?
        GROUP BY view_date
        ORDER BY view_date DESC
        LIMIT ?
        """,
        (since_date, limit),
    ).fetchall()
    return [
        {
            "view_date": str(row["view_date"]),
            "views": int(row["views"]),
            "path_count": int(row["path_count"]),
        }
        for row in rows
    ]


def list_analytics_page_type_totals(
    db: sqlite3.Connection, *, since_date: str, limit: int = 20
) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT
            page_type,
            SUM(views) AS views,
            COUNT(DISTINCT path_key || '|' || lang) AS path_count
        FROM analytics_page_views
        WHERE view_date >= ?
        GROUP BY page_type
        ORDER BY views DESC, page_type ASC
        LIMIT ?
        """,
        (since_date, limit),
    ).fetchall()
    return [
        {
            "page_type": str(row["page_type"]),
            "views": int(row["views"]),
            "path_count": int(row["path_count"]),
        }
        for row in rows
    ]


def list_analytics_top_paths(
    db: sqlite3.Connection, *, since_date: str, limit: int = 20
) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT
            page_type,
            path_key,
            lang,
            SUM(views) AS views
        FROM analytics_page_views
        WHERE view_date >= ?
        GROUP BY page_type, path_key, lang
        ORDER BY views DESC, page_type ASC, path_key ASC, lang ASC
        LIMIT ?
        """,
        (since_date, limit),
    ).fetchall()
    return [
        {
            "page_type": str(row["page_type"]),
            "path_key": str(row["path_key"]),
            "lang": str(row["lang"]),
            "views": int(row["views"]),
        }
        for row in rows
    ]
