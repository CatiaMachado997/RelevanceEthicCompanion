#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

# DeepEval loads the ignored backend/.env.local for OPENAI_API_KEY.
export DEEPEVAL_TELEMETRY_OPT_OUT=1
export DEEPEVAL_UPDATE_WARNING_OPT_IN=0
export ERROR_REPORTING=0
export USE_OPENAI_MODEL=1
export OPENAI_MODEL_NAME=${OPENAI_MODEL_NAME:-gpt-4.1-mini}

cd "$BACKEND_DIR"
exec "$BACKEND_DIR/venv/bin/deepeval" "$@"
