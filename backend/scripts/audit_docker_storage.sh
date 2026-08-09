#!/usr/bin/env bash
set -euo pipefail

readonly POSTGRES_VOLUME="backend_postgres_data"
readonly WEAVIATE_VOLUME="backend_weaviate_data"
readonly EXPECTED_VOLUMES=("$POSTGRES_VOLUME" "$WEAVIATE_VOLUME")

volume_exists() {
  docker volume inspect "$1" >/dev/null 2>&1
}

echo "Canonical Ethic Companion volumes:"
for volume in "${EXPECTED_VOLUMES[@]}"; do
  if volume_exists "$volume"; then
    mountpoint=$(docker volume inspect --format '{{.Mountpoint}}' "$volume")
    echo "  OK  $volume ($mountpoint)"
  else
    echo "  NEW $volume (Compose will create it on first startup)"
  fi
done

echo
echo "Containers using the canonical volumes:"
for volume in "${EXPECTED_VOLUMES[@]}"; do
  containers=$(docker ps -a --filter "volume=$volume" --format '{{.Names}}' | paste -sd ',' -)
  echo "  $volume: ${containers:-none}"
done

candidates=$(
  docker volume ls --format '{{.Name}}' |
    grep -Ei '(ethic|relevance|backend).*(postgres|weaviate)|(postgres|weaviate).*(ethic|relevance|backend)' |
    grep -Fvx "$POSTGRES_VOLUME" |
    grep -Fvx "$WEAVIATE_VOLUME" || true
)

echo
if [[ -z "$candidates" ]]; then
  echo "No non-canonical named Postgres/Weaviate volumes found."
else
  echo "Non-canonical named volumes found (not modified):"
  while IFS= read -r volume; do
    containers=$(docker ps -a --filter "volume=$volume" --format '{{.Names}}' | paste -sd ',' -)
    echo "  WARN $volume (containers: ${containers:-none})"
  done <<<"$candidates"
  echo
  echo "Review these explicitly before removal. This audit never copies or deletes data."
fi
