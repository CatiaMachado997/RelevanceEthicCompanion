"use client"

/**
 * ValuesPanelContent — contents of the Values slide panel.
 *
 * This is the *core* ESL surface: the user's declared boundaries,
 * preferences, topic filters, and time windows. Each value is sacred —
 * we show them prominently grouped by type so the user can see what the
 * companion is actively protecting.
 *
 * Editing stays on /dashboard/values (full form, validation, metadata).
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  ArrowRight, Shield, Heart, Filter, Clock,
} from "lucide-react"
import { api, type UserValue } from "@/lib/api"


interface Props {
  onClose: () => void
}


type ValueType = UserValue['type']


const TYPE_META: Record<ValueType, { label: string; icon: React.ReactNode; color: string }> = {
  boundary:     { label: "Boundaries",    icon: <Shield size={13} />, color: "#B04A3A" },
  preference:   { label: "Preferences",   icon: <Heart  size={13} />, color: "#4a7c59" },
  topic_filter: { label: "Topic filters", icon: <Filter size={13} />, color: "#9B7A3D" },
  time_window:  { label: "Time windows",  icon: <Clock  size={13} />, color: "#4a7c59" },
}

const TYPE_ORDER: ValueType[] = ["boundary", "time_window", "topic_filter", "preference"]


export function ValuesPanelContent({ onClose }: Props) {
  const [values, setValues] = useState<UserValue[] | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.values.list()
      .then(r => setValues(r.values))
      .catch(e => setErr(e instanceof Error ? e.message : 'Could not load values'))
  }, [])

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }
  if (values === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  if (values.length === 0) {
    return (
      <div className="text-center py-10">
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
          style={{ background: "var(--ec-surface-2)" }}
        >
          <Shield size={18} style={{ color: "var(--ec-text-muted)" }} />
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--ec-text)" }}>No values defined</p>
        <p className="text-xs mb-4 px-4" style={{ color: "var(--ec-text-muted)" }}>
          Values are the boundaries ESL enforces on your behalf. The more you define,
          the more the companion can protect you.
        </p>
        <Link
          href="/dashboard/values"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg text-xs font-medium"
          style={{ background: "#4a7c59", color: "#ffffff" }}
        >
          Define your first value <ArrowRight size={13} />
        </Link>
      </div>
    )
  }

  // Group by type
  const groups = new Map<ValueType, UserValue[]>()
  for (const v of values) {
    const arr = groups.get(v.type) ?? []
    arr.push(v)
    groups.set(v.type, arr)
  }
  // Sort each group by priority (high first)
  for (const arr of groups.values()) arr.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))

  return (
    <div className="space-y-5">
      {/* Summary strip */}
      <div
        className="flex items-center gap-2 px-3 py-2.5 rounded-xl"
        style={{
          background: "rgba(74,124,89,0.08)",
          border: "1px solid rgba(74,124,89,0.20)",
        }}
      >
        <Shield size={13} style={{ color: "#4a7c59" }} />
        <span className="text-xs" style={{ color: "#4a7c59" }}>
          <span className="font-semibold">{values.length}</span> {values.length === 1 ? 'value' : 'values'} protected by ESL
        </span>
      </div>

      {TYPE_ORDER.filter(t => groups.has(t)).map(type => {
        const items = groups.get(type)!
        const meta = TYPE_META[type]
        return (
          <div key={type}>
            <div className="flex items-center gap-2 mb-2 px-1">
              <span style={{ color: meta.color }}>{meta.icon}</span>
              <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--ec-text-muted)" }}>
                {meta.label}
              </p>
              <span className="text-[11px] tabular-nums" style={{ color: "var(--ec-text-subtle)" }}>
                {items.length}
              </span>
            </div>
            <div className="space-y-1.5">
              {items.map(v => (
                <div
                  key={v.id}
                  className="flex items-start gap-2.5 p-2.5 rounded-xl"
                  style={{ border: "1px solid var(--ec-card-border)" }}
                >
                  <span
                    className="mt-0.5 shrink-0 w-1 h-4 rounded-full"
                    style={{ background: meta.color }}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm leading-snug" style={{ color: "var(--ec-text)" }}>
                      {v.value}
                    </p>
                    {v.priority >= 2 && (
                      <p className="text-[10px] mt-0.5" style={{ color: "var(--ec-text-subtle)" }}>
                        High priority
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })}

      <div className="pt-3 border-t text-center" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/values"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Manage values <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  )
}
