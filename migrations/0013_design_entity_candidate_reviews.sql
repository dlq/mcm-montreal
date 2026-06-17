CREATE TABLE IF NOT EXISTS design_entity_candidate_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_role TEXT NOT NULL,
    source_text TEXT NOT NULL,
    normalized_source_text TEXT NOT NULL,
    review_status TEXT NOT NULL,
    entity_id INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_role, normalized_source_text)
);

CREATE INDEX IF NOT EXISTS idx_design_entity_candidate_reviews_status
    ON design_entity_candidate_reviews(review_status, source_role);
