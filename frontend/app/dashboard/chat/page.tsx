'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import api from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { Send, ChevronDown, ChevronUp, Copy, Bot, Square, ThumbsUp, ThumbsDown } from 'lucide-react'
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

const ESL_COLORS: Record<string, { bg: string; text: string; border: string; leftBorder: string }> = {
  APPROVED: { bg: 'rgba(74,124,89,0.10)',  text: '#4A7C59', border: 'rgba(74,124,89,0.25)',  leftBorder: '#4A7C59' },
  VETOED:   { bg: 'rgba(176,74,58,0.10)',  text: '#B04A3A', border: 'rgba(176,74,58,0.25)',  leftBorder: '#B04A3A' },
  MODIFIED: { bg: 'rgba(155,122,61,0.10)', text: '#9B7A3D', border: 'rgba(155,122,61,0.25)', leftBorder: '#9B7A3D' },
}

const EXAMPLE_PROMPTS = [
  "What's on my agenda today?",
  "Help me prioritize my goals",
  "Summarize my week",
]

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return ''
  }
}

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard unavailable
    }
  }, [content])

  return (
    <button
      onClick={handleCopy}
      aria-label="Copy message"
      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-black/5"
      style={{ color: copied ? '#4A7C59' : '#9e9e9e' }}
    >
      <Copy size={13} />
    </button>
  )
}

function FeedbackButtons({
  messageId,
  currentFeedback,
  onFeedback,
}: {
  messageId: string
  currentFeedback: 'up' | 'down' | null | undefined
  onFeedback: (id: string, type: 'up' | 'down') => void
}) {
  return (
    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        onClick={() => onFeedback(messageId, 'up')}
        aria-label="Helpful"
        className="p-1 rounded-md hover:bg-black/5 transition-colors"
        style={{ color: currentFeedback === 'up' ? '#4A7C59' : '#c0c0c0' }}
      >
        <ThumbsUp size={13} fill={currentFeedback === 'up' ? '#4A7C59' : 'none'} />
      </button>
      <button
        onClick={() => onFeedback(messageId, 'down')}
        aria-label="Not helpful"
        className="p-1 rounded-md hover:bg-black/5 transition-colors"
        style={{ color: currentFeedback === 'down' ? '#B04A3A' : '#c0c0c0' }}
      >
        <ThumbsDown size={13} fill={currentFeedback === 'down' ? '#B04A3A' : 'none'} />
      </button>
    </div>
  )
}

function ESLTag({ decision }: { decision: Message['esl_decision'] }) {
  const [expanded, setExpanded] = useState(false)
  if (!decision) return null
  const c = ESL_COLORS[decision.status] ?? ESL_COLORS.APPROVED
  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(v => !v)}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium transition-opacity hover:opacity-80"
        style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
      >
        ESL: {decision.status}
        {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
      </button>
      {expanded && (
        <p className="mt-1.5 text-xs px-2" style={{ color: '#6b6b6b' }}>
          {decision.reason}
        </p>
      )}
    </div>
  )
}

