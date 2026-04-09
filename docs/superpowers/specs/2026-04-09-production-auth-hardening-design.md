# Production Auth Hardening Design

**Date:** 2026-04-09
**Status:** Approved
**Scope:** Full production-grade authentication, secrets management, rate limiting, and audit logging

---

## Goal

Enable real per-user data isolation and harden all security surfaces so the app is safe to open to beta users. Today auth is intentionally disabled for local dev; this spec describes every change needed to flip it on correctly and keep it on in production.

---

## Section 1 — Auth Stack Fix & Enforcement

### Problem

Three separate dev bypasses all disable auth at once:

| Layer | Bypass | Fix |
|-------|--------|-----|
| Backend JWT decode | `algorithms=["RS256"]` but Supabase issues ES256 tokens → every token fails when enforcement is on | Change to `algorithms=["ES256"]` in `supabase_auth.py` |
| Backend enforcement | `AUTH_ENFORCEMENT_ENABLED=False` → `get_current_user_id` returns `DEV_USER_ID` for all requests | Set `AUTH_ENFORCEMENT_ENABLED=True` in `.env` / Secret Manager |
| Frontend middleware | `NEXT_PUBLIC_ENVIRONMENT=development` → middleware skips cookie check | Remove env var; middleware always enforces |
| Frontend dashboard layout | `useAuth()` hook skips guard in dev | Same fix — remove env var check |
| Cookie name mismatch | `middleware.ts` checks `sb-*-auth-token`; our session endpoint issues `ec_session` | Update middleware to check `ec_session` |

### Fix

1. **`backend/utils/supabase_auth.py`** — change `algorithms=["RS256"]` → `algorithms=["ES256"]`
2. **`backend/.env`** (and Secret Manager in prod) — `AUTH_ENFORCEMENT_ENABLED=True`
3. **`frontend/.env.local`** — remove `NEXT_PUBLIC_ENVIRONMENT=development`
4. **`frontend/middleware.ts`** — check `ec_session` cookie instead of `sb-*-auth-token`

### Data Isolation (already correct, just needs auth on)

Every DB query already filters by `user_id` (extracted from JWT). Composio uses `entity_id=user_id` so tokens are per-user at Composio's infrastructure level. Weaviate queries filter by `user_id` metadata. Once auth is enforced, no cross-user data access is possible.

---

## Section 2 — Secrets Management

### Problem

All secrets live in `.env` on disk. In production (Cloud Run) this means secrets are either hardcoded in the container image or passed as plain env vars — both are unacceptable.

### Approach

GCP Secret Manager as the single source of truth for all sensitive values in production. Local dev continues to use `.env` via pydantic-settings (no change to dev workflow).

```
ENVIRONMENT=production  → load secrets from GCP Secret Manager at startup
ENVIRONMENT=development → use .env as today (pydantic-settings)
```

### Implementation

- Add `google-cloud-secret-manager` to `requirements.txt`
- Add `load_secrets_from_gcp()` function called in `config.py` before `Settings()` instantiation, only when `ENVIRONMENT=production`
- Secrets to migrate to GCP Secret Manager:
  - `SECRET_KEY`
  - `ENCRYPTION_KEY`
  - `GEMINI_API_KEY`
  - `TAVILY_API_KEY`
  - `COMPOSIO_API_KEY`
  - `GROQ_API_KEY`
  - `GOOGLE_OAUTH_CLIENT_SECRET`
  - `SLACK_CLIENT_SECRET`
  - `GITHUB_CLIENT_SECRET`
  - `NOTION_CLIENT_SECRET`
- Postgres password: managed separately via Cloud SQL connector (stays in Cloud Run env vars)
- CORS origins: stored in Secret Manager as `ALLOWED_ORIGINS` (comma-separated)

### GCP IAM

Cloud Run service account must have `roles/secretmanager.secretAccessor` on all secrets. No other IAM changes needed.

---

## Section 3 — Secure Cookies + CORS

### Cookies

`POST /api/auth/session` (`backend/routes/auth.py`) currently sets:
```python
response.set_cookie("ec_session", token, httponly=True)
```

In production, add:
```python
secure=settings.COOKIE_SECURE,    # True in prod, False in dev
samesite="strict",
```

Add `COOKIE_SECURE: bool = False` to `config.py` (set `True` in production env).

### CORS

`CORS_ORIGINS` currently defaults to `["http://localhost:3000"]`. In production this must be the real frontend domain only. Value comes from Secret Manager as `ALLOWED_ORIGINS`. The `config.py` `CORS_ORIGINS` field already accepts a list — no structural change needed, just correct values per environment.

---

## Section 4 — Rate Limiting

### Library

`slowapi` — the standard FastAPI rate limiter, wraps `limits` library. In-memory store is sufficient for a single Cloud Run instance (no Redis needed for beta).

### Limits

| Endpoint group | Limit | Key |
|----------------|-------|-----|
| `POST /api/auth/session` | 10 req / min | IP address |
| `GET /api/auth/me` | 30 req / min | IP address |
| `POST /api/tools/*/connect` | 20 req / min | user_id (JWT) |
| `POST /api/tools/composio/connect` | 20 req / min | user_id (JWT) |
| All other `/api/*` routes | 100 req / min | user_id (JWT), fall back to IP |

### Implementation

- Add `slowapi` + `slowapi[async]` to `requirements.txt`
- Create `backend/utils/rate_limit.py`: configure `Limiter`, `_rate_limit_exceeded_handler`
- Register limiter and exception handler in `main.py`
- Decorate individual route functions with `@limiter.limit("10/minute")`

---

## Section 5 — Auth Audit Logging

### Schema

New table alongside `esl_audit_log`:

