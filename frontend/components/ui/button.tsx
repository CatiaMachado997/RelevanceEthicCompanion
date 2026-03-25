import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-150 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-1",
  {
    variants: {
      variant: {
        default:
          "bg-[#1a1a1a] text-white hover:bg-[#2d2d2d] active:scale-[0.98]",
        destructive:
          "bg-[#d32f2f] text-white hover:bg-[#b71c1c]",
        outline:
          "border border-[#e0e0e0] bg-white text-[#1a1a1a] hover:bg-[#f5f5f5]",
        secondary:
          "bg-[#f0f0f0] text-[#1a1a1a] hover:bg-[#e0e0e0]",
        ghost:
          "hover:bg-[#f0f0f0] text-[#6b6b6b] hover:text-[#1a1a1a]",
        link: "text-[#1a1a1a] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-5 py-2 has-[>svg]:px-4",
        sm: "h-8 px-4 gap-1.5 has-[>svg]:px-3",
        lg: "h-11 px-6 has-[>svg]:px-5",
        icon: "size-10",
        "icon-sm": "size-9",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
