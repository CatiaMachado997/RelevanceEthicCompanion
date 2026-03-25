'use client'
import { cn } from '@/lib/utils'

interface FilterChip<T extends string = string> {
  value: T | null
  label: string
  count?: number
}
interface FilterChipsProps<T extends string = string> {
  chips: FilterChip<T>[]
  selected: T | null
  onChange: (value: T | null) => void
  className?: string
}

export function FilterChips<T extends string = string>({
  chips, selected, onChange, className
}: FilterChipsProps<T>) {
  return (
    <div className={cn('flex flex-wrap gap-1.5', className)}>
      {chips.map((chip) => (
        <button
          key={chip.value ?? 'all'}
          onClick={() => onChange(chip.value)}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium transition-colors',
            selected === chip.value
              ? 'bg-[#1a1a1a] text-white'
              : 'border border-[#e0e0e0] text-[#6b6b6b] hover:bg-[#f5f5f5]'
          )}
        >
          {chip.label}
          {chip.count !== undefined && (
            <span className="ml-1.5 opacity-70">{chip.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}
