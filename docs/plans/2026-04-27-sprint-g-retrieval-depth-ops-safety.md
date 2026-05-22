# Sprint G — Retrieval depth + ops safety net

Date: 2026-04-27
Status: Plan
Predecessors: Sprints A–F ✅

## Why this sprint exists

Sprint F proved end-to-end retrieval works on real Gmail content (the M-KOPA email
test). Two follow-ups now make sense:

**Quality.** Hybrid search returns reasonable candidates but ranking is fusion-only;
top-K is whatever Weaviate scores fastest. A reranker pass rescores by query-document
relevance and cuts to a tight top-5 for the LLM context. Plus uploaded PDFs/DOCX are
currently second-class — only plain text is chunked, so binary uploads are dead weight.

**Ops safety.** Today's debug session cost hours because migrations 011–015 hadn't been
applied to the running Postgres. The migration runner exists but never fires on boot,
so a fresh checkout or a worktree drift puts the schema and the code out of sync silently.
Auto-run on startup eliminates the failure mode.

This sprint does **not** add a new pillar. It deepens retrieval and removes a recurring
foot-gun.

## Goals

1. **Backend boots schema-safe.** On startup, pending migrations apply automatically. No
   manual step.
2. **Uploads aren't second-class.** PDF and DOCX uploads chunk and embed alongside text.
3. **Reranker tightens top-K.** Hybrid search returns top-20; Jina rerank scores them;
   top-5 reach the LLM. Falls back to raw top-K if API key is missing or call fails.
4. **Retrieval is debuggable.** Transparency tool-call detail shows the full retrieval
   trace: query → hybrid candidates with scores → rerank scores → final cited chunks.

## Architecture decisions

- **Migrations on boot, not a separate command.** Lifespan startup hook calls
  `run_migrations()`. The runner is already idempotent (`schema_migrations` tracking
  table) so re-running is safe. Logs applied count and exits clean if up to date. If
  migration fails, the backend refuses to start — fail loud, fix forward.
- **PDF/DOCX via pluggable extractor.** New `services/document_extractors.py` with
  `extract_text(file_path, mime_type) -> str`. Routes to `pypdf` for PDFs and
  `python-docx` for `.docx`. Falls back to raw text. The existing chunker consumes the
  extracted text — no changes needed downstream.
- **Rerank as a separate service, opt-in.** `services/rerank.py` exposes
  `rerank(query, candidates, top_k=5)`. Calls Jina API. If `JINA_API_KEY` not set or
  the call raises, return candidates unchanged (caller still trims to top_k from raw
  list). `RagRetrievalService.retrieve()` calls it after hybrid search.
- **Why Jina for rerank.** Free tier is 100 RPM / 100K TPM with no monthly cap;
  Cohere's free tier caps at 1000/month and 10 RPM and is non-commercial only. Jina's
  `jina-reranker-v2-base-multilingual` is competitive on RAG benchmarks.
- **Breadcrumbs as JSON in tool_call_events.input/output.** No new persistence. The
  existing telemetry row already stores per-call input and output JSONB; the rerank
  trace fits into output as a structured array. Transparency panel reads and renders.

## Tasks (one commit each)

### 1. Auto-run migrations on backend startup
- `backend/main.py` lifespan: call `run_migrations()` after DB pool is ready, before
  the scheduler starts. Log `f"applied {n} migrations"` or `"schema up to date"`.
- If `run_migrations()` raises, log the error and re-raise — backend refuses to start.
- Keep `python -m scripts.run_migrations` working as a manual escape hatch.
- 1 test: `test_main_startup.py` patches `run_migrations` and asserts it's called in
  the right order.

### 2. PDF/DOCX ingestion
- Add to `backend/requirements.txt`: `pypdf>=4.0`, `python-docx>=1.1`.
- New `backend/services/document_extractors.py`:
  ```python
  def extract_text(file_path: str, mime_type: str | None = None) -> str: ...
  ```
  Routes by extension/mime type. PDF → pypdf. DOCX → python-docx. Plain → file read.
  Unknown → raise or empty string with warning.
- `backend/services/document_processor.py` — replace its current text-only read with
  a call to `extract_text`. The chunker consumes the same string regardless of source.
- Tests: `test_document_extractors.py` — PDF round-trip with a tiny fixture, DOCX
  round-trip, unknown type fallback. Use sample fixtures committed under
  `backend/tests/fixtures/`.