export default function ChatPage() {
  const { user } = useAuth()
  const initials = user?.email?.split('@')[0].substring(0, 2).toUpperCase() ?? 'U'
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [userScrolled, setUserScrolled] = useState(false)

  const endRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const streamRef = useRef<{ cancel: () => void } | null>(null)

  const handleFeedback = useCallback(async (messageId: string, type: 'up' | 'down') => {
    setMessages(prev =>
      prev.map(m => m.id === messageId ? { ...m, feedback: type } : m)
    )
    try {
      await api.feedback.submit({
        item_id: messageId,
        item_type: 'chat_response',
        feedback_type: type === 'up' ? 'thumbs_up' : 'thumbs_down',
      })
    } catch {
      // revert on failure
      setMessages(prev =>
        prev.map(m => m.id === messageId ? { ...m, feedback: null } : m)
      )
    }
  }, [])

  // Load history on mount
  useEffect(() => {
    api.chat.history()
      .then(h => {
        const msgs = (h.messages ?? []).map((m, i) => ({
          id: `h-${i}`,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: m.timestamp ?? '',
        }))
        setMessages(msgs)
      })
      .catch(console.error)
      .finally(() => setLoadingHistory(false))
  }, [])

  // Auto-scroll: only when user hasn't manually scrolled up
  useEffect(() => {
    if (!userScrolled) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, userScrolled])

  // Detect manual scroll
  const handleScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setUserScrolled(distanceFromBottom > 80)
  }, [])

  const handleSend = async (text?: string) => {
    const userMessage = (text ?? input).trim()
    if (!userMessage || isLoading) return

    setInput('')
    setIsLoading(true)
    setUserScrolled(false)

    // Add user message immediately
    setMessages(prev => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', content: userMessage, timestamp: new Date().toISOString() },
    ])

    // Add empty assistant message for streaming
    const assistantId = `a-${Date.now()}`
    setMessages(prev => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', timestamp: new Date().toISOString(), streaming: true },
    ])

    try {
      const streamPromise = api.chat.stream(userMessage, (token) => {
        setMessages(prev => {
          const msgs = [...prev]
          const last = msgs[msgs.length - 1]
          if (last && last.streaming) {
            msgs[msgs.length - 1] = { ...last, content: last.content + token }
          }
          return msgs
        })
      })

      streamRef.current = streamPromise

      await streamPromise

      // Mark streaming complete
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last && last.streaming) {
          const { streaming: _s, ...rest } = last
          msgs[msgs.length - 1] = rest
        }
        return msgs
      })
    } catch (e) {
      // On cancellation or error, finalise the partial message
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last && last.streaming) {
          const { streaming: _s, ...rest } = last
          // If nothing was received, show a fallback
          msgs[msgs.length - 1] = {
            ...rest,
            content: rest.content || 'Something went wrong. Please try again.',
          }
        }
        return msgs
      })
      if (e instanceof Error && e.message !== 'Stream cancelled') {
        console.error(e)
      }
    } finally {
      streamRef.current = null
      setIsLoading(false)
    }
  }

  const handleStop = () => {
    if (streamRef.current) {
      streamRef.current.cancel()
    }
  }

  const isEmpty = !loadingHistory && messages.length === 0

  return (
    <div
      className="flex flex-col rounded-2xl overflow-hidden"
      style={{
        background: '#ffffff',
        border: '1px solid rgba(0,0,0,0.08)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        height: 'calc(100vh - 56px - 48px - 24px)',
      }}
    >
      {/* Messages */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-6 py-4 space-y-4"
      >
        {loadingHistory && (
          <div className="space-y-3">
            {[1, 2, 3].map(i => <Skeleton key={i} className="h-12 w-3/4" />)}
          </div>
        )}

        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <p className="text-sm" style={{ color: '#9e9e9e' }}>
              Ask your companion anything
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {EXAMPLE_PROMPTS.map(p => (
                <button
                  key={p}
                  onClick={() => handleSend(p)}
                  className="px-3 py-1.5 rounded-full text-sm transition-colors hover:bg-[#f5f5f5]"
                  style={{ border: '1px solid rgba(0,0,0,0.10)', color: '#6b6b6b' }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex group ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div className="flex flex-col items-end gap-1 max-w-[70%]">
                <div className="flex items-end gap-1.5">
                  <CopyButton content={msg.content} />
                  <div
                    className="px-4 py-2.5 rounded-2xl rounded-br-sm text-sm"
                    style={{ background: 'rgba(0,0,0,0.06)', color: '#0a0a0a' }}
                  >
                    {msg.content}
                  </div>
                  {/* User avatar */}
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
                    style={{ background: '#332b36', color: '#ffffff' }}
                    aria-label="User"
                  >
                    {initials}
                  </div>
                </div>
                {msg.timestamp && (
                  <span className="text-[10px] pr-9" style={{ color: '#b0b0b0' }}>
                    {formatTime(msg.timestamp)}
                  </span>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-start gap-1 max-w-[70%]">
                <div className="flex items-end gap-1.5">
                  {/* Bot avatar */}
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                    style={{ background: '#f0ecf3', color: '#695e6e' }}
                    aria-label="Assistant"
                  >
                    <Bot size={14} />
                  </div>
                  <div
                    className="px-4 py-2.5 rounded-2xl rounded-bl-sm text-sm border-l-2"
                    style={{
                      background: '#f9f9f9',
                      color: '#0a0a0a',
                      borderLeftColor: msg.esl_decision
                        ? (ESL_COLORS[msg.esl_decision.status]?.leftBorder ?? '#E5E5E5')
                        : '#E5E5E5',
                    }}
                  >
                    {msg.content}
                    {msg.streaming && (
                      <span
                        className="inline-block w-0.5 h-3.5 ml-0.5 align-middle animate-pulse"
                        style={{ background: '#695e6e' }}
                        aria-hidden="true"
                      />
                    )}
                    {msg.esl_decision && <ESLTag decision={msg.esl_decision} />}
                  </div>
                  {!msg.streaming && (
                    <div className="flex items-center gap-0.5">
                      <CopyButton content={msg.content} />
                      <FeedbackButtons
                        messageId={msg.id}
                        currentFeedback={msg.feedback}
                        onFeedback={handleFeedback}
                      />
                    </div>
                  )}
                </div>
                {msg.timestamp && !msg.streaming && (
                  <span className="text-[10px] pl-9" style={{ color: '#b0b0b0' }}>
                    {formatTime(msg.timestamp)}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}

        <div ref={endRef} />
      </div>

      {/* Input bar */}
      <div className="px-4 py-3 border-t border-[rgba(0,0,0,0.08)]" style={{ background: '#fafafa' }}>
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={e => {
              setInput(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="Message your companion…"
            rows={1}
            className="flex-1 resize-none rounded-xl px-4 py-2.5 text-sm outline-none"
            style={{
              background: '#ffffff',
              border: '1px solid rgba(0,0,0,0.10)',
              color: '#0a0a0a',
              maxHeight: '120px',
              overflowY: 'auto',
            }}
          />
          {isLoading ? (
            <button
              onClick={handleStop}
              aria-label="Stop generation"
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-opacity hover:opacity-80"
              style={{ background: '#332b36' }}
            >
              <Square size={13} color="#FFFFFF" fill="#FFFFFF" />
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-opacity disabled:opacity-40"
              style={{ background: '#000000' }}
              aria-label="Send message"
            >
              <Send size={15} color="#FFFFFF" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
