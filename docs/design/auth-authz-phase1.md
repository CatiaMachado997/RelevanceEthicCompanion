# Auth/Authz Phase 1 Design

## Problem
Protected write routes still rely on hardcoded `MOCK_USER_ID`, which allows unauthorized mutation risk and prevents production-grade user isolation.

## Goals
- Enforce Supabase JWT auth on write endpoints in phase scope.
- Derive `user_id` from verified token claims.
- Keep rollout safe with feature-flagged fallback in local development.

## Non-Goals
- Full backend auth lifecycle endpoints (`signup/login/logout`).
- Cookie session transport.
- Read-route enforcement in this phase.

## Design
1. Add `backend/utils/supabase_auth.py` with:
   - Bearer token extraction
   - Supabase JWKS verification
   - `get_current_user()` / `get_current_user_id()` dependencies
2. Add signed OAuth state utility `backend/utils/oauth_state.py`:
   - Signed state payload with expiry + nonce
   - Callback validation and nonce replay protection
3. Migrate write route dependencies to `Depends(get_current_user_id)`.
4. Add `GET /api/auth/me` for token sanity checks.
5. Add frontend API auth configuration for bearer token injection and 401 handling.

## Config
- `AUTH_ENFORCEMENT_ENABLED`
- `AUTH_ENFORCE_WRITE_ROUTES`
- `SUPABASE_URL`
- `SUPABASE_JWT_AUDIENCE`

## Risks
- Misconfigured issuer/audience can cause broad 401s.
- In-memory OAuth nonce store is single-process and non-distributed.

## Mitigations
- Feature flag fallback in local development.
- Explicit error telemetry and staging validation before production enablement.
