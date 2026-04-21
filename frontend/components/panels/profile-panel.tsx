"use client"

/**
 * ProfilePanelContent — contents of the Profile slide panel.
 *
 * Shows the signed-in user's headline info (display name / email /
 * timezone) plus a few roll-up stats (active goals, protected values,
 * ESL approval rate). Full editing lives on /dashboard/profile.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, Mail, Clock, Heart, Target, ShieldCheck } from "lucide-react"
import { api, type UserProfile } from "@/lib/api"
import { useAuth } from "@/hooks/useAuth"


interface Props {
  onClose: () => void
}


export function ProfilePanelContent({ onClose }: Props) {
  const { user } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.profile.get()
      .then(setProfile)
      .catch(e => setErr(e instanceof Error ? e.message : 'Could not load profile'))
  }, [])

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }
  if (profile === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  const initials = (profile.display_name || profile.email || user?.email || 'U')
    .split(/[\s@]/)[0]
    .substring(0, 2)
    .toUpperCase()

  const apctPct = profile.stats
    ? Math.round((profile.stats.approval_rate > 1 ? profile.stats.approval_rate : profile.stats.approval_rate * 100))
    : null

  return (
    <div className="space-y-5">
      {/* Identity header */}
      <div className="flex items-start gap-3">
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center text-lg font-semibold shrink-0"
          style={{ background: "var(--ec-text)", color: "var(--ec-card-bg)" }}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <p className="text-base font-semibold truncate" style={{ color: "var(--ec-text)" }}>
            {profile.display_name || profile.email.split('@')[0]}
          </p>
          <p className="text-xs flex items-center gap-1.5 mt-0.5 truncate" style={{ color: "var(--ec-text-muted)" }}>
            <Mail size={11} />
            <span className="truncate">{profile.email}</span>
          </p>
          {profile.timezone && (
            <p className="text-xs flex items-center gap-1.5 mt-0.5" style={{ color: "var(--ec-text-subtle)" }}>
              <Clock size={11} />
              {profile.timezone}
            </p>
          )}
        </div>
      </div>

      {/* Stats grid */}
      {profile.stats && (
        <div className="grid grid-cols-3 gap-2">
          <div
            className="p-3 rounded-xl"
            style={{ background: "var(--ec-card-bg)", border: "1px solid var(--ec-card-border)" }}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Target size={11} style={{ color: "#4a7c59" }} />
              <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--ec-text-subtle)" }}>
                Goals
              </p>
            </div>
            <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--ec-text)" }}>
              {profile.stats.goals_count}
            </p>
          </div>
          <div
            className="p-3 rounded-xl"
            style={{ background: "var(--ec-card-bg)", border: "1px solid var(--ec-card-border)" }}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Heart size={11} style={{ color: "#4a7c59" }} />
              <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--ec-text-subtle)" }}>
                Values
              </p>
            </div>
            <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--ec-text)" }}>
              {profile.stats.values_count}
            </p>
          </div>
          <div
            className="p-3 rounded-xl"
            style={{ background: "var(--ec-card-bg)", border: "1px solid var(--ec-card-border)" }}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <ShieldCheck size={11} style={{ color: "#4a7c59" }} />
              <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--ec-text-subtle)" }}>
                ESL
              </p>
            </div>
            <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--ec-text)" }}>
              {apctPct !== null ? `${apctPct}%` : "—"}
            </p>
          </div>
        </div>
      )}

      <div className="pt-3 mt-3 border-t text-center space-x-4" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/profile"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Edit profile <ArrowRight size={11} />
        </Link>
        <Link
          href="/dashboard/settings"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-subtle)" }}
        >
          Settings
        </Link>
      </div>
    </div>
  )
}
