"use client"

import { useState, useEffect } from "react"
import { Zap, TrendingUp, FlaskConical, Lightbulb } from "lucide-react"
import { autolabApi, InsightsResponse } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"

const TRACK_LABELS: Record<string, string> = {
  esl_tuning: "ESL Tuning",
  prompt_opt: "Prompt Optimization",
  context_scoring: "Context Scoring",
}

const OUTCOME_STYLES: Record<string, string> = {
  WIN: "bg-green-100 text-green-700",
  LOSS: "bg-red-100 text-red-700",
  SKIP: "bg-amber-100 text-amber-700",
  ERROR: "bg-gray-100 text-gray-700",
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 md:space-y-6 animate-pulse">
      {/* Daily insight skeleton */}
      <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-3" />
        <div className="h-4 bg-gray-200 rounded w-full mb-2" />
        <div className="h-4 bg-gray-200 rounded w-3/4" />
      </div>
      {/* Track cards skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
          >
            <div className="h-3 bg-gray-200 rounded w-1/2 mb-3" />
            <div className="h-8 bg-gray-200 rounded w-1/3" />
          </div>
        ))}
      </div>
      {/* Table skeleton */}
      <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-4 bg-gray-100 rounded w-full mb-2" />
        ))}
      </div>
    </div>
  )
}

export default function InsightsPage() {
  const [data, setData] = useState<InsightsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    autolabApi.insights()
      .then(setData)
      .catch(() => setError("Could not load insights — backend may not be running."))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-4 md:space-y-6">
      <PageHeader title="Insights" subtitle="AutoResearch experiments and daily AI insights" />

      {loading && <LoadingSkeleton />}

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Daily Insight */}
          <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb className="h-4 w-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-[var(--ec-text)]">Daily Insight</h2>
            </div>
            <p className="text-sm text-[var(--ec-text)] leading-relaxed">{data.daily_insight}</p>
          </div>

          {/* AutoLab Best Scores */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 px-1">
              <FlaskConical className="h-4 w-4 text-violet-500" />
              <h2 className="text-sm font-semibold text-[var(--ec-text)]">AutoLab Experiments</h2>
              <span className="ml-auto text-xs text-gray-400">
                {data.autolab.total_wins} wins / {data.autolab.total_trials} trials
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {Object.entries(data.autolab.best_scores).map(([track, score]) => (
                <div
                  key={track}
                  className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
                >
                  <p className="text-xs text-gray-500 mb-1">
                    {TRACK_LABELS[track] ?? track}
                  </p>
                  {score !== null ? (
                    <div className="flex items-end gap-1">
                      <span className="text-2xl font-bold text-[var(--ec-text)]">
                        {Math.round(score * 100)}
                      </span>
                      <span className="text-sm text-gray-400 mb-0.5">%</span>
                    </div>
                  ) : (
                    <span className="text-sm text-gray-400 italic">No data yet</span>
                  )}
                  <div className="mt-2 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-violet-400 transition-all"
                      style={{ width: score !== null ? `${Math.round(score * 100)}%` : "0%" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Experiments */}
          <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="h-4 w-4 text-blue-500" />
              <h2 className="text-sm font-semibold text-[var(--ec-text)]">Recent Experiments</h2>
            </div>
            {data.recent_experiments.length === 0 ? (
              <p className="text-sm text-gray-400 italic">No experiments recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="text-left text-xs font-medium text-gray-400 pb-2 pr-4">Track</th>
                      <th className="text-left text-xs font-medium text-gray-400 pb-2 pr-4">Trial</th>
                      <th className="text-left text-xs font-medium text-gray-400 pb-2 pr-4">Score</th>
                      <th className="text-left text-xs font-medium text-gray-400 pb-2 pr-4">Outcome</th>
                      <th className="text-left text-xs font-medium text-gray-400 pb-2">Hypothesis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_experiments.slice(0, 10).map((exp, idx) => {
                      const outcomeKey = exp.outcome ?? "ERROR"
                      const outcomeStyle = OUTCOME_STYLES[outcomeKey] ?? OUTCOME_STYLES.ERROR
                      return (
                        <tr key={idx} className="border-b border-gray-50 last:border-0">
                          <td className="py-2 pr-4 font-medium text-[var(--ec-text)]">
                            {TRACK_LABELS[exp.track] ?? exp.track}
                          </td>
                          <td className="py-2 pr-4 text-gray-500">
                            {exp.trial !== null ? `#${exp.trial}` : "—"}
                          </td>
                          <td className="py-2 pr-4 text-gray-500">
                            {exp.score !== null ? `${Math.round(exp.score * 100)}%` : "—"}
                          </td>
                          <td className="py-2 pr-4">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${outcomeStyle}`}>
                              {outcomeKey}
                            </span>
                          </td>
                          <td className="py-2 text-gray-500 max-w-xs truncate">
                            {exp.hypothesis}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
