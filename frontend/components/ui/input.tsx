import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "file:text-foreground placeholder:text-[#A3A3A3] selection:bg-[#171717] selection:text-white border-[#E5E5E5] h-10 w-full min-w-0 rounded-lg border bg-white px-3 py-2 text-sm shadow-md transition-all duration-150 outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 text-[#171717]",
        "focus-visible:border-[#171717] focus-visible:ring-2 focus-visible:ring-[#171717]/20",
        "hover:border-[#E5E5E5]",
        "aria-invalid:ring-destructive/20 aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Input }
