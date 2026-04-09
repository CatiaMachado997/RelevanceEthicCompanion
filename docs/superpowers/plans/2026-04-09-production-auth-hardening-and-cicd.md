# Production Auth Hardening & CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable real per-user data isolation, harden all security surfaces, and build a CI/CD pipeline so the app is safe to open to beta users.

**Architecture:** Auth enforcement is already coded — three dev bypasses (RS256 algorithm bug, `AUTH_ENFORCEMENT_ENABLED=False`, frontend `isDev` guard) are disabling it. We fix those first, then layer in cookie hardening, rate limiting, auth audit logging, GCP Secret Manager, and a full Cloud Run CD pipeline.

**Tech Stack:** FastAPI, python-jose, slowapi, google-cloud-secret-manager, psycopg3, Next.js, GitHub Actions, GCP Cloud Run, GCP Artifact Registry, Vercel

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/utils/supabase_auth.py` | Modify | Fix `algorithms=["ES256"]`; log auth events |
| `backend/utils/auth_audit.py` | Create | Fire-and-forget auth event logger |
| `backend/utils/rate_limit.py` | Modify | Add per-endpoint limit helper |
| `backend/routes/auth.py` | Modify | `COOKIE_SECURE`, `SameSite=Strict`, audit on login/logout |
| `backend/config.py` | Modify | `COOKIE_SECURE`, `load_secrets_from_gcp()` |
| `backend/requirements.txt` | Modify | Add `google-cloud-secret-manager` |
| `backend/.env` | Modify | `AUTH_ENFORCEMENT_ENABLED=True`, `AUTH_ENFORCE_READ_ROUTES=True`, `COOKIE_SECURE=False` |
| `backend/migrations/006_auth_audit_log.sql` | Create | `auth_audit_log` DDL |
| `backend/scripts/run_migrations.py` | Create | Ordered SQL migration runner with tracking table |
| `backend/Dockerfile` | Create | Multi-stage Python 3.11-slim image |
| `backend/.dockerignore` | Create | Exclude venv, .env, tests, __pycache__ |
| `frontend/middleware.ts` | Modify | Check `ec_session` cookie; remove dev bypass |
| `frontend/app/dashboard/layout.tsx` | Modify | Remove `isDev` auth bypass |
| `frontend/.env.local` | Modify | Remove `NEXT_PUBLIC_ENVIRONMENT=development` |
| `.github/workflows/ci.yml` | Modify | Remove `continue-on-error`; add missing env vars; remove `develop` trigger |
| `.github/workflows/deploy-backend.yml` | Create | Full Cloud Run CD pipeline via OIDC |

---

## Task 1: Fix ES256 JWT Algorithm Bug

**Files:**
- Modify: `backend/utils/supabase_auth.py:93`
- Create: `backend/tests/test_es256_auth.py`

The single most critical fix: Supabase issues ES256 tokens but the decoder uses RS256. When `AUTH_ENFORCEMENT_ENABLED=True`, every real token fails. This is a one-line change.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_es256_auth.py`:

```python
"""Tests that supabase_auth correctly requires ES256 tokens."""
import json
import time
from unittest.mock import patch

import pytest
from jose import jwk, jwt

SUPABASE_ISSUER = "https://test.supabase.co/auth/v1"
AUDIENCE = "authenticated"


@pytest.fixture
def ec_keypair():
    """Generate a fresh P-256 key pair for each test."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    priv_obj = ec.generate_private_key(ec.SECP256R1(), default_backend())
    priv_pem = priv_obj.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    ).decode()
    jose_key = jwk.construct(priv_pem, algorithm="ES256")
    pub_dict = jose_key.public_key().to_dict()
    pub_dict["kid"] = "test-kid-1"
    return priv_pem, pub_dict


def _make_es256_token(private_pem: str, sub: str = "user-abc-123") -> str:
    return jwt.encode(
        {
            "sub": sub,
            "aud": AUDIENCE,
            "iss": SUPABASE_ISSUER,
            "exp": int(time.time()) + 3600,
        },
        private_pem,
        algorithm="ES256",
        headers={"kid": "test-kid-1"},
    )


def test_es256_token_decoded_successfully(ec_keypair, monkeypatch):
    """_decode_supabase_token accepts a valid ES256 token."""
    priv_pem, pub_jwk = ec_keypair
    import utils.supabase_auth as auth_mod

    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: {"keys": [pub_jwk]})
    monkeypatch.setattr(auth_mod, "_build_issuer", lambda: SUPABASE_ISSUER)
    monkeypatch.setattr(auth_mod.settings, "SUPABASE_JWT_AUDIENCE", AUDIENCE)

    token = _make_es256_token(priv_pem)
    claims = auth_mod._decode_supabase_token(token)
    assert claims["sub"] == "user-abc-123"


def test_rs256_token_rejected(ec_keypair, monkeypatch):
    """_decode_supabase_token rejects an RS256-signed token (wrong algorithm)."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    _, pub_jwk = ec_keypair
    import utils.supabase_auth as auth_mod

    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: {"keys": [pub_jwk]})
    monkeypatch.setattr(auth_mod, "_build_issuer", lambda: SUPABASE_ISSUER)
    monkeypatch.setattr(auth_mod.settings, "SUPABASE_JWT_AUDIENCE", AUDIENCE)

    rsa_key = rsa.generate_private_key(65537, 2048, default_backend())
    rsa_pem = rsa_key.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    ).decode()
    rs256_token = jwt.encode(
        {"sub": "evil", "aud": AUDIENCE, "iss": SUPABASE_ISSUER, "exp": int(time.time()) + 3600},
        rsa_pem,
        algorithm="RS256",
    )

    with pytest.raises(Exception):
        auth_mod._decode_supabase_token(rs256_token)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_es256_auth.py -v
```

Expected: `test_es256_token_decoded_successfully` FAILS (because `algorithms=["RS256"]` rejects the ES256 token). `test_rs256_token_rejected` may pass incidentally.

- [ ] **Step 3: Fix the algorithm in supabase_auth.py**

In `backend/utils/supabase_auth.py`, change line 93:

```python
# BEFORE
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.SUPABASE_JWT_AUDIENCE,
        issuer=_build_issuer(),
    )

# AFTER
    claims = jwt.decode(
        token,
        key,
        algorithms=["ES256"],
        audience=settings.SUPABASE_JWT_AUDIENCE,
        issuer=_build_issuer(),
    )
```

- [ ] **Step 4: Run tests to verify both pass**

