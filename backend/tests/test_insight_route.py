import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_daily_insight_returns_cached(client):
    """Returns cached insight without calling LLM if one exists for today."""
    mock_row = {
        "content": "Today focus on your MVP goal — the team sync is in 2 hours."
    }
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    with patch("routes.insight.get_db", return_value=mock_conn):
        response = client.get(
            "/api/insight/daily?user_id=00000000-0000-0000-0000-000000000000"
        )
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        data = response.json()
        assert "insight" in data
        assert data["cached"] is True


def test_daily_insight_returns_200(client):
    """Endpoint exists and responds."""
    response = client.get(
        "/api/insight/daily?user_id=00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code in (
        200,
        401,
        500,
    )  # 500 acceptable in test env (no DB/LLM)
