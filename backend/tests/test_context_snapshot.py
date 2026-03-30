# backend/tests/test_context_snapshot.py
"""Tests for ContextSnapshotService and GET /api/context/snapshot."""
import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def make_db_mock(fetchall_values=None, fetchone_value=None):
    """
    Return a callable that acts as a context-manager mock for get_db_connection().
    """
    if fetchall_values is None:
        fetchall_values = []
    if fetchone_value is None:
        fetchone_value = {"cnt": 0}

    cur = MagicMock()
    cur.fetchall.return_value = fetchall_values
    cur.fetchone.return_value = fetchone_value

    cur_ctx = MagicMock()
    cur_ctx.__enter__ = MagicMock(return_value=cur)
    cur_ctx.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cur_ctx
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def _db():
        yield conn

    return _db


# ── ContextSnapshotService ────────────────────────────────────────────────────

def test_compute_returns_all_required_keys():
    """compute() returns a dict with every required snapshot key."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    for key in ("computed_at", "tasks_due_soon", "overdue_count",
                "active_projects", "upcoming_events", "active_goals",
                "calendar_pressure"):
        assert key in snapshot, f"Missing key: {key}"


def test_calendar_pressure_light_when_no_events():
    """calendar_pressure is 'light' when there are zero upcoming events."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    assert snapshot["calendar_pressure"] == "light"


def test_calendar_pressure_valid_values():
    """calendar_pressure is always one of the three valid strings."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    assert snapshot["calendar_pressure"] in ("light", "moderate", "heavy")


def test_overdue_count_from_db():
    """overdue_count is taken from the fetchone result."""
    with patch("services.context_snapshot.get_db_connection",
               make_db_mock(fetchone_value={"cnt": 3})):
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute("00000000-0000-0000-0000-000000000000")

    assert snapshot["overdue_count"] == 3


# ── Route ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_read_auth(monkeypatch):
    monkeypatch.setattr(
        "utils.supabase_auth.get_current_read_user_id",
        lambda: "00000000-0000-0000-0000-000000000000",
    )


def test_snapshot_route_returns_200(mock_read_auth):
    """GET /api/context/snapshot returns 200 with snapshot keys."""
    with patch("services.context_snapshot.get_db_connection", make_db_mock()):
        from main import app
        client = TestClient(app)
        response = client.get("/api/context/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert "computed_at" in data
    assert "calendar_pressure" in data
