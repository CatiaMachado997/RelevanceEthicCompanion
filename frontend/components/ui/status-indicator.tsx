import * as React from 'react'
import {
  CheckCircle,
  XCircle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Info
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type StatusType =
  | 'success'
  | 'error'
  | 'warning'
  | 'info'
  | 'esl-approved'
  | 'esl-vetoed'
  | 'esl-modified'

interface StatusIndicatorProps {
  type: StatusType
  message: string
  className?: string
}

const config: Record<StatusType, { icon: React.ComponentType<{ className?: string }>; color: string; bg: string }> = {
  success: {
    icon: CheckCircle,
    color: 'text-[#6B9B7F]',
    bg: 'bg-[#6B9B7F]/10'
  },
  error: {
    icon: XCircle,
    color: 'text-[#B8847A]',
    bg: 'bg-[#B8847A]/10'
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-[#C4A574]',
    bg: 'bg-[#C4A574]/10'
  },
  info: {
    icon: Info,
    color: 'text-[#8799A8]',
    bg: 'bg-[#8799A8]/10'
  },
  'esl-approved': {
    icon: Shield,
    color: 'text-[#6B9B7F]',
    bg: 'bg-[#6B9B7F]/10'
  },
  'esl-vetoed': {
    icon: ShieldAlert,
    color: 'text-[#B8847A]',
    bg: 'bg-[#B8847A]/10'
  },
  'esl-modified': {
    icon: ShieldCheck,
    color: 'text-[#8799A8]',
    bg: 'bg-[#8799A8]/10'
  }
}

export function StatusIndicator({
  type,
  message,
  className
}: StatusIndicatorProps) {
  const { icon: Icon, color, bg } = config[type]

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg",
        bg,
        className
      )}
      role="status"
      aria-live="polite"
    >
      <Icon className={cn("h-4 w-4", color)} />
      <span className={cn("text-sm font-medium", color)}>{message}</span>
    </div>
  )
}
