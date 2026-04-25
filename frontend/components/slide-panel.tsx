"use client"

/**
 * SlidePanel — right-side drawer
 *
 * A generic contextual drawer that slides in from the right. Used to show
 * page content (goals, tasks, transparency log, etc.) alongside the chat
 * without navigating away.
 *
 * Usage:
 *   <SlidePanel open={open} onClose={…} title="Goals">
 *     <GoalsPanelContent />
 *   </SlidePanel>
 *
 * Or trigger-by-event from anywhere (e.g. an inline card in chat):
 *   window.dispatchEvent(new CustomEvent('ec:open-panel', {
 *     detail: { name: 'goals', title: 'Your goals' }
 *   }))
 * and mount <SlidePanelHost /> once at the layout level.
 */

import { useCallback, useEffect, useRef } from "react"
import { X } from "lucide-react"


interface SlidePanelProps {
  open: boolean
  onClose: () => void
  title?: string
  /** Width in px or any CSS length. Default 440px on desktop, full on mobile. */
  width?: string
  children: React.ReactNode
}

// Selector matching everything Tab can reach.
// Excludes negative tabindex and disabled controls.
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",")

function getFocusable(root: HTMLElement): HTMLElement[] {
  return Array.from(
    root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => !el.hasAttribute("aria-hidden"))
}

export function SlidePanel({ open, onClose, title, width = "440px", children }: SlidePanelProps) {
  const panelRef = useRef<HTMLElement | null>(null)

  // Esc to close
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  // Lock body scroll while open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = prev }
  }, [open])

  // Focus trap: capture the previously focused element when the panel
  // opens, move focus inside, and restore it when the panel closes.
  // Tab/Shift-Tab cycle inside the panel — Esc/backdrop click still close.
  useEffect(() => {
    if (!open) return
    const panel = panelRef.current
    if (!panel) return

    const previouslyFocused = document.activeElement as HTMLElement | null
    const focusables = getFocusable(panel)
    ;(focusables[0] ?? panel).focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return
      const items = getFocusable(panel)
      if (items.length === 0) {
        e.preventDefault()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }

    panel.addEventListener("keydown", onKey)
    return () => {
      panel.removeEventListener("keydown", onKey)
      // Restore focus to whatever opened the panel — only if it's still
      // in the document (could have unmounted during the panel's life).
      if (previouslyFocused && document.contains(previouslyFocused)) {
        previouslyFocused.focus()
      }
    }
  }, [open])

  return (
    <>
      {/* Backdrop — only the area left of the panel, and only on mobile/tablet.
          On wide screens we leave the chat visible and interactable behind. */}
      <div
        aria-hidden={!open}
        onClick={onClose}
        className={`fixed inset-0 z-[90] transition-opacity duration-200 lg:hidden ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        style={{ background: "rgba(17,17,17,0.35)" }}
      />

      {/* Panel */}
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title ?? "Detail panel"}
        aria-hidden={!open}
        // tabIndex=-1 so the panel itself can receive programmatic focus
        // when it has no focusable children yet (initial focus fallback).
        tabIndex={-1}
        className={`fixed top-0 right-0 bottom-0 z-[95] flex flex-col transition-transform duration-250 ease-out shadow-2xl outline-none`}
        style={{
          width: `min(100vw, ${width})`,
          background: "var(--ec-card-bg)",
          borderLeft: "1px solid var(--ec-card-border)",
          transform: open ? "translateX(0)" : "translateX(100%)",
        }}
      >
        {/* Header */}
        <header
          className="flex items-center gap-3 h-14 px-5 shrink-0 border-b"
          style={{ borderColor: "var(--ec-card-border)" }}
        >
          <h2 className="flex-1 text-sm font-semibold truncate" style={{ color: "var(--ec-text)" }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close panel"
            className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-[rgba(0,0,0,0.05)]"
          >
            <X size={15} style={{ color: "var(--ec-text-muted)" }} />
          </button>
        </header>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </>
  )
}


// ─── Host: event-driven panel manager ───────────────────────────────────
//
// Mount <SlidePanelHost /> once in the dashboard layout. Any component
// can then dispatch `ec:open-panel` with a name payload to open it.
// Keeps panel state out of every consumer.

import { useState } from "react"
import { GoalsPanelContent } from "@/components/panels/goals-panel"
import { TasksPanelContent } from "@/components/panels/tasks-panel"
import { ProjectsPanelContent } from "@/components/panels/projects-panel"
import { ValuesPanelContent } from "@/components/panels/values-panel"
import { TransparencyPanelContent } from "@/components/panels/transparency-panel"
import { NotificationsPanelContent } from "@/components/panels/notifications-panel"
import { DocumentsPanelContent } from "@/components/panels/documents-panel"
import { ProfilePanelContent } from "@/components/panels/profile-panel"

interface OpenPanelDetail {
  name: "goals" | "tasks" | "projects" | "values" | "transparency" | "notifications" | "documents" | "profile" | string
  title?: string
}

export function SlidePanelHost() {
  const [state, setState] = useState<{ open: boolean; name: string | null; title: string }>({
    open: false,
    name: null,
    title: "",
  })

  const close = useCallback(() => setState(s => ({ ...s, open: false })), [])

  useEffect(() => {
    const onOpen = (e: Event) => {
      const detail = (e as CustomEvent<OpenPanelDetail>).detail
      if (!detail?.name) return
      setState({ open: true, name: detail.name, title: detail.title ?? detail.name })
    }
    window.addEventListener("ec:open-panel", onOpen)
    return () => window.removeEventListener("ec:open-panel", onOpen)
  }, [])

  const content = (() => {
    switch (state.name) {
      case "goals":         return <GoalsPanelContent         onClose={close} />
      case "tasks":         return <TasksPanelContent         onClose={close} />
      case "projects":      return <ProjectsPanelContent      onClose={close} />
      case "values":        return <ValuesPanelContent        onClose={close} />
      case "transparency":  return <TransparencyPanelContent  onClose={close} />
      case "notifications": return <NotificationsPanelContent onClose={close} />
      case "documents":     return <DocumentsPanelContent     onClose={close} />
      case "profile":       return <ProfilePanelContent       onClose={close} />
      default: return <p className="text-sm" style={{ color: "var(--ec-text-muted)" }}>Unknown panel: {state.name}</p>
    }
  })()

  return (
    <SlidePanel open={state.open} onClose={close} title={state.title}>
      {content}
    </SlidePanel>
  )
}
