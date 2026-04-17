"use client"

/**
 * NotificationsPanelContent — contents of the Notifications slide panel.
 *
 * Unread-first list with inline "mark read" / "mark all read" affordances.
 * No destructive deletes here — keep it simple and non-scary.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, Bell, Check, CheckCheck } from "lucide-react"
import { api, type Notification } from "@/lib/api"


interface Props {
  onClose: () => void
}


function formatWhen(iso: string): string {
  const d = new Date(iso)
  const diffMs = Date.now() - d.getTime()
  const mins = Math.round(diffMs / 60_000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}


export function NotificationsPanelContent({ onClose }: Props) {
  const [notifs, setNotifs] = useState<Notification[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    api.notifications.list()
      .then(r => setNotifs(r.notifications))
      .catch(e => setErr(e instanceof Error ? e.message : 'Could not load notifications'))
  }

  useEffect(() => { load() }, [])

  const markOne = async (id: string) => {
    // Optimistic
    setNotifs(prev => prev?.map(n => n.id === id ? { ...n, read: true } : n) ?? null)
    try {
      await api.notifications.markRead(id)
    } catch {
      load()
    }
  }

  const markAll = async () => {
    if (busy) return
    setBusy(true)
    const prevList = notifs
    setNotifs(prev => prev?.map(n => ({ ...n, read: true })) ?? null)
    try {
      await api.notifications.markAllRead()
    } catch {
      setNotifs(prevList)
    } finally {
      setBusy(false)
    }
  }

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }
  if (notifs === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  const unread = notifs.filter(n => !n.read)
  const read = notifs.filter(n => n.read)

  if (notifs.length === 0) {
    return (
      <div className="text-center py-10">
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
          style={{ background: "var(--ec-surface-2)" }}
        >
          <Bell size={18} style={{ color: "var(--ec-text-muted)" }} />
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--ec-text)" }}>No notifications</p>
        <p className="text-xs" style={{ color: "var(--ec-text-muted)" }}>
          You&apos;re all caught up.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Summary + mark all read */}
      <div className="flex items-center gap-3">
        <span className="text-sm" style={{ color: "var(--ec-text)" }}>
          <span className="font-semibold">{unread.length}</span>
          <span style={{ color: "var(--ec-text-muted)" }}> unread</span>
        </span>
        {unread.length > 0 && (
          <button
            onClick={markAll}
            disabled={busy}
            className="ml-auto inline-flex items-center gap-1.5 text-xs h-7 px-3 rounded-lg transition-colors hover:bg-[rgba(0,0,0,0.05)] disabled:opacity-50"
            style={{ color: "var(--ec-text-muted)" }}
          >
            <CheckCheck size={12} />
            {busy ? "Marking…" : "Mark all read"}
          </button>
        )}
      </div>

      {/* Unread first */}
      {unread.length > 0 && (
        <div className="space-y-1.5">
          {unread.map(n => (
            <div
              key={n.id}
              className="group flex items-start gap-2.5 p-3 rounded-xl"
              style={{
                background: "rgba(74,124,89,0.04)",
                border: "1px solid rgba(74,124,89,0.18)",
              }}
            >
              <span
                className="mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full"
                style={{ background: "#4a7c59" }}
                aria-label="Unread"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate" style={{ color: "var(--ec-text)" }}>
                  {n.title}
                </p>
                <p className="text-xs mt-0.5 line-clamp-2" style={{ color: "var(--ec-text-muted)" }}>
                  {n.message}
                </p>
                <p className="text-[10px] mt-1" style={{ color: "var(--ec-text-subtle)" }}>
                  {formatWhen(n.created_at)}
                </p>
              </div>
              <button
                onClick={() => markOne(n.id)}
                className="shrink-0 w-6 h-6 rounded-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[rgba(0,0,0,0.06)]"
                aria-label="Mark as read"
                title="Mark as read"
              >
                <Check size={12} style={{ color: "var(--ec-text-muted)" }} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Read, collapsed by default — show top 5 */}
      {read.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-2 px-1" style={{ color: "var(--ec-text-subtle)" }}>
            Earlier
          </p>
          <div className="space-y-1">
            {read.slice(0, 5).map(n => (
              <div
                key={n.id}
                className="flex items-start gap-2.5 p-2 rounded-lg"
                style={{ color: "var(--ec-text-muted)" }}
              >
                <Bell size={11} className="mt-1 shrink-0" style={{ color: "var(--ec-text-subtle)" }} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs truncate">{n.title}</p>
                  <p className="text-[10px]" style={{ color: "var(--ec-text-subtle)" }}>
                    {formatWhen(n.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="pt-3 mt-3 border-t text-center" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/notifications"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          All notifications <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  )
}
