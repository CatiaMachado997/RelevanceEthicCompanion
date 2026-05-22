# Sprint 4: Projects & Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Projects and Tasks as a first-class domain — Projects group work, Tasks are actionable units, and AI can extract task suggestions from free text (user must confirm before any task is created).

**Architecture:** Two new PostgreSQL tables (`projects`, `tasks`) with UUID primary keys. Two new FastAPI route files follow the exact pattern established in `goals.py` — ESL is evaluated before all write actions, DB access uses the `get_db_connection` context manager with dict_row access, and auth uses the existing Supabase helpers. A `POST /api/tasks/extract` endpoint uses Groq (langchain_groq) to parse task suggestions from free text without persisting anything. Frontend adds two new dashboard pages and two new sidebar nav items.

**Tech Stack:** FastAPI + psycopg3 (dict_row) + Supabase Auth + Groq (llama-3.3-70b-versatile via langchain_groq) + Next.js 15 App Router + TypeScript + Tailwind CSS + lucide-react

---

## File Map

### New files
- `backend/migrations/migration_sprint4.sql` — DDL for `projects` and `tasks` tables plus indexes
- `backend/routes/projects.py` — CRUD routes for projects (`/api/projects`)
- `backend/routes/tasks.py` — CRUD + AI extraction routes for tasks (`/api/tasks`)
- `backend/tests/test_projects_tasks.py` — integration tests for both route modules
- `frontend/app/dashboard/projects/page.tsx` — Projects list + create + archive page
- `frontend/app/dashboard/tasks/page.tsx` — Tasks list grouped by status + create + AI extract page

### Modified files
- `backend/main.py` — add `projects, tasks` to the grouped import line; add two `include_router` calls
- `frontend/lib/api.ts` — add `Project`, `Task`, `ExtractedTask` interfaces; add `projectsApi` and `tasksApi` objects; extend the `api` export object
- `frontend/components/sidebar.tsx` — import `FolderOpen`, `CheckSquare` from lucide-react; add two entries to `NAV_ITEMS`

---

## Task 1: DB Migration

**Files:**
- Create: `/Users/catiamachado/RelevanceEthicCompanion/backend/migrations/migration_sprint4.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- migration_sprint4.sql
-- Sprint 4: Projects and Tasks tables

-- projects
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'completed', 'archived')),
    goal_id     UUID REFERENCES goals(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status  ON projects(status);

-- tasks
CREATE TABLE IF NOT EXISTS tasks (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id     UUID REFERENCES projects(id) ON DELETE SET NULL,
    title          TEXT NOT NULL,
    description    TEXT,
    status         TEXT NOT NULL DEFAULT 'todo'
                   CHECK (status IN ('todo', 'in_progress', 'done', 'cancelled')),
    priority       INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    due_date       TIMESTAMPTZ,
    source_origin  TEXT NOT NULL DEFAULT 'manual',
    ai_confidence  FLOAT,
    user_confirmed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id    ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
```

- [ ] **Step 2: Apply the migration**

Run against your local Docker PostgreSQL. Replace `<DB_URL>` with the value of `DATABASE_URL` in `backend/.env`:

```bash
psql "$DATABASE_URL" -f /Users/catiamachado/RelevanceEthicCompanion/backend/migrations/migration_sprint4.sql
```

Expected output:
```
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
```

- [ ] **Step 3: Verify tables exist**

```bash
psql "$DATABASE_URL" -c "\dt projects" -c "\dt tasks"
```

Expected: both tables listed.

- [ ] **Step 4: Commit**

```bash
git add /Users/catiamachado/RelevanceEthicCompanion/backend/migrations/migration_sprint4.sql
git commit -m "feat: add projects and tasks DB migration (Sprint 4)"
```

---

## Task 2: Projects API

**Files:**
- Create: `/Users/catiamachado/RelevanceEthicCompanion/backend/routes/projects.py`
- Test: `/Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py` (projects section)

- [ ] **Step 1: Write the failing tests for projects**

Create `/Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py`:

