-- Sprint F Task 1: index-failure observability.
--
-- When ConnectorIndexer.index() fails to embed/write a row to Weaviate, we
-- currently log a warning and leave the row's embedding_status untouched —
-- so the user sees "47 synced" but never knows 47 of them never made it
-- into the search index.
--
-- This column captures the most recent exception message (truncated to
-- 1000 chars) for failed rows so the connectors panel can surface it.
ALTER TABLE public.source_items
    ADD COLUMN IF NOT EXISTS embedding_error TEXT;
