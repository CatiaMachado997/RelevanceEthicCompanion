#!/usr/bin/env bash

# Resolve one existing backend virtualenv without creating or copying environments.
resolve_backend_python() {
    local backend_dir="$1"
    local candidate="${DEEPEVAL_PYTHON:-$backend_dir/venv/bin/python}"
    local worktree_root

    if [ -x "$candidate" ]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    while IFS= read -r worktree_root; do
        candidate="$worktree_root/backend/venv/bin/python"
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done <<EOF
$(git -C "$backend_dir" worktree list --porcelain | sed -n 's/^worktree //p')
EOF

    printf '%s\n' \
        "No backend virtualenv found. Set DEEPEVAL_PYTHON to an existing Python executable." \
        >&2
    return 1
}