```python
"""
Projects & Tasks Route Integration Tests

Mocks: DB (get_db_connection context manager), ESL (evaluate_action), Auth dependencies.
Pattern mirrors test_goals_routes.py exactly.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC
import pytest

from esl.models import ESLDecision, ESLDecisionStatus
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def make_mock_esl():
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(
        return_value=ESLDecision(
            status=ESLDecisionStatus.APPROVED,
            reason="Approved for testing",
            confidence=1.0,
        )
    )
    return mock_esl


def make_db_mock(fetchone_result=None, fetchall_result=None):
    """Build a mock for get_db_connection() context manager."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# ─────────────────────────────────────────────
# Projects fixtures
# ─────────────────────────────────────────────

SAMPLE_PROJECT_ROW = {
    "id": "proj-001",
    "user_id": TEST_USER_ID,
    "title": "Website Redesign",
    "description": "Rebuild the marketing site",
    "status": "active",
    "goal_id": None,
    "created_at": datetime(2026, 3, 28, tzinfo=UTC),
    "updated_at": datetime(2026, 3, 28, tzinfo=UTC),
}


def make_projects_app():
    from routes.projects import router as projects_router, get_esl
    app = FastAPI()
    app.include_router(projects_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = make_mock_esl
    return app


@pytest.fixture
def projects_client():
    return TestClient(make_projects_app())


# ─────────────────────────────────────────────
# Projects tests
# ─────────────────────────────────────────────

def test_create_project_success(projects_client):
    """POST /api/projects → 201 with project data."""
    mock_conn, _ = make_db_mock(fetchone_result=SAMPLE_PROJECT_ROW)

    with patch("routes.projects.get_db_connection", return_value=mock_conn):
        response = projects_client.post(
            "/api/projects",
            json={"title": "Website Redesign", "description": "Rebuild the marketing site"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["title"] == "Website Redesign"


def test_create_project_esl_veto():
    """POST /api/projects → 403 when ESL vetoes."""
    from routes.projects import router as projects_router, get_esl
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(
        return_value=ESLDecision(
            status=ESLDecisionStatus.VETOED,
            reason="Blocked by focus mode",
            confidence=1.0,
        )
    )
    app = FastAPI()
    app.include_router(projects_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = lambda: mock_esl

    response = TestClient(app).post(
        "/api/projects",
        json={"title": "Blocked Project"},
    )
    assert response.status_code == 403
    assert "ESL" in response.json()["detail"]


def test_list_projects_default_active(projects_client):
    """GET /api/projects → returns active projects by default."""
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_PROJECT_ROW])

    with patch("routes.projects.get_db_connection", return_value=mock_conn):
        response = projects_client.get("/api/projects")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["count"] == 1
    assert data["data"][0]["status"] == "active"


def test_list_projects_filter_by_status(projects_client):
    """GET /api/projects?status=completed → uses status param."""
    completed_row = {**SAMPLE_PROJECT_ROW, "status": "completed"}
    mock_conn, _ = make_db_mock(fetchall_result=[completed_row])

    with patch("routes.projects.get_db_connection", return_value=mock_conn):
        response = projects_client.get("/api/projects?status=completed")

    assert response.status_code == 200
    data = response.json()
    assert data["data"][0]["status"] == "completed"


def test_get_project_by_id(projects_client):
    """GET /api/projects/{id} → returns single project."""
    mock_conn, _ = make_db_mock(fetchone_result=SAMPLE_PROJECT_ROW)

    with patch("routes.projects.get_db_connection", return_value=mock_conn):
        response = projects_client.get("/api/projects/proj-001")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "proj-001"


def test_get_project_not_found(projects_client):
    """GET /api/projects/{id} → 404 when not found."""
    mock_conn, _ = make_db_mock(fetchone_result=None)

    with patch("routes.projects.get_db_connection", return_value=mock_conn):
        response = projects_client.get("/api/projects/nonexistent")

    assert response.status_code == 404


def test_patch_project(projects_client):
    """PATCH /api/projects/{id} → updated project."""
    updated_row = {**SAMPLE_PROJECT_ROW, "title": "New Title"}
    mock_conn, _ = make_db_mock(fetchone_result=updated_row)

    with patch("routes.projects.get_db_connection", return_value=mock_conn):
        response = projects_client.patch(
            "/api/projects/proj-001",
            json={"title": "New Title"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "New Title"


def test_delete_project_archives(projects_client):
    """DELETE /api/projects/{id} → status=archived (soft delete)."""
    archived_row = {**SAMPLE_PROJECT_ROW, "status": "archived"}
    mock_conn, _ = make_db_mock(fetchone_result=archived_row)

    with patch("routes.projects.get_db_connection", return_value=mock_conn):
        response = projects_client.delete("/api/projects/proj-001")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "archived"


# ─────────────────────────────────────────────
# Tasks fixtures
# ─────────────────────────────────────────────

SAMPLE_TASK_ROW = {
    "id": "task-001",
    "user_id": TEST_USER_ID,
    "project_id": "proj-001",
    "title": "Write unit tests",
    "description": "Cover all new routes",
    "status": "todo",
    "priority": 3,
    "due_date": None,
    "source_origin": "manual",
    "ai_confidence": None,
    "user_confirmed": True,
    "created_at": datetime(2026, 3, 28, tzinfo=UTC),
    "updated_at": datetime(2026, 3, 28, tzinfo=UTC),
}


def make_tasks_app():
    from routes.tasks import router as tasks_router, get_esl
    app = FastAPI()
    app.include_router(tasks_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = make_mock_esl
    return app


@pytest.fixture
def tasks_client():
    return TestClient(make_tasks_app())


# ─────────────────────────────────────────────
# Tasks tests
# ─────────────────────────────────────────────

def test_create_task_success(tasks_client):
    """POST /api/tasks → 201 with task data."""
    mock_conn, _ = make_db_mock(fetchone_result=SAMPLE_TASK_ROW)

    with patch("routes.tasks.get_db_connection", return_value=mock_conn):
        response = tasks_client.post(
            "/api/tasks",
            json={"title": "Write unit tests", "priority": 3},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["title"] == "Write unit tests"


def test_create_task_esl_veto():
    """POST /api/tasks → 403 when ESL vetoes."""
    from routes.tasks import router as tasks_router, get_esl
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(
        return_value=ESLDecision(
            status=ESLDecisionStatus.VETOED,
            reason="Blocked",
            confidence=1.0,
        )
    )
    app = FastAPI()
    app.include_router(tasks_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = lambda: mock_esl

    response = TestClient(app).post("/api/tasks", json={"title": "Blocked"})
    assert response.status_code == 403


def test_update_project_esl_veto(mock_esl_vetoed, mock_auth):
    """PATCH /api/projects/{id} should return 403 when ESL vetoes."""
    response = client.patch(
        "/api/projects/some-id",
        json={"title": "Updated"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 403

def test_archive_project_esl_veto(mock_esl_vetoed, mock_auth):
    """DELETE /api/projects/{id} should return 403 when ESL vetoes."""
    response = client.delete(
        "/api/projects/some-id",
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 403

def test_update_task_esl_veto(mock_esl_vetoed, mock_auth):
    """PATCH /api/tasks/{id} should return 403 when ESL vetoes."""
    response = client.patch(
        "/api/tasks/some-id",
        json={"status": "done"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 403

def test_delete_task_esl_veto(mock_esl_vetoed, mock_auth):
    """DELETE /api/tasks/{id} should return 403 when ESL vetoes."""
    response = client.delete(
        "/api/tasks/some-id",
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 403


def test_list_tasks(tasks_client):
    """GET /api/tasks → list of tasks."""
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_TASK_ROW])

    with patch("routes.tasks.get_db_connection", return_value=mock_conn):
        response = tasks_client.get("/api/tasks")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["data"][0]["title"] == "Write unit tests"


def test_list_tasks_filter_by_project(tasks_client):
    """GET /api/tasks?project_id=proj-001 → filtered list."""
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_TASK_ROW])

    with patch("routes.tasks.get_db_connection", return_value=mock_conn):
        response = tasks_client.get("/api/tasks?project_id=proj-001")

    assert response.status_code == 200
    assert response.json()["data"][0]["project_id"] == "proj-001"


def test_get_task_by_id(tasks_client):
    """GET /api/tasks/{id} → single task."""
    mock_conn, _ = make_db_mock(fetchone_result=SAMPLE_TASK_ROW)

    with patch("routes.tasks.get_db_connection", return_value=mock_conn):
        response = tasks_client.get("/api/tasks/task-001")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "task-001"


def test_get_task_not_found(tasks_client):
    """GET /api/tasks/{id} → 404 when not found."""
    mock_conn, _ = make_db_mock(fetchone_result=None)

    with patch("routes.tasks.get_db_connection", return_value=mock_conn):
        response = tasks_client.get("/api/tasks/nonexistent")

    assert response.status_code == 404


def test_patch_task_status(tasks_client):
    """PATCH /api/tasks/{id} → updated task."""
    updated_row = {**SAMPLE_TASK_ROW, "status": "in_progress"}
    mock_conn, _ = make_db_mock(fetchone_result=updated_row)

    with patch("routes.tasks.get_db_connection", return_value=mock_conn):
        response = tasks_client.patch(
            "/api/tasks/task-001",
            json={"status": "in_progress"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "in_progress"


def test_delete_task_hard_delete(tasks_client):
    """DELETE /api/tasks/{id} → hard delete, returns success."""
    mock_conn, mock_cursor = make_db_mock(fetchone_result=SAMPLE_TASK_ROW)

    with patch("routes.tasks.get_db_connection", return_value=mock_conn):
        response = tasks_client.delete("/api/tasks/task-001")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_extract_tasks_returns_suggestions(tasks_client):
    """POST /api/tasks/extract → returns task suggestions without creating them."""
    mock_llm_content = '{"tasks": [{"title": "Buy groceries", "description": "Get milk and eggs", "priority": 5}]}'

    with patch("routes.tasks.ChatGroq") as mock_groq_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_llm_content)
        mock_groq_cls.return_value = mock_llm

        response = tasks_client.post(
            "/api/tasks/extract",
            json={"text": "I need to buy groceries — milk and eggs."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["title"] == "Buy groceries"


def test_extract_tasks_graceful_on_bad_json(tasks_client):
    """POST /api/tasks/extract → returns empty suggestions when LLM returns invalid JSON."""
    with patch("routes.tasks.ChatGroq") as mock_groq_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="not valid json at all")
        mock_groq_cls.return_value = mock_llm

        response = tasks_client.post(
            "/api/tasks/extract",
            json={"text": "Some text"},
        )

    assert response.status_code == 200
    assert response.json()["suggestions"] == []


def test_extract_tasks_esl_veto():
    """POST /api/tasks/extract → 403 when ESL vetoes content generation."""
    from routes.tasks import router as tasks_router, get_esl
    mock_esl = MagicMock()
    mock_esl.evaluate_action = AsyncMock(
        return_value=ESLDecision(
            status=ESLDecisionStatus.VETOED,
            reason="Content generation blocked",
            confidence=1.0,
        )
    )
    app = FastAPI()
    app.include_router(tasks_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_esl] = lambda: mock_esl

    response = TestClient(app).post("/api/tasks/extract", json={"text": "Do something"})
    assert response.status_code == 403
```

