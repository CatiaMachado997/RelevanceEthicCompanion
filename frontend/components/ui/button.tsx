import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-150 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-0",
  {
    variants: {
      variant: {
        default: "bg-gradient-to-r from-[#171717] to-[#525252] text-white hover:from-[#525252] hover:to-[#525252] shadow-md shadow-none/10 hover:shadow-md hover:shadow-none/20 ",
        destructive:
          "bg-gradient-to-r from-[#EF4444] to-[#DC2626] text-white hover:from-[#DC2626] hover:to-[#B91C1C] shadow-md shadow-none hover:shadow-md hover:shadow-none ",
        outline:
          "border border-[#E5E5E5] bg-white hover:bg-[#F5F5F5] hover:text-[#171717] hover:border-[#E5E5E5] text-[#525252] ",
        secondary:
          "bg-[#F5F5F5] text-[#171717] hover:bg-[#E5E5E5] ",
        ghost:
          "hover:bg-[#F5F5F5] hover:text-[#171717] text-[#525252] ",
        link: "text-[#171717] underline-offset-4 hover:underline hover:text-[#525252]",
      },
      size: {
        default: "h-10 px-4 py-2 has-[>svg]:px-3",
        sm: "h-9 rounded-lg gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-11 rounded-lg px-6 has-[>svg]:px-4",
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
