CREATE TABLE IF NOT EXISTS anonymous_saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_key TEXT NOT NULL,
    name TEXT NOT NULL,
    query_string TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(owner_key, query_string)
);

CREATE INDEX IF NOT EXISTS idx_anonymous_saved_searches_owner
    ON anonymous_saved_searches(owner_key, updated_at);
