"use client"

/**
 * TransparencyPanelContent — contents of the Transparency slide panel.
 *
 * Shows the ESL's recent work in a glanceable form: approval rate,
 * counts per outcome, and the most recent vetoes with reasons. This is
 * what "Trust over Engagement" looks like in practice — the companion's
 * reasoning is always legible.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  ArrowRight, ShieldCheck, Ban, Wrench, Eye,
} from "lucide-react"
import { api } from "@/lib/api"


interface Props {
  onClose: () => void
}


interface Report {
  period_days: number
  total_decisions: number
  approved_count: number
  vetoed_count: number
  modified_count: number
  approval_rate: number
  recent_vetoes: Array<{
    action_type: string
    reason: string
    timestamp: string
  }>
  message?: string
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


export function TransparencyPanelContent({ onClose }: Props) {
  const [report, setReport] = useState<Report | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.transparency.report(7)
      .then(r => setReport(r as Report))
      .catch(e => setErr(e instanceof Error ? e.message : 'Could not load transparency report'))
  }, [])

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }
  if (report === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  if (report.total_decisions === 0) {
    return (
      <div className="text-center py-10">
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
          style={{ background: "var(--ec-surface-2)" }}
        >
          <Eye size={18} style={{ color: "var(--ec-text-muted)" }} />
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--ec-text)" }}>No ESL activity yet</p>
        <p className="text-xs mb-4 px-4" style={{ color: "var(--ec-text-muted)" }}>
          Every time the companion acts on your behalf, the Ethical Safeguard
          Layer reviews it. Decisions will show up here.
        </p>
        <Link
          href="/dashboard/transparency"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg text-xs font-medium"
          style={{ background: "#4a7c59", color: "#ffffff" }}
        >
          Open full log <ArrowRight size={13} />
        </Link>
      </div>
    )
  }

  const pct = Math.round((report.approval_rate > 1 ? report.approval_rate : report.approval_rate * 100))

  return (
    <div className="space-y-5">
      {/* Hero stat: approval rate over N days */}
      <div
        className="p-4 rounded-2xl"
        style={{
          background: "rgba(74,124,89,0.08)",
          border: "1px solid rgba(74,124,89,0.20)",
        }}
      >
        <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: "#4a7c59" }}>
          Last {report.period_days} days
        </p>
        <p className="text-3xl font-semibold mt-1 tabular-nums" style={{ color: "var(--ec-text)" }}>
          {pct}%
          <span className="text-sm font-normal ml-2" style={{ color: "var(--ec-text-muted)" }}>approval rate</span>
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--ec-text-muted)" }}>
          {report.total_decisions} {report.total_decisions === 1 ? "decision" : "decisions"} reviewed by ESL
        </p>
      </div>

      {/* Outcome breakdown */}
      <div className="grid grid-cols-3 gap-2">
        <div
          className="p-3 rounded-xl"
          style={{ background: "var(--ec-card-bg)", border: "1px solid var(--ec-card-border)" }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldCheck size={11} style={{ color: "#4a7c59" }} />
            <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--ec-text-subtle)" }}>
              Approved
            </p>
          </div>
          <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--ec-text)" }}>
            {report.approved_count}
          </p>
        </div>
        <div
          className="p-3 rounded-xl"
          style={{ background: "var(--ec-card-bg)", border: "1px solid var(--ec-card-border)" }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <Wrench size={11} style={{ color: "#9B7A3D" }} />
            <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--ec-text-subtle)" }}>
              Modified
            </p>
          </div>
          <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--ec-text)" }}>
            {report.modified_count}
          </p>
        </div>
        <div
          className="p-3 rounded-xl"
          style={{ background: "var(--ec-card-bg)", border: "1px solid var(--ec-card-border)" }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <Ban size={11} style={{ color: "#B04A3A" }} />
            <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--ec-text-subtle)" }}>
              Vetoed
            </p>
          </div>
          <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--ec-text)" }}>
            {report.vetoed_count}
          </p>
        </div>
      </div>

      {/* Recent vetoes — most important for trust */}
      {report.recent_vetoes.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-2 px-1" style={{ color: "var(--ec-text-muted)" }}>
            Recent vetoes
          </p>
          <div className="space-y-1.5">
            {report.recent_vetoes.slice(0, 5).map((v, i) => (
              <div
                key={i}
                className="p-3 rounded-xl"
                style={{
                  background: "rgba(176,74,58,0.04)",
                  border: "1px solid rgba(176,74,58,0.15)",
                }}
              >
                <div className="flex items-start gap-2">
                  <Ban size={11} className="mt-0.5 shrink-0" style={{ color: "#B04A3A" }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium" style={{ color: "#B04A3A" }}>
                      {v.action_type.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--ec-text)" }}>
                      {v.reason}
                    </p>
                    <p className="text-[10px] mt-1" style={{ color: "var(--ec-text-subtle)" }}>
                      {formatWhen(v.timestamp)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="pt-3 border-t text-center" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/transparency"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Full audit log <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  )
}
