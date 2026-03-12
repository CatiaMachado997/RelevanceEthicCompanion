import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "placeholder:text-[#9e9e9e] selection:bg-[#0a0a0a] selection:text-white h-10 w-full min-w-0 rounded-xl border border-[rgba(0,0,0,0.12)] bg-white px-3 py-2 text-sm text-[#0a0a0a] transition-all duration-150 outline-none",
        "file:text-foreground file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-[#0a0a0a] focus-visible:ring-2 focus-visible:ring-[#0a0a0a]/10",
        "aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Input }
