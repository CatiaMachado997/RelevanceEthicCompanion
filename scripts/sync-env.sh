#!/usr/bin/env bash
# Symlink this worktree's env files to the primary repo's, so OAuth creds,
# DB URLs, and API keys don't go missing whenever a worktree is created.
#
# Usage:   scripts/sync-env.sh [--force]
# Run from anywhere inside any worktree.
#
# What it does:
#   - locates the primary repo (the one whose .git is a real directory, not a file)
#   - for each (backend/.env, frontend/.env.local), if the source exists in the
#     primary repo, replace this worktree's copy with a symlink to it
#   - existing real files are backed up to <name>.bak.<timestamp> first
#   - if the worktree already has a correct symlink, no-op

set -euo pipefail

force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

# Resolve the primary repo (the one containing the actual .git directory).
# git rev-parse --git-common-dir returns the shared .git path; its parent is
# the primary worktree.
common_git=$(git rev-parse --git-common-dir)
if [[ "$common_git" != /* ]]; then
  common_git="$(pwd)/$common_git"
fi
primary_repo=$(cd "$(dirname "$common_git")" && pwd)

# Resolve the current worktree root.
this_repo=$(git rev-parse --show-toplevel)

if [[ "$primary_repo" == "$this_repo" ]]; then
  echo "Already in primary repo ($primary_repo) — nothing to symlink."
  exit 0
fi

echo "Primary repo:    $primary_repo"
echo "This worktree:   $this_repo"
echo

link_one() {
  local rel="$1"
  local src="$primary_repo/$rel"
  local dst="$this_repo/$rel"

  if [[ ! -e "$src" ]]; then
    echo "skip  $rel  (not present in primary repo)"
    return 0
  fi

  if [[ -L "$dst" ]]; then
    local target
    target=$(readlink "$dst")
    if [[ "$target" == "$src" ]]; then
      echo "ok    $rel  (already linked)"
      return 0
    fi
    echo "relink $rel  (was → $target)"
    rm "$dst"
  elif [[ -e "$dst" ]]; then
    if [[ "$force" -ne 1 ]]; then
      local bak="$dst.bak.$(date +%s)"
      mv "$dst" "$bak"
      echo "backup $rel → $(basename "$bak")"
    else
      rm -f "$dst"
    fi
  fi

  ln -s "$src" "$dst"
  echo "link  $rel  →  $src"
}

mkdir -p "$this_repo/backend" "$this_repo/frontend"
link_one backend/.env
link_one frontend/.env.local

echo
echo "Done. Restart any running dev servers so they pick up the env."