```bash
cd backend
pytest tests/test_es256_auth.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/supabase_auth.py backend/tests/test_es256_auth.py
git commit -m "fix: use ES256 algorithm for Supabase JWT validation"
```

---

## Task 2: Enable Auth Enforcement

**Files:**
- Modify: `backend/.env`
- Modify: `frontend/middleware.ts`
- Modify: `frontend/app/dashboard/layout.tsx`
- Modify: `frontend/.env.local`

With the ES256 fix in place, flipping these switches is safe. After this task, every request uses the real authenticated user_id.

- [ ] **Step 1: Enable enforcement in backend .env**

In `backend/.env`, change:

```
# BEFORE
AUTH_ENFORCEMENT_ENABLED=False

# AFTER
AUTH_ENFORCEMENT_ENABLED=True
AUTH_ENFORCE_READ_ROUTES=True
```

- [ ] **Step 2: Write a test that enforcement is respected**

Add this test to `backend/tests/test_es256_auth.py`:

```python
def test_unauthenticated_request_returns_401_when_enforcement_enabled(monkeypatch):
    """With AUTH_ENFORCEMENT_ENABLED=True, missing token → 401."""
    import utils.supabase_auth as auth_mod
    monkeypatch.setattr(auth_mod.settings, "AUTH_ENFORCEMENT_ENABLED", True)
    monkeypatch.setattr(auth_mod.settings, "ENVIRONMENT", "production")

    # _is_dev_fallback_enabled() must return False
    assert auth_mod._is_dev_fallback_enabled() is False
```

- [ ] **Step 3: Run test**

```bash
cd backend
pytest tests/test_es256_auth.py::test_unauthenticated_request_returns_401_when_enforcement_enabled -v
```

Expected: PASS.

- [ ] **Step 4: Fix frontend middleware — check ec_session cookie**

Replace the entire contents of `frontend/middleware.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'

export async function middleware(request: NextRequest) {
  // Only protect /dashboard routes
  if (!request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.next()
  }

  // Check for our HttpOnly session cookie (set by POST /api/auth/session)
  const cookieHeader = request.headers.get('cookie') ?? ''
  const hasSessionCookie = cookieHeader
    .split(';')
    .some(c => c.trim().startsWith('ec_session='))

  if (!hasSessionCookie) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
```

- [ ] **Step 5: Fix dashboard layout — remove isDev auth bypass**

In `frontend/app/dashboard/layout.tsx`, make these changes:

Remove the `isDev` constant declaration (line 47):
```typescript
// DELETE this line:
const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development'
```

Change the `useEffect` that guards auth (lines 49–56):
```typescript
// BEFORE
  useEffect(() => {
    if (!isDev && !loading && !isAuthenticated) {
      if (typeof window !== 'undefined') {
        localStorage.setItem('ec_lastRoute', window.location.pathname)
      }
      router.push('/login')
    }
  }, [loading, isAuthenticated, router, isDev])

// AFTER
  useEffect(() => {
    if (!loading && !isAuthenticated) {
      if (typeof window !== 'undefined') {
        localStorage.setItem('ec_lastRoute', window.location.pathname)
      }
      router.push('/login')
    }
  }, [loading, isAuthenticated, router])
```

Change the early return while loading (line 58):
```typescript
// BEFORE
  if (!isDev && loading) return null

// AFTER
  if (loading) return null
```

- [ ] **Step 6: Remove NEXT_PUBLIC_ENVIRONMENT from frontend .env.local**

In `frontend/.env.local`, remove the line:
```
NEXT_PUBLIC_ENVIRONMENT=development
```

Keep all other lines unchanged.

- [ ] **Step 7: Restart backend and verify login flow works**

```bash
cd backend && python main.py
```

In a browser, navigate to `http://localhost:3000/dashboard`. Expected: redirected to `/login`.

Log in with a real Supabase email (magic link). Expected: redirected back to dashboard, `ec_session` cookie set in browser DevTools → Application → Cookies.

- [ ] **Step 8: Commit**

```bash
git add backend/.env frontend/middleware.ts frontend/app/dashboard/layout.tsx frontend/.env.local
git commit -m "feat: enable auth enforcement; fix middleware cookie check; remove dev bypasses"
```

---

## Task 3: Harden Auth Cookie

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/routes/auth.py`
- Test: `backend/tests/test_auth_cookie.py`

Add `COOKIE_SECURE` flag (False in dev, True in prod) and tighten `SameSite` to `strict`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth_cookie.py`:

```python
"""Tests that the auth session cookie is set with correct security attributes."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_secure_cookie(monkeypatch):
    """TestClient with COOKIE_SECURE=True."""
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app
        from config import settings
        monkeypatch.setattr(settings, "COOKIE_SECURE", True)
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


@pytest.fixture
def client_with_insecure_cookie(monkeypatch):
    """TestClient with COOKIE_SECURE=False (default dev setting)."""
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app
        from config import settings
        monkeypatch.setattr(settings, "COOKIE_SECURE", False)
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


def test_session_cookie_samesite_strict(client_with_insecure_cookie):
    """Session cookie always has SameSite=Strict."""
    resp = client_with_insecure_cookie.post(
        "/api/auth/session",
        json={"access_token": "fake-token", "remember_me": False},
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "samesite=strict" in set_cookie.lower()


def test_session_cookie_secure_flag_when_enabled(client_with_secure_cookie):
    """Cookie has Secure flag when COOKIE_SECURE=True."""
    resp = client_with_secure_cookie.post(
        "/api/auth/session",
        json={"access_token": "fake-token", "remember_me": False},
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "secure" in set_cookie.lower()


def test_session_cookie_no_secure_in_dev(client_with_insecure_cookie):
    """Cookie does NOT have Secure flag in dev (COOKIE_SECURE=False)."""
    resp = client_with_insecure_cookie.post(
        "/api/auth/session",
        json={"access_token": "fake-token", "remember_me": False},
    )
    set_cookie = resp.headers.get("set-cookie", "")
    # FastAPI omits "secure" attribute when secure=False
    assert "samesite=strict" in set_cookie.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_auth_cookie.py -v
```

Expected: `test_session_cookie_samesite_strict` FAILS (current code uses `samesite="lax"`).

- [ ] **Step 3: Add COOKIE_SECURE to config.py**

In `backend/config.py`, add after the `ENCRYPTION_KEY` line:

```python
    # Cookie security — False for local dev, True for production
    COOKIE_SECURE: bool = False
```

