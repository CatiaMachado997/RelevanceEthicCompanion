'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import api from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import {
  Send, ChevronDown, ChevronUp, Copy, Square,
  ThumbsUp, ThumbsDown, RotateCcw, Plus,
} from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  streaming?: boolean
  feedback?: 'up' | 'down' | null
  esl_decision?: {
    status: 'APPROVED' | 'VETOED' | 'MODIFIED'
    reason: string
  }
}

const ESL_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  APPROVED: { bg: 'rgba(74,124,89,0.08)',  text: '#4A7C59', border: 'rgba(74,124,89,0.20)' },
  VETOED:   { bg: 'rgba(176,74,58,0.08)',  text: '#B04A3A', border: 'rgba(176,74,58,0.20)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.08)', text: '#9B7A3D', border: 'rgba(155,122,61,0.20)' },
}

const EXAMPLE_PROMPTS = [
  "What's on my agenda today?",
  "Help me prioritize my goals",
  "Summarize my week",
  "How are my values being respected?",
]

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch { return '' }
}

/* ─── Copy button ─── */
function CopyButton({ content, size = 14 }: { content: string; size?: number }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* ignore */ }
  }, [content])
  return (
    <button
      onClick={handleCopy}
      aria-label={copied ? 'Copied' : 'Copy'}
      title={copied ? 'Copied!' : 'Copy'}
      className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-black/6"
      style={{ color: copied ? '#4A7C59' : '#a0a0a0' }}
    >
      <Copy size={size} />
    </button>
  )
}

