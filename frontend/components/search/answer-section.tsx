"use client"

import * as React from "react"
import { Lightbulb } from "lucide-react"
import { cn } from "@/lib/utils"

interface AnswerSectionProps {
  content: string
  className?: string
}

export function AnswerSection({ content, className }: AnswerSectionProps) {
  return (
    <div className={cn("space-y-3", className)}>
      {/* Header */}
      <div className="flex items-center gap-2">
        <Lightbulb className="h-6 w-6 text-[#525252]" />
        <span className="text-base font-bold text-[#404040]">Answer</span>
      </div>

      {/* Content */}
      <div className="text-sm font-bold leading-[160%] text-[#525252]">
        <AnswerContent content={content} />
      </div>
    </div>
  )
}

function AnswerContent({ content }: { content: string }) {
  // Simple markdown-like parsing for display
  const lines = content.split("\n")

  return (
    <div className="space-y-4">
      {lines.map((line, index) => {
        // Handle bullet points
        if (line.startsWith("- ") || line.startsWith("• ")) {
          return (
            <div key={index} className="flex gap-2 pl-4">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#525252]" />
              <span>{parseBoldText(line.slice(2))}</span>
            </div>
          )
        }

        // Handle numbered lists
        const numberedMatch = line.match(/^(\d+)\.\s/)
        if (numberedMatch) {
          return (
            <div key={index} className="flex gap-2 pl-4">
              <span className="shrink-0 text-[#525252]">{numberedMatch[1]}.</span>
              <span>{parseBoldText(line.slice(numberedMatch[0].length))}</span>
            </div>
          )
        }

        // Handle headers (##)
        if (line.startsWith("## ")) {
          return (
            <h3 key={index} className="mt-6 text-base font-bold text-[#404040]">
              {line.slice(3)}
            </h3>
          )
        }

        // Regular paragraph with bold parsing
        if (line.trim()) {
          return <p key={index}>{parseBoldText(line)}</p>
        }

        return null
      })}
    </div>
  )
}

function parseBoldText(text: string): React.ReactNode {
  if (!text.includes("**")) {
    return text
  }

  const parts = text.split(/\*\*(.*?)\*\*/g)
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-bold text-[#404040]">{part}</strong>
    ) : (
      <React.Fragment key={i}>{part}</React.Fragment>
    )
  )
}
