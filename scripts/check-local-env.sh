#!/usr/bin/env bash
set -euo pipefail

read_value() {
  local file="$1" key="$2"
  sed -nE "s/^${key}=(.*)$/\1/p" "$file" | tail -1
}

require_value() {
  local file="$1" key="$2" expected="$3"
  local actual
  actual="$(read_value "$file" "$key")"
  if [[ "$actual" != "$expected" ]]; then
    printf 'ERROR: %s in %s must be %s for local development.\n' "$key" "$file" "$expected" >&2
    exit 1
  fi
}

require_value backend/.env.local ENVIRONMENT development
require_value backend/.env.local POSTGRES_SERVER localhost
require_value backend/.env.local WEAVIATE_URL http://localhost:8080
require_value backend/.env.local FRONTEND_URL http://localhost:3000
require_value frontend/.env.local NEXT_PUBLIC_API_URL http://localhost:8000

local_supabase="$(read_value backend/.env.local SUPABASE_URL)"
frontend_supabase="$(read_value frontend/.env.local NEXT_PUBLIC_SUPABASE_URL)"

if [[ -z "$local_supabase" || "$local_supabase" != "$frontend_supabase" ]]; then
  echo 'ERROR: frontend and backend must use the same Supabase development project.' >&2
  exit 1
fi

if [[ -n "${PRODUCTION_SUPABASE_URL:-}" && "$local_supabase" == "$PRODUCTION_SUPABASE_URL" ]]; then
  echo 'ERROR: local development is configured with the production Supabase project.' >&2
  exit 1
fi

echo 'Local environment boundary check passed.'
