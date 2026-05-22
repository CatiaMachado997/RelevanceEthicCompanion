-- Sprint J Task 2: master safety toggle.
--
-- When safe_mode_enabled is true, every tool action pauses via the
-- LangGraph interrupt() inside tool_execution_node, regardless of the
-- per-category or per-tool preference layers. Default: false (no
-- friction unless the user opts in).

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS safe_mode_enabled BOOLEAN NOT NULL DEFAULT FALSE;
