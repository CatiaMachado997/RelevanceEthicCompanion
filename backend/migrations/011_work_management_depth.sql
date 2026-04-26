-- 011_work_management_depth.sql
-- Sprint D Task 1: work-management depth
--
-- Adds:
--   1. task_dependencies (many-to-many task edges; cycle prevention enforced in service layer)
--   2. tasks.goal_id (nullable FK -> goals)
--   3. goal_milestones.target_date + goal_milestones.completed_at
--   4. v_project_rollup view
--   5. v_goal_rollup view
--
-- Idempotent: uses IF NOT EXISTS / CREATE OR REPLACE everywhere.

-- 1. task_dependencies -------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.task_dependencies (
    task_id            UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    depends_on_task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, depends_on_task_id),
    CHECK (task_id <> depends_on_task_id)
);
CREATE INDEX IF NOT EXISTS idx_task_deps_depends_on
    ON public.task_dependencies (depends_on_task_id);

-- 2. tasks.goal_id -----------------------------------------------------------
ALTER TABLE public.tasks
    ADD COLUMN IF NOT EXISTS goal_id UUID REFERENCES public.goals(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_goal_id ON public.tasks (goal_id);

-- 3. goal_milestones.target_date + completed_at ------------------------------
ALTER TABLE public.goal_milestones
    ADD COLUMN IF NOT EXISTS target_date  DATE,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- 4. v_project_rollup --------------------------------------------------------
CREATE OR REPLACE VIEW public.v_project_rollup AS
SELECT
    p.id AS project_id,
    p.user_id,
    COUNT(t.id)::int                                          AS tasks_total,
    COUNT(t.id) FILTER (WHERE t.status = 'done')::int         AS tasks_done,
    COUNT(t.id) FILTER (WHERE t.status NOT IN ('done','cancelled'))::int AS tasks_open,
    COUNT(t.id) FILTER (
        WHERE t.status NOT IN ('done','cancelled')
          AND t.due_date IS NOT NULL
          AND t.due_date < (NOW() + INTERVAL '2 days')
    )::int                                                    AS at_risk_count,
    CASE WHEN COUNT(t.id) = 0 THEN 0
         ELSE ROUND(
             100.0 * COUNT(t.id) FILTER (WHERE t.status = 'done')
                   / NULLIF(COUNT(t.id) FILTER (WHERE t.status <> 'cancelled'), 0)
         )::int
    END                                                       AS completion_pct
FROM public.projects p
LEFT JOIN public.tasks t ON t.project_id = p.id
GROUP BY p.id, p.user_id;

-- 5. v_goal_rollup -----------------------------------------------------------
CREATE OR REPLACE VIEW public.v_goal_rollup AS
WITH milestone_stats AS (
    SELECT goal_id,
           COUNT(*)::int                                  AS milestones_total,
           COUNT(*) FILTER (WHERE completed)::int         AS milestones_hit
    FROM public.goal_milestones
    GROUP BY goal_id
),
task_stats AS (
    SELECT goal_id,
           COUNT(*)::int                                  AS tasks_total,
           COUNT(*) FILTER (WHERE status = 'done')::int   AS tasks_done
    FROM public.tasks
    WHERE goal_id IS NOT NULL
    GROUP BY goal_id
)
SELECT
    g.id AS goal_id,
    g.user_id,
    COALESCE(ms.milestones_total, 0) AS milestones_total,
    COALESCE(ms.milestones_hit,   0) AS milestones_hit,
    COALESCE(ts.tasks_total,      0) AS tasks_total,
    COALESCE(ts.tasks_done,       0) AS tasks_done,
    CASE
        WHEN COALESCE(ms.milestones_total, 0) > 0
            THEN ROUND(100.0 * ms.milestones_hit / ms.milestones_total)::int
        WHEN COALESCE(ts.tasks_total, 0) > 0
            THEN ROUND(100.0 * ts.tasks_done / ts.tasks_total)::int
        ELSE 0
    END AS progress_pct
FROM public.goals g
LEFT JOIN milestone_stats ms ON ms.goal_id = g.id
LEFT JOIN task_stats      ts ON ts.goal_id = g.id;
