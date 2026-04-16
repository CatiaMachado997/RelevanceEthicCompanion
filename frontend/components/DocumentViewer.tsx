'use client'

import * as Dialog from '@radix-ui/react-dialog'
import { X, Download } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import { useState, useEffect } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

interface DocumentViewerProps {
  documentId: string | null
  filename: string
  open: boolean
  onClose: () => void
}

export function DocumentViewer({ documentId, filename, open, onClose }: DocumentViewerProps) {
  // Track the URL alongside the documentId it was built for so we can
  // derive the visible URL — avoids a synchronous setState in the effect
  // (which would trigger cascading renders) and also prevents flashing a
  // stale URL when documentId changes.
  const [loaded, setLoaded] = useState<{ id: string; url: string } | null>(null)

  useEffect(() => {
    if (!open || !documentId) return
    let cancelled = false
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (cancelled) return
      const token = session?.access_token ?? ''
      setLoaded({
        id: documentId,
        url: `${API_URL}/api/documents/${documentId}/view?token=${encodeURIComponent(token)}`,
      })
    })
    return () => { cancelled = true }
  }, [open, documentId])

  const viewUrl = open && documentId && loaded?.id === documentId ? loaded.url : null

  return (
    <Dialog.Root open={open} onOpenChange={v => { if (!v) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
        <Dialog.Content
          className="fixed inset-4 z-50 flex flex-col rounded-2xl overflow-hidden shadow-2xl"
          style={{ background: 'var(--ec-card-bg)', border: '1px solid var(--ec-card-border)' }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-5 py-3 shrink-0 border-b"
            style={{ borderColor: 'var(--ec-card-border)' }}
          >
            <Dialog.Title className="text-sm font-semibold truncate max-w-[60%]" style={{ color: 'var(--ec-text)' }}>
              {filename}
            </Dialog.Title>
            <div className="flex items-center gap-2">
              {viewUrl && (
                <a
                  href={viewUrl}
                  download={filename}
                  className="flex items-center gap-1.5 px-3 h-8 rounded-lg text-xs font-medium transition-colors hover:bg-black/5"
                  style={{ color: 'var(--ec-text-subtle)' }}
                >
                  <Download size={13} />
                  Download
                </a>
              )}
              <Dialog.Close asChild>
                <button
                  className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-black/6"
                  aria-label="Close"
                >
                  <X size={16} style={{ color: 'var(--ec-text-subtle)' }} />
                </button>
              </Dialog.Close>
            </div>
          </div>

          {/* PDF iframe */}
          <div className="flex-1 bg-[#525659]">
            {viewUrl ? (
              <iframe
                src={viewUrl}
                className="w-full h-full border-0"
                title={filename}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="w-6 h-6 rounded-full border-2 border-white/20 border-t-white animate-spin" />
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
