'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, FileText } from 'lucide-react'

interface ArtifactCardProps {
  title: string
  children: React.ReactNode
}

export function ArtifactCard({ title, children }: ArtifactCardProps) {
  const [open, setOpen] = useState(true)

  return (
    <div
      className="my-3 rounded-xl overflow-hidden"
      style={{
        border: '1px solid var(--ec-card-border)',
        background: 'var(--ec-card-bg)',
        boxShadow: 'var(--ec-card-shadow)',
      }}
    >
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-black/[0.03]"
        style={{ borderBottom: open ? '1px solid var(--ec-card-border)' : 'none' }}
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <FileText size={13} style={{ color: '#4A7C59' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--ec-text)' }}>
            {title}
          </span>
        </div>
        {open
          ? <ChevronUp size={14} style={{ color: 'var(--ec-text-subtle)' }} />
          : <ChevronDown size={14} style={{ color: 'var(--ec-text-subtle)' }} />
        }
      </button>
      {open && (
        <div className="px-4 py-3 chat-prose" style={{ fontSize: '0.85rem' }}>
          {children}
        </div>
      )}
    </div>
  )
}
