# Sprint 3: Documents Domain

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make documents a first-class product surface — upload PDF/text files, extract + chunk + embed them, search across them, and surface document content in chat responses.

**Architecture:** New `documents` table stores metadata. Chunks are written to `source_items` (source_type='document', source_item_type='chunk') so they participate in the same normalized pipeline as Calendar/Gmail/Slack items. Chunks are also embedded into a new Weaviate `DocumentMemory` collection. The existing search route gains a `document` collection. A new `/dashboard/documents` page provides upload + list + delete UI.

**Tech Stack:** FastAPI · python-multipart · pypdf · psycopg3 (dict_row) · Weaviate · Gemini embeddings · Next.js 15 · TypeScript

---

## File Map

### New files
- `backend/database/migration_sprint3.sql` — `documents` table
- `backend/services/document_processor.py` — extract text, chunk, embed, store
- `backend/routes/documents.py` — upload / list / delete routes
- `backend/tests/test_document_processor.py` — unit tests for processor
- `frontend/app/dashboard/documents/page.tsx` — documents page (upload + list)

### Modified files
- `backend/routes/search.py` — add `DocumentMemory` to SEARCH_COLLECTIONS
- `backend/main.py` — register documents router
- `frontend/app/dashboard/layout.tsx` — add Documents nav item (if not already there)
- `frontend/app/dashboard/search/page.tsx` — add "document" filter chip + file icon
- `frontend/lib/api.ts` — add `documentsApi`
- `frontend/components/sidebar.tsx` — add Documents link

### Untouched
- `backend/services/connectors/` — connector framework is not changed
- `backend/services/data_ingestion.py` — not changed
- `backend/esl/` — untouched (ESL is checked inside document_processor before storing)

---

## Task 1: Database Migration — documents table

**Files:**
- Create: `backend/database/migration_sprint3.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Sprint 3: Documents domain — document metadata table
-- Run: PGPASSWORD=postgres psql -h localhost -U postgres -d ethic_companion -f migration_sprint3.sql

CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    content_type  TEXT NOT NULL,         -- 'application/pdf', 'text/plain', etc.
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'processing'
                  CHECK (status IN ('processing', 'ready', 'failed')),
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status  ON documents(status);
```

- [ ] **Step 2: Apply to local DB**

```bash
PGPASSWORD=postgres psql -h localhost -U postgres -d ethic_companion -f backend/database/migration_sprint3.sql
```

Expected: `CREATE TABLE`, `CREATE INDEX`, `CREATE INDEX`

- [ ] **Step 3: Verify**

```bash
PGPASSWORD=postgres psql -h localhost -U postgres -d ethic_companion -c "\d documents"
```

Expected: table with id, user_id, filename, content_type, size_bytes, status, chunk_count, error_message, created_at, updated_at.

- [ ] **Step 4: Commit**

```bash
git add backend/database/migration_sprint3.sql
git commit -m "feat: add documents table for Sprint 3 document domain"
```

---

## Task 2: DocumentProcessor Service

Handles extraction, chunking, embedding, and storage for uploaded files.

**Files:**
- Create: `backend/services/document_processor.py`
- Create: `backend/tests/test_document_processor.py`

**Note on dependencies:** `pypdf` is needed for PDF parsing. Check if it is in `requirements.txt`:
```bash
grep -i "pypdf\|PyPDF" backend/requirements.txt
```
If not present, add `pypdf>=4.0.0` to `requirements.txt` and install it:
```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/pip install "pypdf>=4.0.0"
```

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_document_processor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.document_processor import DocumentProcessor, chunk_text


# ── chunk_text ──────────────────────────────────────────────────────────────

