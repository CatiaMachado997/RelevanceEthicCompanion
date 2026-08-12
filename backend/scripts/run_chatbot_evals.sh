#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
RESULT_DIR="$BACKEND_DIR/tests/evals/results"

mkdir -p "$RESULT_DIR"
cd "$BACKEND_DIR"

export RUN_INTEGRATION_TESTS=1
export RUN_CHATBOT_EVALS=1
export DEEPEVAL_TRACING_ENABLED=1
export DEEPEVAL_HOSTED="${DEEPEVAL_HOSTED:-0}"
export DEEPEVAL_METRICS_ASYNC="${DEEPEVAL_METRICS_ASYNC:-0}"
export CHATBOT_EVAL_LIMIT="${CHATBOT_EVAL_LIMIT:-20}"
export CHATBOT_EVAL_MAX_TURNS="${CHATBOT_EVAL_MAX_TURNS:-5}"
export CHATBOT_EVAL_APP_MODEL="${CHATBOT_EVAL_APP_MODEL:-llama-3.3-70b-versatile}"
RUN_ID="${1:-chatbot-baseline}"

"$SCRIPT_DIR/deepeval_groq.sh" test run \
  tests/evals/test_chatbot_answer_quality.py \
  tests/evals/test_chatbot_multiturn_quality.py \
  --identifier "$RUN_ID" \
  --display all 2>&1 | tee "$RESULT_DIR/chatbot-latest.log"
