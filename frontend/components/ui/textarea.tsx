import * as React from "react"

import { cn } from "@/lib/utils"

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[80px] w-full rounded-xl border border-[rgba(0,0,0,0.12)] bg-background px-3 py-2 text-sm text-[#0a0a0a] placeholder:text-[#9e9e9e] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0a0a0a]/10 focus-visible:border-[#0a0a0a] disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
