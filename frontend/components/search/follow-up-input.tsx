"use client"

import * as React from "react"
import { PlusCircle, Mic, Paperclip, ArrowUp } from "lucide-react"
import { cn } from "@/lib/utils"

interface FollowUpInputProps {
  onSubmit?: (message: string) => void
  placeholder?: string
  className?: string
}

export function FollowUpInput({
  onSubmit,
  placeholder = "Ask a follow up...",
  className,
}: FollowUpInputProps) {
  const [value, setValue] = React.useState("")
  const inputRef = React.useRef<HTMLInputElement>(null)

  const handleSubmit = () => {
    if (!value.trim()) return

    if (onSubmit) {
      onSubmit(value)
    } else {
      alert(`Follow-up question: ${value}`)
    }
    setValue("")
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className={cn("flex items-center gap-3", className)}>
      {/* Input Container */}
      <div className="flex flex-1 items-center gap-2 rounded-full border border-[#E5E5E5] bg-white px-3 py-3 shadow-md">
        <PlusCircle className="h-6 w-6 shrink-0 text-[#404040]" />

        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-base text-[#404040] outline-none placeholder:text-[#525252]"
        />

        <div className="flex shrink-0 items-center gap-3">
          <button
            type="button"
            onClick={() => console.log("Voice input")}
            className="text-[#404040] hover:text-[#171717]"
          >
            <Mic className="h-6 w-6" />
          </button>

          <button
            type="button"
            onClick={() => console.log("Attach file")}
            className="text-[#404040] hover:text-[#171717]"
          >
            <Paperclip className="h-6 w-6" />
          </button>
        </div>
      </div>

      {/* Send Button */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!value.trim()}
        className="flex h-10 w-10 items-center justify-center rounded-full bg-[#171717] text-white transition-colors hover:bg-[#4338CA] disabled:opacity-50"
      >
        <ArrowUp className="h-6 w-6" />
      </button>
    </div>
  )
}
