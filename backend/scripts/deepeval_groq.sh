#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
. "$SCRIPT_DIR/python_runtime.sh"
PYTHON_BIN=$(resolve_backend_python "$BACKEND_DIR")

cd "$BACKEND_DIR"
exec "$PYTHON_BIN" "$SCRIPT_DIR/deepeval_cli_groq.py" "$@"
