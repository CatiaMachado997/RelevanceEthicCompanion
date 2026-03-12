'use client'

import { useState, useEffect, useRef } from 'react'
import api from '@/lib/api'
import { Send, ChevronDown, ChevronUp } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
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
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const endRef = useRef<HTMLDivElement>(null)

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

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text: string) => {
    const msg = text.trim()
    if (!msg || loading) return
    setInput('')
    setLoading(true)

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: msg,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])

    try {
      const result = await api.chat.send(msg)
      const aiMsg: Message = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: result.response ?? 'No response.',
        timestamp: result.timestamp ?? new Date().toISOString(),
        esl_decision: result.esl_decision
          ? { status: result.esl_decision.status, reason: result.esl_decision.reason }
          : undefined,
      }
      setMessages(prev => [...prev, aiMsg])
    } catch {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setLoading(false)
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
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
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
                  onClick={() => send(p)}
                  className="px-3 py-1.5 rounded-full text-sm transition-colors hover:bg-black/5"
                  style={{ border: '1px solid rgba(0,0,0,0.08)', color: '#6b6b6b' }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div
                className="max-w-[70%] px-4 py-2.5 rounded-2xl rounded-br-sm text-sm"
                style={{ background: 'rgba(0,0,0,0.06)', color: '#0a0a0a' }}
              >
                {msg.content}
              </div>
            ) : (
              <div
                className="max-w-[70%] px-4 py-2.5 rounded-2xl rounded-bl-sm text-sm border-l-2"
                style={{
                  background: '#f9f9f9',
                  color: '#0a0a0a',
                  borderLeftColor: msg.esl_decision
                    ? (ESL_COLORS[msg.esl_decision.status]?.leftBorder ?? '#E5E5E5')
                    : '#E5E5E5',
                }}
              >
                {msg.content}
                {msg.esl_decision && <ESLTag decision={msg.esl_decision} />}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div
              className="px-4 py-3 rounded-2xl rounded-bl-sm"
              style={{ background: '#f5f5f5', border: '1px solid rgba(0,0,0,0.06)' }}
            >
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full animate-bounce"
                    style={{ background: '#9e9e9e', animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Input bar */}
      <div className="px-4 py-3 border-t border-black/5" style={{ background: '#f5f5f5' }}>
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
                send(input)
              }
            }}
            placeholder="Message your companion…"
            rows={1}
            className="flex-1 resize-none rounded-xl px-4 py-2.5 text-sm outline-none"
            style={{
              background: '#ffffff',
              border: '1px solid rgba(0,0,0,0.08)',
              color: '#0a0a0a',
              maxHeight: '120px',
              overflowY: 'auto',
            }}
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-opacity disabled:opacity-40"
            style={{ background: '#000000' }}
            aria-label="Send message"
          >
            <Send size={15} color="#FFFFFF" />
          </button>
        </div>
      </div>
    </div>
  )
}
