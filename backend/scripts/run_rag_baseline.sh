#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
RESULT_DIR="$BACKEND_DIR/tests/evals/results"

mkdir -p "$RESULT_DIR"
cd "$BACKEND_DIR"

export RUN_INTEGRATION_TESTS=1
export DEEPEVAL_TRACING_ENABLED=1
export DEEPEVAL_HOSTED=1
export GROQ_EVAL_MODEL="${GROQ_EVAL_MODEL:-groq/compound}"
export RAG_EVAL_LIMIT="${2:-${RAG_EVAL_LIMIT:-20}}"
export RAG_EVAL_DELAY_SECONDS="${RAG_EVAL_DELAY_SECONDS:-0}"
export RAG_HYBRID_ALPHA="${RAG_HYBRID_ALPHA:-0.5}"
export RAG_EVAL_TOP_K="${RAG_EVAL_TOP_K:-3}"
export RAG_CANDIDATE_FLOOR="${RAG_CANDIDATE_FLOOR:-20}"
export RAG_QUERY_EXPANSION="${RAG_QUERY_EXPANSION:-0}"
export RAG_METADATA_RERANK_WEIGHT="${RAG_METADATA_RERANK_WEIGHT:-0}"
RAG_EVAL_RUN_ID="${1:-${RAG_EVAL_RUN_ID:-rag-baseline}}"

DEEPEVAL_COMMAND=(
  "$SCRIPT_DIR/deepeval_groq.sh" test run
  tests/evals/test_rag_retrieval_baseline.py
  --identifier "$RAG_EVAL_RUN_ID"
  --display all
)
if [[ "${RAG_EVAL_OFFICIAL:-0}" == "1" ]]; then
  DEEPEVAL_COMMAND+=(--official)
fi

set +e
"${DEEPEVAL_COMMAND[@]}" 2>&1 | tee "$RESULT_DIR/latest.log"
TEST_STATUS=${PIPESTATUS[0]}
set -e

"$BACKEND_DIR/venv/bin/python" "$SCRIPT_DIR/summarize_rag_run.py" \
  "$BACKEND_DIR/.deepeval/.latest_run_full.json" \
  "$RESULT_DIR/comparison.json" \
  --run-id "$RAG_EVAL_RUN_ID" \
  --alpha "$RAG_HYBRID_ALPHA" \
  --top-k "$RAG_EVAL_TOP_K" \
  --candidate-floor "$RAG_CANDIDATE_FLOOR" \
  --query-expansion "$RAG_QUERY_EXPANSION" \
  --metadata-weight "$RAG_METADATA_RERANK_WEIGHT"

exit "$TEST_STATUS"
