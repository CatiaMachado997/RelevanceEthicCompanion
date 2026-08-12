"""ConnectorIndexer — chunks a SourceItem's body and indexes each chunk into
the same Weaviate DocumentMemory collection that Sprint A's `search_documents`
queries. The collection's hybrid search (alpha=0.7) returns connector content
alongside uploaded documents with no further changes to the retrieval path.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from config import settings
from services.connectors.base import SourceItem
from services.embedding_service import EmbeddingService
from services.text_chunking import (
    TextChunk,
    detect_language,
    embedding_text,
    structure_aware_chunks,
)
from utils.weaviate_client import get_weaviate_client
from utils.db import get_db_connection

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = "DocumentMemory"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 45


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Lazy singleton — avoids constructing the Gemini client at import time."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
    return _embedding_service


def _chunk_text(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """String view over the shared structure-aware chunker."""
    return [
        chunk.content
        for chunk in structure_aware_chunks(text, max_words=size, overlap_words=overlap)
    ]


class ConnectorIndexer:
    """Connector → DocumentMemory pipeline."""

    async def index(self, item: SourceItem) -> int:
        """Chunk + embed the item. Returns number of chunks indexed (0 on skip/error)."""
        weav = get_weaviate_client()
        if weav is None:
            return 0

        body = (item.body or "").strip()
        if not body:
            return 0

        # Prepend the title so the first chunk anchors on subject/channel.
        full = f"{item.title}\n\n{body}" if item.title else body
        structured_chunks = structure_aware_chunks(
            full, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP
        )
        if not structured_chunks:
            return 0

        embed = get_embedding_service()
        now = datetime.now(timezone.utc).isoformat()
        language = detect_language(full)

        last_error: Optional[Exception] = None

        for idx, structured_chunk in enumerate(structured_chunks):
            chunk = structured_chunk.content
            try:
                vec = await embed.generate_embedding(
                    embedding_text(
                        TextChunk(chunk, structured_chunk.section_title),
                        title=item.title or item.external_id,
                    )
                )
                weav.store_memory(
                    DOCUMENT_COLLECTION,
                    {
                        "user_id": str(item.user_id),
                        "content": chunk,
                        "document_id": f"{item.source_type}:{item.external_id}",
                        "filename": item.title or item.external_id,
                        "chunk_index": idx,
                        "chunk_count": len(structured_chunks),
                        "source_type": item.source_type,
                        "embedding_model": embed.model,
                        "section_title": structured_chunk.section_title,
                        "language": language,
                        "document_version": "",
                        "created_at": now,
                    },
                    vec,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"⚠️ index chunk {idx} of {item.source_type}:{item.external_id} failed: {e}"
                )
                # Continue with remaining chunks; partial coverage beats none.

        if last_error is not None:
            # Surface the failure on the row + emit telemetry so the user can
            # see it in the connectors panel. Data_ingestion's success-update
            # will not run because we re-raise below.
            err_msg = str(last_error)[:1000]
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE source_items
                                  SET embedding_status = 'failed',
                                      embedding_error = %s
                                WHERE user_id = %s
                                  AND source_type = %s
                                  AND external_id = %s""",
                            (err_msg, item.user_id, item.source_type, item.external_id),
                        )
                    conn.commit()
            except Exception as db_exc:
                logger.warning(f"⚠️ embedding_status=failed update failed: {db_exc}")

            try:
                from services.tool_telemetry import ToolTelemetryService

                ToolTelemetryService().record_tool_call(
                    user_id=str(item.user_id),
                    tool_name="connector_indexer",
                    source="scheduled",
                    source_ref=item.source_type,
                    input={"external_id": item.external_id},
                    output=None,
                    status="error",
                    error_message=err_msg,
                )
            except Exception as tele_exc:  # noqa: BLE001
                logger.warning(f"⚠️ telemetry record_tool_call failed: {tele_exc}")

            # Re-raise so data_ingestion's success-update path is skipped.
            raise last_error

        return len(structured_chunks)
