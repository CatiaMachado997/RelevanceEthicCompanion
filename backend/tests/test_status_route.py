import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from main import app
from utils.supabase_auth import get_current_user_id


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
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.put("/api/status/", json={"status": "invalid_status"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert r.status_code == 422
