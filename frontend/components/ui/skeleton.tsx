import { cn } from "@/lib/utils"

function Skeleton({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "bg-[#f5f5f5] animate-pulse rounded-lg",
        "relative overflow-hidden",
        "before:absolute before:inset-0",
        "before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent",
        "before:animate-shimmer",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
