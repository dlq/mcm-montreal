CREATE TABLE IF NOT EXISTS analytics_page_views (
    view_date TEXT NOT NULL,
    page_type TEXT NOT NULL,
    path_key TEXT NOT NULL,
    lang TEXT NOT NULL DEFAULT '',
    views INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (view_date, page_type, path_key, lang)
);

CREATE INDEX IF NOT EXISTS idx_analytics_page_views_type_date
    ON analytics_page_views(page_type, view_date);
