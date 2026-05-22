# Sprint D — Work Management Depth

Date: 2026-04-26
Status: Plan
Predecessors: Sprint A (RAG/citations) ✅, Sprint B (Connector framework) ✅
Note: Sprint C (Agentic Workspace Unification) deferred at user request — Sprint D goes first.

## Goal

Make tasks, projects, and goals first-class with **dependencies, milestones, and rollup reporting** — and surface a **weekly review** UX that uses real project state. ESL guards every user-visible mutation as usual.

## North-star UX after this sprint

1. User opens a task drawer and sees "Blocks: 2 tasks · Blocked by: 1 task" with click-through.
2. User opens a project and sees "62% complete · 3 of 5 milestones hit · 2 tasks at risk."
3. Each Monday the dashboard surfaces a **Weekly Review card**: "Last week: 8 tasks done, 1 milestone hit, 2 carry-overs. This week: 3 tasks due, 1 milestone deadline."
4. Tasks can link directly to goals (not only via project), so cross-project goals work.

## Architecture decisions

- **Dependencies as edges, not columns.** New `task_dependencies(task_id, depends_on_task_id)` table — many-to-many, cycle-prevented at insert time. Avoids array columns that fight Postgres FK semantics.
- **Rollups computed, not stored.** `project.completion_pct` and `goal.progress_pct` are derived in a SQL view + a thin service method, not persisted. Cheaper than maintaining triggers, and the values are always fresh. If perf bites later we add a materialized view.
- **Weekly review = read-only aggregator.** No new ESL surface. It reads existing tables and presents them. The optional "send me this Monday morning" notification is gated by ESL exactly like the existing daily focus plan.
- **Direct `tasks.goal_id` FK.** Nullable, in addition to `tasks.project_id`. Enables tasks pinned to a goal without a project (common for personal goals).

## File map

### Backend

**New:**
- `backend/migrations/011_work_management_depth.sql` — `task_dependencies` table, `tasks.goal_id` column, `goal_milestones.target_date` + `goal_milestones.completed_at` columns, view `v_project_rollup`, view `v_goal_rollup`.
- `backend/services/work_rollups.py` — `get_project_rollup(project_id)`, `get_goal_rollup(goal_id)`, `get_weekly_review(user_id, week_start=None)`. Pure read service.
- `backend/services/task_dependencies.py` — `add_dependency(task_id, depends_on)`, `remove_dependency(...)`, `get_blockers(task_id)`, `get_blocked_by(task_id)`, cycle check via recursive CTE.
- `backend/routes/weekly_review.py` — `GET /api/weekly-review`.
- `backend/tests/test_task_dependencies.py` — add/remove, cycle prevention, transitive blocker query.
- `backend/tests/test_work_rollups.py` — project completion %, goal progress %, weekly review aggregation.
- `backend/tests/test_weekly_review_route.py` — route smoke test.

**Modified:**
- `backend/routes/tasks.py` — accept optional `goal_id` in POST/PATCH; expose `GET /api/tasks/{id}/dependencies` and `POST /api/tasks/{id}/dependencies` + DELETE.
- `backend/routes/projects.py` — `GET /api/projects/{id}` includes `rollup: {completion_pct, tasks_open, tasks_done, at_risk_count}`.
- `backend/routes/goals.py` — `GET /api/goals/{id}` includes `rollup: {progress_pct, milestones_hit, milestones_total}`.
- `backend/routes/dashboard.py` — add `weekly_review_summary` to overview if it's the start of a new week.
- `backend/main.py` — include weekly_review router.

### Frontend

**New:**
- `frontend/components/tasks/DependencyChips.tsx` — renders blockers/blocked_by as chips inside TaskDrawer.
- `frontend/components/tasks/AddDependencyDialog.tsx` — autocomplete-search a task and link it.
- `frontend/components/projects/ProjectRollupCard.tsx` — completion bar + at-risk badges.
- `frontend/components/goals/GoalProgressCard.tsx` — milestone checklist with deadlines, progress %.
- `frontend/app/dashboard/weekly-review/page.tsx` — full weekly review page.
- `frontend/components/dashboard/WeeklyReviewCard.tsx` — compact card on the main dashboard, links to the page.

**Modified:**
- `frontend/components/drawers/TaskDrawer.tsx` — embed `<DependencyChips>` and `<AddDependencyDialog>`; add `goal_id` selector.
- `frontend/app/dashboard/projects/[id]/page.tsx` (or wherever project detail lives) — embed `<ProjectRollupCard>`.
- `frontend/app/dashboard/goals/page.tsx` — embed `<GoalProgressCard>` per goal.
- `frontend/app/dashboard/page.tsx` — render `<WeeklyReviewCard>` on Mondays (or always, with "this week" framing).
- `frontend/lib/api.ts` — `tasksApi.addDependency / removeDependency / listDependencies`, `projectsApi.getRollup`, `goalsApi.getRollup`, `weeklyReviewApi.get`.

