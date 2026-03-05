import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  className?: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  className
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4 text-center",
        className
      )}
      role="status"
      aria-label={title}
    >
      <Icon className="h-8 w-8 text-[#D4D0C8] mb-4" />
      <h3 className="text-lg font-medium text-[#1F1C18] mb-2">{title}</h3>
      <p className="text-sm text-[#5C5850] max-w-sm">{description}</p>
    </div>
  )
}
