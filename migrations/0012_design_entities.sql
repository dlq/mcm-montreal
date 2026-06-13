CREATE TABLE IF NOT EXISTS design_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'creator',
    review_status TEXT NOT NULL DEFAULT 'approved',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS design_entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    normalized_alias TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL,
    UNIQUE(entity_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS listing_design_entity_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    evidence_role TEXT NOT NULL,
    source_text TEXT NOT NULL,
    normalized_source_text TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    review_status TEXT NOT NULL DEFAULT 'approved',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(listing_id, entity_id, evidence_role, normalized_source_text)
);

CREATE INDEX IF NOT EXISTS idx_design_entity_aliases_entity
    ON design_entity_aliases(entity_id);

CREATE INDEX IF NOT EXISTS idx_listing_design_entity_evidence_listing
    ON listing_design_entity_evidence(listing_id, evidence_role);

CREATE INDEX IF NOT EXISTS idx_listing_design_entity_evidence_entity
    ON listing_design_entity_evidence(entity_id);
