-- Preserve uploaded document bytes so files can be viewed and reprocessed.
-- The documents table predates this field in some local installations, while
-- newer route code already reads and writes it.
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS raw_content BYTEA;
