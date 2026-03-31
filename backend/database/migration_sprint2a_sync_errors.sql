-- Sprint 2a: Add sync error tracking columns to data_sources
ALTER TABLE public.data_sources
    ADD COLUMN IF NOT EXISTS sync_error_message TEXT,
    ADD COLUMN IF NOT EXISTS sync_error_count INTEGER NOT NULL DEFAULT 0;
