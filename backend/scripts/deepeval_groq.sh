#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

cd "$BACKEND_DIR"
exec "$BACKEND_DIR/venv/bin/python" "$SCRIPT_DIR/deepeval_cli_groq.py" "$@"