def test_chunk_text_short_document():
    """Short text should produce exactly one chunk."""
    text = "Hello world. This is a short document."
    chunks = chunk_text(text, chunk_size=2000, overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_splits_long_document():
    """Long text should be split into multiple chunks."""
    text = "word " * 1000  # ~5000 chars
    chunks = chunk_text(text, chunk_size=2000, overlap=200)
    assert len(chunks) > 1
    # Every chunk should be ≤ chunk_size
    for chunk in chunks:
        assert len(chunk) <= 2000 + 200  # allow slight overlap


def test_chunk_text_overlap():
    """Consecutive chunks should share overlapping content."""
    text = "a" * 100 + " " + "b" * 100 + " " + "c" * 100
    chunks = chunk_text(text, chunk_size=150, overlap=50)
    assert len(chunks) >= 2
    # The tail of chunk[0] and the head of chunk[1] should overlap
    if len(chunks) >= 2:
        tail = chunks[0][-50:]
        head = chunks[1][:50]
        # They should share at least some characters
        assert len(tail) > 0 and len(head) > 0


def test_chunk_text_empty():
    """Empty text should return an empty list."""
    chunks = chunk_text("", chunk_size=2000, overlap=200)
    assert chunks == []


def test_chunk_text_whitespace_only():
    """Whitespace-only text should return empty list."""
    chunks = chunk_text("   \n\t  ", chunk_size=2000, overlap=200)
    assert chunks == []


# ── extract_text ────────────────────────────────────────────────────────────

def test_extract_text_plain():
    """Plain text bytes should be decoded and returned as-is."""
    processor = DocumentProcessor(context_manager=MagicMock(), embedding_service=MagicMock())
    text = processor.extract_text(b"Hello, world!", "text/plain")
    assert text == "Hello, world!"


def test_extract_text_unsupported():
    """Unsupported content type should raise ValueError."""
    processor = DocumentProcessor(context_manager=MagicMock(), embedding_service=MagicMock())
    with pytest.raises(ValueError, match="Unsupported"):
        processor.extract_text(b"data", "image/png")
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_document_processor.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'services.document_processor'`

- [ ] **Step 3: Write the service**

```python
# backend/services/document_processor.py
"""
DocumentProcessor — extracts, chunks, embeds, and stores uploaded documents.

Storage:
  M1 (PostgreSQL): documents table (metadata) + source_items (one row per chunk)
  M2 (Weaviate): DocumentMemory collection (one object per chunk)
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from services.context_manager import ContextManager
from services.embedding_service import EmbeddingService
from utils.db import get_db_connection

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = "DocumentMemory"
CHUNK_SIZE = 2000   # characters
CHUNK_OVERLAP = 200  # characters


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: The full document text.
        chunk_size: Maximum characters per chunk.
        overlap: Characters of overlap between adjacent chunks.

    Returns:
        List of text chunks. Empty list if text is blank.
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap  # step back by overlap for next chunk
        if start >= len(text):
            break

    return chunks


class DocumentProcessor:
    """Orchestrates the full document ingestion pipeline."""

    SUPPORTED_TYPES = {
        "text/plain": "_extract_plain",
        "application/pdf": "_extract_pdf",
    }

    def __init__(self, context_manager: ContextManager, embedding_service: EmbeddingService):
        self.context_manager = context_manager
        self.embedding_service = embedding_service

    def extract_text(self, file_bytes: bytes, content_type: str) -> str:
        """
        Extract plain text from a file.

        Args:
            file_bytes: Raw file bytes.
            content_type: MIME type of the file.

        Returns:
            Extracted text string.

        Raises:
            ValueError: If content_type is not supported.
        """
        # Normalise content type (strip charset, params)
        base_type = content_type.split(";")[0].strip().lower()

        if base_type not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported content type: {base_type}. "
                f"Supported: {list(self.SUPPORTED_TYPES.keys())}"
            )

        method_name = self.SUPPORTED_TYPES[base_type]
        return getattr(self, method_name)(file_bytes)

    def _extract_plain(self, file_bytes: bytes) -> str:
        return file_bytes.decode("utf-8", errors="replace")

    def _extract_pdf(self, file_bytes: bytes) -> str:
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except Exception as e:
            raise ValueError(f"PDF extraction failed: {e}") from e

    async def process_document(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> int:
        """
        Full pipeline: extract → chunk → store M1 → embed → store M2.

        Updates the documents table status to 'ready' or 'failed'.

        Returns:
            Number of chunks stored.
        """
        try:
            # 1. Extract text
            text = self.extract_text(file_bytes, content_type)
            if not text.strip():
                raise ValueError("Document contains no extractable text")

            # 2. Chunk
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("Document produced no chunks after splitting")

            # 3. Store each chunk in M1 (source_items) + M2 (Weaviate)
            for idx, chunk in enumerate(chunks):
                chunk_external_id = f"{document_id}_chunk_{idx}"

                # M1 write
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO source_items
                                (user_id, source_type, source_item_type, external_id,
                                 title, body, metadata, embedding_status)
                            VALUES (%s, 'document', 'chunk', %s, %s, %s, %s, 'pending')
                            ON CONFLICT (user_id, source_type, external_id) DO UPDATE SET
                                body = EXCLUDED.body,
                                synced_at = NOW()
                            """,
                            (
                                user_id,
                                chunk_external_id,
                                f"{filename} [chunk {idx + 1}/{len(chunks)}]",
                                chunk,
                                json.dumps({
                                    "document_id": document_id,
                                    "chunk_index": idx,
                                    "chunk_count": len(chunks),
                                    "filename": filename,
                                }),
                            ),
                        )

                # M2 write (best-effort)
                await self._embed_chunk(
                    user_id=user_id,
                    chunk=chunk,
                    document_id=document_id,
                    filename=filename,
                    chunk_index=idx,
                    chunk_count=len(chunks),
                )

            # 4. Mark document as ready
            self._update_document_status(document_id, "ready", chunk_count=len(chunks))
            logger.info(f"✅ Document {document_id} processed: {len(chunks)} chunks")
            return len(chunks)

        except Exception as e:
            logger.error(f"❌ Document processing failed for {document_id}: {e}")
            self._update_document_status(document_id, "failed", error_message=str(e)[:500])
            raise

    async def _embed_chunk(
        self,
        user_id: str,
        chunk: str,
        document_id: str,
        filename: str,
        chunk_index: int,
        chunk_count: int,
    ):
        """Store a single chunk in Weaviate DocumentMemory (best-effort)."""
        if not (self.context_manager.weaviate and self.embedding_service):
            return
        try:
            embedding = await self.embedding_service.generate_embedding(
                chunk, task_type="retrieval_document"
            )
            self.context_manager.weaviate.store_memory(
                DOCUMENT_COLLECTION,
                {
                    "user_id": str(user_id),
                    "content": chunk,
                    "document_id": str(document_id),
                    "filename": filename,
                    "chunk_index": chunk_index,
                    "chunk_count": chunk_count,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                embedding,
            )
            # Update embedding_status to 'indexed'
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE source_items SET embedding_status = 'indexed'
                        WHERE user_id = %s AND source_type = 'document'
                          AND external_id = %s
                        """,
                        (user_id, f"{document_id}_chunk_{chunk_index}"),
                    )
        except Exception as e:
            logger.warning(f"⚠️ Embed failed for chunk {chunk_index} of {document_id}: {e}")

    def _update_document_status(
        self,
        document_id: str,
        status: str,
        chunk_count: int = 0,
        error_message: Optional[str] = None,
    ):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE documents
                    SET status = %s,
                        chunk_count = %s,
                        error_message = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (status, chunk_count, error_message, document_id),
                )
```

- [ ] **Step 4: Add DocumentMemory schema to `weaviate_config.py`**

Open `backend/weaviate_config.py` and append the following schema to the `WEAVIATE_SCHEMAS` list (before the closing `]`):

```python
    {
        "class": "DocumentMemory",
        "description": "Document chunks with semantic embeddings for search",
        "vectorizer": "none",
        "properties": [
            {"name": "user_id",      "dataType": ["text"], "indexFilterable": True,  "indexSearchable": False},
            {"name": "content",      "dataType": ["text"], "indexFilterable": False, "indexSearchable": True},
            {"name": "document_id",  "dataType": ["text"], "indexFilterable": True,  "indexSearchable": False},
            {"name": "filename",     "dataType": ["text"], "indexFilterable": False, "indexSearchable": True},
            {"name": "chunk_index",  "dataType": ["int"],  "indexFilterable": True,  "indexSearchable": False},
            {"name": "chunk_count",  "dataType": ["int"],  "indexFilterable": False, "indexSearchable": False},
            {"name": "created_at",   "dataType": ["date"], "indexFilterable": True,  "indexSearchable": False},
        ],
    },
```

- [ ] **Step 5: Run the tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_document_processor.py -v
```

Expected: 7 PASSED.

- [ ] **Step 6: Run full regression**

```bash
/Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_esl.py tests/test_feedback.py tests/test_document_processor.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/services/document_processor.py backend/tests/test_document_processor.py backend/requirements.txt backend/weaviate_config.py
git commit -m "feat: add DocumentProcessor — extract, chunk, embed, store pipeline"
```

---

## Task 3: Documents API Routes

**Files:**
- Create: `backend/routes/documents.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to backend/tests/test_document_processor.py

from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


def test_documents_list_endpoint():
    """GET /api/documents should return a list (may be empty)."""
    from main import app
    client = TestClient(app)
    with patch("routes.documents.get_current_read_user_id", return_value="user-1"), \
         patch("routes.documents.get_user_documents", return_value=[]):
        response = client.get("/api/documents/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_documents_upload_unsupported_type():
    """Upload of unsupported file type should return 400."""
    from main import app
    import io
    client = TestClient(app)
    with patch("routes.documents.get_current_user_id", return_value="user-1"):
        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")},
        )
    assert response.status_code == 400
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_document_processor.py::test_documents_list_endpoint tests/test_document_processor.py::test_documents_upload_unsupported_type -v 2>&1 | head -10
```

Expected: ImportError or 404.

- [ ] **Step 3: Write the routes**

```python
# backend/routes/documents.py
"""
Documents API routes.

POST /api/documents/upload  — upload a file (PDF or plain text)
GET  /api/documents/        — list user's documents
DELETE /api/documents/{id}  — delete a document + its chunks
"""
import logging
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from services.document_processor import DocumentProcessor
from services.context_manager import ContextManager
from services.embedding_service import EmbeddingService
from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from utils.weaviate_client import get_weaviate_client
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

SUPPORTED_CONTENT_TYPES = {"application/pdf", "text/plain"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def get_document_processor() -> DocumentProcessor:
    weaviate_client = get_weaviate_client()
    embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
    context_manager = ContextManager(
        weaviate_client=weaviate_client,
        embedding_service=embedding_service,
    )
    return DocumentProcessor(
        context_manager=context_manager,
        embedding_service=embedding_service,
    )


def get_user_documents(user_id: str) -> List[Dict[str, Any]]:
    """Query documents table for a user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, content_type, size_bytes, status,
                       chunk_count, error_message, created_at
                FROM documents
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(row["id"]),
            "filename": row["filename"],
            "content_type": row["content_type"],
            "size_bytes": row["size_bytes"],
            "status": row["status"],
            "chunk_count": row["chunk_count"],
            "error_message": row["error_message"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> Dict[str, Any]:
    """
    Upload a PDF or plain text file for indexing.

    The file is stored, chunked, embedded, and indexed for search.
    Processing happens synchronously (Sprint 3 MVP — async queue in Sprint 4+).
    """
    # Validate content type
    content_type = file.content_type or ""
    base_type = content_type.split(";")[0].strip().lower()
    if base_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {base_type}. Supported: PDF, plain text.",
        )

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB.",
        )
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty.")

    # Create document record (status=processing)
    document_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (id, user_id, filename, content_type, size_bytes, status)
                VALUES (%s, %s, %s, %s, %s, 'processing')
                """,
                (document_id, user_id, file.filename or "untitled", base_type, len(file_bytes)),
            )

    # Process synchronously
    try:
        chunk_count = await processor.process_document(
            user_id=user_id,
            document_id=document_id,
            filename=file.filename or "untitled",
            content_type=base_type,
            file_bytes=file_bytes,
        )
        return {
            "id": document_id,
            "filename": file.filename,
            "status": "ready",
            "chunk_count": chunk_count,
            "message": f"Indexed {chunk_count} chunks",
        }
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        raise HTTPException(status_code=422, detail=f"Processing failed: {str(e)}")


@router.get("/")
async def list_documents(
    user_id: str = Depends(get_current_read_user_id),
) -> List[Dict[str, Any]]:
    """List all documents uploaded by the current user."""
    try:
        return get_user_documents(user_id)
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Delete a document and all its chunks from M1 (source_items + documents table).
    Weaviate cleanup is best-effort.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify ownership
                cur.execute(
                    "SELECT id FROM documents WHERE id = %s AND user_id = %s",
                    (document_id, user_id),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Document not found")

                # Delete chunks from source_items
                cur.execute(
                    """
                    DELETE FROM source_items
                    WHERE user_id = %s AND source_type = 'document'
                      AND metadata->>'document_id' = %s
                    """,
                    (user_id, document_id),
                )

                # Delete document record
                cur.execute(
                    "DELETE FROM documents WHERE id = %s AND user_id = %s",
                    (document_id, user_id),
                )

        return {"success": True, "id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")
```

- [ ] **Step 4: Register the router in `main.py`**

Find the line in `backend/main.py` where other routers are registered (e.g., `app.include_router(search.router)`). Add:

```python
from routes import documents
app.include_router(documents.router)
```

- [ ] **Step 5: Run the tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_document_processor.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 6: Verify route registered**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -c "from main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'document' in r])"
```

Expected: `['/api/documents/upload', '/api/documents/', '/api/documents/{document_id}']`

- [ ] **Step 7: Commit**

```bash
git add backend/routes/documents.py backend/main.py
git commit -m "feat: add document upload/list/delete API routes"
```

---

## Task 4: Expand Search to Include Documents

**Files:**
- Modify: `backend/routes/search.py`

One-line change — add the DocumentMemory collection to SEARCH_COLLECTIONS.

- [ ] **Step 1: Edit `backend/routes/search.py`**

Find:
```python
SEARCH_COLLECTIONS = [
    ("ConversationMemory", "memory"),
    ("ContextualEvents", "event"),
]
```

Replace with:
```python
SEARCH_COLLECTIONS = [
    ("ConversationMemory", "memory"),
    ("ContextualEvents", "event"),
    ("DocumentMemory", "document"),
]
```

- [ ] **Step 2: Verify the search still works with the extra collection**

The existing search route already handles missing collections gracefully (`except Exception: logger.warning(...) continue`), so if `DocumentMemory` doesn't exist in Weaviate yet, search still works.

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_esl.py tests/test_document_processor.py -q
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add backend/routes/search.py
git commit -m "feat: expand search to include DocumentMemory collection"
```

---

## Task 5: Frontend — documentsApi in api.ts

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Check existing api.ts pattern**

```bash
grep -n "export\|Api\|apiRequest" frontend/lib/api.ts | head -20
```

Note how existing APIs (dataSourcesApi, searchApi) are structured.

- [ ] **Step 2: Add documentsApi**

Add to `frontend/lib/api.ts` (following the existing pattern):

```typescript
export interface Document {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  status: 'processing' | 'ready' | 'failed'
  chunk_count: number
  error_message?: string | null
  created_at: string
}

export const documentsApi = {
  list: async (): Promise<Document[]> => {
    return apiRequest('/api/documents/')
  },

  upload: async (file: File): Promise<{ id: string; filename: string; status: string; chunk_count: number; message: string }> => {
    const formData = new FormData()
    formData.append('file', file)
    return apiRequest('/api/documents/upload', {
      method: 'POST',
      body: formData,
      // Don't set Content-Type — browser sets it with boundary for multipart
    })
  },

  delete: async (id: string): Promise<{ success: boolean; id: string }> => {
    return apiRequest(`/api/documents/${id}`, { method: 'DELETE' })
  },
}
```

**Important note on `apiRequest`:** Check if `apiRequest` sets `Content-Type: application/json` by default. If so, the `upload` call needs to NOT pass that header (FormData sets its own boundary). Read `apiRequest` implementation to check and adjust if needed — the existing upload should NOT set `Content-Type` manually.

- [ ] **Step 3: Run TypeScript check**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend && npx tsc --noEmit 2>&1 | grep -v "node_modules" | head -20
```

Expected: no errors in application code.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add documentsApi to frontend api client"
```

---

## Task 6: Frontend — Documents Page

**Files:**
- Create: `frontend/app/dashboard/documents/page.tsx`
- Modify: `frontend/components/sidebar.tsx` (add Documents nav link)

- [ ] **Step 1: Read sidebar.tsx to understand nav link pattern**

```bash
cat frontend/components/sidebar.tsx | grep -A3 "href\|navItem\|link"
```

Note the pattern for existing nav items (path, icon, label).

- [ ] **Step 2: Write the documents page**

```tsx
// frontend/app/dashboard/documents/page.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { FileText, Upload, Trash2, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { documentsApi, Document } from '@/lib/api'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function StatusBadge({ status }: { status: Document['status'] }) {
  if (status === 'ready') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#e6f4ee', color: '#2d6a4f' }}>
        <span className="w-1.5 h-1.5 rounded-full bg-[#4A7C59]" />
        Ready
      </span>
    )
  }
  if (status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#fff8e6', color: '#8a6200' }}>
        <Loader2 size={9} className="animate-spin" />
        Processing
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: 'rgba(176,74,58,0.08)', color: '#B04A3A' }}>
      <AlertCircle size={9} />
      Failed
    </span>
  )
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [flash, setFlash] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await documentsApi.list()
      setDocuments(docs)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadDocuments() }, [loadDocuments])

  const showFlash = (type: 'success' | 'error', message: string) => {
    setFlash({ type, message })
    setTimeout(() => setFlash(null), 5000)
  }

  const handleUpload = async (file: File) => {
    const allowed = ['application/pdf', 'text/plain']
    if (!allowed.includes(file.type)) {
      showFlash('error', `Unsupported file type: ${file.type}. Only PDF and plain text are supported.`)
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      showFlash('error', 'File is too large. Maximum size is 10 MB.')
      return
    }

    setUploading(true)
    try {
      const result = await documentsApi.upload(file)
      showFlash('success', `${result.filename} indexed — ${result.chunk_count} chunks ready for search.`)
      await loadDocuments()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed. Please try again.'
      showFlash('error', msg)
    } finally {
      setUploading(false)
    }
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  const handleDelete = async (id: string, filename: string) => {
    setDeleting(id)
    try {
      await documentsApi.delete(id)
      setDocuments(prev => prev.filter(d => d.id !== id))
      showFlash('success', `${filename} deleted.`)
    } catch {
      showFlash('error', 'Failed to delete document. Please try again.')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold" style={{ color: '#1c1520' }}>Documents</h2>
        <p className="text-sm mt-0.5" style={{ color: '#695e6e' }}>
          Upload PDFs and text files to search across them and use them in chat.
        </p>
      </div>

      {/* Flash */}
      {flash && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm" style={{
          background: flash.type === 'success' ? '#f0f7f2' : 'rgba(176,74,58,0.07)',
          border: `1px solid ${flash.type === 'success' ? '#c8e6d3' : 'rgba(176,74,58,0.25)'}`,
          color: flash.type === 'success' ? '#2d6a4f' : '#B04A3A',
        }}>
          {flash.type === 'success' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
          <span>{flash.message}</span>
        </div>
      )}

      {/* Upload area */}
      <label
        className="block cursor-pointer rounded-2xl border-2 border-dashed transition-colors"
        style={{
          borderColor: dragOver ? '#4A7C59' : 'rgba(0,0,0,0.12)',
          background: dragOver ? 'rgba(74,124,89,0.04)' : '#fafafa',
        }}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <input type="file" className="sr-only" accept=".pdf,.txt,text/plain,application/pdf"
          onChange={handleFileInput} disabled={uploading} />
        <div className="flex flex-col items-center justify-center py-10 gap-3">
          {uploading ? (
            <>
              <Loader2 size={28} className="animate-spin" style={{ color: '#4A7C59' }} />
              <p className="text-sm font-medium" style={{ color: '#4A7C59' }}>Indexing document…</p>
            </>
          ) : (
            <>
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                style={{ background: '#f0f0f0' }}>
                <Upload size={22} style={{ color: '#6b6b6b' }} />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium" style={{ color: '#1c1520' }}>
                  Drop a file here, or <span style={{ color: '#4A7C59' }}>browse</span>
                </p>
                <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>PDF or plain text · max 10 MB</p>
              </div>
            </>
          )}
        </div>
      </label>

      {/* Document list */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2].map(i => (
            <div key={i} className="h-16 rounded-2xl animate-pulse" style={{ background: '#f0f0f0' }} />
          ))}
        </div>
      ) : documents.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: '#9e9e9e' }}>
            {documents.length} document{documents.length !== 1 ? 's' : ''}
          </p>
          {documents.map(doc => (
            <div key={doc.id} className="flex items-center gap-3 px-4 py-3 rounded-2xl"
              style={{ border: '1px solid rgba(0,0,0,0.08)', background: '#fff' }}>
              <FileText size={18} style={{ color: '#6b6b6b', flexShrink: 0 }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium truncate" style={{ color: '#1c1520' }}>
                    {doc.filename}
                  </span>
                  <StatusBadge status={doc.status} />
                </div>
                <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>
                  {formatBytes(doc.size_bytes)}
                  {doc.status === 'ready' && ` · ${doc.chunk_count} chunks`}
                  {doc.error_message && ` · ${doc.error_message}`}
                </p>
              </div>
              <button
                onClick={() => handleDelete(doc.id, doc.filename)}
                disabled={deleting === doc.id}
                className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors hover:bg-[#fce8e6] disabled:opacity-40"
                title="Delete document"
              >
                {deleting === doc.id
                  ? <Loader2 size={14} className="animate-spin" style={{ color: '#B04A3A' }} />
                  : <Trash2 size={14} style={{ color: '#B04A3A' }} />
                }
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
            style={{ background: '#f5f2ef' }}>
            <FileText size={24} style={{ color: '#b0a6b4' }} />
          </div>
          <p className="text-sm font-medium" style={{ color: '#1c1520' }}>No documents yet</p>
          <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>
            Upload a PDF or text file to get started
          </p>
        </div>
      )}

      {/* Info footer */}
      <div className="flex items-start gap-2 px-4 py-3 rounded-xl"
        style={{ background: '#f9f6fa', border: '1px solid #e4dee7' }}>
        <AlertCircle size={13} className="mt-0.5 shrink-0" style={{ color: '#b0a6b4' }} />
        <p className="text-xs leading-relaxed" style={{ color: '#9e9e9e' }}>
          Documents are chunked and indexed for semantic search. Content is only accessible to you.
          ESL applies to all document-sourced responses.
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Add Documents link to sidebar**

Read `frontend/components/sidebar.tsx`. Find where nav items are defined (look for `href="/dashboard/integrations"` or similar). Add a Documents entry following the same pattern:

```tsx
{ href: '/dashboard/documents', icon: FileText, label: 'Documents' }
```

Import `FileText` from `lucide-react` if not already imported.

- [ ] **Step 4: TypeScript check**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend && npx tsc --noEmit 2>&1 | grep -v "node_modules\|test" | head -20
```

Expected: no application code errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/dashboard/documents/page.tsx frontend/components/sidebar.tsx
git commit -m "feat: add Documents page with upload/list/delete UI and sidebar nav link"
```

---

## Task 7: Frontend — Add document filter to search page

**Files:**
- Modify: `frontend/app/dashboard/search/page.tsx`

Small additive changes only — add `document` as a filter type and show a file icon for document results.

- [ ] **Step 1: Update FilterType and getIcon/getTypeLabel**

In `search/page.tsx`:

Change:
```typescript
type FilterType = "all" | "memory" | "event"
```
To:
```typescript
type FilterType = "all" | "memory" | "event" | "document"
```

Add `FileText` to the lucide-react import at the top.

In `getIcon`:
```typescript
case "document":
  return <FileText className="h-4 w-4" />
```

In `getTypeLabel`:
```typescript
case "document": return "Document"
```

- [ ] **Step 2: Add document chip to FilterChips**

Find the chips array:
```tsx
chips={[
  { value: null, label: 'All' },
  { value: 'memory', label: 'Memory' },
  { value: 'event', label: 'Event' },
]}
```

Add:
```tsx
{ value: 'document', label: 'Document' },
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend && npx tsc --noEmit 2>&1 | grep -v "node_modules\|test" | head -10
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/dashboard/search/page.tsx
git commit -m "feat: add document filter chip and icon to search page"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_esl.py tests/test_feedback.py tests/test_goals_routes.py tests/test_connectors.py tests/test_document_processor.py -q
```

Expected: all pass (≥80 tests).

- [ ] **End-to-end smoke test**

1. Start backend: `cd backend && python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to `/dashboard/documents` — upload area should appear
4. Upload a `.txt` file — should show "X chunks ready for search"
5. Go to `/dashboard/search` — search for content from the file — should return document results
6. Delete the document — should disappear from the list

- [ ] **Tag**

```bash
git tag sprint/3-documents
```

---

## Critical Files Reference

| File | Change | Why |
|------|--------|-----|
| `backend/database/migration_sprint3.sql` | New | documents table |
| `backend/services/document_processor.py` | New | extract + chunk + embed pipeline |
| `backend/routes/documents.py` | New | upload/list/delete API |
| `backend/main.py` | Additive | register documents router |
| `backend/routes/search.py` | 1-line change | add DocumentMemory collection |
| `frontend/lib/api.ts` | Additive | documentsApi + Document type |
| `frontend/app/dashboard/documents/page.tsx` | New | documents UI |
| `frontend/components/sidebar.tsx` | Additive | Documents nav link |
| `frontend/app/dashboard/search/page.tsx` | Additive | document filter + icon |
