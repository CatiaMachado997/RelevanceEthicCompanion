-- Sprint 2a: Add raw_content column to documents for PDF inline viewing
-- Run: PGPASSWORD=postgres psql -h localhost -U postgres -d ethic_companion -f migration_sprint2a_documents_raw.sql

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS raw_content BYTEA;
