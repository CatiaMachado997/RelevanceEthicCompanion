# backend/routes/documents.py
"""
Documents API routes.

POST /api/documents/upload      — upload a file (PDF or plain text)
GET  /api/documents/            — list user's documents
DELETE /api/documents/{id}      — delete a document + its chunks
GET  /api/documents/{id}/view   — stream document bytes inline (Bearer or ?token=)
"""
import io
import logging
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from services.document_processor import DocumentProcessor
from services.context_manager import ContextManager
from services.embedding_service import EmbeddingService
from utils.db import get_db_connection
from utils.supabase_auth import (
    get_current_user_id,
    get_current_read_user_id,
    get_user_id_from_token,
)
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
                       chunk_count, error_message, created_at,
                       raw_content IS NOT NULL AS has_raw_content
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
            "has_raw_content": bool(row["has_raw_content"]),
        }
        for row in rows
    ]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> Dict[str, Any]:
    """Upload a PDF or plain text file for indexing."""
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
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB.",
        )

    # Create document record (status=processing), storing raw bytes for inline viewing
    document_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (id, user_id, filename, content_type, size_bytes, status, raw_content)
                VALUES (%s, %s, %s, %s, %s, 'processing', %s)
                """,
                (document_id, user_id, file.filename or "untitled", base_type, len(file_bytes), file_bytes),
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
    """Delete a document and all its chunks from M1. Weaviate cleanup is best-effort."""
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

        # TODO: delete chunks from Weaviate by document_id filter
        return {"success": True, "id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> Dict[str, Any]:
    """
    Re-run processing on a failed document using its stored raw bytes.
    Only available for documents that have raw_content stored (uploaded after sprint-2a).
    Documents uploaded before this feature was added must be re-uploaded.
    """
    # Fetch document with raw bytes
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, content_type, raw_content, status
                FROM documents
                WHERE id = %s AND user_id = %s
                """,
                (document_id, user_id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    raw = row["raw_content"]
    if raw is None:
        raise HTTPException(
            status_code=422,
            detail="No raw content stored — please re-upload the file.",
        )

    filename = row["filename"]
    content_type = row["content_type"] or "application/pdf"

    # Mark as processing
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET status = 'processing', error_message = NULL, chunk_count = 0 WHERE id = %s",
                (document_id,),
            )

    try:
        file_bytes = raw if isinstance(raw, bytes) else raw.tobytes()
        chunk_count = await processor.process_document(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
        )
        return {
            "id": document_id,
            "filename": filename,
            "status": "ready",
            "chunk_count": chunk_count,
            "message": f"Reprocessed successfully: {chunk_count} chunks indexed",
        }
    except Exception as e:
        logger.error(f"Reprocess failed for {document_id}: {e}")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET status = 'failed', error_message = %s WHERE id = %s",
                    (str(e), document_id),
                )
        raise HTTPException(status_code=422, detail=f"Reprocessing failed: {str(e)}")


@router.get("/{document_id}/view")
async def view_document(
    document_id: str,
    request: Request,
    token: str | None = None,
):
    """
    Stream document bytes for inline viewing in an iframe.
    Accepts auth via Bearer header OR ?token= query param (required for iframes,
    which cannot set custom headers).
    """
    # Auth: try Bearer header first, fall back to ?token= query param
    auth_header = request.headers.get("Authorization", "")
    jwt = None
    if auth_header.startswith("Bearer "):
        jwt = auth_header[7:]
    elif token:
        jwt = token

    if not jwt:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Verify JWT using the public helper (handles dev-mode bypass and error cases)
    user_id = get_user_id_from_token(jwt)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, content_type, raw_content
                FROM documents
                WHERE id = %s AND user_id = %s
                """,
                (document_id, user_id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    raw = row["raw_content"]
    if raw is None:
        raise HTTPException(status_code=404, detail="Document content not available")

    content_type = row["content_type"] or "application/octet-stream"

    safe_name = row["filename"].replace('"', "'").replace("\r", "").replace("\n", "")
    return StreamingResponse(
        io.BytesIO(raw if isinstance(raw, bytes) else raw.tobytes()),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control": "private, max-age=300",
        },
    )
