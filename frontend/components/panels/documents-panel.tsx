"use client"

/**
 * DocumentsPanelContent — contents of the Documents slide panel.
 *
 * Read-oriented list of uploaded documents with processing status badges.
 * Upload flow stays on /dashboard/documents — the panel is for glancing.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  ArrowRight, FileText, Loader2, AlertTriangle, CheckCircle,
  Upload,
} from "lucide-react"
import { api, type Document } from "@/lib/api"


interface Props {
  onClose: () => void
}


function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}


const STATUS_META: Record<Document['status'], { label: string; icon: React.ReactNode; color: string; bg: string }> = {
  ready:      { label: "Ready",      icon: <CheckCircle size={10} />, color: "#4a7c59", bg: "rgba(74,124,89,0.10)" },
  processing: { label: "Processing", icon: <Loader2 size={10} className="animate-spin" />, color: "#9B7A3D", bg: "rgba(155,122,61,0.10)" },
  failed:     { label: "Failed",     icon: <AlertTriangle size={10} />, color: "#B04A3A", bg: "rgba(176,74,58,0.10)" },
}


export function DocumentsPanelContent({ onClose }: Props) {
  const [docs, setDocs] = useState<Document[] | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.documents.list()
      .then(res => setDocs(Array.isArray(res) ? res : []))
      .catch(e => setErr(e instanceof Error ? e.message : 'Could not load documents'))
  }, [])

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }
  if (docs === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  if (docs.length === 0) {
    return (
      <div className="text-center py-10">
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
          style={{ background: "var(--ec-surface-2)" }}
        >
          <FileText size={18} style={{ color: "var(--ec-text-muted)" }} />
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--ec-text)" }}>No documents yet</p>
        <p className="text-xs mb-4 px-4" style={{ color: "var(--ec-text-muted)" }}>
          Upload files and the companion can reference them during chat.
        </p>
        <Link
          href="/dashboard/documents"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg text-xs font-medium"
          style={{ background: "#4a7c59", color: "#ffffff" }}
        >
          <Upload size={13} />
          Upload first document
        </Link>
      </div>
    )
  }

  const processing = docs.filter(d => d.status === 'processing').length
  const ready = docs.filter(d => d.status === 'ready').length

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-3 text-xs">
        <span className="font-medium" style={{ color: "var(--ec-text)" }}>
          {ready} ready
        </span>
        {processing > 0 && (
          <span className="flex items-center gap-1" style={{ color: "#9B7A3D" }}>
            <Loader2 size={10} className="animate-spin" />
            {processing} processing
          </span>
        )}
        <Link
          href="/dashboard/documents"
          onClick={onClose}
          className="ml-auto inline-flex items-center gap-1 text-xs h-7 px-2.5 rounded-lg transition-colors hover:bg-[rgba(0,0,0,0.05)]"
          style={{ color: "var(--ec-text-muted)" }}
        >
          <Upload size={11} /> Upload
        </Link>
      </div>

      <div className="space-y-1.5">
        {docs.slice(0, 20).map(d => {
          const meta = STATUS_META[d.status]
          return (
            <div
              key={d.id}
              className="flex items-start gap-2.5 p-2.5 rounded-xl"
              style={{ border: "1px solid var(--ec-card-border)" }}
            >
              <FileText size={13} className="mt-0.5 shrink-0" style={{ color: "var(--ec-text-muted)" }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate" style={{ color: "var(--ec-text)" }}>
                  {d.filename}
                </p>
                <div className="flex items-center gap-2 mt-0.5 text-[11px]" style={{ color: "var(--ec-text-subtle)" }}>
                  <span>{formatSize(d.size_bytes)}</span>
                  {d.chunk_count > 0 && <span>·</span>}
                  {d.chunk_count > 0 && <span>{d.chunk_count} chunks</span>}
                </div>
                {d.status === 'failed' && d.error_message && (
                  <p className="text-[10px] mt-1" style={{ color: "#B04A3A" }}>
                    {d.error_message}
                  </p>
                )}
              </div>
              <span
                className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                style={{ background: meta.bg, color: meta.color }}
              >
                {meta.icon}
                {meta.label}
              </span>
            </div>
          )
        })}
      </div>

      <div className="pt-3 border-t text-center" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/documents"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Manage documents <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  )
}
