#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

# Ollama model defaults with no dotenv or global DeepEval provider state.
# Set DEEPEVAL_HOSTED=1 plus CONFIDENT_API_KEY to upload run comparisons.
export DEEPEVAL_DISABLE_DOTENV=1
export DEEPEVAL_UPDATE_WARNING_OPT_IN=0
if [ "${DEEPEVAL_HOSTED:-0}" = "1" ]; then
    export DEEPEVAL_TELEMETRY_OPT_OUT=0
else
    export DEEPEVAL_TELEMETRY_OPT_OUT=1
    export ERROR_REPORTING=0
fi
export LOCAL_MODEL_API_KEY=ollama
export OLLAMA_MODEL_NAME=${OLLAMA_MODEL_NAME:-llama3.2:latest}
export LOCAL_MODEL_BASE_URL=${LOCAL_MODEL_BASE_URL:-http://127.0.0.1:11434}
export USE_LOCAL_EMBEDDINGS=1
export LOCAL_EMBEDDING_API_KEY=ollama
export LOCAL_EMBEDDING_MODEL_NAME=${LOCAL_EMBEDDING_MODEL_NAME:-bge-m3:latest}
export LOCAL_EMBEDDING_BASE_URL=${LOCAL_EMBEDDING_BASE_URL:-http://127.0.0.1:11434}
export DEEPEVAL_TRACING_ENABLED=1

exec "$BACKEND_DIR/venv/bin/python" "$SCRIPT_DIR/deepeval_cli_local.py" "$@"