```sql
CREATE TABLE auth_audit_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID,                    -- NULL for pre-auth events (invalid token, rate limit)
    event        TEXT NOT NULL,           -- see Event Types below
    ip_address   TEXT,
    user_agent   TEXT,
    detail       JSONB,                   -- optional extra context (e.g. error message)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_audit_user_id ON auth_audit_log (user_id);
CREATE INDEX idx_auth_audit_created_at ON auth_audit_log (created_at DESC);
```

### Event Types

| Event | When |
|-------|------|
| `login_success` | `POST /api/auth/session` succeeds |
| `logout` | `DELETE /api/auth/session` |
| `token_invalid` | JWT decode fails in `get_current_user_id` |
| `token_expired` | JWT expired specifically |
| `rate_limited` | Rate limit exceeded on any auth endpoint |
| `session_exchanged` | Supabase code → session cookie exchange |

### Implementation

- `backend/utils/auth_audit.py`: async `log_auth_event(event, user_id=None, request=None, detail=None)`
- Called from `supabase_auth.py` on validation failures and from `routes/auth.py` on login/logout
- Fire-and-forget (`asyncio.create_task`) — never blocks the request path
- Migration: `backend/migrations/006_auth_audit_log.sql`

---

## Section 6 — OAuth App Registration + Composio Auth Config

### Why register our own OAuth apps

Composio's default setup uses Composio's own OAuth app credentials. This means the OAuth consent screen says "Composio wants access to…" instead of "Ethic Companion wants access to…". For beta users, this is confusing and reduces trust.

By registering our own OAuth apps and feeding the credentials into Composio's Auth Config, the consent screen correctly identifies our app.

### Per-provider setup

| Provider | Console URL | Scopes needed | Redirect URI |
|----------|-------------|---------------|--------------|
| **GitHub** | github.com/settings/developers | `repo`, `read:user` | `https://backend.composio.dev/api/v3/toolkits/auth/callback` |
| **Google** (Calendar + Gmail) | console.cloud.google.com → APIs & Services → Credentials | `calendar.events`, `gmail.send`, `gmail.readonly` | `https://backend.composio.dev/api/v3/toolkits/auth/callback` |
| **Slack** | api.slack.com/apps | `channels:read`, `chat:write`, `files:write` | `https://backend.composio.dev/api/v3/toolkits/auth/callback` |
| **Notion** | www.notion.so/my-integrations | default (read/write pages) | `https://backend.composio.dev/api/v3/toolkits/auth/callback` |

### Composio Auth Config

For each provider, in the Composio dashboard (app.composio.dev → Auth Configs):
1. Select the app (GitHub, Google, Slack, Notion)
2. Paste our Client ID + Client Secret
3. Save → Composio uses our credentials for all OAuth flows

The resulting Auth Config ID is stored in Secret Manager (not needed in code — Composio picks it up automatically by `entity_id`).

### Secrets to store

```
GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET
GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET  (already in .env, move to Secret Manager)
SLACK_CLIENT_ID / SLACK_CLIENT_SECRET                (already in .env, move to Secret Manager)
NOTION_CLIENT_ID / NOTION_CLIENT_SECRET
```

---

## Testing Plan

| Test | How |
|------|-----|
| ES256 JWT validates correctly | Unit test: generate ES256 token with test key, assert `get_current_user_id` returns correct UUID |
| RS256 token rejected | Unit test: generate RS256 token, assert `AuthError` raised |
| Dev bypass completely removed | Integration test: with `AUTH_ENFORCEMENT_ENABLED=True`, unauthenticated request to write route returns 401 |
| Rate limit triggers | Integration test: send 11 auth requests in a row, assert 12th returns 429 |
| Auth audit events written | Integration test: login → assert row in `auth_audit_log` with `event='login_success'` |
| Secure cookie set in prod mode | Unit test: with `COOKIE_SECURE=True`, assert `Set-Cookie` header has `Secure; SameSite=Strict` |
| Cross-user isolation | Integration test: user A logs in, user B logs in, assert user A cannot read user B's data |

---

## Files Created / Modified

| File | Change |
|------|--------|
| `backend/utils/supabase_auth.py` | `algorithms=["ES256"]`, log auth events |
| `backend/utils/auth_audit.py` | New — auth event logger |
| `backend/utils/rate_limit.py` | New — slowapi limiter config |
| `backend/routes/auth.py` | Add `COOKIE_SECURE`, `SameSite=Strict`, log login/logout |
| `backend/config.py` | Add `COOKIE_SECURE: bool`, `load_secrets_from_gcp()` |
| `backend/main.py` | Register rate limiter + exception handler |
| `backend/requirements.txt` | Add `slowapi`, `google-cloud-secret-manager` |
| `backend/migrations/006_auth_audit_log.sql` | New — auth_audit_log table |
| `frontend/middleware.ts` | Check `ec_session` cookie, remove dev bypass |
| `frontend/app/dashboard/layout.tsx` | Remove `NEXT_PUBLIC_ENVIRONMENT` guard |
| `frontend/.env.local` | Remove `NEXT_PUBLIC_ENVIRONMENT=development` |
| `backend/.env` | `AUTH_ENFORCEMENT_ENABLED=True`, `COOKIE_SECURE=False` (dev) |
| GCP Secret Manager | All secrets migrated (manual, one-time) |
| Composio Auth Config | OAuth apps registered per provider (manual, one-time) |

---

## Non-Goals (explicitly out of scope)

- MFA / two-factor auth (post-beta)
- Session revocation / token blacklist (post-beta)
- GDPR data deletion flows (post-beta)
- Redis-backed rate limiting (not needed until multi-instance)
- Penetration testing (post-beta)
