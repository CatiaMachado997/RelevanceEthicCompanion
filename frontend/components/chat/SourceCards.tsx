'use client'

import type { ComponentType } from 'react'
import { FileText, Mail, MessageSquare } from 'lucide-react'
import type { DocumentSource } from '@/lib/api'

const SOURCE_ICON: Record<string, ComponentType<{ size?: number | string }>> = {
  document: FileText,
  gmail: Mail,
  slack: MessageSquare,
}

/**
 * Citation cards for grounded RAG answers.
 *
 * Renders below assistant messages whose `document_sources` is non-empty.
 * Each card shows filename, snippet preview, and a relevance score badge.
 * Trust-over-engagement: every grounded answer surfaces the exact chunks the
 * model could see, so the user can audit what informed the response.
 */
export function SourceCards({ sources }: { sources?: DocumentSource[] }) {
  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-3 space-y-2">
      <div
        className="text-[11px] font-medium uppercase tracking-wide"
        style={{ color: 'var(--ec-text-muted, #888)' }}
      >
        Sources ({sources.length})
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {sources.map((s, i) => (
          <SourceCard key={s.chunk_uuid || `${s.document_id}-${s.chunk_index}-${i}`} source={s} index={i + 1} />
        ))}
      </div>
    </div>
  )
}

function SourceCard({ source, index }: { source: DocumentSource; index: number }) {
  const snippet = (source.snippet || '').trim()
  const preview = snippet.length > 220 ? snippet.slice(0, 220) + '…' : snippet
  const score =
    typeof source.score === 'number' && Number.isFinite(source.score)
      ? source.score.toFixed(2)
      : null

  return (
    <a
      href={source.document_id ? `/dashboard/documents?doc=${source.document_id}` : '#'}
      className="group block rounded-lg border p-3 transition-colors hover:bg-black/5 focus:outline-none focus:ring-2 focus:ring-blue-400"
      style={{
        background: 'var(--ec-surface-2, #f5f2ef)',
        borderColor: 'var(--ec-card-border, rgba(0,0,0,0.08))',
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <div
          className="flex min-w-0 items-center gap-1.5 text-[11px] font-medium"
          style={{ color: 'var(--ec-text-muted)' }}
        >
          <span
            className="flex h-4 w-4 items-center justify-center rounded-full text-[9px]"
            style={{
              background: 'var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          >
            {index}
          </span>
          {(() => {
            const Icon = SOURCE_ICON[source.source_type ?? 'document'] ?? FileText
            return <Icon size={11} />
          })()}
          <span className="truncate">{source.filename || 'Untitled document'}</span>
        </div>
        {score && (
          <span
            className="shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium"
            style={{
              background: 'var(--ec-card-border)',
              color: 'var(--ec-text-muted)',
            }}
            title="Hybrid relevance score (dense + BM25)"
          >
            {score}
          </span>
        )}
      </div>
      {preview && (
        <p
          className="mt-1.5 text-xs leading-relaxed"
          style={{ color: 'var(--ec-text, #333)' }}
        >
          {preview}
        </p>
      )}
    </a>
  )
}
