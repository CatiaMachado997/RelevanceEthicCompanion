"use client"

/**
 * SlashCommands — in-chat command popover.
 *
 * Watches the chat input and shows a command palette above it when the
 * user types `/` at the start. Supports:
 *   /goals /tasks /projects /values /transparency /docs /notifications
 *   /new-chat      — clears the current chat
 *   /new-folder    — prompts for a folder name and creates it
 *   /clear-input   — clears the text input
 *
 * Keyboard: ↑↓ to navigate, Enter/Tab to select, Esc to close.
 *
 * The component is controlled — the chat page owns the input state and
 * passes it + a few callbacks. This keeps slash-command logic out of the
 * already-large chat page.
 */

import { useEffect, useMemo, useState } from "react"
import {
  Target, CheckSquare, FolderOpen, Shield, Eye, Bell, FileText,
  Plus, FolderPlus, X, Sparkles,
} from "lucide-react"
import { api } from "@/lib/api"
import { parseNaturalDate } from "./parse-natural-date"


export type SlashContext = {
  /** Currently typed value in the chat input */
  input: string
  /** Setter to update the input (to clear / replace the slash command) */
  setInput: (v: string) => void
  /** Clears the chat (forwards to the existing new-chat handler) */
  onClearChat: () => void
  /** Optional free-text args typed after the keyword (creation commands use this) */
  args?: string
}


interface Command {
  id: string
  keyword: string            // the text after the slash, e.g. "goals"
  aliases?: string[]         // alternative keywords
  label: string
  description: string
  icon: React.ReactNode
  /** If true, command accepts free-text args after the keyword. Example:
      `/task Buy milk tomorrow`. Args are passed via ctx.args. */
  takesArgs?: boolean
  /** Placeholder to show when args-accepting command has no args typed yet. */
  argsPlaceholder?: string
  run: (ctx: SlashContext) => void | Promise<void>
}


function openPanel(name: string, title: string) {
  window.dispatchEvent(new CustomEvent("ec:open-panel", { detail: { name, title } }))
}


const COMMANDS: Command[] = [
  {
    id: "goals", keyword: "goals",
    label: "Peek at goals", description: "Open goals in a side panel",
    icon: <Target size={14} />,
    run: ({ setInput }) => { setInput(""); openPanel("goals", "Your goals") },
  },
  {
    id: "tasks", keyword: "tasks",
    label: "Peek at tasks", description: "Open tasks in a side panel",
    icon: <CheckSquare size={14} />,
    run: ({ setInput }) => { setInput(""); openPanel("tasks", "Your tasks") },
  },
  {
    id: "projects", keyword: "projects",
    label: "Peek at projects", description: "Active projects with progress",
    icon: <FolderOpen size={14} />,
    run: ({ setInput }) => { setInput(""); openPanel("projects", "Your projects") },
  },
  {
    id: "values", keyword: "values",
    label: "Peek at values", description: "Boundaries ESL is protecting",
    icon: <Shield size={14} />,
    run: ({ setInput }) => { setInput(""); openPanel("values", "Your values") },
  },
  {
    id: "transparency", keyword: "transparency", aliases: ["esl"],
    label: "Peek at ESL log", description: "Approval rate & recent vetoes",
    icon: <Eye size={14} />,
    run: ({ setInput }) => { setInput(""); openPanel("transparency", "ESL transparency") },
  },
  {
    id: "notifications", keyword: "notifications", aliases: ["notifs"],
    label: "Peek at notifications", description: "Unread activity & alerts",
    icon: <Bell size={14} />,
    run: ({ setInput }) => { setInput(""); openPanel("notifications", "Notifications") },
  },
  {
    id: "docs", keyword: "docs", aliases: ["documents"],
    label: "Peek at documents", description: "Uploaded files & chunks",
    icon: <FileText size={14} />,
    run: ({ setInput }) => { setInput(""); openPanel("documents", "Your documents") },
  },
  {
    id: "new-chat", keyword: "new-chat", aliases: ["new", "reset"],
    label: "New chat", description: "Start a fresh conversation",
    icon: <Plus size={14} />,
    run: ({ setInput, onClearChat }) => { setInput(""); onClearChat() },
  },

  // ─── Creation commands (take free-text args) ──────────────────────
  {
    id: "create-task", keyword: "task",
    label: "New task", description: 'e.g. "/task Buy milk tomorrow"',
    icon: <CheckSquare size={14} />,
    takesArgs: true,
    argsPlaceholder: "Task title — include a date like tomorrow, friday, in 3 days",
    run: async ({ setInput, args }) => {
      const text = (args ?? "").trim()
      if (!text) return
      setInput("")
      const { title, iso } = parseNaturalDate(text)
      if (!title) return
      try {
        await api.tasks.create({
          title,
          priority: 1,
          ...(iso ? { due_date: iso } : {}),
        })
        // Open the tasks panel so the user sees the new task land.
        window.dispatchEvent(new CustomEvent("ec:open-panel", {
          detail: { name: "tasks", title: "Your tasks" },
        }))
      } catch (e) {
        console.error("create task failed", e)
      }
    },
  },
  {
    id: "create-goal", keyword: "goal",
    label: "New goal", description: 'e.g. "/goal Ship MVP by may 30"',
    icon: <Target size={14} />,
    takesArgs: true,
    argsPlaceholder: "Goal title — optionally include a target date",
    run: async ({ setInput, args }) => {
      const text = (args ?? "").trim()
      if (!text) return
      setInput("")
      const { title, iso } = parseNaturalDate(text)
      if (!title) return
      try {
        await api.goals.create({
          title,
          priority: 1,
          ...(iso ? { target_date: iso } : {}),
        })
        window.dispatchEvent(new CustomEvent("ec:open-panel", {
          detail: { name: "goals", title: "Your goals" },
        }))
      } catch (e) {
        console.error("create goal failed", e)
      }
    },
  },
  {
    id: "new-folder", keyword: "folder", aliases: ["new-folder"],
    label: "New folder", description: 'e.g. "/folder Work"',
    icon: <FolderPlus size={14} />,
    takesArgs: true,
    argsPlaceholder: "Folder name",
    run: async ({ setInput, args }) => {
      const name = (args ?? "").trim() || window.prompt("Folder name?")?.trim()
      setInput("")
      if (!name) return
      try {
        await api.folders.create(name)
        window.dispatchEvent(new Event("ec:conversation-created"))
      } catch (e) {
        console.error("create folder failed", e)
      }
    },
  },
  {
    id: "clear", keyword: "clear-input", aliases: ["clear"],
    label: "Clear input", description: "Empty the chat textarea",
    icon: <X size={14} />,
    run: ({ setInput }) => setInput(""),
  },
]