## Tasks (one commit each, TDD)

### 1. Migration: `task_dependencies`, `tasks.goal_id`, milestone dates, rollup views.
SQL only. Cycle prevention enforced in service layer (Postgres `CHECK` cannot express graph cycles). Verify migration applies clean and rolls forward from the prior state.

### 2. `services/task_dependencies.py` + tests.
- `add_dependency(task_id, depends_on)` — rejects self-dependency, rejects if creating a cycle (recursive CTE walk from `depends_on` to see if `task_id` is reachable; if yes, reject).
- `get_blockers(task_id)` — direct + transitive (recursive CTE).
- `get_blocked_by(task_id)` — same, inverted direction.
- 4 tests: simple add, self-dependency rejected, cycle rejected (A→B→C, then C→A blocked), transitive blocker chain.

### 3. `services/work_rollups.py` + tests.
- `get_project_rollup(project_id)` — query `v_project_rollup`, return dict.
- `get_goal_rollup(goal_id)` — same for goal.
- `get_weekly_review(user_id, week_start=None)` — week defaults to most recent Monday 00:00 user-local (UTC for now, timezone refinement later). Returns: `{period: {start, end}, completed_tasks, completed_milestones, carry_over_tasks, upcoming_tasks, upcoming_milestones}`.
- 5 tests: project with 0 tasks (0%), project all done (100%), goal with mixed milestones, weekly review pulls correct window, empty user returns zeroed shape.

### 4. Tasks route updates.
- Accept `goal_id` in create/patch.
- Add 3 dependency sub-routes.
- Tests: 3 route tests + extend existing `test_tasks_routes.py`.

### 5. Projects + Goals route rollup expansion.
- Inline `rollup` in detail responses.
- 2 tests.

### 6. Weekly review route.
- `GET /api/weekly-review?week_start=YYYY-MM-DD`.
- Wire into `main.py`.
- 1 route test.

### 7. Frontend: `lib/api.ts` helpers.
Add typed helpers for everything new. Typecheck must stay clean.

### 8. Frontend: TaskDrawer dependency UI.
- `DependencyChips` reads `tasksApi.listDependencies(taskId)`.
- `AddDependencyDialog` does autocomplete via `tasksApi.list({search})` if it exists, otherwise fetches all and filters client-side.
- Goal selector dropdown (existing goals list).

### 9. Frontend: ProjectRollupCard + GoalProgressCard.
Pure presentational; data fetched in the parent page.

### 10. Frontend: Weekly review page + dashboard card.
- Full page at `/dashboard/weekly-review` with completed/upcoming sections.
- Compact `<WeeklyReviewCard>` on dashboard linking to the page.

### 11. ESL touch points.
None new. Dependency mutations are user-initiated CRUD on the user's own data; existing route-level auth is sufficient. The weekly review aggregator is read-only. Document this decision in the route docstring.

### 12. Full backend suite + frontend typecheck.
`pytest --tb=short -q` ; `cd frontend && npx tsc --noEmit`. Both green before sprint closes.

## Verification

```bash
# Backend
cd backend
pytest tests/test_task_dependencies.py tests/test_work_rollups.py tests/test_weekly_review_route.py -v
pytest --tb=short -q

# Frontend
cd frontend
npx tsc --noEmit
```

**Manual checklist:**
1. Create two tasks, link one as blocker of the other → drawer shows the relationship both ways.
2. Try to create a cycle → API rejects with a clear error.
3. Mark a task done → project rollup % climbs.
4. Hit milestone target_date in past with `completed=false` → goal rollup shows it as overdue.
5. Open `/dashboard/weekly-review` → see real numbers from the user's actual tasks/milestones over the past 7 days.
6. ESL audit log unchanged for these operations (no new gated actions added).

## Out of scope (for later)

- **Burndown charts / completion trends.** Deferred — needs a daily snapshot table; not worth it until rollups prove useful.
- **Task templates / recurring tasks.** Separate sprint.
- **Multi-user sharing on projects.** This product is single-user for now.
- **Reminder scheduling for milestones.** Could land in Sprint C (Agentic) when the planner can schedule across surfaces.
- **Materialized rollup views.** View-based queries are fine until perf data says otherwise.

## Open questions deferred to execution

- **Timezone for "weekly".** Start with UTC Monday 00:00; refine when we add user timezone preferences.
- **At-risk heuristic.** First pass: a task is at-risk if `due_date < now + 2 days AND status != done`. Tunable later.
- **Goal progress formula.** First pass: `milestones_completed / milestones_total`, fallback to `tasks_done / tasks_total` when no milestones. Document in `work_rollups.py`.