- [ ] **Step 2: Run the tests to confirm they fail (routes don't exist yet)**

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest /Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` — `routes.projects` does not exist yet.

- [ ] **Step 3: Implement `backend/routes/projects.py`**

Create `/Users/catiamachado/RelevanceEthicCompanion/backend/routes/projects.py`:

```python
"""
Projects API Routes

Projects group related tasks and can be linked to a user goal.
All write actions pass through the Ethical Safeguard Layer.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel, Field

from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from services.context_manager import ContextManager
from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus


def get_context_manager() -> ContextManager:
    return ContextManager()


def get_esl(context_manager: ContextManager = Depends(get_context_manager)) -> EthicalSafeguardLayer:
    return EthicalSafeguardLayer(context_manager)


# ── Request / Response models ──────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Project title")
    description: Optional[str] = Field(None, description="Project description")
    goal_id: Optional[str] = Field(None, description="Linked goal UUID")


class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    goal_id: Optional[str] = None


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _serialize_project(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "goal_id": str(row["goal_id"]) if row["goal_id"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.post("", response_model=dict, status_code=201)
async def create_project(
    request: CreateProjectRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """Create a new project. ESL evaluated before DB write."""
    try:
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="project_creation",
            content=f"Creating project: {request.title}",
            urgency=UrgencyLevel.LOW,
            metadata={"project_title": request.title},
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Project creation blocked by ESL: {decision.reason}",
            )

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO projects (user_id, title, description, goal_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, user_id, title, description, status, goal_id, created_at, updated_at
                    """,
                    (str(user_id), request.title, request.description, request.goal_id),
                )
                new_project = cur.fetchone()

        if not new_project:
            raise HTTPException(status_code=500, detail="Failed to create project")

        return {
            "status": "success",
            "message": "Project created successfully",
            "data": _serialize_project(new_project),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")


@router.get("", response_model=dict)
async def list_projects(
    user_id: str = Depends(get_current_read_user_id),
    status: Optional[str] = None,
):
    """List projects. Defaults to active only; pass ?status= to override."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM projects WHERE user_id = %s"
                params: list = [str(user_id)]

                if status:
                    query += " AND status = %s"
                    params.append(status)
                else:
                    query += " AND status = 'active'"

                query += " ORDER BY created_at DESC"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        return {
            "status": "success",
            "count": len(rows),
            "data": [_serialize_project(r) for r in rows],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching projects: {str(e)}")


@router.get("/{project_id}", response_model=dict)
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_read_user_id),
):
    """Get a single project by ID."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM projects WHERE id = %s AND user_id = %s",
                    (str(project_id), str(user_id)),
                )
                row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        return {"status": "success", "data": _serialize_project(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching project: {str(e)}")


@router.patch("/{project_id}", response_model=dict)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """Update project fields. ESL evaluated before DB write."""
    try:
        # ESL evaluation
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="project_update",
            content=f"Updating project: {project_id}",
            urgency=UrgencyLevel.LOW,
            metadata={"project_id": project_id}
        )
        decision = await esl.evaluate_action(proposed_action, user_id)
        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(status_code=403, detail=f"Update blocked by ESL: {decision.reason}")

        update_data: dict = {}
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.status is not None:
            update_data["status"] = request.status
        if request.goal_id is not None:
            update_data["goal_id"] = request.goal_id

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_data["updated_at"] = "NOW()"

        set_clause = ", ".join(
            [f"{k} = NOW()" if v == "NOW()" else f"{k} = %s" for k, v in update_data.items()]
        )
        params = [v for v in update_data.values() if v != "NOW()"]
        params.extend([str(project_id), str(user_id)])

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE projects SET {set_clause} WHERE id = %s AND user_id = %s RETURNING *",
                    tuple(params),
                )
                updated = cur.fetchone()

        if not updated:
            raise HTTPException(status_code=404, detail="Project not found")

        return {
            "status": "success",
            "message": "Project updated successfully",
            "data": _serialize_project(updated),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating project: {str(e)}")


@router.delete("/{project_id}", response_model=dict)
async def archive_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """Archive a project (soft delete — sets status=archived). ESL evaluated before DB write."""
    try:
        # ESL evaluation
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="project_archive",
            content=f"Archiving project: {project_id}",
            urgency=UrgencyLevel.LOW,
            metadata={"project_id": project_id}
        )
        decision = await esl.evaluate_action(proposed_action, user_id)
        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(status_code=403, detail=f"Archive blocked by ESL: {decision.reason}")

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE projects
                    SET status = 'archived', updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                    RETURNING *
                    """,
                    (str(project_id), str(user_id)),
                )
                archived = cur.fetchone()

        if not archived:
            raise HTTPException(status_code=404, detail="Project not found")

        return {
            "status": "success",
            "message": "Project archived successfully",
            "data": _serialize_project(archived),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error archiving project: {str(e)}")
```

- [ ] **Step 4: Run the projects tests**

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest /Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py -k "project" -v
```

Expected: all `test_*project*` tests pass. Tasks tests still fail (tasks module not yet created).

- [ ] **Step 5: Commit**

```bash
git add /Users/catiamachado/RelevanceEthicCompanion/backend/routes/projects.py \
        /Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py
git commit -m "feat: add Projects API routes with ESL + tests (Sprint 4)"
```

---

## Task 3: Tasks API

**Files:**
- Create: `/Users/catiamachado/RelevanceEthicCompanion/backend/routes/tasks.py`
- Modify: `/Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py` (tasks section already written in Task 2)

- [ ] **Step 1: Verify tasks tests fail**

The tasks tests were written in Task 2. Confirm they still fail before implementing:

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest /Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py -k "task" -v 2>&1 | head -20
```

Expected: `ImportError` — `routes.tasks` does not exist yet.

- [ ] **Step 2: Implement `backend/routes/tasks.py`**

Create `/Users/catiamachado/RelevanceEthicCompanion/backend/routes/tasks.py`:

```python
"""
Tasks API Routes