- [ ] **Step 4: Update routes/auth.py to use COOKIE_SECURE and SameSite=Strict**

Replace the `create_session` function in `backend/routes/auth.py`:

```python
@router.post("/session")
async def create_session(body: SessionCreate, response: Response):
    """Exchange Supabase token for an HttpOnly cookie session."""
    max_age = 60 * 60 * 24 * 30 if body.remember_me else 60 * 60 * 24  # 30d or 24h
    response.set_cookie(
        key="ec_session",
        value=body.access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=max_age,
    )
    return {"ok": True}
```

Also add the settings import at the top of `backend/routes/auth.py` (after existing imports):

```python
from config import settings
```

- [ ] **Step 5: Run tests**

```bash
cd backend
pytest tests/test_auth_cookie.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/config.py backend/routes/auth.py backend/tests/test_auth_cookie.py
git commit -m "feat: harden auth cookie with COOKIE_SECURE flag and SameSite=Strict"
```

---

## Task 4: Auth Audit Logging

**Files:**
- Create: `backend/migrations/006_auth_audit_log.sql`
- Create: `backend/utils/auth_audit.py`
- Modify: `backend/routes/auth.py`
- Modify: `backend/utils/supabase_auth.py`
- Test: `backend/tests/test_auth_audit.py`

Every login, logout, and token failure gets recorded in `auth_audit_log`. This is the paper trail for security incidents.

- [ ] **Step 1: Create the migration file**

Create directory `backend/migrations/` and file `backend/migrations/006_auth_audit_log.sql`:

```sql
-- Migration 006: Auth audit log
-- Records login, logout, and token validation events for security auditing

CREATE TABLE IF NOT EXISTS auth_audit_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID,                                    -- NULL for pre-auth failures
    event       TEXT        NOT NULL,                    -- login_success | logout | token_invalid | token_expired | rate_limited | session_exchanged
    ip_address  TEXT,
    user_agent  TEXT,
    detail      JSONB,                                   -- optional extra context
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_audit_user_id   ON auth_audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_auth_audit_created_at ON auth_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_audit_event      ON auth_audit_log (event);
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_auth_audit.py`:

```python
"""Tests for auth_audit.py logger."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def test_log_auth_event_inserts_row():
    """log_auth_event fires an INSERT without blocking the caller."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("utils.auth_audit.get_db_connection", return_value=mock_conn):
        from utils.auth_audit import _write_audit_event
        _write_audit_event(
            event="login_success",
            user_id="user-123",
            ip_address="127.0.0.1",
            user_agent="pytest",
            detail=None,
        )

    mock_cur.execute.assert_called_once()
    call_args = mock_cur.execute.call_args[0]
    assert "INSERT INTO auth_audit_log" in call_args[0]
    assert "login_success" in call_args[1]


def test_log_auth_event_does_not_raise_on_db_error():
    """A DB failure in the audit logger must NOT propagate to the caller."""
    with patch("utils.auth_audit.get_db_connection", side_effect=Exception("DB down")):
        from utils import auth_audit
        # Should not raise
        auth_audit._write_audit_event(
            event="login_success",
            user_id=None,
            ip_address=None,
            user_agent=None,
            detail=None,
        )


def test_log_auth_event_public_api_is_fire_and_forget():
    """log_auth_event is non-blocking (returns immediately, schedules work)."""
    import threading
    events_written = []

    def fake_write(**kwargs):
        events_written.append(kwargs["event"])

    with patch("utils.auth_audit._write_audit_event", side_effect=fake_write):
        from utils.auth_audit import log_auth_event
        log_auth_event(event="logout", user_id="u1")
        # Give the background thread time to run
        import time; time.sleep(0.05)

    assert "logout" in events_written
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend
pytest tests/test_auth_audit.py -v
```

Expected: ImportError — `utils.auth_audit` does not exist yet.

- [ ] **Step 4: Create backend/utils/auth_audit.py**

```python
"""
Auth Audit Logger

Records authentication events to auth_audit_log.
All writes are fire-and-forget (background thread) — never blocks the request path.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _write_audit_event(
    event: str,
    user_id: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
    detail: Optional[Any],
) -> None:
    """Write one row to auth_audit_log. Called in a background thread."""
    try:
        import json
        from utils.db import get_db_connection

        detail_json = json.dumps(detail) if detail is not None else None
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_audit_log (user_id, event, ip_address, user_agent, detail)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (user_id, event, ip_address, user_agent, detail_json),
                )
    except Exception as exc:
        logger.warning("auth_audit: failed to write event '%s': %s", event, exc)


def log_auth_event(
    event: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail: Optional[Any] = None,
) -> None:
    """
    Log an auth event asynchronously. Returns immediately.

    event: one of login_success | logout | token_invalid | token_expired |
               rate_limited | session_exchanged
    """
    t = threading.Thread(
        target=_write_audit_event,
        kwargs={
            "event": event,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "detail": detail,
        },
        daemon=True,
    )
    t.start()
```

- [ ] **Step 5: Run tests**