/* ─── ESL badge ─── */
function ESLTag({ decision }: { decision: Message['esl_decision'] }) {
  const [open, setOpen] = useState(false)
  if (!decision) return null
  const c = ESL_COLORS[decision.status] ?? ESL_COLORS.APPROVED
  return (
    <div className="mt-3 inline-flex flex-col items-start">
      <button
        onClick={() => setOpen(v => !v)}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide uppercase transition-opacity hover:opacity-75"
        style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
      >
        ESL · {decision.status}
        {open ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
      </button>
      {open && (
        <p className="mt-1.5 text-xs leading-relaxed" style={{ color: '#6b6b6b', maxWidth: '480px' }}>
          {decision.reason}
        </p>
      )}
    </div>
  )
}

/* ─── Message action row (copy / thumbs / regenerate) ─── */
function AssistantActions({
  msg,
  onFeedback,
  onRegenerate,
}: {
  msg: Message
  onFeedback: (id: string, type: 'up' | 'down') => void
  onRegenerate?: () => void
}) {
  return (
    <div className="flex items-center gap-0.5 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
      <CopyButton content={msg.content} />
      <button
        onClick={() => onFeedback(msg.id, 'up')}
        aria-label="Helpful"
        title="Helpful"
        className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-black/6"
        style={{ color: msg.feedback === 'up' ? '#4A7C59' : '#a0a0a0' }}
      >
        <ThumbsUp size={14} fill={msg.feedback === 'up' ? '#4A7C59' : 'none'} />
      </button>
      <button
        onClick={() => onFeedback(msg.id, 'down')}
        aria-label="Not helpful"
        title="Not helpful"
        className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-black/6"
        style={{ color: msg.feedback === 'down' ? '#B04A3A' : '#a0a0a0' }}
      >
        <ThumbsDown size={14} fill={msg.feedback === 'down' ? '#B04A3A' : 'none'} />
      </button>
      {onRegenerate && (
        <button
          onClick={onRegenerate}
          aria-label="Regenerate"
          title="Regenerate response"
          className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-black/6"
          style={{ color: '#a0a0a0' }}
        >
          <RotateCcw size={13} />
        </button>
      )}
    </div>
  )
}

/* ─── EC companion avatar (shown once, at the top of each assistant turn) ─── */
function CompanionAvatar() {
  return (
    <div
      className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 select-none"
      style={{ background: 'var(--ec-text)', color: 'var(--ec-sidebar-bg)' }}
      aria-hidden="true"
    >
      EC
    </div>
  )
}

/* ─── Streaming cursor ─── */
function Cursor() {
  return (
    <span
      className="inline-block w-[2px] h-[1em] ml-0.5 align-[-0.05em] animate-pulse rounded-sm"
      style={{ background: '#1a1a1a', animationDuration: '800ms' }}
      aria-hidden
    />
  )
}

/* ═══════════════════════════════════════════════════ */
export default function ChatPage() {
  const { user } = useAuth()
  const initials = user?.email?.split('@')[0].substring(0, 2).toUpperCase() ?? 'U'

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput]       = useState('')
  const [isLoading, setIsLoading]       = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [userScrolled, setUserScrolled] = useState(false)

  const endRef       = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const textareaRef  = useRef<HTMLTextAreaElement>(null)
  const streamRef    = useRef<{ cancel: () => void } | null>(null)

  /* feedback */
  const handleFeedback = useCallback(async (messageId: string, type: 'up' | 'down') => {
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, feedback: type } : m))
    try {
      await api.feedback.submit({
        item_id:       messageId,
        item_type:     'chat_response',
        feedback_type: type === 'up' ? 'thumbs_up' : 'thumbs_down',
      })
    } catch {
      setMessages(prev => prev.map(m => m.id === messageId ? { ...m, feedback: null } : m))
    }
  }, [])

  /* history */
  useEffect(() => {
    api.chat.history()
      .then(h => {
        setMessages((h.messages ?? []).map((m, i) => ({
          id:        `h-${i}`,
          role:      m.role as 'user' | 'assistant',
          content:   m.content,
          timestamp: m.timestamp ?? '',
        })))
      })
      .catch(console.error)
      .finally(() => setLoadingHistory(false))
  }, [])

  /* auto-scroll */
  useEffect(() => {
    if (!userScrolled) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, userScrolled])

  const handleScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    setUserScrolled(el.scrollHeight - el.scrollTop - el.clientHeight > 80)
  }, [])

  /* resize textarea */
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }, [])

  /* send */
  const handleSend = async (text?: string) => {
    const userMessage = (text ?? input).trim()
    if (!userMessage || isLoading) return

    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setIsLoading(true)
    setUserScrolled(false)

    setMessages(prev => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', content: userMessage, timestamp: new Date().toISOString() },
    ])

    const assistantId = `a-${Date.now()}`
    setMessages(prev => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', timestamp: new Date().toISOString(), streaming: true },
    ])

    try {
      const s = api.chat.stream(userMessage, (token) => {
        setMessages(prev => {
          const msgs = [...prev]
          const last = msgs[msgs.length - 1]
          if (last?.streaming) msgs[msgs.length - 1] = { ...last, content: last.content + token }
          return msgs
        })
      })
      streamRef.current = s
      await s
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last?.streaming) {
          const { streaming: _s, ...rest } = last
          msgs[msgs.length - 1] = rest
        }
        return msgs
      })
    } catch (e) {
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last?.streaming) {
          const { streaming: _s, ...rest } = last
          msgs[msgs.length - 1] = {
            ...rest,
            content: rest.content || 'Something went wrong. Please try again.',
          }
        }
        return msgs
      })
      if (e instanceof Error && e.message !== 'Stream cancelled') console.error(e)
    } finally {
      streamRef.current = null
      setIsLoading(false)
    }
  }

  const handleStop = () => streamRef.current?.cancel()

  const isEmpty = !loadingHistory && messages.length === 0

  return (
    <div
      className="flex flex-col"
      style={{ height: 'calc(100vh - 56px - 48px - 24px)' }}
    >
      {/* ── Messages ── */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        <div className="mx-auto max-w-[720px] px-4 py-8 space-y-8">

          {loadingHistory && (
            <div className="space-y-5">
              {[120, 80, 160].map((w, i) => (
                <Skeleton key={i} className="h-4 rounded-full" style={{ width: `${w}px` }} />
              ))}
            </div>
          )}

          {/* Empty state */}
          {isEmpty && (
            <div className="flex flex-col items-center justify-center gap-6 pt-20 text-center">
              <div>
                <div
                  className="w-11 h-11 rounded-2xl flex items-center justify-center text-sm font-bold mx-auto mb-5"
                  style={{ background: 'var(--ec-text)', color: 'var(--ec-sidebar-bg)' }}
                >
                  EC
                </div>
                <p className="text-base font-medium" style={{ color: '#1a1a1a' }}>
                  How can I help you today?
                </p>
                <p className="text-sm mt-1" style={{ color: '#9e9e9e' }}>
                  Your companion is ready — protected by ESL.
                </p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-w-[520px]">
                {EXAMPLE_PROMPTS.map(p => (
                  <button
                    key={p}
                    onClick={() => handleSend(p)}
                    className="px-3.5 py-1.5 rounded-full text-sm transition-colors hover:bg-[#f0f0f0]"
                    style={{
                      border: '1px solid rgba(0,0,0,0.10)',
                      color: '#6b6b6b',
                      background: '#fafafa',
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message list */}
          {messages.map((msg, idx) => {
            const isLast = idx === messages.length - 1

            if (msg.role === 'user') {
              return (
                <div key={msg.id} className="flex justify-end group">
                  <div className="flex flex-col items-end gap-1 max-w-[80%]">
                    <div className="flex items-center gap-2">
                      <CopyButton content={msg.content} size={13} />
                      <div
                        className="px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm leading-relaxed"
                        style={{
                          background: 'rgba(0,0,0,0.06)',
                          color: '#0a0a0a',
                        }}
                      >
                        {msg.content}
                      </div>
                      {/* User avatar */}
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0"
                        style={{ background: '#332b36', color: '#ffffff' }}
                        aria-label="You"
                      >
                        {initials}
                      </div>
                    </div>
                    {msg.timestamp && (
                      <span className="text-[10px] pr-9" style={{ color: '#c0c0c0' }}>
                        {formatTime(msg.timestamp)}
                      </span>
                    )}
                  </div>
                </div>
              )
            }

            /* assistant */
            return (
              <div key={msg.id} className="flex flex-col items-start group">
                {/* Avatar + timestamp header */}
                <div className="flex items-center gap-2 mb-2">
                  <CompanionAvatar />
                  {msg.timestamp && !msg.streaming && (
                    <span className="text-[10px]" style={{ color: '#c0c0c0' }}>
                      {formatTime(msg.timestamp)}
                    </span>
                  )}
                </div>

                {/* Message body */}
                <div
                  className="pl-9 text-sm leading-[1.75] w-full"
                  style={{ color: '#1a1a1a' }}
                >
                  {msg.content || (msg.streaming && (
                    <span className="inline-block" style={{ color: '#9e9e9e' }}>…</span>
                  ))}
                  {msg.streaming && <Cursor />}
                  {msg.esl_decision && <ESLTag decision={msg.esl_decision} />}
                </div>

                {/* Action row — only after streaming done */}
                {!msg.streaming && (
                  <div className="pl-9 mt-0.5">
                    <AssistantActions
                      msg={msg}
                      onFeedback={handleFeedback}
                      onRegenerate={isLast && !isLoading ? () => {
                        // find last user message and re-send
                        const lastUser = [...messages].reverse().find(m => m.role === 'user')
                        if (lastUser) handleSend(lastUser.content)
                      } : undefined}
                    />
                  </div>
                )}
              </div>
            )
          })}

          <div ref={endRef} />
        </div>
      </div>

      {/* ── Input card ── */}
      <div className="shrink-0 px-4 pb-4">
        <div
          className="mx-auto max-w-[720px] rounded-2xl overflow-hidden"
          style={{
            background: '#ffffff',
            border: '1px solid rgba(0,0,0,0.12)',
            boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
          }}
        >
          {/* Textarea */}
          <div className="px-4 pt-3.5 pb-1">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => { setInput(e.target.value); resizeTextarea() }}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Reply…"
              rows={1}
              className="w-full resize-none text-sm outline-none bg-transparent leading-relaxed"
              style={{ color: '#0a0a0a', maxHeight: '140px', overflowY: 'auto' }}
            />
          </div>

          {/* Bottom bar */}
          <div className="flex items-center justify-between px-3 pb-2.5 pt-1">
            {/* Left: attach */}
            <button
              className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-black/5"
              aria-label="Attach"
              title="Attach file"
              style={{ color: '#9e9e9e' }}
            >
              <Plus size={16} />
            </button>

            {/* Right: model chip + send/stop */}
            <div className="flex items-center gap-2">
              {/* Model indicator */}
              <div
                className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
                style={{
                  background: 'rgba(0,0,0,0.04)',
                  color: '#6b6b6b',
                  border: '1px solid rgba(0,0,0,0.06)',
                }}
              >
                Ethic Companion
                <ChevronDown size={10} />
              </div>

              {/* Send / Stop */}
              {isLoading ? (
                <button
                  onClick={handleStop}
                  aria-label="Stop generation"
                  className="w-8 h-8 rounded-xl flex items-center justify-center transition-opacity hover:opacity-80"
                  style={{ background: '#1a1a1a' }}
                >
                  <Square size={12} color="#fff" fill="#fff" />
                </button>
              ) : (
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim()}
                  aria-label="Send"
                  className="w-8 h-8 rounded-xl flex items-center justify-center transition-opacity disabled:opacity-30"
                  style={{ background: '#1a1a1a' }}
                >
                  <Send size={13} color="#fff" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