/**
 * Parse the input for a slash command.
 *
 * Two modes:
 *   1. Filter mode — input is `/` or `/<letters>` with NO space yet.
 *      We show the full command list filtered by the typed query.
 *   2. Args mode   — input is `/<keyword> <rest>`. We show only the
 *      matching command with `rest` rendered as live args.
 */
interface SlashParse {
  /** Filter query or keyword (lower-cased). Empty string when input is just "/". */
  keyword: string
  /** Free-text args, or null when no space yet. */
  args: string | null
}

function parseSlashQuery(input: string): SlashParse | null {
  // Filter mode: /xxx with no space
  const filter = input.match(/^\/([a-z-]*)$/i)
  if (filter) return { keyword: filter[1].toLowerCase(), args: null }

  // Args mode: /keyword <space> <rest>
  const args = input.match(/^\/([a-z-]+)\s(.*)$/i)
  if (args) return { keyword: args[1].toLowerCase(), args: args[2] }

  return null
}


interface Props {
  input: string
  setInput: (v: string) => void
  onClearChat: () => void
  /** Register a keydown handler; returns true if the event was consumed. */
  onKeyDownRef?: React.MutableRefObject<((e: KeyboardEvent) => boolean) | null>
}


export function SlashCommands({ input, setInput, onClearChat, onKeyDownRef }: Props) {
  const parsed = parseSlashQuery(input)
  const open = parsed !== null
  const [cursor, setCursor] = useState(0)

  const results = useMemo<Command[]>(() => {
    if (!parsed) return []

    // Args mode — only show the command whose keyword/alias matches exactly
    // (and which declares it accepts args).
    if (parsed.args !== null) {
      const exact = COMMANDS.find(c =>
        c.takesArgs && (
          c.keyword === parsed.keyword ||
          (c.aliases?.includes(parsed.keyword) ?? false)
        )
      )
      return exact ? [exact] : []
    }

    // Filter mode — partial match against keyword/aliases/label
    const q = parsed.keyword
    if (!q) return COMMANDS
    return COMMANDS.filter(c =>
      c.keyword.startsWith(q) ||
      c.aliases?.some(a => a.startsWith(q)) ||
      c.label.toLowerCase().includes(q)
    )
  }, [parsed])

  const argsMode = parsed?.args !== null && parsed?.args !== undefined
  const activeArgs = parsed?.args ?? ""

  useEffect(() => {
    if (cursor >= results.length) setCursor(Math.max(0, results.length - 1))
  }, [results.length, cursor])

  // Expose a keydown handler via ref so the chat page's textarea can intercept
  // arrow keys / Enter / Escape without us owning focus.
  useEffect(() => {
    if (!onKeyDownRef) return
    onKeyDownRef.current = (e: KeyboardEvent) => {
      if (!open) return false
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setCursor(c => Math.min(c + 1, results.length - 1))
        return true
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        setCursor(c => Math.max(c - 1, 0))
        return true
      }
      if (e.key === "Enter" || e.key === "Tab") {
        if (results.length > 0) {
          const cmd = results[cursor]
          // If user hits Enter in args mode, run with args. Otherwise:
          //   - non-args command: run immediately
          //   - args command in filter mode (Tab pressed to accept): expand
          //     into args mode by appending a space, don't run yet.
          if (argsMode) {
            e.preventDefault()
            cmd.run({ input, setInput, onClearChat, args: activeArgs })
            return true
          }
          if (cmd.takesArgs && e.key === "Tab") {
            e.preventDefault()
            setInput(`/${cmd.keyword} `)
            return true
          }
          if (!cmd.takesArgs) {
            e.preventDefault()
            cmd.run({ input, setInput, onClearChat })
            return true
          }
          // Args-taking command + Enter + no args typed yet → expand to args mode
          if (cmd.takesArgs && e.key === "Enter") {
            e.preventDefault()
            setInput(`/${cmd.keyword} `)
            return true
          }
        }
      }
      if (e.key === "Escape") {
        e.preventDefault()
        setInput("")
        return true
      }
      return false
    }
    return () => { if (onKeyDownRef) onKeyDownRef.current = null }
  }, [open, results, cursor, input, setInput, onClearChat, onKeyDownRef, argsMode, activeArgs])

  if (!open) return null

  return (
    <div
      className="absolute bottom-full mb-2 left-0 right-0 z-50 rounded-xl overflow-hidden"
      style={{
        background: "var(--ec-card-bg)",
        border: "1px solid var(--ec-card-border)",
        boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
      }}
      onMouseDown={e => e.preventDefault()}   // prevent blur on textarea
    >
      <div
        className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider border-b"
        style={{ color: "var(--ec-text-subtle)", borderColor: "var(--ec-card-border)" }}
      >
        Slash commands
      </div>

      {results.length === 0 ? (
        <p className="px-3 py-3 text-xs" style={{ color: "var(--ec-text-subtle)" }}>
          No commands match <span className="font-mono">/{parsed?.keyword}{argsMode ? ` ${activeArgs}` : ""}</span>
        </p>
      ) : (
        <div className="max-h-[280px] overflow-y-auto py-1">
          {results.map((c, i) => {
            const active = i === cursor
            // In args mode: show the parsed-date preview right inside the row
            const preview = argsMode && c.takesArgs ? parseNaturalDate(activeArgs) : null

            return (
              <button
                key={c.id}
                onClick={() => {
                  if (argsMode) {
                    c.run({ input, setInput, onClearChat, args: activeArgs })
                  } else if (c.takesArgs) {
                    setInput(`/${c.keyword} `)
                  } else {
                    c.run({ input, setInput, onClearChat })
                  }
                }}
                onMouseEnter={() => setCursor(i)}
                className="w-full flex items-start gap-3 px-3 py-2 text-left text-sm transition-colors"
                style={{
                  background: active ? "var(--ec-sidebar-active)" : "transparent",
                  color: "var(--ec-text)",
                }}
              >
                <span
                  className="mt-0.5 w-6 h-6 rounded-md flex items-center justify-center shrink-0"
                  style={{ background: "var(--ec-surface-2)", color: "var(--ec-text-muted)" }}
                >
                  {c.icon}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="flex items-baseline gap-2">
                    <span className="font-mono text-xs" style={{ color: "var(--ec-text-muted)" }}>
                      /{c.keyword}{c.takesArgs ? " …" : ""}
                    </span>
                    <span className="text-sm truncate">{c.label}</span>
                  </span>
                  {argsMode && preview ? (
                    <span className="block text-[11px] mt-0.5" style={{ color: "var(--ec-text)" }}>
                      {preview.title ? (
                        <>
                          <span className="font-medium">{preview.title}</span>
                          {preview.iso && (
                            <span className="ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px]" style={{ background: "rgba(74,124,89,0.10)", color: "#4a7c59" }}>
                              <Sparkles size={9} />
                              {preview.iso}
                            </span>
                          )}
                        </>
                      ) : (
                        <span style={{ color: "var(--ec-text-subtle)" }}>{c.argsPlaceholder}</span>
                      )}
                    </span>
                  ) : (
                    <span className="block text-[11px] truncate" style={{ color: "var(--ec-text-subtle)" }}>
                      {c.description}
                    </span>
                  )}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
