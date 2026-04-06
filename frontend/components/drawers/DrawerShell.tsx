'use client'

import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

interface DrawerShellProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  footer?: React.ReactNode
}

export function DrawerShell({ open, onClose, title, children, footer }: DrawerShellProps) {
  return (
    <Dialog.Root open={open} onOpenChange={v => { if (!v) onClose() }}>
      <Dialog.Portal>
        {/* Overlay */}
        <Dialog.Overlay
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
        />
        {/* Panel */}
        <Dialog.Content
          className="fixed right-0 top-0 z-50 h-full flex flex-col shadow-2xl
            w-full sm:w-[480px]
            data-[state=open]:animate-in data-[state=closed]:animate-out
            data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right
            duration-200"
          style={{ background: 'var(--ec-card-bg)', borderLeft: '1px solid var(--ec-card-border)' }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-5 py-4 shrink-0 border-b"
            style={{ borderColor: 'var(--ec-card-border)' }}
          >
            <Dialog.Title className="text-sm font-semibold" style={{ color: 'var(--ec-text)' }}>
              {title}
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-black/6"
                aria-label="Close"
              >
                <X size={16} style={{ color: 'var(--ec-text-subtle)' }} />
              </button>
            </Dialog.Close>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {children}
          </div>

          {/* Sticky footer */}
          {footer && (
            <div
              className="shrink-0 px-5 py-3 border-t flex items-center gap-2"
              style={{ borderColor: 'var(--ec-card-border)' }}
            >
              {footer}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
