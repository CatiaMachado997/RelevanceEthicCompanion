"use client"

/**
 * Command Palette (⌘K / Ctrl+K)
 *
 * Universal keyboard-first entry point. Searches the user's conversations
 * and folders by name, plus a fixed set of quick actions (new chat, open
 * Settings / Integrations, search semantic memory).
 *
 * Mount once per authenticated layout. It attaches its own global keydown
 * listener and owns its open/closed state.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import {
  Search, MessageSquare, Folder as FolderIcon, Plus, Settings, Plug,
  ArrowRight, Brain, Target, CheckSquare, FolderOpen, Shield,
  Eye, Bell, FileText, UserCircle,
} from "lucide-react"
import { api, type Folder, type Goal, type Task, type Document } from "@/lib/api"

interface Conversation {
  id: string
  title: string
  folder_id: string | null
  updated_at: string
}

type ResultKind =
  | "conversation"
  | "folder"
  | "action"
  | "semantic"
  | "goal"
  | "task"
  | "document"

interface Result {
  kind: ResultKind
  id: string
  label: string
  sublabel?: string
  icon: React.ReactNode
  run: () => void
}


export function CommandPalette() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [cursor, setCursor] = useState(0)

  // Shared query cache — same keys the sidebar uses, so no duplicate fetches
  const { data: convData } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.chat.conversations.list(),
  })
  const { data: folderData } = useQuery({
    queryKey: ["folders"],
    queryFn: () => api.folders.list(),
  })
  // Active goals + open tasks + ready documents are the items most worth
  // surfacing in the palette. Status filters here mirror what the
  // dedicated listing pages show by default.
  const { data: goalData } = useQuery({
    queryKey: ["goals", "active"],
    queryFn: () => api.goals.list("active"),
  })
  const { data: taskData } = useQuery({
    queryKey: ["tasks", "open"],
    queryFn: () => api.tasks.list(),
  })
  const { data: docData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.documents.list(),
  })
  const conversations: Conversation[] = convData?.conversations ?? []
  const folders: Folder[] = folderData?.folders ?? []
  const goals: Goal[] = goalData?.goals ?? []
  const tasks: Task[] = Array.isArray(taskData) ? taskData : []
  const documents: Document[] = Array.isArray(docData) ? docData : []

  const inputRef = useRef<HTMLInputElement>(null)

  // ─── Global keybinding: ⌘K / Ctrl+K opens; Esc closes ────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isMod = e.metaKey || e.ctrlKey
      if (isMod && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen(prev => !prev)
      } else if (e.key === "Escape" && open) {
        setOpen(false)
      }
    }
    const onEvent = () => setOpen(true)
    window.addEventListener("keydown", onKey)
    window.addEventListener("ec:open-palette", onEvent)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener("ec:open-palette", onEvent)
    }
  }, [open])

  // ─── Reset query/cursor and autofocus each time the palette opens ─────
  // Intentional synchronous setState — resets query/cursor whenever the
  // palette is reopened. Runs at most once per open transition.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!open) return
    setQuery("")
    setCursor(0)
    requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])
  /* eslint-enable react-hooks/set-state-in-effect */

  const close = useCallback(() => setOpen(false), [])

  // ─── Build result set from query ─────────────────────────────────────
  const results: Result[] = useMemo(() => {
    const q = query.trim().toLowerCase()
    const out: Result[] = []

    // Quick actions always appear first when query is empty; otherwise
    // only those that partially match.
    const actions: Result[] = [
      {
        kind: "action", id: "new-chat",
        label: "New chat", sublabel: "Start a fresh conversation",
        icon: <Plus size={14} />,
        run: () => { router.push("/dashboard/chat"); close() },
      },
      {
        kind: "action", id: "settings",
        label: "Settings", sublabel: "Preferences, privacy, relevance tuning",
        icon: <Settings size={14} />,
        run: () => { router.push("/dashboard/settings"); close() },
      },
      {
        kind: "action", id: "integrations",
        label: "Integrations", sublabel: "Connect calendars, docs, email",
        icon: <Plug size={14} />,
        run: () => { router.push("/dashboard/integrations"); close() },
      },
      {
        kind: "action", id: "goals-panel",
        label: "Show goals", sublabel: "Open goals in a side panel",
        icon: <Target size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "goals", title: "Your goals" },
          }))
        },
      },
      {
        kind: "action", id: "tasks-panel",
        label: "Show tasks", sublabel: "Open tasks in a side panel",
        icon: <CheckSquare size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "tasks", title: "Your tasks" },
          }))
        },
      },
      {
        kind: "action", id: "projects-panel",
        label: "Show projects", sublabel: "Active projects with progress",
        icon: <FolderOpen size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "projects", title: "Your projects" },
          }))
        },
      },
      {
        kind: "action", id: "values-panel",
        label: "Show values", sublabel: "Boundaries ESL is protecting",
        icon: <Shield size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "values", title: "Your values" },
          }))
        },
      },
      {
        kind: "action", id: "transparency-panel",
        label: "Show transparency", sublabel: "Recent ESL decisions & vetoes",
        icon: <Eye size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "transparency", title: "ESL transparency" },
          }))
        },
      },
      {
        kind: "action", id: "notifications-panel",
        label: "Show notifications", sublabel: "Unread activity & alerts",
        icon: <Bell size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "notifications", title: "Notifications" },
          }))
        },
      },
      {
        kind: "action", id: "documents-panel",
        label: "Show documents", sublabel: "Uploaded files & chunks",
        icon: <FileText size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "documents", title: "Your documents" },
          }))
        },
      },
      {
        kind: "action", id: "profile-panel",
        label: "Show profile", sublabel: "Your identity & stats",
        icon: <UserCircle size={14} />,
        run: () => {
          close()
          window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "profile", title: "Your profile" },
          }))
        },
      },
    ]
    for (const a of actions) {
      if (!q || a.label.toLowerCase().includes(q) || a.sublabel?.toLowerCase().includes(q)) {
        out.push(a)
      }
    }

    // Folders
    for (const f of folders) {
      if (!q || f.name.toLowerCase().includes(q)) {
        out.push({
          kind: "folder",
          id: f.id,
          label: f.name,
          sublabel: "Folder",
          icon: <FolderIcon size={14} style={{ color: f.color ?? undefined }} />,
          run: () => {
            // No folder detail route yet; route to chat and let sidebar show it.
            router.push("/dashboard/chat")
            close()
          },
        })
      }
    }

    // Conversations — filter by title
    for (const c of conversations) {
      if (!q || c.title.toLowerCase().includes(q)) {
        out.push({
          kind: "conversation",
          id: c.id,
          label: c.title || "Untitled",
          sublabel: new Date(c.updated_at).toLocaleDateString(),
          icon: <MessageSquare size={14} />,
          run: () => { router.push(`/dashboard/chat/${c.id}`); close() },
        })
      }
    }

    // Goals — filter by title or description
    for (const g of goals) {
      const haystack = (g.title + " " + (g.description ?? "")).toLowerCase()
      if (!q || haystack.includes(q)) {
        out.push({
          kind: "goal",
          id: g.id,
          label: g.title,
          sublabel: "Goal",
          icon: <Target size={14} />,
          run: () => { router.push("/dashboard/goals"); close() },
        })
      }
    }

    // Tasks — filter by title (skip completed/cancelled to keep the list useful)
    for (const t of tasks) {
      if (t.status === "done" || t.status === "cancelled") continue
      const haystack = (t.title + " " + (t.description ?? "")).toLowerCase()
      if (!q || haystack.includes(q)) {
        out.push({
          kind: "task",
          id: t.id,
          label: t.title,
          sublabel: t.status === "in_progress" ? "Task — in progress" : "Task",
          icon: <CheckSquare size={14} />,
          run: () => { router.push("/dashboard/tasks"); close() },
        })
      }
    }

    // Documents — filter by filename
    for (const d of documents) {
      if (!q || d.filename.toLowerCase().includes(q)) {
        out.push({
          kind: "document",
          id: d.id,
          label: d.filename,
          sublabel: "Document",
          icon: <FileText size={14} />,
          run: () => { router.push("/dashboard/documents"); close() },
        })
      }
    }

    // Semantic memory — only offered when the user has typed a query.
    // This is a hint card; selecting it runs a real search against /api/search.
    if (q) {
      out.push({
        kind: "semantic",
        id: "semantic-search",
        label: `Search memory for "${query.trim()}"`,
        sublabel: "Semantic search across your history",
        icon: <Brain size={14} />,
        run: async () => {
          close()
          router.push(`/dashboard/search?q=${encodeURIComponent(query.trim())}`)
        },
      })
    }

    return out.slice(0, 30)
  }, [query, folders, conversations, goals, tasks, documents, router, close])

  // Clamp cursor if results shrink. Intentional synchronous setState —
  // produces at most one extra render when results shorten past the cursor.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (cursor >= results.length) setCursor(Math.max(0, results.length - 1))
  }, [results.length, cursor])
  /* eslint-enable react-hooks/set-state-in-effect */

  const onKeyDownInput = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setCursor(c => Math.min(c + 1, results.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setCursor(c => Math.max(c - 1, 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      const r = results[cursor]
      if (r) r.run()
    }
  }

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-label="Command palette"
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[18vh] px-4"
      onClick={close}
    >
      {/* Backdrop */}
      <div className="absolute inset-0" style={{ background: "rgba(17,17,17,0.4)" }} />

      {/* Panel */}
      <div
        onClick={e => e.stopPropagation()}
        className="relative w-full max-w-[560px] rounded-2xl overflow-hidden"
        style={{
          background: "var(--ec-card-bg)",
          border: "1px solid var(--ec-card-border)",
          boxShadow: "0 10px 40px rgba(0,0,0,0.2)",
        }}
      >
        {/* Search input */}
        <div
          className="flex items-center gap-3 px-4 h-12 border-b"
          style={{ borderColor: "var(--ec-card-border)" }}
        >
          <Search size={16} style={{ color: "var(--ec-text-subtle)" }} />
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setCursor(0) }}
            onKeyDown={onKeyDownInput}
            placeholder="Search conversations, folders, or type a command…"
            className="flex-1 bg-transparent outline-none text-sm"
            style={{ color: "var(--ec-text)" }}
          />
          <kbd
            className="px-1.5 py-0.5 text-[10px] font-medium rounded"
            style={{ background: "var(--ec-surface-2)", color: "var(--ec-text-muted)" }}
          >
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto py-1">
          {results.length === 0 ? (
            <p className="text-xs px-4 py-6 text-center" style={{ color: "var(--ec-text-subtle)" }}>
              No matches. Try a different search.
            </p>
          ) : (
            results.map((r, i) => {
              const active = i === cursor
              return (
                <button
                  key={r.kind + ":" + r.id}
                  onClick={() => r.run()}
                  onMouseEnter={() => setCursor(i)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors"
                  style={{
                    background: active ? "var(--ec-sidebar-active)" : "transparent",
                    color: "var(--ec-text)",
                  }}
                >
                  <span
                    className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: "var(--ec-surface-2)", color: "var(--ec-text-muted)" }}
                  >
                    {r.icon}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block truncate">{r.label}</span>
                    {r.sublabel && (
                      <span className="block text-xs truncate" style={{ color: "var(--ec-text-subtle)" }}>
                        {r.sublabel}
                      </span>
                    )}
                  </span>
                  {active && <ArrowRight size={13} style={{ color: "var(--ec-text-muted)" }} />}
                </button>
              )
            })
          )}
        </div>

        {/* Footer hint */}
        <div
          className="flex items-center justify-between px-4 py-2 border-t text-[10px]"
          style={{ borderColor: "var(--ec-card-border)", color: "var(--ec-text-subtle)" }}
        >
          <span>
            <kbd className="px-1 py-0.5 rounded" style={{ background: "var(--ec-surface-2)" }}>↑↓</kbd>{" "}
            navigate
            <span className="mx-2">·</span>
            <kbd className="px-1 py-0.5 rounded" style={{ background: "var(--ec-surface-2)" }}>↵</kbd>{" "}
            open
          </span>
          <span>
            <kbd className="px-1 py-0.5 rounded" style={{ background: "var(--ec-surface-2)" }}>⌘K</kbd>{" "}
            to toggle
          </span>
        </div>
      </div>
    </div>
  )
}
