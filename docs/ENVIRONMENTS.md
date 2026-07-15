# Environment separation

Production and local development must use separate runtime configuration.

## Production

Production configuration belongs in the Vercel and Railway dashboards. Do not
run production from a checked-out `.env.production` file.

- Vercel deploys `frontend/` from `main`.
- Railway deploys `backend/` from `main`.
- Railway uses the production Supabase project and production provider URLs.
- OAuth providers register the HTTPS Railway callback URLs.

## Local development

Local configuration belongs in the ignored files `frontend/.env.local` and
`backend/.env.local`.

- Postgres: `localhost:5432` through Docker.
- Weaviate: `http://localhost:8080` through Docker.
- Backend: `http://localhost:8000`.
- Frontend: `http://localhost:3000`.
- Supabase: a separate development project.
- OAuth providers: separate development apps are preferred; at minimum, add
  the localhost callback URLs to the provider apps.

Run `make check-local-env` before starting the app. For an additional guard,
export the production Supabase URL in your shell; the check then rejects a
local configuration that points at it:

```bash
export PRODUCTION_SUPABASE_URL=https://your-production-project.supabase.co
make dev
```

Register these development redirects:

```text
Supabase: http://localhost:3000/auth/callback
Google Calendar: http://localhost:8000/api/data-sources/oauth/google_calendar/callback
Gmail: http://localhost:8000/api/data-sources/oauth/gmail/callback
Slack: http://localhost:8000/api/data-sources/oauth/slack/callback
Composio: http://localhost:8000/api/tools/composio/callback
```
