# Auth/Authz Phase 1 Test Plan

## Unit
- `get_current_user()`:
  - missing auth header -> 401
  - malformed bearer -> 401
  - invalid token -> 401
  - valid token claims -> user principal
- OAuth state helpers:
  - valid state accepted
  - bad signature rejected
  - expired state rejected
  - replayed nonce rejected

## Integration
- Protected write routes:
  - no token -> 401
  - invalid token -> 401
  - valid token -> route handler proceeds
- `GET /api/auth/me`:
  - valid token -> returns principal

## Frontend
- API client adds `Authorization: Bearer <token>` when token is available.
- 401 responses trigger unauthorized callback.

## Acceptance
- No write route in scope depends on `MOCK_USER_ID`.
- All added tests pass in CI.
