'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

interface CodeBlockProps {
  language?: string
  children: string
}

export function CodeBlock({ language, children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(children)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className="relative group my-3"
      style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--ec-card-border)' }}
    >
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{ background: '#161b22', borderBottom: '1px solid #30363d' }}
      >
        <span
          className="text-[10px] font-mono uppercase tracking-wider"
          style={{ color: '#8b949e' }}
        >
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded transition-colors"
          style={{
            color: copied ? '#4A7C59' : '#8b949e',
            background: copied ? 'rgba(74,124,89,0.1)' : 'transparent',
          }}
          aria-label={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? <Check size={10} /> : <Copy size={10} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      {/* Code */}
      <pre style={{ margin: 0, background: '#0d1117', borderRadius: 0 }}>
        <code
          className={language ? `language-${language}` : ''}
          style={{
            display: 'block',
            padding: '0.9em 1em',
            overflowX: 'auto',
            fontFamily: "'SF Mono', 'Fira Code', monospace",
            fontSize: '0.78rem',
            lineHeight: 1.6,
            color: '#e6edf3',
            background: 'transparent',
          }}
        >
          {children}
        </code>
      </pre>
    </div>
  )
}
