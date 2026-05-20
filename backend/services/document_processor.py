# backend/services/document_processor.py
"""
DocumentProcessor — extracts, chunks, embeds, and stores uploaded documents.

Storage:
  M1 (PostgreSQL): documents table (metadata) + source_items (one row per chunk)
  M2 (Weaviate): DocumentMemory collection (one object per chunk)
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from services.context_manager import ContextManager
from services.document_extractors import extract_text as _extract_from_path
from utils.db import get_db_connection

if TYPE_CHECKING:
    from services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = "DocumentMemory"
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """Split text into overlapping chunks. Returns empty list if text is blank."""
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
        start = end - overlap
        if start >= len(text):
            break

    return chunks


class DocumentProcessor:
    """Orchestrates the full document ingestion pipeline."""

    SUPPORTED_TYPES = {
        "text/plain": "plain",
        "text/markdown": "plain",
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "docx",
    }

    def __init__(
        self, context_manager: ContextManager, embedding_service: "EmbeddingService"
    ):
        self.context_manager = context_manager
        self.embedding_service = embedding_service

    def extract_text(
        self,
        file_bytes: bytes,
        content_type: str,
        filename: Optional[str] = None,
    ) -> str:
        """Extract plain text from a file's raw bytes.

        Routes via services.document_extractors.extract_text, which dispatches
        on extension/mime type. Writes bytes to a temp file so extractors can
        use their native file-path APIs (pypdf, python-docx).
        """
        base_type = content_type.split(";")[0].strip().lower()
        suffix = self._suffix_for(filename, base_type)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            text = _extract_from_path(tmp_path, mime_type=base_type)
            if not text and base_type not in self.SUPPORTED_TYPES:
                raise ValueError(
                    f"Unsupported content type: {base_type}. "
                    f"Supported: {sorted(self.SUPPORTED_TYPES.keys())}"
                )
            return text
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _suffix_for(filename: Optional[str], base_type: str) -> str:
        if filename:
            ext = os.path.splitext(filename)[1].lower()
            if ext:
                return ext
        if base_type == "application/pdf":
            return ".pdf"
        if "wordprocessingml" in base_type or base_type == "application/msword":
            return ".docx"
        if base_type.startswith("text/"):
            return ".txt"
        return ""

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
        Updates documents table status to 'ready' or 'failed'.
        Returns number of chunks stored.
        """
        try:
            # 1. Extract text
            logger.info(
                "Extracting text from %s (type=%s, size=%d bytes)",
                filename,
                content_type,
                len(file_bytes),
            )
            text = self.extract_text(file_bytes, content_type, filename=filename)
            if not text.strip():
                raise ValueError("Document contains no extractable text")

            # 2. Chunk
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("Document produced no chunks after splitting")

            # 3. Store each chunk in M1 (source_items) + M2 (Weaviate)
            for idx, chunk in enumerate(chunks):
                chunk_external_id = f"{document_id}_chunk_{idx}"

                # M1 write (auto-committed by context manager)
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
                                json.dumps(
                                    {
                                        "document_id": document_id,
                                        "chunk_index": idx,
                                        "chunk_count": len(chunks),
                                        "filename": filename,
                                    }
                                ),
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
            self._update_document_status(
                document_id, "failed", error_message=str(e)[:500]
            )
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
            embedding = await self.embedding_service.generate_embedding(chunk)
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
            logger.warning(
                f"⚠️ Embed failed for chunk {chunk_index} of {document_id}: {e}"
            )

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