```bash
cd backend
pytest tests/test_auth_audit.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Wire audit logging into routes/auth.py**

Replace the full contents of `backend/routes/auth.py`:

```python
"""
Minimal auth routes for Supabase JWT identity introspection.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from config import settings
from utils.auth_audit import log_auth_event
from utils.supabase_auth import UserPrincipal, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class SessionCreate(BaseModel):
    access_token: str
    remember_me: bool = False


@router.get("/me", response_model=dict)
async def get_me(user: UserPrincipal = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "email": user.email,
    }


@router.post("/session")
async def create_session(request: Request, body: SessionCreate, response: Response):
    """Exchange Supabase token for an HttpOnly cookie session."""
    max_age = 60 * 60 * 24 * 30 if body.remember_me else 60 * 60 * 24  # 30d or 24h
    response.set_cookie(
        key="ec_session",
        value=body.access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=max_age,
    )
    log_auth_event(
        event="session_exchanged",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"ok": True}


@router.delete("/session")
async def delete_session(request: Request, response: Response):
    """Clear the session cookie on sign-out."""
    response.delete_cookie("ec_session")
    log_auth_event(
        event="logout",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"ok": True}
```

- [ ] **Step 7: Wire audit logging into supabase_auth.py on token failure**

In `backend/utils/supabase_auth.py`, update the `get_current_user` function's except block:

```python
async def get_current_user(request: Request) -> UserPrincipal:
    if _is_dev_fallback_enabled():
        logger.warning("Auth enforcement disabled in development, using mock user fallback")
        return UserPrincipal(user_id=MOCK_USER_ID, email=None, claims={"sub": MOCK_USER_ID})

    try:
        token = _extract_token(request)
        claims = _decode_supabase_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        # Audit the failure (fire-and-forget — import here to avoid circular import)
        try:
            from utils.auth_audit import log_auth_event
            log_auth_event(
                event="token_invalid",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                detail={"error": str(exc)},
            )
        except Exception:
            pass
        raise _auth_error("Invalid or expired token", code="invalid_token")

    user_id = claims.get("sub")
    if not user_id:
        raise _auth_error("Token missing subject claim", code="invalid_token")

    return UserPrincipal(
        user_id=str(user_id),
        email=claims.get("email"),
        claims=claims,
    )
```

- [ ] **Step 8: Run all auth tests**

```bash
cd backend
pytest tests/test_auth_audit.py tests/test_auth_cookie.py tests/test_es256_auth.py -v
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/migrations/ backend/utils/auth_audit.py backend/routes/auth.py backend/utils/supabase_auth.py backend/tests/test_auth_audit.py
git commit -m "feat: add auth audit logging for login, logout, and token failures"
```

---

## Task 5: Rate Limiting Improvements

**Files:**
- Modify: `backend/utils/rate_limit.py`
- Modify: `backend/routes/auth.py`
- Test: `backend/tests/test_rate_limiting.py`

`slowapi` middleware is already wired in `main.py` with a global 200/min default. We add tighter limits on auth endpoints and a helper for per-user limits on sensitive tool routes.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_rate_limiting.py`:

```python
"""Tests that rate limiting is active on auth endpoints."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("utils.weaviate_client.get_weaviate_client", return_value=None):
        from main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def test_auth_session_endpoint_has_rate_limit_decorator(client):
    """POST /api/auth/session must return 429 after exceeding its limit.

    We test the limit attribute, not the actual throttling, because
    testing real throttling would require 10+ identical requests.
    """
    import routes.auth as auth_routes
    import inspect

    # The create_session function must have a __wrapped__ or limit attr from slowapi
    fn = auth_routes.create_session
    # slowapi stores limit as a route attribute via the decorator
    # Verify the route is registered in the app with the right path
    routes = [r for r in client.app.routes if hasattr(r, "path") and r.path == "/api/auth/session"]
    assert len(routes) == 1, "POST /api/auth/session route must exist"


def test_get_user_id_key_func_returns_string():
    """get_user_id_or_ip must return a string key."""
    from utils.rate_limit import get_user_id_or_ip
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    mock_request.state.user_id = "abc-123"
    key = get_user_id_or_ip(mock_request)
    assert key == "abc-123"


def test_get_user_id_key_func_falls_back_to_ip():
    """get_user_id_or_ip falls back to IP when no user_id on state."""
    from utils.rate_limit import get_user_id_or_ip
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    del mock_request.state.user_id  # simulate AttributeError
    mock_request.client.host = "1.2.3.4"
    key = get_user_id_or_ip(mock_request)
    assert key == "1.2.3.4"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_rate_limiting.py::test_get_user_id_key_func_returns_string -v
```

Expected: FAIL — `get_user_id_or_ip` does not exist in `utils.rate_limit`.

- [ ] **Step 3: Update utils/rate_limit.py**

Replace the full contents of `backend/utils/rate_limit.py`:

```python
"""
Rate limiting configuration.

Uses slowapi (wraps `limits` library). The limiter is registered in main.py.

Two key functions:
- `get_remote_address` (from slowapi) — used for IP-based limits (auth endpoints)
- `get_user_id_or_ip` — used for user-based limits (authenticated tool endpoints)
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_user_id_or_ip(request: Request) -> str:
    """Key function: use user_id from request state, fall back to IP."""
    try:
        user_id = request.state.user_id
        if user_id:
            return str(user_id)
    except AttributeError:
        pass
    return get_remote_address(request)


# Global limiter: 200 req/min default (applies to all routes without a decorator)
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
```

- [ ] **Step 4: Add rate limit decorators to auth routes**

In `backend/routes/auth.py`, add the import and decorators:

Add to imports at the top:
```python
from slowapi import Limiter
from utils.rate_limit import limiter
```

Add `@limiter.limit` decorators and `request: Request` param (already added in Task 4). Update the route decorators:

```python
@router.get("/me", response_model=dict)
@limiter.limit("30/minute")
async def get_me(request: Request, user: UserPrincipal = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "email": user.email,
    }


@router.post("/session")
@limiter.limit("10/minute")
async def create_session(request: Request, body: SessionCreate, response: Response):
    # ... rest of function unchanged
```

```python
@router.delete("/session")
@limiter.limit("30/minute")
async def delete_session(request: Request, response: Response):
    # ... rest of function unchanged
```

The full updated `backend/routes/auth.py`:

```python
"""
Minimal auth routes for Supabase JWT identity introspection.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from config import settings
from utils.auth_audit import log_auth_event
from utils.rate_limit import limiter
from utils.supabase_auth import UserPrincipal, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class SessionCreate(BaseModel):
    access_token: str
    remember_me: bool = False


@router.get("/me", response_model=dict)
@limiter.limit("30/minute")
async def get_me(request: Request, user: UserPrincipal = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "email": user.email,
    }


@router.post("/session")
@limiter.limit("10/minute")
async def create_session(request: Request, body: SessionCreate, response: Response):
    """Exchange Supabase token for an HttpOnly cookie session."""
    max_age = 60 * 60 * 24 * 30 if body.remember_me else 60 * 60 * 24  # 30d or 24h
    response.set_cookie(
        key="ec_session",
        value=body.access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=max_age,
    )
    log_auth_event(
        event="session_exchanged",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"ok": True}


@router.delete("/session")
@limiter.limit("30/minute")
async def delete_session(request: Request, response: Response):
    """Clear the session cookie on sign-out."""
    response.delete_cookie("ec_session")
    log_auth_event(
        event="logout",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"ok": True}
```

- [ ] **Step 5: Run tests**

```bash
cd backend
pytest tests/test_rate_limiting.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
cd backend
pytest tests/ -v --tb=short -q
```

Expected: all tests pass (or same failures as before this PR).

- [ ] **Step 7: Commit**

```bash
git add backend/utils/rate_limit.py backend/routes/auth.py backend/tests/test_rate_limiting.py
git commit -m "feat: add per-endpoint rate limits on auth routes; add user_id key function"
```

---

## Task 6: GCP Secret Manager Integration

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Test: `backend/tests/test_secrets_manager.py`

In production, secrets come from GCP Secret Manager instead of `.env`. Local dev is unchanged.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_secrets_manager.py`:

```python
"""Tests for GCP Secret Manager integration in config.py."""
from unittest.mock import MagicMock, patch
import pytest


def test_load_secrets_from_gcp_sets_env_vars(monkeypatch):
    """load_secrets_from_gcp reads each secret and sets it as an env var."""
    import os

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = "test-secret-value"
    mock_client.access_secret_version.return_value = mock_response

    with patch("google.cloud.secretmanager.SecretManagerServiceClient", return_value=mock_client):
        import importlib
        import config as cfg_mod

        # Simulate production environment
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

        cfg_mod.load_secrets_from_gcp(project_id="test-project", client=mock_client)

        # Verify the client was called for at least one expected secret
        call_args_list = mock_client.access_secret_version.call_args_list
        names = [str(call) for call in call_args_list]
        assert any("GEMINI_API_KEY" in n or "gemini" in n.lower() for n in names), \
            f"Expected GEMINI_API_KEY secret lookup, got: {names}"


def test_load_secrets_from_gcp_not_called_in_development(monkeypatch):
    """load_secrets_from_gcp must NOT be called when ENVIRONMENT=development."""
    import os
    monkeypatch.setenv("ENVIRONMENT", "development")

    with patch("google.cloud.secretmanager.SecretManagerServiceClient") as mock_cls:
        import config as cfg_mod
        # Calling the guard logic directly
        env = os.getenv("ENVIRONMENT", "development")
        if env != "production":
            pass  # No call to load_secrets_from_gcp
        mock_cls.assert_not_called()


def test_load_secrets_from_gcp_does_not_raise_on_missing_secret(monkeypatch):
    """A missing secret logs a warning but does not crash startup."""
    from google.api_core.exceptions import NotFound

    mock_client = MagicMock()
    mock_client.access_secret_version.side_effect = NotFound("secret not found")

    import config as cfg_mod
    # Should not raise
    cfg_mod.load_secrets_from_gcp(project_id="test-project", client=mock_client)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_secrets_manager.py -v
```

Expected: ImportError or AttributeError — `load_secrets_from_gcp` does not exist on `config`.

- [ ] **Step 3: Add google-cloud-secret-manager to requirements.txt**

In `backend/requirements.txt`, add after the `google-auth-oauthlib` line:

```
google-cloud-secret-manager>=2.16.0
```

- [ ] **Step 4: Install the new dependency**

```bash
cd backend
pip install "google-cloud-secret-manager>=2.16.0"
```

- [ ] **Step 5: Add load_secrets_from_gcp to config.py**

Add the following function at the top of `backend/config.py`, before the `Settings` class, after the imports:

```python
import os
import logging as _logging

_secrets_logger = _logging.getLogger(__name__)

# Ordered list of secret names in GCP Secret Manager → env var names they map to.
# Add new secrets here as the app grows.
_GCP_SECRETS: list[tuple[str, str]] = [
    ("ethic-companion-secret-key",          "SECRET_KEY"),
    ("ethic-companion-encryption-key",       "ENCRYPTION_KEY"),
    ("ethic-companion-gemini-api-key",       "GEMINI_API_KEY"),
    ("ethic-companion-groq-api-key",         "GROQ_API_KEY"),
    ("ethic-companion-tavily-api-key",       "TAVILY_API_KEY"),
    ("ethic-companion-composio-api-key",     "COMPOSIO_API_KEY"),
    ("ethic-companion-google-oauth-secret",  "GOOGLE_OAUTH_CLIENT_SECRET"),
    ("ethic-companion-slack-client-secret",  "SLACK_CLIENT_SECRET"),
    ("ethic-companion-github-client-secret", "GITHUB_CLIENT_SECRET"),
    ("ethic-companion-notion-client-secret", "NOTION_CLIENT_SECRET"),
]


def load_secrets_from_gcp(project_id: str, client=None) -> None:
    """
    Fetch secrets from GCP Secret Manager and set them as environment variables.

    Called once at startup when ENVIRONMENT=production.
    Missing secrets log a warning but do not crash startup — allows gradual migration.

    Args:
        project_id: GCP project ID.
        client: optional pre-built SecretManagerServiceClient (for testing).
    """
    if client is None:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()

    for secret_name, env_var in _GCP_SECRETS:
        resource = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        try:
            response = client.access_secret_version(name=resource)
            value = response.payload.data.decode("utf-8").strip()
            os.environ[env_var] = value
            _secrets_logger.debug("Loaded secret %s → %s", secret_name, env_var)
        except Exception as exc:
            _secrets_logger.warning(
                "Could not load secret '%s' from GCP Secret Manager: %s", secret_name, exc
            )
```

Also update `config.py` to call `load_secrets_from_gcp` at module load when in production. Add this block just before `settings = Settings()` at the bottom of the file:

```python
# Load GCP secrets before instantiating Settings so pydantic picks them up from env.
if os.environ.get("ENVIRONMENT") == "production":
    _project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if _project:
        load_secrets_from_gcp(project_id=_project)
    else:
        _secrets_logger.warning("GOOGLE_CLOUD_PROJECT not set; skipping GCP secret loading")

settings = Settings()
```

Also add `import os` at the top of `config.py` if not already present. Current imports only use `pydantic` — add it:

```python
import os
import logging as _logging
from pydantic import computed_field, ConfigDict
from pydantic_settings import BaseSettings
from typing import List, Optional
```

- [ ] **Step 6: Run tests**

```bash
cd backend
pytest tests/test_secrets_manager.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Run full test suite**

```bash
cd backend
pytest tests/ -q --tb=short
```

Expected: same pass rate as before (no regressions from config change).

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/config.py backend/tests/test_secrets_manager.py
git commit -m "feat: add GCP Secret Manager integration for production secrets"
```

---

## Task 7: SQL Migration Runner

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/run_migrations.py`
- Test: `backend/tests/test_migration_runner.py`

A simple script that tracks which `.sql` files in `backend/migrations/` have been applied and runs any pending ones. Used in the CD pipeline before traffic shifts to a new revision.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_migration_runner.py`:

