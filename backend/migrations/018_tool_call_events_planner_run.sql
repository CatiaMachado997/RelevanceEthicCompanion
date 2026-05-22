-- Sprint I Task 2: cross-reference columns on tool_call_events so each
-- tool call can be grouped back into its (step, action) position within
-- the planner_runs row that produced it.
--
-- No FK constraint on planner_run_id deliberately — tool_call_events
-- rows are written DURING execution, before the planner_run is finalized.
-- We don't need referential integrity to render the UI.

ALTER TABLE public.tool_call_events
    ADD COLUMN IF NOT EXISTS planner_run_id UUID,
    ADD COLUMN IF NOT EXISTS step_index INTEGER,
    ADD COLUMN IF NOT EXISTS action_index INTEGER;

CREATE INDEX IF NOT EXISTS idx_tool_call_events_planner_run
    ON public.tool_call_events (planner_run_id)
    WHERE planner_run_id IS NOT NULL;
