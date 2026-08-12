# Ethic Companion knowledge base

This directory is the reproducible source corpus for local RAG development and
evaluation. Runtime indexing still writes user-scoped chunks to Weaviate and
metadata/original upload bytes to Postgres.

## Layout

- `personal/` — user-provided source files. Keep private or sensitive files out
  of Git unless they are intentionally publishable.
- `authoritative/` — reviewed public standards, regulations, and guidance.
- `recovered/` — material recovered from legacy local vector stores.
- `catalog.md` — source provenance, version, language, license, and inclusion
  rationale.

Do not treat every downloaded document as authoritative merely because it is
present. The catalog records why each source belongs in the corpus and whether
it is normative, advisory, or contextual.
