ALTER TABLE refresh_jobs ADD COLUMN chunk_index INTEGER;
ALTER TABLE refresh_jobs ADD COLUMN entry_url TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_refresh_jobs_source_chunk_started
    ON refresh_jobs(source_slug, chunk_index, started_at);
