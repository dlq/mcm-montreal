CREATE TABLE IF NOT EXISTS anonymous_identities (
    owner_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anonymous_favourite_listings (
    owner_key TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (owner_key, listing_id)
);

CREATE TABLE IF NOT EXISTS anonymous_favourite_shops (
    owner_key TEXT NOT NULL,
    shop_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (owner_key, shop_id)
);

CREATE INDEX IF NOT EXISTS idx_anonymous_favourite_listings_listing
    ON anonymous_favourite_listings(listing_id);

CREATE INDEX IF NOT EXISTS idx_anonymous_favourite_shops_shop
    ON anonymous_favourite_shops(shop_id);
