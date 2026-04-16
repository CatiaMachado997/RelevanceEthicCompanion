import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_put_status_unauthenticated():
    # Must enable auth enforcement — dev mode falls back to mock user otherwise
    with patch("utils.supabase_auth.settings") as mock_settings:
        mock_settings.AUTH_ENFORCEMENT_ENABLED = True
        mock_settings.ENVIRONMENT = "production"
        mock_settings.AUTH_ENFORCE_WRITE_ROUTES = True
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.put("/api/status/", json={"status": "focus"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_put_status_invalid_value():
    with patch("utils.supabase_auth.get_current_user_id", return_value="user-1"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.put("/api/status/", json={"status": "invalid_status"})
    assert r.status_code == 422
