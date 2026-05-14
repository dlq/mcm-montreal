CREATE TABLE IF NOT EXISTS listing_availability_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    shop_id INTEGER NOT NULL,
    source_listing_key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    from_status TEXT NOT NULL DEFAULT '',
    to_status TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'source_refresh'
);

CREATE INDEX IF NOT EXISTS idx_listing_availability_events_listing
    ON listing_availability_events(listing_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_listing_availability_events_transition
    ON listing_availability_events(listing_id, from_status, to_status);
