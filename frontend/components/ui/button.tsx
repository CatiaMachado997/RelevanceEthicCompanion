import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-all duration-150 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-[#000000] focus-visible:ring-offset-0",
  {
    variants: {
      variant: {
        default:
          "bg-[#000000] text-white hover:bg-[#333333]",
        destructive:
          "bg-[#EF4444] text-white hover:bg-[#DC2626]",
        outline:
          "border border-[rgba(0,0,0,0.15)] bg-white text-[#0a0a0a] hover:bg-[#f5f5f5]",
        secondary:
          "bg-[#f5f5f5] text-[#0a0a0a] hover:bg-[#e5e5e5]",
        ghost:
          "hover:bg-[#f5f5f5] text-[#6b6b6b] hover:text-[#0a0a0a]",
        link: "text-[#0a0a0a] underline-offset-4 hover:underline",
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