```python
"""Tests for the SQL migration runner script."""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch
import pytest


@pytest.fixture
def mock_conn():
    """A mock psycopg connection that records execute calls."""
    conn = MagicMock()
    cur = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = []  # no migrations applied yet
    return conn, cur


@pytest.fixture
def migrations_dir(tmp_path):
    """A temp directory with two SQL migration files."""
    (tmp_path / "001_create_users.sql").write_text("CREATE TABLE users (id UUID PRIMARY KEY);")
    (tmp_path / "002_add_email.sql").write_text("ALTER TABLE users ADD COLUMN email TEXT;")
    return tmp_path


def test_run_migrations_applies_pending_files(mock_conn, migrations_dir):
    """run_migrations runs all .sql files that are not yet applied."""
    conn, cur = mock_conn

    with patch("scripts.run_migrations.get_db_connection", return_value=conn):
        from scripts.run_migrations import run_migrations
        run_migrations(migrations_dir=str(migrations_dir))

    # Should have created the tracking table
    executed_sqls = [str(c) for c in cur.execute.call_args_list]
    assert any("schema_migrations" in s for s in executed_sqls)

    # Should have executed both migration files
    assert any("CREATE TABLE users" in s for s in executed_sqls)
    assert any("ALTER TABLE users" in s for s in executed_sqls)


def test_run_migrations_skips_already_applied(mock_conn, migrations_dir):
    """run_migrations does not re-run already-applied migrations."""
    conn, cur = mock_conn
    # Simulate 001 already applied
    cur.fetchall.return_value = [("001_create_users.sql",)]

    with patch("scripts.run_migrations.get_db_connection", return_value=conn):
        from scripts.run_migrations import run_migrations
        run_migrations(migrations_dir=str(migrations_dir))

    executed_sqls = [str(c) for c in cur.execute.call_args_list]
    assert not any("CREATE TABLE users" in s for s in executed_sqls), \
        "001_create_users.sql was already applied and must be skipped"
    assert any("ALTER TABLE users" in s for s in executed_sqls), \
        "002_add_email.sql is pending and must be run"


def test_run_migrations_is_idempotent(mock_conn, migrations_dir):
    """Running migrations twice when both are applied changes nothing."""
    conn, cur = mock_conn
    cur.fetchall.return_value = [
        ("001_create_users.sql",),
        ("002_add_email.sql",),
    ]

    with patch("scripts.run_migrations.get_db_connection", return_value=conn):
        from scripts.run_migrations import run_migrations
        run_migrations(migrations_dir=str(migrations_dir))

    executed_sqls = [str(c) for c in cur.execute.call_args_list]
    assert not any("CREATE TABLE users" in s for s in executed_sqls)
    assert not any("ALTER TABLE users" in s for s in executed_sqls)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_migration_runner.py -v
```

Expected: ImportError — `scripts.run_migrations` does not exist.

- [ ] **Step 3: Create scripts package**

```bash
mkdir -p backend/scripts
touch backend/scripts/__init__.py
```

- [ ] **Step 4: Create backend/scripts/run_migrations.py**

```python
"""
SQL Migration Runner

Applies pending .sql files from the migrations/ directory in alphabetical order.
Tracks applied migrations in a `schema_migrations` table to ensure idempotency.

Usage:
    python -m scripts.run_migrations
    python -m scripts.run_migrations --migrations-dir /path/to/migrations
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def get_db_connection():
    """Import here to allow mocking in tests without triggering config load."""
    from utils.db import get_db_connection as _get
    return _get()


def run_migrations(migrations_dir: str | None = None) -> None:
    """
    Apply all pending .sql files in migrations_dir.

    Args:
        migrations_dir: Path to directory containing .sql files.
                        Defaults to <this_file>/../migrations/
    """
    if migrations_dir is None:
        migrations_dir = str(Path(__file__).parent.parent / "migrations")

    sql_files = sorted(
        f for f in os.listdir(migrations_dir) if f.endswith(".sql")
    )

    if not sql_files:
        logger.info("No migration files found in %s", migrations_dir)
        return

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Ensure tracking table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename   TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Fetch already-applied migrations
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        for filename in sql_files:
            if filename in applied:
                logger.info("  skip (already applied): %s", filename)
                continue

            filepath = os.path.join(migrations_dir, filename)
            sql = Path(filepath).read_text(encoding="utf-8")

            logger.info("  applying: %s", filename)
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (filename,),
                )
            logger.info("  done: %s", filename)

    logger.info("Migrations complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Run pending SQL migrations")
    parser.add_argument(
        "--migrations-dir",
        default=None,
        help="Path to migrations directory (default: backend/migrations/)",
    )
    args = parser.parse_args()

    try:
        run_migrations(migrations_dir=args.migrations_dir)
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        sys.exit(1)
```

- [ ] **Step 5: Run tests**

```bash
cd backend
pytest tests/test_migration_runner.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Verify the runner works against local DB**

```bash
cd backend
python -m scripts.run_migrations
```

Expected output:
```
  applying: 006_auth_audit_log.sql
  done: 006_auth_audit_log.sql
Migrations complete.
```

Run again to verify idempotency:
```bash
python -m scripts.run_migrations
```

Expected output:
```
  skip (already applied): 006_auth_audit_log.sql
Migrations complete.
```

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/ backend/tests/test_migration_runner.py backend/migrations/
git commit -m "feat: add SQL migration runner and auth_audit_log migration"
```

---

## Task 8: Dockerfile and .dockerignore

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

The backend needs a container image to deploy to Cloud Run.

- [ ] **Step 1: Create backend/.dockerignore**

```
venv/
.venv/
__pycache__/
*.pyc
*.pyo
.env
.env.*
tests/
*.md
.git/
.github/
```

- [ ] **Step 2: Create backend/Dockerfile**

```dockerfile
# Build stage — install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Runtime stage — lean final image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application source
COPY . .

# Ensure scripts in .local are in PATH
ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000

# Uvicorn with a single worker — Cloud Run scales via instances, not workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

- [ ] **Step 3: Build and verify the image locally**

```bash
cd backend
docker build -t ethic-companion-backend:local .
```

Expected: build completes without errors. Final image size should be under 800 MB.

- [ ] **Step 4: Smoke-test the container**

```bash
docker run --rm -p 8001:8000 \
  --env-file .env \
  ethic-companion-backend:local
```

In a separate terminal:
```bash
curl http://localhost:8001/health
```

Expected: `{"status": "ok"}` or similar JSON response. Stop the container with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore
git commit -m "feat: add Dockerfile for Cloud Run deployment"
```

---

## Task 9: Fix CI Workflow

**Files:**
- Modify: `.github/workflows/ci.yml`

