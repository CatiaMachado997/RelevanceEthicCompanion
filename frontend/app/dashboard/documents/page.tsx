'use client'

import { useState, useEffect, useRef, useCallback, DragEvent, ChangeEvent } from 'react'
import { api, Document } from '@/lib/api'
import { FileText, Upload, Trash2, AlertCircle, CheckCircle2, Clock, RefreshCw, Eye } from 'lucide-react'
import { DocumentViewer } from '@/components/DocumentViewer'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function StatusBadge({ status }: { status: Document['status'] }) {
  if (status === 'ready') {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#e6f4ee', color: '#2d6a4f', border: '1px solid #c8e6d3' }}
      >
        <CheckCircle2 size={10} />
        Ready
      </span>
    )
  }
  if (status === 'processing') {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#fff8e1', color: '#8a6600', border: '1px solid #ffe082' }}
      >
        <Clock size={10} className="animate-pulse" />
        Processing
      </span>
    )
  }
  // failed
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: 'rgba(176,74,58,0.08)', color: '#B04A3A', border: '1px solid rgba(176,74,58,0.25)' }}
    >
      <AlertCircle size={10} />
      Failed
    </span>
  )
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [reprocessingId, setReprocessingId] = useState<string | null>(null)
  const [viewingDoc, setViewingDoc] = useState<{ id: string; filename: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await api.documents.list()
      setDocuments(docs)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadDocuments() }, [loadDocuments])

  const handleUpload = useCallback(async (file: File) => {
    const allowed = ['application/pdf', 'text/plain']
    const allowedExts = ['.pdf', '.txt']
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()

    if (!allowed.includes(file.type) && !allowedExts.includes(ext)) {
      setUploadError('Only PDF and plain text (.txt) files are supported.')
      return
    }

    setUploading(true)
    setUploadError(null)

    try {
      await api.documents.upload(file)
      await loadDocuments()
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }, [loadDocuments])

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }, [handleUpload])

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragOver(false)
  }, [])

  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    // Reset so the same file can be re-uploaded if needed
    e.target.value = ''
  }, [handleUpload])

  const handleDelete = useCallback(async (id: string) => {
    setDeletingId(id)
    try {
      await api.documents.delete(id)
      setDocuments(prev => prev.filter(d => d.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete document')
    } finally {
      setDeletingId(null)
    }
  }, [])

  const handleReprocess = useCallback(async (id: string) => {
    setReprocessingId(id)
    setError(null)
    try {
      await api.documents.reprocess(id)
      await loadDocuments()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reprocessing failed. Please re-upload the file.')
    } finally {
      setReprocessingId(null)
    }
  }, [loadDocuments])

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Page header */}
      <div>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--ec-text)' }}>Documents</h2>
        <p className="text-sm mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>
          Upload PDFs and text files so ESL can use them as context when making decisions.
        </p>
      </div>

      {/* Upload error banner */}
      {uploadError && (
        <div
          className="flex items-center justify-between gap-2 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'rgba(176,74,58,0.07)', border: '1px solid rgba(176,74,58,0.25)', color: '#B04A3A' }}
        >
          <div className="flex items-center gap-2">
            <AlertCircle size={15} />
            <span>{uploadError}</span>
          </div>
          <button
            onClick={() => setUploadError(null)}
            className="shrink-0 opacity-50 hover:opacity-100 transition-opacity text-base leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* List error banner */}
      {error && (
        <div
          className="flex items-center justify-between gap-2 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'rgba(176,74,58,0.07)', border: '1px solid rgba(176,74,58,0.25)', color: '#B04A3A' }}
        >
          <div className="flex items-center gap-2">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="shrink-0 opacity-50 hover:opacity-100 transition-opacity text-base leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => !uploading && fileInputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click() }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className="rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-3 py-10 px-6 cursor-pointer transition-colors duration-150 select-none"
        style={{
          background: dragOver
            ? 'var(--ec-surface-2, rgba(74,124,89,0.06))'
            : 'var(--ec-card-bg)',
          borderColor: dragOver ? '#4A7C59' : 'var(--ec-card-border)',
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,application/pdf,text/plain"
          className="hidden"
          onChange={handleFileChange}
        />

        {uploading ? (
          <>
            <RefreshCw size={28} className="animate-spin" style={{ color: '#4A7C59' }} />
            <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>Uploading…</p>
          </>
        ) : (
          <>
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
            >
              <Upload size={20} style={{ color: dragOver ? '#4A7C59' : 'var(--ec-text-muted)' }} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>
                Drop a file here, or <span style={{ color: '#4A7C59' }}>browse</span>
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-subtle)' }}>
                PDF and plain text (.txt) — up to one file at a time
              </p>
            </div>
          </>
        )}
      </div>

      {/* Document list */}
      <div>
        {loading ? (
          <div className="flex items-center justify-center py-12 gap-2" style={{ color: 'var(--ec-text-subtle)' }}>
            <RefreshCw size={16} className="animate-spin" />
            <span className="text-sm">Loading documents…</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
            >
              <FileText size={20} style={{ color: 'var(--ec-text-subtle)' }} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No documents yet</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-subtle)' }}>
                Upload a PDF or text file above to get started.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: 'var(--ec-text-subtle)' }}>
              {documents.length} document{documents.length !== 1 ? 's' : ''}
            </p>
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-4 px-4 py-3 rounded-xl"
                style={{
                  background: 'var(--ec-card-bg)',
                  border: '1px solid var(--ec-card-border)',
                  boxShadow: 'var(--ec-card-shadow)',
                }}
              >
                {/* File icon */}
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
                >
                  <FileText size={16} style={{ color: 'var(--ec-text-muted)' }} />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium truncate" style={{ color: 'var(--ec-text)' }}>
                      {doc.filename}
                    </span>
                    <StatusBadge status={doc.status} />
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>
                      {formatBytes(doc.size_bytes)}
                    </span>
                    {doc.status === 'ready' && doc.chunk_count > 0 && (
                      <span className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>
                        · {doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''}
                      </span>
                    )}
                    <span className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>
                      · {formatDate(doc.created_at)}
                    </span>
                  </div>
                  {doc.status === 'failed' && !doc.has_raw_content && (
                    <p className="text-xs mt-1" style={{ color: '#B04A3A' }}>
                      Delete and re-upload to index this file.
                    </p>
                  )}
                </div>

                {/* Reprocess (failed docs with stored raw bytes) */}
                {doc.status === 'failed' && doc.has_raw_content && (
                  <button
                    onClick={() => handleReprocess(doc.id)}
                    disabled={reprocessingId === doc.id}
                    className="w-9 h-9 flex items-center justify-center rounded-lg transition-colors hover:bg-amber-50 disabled:opacity-40"
                    aria-label="Retry processing"
                    title="Retry processing"
                  >
                    <RefreshCw
                      size={14}
                      className={reprocessingId === doc.id ? 'animate-spin' : ''}
                      style={{ color: '#8a6600' }}
                    />
                  </button>
                )}

                {/* View (ready documents only) */}
                {doc.status === 'ready' && (
                  <button
                    onClick={() => setViewingDoc({ id: doc.id, filename: doc.filename })}
                    className="w-9 h-9 flex items-center justify-center rounded-lg transition-colors hover:bg-black/5"
                    aria-label="View document"
                  >
                    <Eye size={15} style={{ color: 'var(--ec-text-subtle)' }} />
                  </button>
                )}

                {/* Delete */}
                <button
                  onClick={() => handleDelete(doc.id)}
                  disabled={deletingId === doc.id}
                  className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors disabled:opacity-40 hover:opacity-70"
                  style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
                  title="Delete document"
                  aria-label={`Delete ${doc.filename}`}
                >
                  {deletingId === doc.id
                    ? <RefreshCw size={13} className="animate-spin" style={{ color: 'var(--ec-text-muted)' }} />
                    : <Trash2 size={13} style={{ color: '#B04A3A' }} />
                  }
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info footer */}
      <div
        className="flex items-start gap-2 px-4 py-3 rounded-xl"
        style={{ background: 'var(--ec-surface-2, #fafafa)', border: '1px solid var(--ec-card-border)' }}
      >
        <AlertCircle size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--ec-text-subtle)' }} />
        <p className="text-xs leading-relaxed" style={{ color: 'var(--ec-text-subtle)' }}>
          Documents are chunked and stored as embeddings so ESL can retrieve relevant context.
          They are never shared externally.
        </p>
      </div>

      <DocumentViewer
        documentId={viewingDoc?.id ?? null}
        filename={viewingDoc?.filename ?? ''}
        open={!!viewingDoc}
        onClose={() => setViewingDoc(null)}
      />
    </div>
  )
}
