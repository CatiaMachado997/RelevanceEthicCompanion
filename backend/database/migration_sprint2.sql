-- Sprint 2: Add sync error tracking to data_sources
-- Run: psql -h localhost -U postgres -d ethic_companion -f migration_sprint2.sql

ALTER TABLE data_sources
    ADD COLUMN IF NOT EXISTS sync_error_message TEXT,
    ADD COLUMN IF NOT EXISTS sync_error_count INTEGER NOT NULL DEFAULT 0;
