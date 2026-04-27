"use client"

/**
 * DashboardHero — time-aware greeting + quick actions.
 *
 * Adds dynamic flavour to the top of the dashboard: a greeting that changes
 * with the hour, a day-of-week line, and three quick-action buttons that
 * open the ⌘K palette / slide panels / chat without navigation.
 */

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { MessageSquare, Target, Search, ArrowRight, Clock, Sparkles } from "lucide-react"
import { useAuth } from "@/hooks/useAuth"
import { contextApi, insightApi, type ContextSnapshot } from "@/lib/api"


function greeting(hour: number): string {
  if (hour < 5) return "Still up"
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
}


export function DashboardHero() {
  const { user } = useAuth()
  const [now, setNow] = useState<Date | null>(null)
  const router = useRouter()

  useEffect(() => {
    // Hydration gate — server-rendered as `null`, populated client-side
    // to avoid SSR/CSR mismatch on the time-aware greeting.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNow(new Date())
    // Re-render every minute so the greeting stays accurate across midnight / hour boundaries.
    const interval = setInterval(() => setNow(new Date()), 60_000)
    return () => clearInterval(interval)
  }, [])

  // Pulled into the hero from the (now-removed) "Today" + "Daily insight"
  // sections below. Kept compact: a single chip for the next event, and
  // one italic line for the insight. Both fail silently if the backend
  // is offline — the hero still works as a greeting.
  const { data: snapshot } = useQuery<ContextSnapshot>({
    queryKey: ["context-snapshot"],
    queryFn: () => contextApi.snapshot(),
    retry: false,
    staleTime: 60_000,
  })
  const { data: insight } = useQuery<{ insight: string; cached: boolean }>({
    queryKey: ["daily-insight"],
    queryFn: () => insightApi.daily(),
    retry: false,
    staleTime: 5 * 60_000,
  })

  const name = user?.email?.split("@")[0] ?? "there"
  const hour = now?.getHours() ?? 0
  const greet = now ? greeting(hour) : "Welcome back"
  const dayLine = now
    ? now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })
    : ""

  const nextEvent = snapshot?.upcoming_events?.[0]
  const nextEventTime = nextEvent?.start_time
    ? new Date(nextEvent.start_time).toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
      })
    : null

  return (
    <section>
      <div className="mb-5">
        <h1
          className="text-2xl sm:text-3xl leading-tight"
          style={{ fontFamily: "var(--font-fraunces)", color: "var(--ec-text)", fontWeight: 400 }}
        >
          {greet}, <em>{name}</em>
        </h1>
        {dayLine && (
          <p className="text-sm mt-1" style={{ color: "var(--ec-text-muted)" }}>
            {dayLine}
          </p>
        )}

        {/* Today's next event — replaces the standalone "Today" card */}
        {nextEvent && (
          <p
            className="mt-2 inline-flex items-center gap-1.5 text-xs"
            style={{ color: "var(--ec-text-muted)" }}
          >
            <Clock size={12} style={{ color: "var(--ec-text-subtle)" }} />
            <span style={{ color: "var(--ec-text-subtle)" }}>Next up:</span>
            {nextEventTime && <span className="tabular-nums">{nextEventTime}</span>}
            <span style={{ color: "var(--ec-text)" }}>·</span>
            <span className="truncate max-w-[18rem]">{nextEvent.title}</span>
          </p>
        )}

        {/* Daily insight — one line, replaces the standalone insight card */}
        {insight?.insight && (
          <p
            className="mt-1.5 inline-flex items-start gap-1.5 text-xs italic"
            style={{ color: "var(--ec-text-muted)" }}
          >
            <Sparkles size={12} className="mt-0.5 shrink-0" style={{ color: "var(--ec-text-subtle)" }} />
            <span className="line-clamp-2">{insight.insight}</span>
          </p>
        )}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <button
          onClick={() => router.push("/dashboard/chat")}
          className="flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all hover:-translate-y-0.5"
          style={{
            background: "#111111",
            color: "#ffffff",
          }}
        >
          <MessageSquare size={15} />
          <span className="flex-1 text-sm font-medium">Start a new chat</span>
          <ArrowRight size={13} className="opacity-70" />
        </button>

        <button
          onClick={() => window.dispatchEvent(new CustomEvent("ec:open-panel", {
            detail: { name: "goals", title: "Your goals" },
          }))}
          className="flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all hover:-translate-y-0.5"
          style={{
            background: "var(--ec-card-bg)",
            color: "var(--ec-text)",
            border: "1px solid var(--ec-card-border)",
            boxShadow: "var(--ec-card-shadow)",
          }}
        >
          <Target size={15} style={{ color: "#4a7c59" }} />
          <span className="flex-1 text-sm font-medium">Peek at goals</span>
          <ArrowRight size={13} style={{ color: "var(--ec-text-subtle)" }} />
        </button>

        <button
          onClick={() => window.dispatchEvent(new Event("ec:open-palette"))}
          className="flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all hover:-translate-y-0.5"
          style={{
            background: "var(--ec-card-bg)",
            color: "var(--ec-text)",
            border: "1px solid var(--ec-card-border)",
            boxShadow: "var(--ec-card-shadow)",
          }}
        >
          <Search size={15} style={{ color: "var(--ec-text-muted)" }} />
          <span className="flex-1 text-sm font-medium">Search anything</span>
          <kbd
            className="px-1.5 py-0.5 text-[10px] font-medium rounded"
            style={{ background: "var(--ec-surface-2)", color: "var(--ec-text-muted)" }}
          >
            ⌘K
          </kbd>
        </button>
      </div>
    </section>
  )
}