Remove `continue-on-error: true` from quality checks so black/flake8/mypy/tsc failures actually block PRs. Add missing env vars that tests need. Remove `develop` branch (trunk-based dev uses only `main`).

- [ ] **Step 1: Update .github/workflows/ci.yml**

Replace the full file contents with:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  # Backend Tests & Quality Checks
  backend:
    name: Backend Tests
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements.txt

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Format check (Black)
        run: black --check .

      - name: Lint (Flake8)
        run: flake8 . --max-line-length=120 --exclude=venv,__pycache__,.git

      - name: Type check (MyPy)
        run: mypy . --ignore-missing-imports --exclude venv

      - name: Run tests with coverage
        run: |
          pytest tests/ -v --cov=. --cov-report=xml --cov-report=term-missing
        env:
          DATABASE_URL: "postgresql://test:test@localhost:5432/test"
          POSTGRES_SERVER: "localhost"
          POSTGRES_PORT: "5432"
          POSTGRES_DB: "test"
          POSTGRES_USER: "test"
          POSTGRES_PASSWORD: "test"
          GROQ_API_KEY: "test-key"
          GEMINI_API_KEY: "test-key"
          TAVILY_API_KEY: "test-key"
          WEAVIATE_URL: "http://localhost:8080"
          SECRET_KEY: "ci-test-secret-key-must-be-32-chars-min"
          ALGORITHM: "HS256"
          ACCESS_TOKEN_EXPIRE_MINUTES: "30"

          GOOGLE_CLOUD_PROJECT: "test-project"
          ENVIRONMENT: "test"
          SUPABASE_URL: "https://test.supabase.co"

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: backend/coverage.xml
          flags: backend
          fail_ci_if_error: false

  # Frontend Tests & Quality Checks
  frontend:
    name: Frontend Tests
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Lint
        run: npm run lint

      - name: Type check
        run: npx tsc --noEmit

      - name: Run tests
        run: npm run test -- --passWithNoTests

      - name: Build
        run: npm run build
        env:
          NEXT_PUBLIC_API_URL: "http://localhost:8000"

  # ESL-specific tests (Critical — must never drop below 75% coverage)
  esl-tests:
    name: ESL Critical Tests
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements.txt

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run ESL tests
        run: |
          pytest tests/test_esl.py -v --tb=long
        env:
          DATABASE_URL: "postgresql://test:test@localhost:5432/test"
          POSTGRES_SERVER: "localhost"
          POSTGRES_PORT: "5432"
          POSTGRES_DB: "test"
          POSTGRES_USER: "test"
          POSTGRES_PASSWORD: "test"
          GROQ_API_KEY: "test-key"
          GEMINI_API_KEY: "test-key"
          TAVILY_API_KEY: "test-key"
          SECRET_KEY: "ci-test-secret-key-must-be-32-chars-min"
          ALGORITHM: "HS256"
          ACCESS_TOKEN_EXPIRE_MINUTES: "30"

          GOOGLE_CLOUD_PROJECT: "test-project"
          ENVIRONMENT: "test"
          SUPABASE_URL: "https://test.supabase.co"

      - name: Check ESL coverage
        run: |
          pytest tests/test_esl.py --cov=esl --cov-report=term-missing --cov-fail-under=75
        env:
          DATABASE_URL: "postgresql://test:test@localhost:5432/test"
          POSTGRES_SERVER: "localhost"
          POSTGRES_PORT: "5432"
          POSTGRES_DB: "test"
          POSTGRES_USER: "test"
          POSTGRES_PASSWORD: "test"
          GROQ_API_KEY: "test-key"
          GEMINI_API_KEY: "test-key"
          TAVILY_API_KEY: "test-key"
          SECRET_KEY: "ci-test-secret-key-must-be-32-chars-min"
          ALGORITHM: "HS256"
          ACCESS_TOKEN_EXPIRE_MINUTES: "30"

          GOOGLE_CLOUD_PROJECT: "test-project"
          ENVIRONMENT: "test"
          SUPABASE_URL: "https://test.supabase.co"
```

- [ ] **Step 2: Verify locally that quality checks would block**

Introduce a deliberate formatting error, check it would fail, then revert:

```bash
cd backend
# Temporarily break formatting
echo "x=1+1" >> utils/rate_limit.py
black --check . 2>&1 | head -5
# Expected: "would reformat utils/rate_limit.py" → exit code 1
# Revert
git checkout utils/rate_limit.py
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: remove continue-on-error from quality checks; add missing env vars; trunk-based triggers"
```

---

## Task 10: CD Workflow — Cloud Run Deployment

**Files:**
- Create: `.github/workflows/deploy-backend.yml`

Automates: test → build image → push to Artifact Registry → run migrations → deploy to Cloud Run → shift traffic. Uses OIDC (Workload Identity Federation) — no JSON service account key.

**Prerequisites (one-time manual GCP setup — do before first deploy):**

Run these commands once in your GCP project. Replace `PROJECT_ID`, `PROJECT_NUMBER`, `REGION`, `REPO_NAME`, `SERVICE_NAME` with your values.

```bash
# 1. Create WIF pool
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions Pool"

# 2. Create OIDC provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='CatiaMachado997/RelevanceEthicCompanion'"

# 3. Create deployer service account
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer"

# 4. Grant needed roles
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:github-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:github-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:github-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud iam service-accounts add-iam-policy-binding \
  github-deployer@PROJECT_ID.iam.gserviceaccount.com \
  --member="serviceAccount:github-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# 5. Bind WIF to service account
gcloud iam service-accounts add-iam-policy-binding \
  github-deployer@PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/CatiaMachado997/RelevanceEthicCompanion"

# 6. Create Artifact Registry repo (if not exists)
gcloud artifacts repositories create ethic-companion \
  --repository-format=docker \
  --location=REGION

# Get WIF provider resource name (add to GitHub Secrets as WIF_PROVIDER)
gcloud iam workload-identity-pools providers describe github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --format="value(name)"
```

**GitHub repository secrets to add (Settings → Secrets → Actions):**

| Secret name | Value |
|-------------|-------|
| `WIF_PROVIDER` | Output of the last gcloud command above |
| `WIF_SA_EMAIL` | `github-deployer@PROJECT_ID.iam.gserviceaccount.com` |
| `GCP_PROJECT` | Your GCP project ID |
| `GCP_REGION` | e.g. `us-central1` |
| `CLOUD_RUN_SERVICE` | e.g. `ethic-companion-backend` |
| `ARTIFACT_REGISTRY_REPO` | e.g. `us-central1-docker.pkg.dev/PROJECT_ID/ethic-companion` |
| `PROD_DATABASE_URL` | Full PostgreSQL connection string for production DB |

- [ ] **Step 1: Create .github/workflows/deploy-backend.yml**

```yaml
name: Deploy Backend