### 3. Jina rerank service + RAG integration
- `.env.example` adds `JINA_API_KEY=` (empty default) and
  `RERANK_MODEL=jina-reranker-v2-base-multilingual`.
- New `backend/services/rerank.py`:
  ```python
  async def rerank(
      query: str,
      candidates: list[dict],     # each has 'snippet' + arbitrary metadata
      *,
      top_k: int = 5,
      api_key: str | None = None,
  ) -> list[dict]: ...
  ```
  Calls `https://api.jina.ai/v1/rerank` with `documents=[c["snippet"] for c in candidates]`.
  Annotates each kept candidate with `rerank_score`. On error / missing key, returns
  `candidates[:top_k]` unchanged with a debug log.
- `backend/services/rag_retrieval.py`:
  - `retrieve()` widens the hybrid-search call to `k=20` (was probably 5).
  - Pass results through `rerank(query, results, top_k=k_requested)` (where `k_requested`
    is the caller-specified k, default 5).
  - The returned chunks now carry both `score` (hybrid) and optional `rerank_score`.
- Tests: `test_rerank.py` — mocked HTTP, asserts the response is sorted by rerank_score
  and trimmed; missing-key path returns `candidates[:top_k]`; error path falls back.
  `test_rag_retrieval.py` extends with a rerank-applied test using the integration test
  pattern from Sprint F Task 2.

### 4. Retrieval breadcrumbs in Transparency
- `services/rag_retrieval.py`: build a `trace` dict alongside results:
  ```json
  {
    "query": "...",
    "candidates": [{"chunk_uuid": "...", "hybrid_score": 0.82, "snippet_preview": "..."}, ...],
    "rerank_applied": true,
    "rerank_top": [{"chunk_uuid": "...", "rerank_score": 0.91}, ...],
    "final": ["chunk_uuid", "..."]
  }
  ```
- `services/tools/search_documents.py` (Sprint A) — return the trace alongside
  results. The tool's `record_tool_call` writes the trace into
  `tool_call_events.output`.
- `frontend/components/transparency/ToolCallsTab.tsx` — when the selected event's
  `tool_name == "search_documents"` and `output.trace` exists, render a "Retrieval
  trace" section in the detail dialog: candidate list with hybrid scores, rerank
  scores (if applied), and which chunks were finally cited.
- 1 backend test asserting the trace is recorded; frontend typecheck.

### 5. Full suite + push + PR update
- `pytest --tb=short -q` ; `cd frontend && npx tsc --noEmit`. Both green.
- Push. Update PR #48 body with a Sprint G section.

## Verification

```bash
cd backend
pytest tests/test_rerank.py tests/test_document_extractors.py tests/test_main_startup.py -v
pytest --tb=short -q

cd ../frontend
npx tsc --noEmit
```

**Manual checklist:**
1. Stop backend. Drop a migration into `backend/migrations/`. Start backend. Watch
   logs — see `applied 1 migration: <filename>`. No manual step.
2. Upload a PDF on `/dashboard/documents`. Wait for indexing. Ask a chat question
   whose answer is in the PDF. Get a citation pointing to the PDF.
3. Without `JINA_API_KEY` set, retrieval still works (raw hybrid). Set the key,
   restart backend, ask the same question — expect tighter, more relevant citations.
4. Open Transparency → click a `search_documents` event → see the retrieval trace
   panel: candidates with scores, rerank scores, which were cited.

## Out of scope

- **Rerank eval harness** with real benchmark queries. Ship the rerank, measure with
  real usage, decide if a harness is needed in a future sprint.
- **Per-project document scoping.** Needs a UI to choose a project context per chat.
  Own micro-sprint.
- **Scheduler alerting on failures.** Logs are still enough.
- **OCR for image-only PDFs.** pypdf returns empty for them; we accept that and warn.
- **Reranking across non-document sources** (calendar events as candidates etc.).
  Right now only `DocumentMemory` content is reranked.

## Open questions deferred to execution

- Exact Jina API request shape for `top_n` parameter — verify on first call. The
  service should pass `top_n` not just trim client-side.
- Where does the Sprint F integration test mock Weaviate? Does it allow the rerank
  layer to be added with one more mock or does it need restructuring? Likely
  one-line mock addition.
- Should the trace be stored on every retrieval, or only when telemetry is enabled?
  Start with always — it's small JSON. Add a config flag if it bloats.
