'use client'

import { Shield } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'

interface ESLIndicatorProps {
  status: 'approved' | 'vetoed' | 'modified'
  reason: string
  className?: string
  pulse?: boolean
}

const statusColors = {
  approved: 'ring-[#6B9B7F]/30 bg-[#6B9B7F]/10',
  vetoed: 'ring-[#B8847A]/30 bg-[#B8847A]/10',
  modified: 'ring-[#8799A8]/30 bg-[#8799A8]/10'
}

export function ESLIndicator({
  status,
  reason,
  className,
  pulse = false
}: ESLIndicatorProps) {
  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "h-2 w-2 rounded-full bg-[#D4D0C8] transition-all duration-150",
              "opacity-0 group-hover:opacity-100",
              "group-hover:h-4 group-hover:w-4 group-hover:ring-2",
              statusColors[status],
              pulse && "animate-esl-pulse",
              className
            )}
            role="status"
            aria-live="polite"
            aria-label={`ESL decision: ${status}`}
          />
        </TooltipTrigger>
        <TooltipContent
          side="left"
          className="bg-[#48443D] text-white border-[#5C5850] rounded-lg"
        >
          <div className="flex items-center gap-2">
            <Shield className="h-3 w-3" />
            <span className="text-xs font-medium">{reason}</span>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
