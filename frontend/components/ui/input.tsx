import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "placeholder:text-[#b0a6b4] selection:bg-[#332b36] selection:text-white h-10 w-full min-w-0 rounded-xl border border-[#e4dee7] bg-white px-3 py-2 text-sm text-[#332b36] transition-all duration-150 outline-none",
        "file:text-foreground file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-[#332b36] focus-visible:ring-2 focus-visible:ring-[#332b36]/10",
        "aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Input }
