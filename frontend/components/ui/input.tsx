import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "placeholder:text-[#9e9e9e] selection:bg-[#1a1a1a] selection:text-white h-10 w-full min-w-0 rounded-lg border border-[#e0e0e0] bg-white px-3 py-2 text-sm text-[#1a1a1a] transition-all duration-150 outline-none",
        "file:text-foreground file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-[#1a1a1a] focus-visible:ring-2 focus-visible:ring-[#1a1a1a]/8",
        "aria-invalid:border-[#d32f2f] aria-invalid:ring-[#d32f2f]/10",
        className
      )}
      {...props}
    />
  )
}

export { Input }
