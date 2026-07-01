'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { PageHeader } from '@/components/ui/page-header'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

const CARD_STYLE = {
  background: 'var(--ec-card-bg)',
  border: '1px solid var(--ec-card-border)',
  borderRadius: '16px',
  boxShadow: 'var(--ec-card-shadow)',
}

const CATEGORY_META: Record<string, { label: string; hint: string }> = {
  'read-personal':  { label: 'Read · Personal',  hint: 'Your calendar, memory, goals, documents' },
  'read-external':  { label: 'Read · External',  hint: 'Web search' },
  'write-personal': { label: 'Write · Personal', hint: 'Notes you save' },
  'write-external': { label: 'Write · External', hint: 'Emails, Slack messages, calendar writes' },
}
const CATEGORY_KEYS = Object.keys(CATEGORY_META)

export default function SafetySettingsPage() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['safety-state'],
    queryFn: () => api.safety.state(),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['safety-state'] })

  const safeMutate = useMutation({
    mutationFn: (enabled: boolean) => api.safety.setSafeMode(enabled),
    onSuccess: invalidate,
  })

  const categoryMutate = useMutation({
    mutationFn: ({ category, requires_confirmation }: { category: string; requires_confirmation: boolean }) =>
      api.safety.setCategory(category, requires_confirmation),
    onSuccess: invalidate,
  })

  const toolMutate = useMutation({
    mutationFn: ({ tool_name, requires_confirmation }: { tool_name: string; requires_confirmation: boolean }) =>
      api.safety.setTool(tool_name, requires_confirmation),
    onSuccess: invalidate,
  })

  const safeModeEnabled = data?.safe_mode_enabled ?? false
  const activeCategories = new Set(data?.categories ?? [])
  const activeTools = new Set(data?.tools ?? [])
  const availableTools = data?.available_tools ?? []

  const lowerSectionStyle: React.CSSProperties = safeModeEnabled
    ? { opacity: 0.4, pointerEvents: 'none' as const }
    : {}

  if (isLoading) {
    return (
      <div className="max-w-[700px] mx-auto px-4 py-8">
        <PageHeader title="Safety Settings" subtitle="Control when Ethic Companion asks before acting" />
        <p className="text-sm mt-8" style={{ color: 'var(--ec-text-muted)' }}>Loading…</p>
      </div>
    )
  }

  return (
    <div className="max-w-[700px] mx-auto px-4 py-8 space-y-6">
      <PageHeader title="Safety Settings" subtitle="Control when Ethic Companion asks before acting" />

      {/* Section 1 — Master toggle */}
      <div className="p-5 space-y-2" style={CARD_STYLE}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <Label className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>
              Ask me before any action runs
            </Label>
            <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>
              Every tool call will pause and wait for your approval, regardless of category.
            </p>
          </div>
          <Switch
            checked={safeModeEnabled}
            onCheckedChange={(enabled) => safeMutate.mutate(enabled)}
            aria-label="Safe mode"
          />
        </div>
      </div>

      {/* Section 2 — Category grid */}
      <div className="p-5 space-y-4" style={{ ...CARD_STYLE, ...lowerSectionStyle }}>
        <div>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--ec-text)' }}>
            Confirm by category
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>
            All tools in the selected category will require confirmation.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {CATEGORY_KEYS.map((key) => {
            const meta = CATEGORY_META[key]
            const checked = activeCategories.has(key)
            return (
              <label
                key={key}
                className="flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-colors hover:bg-black/3"
                style={{ border: '1px solid var(--ec-card-border)' }}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 accent-[#4A7C59]"
                  checked={checked}
                  onChange={(e) =>
                    categoryMutate.mutate({ category: key, requires_confirmation: e.target.checked })
                  }
                />
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>{meta.label}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>{meta.hint}</p>
                </div>
              </label>
            )
          })}
        </div>
      </div>

      {/* Section 3 — Per-tool list */}
      {availableTools.length > 0 && (
        <div className="p-5 space-y-4" style={{ ...CARD_STYLE, ...lowerSectionStyle }}>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--ec-text)' }}>
              Confirm by tool
            </h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>
              Fine-grained control over individual tools.
            </p>
          </div>
          <ul className="space-y-2">
            {availableTools.map((tool) => {
              const coveredByCategory = activeCategories.has(tool.category)
              const checked = activeTools.has(tool.name) || coveredByCategory
              return (
                <li
                  key={tool.name}
                  className="flex items-center gap-3 py-2 px-3 rounded-xl"
                  style={{ border: '1px solid var(--ec-card-border)' }}
                >
                  <input
                    type="checkbox"
                    className="accent-[#4A7C59]"
                    checked={checked}
                    disabled={coveredByCategory}
                    onChange={(e) =>
                      toolMutate.mutate({ tool_name: tool.name, requires_confirmation: e.target.checked })
                    }
                  />
                  <span className="flex-1 text-sm" style={{ color: 'var(--ec-text)' }}>{tool.name}</span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                    style={{
                      background: 'var(--ec-surface-2)',
                      color: 'var(--ec-text-muted)',
                      border: '1px solid var(--ec-card-border)',
                    }}
                  >
                    {tool.category}
                  </span>
                  {coveredByCategory && (
                    <span className="text-[10px]" style={{ color: 'var(--ec-text-subtle)' }}>
                      covered by category
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
