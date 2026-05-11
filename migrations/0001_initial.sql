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

CREATE TABLE IF NOT EXISTS listing_identity_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    source_listing_key TEXT NOT NULL,
    title TEXT NOT NULL,
    candidate_listing_ids TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE INDEX IF NOT EXISTS idx_listings_source_shop ON listings(source_shop_id);
CREATE INDEX IF NOT EXISTS idx_listings_active_availability
    ON listings(is_active, availability_status, availability_override);
CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_listings_last_checked ON listings(last_checked_at);
