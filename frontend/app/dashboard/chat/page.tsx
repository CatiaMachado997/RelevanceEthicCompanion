'use client'

import { useState, useEffect, useRef, useCallback, ChangeEvent, ReactElement } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CodeBlock } from '@/components/chat/CodeBlock'
import { ArtifactCard } from '@/components/chat/ArtifactCard'
import api, { CitationSource } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/navigation'
import {
  Send, ChevronDown, ChevronUp, Copy, Square,
  ThumbsUp, ThumbsDown, RotateCcw, Plus, Cpu,
  Paperclip, Globe, Calendar, Target, StickyNote,
  BarChart2, ShieldCheck, Sparkles,
  BookmarkPlus, ListTodo, CheckCircle,
} from 'lucide-react'
import type { ExtractedTask as ExtractedTaskType } from '@/lib/api'
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
  citations?: CitationSource[]
}

const ESL_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  APPROVED: { bg: 'rgba(74,124,89,0.08)',  text: '#4A7C59', border: 'rgba(74,124,89,0.20)' },
  VETOED:   { bg: 'rgba(176,74,58,0.08)',  text: '#B04A3A', border: 'rgba(176,74,58,0.20)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.08)', text: '#9B7A3D', border: 'rgba(155,122,61,0.20)' },
}

const GROQ_MODELS = [
  // Production
  { id: 'llama-3.3-70b-versatile',                    label: 'Llama 3.3 70B',      badge: 'Best',      group: 'Production' },
  { id: 'llama-3.1-8b-instant',                       label: 'Llama 3.1 8B',       badge: '560 t/s',   group: 'Production' },
  { id: 'openai/gpt-oss-120b',                        label: 'GPT OSS 120B',       badge: '500 t/s',   group: 'Production' },
  { id: 'openai/gpt-oss-20b',                         label: 'GPT OSS 20B',        badge: '1000 t/s',  group: 'Production' },
  { id: 'groq/compound',                              label: 'Groq Compound',      badge: '450 t/s',   group: 'Production' },
  { id: 'groq/compound-mini',                         label: 'Compound Mini',      badge: 'Fast',      group: 'Production' },
  // Preview
  { id: 'meta-llama/llama-4-scout-17b-16e-instruct',  label: 'Llama 4 Scout 17B',  badge: 'Preview',   group: 'Preview' },
  { id: 'moonshotai/kimi-k2-instruct-0905',           label: 'Kimi K2',            badge: '262K ctx',  group: 'Preview' },
  { id: 'qwen/qwen3-32b',                             label: 'Qwen3 32B',          badge: 'Preview',   group: 'Preview' },
]
const DEFAULT_MODEL = GROQ_MODELS[0].id

const SOURCE_OPTIONS = [
  { id: 'calendar', label: 'Calendar', icon: Calendar },
  { id: 'web',      label: 'Web',      icon: Globe },
  { id: 'goals',    label: 'Goals',    icon: Target },
  { id: 'memory',   label: 'Memory',   icon: StickyNote },
] as const
type SourceId = typeof SOURCE_OPTIONS[number]['id']
const ALL_SOURCE_IDS = SOURCE_OPTIONS.map(s => s.id) as SourceId[]

