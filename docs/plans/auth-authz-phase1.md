# Auth/Authz Phase 1 Implementation Plan

## Increment 0
- Add auth utility tests (missing/invalid/valid token handling).
- Add representative route auth tests for chat and data sources.
- Add frontend API client tests for bearer injection + 401.

## Increment 1
- Implement Supabase JWT validation utility.
- Add config flags and Supabase auth settings.

## Increment 2
- Migrate write endpoints:
  - values: POST/PUT/DELETE/activate
  - goals: POST/PUT/complete/DELETE
  - chat: POST `/`, POST `/proactive`, DELETE `/history`
  - data sources: oauth authorize/callback, sync, disconnect

## Increment 3
- Add `GET /api/auth/me`.

## Increment 4
- Add frontend `configureApiAuth()` and default token provider.
- Add unauthorized callback for session handling.

## Rollout
1. Keep `AUTH_ENFORCEMENT_ENABLED=false` locally during migration.
2. Enable in staging and validate write routes.
3. Enable in production for write routes.
