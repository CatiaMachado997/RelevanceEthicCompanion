"use client"

import { useEffect, useState } from "react"
import { useRouter, useParams } from "next/navigation"
import {
  SecondarySidebar,
  SecondarySidebarSection,
  SecondarySidebarPromo,
} from "@/components/secondary-sidebar"
import { Button } from "@/components/ui/button"
import { Plus, MessageSquare, Sparkles, Clock } from "lucide-react"
import api from "@/lib/api"

interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

interface ChatSidebarProps {
  onNewChat?: () => void
}

type DateBucket = 'Today' | 'Yesterday' | 'Last 7 days' | 'Older'

function getBucket(dateString: string): DateBucket {
  const date = new Date(dateString)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / 86400000)
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return 'Last 7 days'
  return 'Older'
}

const BUCKET_ORDER: DateBucket[] = ['Today', 'Yesterday', 'Last 7 days', 'Older']

function groupConversations(convs: Conversation[]): Map<DateBucket, Conversation[]> {
  const sorted = [...convs].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
  const map = new Map<DateBucket, Conversation[]>()
  for (const c of sorted) {
    const bucket = getBucket(c.updated_at)
    if (!map.has(bucket)) map.set(bucket, [])
    map.get(bucket)!.push(c)
  }
  return map
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function ChatSidebar({ onNewChat }: ChatSidebarProps) {
  const router = useRouter()
  const params = useParams()
  const activeId = params?.id as string | undefined

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    const load = () => {
      api.chat.conversations.list()
        .then(res => { if (!cancelled) setConversations(res.conversations ?? []) })
        .catch(() => {})
        .finally(() => { if (!cancelled) setLoading(false) })
    }

    load()
    const interval = setInterval(load, 10_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  useEffect(() => {
    const handler = () => {
      api.chat.conversations.list()
        .then(res => setConversations(res.conversations ?? []))
        .catch(() => {})
    }
    window.addEventListener('ec:conversation-created', handler)
    return () => window.removeEventListener('ec:conversation-created', handler)
  }, [])

  const filtered = searchQuery
    ? conversations.filter(c =>
        c.title.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : conversations

  return (
    <SecondarySidebar
      title="Conversations"
      action={
        <Button
          size="sm"
          className="rounded-full bg-[#171717] hover:bg-[#4338CA] h-8 w-8 p-0"
          onClick={onNewChat ?? (() => router.push('/dashboard/chat'))}
        >
          <Plus className="h-4 w-4" />
        </Button>
      }
      showSearch
      searchPlaceholder="Search conversations..."
      onSearch={setSearchQuery}
      footer={
        <SecondarySidebarPromo
          title="AI with Ethics"
          description="Every response is filtered through our Ethical Safeguard Layer."
        />
      }
    >
      <SecondarySidebarSection title="Recent">
        <div className="space-y-1">
          {loading && (
            <p className="text-xs text-[#A3A3A3] px-3 py-2">Loading…</p>
          )}
          {!loading && filtered.length === 0 && (
            <div className="px-3 py-6 text-center text-[#A3A3A3]">
              <p className="text-sm">No conversations yet.</p>
              <p className="text-xs mt-1">Start chatting to create one.</p>
            </div>
          )}
          {(() => {
            const grouped = groupConversations(filtered)
            return BUCKET_ORDER.flatMap(bucket => {
              const convs = grouped.get(bucket)
              if (!convs || convs.length === 0) return []
              return [
                <div key={`label-${bucket}`} className="px-3 pt-3 pb-1">
                  <span className="text-[10px] font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>
                    {bucket}
                  </span>
                </div>,
                ...convs.map(conv => (
                  <button
                    key={conv.id}
                    onClick={() => router.push(`/dashboard/chat/${conv.id}`)}
                    className={`w-full flex items-start gap-3 p-3 rounded-lg transition-colors text-left ${
                      activeId === conv.id
                        ? 'bg-[#F0F0F0]'
                        : 'hover:bg-[#F5F5F5]'
                    }`}
                  >
                    <div className="w-8 h-8 rounded-lg bg-[#171717]/10 flex items-center justify-center shrink-0">
                      <MessageSquare className="h-4 w-4 text-[#171717]" />
                    </div>
                    <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                      <span className="truncate text-sm font-medium leading-tight text-[#171717]">
                        {conv.title || 'New chat'}
                      </span>
                      {conv.updated_at && (
                        <span className="text-xs text-[#A3A3A3]">
                          {formatRelativeTime(conv.updated_at)}
                        </span>
                      )}
                    </div>
                  </button>
                )),
              ]
            })
          })()}
        </div>
      </SecondarySidebarSection>

      <SecondarySidebarSection title="Suggestions">
        <div className="space-y-2">
          <div className="p-3 rounded-lg bg-[#FAFAFA] border border-[#E5E5E5]">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-[#171717]" />
              <span className="text-xs font-medium text-[#171717]">Try asking</span>
            </div>
            <p className="text-sm text-[#525252]">"Help me prioritize my goals for this week"</p>
          </div>
          <div className="p-3 rounded-lg bg-[#FAFAFA] border border-[#E5E5E5]">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="h-4 w-4 text-[#171717]" />
              <span className="text-xs font-medium text-[#171717]">Quick prompt</span>
            </div>
            <p className="text-sm text-[#525252]">"What should I focus on today?"</p>
          </div>
        </div>
      </SecondarySidebarSection>
    </SecondarySidebar>
  )
}
