import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[#171717] text-white shadow hover:bg-[#333333]",
        brand:
          "border-transparent bg-[#171717] text-white shadow hover:bg-[#333333]",
        secondary:
          "border-transparent bg-[#F5F5F5] text-[#171717] hover:bg-[#E5E5E5]",
        destructive:
          "border-transparent bg-destructive text-white shadow hover:bg-destructive/80",
        outline: "text-[#525252] border-[#E5E5E5]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