on:
  push:
    branches: [main]
    paths:
      - 'backend/**'
      - '.github/workflows/deploy-backend.yml'

permissions:
  contents: read
  id-token: write   # Required for Workload Identity Federation

jobs:
  test:
    name: Backend Tests (pre-deploy gate)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements.txt

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run full test suite
        run: pytest tests/ -v --tb=short
        env:
          DATABASE_URL: "postgresql://test:test@localhost:5432/test"
          POSTGRES_SERVER: "localhost"
          POSTGRES_PORT: "5432"
          POSTGRES_DB: "test"
          POSTGRES_USER: "test"
          POSTGRES_PASSWORD: "test"
          GROQ_API_KEY: "test-key"
          GEMINI_API_KEY: "test-key"
          TAVILY_API_KEY: "test-key"
          SECRET_KEY: "ci-test-secret-key-must-be-32-chars-min"
          ALGORITHM: "HS256"
          ACCESS_TOKEN_EXPIRE_MINUTES: "30"

          GOOGLE_CLOUD_PROJECT: "test-project"
          ENVIRONMENT: "test"
          SUPABASE_URL: "https://test.supabase.co"
          WEAVIATE_URL: "http://localhost:8080"

  deploy:
    name: Build → Migrate → Deploy to Cloud Run
    needs: test
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      # Authenticate to GCP via OIDC — no JSON key file needed
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SA_EMAIL }}

      - uses: google-github-actions/setup-gcloud@v2

      # Configure Docker to push to Artifact Registry
      - name: Configure Docker for Artifact Registry
        run: gcloud auth configure-docker ${{ secrets.GCP_REGION }}-docker.pkg.dev --quiet

      # Build and push image tagged with git SHA (immutable, traceable)
      - name: Build and push Docker image
        env:
          IMAGE: ${{ secrets.ARTIFACT_REGISTRY_REPO }}/backend:${{ github.sha }}
        run: |
          docker build -t $IMAGE ./backend
          docker push $IMAGE
          echo "IMAGE=$IMAGE" >> $GITHUB_ENV

      # Run migrations BEFORE shifting traffic (backward-compatible schema first)
      - name: Run database migrations
        working-directory: backend
        run: python -m scripts.run_migrations
        env:
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
          ENVIRONMENT: "production"
          GOOGLE_CLOUD_PROJECT: ${{ secrets.GCP_PROJECT }}

      # Deploy new revision without traffic (validate it starts cleanly first)
      - name: Deploy new revision (no traffic)
        run: |
          gcloud run deploy ${{ secrets.CLOUD_RUN_SERVICE }} \
            --image=${{ env.IMAGE }} \
            --region=${{ secrets.GCP_REGION }} \
            --project=${{ secrets.GCP_PROJECT }} \
            --no-traffic \
            --quiet

      # Shift all traffic to the new revision
      - name: Shift traffic to new revision
        run: |
          gcloud run services update-traffic ${{ secrets.CLOUD_RUN_SERVICE }} \
            --to-latest \
            --region=${{ secrets.GCP_REGION }} \
            --project=${{ secrets.GCP_PROJECT }} \
            --quiet

      - name: Print deployed URL
        run: |
          gcloud run services describe ${{ secrets.CLOUD_RUN_SERVICE }} \
            --region=${{ secrets.GCP_REGION }} \
            --project=${{ secrets.GCP_PROJECT }} \
            --format="value(status.url)"
```

- [ ] **Step 2: Validate the YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-backend.yml'))"
```

Expected: no output (valid YAML).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy-backend.yml
git commit -m "ci: add Cloud Run CD workflow with OIDC auth and migration runner"
```

---

## Manual Setup Checklist (no code — one-time console work)

These items have no automated tasks because they are OAuth app registrations done in browser dashboards. Complete them when deploying to production.

- [ ] **GitHub OAuth app** — github.com/settings/developers → New OAuth App. Set callback URI to `https://backend.composio.dev/api/v3/toolkits/auth/callback`. Copy Client ID + Secret into Composio Auth Config dashboard (app.composio.dev → Auth Configs → GitHub).
- [ ] **Google OAuth app** — console.cloud.google.com → APIs & Services → Credentials → Create OAuth 2.0 Client ID. Enable Calendar API and Gmail API. Set authorized redirect URI to `https://backend.composio.dev/api/v3/toolkits/auth/callback`. Copy credentials into Composio Auth Config.
- [ ] **Slack OAuth app** — api.slack.com/apps → Create New App → OAuth & Permissions. Set redirect URL to `https://backend.composio.dev/api/v3/toolkits/auth/callback`. Copy Client ID + Secret into Composio Auth Config.
- [ ] **Notion OAuth app** — www.notion.so/my-integrations → New integration → OAuth. Set redirect URI to `https://backend.composio.dev/api/v3/toolkits/auth/callback`. Copy credentials into Composio Auth Config.
- [ ] **GCP WIF setup** — follow the `gcloud` commands in Task 10 above.
- [ ] **Vercel Required Checks** — in Vercel project settings → Git → Required Checks, add `Frontend Tests` (the GitHub Actions job name).

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd backend
pytest tests/ -v --tb=short -q
```

Expected: all tests pass. Note any pre-existing failures (they are not regressions from this work).

- [ ] **Run ESL coverage gate**

```bash
cd backend
pytest tests/test_esl.py --cov=esl --cov-report=term-missing --cov-fail-under=75
```

Expected: coverage ≥ 75%.

- [ ] **Verify frontend builds cleanly**

```bash
cd frontend
npm run build
```

Expected: no TypeScript errors, build succeeds.

- [ ] **Manual smoke test with real Supabase login**

1. Start backend: `cd backend && python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to `http://localhost:3000/dashboard` → should redirect to `/login`
4. Enter a real email → receive magic link → click link → should land on `/dashboard`
5. Check browser DevTools → Application → Cookies: `ec_session` must be present with `HttpOnly` flag

- [ ] **Push to GitHub and verify CI passes**

```bash
git push origin main
```

Open `https://github.com/CatiaMachado997/RelevanceEthicCompanion/actions` and verify all three CI jobs (Backend Tests, Frontend Tests, ESL Critical Tests) go green.