const EXAMPLE_PROMPTS = [
  { text: "What's on my agenda today?",       icon: Calendar,     desc: 'Review upcoming events' },
  { text: "Help me prioritize my goals",       icon: Target,       desc: 'Align work with values' },
  { text: "Summarize my week",                 icon: BarChart2,    desc: 'Reflect on recent activity' },
  { text: "How are my values being respected?", icon: ShieldCheck, desc: 'ESL transparency check' },
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

/* ─── Citation source pills ─── */
const CITATION_ICONS: Record<string, ReactElement | null> = {
  calendar: <Calendar size={11} />,
  globe:    <Globe size={11} />,
  target:   <Target size={11} />,
  memory:   <StickyNote size={11} />,
}

function CitationPills({ citations }: { citations?: CitationSource[] }) {
  if (!citations || citations.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {citations.map(c => (
        <span
          key={c.tool}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
          style={{
            background: 'var(--ec-surface-2, #f5f2ef)',
            border: '1px solid var(--ec-card-border)',
            color: 'var(--ec-text-muted)',
          }}
        >
          {CITATION_ICONS[c.icon] ?? null}
          {c.label}
        </span>
      ))}
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
      className="w-7 h-7 rounded-xl flex items-center justify-center text-[9px] font-bold shrink-0 select-none"
      style={{
        background: 'linear-gradient(145deg, #1a1a1a 0%, #3d3d3d 100%)',
        color: '#ffffff',
        boxShadow: '0 2px 6px rgba(0,0,0,0.18)',
      }}
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

/* ─── Markdown component map ─── */
const markdownComponents = {
  code({ node, className, children, ...props }: any) {
    const language = /language-(\w+)/.exec(className || '')?.[1]
    const content = String(children).replace(/\n$/, '')
    // Treat as block if it contains newlines or has a language hint
    const isBlock = content.includes('\n') || !!language
    if (!isBlock) {
      return <code className={className} {...props}>{children}</code>
    }
    return <CodeBlock language={language}>{content}</CodeBlock>
  },
  table({ children }: any) {
    return (
      <div style={{ overflowX: 'auto', margin: '0.75em 0' }}>
        <table style={{ minWidth: '100%' }}>{children}</table>
      </div>
    )
  },
  input({ checked, ...props }: any) {
    return (
      <input
        type="checkbox"
        checked={checked}
        readOnly
        style={{ accentColor: '#4A7C59', marginRight: '0.4em' }}
        {...props}
      />
    )
  },
  h1({ children }: any) {
    const text = String(children)
    if (/^(plan|schedule|agenda|summary|report):/i.test(text)) {
      return <ArtifactCard title={text}>{null}</ArtifactCard>
    }
    return <h1>{children}</h1>
  },
}

/* ═══════════════════════════════════════════════════ */
export default function ChatPage({ conversationId }: { conversationId?: string } = {}) {
  const { user } = useAuth()
  const router = useRouter()
  const initials = user?.email?.split('@')[0].substring(0, 2).toUpperCase() ?? 'U'

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput]       = useState('')
  const [isLoading, setIsLoading]       = useState(false)
  const [isThinking, setIsThinking]     = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [userScrolled, setUserScrolled] = useState(false)
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL)
  const [modelMenuOpen, setModelMenuOpen] = useState(false)
  const [rateLimitWarning, setRateLimitWarning] = useState<{ level: string; message: string } | null>(null)
  const rateLimitDismissedRef = useRef(false)
  const [rateLimitExceeded, setRateLimitExceeded] = useState<{ retryAfter: string; message: string } | null>(null)

  const [attachedFile, setAttachedFile] = useState<{ name: string; content: string } | null>(null)
  const [plusMenuOpen, setPlusMenuOpen] = useState(false)

  const [activeSources, setActiveSources] = useState<Set<SourceId>>(new Set(ALL_SOURCE_IDS))

  const [extractingFor, setExtractingFor] = useState<string | null>(null)
  const [extractedSuggestions, setExtractedSuggestions] = useState<Array<ExtractedTaskType & { _key: string }>>([])
  const [extractLoading, setExtractLoading] = useState(false)
  const [savedNoteFor, setSavedNoteFor] = useState<string | null>(null)

  const endRef       = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const textareaRef  = useRef<HTMLTextAreaElement>(null)
  const streamRef    = useRef<{ cancel: () => void } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Close menus on outside click
  useEffect(() => {
    if (!modelMenuOpen) return
    const handler = () => setModelMenuOpen(false)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [modelMenuOpen])

  useEffect(() => {
    if (!plusMenuOpen) return
    const handler = () => setPlusMenuOpen(false)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [plusMenuOpen])

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
    setMessages([])
    setLoadingHistory(true)
    api.chat.history(50, 0, conversationId)
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
  }, [conversationId])

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

  /* file attachment */
  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const content = ev.target?.result as string
      setAttachedFile({ name: file.name, content })
    }
    reader.readAsText(file)
    // Reset input so the same file can be re-selected
    e.target.value = ''
  }, [])

  /* send */
  const handleSend = async (text?: string) => {
    const userText = (text ?? input).trim()
    const userMessage = attachedFile
      ? `${userText ? userText + '\n\n' : ''}[Attached file: ${attachedFile.name}]\n\`\`\`\n${attachedFile.content.slice(0, 8000)}\n\`\`\``
      : userText
    if (!userMessage || isLoading) return

    setInput('')
    setAttachedFile(null)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setIsLoading(true)
    setIsThinking(true)
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
      setRateLimitExceeded(null)

      // Create a conversation if one doesn't exist yet, then redirect
      let activeConvId = conversationId
      if (!activeConvId) {
        const conv = await api.chat.conversations.create()
        activeConvId = conv.id
        router.replace(`/dashboard/chat/${activeConvId}`)
        window.dispatchEvent(new Event('ec:conversation-created'))
      }

      const selectedSources = activeSources.size < ALL_SOURCE_IDS.length
        ? Array.from(activeSources)
        : undefined  // undefined = all sources = no filter param sent

      const s = api.chat.stream(userMessage, {
        model: selectedModel,
        conversation_id: activeConvId,
        active_sources: selectedSources,
        onRateLimitWarning: (level, message) => { if (!rateLimitDismissedRef.current) setRateLimitWarning({ level, message }) },
        onRateLimitExceeded: (retryAfter, message) => {
          setRateLimitExceeded({ retryAfter, message })
          setIsLoading(false)
          setIsThinking(false)
          // Replace empty assistant bubble with the error message
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, content: `⚠️ ${message}`, streaming: false }
              : m
          ))
        },
        onToken: (token) => {
          setIsThinking(false)
          setMessages(prev => {
            const msgs = [...prev]
            const last = msgs[msgs.length - 1]
            if (last?.streaming) msgs[msgs.length - 1] = { ...last, content: last.content + token }
            return msgs
          })
        },
        onToolUse: (tool) => {
          setIsThinking(false)
          setActiveTool(tool)
        },
        onToolResult: () => setActiveTool(null),
        onDone: ({ citations }) => {
          if (citations && citations.length > 0) {
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, citations } : m
            ))
          }
        },
      })
      streamRef.current = s
      await s
      setActiveTool(null)
      setIsThinking(false)
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
      setIsThinking(false)
      setActiveTool(null)

      if (e instanceof Error && e.message === 'Stream cancelled') {
        // User hit Stop — just seal the bubble with whatever arrived
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, streaming: false } : m
        ))
      } else {
        const raw = e instanceof Error ? e.message : String(e)
        let userMsg: string

        if (raw.includes('Failed to fetch') || raw.includes('NetworkError') || raw.includes('fetch')) {
          userMsg = "Can't reach the server. Make sure the backend is running and try again."
        } else if (raw.includes('Stream connection lost')) {
          userMsg = "Connection dropped mid-response. Please try again."
        } else if (raw.includes('validation') || raw.includes('Pydantic') || raw.includes('validation error')) {
          userMsg = "The model returned an unexpected format. Try a different model or rephrase your message."
        } else if (raw.includes('401') || raw.includes('Unauthorized')) {
          userMsg = "Session expired. Please refresh the page and sign in again."
        } else if (raw.includes('503') || raw.includes('502') || raw.includes('unavailable')) {
          userMsg = "The AI service is temporarily unavailable. Try again in a moment."
        } else {
          userMsg = "Something went wrong. Please try again."
        }

        console.error('[chat] stream error:', raw)

        // Update the assistant bubble — works whether it's still streaming or already sealed
        setMessages(prev => prev.map(m => {
          if (m.id !== assistantId) return m
          const partial = m.content?.trim()
          return {
            ...m,
            streaming: false,
            content: partial
              ? `${partial}\n\n*— response interrupted: ${userMsg}*`
              : `⚠️ ${userMsg}`,
          }
        }))
      }
    } finally {
      streamRef.current = null
      setIsLoading(false)
    }
  }

  const handleStop = () => streamRef.current?.cancel()

  const handleExtractTasks = async (content: string, msgKey: string) => {
    setExtractingFor(msgKey)
    setExtractedSuggestions([])
    setExtractLoading(true)
    try {
      const result = await api.tasks.extract(content)
      setExtractedSuggestions((result.suggestions ?? []).map((s, i) => ({ ...s, _key: `${s.title}-${i}` })))
    } catch {
      setExtractedSuggestions([])
    } finally {
      setExtractLoading(false)
    }
  }

  const handleConfirmTask = async (suggestion: ExtractedTaskType & { _key: string }) => {
    try {
      await api.tasks.create({
        title: suggestion.title,
        description: suggestion.description ?? undefined,
        priority: suggestion.priority ?? 5,
        source_origin: 'chat_extract',
      })
      setExtractedSuggestions(prev => prev.filter(s => s._key !== suggestion._key))
    } catch {
      // silently ignore
    }
  }

  const handleSaveNote = async (content: string, msgKey: string) => {
    try {
      await api.values.create({
        type: 'preference',
        value: content.slice(0, 1000),
        priority: 5,
        metadata: { subtype: 'note', source: 'chat_response' },
      })
      setSavedNoteFor(msgKey)
      setTimeout(() => setSavedNoteFor(null), 3000)
    } catch {
      // silently ignore — note saving is best-effort
    }
  }

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
        <div className="mx-auto max-w-[700px] px-4 py-8 space-y-6">

          {loadingHistory && (
            <div className="space-y-5">
              {[120, 80, 160].map((w, i) => (
                <Skeleton key={i} className="h-4 rounded-full" style={{ width: `${w}px` }} />
              ))}
            </div>
          )}

          {/* Empty state */}
          {isEmpty && (
            <div className="flex flex-col items-center justify-center gap-8 pt-16 pb-8 text-center">
              {/* Logo */}
              <div className="relative">
                <div
                  className="w-16 h-16 rounded-3xl flex items-center justify-center text-base font-bold mx-auto select-none"
                  style={{
                    background: 'linear-gradient(145deg, #1a1a1a 0%, #3d3d3d 100%)',
                    color: '#ffffff',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.16), 0 2px 8px rgba(0,0,0,0.12)',
                  }}
                >
                  EC
                </div>
                <div
                  className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 flex items-center justify-center"
                  style={{ background: '#4A7C59', borderColor: 'var(--ec-page-bg)' }}
                >
                  <Sparkles size={10} color="#fff" />
                </div>
              </div>

              <div>
                <h2 className="text-xl font-semibold tracking-tight" style={{ color: 'var(--ec-text)' }}>
                  How can I help you today?
                </h2>
                <p className="text-sm mt-1.5" style={{ color: 'var(--ec-text-subtle)' }}>
                  Your AI companion — guided by your values, protected by ESL
                </p>
              </div>

              {/* Prompt cards */}
              <div className="grid grid-cols-2 gap-3 w-full max-w-[500px]">
                {EXAMPLE_PROMPTS.map(({ text, icon: Icon, desc }) => (
                  <button
                    key={text}
                    onClick={() => handleSend(text)}
                    className="prompt-card flex flex-col items-start gap-2 p-4 rounded-2xl text-left active:scale-[0.98]"
                    style={{
                      background: 'var(--ec-card-bg)',
                      border: '1px solid var(--ec-card-border)',
                      boxShadow: 'var(--ec-card-shadow)',
                    }}
                  >
                    <div
                      className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
                      style={{ background: 'rgba(74,124,89,0.1)' }}
                    >
                      <Icon size={15} style={{ color: '#4A7C59' }} />
                    </div>
                    <div>
                      <p className="text-sm font-medium leading-snug" style={{ color: 'var(--ec-text)' }}>{text}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>{desc}</p>
                    </div>
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
                          background: 'var(--ec-surface-2)',
                          color: 'var(--ec-text)',
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
                <div className="pl-9 text-sm w-full">
                  {msg.streaming && isThinking && !msg.content ? (
                    <div className="flex items-center gap-2 h-6">
                      <div className="flex gap-1">
                        {[0,1,2].map(i => (
                          <span key={i} className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.18}s`, background: '#c0c0c0' }} />
                        ))}
                      </div>
                      <span className="text-xs" style={{ color: '#b0b0b0' }}>Thinking…</span>
                    </div>
                  ) : msg.content ? (
                    <>
                      {msg.streaming && activeTool && (
                        <div
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs mb-3"
                          style={{ background: 'rgba(74,124,89,0.08)', color: '#4A7C59', border: '1px solid rgba(74,124,89,0.18)' }}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-[#4A7C59] animate-pulse" />
                          {activeTool === 'web_search' && 'Searching the web…'}
                          {activeTool === 'query_calendar' && 'Checking your calendar…'}
                          {activeTool === 'query_memory' && 'Recalling context…'}
                          {activeTool === 'get_user_goals' && 'Checking your goals…'}
                          {activeTool === 'create_note' && 'Saving note…'}
                        </div>
                      )}
                      <div className="chat-prose max-w-none" style={{ whiteSpace: 'pre-wrap' }}>
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={markdownComponents}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                      {msg.streaming && <Cursor />}
                    </>
                  ) : null}
                  <CitationPills citations={msg.citations} />
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

                {/* Follow-up actions — only on completed, non-streaming messages */}
                {!msg.streaming && msg.content && (
                  <div className="pl-9 mt-2">
                    {/* Action buttons */}
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleExtractTasks(msg.content, msg.id)}
                        disabled={extractLoading && extractingFor === msg.id}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors ${extractLoading && extractingFor === msg.id ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80'}`}
                        style={{
                          background: 'var(--ec-surface-2, rgba(0,0,0,0.04))',
                          color: 'var(--ec-text-subtle)',
                          border: '1px solid var(--ec-card-border)',
                        }}
                        title="Extract tasks from this response"
                      >
                        <ListTodo size={11} />
                        Extract tasks
                      </button>
                      <button
                        onClick={() => handleSaveNote(msg.content, msg.id)}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors hover:opacity-80"
                        style={{
                          background: savedNoteFor === msg.id
                            ? 'rgba(74,124,89,0.10)'
                            : 'var(--ec-surface-2, rgba(0,0,0,0.04))',
                          color: savedNoteFor === msg.id ? '#4A7C59' : 'var(--ec-text-subtle)',
                          border: '1px solid var(--ec-card-border)',
                        }}
                        title="Save this response as a note"
                      >
                        {savedNoteFor === msg.id
                          ? <><CheckCircle size={11} /> Saved</>
                          : <><BookmarkPlus size={11} /> Save as note</>
                        }
                      </button>
                    </div>

                    {/* Extract panel */}
                    {extractingFor === msg.id && (
                      <div
                        className="mt-3 rounded-xl p-4"
                        style={{
                          background: 'var(--ec-card-bg)',
                          border: '1px solid var(--ec-card-border)',
                        }}
                      >
                        <p className="text-xs font-medium mb-2" style={{ color: 'var(--ec-text)' }}>
                          Extracted tasks
                        </p>
                        {extractLoading ? (
                          <p className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>Analysing…</p>
                        ) : extractedSuggestions.length === 0 ? (
                          <p className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>No tasks found.</p>
                        ) : (
                          <ul className="space-y-2">
                            {extractedSuggestions.map((s) => (
                              <li key={s._key} className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="text-sm font-medium truncate" style={{ color: 'var(--ec-text)' }}>
                                    {s.title}
                                  </p>
                                  {s.description && (
                                    <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--ec-text-subtle)' }}>
                                      {s.description}
                                    </p>
                                  )}
                                </div>
                                <button
                                  onClick={() => handleConfirmTask(s)}
                                  aria-label={`Add task: ${s.title}`}
                                  className="shrink-0 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors hover:opacity-80"
                                  style={{ background: '#4A7C59', color: '#fff' }}
                                >
                                  Add
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                        <button
                          onClick={() => { setExtractingFor(null); setExtractedSuggestions([]) }}
                          aria-label="Dismiss extracted tasks"
                          className="mt-2 text-xs hover:opacity-70"
                          style={{ color: 'var(--ec-text-subtle)' }}
                        >
                          Dismiss
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}

          <div ref={endRef} />
        </div>
      </div>

      {/* ── Rate limit banners ── */}
      {rateLimitExceeded && (
        <div className="shrink-0 mx-4 mb-2 px-4 py-3 rounded-xl flex items-start justify-between gap-3 text-sm"
          style={{ background: 'rgba(176,74,58,0.08)', border: '1px solid rgba(176,74,58,0.25)', color: '#B04A3A' }}>
          <div>
            <p className="font-medium">Token limit reached</p>
            <p className="text-xs mt-0.5 opacity-80">{rateLimitExceeded.message}</p>
          </div>
          <button onClick={() => setRateLimitExceeded(null)} className="shrink-0 text-lg leading-none opacity-50 hover:opacity-100">×</button>
        </div>
      )}
      {rateLimitWarning && !rateLimitExceeded && (
        <div className="shrink-0 mx-4 mb-2 px-4 py-3 rounded-xl flex items-start justify-between gap-3 text-sm"
          style={{
            background: rateLimitWarning.level === 'high' ? 'rgba(176,120,58,0.08)' : 'rgba(155,155,58,0.06)',
            border: `1px solid ${rateLimitWarning.level === 'high' ? 'rgba(176,120,58,0.25)' : 'rgba(155,155,58,0.20)'}`,
            color: rateLimitWarning.level === 'high' ? '#9B6A2A' : '#7A7A2A',
          }}>
          <p className="text-xs">{rateLimitWarning.message}</p>
          <button onClick={() => { rateLimitDismissedRef.current = true; setRateLimitWarning(null) }} className="shrink-0 text-lg leading-none opacity-50 hover:opacity-100">×</button>
        </div>
      )}

      {/* ── Input card ── */}
      <div className="shrink-0 px-4" style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
        <div
          className="mx-auto max-w-[700px] rounded-2xl transition-shadow focus-within:shadow-[0_2px_20px_rgba(0,0,0,0.12)]"
          style={{
            background: 'var(--ec-card-bg)',
            border: '1px solid var(--ec-border)',
            boxShadow: '0 2px 12px rgba(0,0,0,0.07)',
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
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Message your companion…"
              rows={1}
              className="w-full resize-none text-sm outline-none bg-transparent leading-relaxed placeholder:text-[#b0b0b0]"
              style={{ color: 'var(--ec-text)', maxHeight: '140px', overflowY: 'auto' }}
            />
          </div>

          {/* Attached file chip */}
          {attachedFile && (
            <div className="flex items-center gap-2 px-4 pt-2">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs"
                style={{ background: 'rgba(0,0,0,0.06)', color: '#6b6b6b', border: '1px solid rgba(0,0,0,0.08)' }}>
                <span className="max-w-[180px] truncate">{attachedFile.name}</span>
                <button
                  onClick={() => setAttachedFile(null)}
                  className="shrink-0 ml-1 opacity-50 hover:opacity-100 transition-opacity"
                  aria-label="Remove attachment"
                >×</button>
              </div>
            </div>
          )}

          {/* Bottom bar */}
          <div className="flex items-center justify-between px-3 pb-2.5 pt-1">
            {/* Left: Plus menu */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.csv,.json,.py,.js,.ts,.html,.css,.xml,.yaml,.yml,.log"
              className="hidden"
              onChange={handleFileChange}
            />
            <div className="relative">
              <button
                onClick={e => { e.stopPropagation(); setPlusMenuOpen(v => !v) }}
                disabled={isLoading}
                className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-black/5 disabled:opacity-30"
                aria-label="More options"
                style={{ color: '#9e9e9e' }}
              >
                <Plus size={16} />
              </button>

              {plusMenuOpen && (
                <div
                  className="absolute bottom-full mb-2 left-0 z-50 rounded-xl py-1.5 min-w-[220px]"
                  style={{
                    background: '#fff',
                    border: '1px solid rgba(0,0,0,0.10)',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                  }}
                  onClick={e => e.stopPropagation()}
                >
                  {/* Attach file */}
                  <button
                    onClick={() => { fileInputRef.current?.click(); setPlusMenuOpen(false) }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors hover:bg-black/4"
                    style={{ color: '#0a0a0a' }}
                  >
                    <Paperclip size={15} style={{ color: '#6b6b6b' }} />
                    Attach file
                  </button>

                  {/* Web search */}
                  <button
                    onClick={() => {
                      setInput(prev => prev ? prev : '/search ')
                      textareaRef.current?.focus()
                      setPlusMenuOpen(false)
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors hover:bg-black/4"
                    style={{ color: '#0a0a0a' }}
                  >
                    <Globe size={15} style={{ color: '#6b6b6b' }} />
                    Search the web
                  </button>

                  <div style={{ height: '1px', background: 'rgba(0,0,0,0.06)', margin: '4px 0' }} />

                  {/* Calendar */}
                  <button
                    onClick={() => {
                      handleSend("What's on my calendar today?")
                      setPlusMenuOpen(false)
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors hover:bg-black/4"
                    style={{ color: '#0a0a0a' }}
                  >
                    <Calendar size={15} style={{ color: '#6b6b6b' }} />
                    Check calendar
                  </button>

                  {/* Goals */}
                  <button
                    onClick={() => {
                      handleSend("Show me my active goals and progress")
                      setPlusMenuOpen(false)
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors hover:bg-black/4"
                    style={{ color: '#0a0a0a' }}
                  >
                    <Target size={15} style={{ color: '#6b6b6b' }} />
                    Review goals
                  </button>

                  {/* Save note */}
                  <button
                    onClick={() => {
                      setInput('Remember that ')
                      textareaRef.current?.focus()
                      setPlusMenuOpen(false)
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors hover:bg-black/4"
                    style={{ color: '#0a0a0a' }}
                  >
                    <StickyNote size={15} style={{ color: '#6b6b6b' }} />
                    Save a note
                  </button>
                </div>
              )}
            </div>

            {/* Center: source toggles */}
            <div className="flex items-center gap-1">
              {SOURCE_OPTIONS.map(({ id, label, icon: Icon }) => {
                const on = activeSources.has(id)
                return (
                  <button
                    key={id}
                    onClick={() => setActiveSources(prev => {
                      const next = new Set(prev)
                      if (next.has(id)) { next.delete(id) } else { next.add(id) }
                      // Keep at least one source active
                      if (next.size === 0) return prev
                      return next
                    })}
                    title={on ? `Disable ${label}` : `Enable ${label}`}
                    className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-all"
                    style={{
                      background: on ? 'rgba(0,0,0,0.07)' : 'transparent',
                      color: on ? '#3d3d3d' : '#c0c0c0',
                      border: `1px solid ${on ? 'rgba(0,0,0,0.12)' : 'transparent'}`,
                    }}
                  >
                    <Icon size={10} />
                    <span className="hidden sm:inline">{label}</span>
                  </button>
                )
              })}
            </div>

            {/* Right: model selector + send/stop */}
            <div className="flex items-center gap-2">
              {/* Model selector */}
              <div className="relative">
                <button
                  onClick={() => setModelMenuOpen(v => !v)}
                  disabled={isLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors hover:bg-black/6 disabled:opacity-50"
                  style={{
                    background: 'rgba(0,0,0,0.04)',
                    color: '#6b6b6b',
                    border: '1px solid rgba(0,0,0,0.06)',
                  }}
                >
                  <Cpu size={10} />
                  {GROQ_MODELS.find(m => m.id === selectedModel)?.label ?? selectedModel}
                  <ChevronDown size={10} />
                </button>
                {modelMenuOpen && (
                  <div
                    className="absolute bottom-full mb-2 right-0 z-50 rounded-xl overflow-hidden py-1 min-w-[200px]"
                    style={{
                      background: '#fff',
                      border: '1px solid rgba(0,0,0,0.10)',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                    }}
                  >
                    {(['Production', 'Preview'] as const).map(group => (
                      <div key={group}>
                        <div className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#c0c0c0' }}>{group}</div>
                        {GROQ_MODELS.filter(m => m.group === group).map(m => (
                          <button
                            key={m.id}
                            onClick={() => { setSelectedModel(m.id); setModelMenuOpen(false) }}
                            className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-left transition-colors hover:bg-black/4"
                            style={{ color: m.id === selectedModel ? '#0a0a0a' : '#6b6b6b', fontWeight: m.id === selectedModel ? 600 : 400 }}
                          >
                            <span>{m.label}</span>
                            <span className="ml-2 px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'rgba(0,0,0,0.05)', color: '#9e9e9e' }}>
                              {m.badge}
                            </span>
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
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
                  disabled={!input.trim() && !attachedFile}
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