Tasks are actionable work units, optionally linked to a project.
The /extract endpoint uses Groq to suggest tasks from free text
WITHOUT persisting anything — the user must confirm before creation.
All write actions and AI generation pass through the Ethical Safeguard Layer.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from config import settings
from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from services.context_manager import ContextManager
from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """\
Extract actionable tasks from the following text. Return valid JSON only, no other text.
Format: {{"tasks": [{{"title": "short action title", "description": "optional detail", "priority": 5}}]}}
Priority scale: 1=highest urgency, 10=lowest. Only include concrete actionable items.

Text:
{text}"""


def get_context_manager() -> ContextManager:
    return ContextManager()


def get_esl(context_manager: ContextManager = Depends(get_context_manager)) -> EthicalSafeguardLayer:
    return EthicalSafeguardLayer(context_manager)


# ── Request / Response models ──────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Task title")
    description: Optional[str] = Field(None)
    project_id: Optional[str] = Field(None)
    priority: int = Field(default=5, ge=1, le=10)
    due_date: Optional[str] = Field(None, description="ISO datetime string")
    source_origin: str = Field(default="manual")
    ai_confidence: Optional[float] = Field(None)
    user_confirmed: bool = Field(default=True)


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    due_date: Optional[str] = None
    project_id: Optional[str] = None


class ExtractTasksRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Free text to extract tasks from")


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _serialize_task(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "project_id": str(row["project_id"]) if row["project_id"] else None,
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
        "source_origin": row["source_origin"],
        "ai_confidence": row["ai_confidence"],
        "user_confirmed": row["user_confirmed"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.post("/extract", response_model=dict)
async def extract_tasks(
    request: ExtractTasksRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """
    Extract task suggestions from free text using Groq LLM.
    Returns suggestions only — does NOT create any tasks.
    ESL evaluates as CONTENT_GENERATION before the LLM is called.
    """
    try:
        proposed_action = ProposedAction(
            action_type=ActionType.CONTENT_GENERATION,
            content_type="task_extraction",
            content=f"Extracting tasks from text ({len(request.text)} chars)",
            urgency=UrgencyLevel.LOW,
            metadata={"text_length": len(request.text)},
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Task extraction blocked by ESL: {decision.reason}",
            )

        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=settings.GROQ_API_KEY,
            temperature=0,
        )
        prompt = _EXTRACT_PROMPT.format(text=request.text)
        response = llm.invoke([HumanMessage(content=prompt)])

        try:
            parsed = json.loads(response.content)
            suggestions = parsed.get("tasks", [])
        except (json.JSONDecodeError, AttributeError):
            logger.warning("LLM returned non-JSON content for task extraction")
            suggestions = []

        return {
            "status": "success",
            "suggestions": suggestions,
            "count": len(suggestions),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting tasks: {str(e)}")


@router.post("", response_model=dict, status_code=201)
async def create_task(
    request: CreateTaskRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """Create a new task. ESL evaluated before DB write."""
    try:
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="task_creation",
            content=f"Creating task: {request.title}",
            urgency=UrgencyLevel.LOW,
            metadata={"task_title": request.title, "source_origin": request.source_origin},
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Task creation blocked by ESL: {decision.reason}",
            )

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tasks (
                        user_id, project_id, title, description, priority,
                        due_date, source_origin, ai_confidence, user_confirmed
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, user_id, project_id, title, description, status,
                              priority, due_date, source_origin, ai_confidence,
                              user_confirmed, created_at, updated_at
                    """,
                    (
                        str(user_id),
                        request.project_id,
                        request.title,
                        request.description,
                        request.priority,
                        request.due_date,
                        request.source_origin,
                        request.ai_confidence,
                        request.user_confirmed,
                    ),
                )
                new_task = cur.fetchone()

        if not new_task:
            raise HTTPException(status_code=500, detail="Failed to create task")

        return {
            "status": "success",
            "message": "Task created successfully",
            "data": _serialize_task(new_task),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")


@router.get("", response_model=dict)
async def list_tasks(
    user_id: str = Depends(get_current_read_user_id),
    project_id: Optional[str] = None,
    status: Optional[str] = None,
):
    """List tasks. Optional filters: project_id, status."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM tasks WHERE user_id = %s"
                params: list = [str(user_id)]

                if project_id:
                    query += " AND project_id = %s"
                    params.append(str(project_id))
                if status:
                    query += " AND status = %s"
                    params.append(status)

                query += " ORDER BY priority, created_at DESC"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        return {
            "status": "success",
            "count": len(rows),
            "data": [_serialize_task(r) for r in rows],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tasks: {str(e)}")


@router.get("/{task_id}", response_model=dict)
async def get_task(
    task_id: str,
    user_id: str = Depends(get_current_read_user_id),
):
    """Get a single task by ID."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
                    (str(task_id), str(user_id)),
                )
                row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        return {"status": "success", "data": _serialize_task(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching task: {str(e)}")


@router.patch("/{task_id}", response_model=dict)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """Update task fields. ESL evaluated before DB write."""
    try:
        # ESL evaluation
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="task_update",
            content=f"Updating task: {task_id}",
            urgency=UrgencyLevel.LOW,
            metadata={"task_id": task_id}
        )
        decision = await esl.evaluate_action(proposed_action, user_id)
        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(status_code=403, detail=f"Update blocked by ESL: {decision.reason}")

        update_data: dict = {}
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.status is not None:
            update_data["status"] = request.status
        if request.priority is not None:
            update_data["priority"] = request.priority
        if request.due_date is not None:
            update_data["due_date"] = request.due_date
        if request.project_id is not None:
            update_data["project_id"] = request.project_id

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
        set_clause += ", updated_at = NOW()"
        params = list(update_data.values())
        params.extend([str(task_id), str(user_id)])

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE tasks SET {set_clause} WHERE id = %s AND user_id = %s RETURNING *",
                    tuple(params),
                )
                updated = cur.fetchone()

        if not updated:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "status": "success",
            "message": "Task updated successfully",
            "data": _serialize_task(updated),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating task: {str(e)}")


@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """Hard delete a task. ESL evaluated before DB delete."""
    try:
        # ESL evaluation
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="task_delete",
            content=f"Deleting task: {task_id}",
            urgency=UrgencyLevel.LOW,
            metadata={"task_id": task_id}
        )
        decision = await esl.evaluate_action(proposed_action, user_id)
        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(status_code=403, detail=f"Delete blocked by ESL: {decision.reason}")

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM tasks WHERE id = %s AND user_id = %s",
                    (str(task_id), str(user_id)),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Task not found")

                cur.execute(
                    "DELETE FROM tasks WHERE id = %s AND user_id = %s",
                    (str(task_id), str(user_id)),
                )

        return {"status": "success", "message": "Task deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting task: {str(e)}")
```

- [ ] **Step 3: Run all projects + tasks tests**

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest /Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py -v
```

Expected output (all green):
```
PASSED tests/test_projects_tasks.py::test_create_project_success
PASSED tests/test_projects_tasks.py::test_create_project_esl_veto
PASSED tests/test_projects_tasks.py::test_list_projects_default_active
PASSED tests/test_projects_tasks.py::test_list_projects_filter_by_status
PASSED tests/test_projects_tasks.py::test_get_project_by_id
PASSED tests/test_projects_tasks.py::test_get_project_not_found
PASSED tests/test_projects_tasks.py::test_patch_project
PASSED tests/test_projects_tasks.py::test_delete_project_archives
PASSED tests/test_projects_tasks.py::test_create_task_success
PASSED tests/test_projects_tasks.py::test_create_task_esl_veto
PASSED tests/test_projects_tasks.py::test_list_tasks
PASSED tests/test_projects_tasks.py::test_list_tasks_filter_by_project
PASSED tests/test_projects_tasks.py::test_get_task_by_id
PASSED tests/test_projects_tasks.py::test_get_task_not_found
PASSED tests/test_projects_tasks.py::test_patch_task_status
PASSED tests/test_projects_tasks.py::test_delete_task_hard_delete
PASSED tests/test_projects_tasks.py::test_extract_tasks_returns_suggestions
PASSED tests/test_projects_tasks.py::test_extract_tasks_graceful_on_bad_json
PASSED tests/test_projects_tasks.py::test_extract_tasks_esl_veto
```

- [ ] **Step 4: Commit**

```bash
git add /Users/catiamachado/RelevanceEthicCompanion/backend/routes/tasks.py
git commit -m "feat: add Tasks API routes with ESL + AI extraction endpoint (Sprint 4)"
```

---

## Task 4: Register Routers in main.py

**Files:**
- Modify: `/Users/catiamachado/RelevanceEthicCompanion/backend/main.py`

- [ ] **Step 1: Update the grouped import line**

In `/Users/catiamachado/RelevanceEthicCompanion/backend/main.py`, find line 169:

```python
from routes import auth, values, chat, goals, transparency, relevance, data_sources, profile, notifications, feedback, search, documents
```

Replace with:

```python
from routes import auth, values, chat, goals, transparency, relevance, data_sources, profile, notifications, feedback, search, documents, projects, tasks
```

- [ ] **Step 2: Add the two include_router calls**

In the same file, find line 189:

```python
app.include_router(documents.router)
```

Add after it:

```python
app.include_router(projects.router)
app.include_router(tasks.router)
```

- [ ] **Step 3: Verify the app starts without error**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && \
  /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -c "from main import app; print('OK')"
```

Expected output:
```
OK
```

- [ ] **Step 4: Run the full existing test suite to check for regressions**

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest /Users/catiamachado/RelevanceEthicCompanion/backend/tests/ -v --tb=short -q 2>&1 | tail -20
```

Expected: no new failures (existing tests remain green; new tests green).

- [ ] **Step 5: Commit**

```bash
git add /Users/catiamachado/RelevanceEthicCompanion/backend/main.py
git commit -m "feat: register projects and tasks routers in main.py (Sprint 4)"
```

---

## Task 5: Frontend api.ts

**Files:**
- Modify: `/Users/catiamachado/RelevanceEthicCompanion/frontend/lib/api.ts`

- [ ] **Step 1: Add interfaces and projectsApi after the Documents API section**

In `/Users/catiamachado/RelevanceEthicCompanion/frontend/lib/api.ts`, find the line:

```typescript
export const api = {
```

Insert the following block **immediately before** that line:

```typescript
// ==================== Projects API ====================

export interface Project {
  id: string
  user_id: string
  title: string
  description: string | null
  status: 'active' | 'completed' | 'archived'
  goal_id: string | null
  created_at: string | null
  updated_at: string | null
}

export const projectsApi = {
  /**
   * List projects (active by default; pass status to override)
   */
  list: async (status?: string): Promise<{ projects: Project[]; count: number }> => {
    const query = status ? `?status=${status}` : ''
    const response = await apiRequest<{ status: string; count: number; data: Project[] }>(
      `/api/projects${query}`
    )
    return { projects: response.data || [], count: response.count || 0 }
  },

  /**
   * Get a single project by ID
   */
  get: async (id: string): Promise<Project> => {
    const response = await apiRequest<{ status: string; data: Project }>(`/api/projects/${id}`)
    return response.data
  },

  /**
   * Create a new project
   */
  create: async (data: {
    title: string
    description?: string
    goal_id?: string
  }): Promise<Project> => {
    const response = await apiRequest<{ status: string; message: string; data: Project }>(
      '/api/projects',
      { method: 'POST', body: JSON.stringify(data) }
    )
    return response.data
  },

  /**
   * Update a project (title, description, status, goal_id)
   */
  update: async (id: string, data: Partial<Pick<Project, 'title' | 'description' | 'status' | 'goal_id'>>): Promise<Project> => {
    const response = await apiRequest<{ status: string; message: string; data: Project }>(
      `/api/projects/${id}`,
      { method: 'PATCH', body: JSON.stringify(data) }
    )
    return response.data
  },

  /**
   * Archive a project (soft delete)
   */
  archive: async (id: string): Promise<Project> => {
    const response = await apiRequest<{ status: string; message: string; data: Project }>(
      `/api/projects/${id}`,
      { method: 'DELETE' }
    )
    return response.data
  },
}

// ==================== Tasks API ====================

export interface Task {
  id: string
  user_id: string
  project_id: string | null
  title: string
  description: string | null
  status: 'todo' | 'in_progress' | 'done' | 'cancelled'
  priority: number
  due_date: string | null
  source_origin: string
  ai_confidence: number | null
  user_confirmed: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ExtractedTask {
  title: string
  description?: string
  priority: number
}

export const tasksApi = {
  /**
   * List tasks (optional filters: project_id, status)
   */
  list: async (filters?: { project_id?: string; status?: string }): Promise<{ tasks: Task[]; count: number }> => {
    const params = new URLSearchParams()
    if (filters?.project_id) params.append('project_id', filters.project_id)
    if (filters?.status) params.append('status', filters.status)
    const query = params.toString() ? `?${params}` : ''
    const response = await apiRequest<{ status: string; count: number; data: Task[] }>(
      `/api/tasks${query}`
    )
    return { tasks: response.data || [], count: response.count || 0 }
  },

  /**
   * Get a single task by ID
   */
  get: async (id: string): Promise<Task> => {
    const response = await apiRequest<{ status: string; data: Task }>(`/api/tasks/${id}`)
    return response.data
  },

  /**
   * Create a new task
   */
  create: async (data: {
    title: string
    description?: string
    project_id?: string
    priority?: number
    due_date?: string
    source_origin?: string
    ai_confidence?: number
    user_confirmed?: boolean
  }): Promise<Task> => {
    const response = await apiRequest<{ status: string; message: string; data: Task }>(
      '/api/tasks',
      { method: 'POST', body: JSON.stringify(data) }
    )
    return response.data
  },

  /**
   * Update a task
   */
  update: async (
    id: string,
    data: Partial<Pick<Task, 'title' | 'description' | 'status' | 'priority' | 'due_date' | 'project_id'>>
  ): Promise<Task> => {
    const response = await apiRequest<{ status: string; message: string; data: Task }>(
      `/api/tasks/${id}`,
      { method: 'PATCH', body: JSON.stringify(data) }
    )
    return response.data
  },

  /**
   * Hard delete a task
   */
  delete: async (id: string): Promise<void> => {
    await apiRequest(`/api/tasks/${id}`, { method: 'DELETE' })
  },

  /**
   * Extract task suggestions from free text (does NOT create tasks)
   */
  extract: async (text: string): Promise<{ suggestions: ExtractedTask[]; count: number }> => {
    const response = await apiRequest<{
      status: string
      suggestions: ExtractedTask[]
      count: number
    }>('/api/tasks/extract', {
      method: 'POST',
      body: JSON.stringify({ text }),
    })
    return { suggestions: response.suggestions || [], count: response.count || 0 }
  },
}
```

- [ ] **Step 2: Extend the `api` export object**

Find:

```typescript
export const api = {
  values: valuesApi,
  chat: chatApi,
  goals: goalsApi,
  transparency: transparencyApi,
  relevance: relevanceApi,
  feedback: feedbackApi,
  events: eventsApi,
  dataSources: dataSourcesApi,
  settings: settingsApi,
  notifications: notificationsApi,
  search: searchApi,
  insight: insightApi,
  documents: documentsApi,
};
```

Replace with:

```typescript
export const api = {
  values: valuesApi,
  chat: chatApi,
  goals: goalsApi,
  transparency: transparencyApi,
  relevance: relevanceApi,
  feedback: feedbackApi,
  events: eventsApi,
  dataSources: dataSourcesApi,
  settings: settingsApi,
  notifications: notificationsApi,
  search: searchApi,
  insight: insightApi,
  documents: documentsApi,
  projects: projectsApi,
  tasks: tasksApi,
};
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors (exit 0, empty or clean output).

- [ ] **Step 4: Commit**

```bash
git add /Users/catiamachado/RelevanceEthicCompanion/frontend/lib/api.ts
git commit -m "feat: add projectsApi and tasksApi to frontend api client (Sprint 4)"
```

---

## Task 6: Frontend Pages + Sidebar

**Files:**
- Create: `/Users/catiamachado/RelevanceEthicCompanion/frontend/app/dashboard/projects/page.tsx`
- Create: `/Users/catiamachado/RelevanceEthicCompanion/frontend/app/dashboard/tasks/page.tsx`
- Modify: `/Users/catiamachado/RelevanceEthicCompanion/frontend/components/sidebar.tsx`

- [ ] **Step 1: Add Projects and Tasks to the sidebar nav**

In `/Users/catiamachado/RelevanceEthicCompanion/frontend/components/sidebar.tsx`, find:

```typescript
import {
  LayoutDashboard, MessageSquare, Heart, Target,
  Eye, Plug, Settings, LogOut, Bell, User, Sun, Moon, Search,
  Plus, Pencil, Trash2, Check, X, FileText,
} from "lucide-react"
```

Replace with:

```typescript
import {
  LayoutDashboard, MessageSquare, Heart, Target,
  Eye, Plug, Settings, LogOut, Bell, User, Sun, Moon, Search,
  Plus, Pencil, Trash2, Check, X, FileText, FolderOpen, CheckSquare,
} from "lucide-react"
```

Then add two entries to `NAV_ITEMS` in `frontend/components/sidebar.tsx`. Place them after the Goals entry (`{ href: "/dashboard/goals", ... }`). Import `FolderOpen` and `CheckSquare` from lucide-react in the existing import block. Add:

```typescript
{ href: "/dashboard/projects", label: "Projects", icon: FolderOpen },
{ href: "/dashboard/tasks",    label: "Tasks",     icon: CheckSquare },
```

- [ ] **Step 2: Create the Projects page**

Create `/Users/catiamachado/RelevanceEthicCompanion/frontend/app/dashboard/projects/page.tsx`:

```tsx
"use client"

import { useState, useEffect } from "react"
import { projectsApi, type Project } from "@/lib/api"
import { Plus, Archive, FolderOpen } from "lucide-react"

const STATUS_STYLES: Record<Project["status"], { bg: string; text: string; border: string }> = {
  active:    { bg: "rgba(74,124,89,0.10)",   text: "#4A7C59", border: "rgba(74,124,89,0.25)" },
  completed: { bg: "rgba(10,10,10,0.08)",    text: "#0a0a0a", border: "rgba(10,10,10,0.15)" },
  archived:  { bg: "rgba(158,158,158,0.10)", text: "#9e9e9e", border: "rgba(158,158,158,0.25)" },
}

function StatusBadge({ status }: { status: Project["status"] }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.active
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize"
      style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
    >
      {status}
    </span>
  )
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create form state
  const [showForm, setShowForm] = useState(false)
  const [formTitle, setFormTitle] = useState("")
  const [formDesc, setFormDesc] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    projectsApi
      .list()
      .then(r => setProjects(r.projects))
      .catch(() => setError("Failed to load projects"))
      .finally(() => setLoading(false))
  }, [])

  const handleCreate = async () => {
    if (!formTitle.trim()) return
    setSaving(true)
    try {
      const created = await projectsApi.create({
        title: formTitle.trim(),
        description: formDesc.trim() || undefined,
      })
      setProjects(prev => [created, ...prev])
      setFormTitle("")
      setFormDesc("")
      setShowForm(false)
    } catch {
      setError("Failed to create project")
    } finally {
      setSaving(false)
    }
  }

  const handleArchive = async (id: string) => {
    try {
      await projectsApi.archive(id)
      setProjects(prev => prev.filter(p => p.id !== id))
    } catch {
      setError("Failed to archive project")
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <FolderOpen size={22} style={{ color: "var(--ec-text)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--ec-text)" }}>
            Projects
          </h1>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
          style={{ background: "var(--ec-text)", color: "var(--ec-card-bg)" }}
        >
          <Plus size={15} />
          New project
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div
          className="rounded-xl border p-4 mb-6"
          style={{ background: "var(--ec-card-bg)", borderColor: "var(--ec-border)" }}
        >
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--ec-text)" }}>
            New project
          </h2>
          <input
            autoFocus
            value={formTitle}
            onChange={e => setFormTitle(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleCreate()}
            placeholder="Project title"
            className="w-full rounded-lg border px-3 py-2 text-sm mb-2 outline-none"
            style={{
              background: "var(--ec-input-bg, var(--ec-card-bg))",
              borderColor: "var(--ec-border)",
              color: "var(--ec-text)",
            }}
          />
          <textarea
            value={formDesc}
            onChange={e => setFormDesc(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full rounded-lg border px-3 py-2 text-sm mb-3 outline-none resize-none"
            style={{
              background: "var(--ec-input-bg, var(--ec-card-bg))",
              borderColor: "var(--ec-border)",
              color: "var(--ec-text)",
            }}
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 rounded-lg text-sm hover:opacity-70"
              style={{ color: "var(--ec-text-subtle)" }}
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={saving || !formTitle.trim()}
              className="px-4 py-1.5 rounded-lg text-sm font-medium disabled:opacity-40 transition-opacity hover:opacity-80"
              style={{ background: "var(--ec-text)", color: "var(--ec-card-bg)" }}
            >
              {saving ? "Creating…" : "Create"}
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-sm mb-4" style={{ color: "#B04A3A" }}>
          {error}
        </p>
      )}

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div
              key={i}
              className="h-16 rounded-xl animate-pulse"
              style={{ background: "var(--ec-card-bg)" }}
            />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div
          className="rounded-xl border p-8 text-center"
          style={{ borderColor: "var(--ec-border)" }}
        >
          <FolderOpen size={32} className="mx-auto mb-2 opacity-30" style={{ color: "var(--ec-text)" }} />
          <p className="text-sm" style={{ color: "var(--ec-text-subtle)" }}>
            No active projects. Create one to get started.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {projects.map(project => (
            <li
              key={project.id}
              className="flex items-start justify-between rounded-xl border p-4 transition-shadow hover:shadow-sm"
              style={{ background: "var(--ec-card-bg)", borderColor: "var(--ec-border)" }}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium truncate" style={{ color: "var(--ec-text)" }}>
                    {project.title}
                  </span>
                  <StatusBadge status={project.status} />
                </div>
                {project.description && (
                  <p className="text-xs line-clamp-2" style={{ color: "var(--ec-text-subtle)" }}>
                    {project.description}
                  </p>
                )}
              </div>
              <button
                onClick={() => handleArchive(project.id)}
                title="Archive project"
                className="ml-3 p-1.5 rounded-lg transition-opacity hover:opacity-60 shrink-0"
                style={{ color: "var(--ec-text-subtle)" }}
              >
                <Archive size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create the Tasks page**

Create `/Users/catiamachado/RelevanceEthicCompanion/frontend/app/dashboard/tasks/page.tsx`:

```tsx
"use client"

import { useState, useEffect } from "react"
import { tasksApi, type Task, type ExtractedTask } from "@/lib/api"
import { Plus, Trash2, CheckSquare, Sparkles } from "lucide-react"

type TaskStatus = Task["status"]

const STATUS_GROUPS: { status: TaskStatus; label: string }[] = [
  { status: "todo",        label: "To do" },
  { status: "in_progress", label: "In progress" },
  { status: "done",        label: "Done" },
]

const STATUS_STYLES: Record<TaskStatus, { bg: string; text: string; border: string }> = {
  todo:        { bg: "rgba(91,127,166,0.10)",  text: "#5B7FA6", border: "rgba(91,127,166,0.25)" },
  in_progress: { bg: "rgba(155,122,61,0.10)",  text: "#9B7A3D", border: "rgba(155,122,61,0.25)" },
  done:        { bg: "rgba(74,124,89,0.10)",   text: "#4A7C59", border: "rgba(74,124,89,0.25)" },
  cancelled:   { bg: "rgba(158,158,158,0.10)", text: "#9e9e9e", border: "rgba(158,158,158,0.25)" },
}

const NEXT_STATUS: Partial<Record<TaskStatus, TaskStatus>> = {
  todo: "in_progress",
  in_progress: "done",
}

function StatusBadge({ status }: { status: TaskStatus }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.todo
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium capitalize"
      style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
    >
      {status.replace("_", " ")}
    </span>
  )
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create form
  const [showForm, setShowForm] = useState(false)
  const [formTitle, setFormTitle] = useState("")
  const [formDesc, setFormDesc] = useState("")
  const [formPriority, setFormPriority] = useState(5)
  const [saving, setSaving] = useState(false)

  // AI extract
  const [extractText, setExtractText] = useState("")
  const [extracting, setExtracting] = useState(false)
  const [suggestions, setSuggestions] = useState<ExtractedTask[]>([])
  const [confirmingIdx, setConfirmingIdx] = useState<number | null>(null)

  useEffect(() => {
    tasksApi
      .list()
      .then(r => setTasks(r.tasks))
      .catch(() => setError("Failed to load tasks"))
      .finally(() => setLoading(false))
  }, [])

  const handleCreate = async () => {
    if (!formTitle.trim()) return
    setSaving(true)
    try {
      const created = await tasksApi.create({
        title: formTitle.trim(),
        description: formDesc.trim() || undefined,
        priority: formPriority,
      })
      setTasks(prev => [created, ...prev])
      setFormTitle("")
      setFormDesc("")
      setFormPriority(5)
      setShowForm(false)
    } catch {
      setError("Failed to create task")
    } finally {
      setSaving(false)
    }
  }

  const handleStatusToggle = async (task: Task) => {
    const next = NEXT_STATUS[task.status]
    if (!next) return
    try {
      const updated = await tasksApi.update(task.id, { status: next })
      setTasks(prev => prev.map(t => (t.id === task.id ? updated : t)))
    } catch {
      setError("Failed to update task")
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await tasksApi.delete(id)
      setTasks(prev => prev.filter(t => t.id !== id))
    } catch {
      setError("Failed to delete task")
    }
  }

  const handleExtract = async () => {
    if (!extractText.trim()) return
    setExtracting(true)
    setSuggestions([])
    try {
      const result = await tasksApi.extract(extractText)
      setSuggestions(result.suggestions)
    } catch {
      setError("Failed to extract tasks")
    } finally {
      setExtracting(false)
    }
  }

  const handleConfirmSuggestion = async (suggestion: ExtractedTask, idx: number) => {
    setConfirmingIdx(idx)
    try {
      const created = await tasksApi.create({
        title: suggestion.title,
        description: suggestion.description,
        priority: suggestion.priority,
        source_origin: "ai_extract",
        ai_confidence: 0.8,
        user_confirmed: true,
      })
      setTasks(prev => [created, ...prev])
      setSuggestions(prev => prev.filter((_, i) => i !== idx))
    } catch {
      setError("Failed to create task from suggestion")
    } finally {
      setConfirmingIdx(null)
    }
  }

  const tasksByStatus = (status: TaskStatus) => tasks.filter(t => t.status === status)

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <CheckSquare size={22} style={{ color: "var(--ec-text)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--ec-text)" }}>
            Tasks
          </h1>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
          style={{ background: "var(--ec-text)", color: "var(--ec-card-bg)" }}
        >
          <Plus size={15} />
          New task
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div
          className="rounded-xl border p-4 mb-6"
          style={{ background: "var(--ec-card-bg)", borderColor: "var(--ec-border)" }}
        >
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--ec-text)" }}>
            New task
          </h2>
          <input
            autoFocus
            value={formTitle}
            onChange={e => setFormTitle(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleCreate()}
            placeholder="Task title"
            className="w-full rounded-lg border px-3 py-2 text-sm mb-2 outline-none"
            style={{
              background: "var(--ec-input-bg, var(--ec-card-bg))",
              borderColor: "var(--ec-border)",
              color: "var(--ec-text)",
            }}
          />
          <textarea
            value={formDesc}
            onChange={e => setFormDesc(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full rounded-lg border px-3 py-2 text-sm mb-2 outline-none resize-none"
            style={{
              background: "var(--ec-input-bg, var(--ec-card-bg))",
              borderColor: "var(--ec-border)",
              color: "var(--ec-text)",
            }}
          />
          <div className="flex items-center gap-2 mb-3">
            <label className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>
              Priority (1=high, 10=low)
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={formPriority}
              onChange={e => setFormPriority(Number(e.target.value))}
              className="w-16 rounded-lg border px-2 py-1 text-sm outline-none"
              style={{
                background: "var(--ec-input-bg, var(--ec-card-bg))",
                borderColor: "var(--ec-border)",
                color: "var(--ec-text)",
              }}
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 rounded-lg text-sm hover:opacity-70"
              style={{ color: "var(--ec-text-subtle)" }}
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={saving || !formTitle.trim()}
              className="px-4 py-1.5 rounded-lg text-sm font-medium disabled:opacity-40 transition-opacity hover:opacity-80"
              style={{ background: "var(--ec-text)", color: "var(--ec-card-bg)" }}
            >
              {saving ? "Creating…" : "Create"}
            </button>
          </div>
        </div>
      )}

      {/* AI Extract */}
      <div
        className="rounded-xl border p-4 mb-6"
        style={{ background: "var(--ec-card-bg)", borderColor: "var(--ec-border)" }}
      >
        <div className="flex items-center gap-2 mb-2">
          <Sparkles size={15} style={{ color: "var(--ec-text-subtle)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--ec-text)" }}>
            Extract tasks from text
          </h2>
        </div>
        <p className="text-xs mb-3" style={{ color: "var(--ec-text-subtle)" }}>
          Paste any text — meeting notes, emails, brain dumps — and AI will suggest tasks. You confirm each one before it is saved.
        </p>
        <textarea
          value={extractText}
          onChange={e => setExtractText(e.target.value)}
          placeholder="Paste your text here…"
          rows={3}
          className="w-full rounded-lg border px-3 py-2 text-sm mb-3 outline-none resize-none"
          style={{
            background: "var(--ec-input-bg, var(--ec-card-bg))",
            borderColor: "var(--ec-border)",
            color: "var(--ec-text)",
          }}
        />
        <button
          onClick={handleExtract}
          disabled={extracting || !extractText.trim()}
          className="px-4 py-1.5 rounded-lg text-sm font-medium disabled:opacity-40 transition-opacity hover:opacity-80"
          style={{ background: "var(--ec-text)", color: "var(--ec-card-bg)" }}
        >
          {extracting ? "Extracting…" : "Extract tasks"}
        </button>

        {suggestions.length > 0 && (
          <div className="mt-4 space-y-2">
            <p className="text-xs font-medium" style={{ color: "var(--ec-text-subtle)" }}>
              {suggestions.length} suggestion{suggestions.length !== 1 ? "s" : ""} — confirm to add
            </p>
            {suggestions.map((s, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between rounded-lg border px-3 py-2 gap-3"
                style={{ borderColor: "var(--ec-border)" }}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate" style={{ color: "var(--ec-text)" }}>
                    {s.title}
                  </p>
                  {s.description && (
                    <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>
                      {s.description}
                    </p>
                  )}
                  <span className="text-[11px]" style={{ color: "var(--ec-text-subtle)" }}>
                    Priority {s.priority}
                  </span>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => setSuggestions(prev => prev.filter((_, i) => i !== idx))}
                    className="px-2 py-1 rounded text-xs hover:opacity-70"
                    style={{ color: "var(--ec-text-subtle)" }}
                  >
                    Dismiss
                  </button>
                  <button
                    onClick={() => handleConfirmSuggestion(s, idx)}
                    disabled={confirmingIdx === idx}
                    className="px-3 py-1 rounded text-xs font-medium disabled:opacity-40 hover:opacity-80"
                    style={{ background: "var(--ec-text)", color: "var(--ec-card-bg)" }}
                  >
                    {confirmingIdx === idx ? "Adding…" : "Add task"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <p className="text-sm mb-4" style={{ color: "#B04A3A" }}>
          {error}
        </p>
      )}

      {/* Tasks grouped by status */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div
              key={i}
              className="h-14 rounded-xl animate-pulse"
              style={{ background: "var(--ec-card-bg)" }}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {STATUS_GROUPS.map(({ status, label }) => {
            const group = tasksByStatus(status)
            if (group.length === 0) return null
            return (
              <section key={status}>
                <h3
                  className="text-xs font-semibold uppercase tracking-wider mb-2"
                  style={{ color: "var(--ec-text-subtle)" }}
                >
                  {label} ({group.length})
                </h3>
                <ul className="space-y-2">
                  {group.map(task => (
                    <li
                      key={task.id}
                      className="flex items-start justify-between rounded-xl border p-3 gap-3"
                      style={{ background: "var(--ec-card-bg)", borderColor: "var(--ec-border)" }}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                          <span
                            className="text-sm font-medium truncate"
                            style={{ color: "var(--ec-text)" }}
                          >
                            {task.title}
                          </span>
                          <StatusBadge status={task.status} />
                        </div>
                        {task.description && (
                          <p className="text-xs line-clamp-1" style={{ color: "var(--ec-text-subtle)" }}>
                            {task.description}
                          </p>
                        )}
                        <span className="text-[11px]" style={{ color: "var(--ec-text-subtle)" }}>
                          Priority {task.priority}
                          {task.source_origin === "ai_extract" ? " · AI suggested" : ""}
                        </span>
                      </div>
                      <div className="flex gap-1.5 shrink-0">
                        {NEXT_STATUS[task.status] && (
                          <button
                            onClick={() => handleStatusToggle(task)}
                            title={`Move to ${NEXT_STATUS[task.status]?.replace("_", " ")}`}
                            className="p-1.5 rounded-lg transition-opacity hover:opacity-60"
                            style={{ color: "var(--ec-text-subtle)" }}
                          >
                            <CheckSquare size={14} />
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(task.id)}
                          title="Delete task"
                          className="p-1.5 rounded-lg transition-opacity hover:opacity-60"
                          style={{ color: "var(--ec-text-subtle)" }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}

          {tasks.length === 0 && (
            <div
              className="rounded-xl border p-8 text-center"
              style={{ borderColor: "var(--ec-border)" }}
            >
              <CheckSquare size={32} className="mx-auto mb-2 opacity-30" style={{ color: "var(--ec-text)" }} />
              <p className="text-sm" style={{ color: "var(--ec-text-subtle)" }}>
                No tasks yet. Create one or extract from text above.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 5: Run the full backend test suite one final time**

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest /Users/catiamachado/RelevanceEthicCompanion/backend/tests/test_projects_tasks.py -v
```

Expected: all 19 tests pass.

- [ ] **Step 6: Commit**

```bash
git add /Users/catiamachado/RelevanceEthicCompanion/frontend/app/dashboard/projects/page.tsx \
        /Users/catiamachado/RelevanceEthicCompanion/frontend/app/dashboard/tasks/page.tsx \
        /Users/catiamachado/RelevanceEthicCompanion/frontend/components/sidebar.tsx
git commit -m "feat: add Projects and Tasks frontend pages + sidebar nav (Sprint 4)"
```