// ─── Recent conversations ─────────────────────────────────────────────

import { api } from "@/lib/api"
import { useMemo } from "react"

interface Conv {
  id: string
  title: string
  folder_id: string | null
  updated_at: string
}


export function RecentConversations() {
  const [convs, setConvs] = useState<Conv[] | null>(null)

  useEffect(() => {
    api.chat.conversations.list()
      .then(r => setConvs(r.conversations))
      .catch(() => setConvs([]))
  }, [])

  const recent = useMemo(() => {
    if (!convs) return null
    // API already returns most-recent first; just cap at 5.
    return convs.slice(0, 5)
  }, [convs])

  if (recent === null) return null
  if (recent.length === 0) return null  // Nothing to show for fresh users; they see the chat CTA above.

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold" style={{ color: "var(--ec-text)" }}>
          Recent conversations
        </h2>
        <Link
          href="/dashboard/chat"
          className="text-xs flex items-center gap-1"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Open chat <ArrowRight size={11} />
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {recent.map(c => {
          const d = new Date(c.updated_at)
          const label = d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
          const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
          return (
            <Link
              key={c.id}
              href={`/dashboard/chat/${c.id}`}
              className="group flex items-start gap-3 px-4 py-3 rounded-xl transition-all hover:-translate-y-0.5"
              style={{
                background: "var(--ec-card-bg)",
                border: "1px solid var(--ec-card-border)",
                boxShadow: "var(--ec-card-shadow)",
              }}
            >
              <MessageSquare size={14} className="mt-0.5 shrink-0" style={{ color: "var(--ec-text-subtle)" }} />
              <span className="flex-1 min-w-0">
                <span className="block text-sm font-medium truncate" style={{ color: "var(--ec-text)" }}>
                  {c.title || "Untitled"}
                </span>
                <span className="text-[11px]" style={{ color: "var(--ec-text-subtle)" }}>
                  {label} · {time}
                </span>
              </span>
              <ArrowRight
                size={12}
                className="mt-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: "var(--ec-text-subtle)" }}
              />
            </Link>
          )
        })}
      </div>
    </section>
  )
}
