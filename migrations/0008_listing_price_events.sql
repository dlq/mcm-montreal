CREATE TABLE IF NOT EXISTS listing_price_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    shop_id INTEGER NOT NULL,
    source_listing_key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    from_price_raw TEXT NOT NULL DEFAULT '',
    from_price_value REAL,
    to_price_raw TEXT NOT NULL DEFAULT '',
    to_price_value REAL,
    currency TEXT NOT NULL DEFAULT 'CAD',
    event_type TEXT NOT NULL DEFAULT 'source_refresh'
);

CREATE INDEX IF NOT EXISTS idx_listing_price_events_listing
    ON listing_price_events(listing_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_listing_price_events_change
    ON listing_price_events(listing_id, from_price_value, to_price_value);
