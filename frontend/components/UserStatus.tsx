'use client'
import { useState, useEffect } from 'react'
import * as Popover from '@radix-ui/react-popover'

const STATUS_OPTIONS = [
  { value: 'available', label: 'Available', color: 'bg-green-500' },
  { value: 'focus', label: 'Focus', color: 'bg-yellow-500' },
  { value: 'do_not_disturb', label: 'Do Not Disturb', color: 'bg-red-500' },
  { value: 'away', label: 'Away', color: 'bg-gray-400' },
]

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

export function UserStatus() {
  const [status, setStatus] = useState('available')
  const [open, setOpen] = useState(false)

  useEffect(() => {
    fetch(`${API_URL}/api/status/`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setStatus(d.status))
      .catch(() => {})
  }, [])

  const updateStatus = async (value: string) => {
    try {
      await fetch(`${API_URL}/api/status/`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: value }),
      })
      setStatus(value)
    } catch {}
    setOpen(false)
  }

  const current = STATUS_OPTIONS.find(s => s.value === status) ?? STATUS_OPTIONS[0]

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800">
          <span className={`w-2.5 h-2.5 rounded-full ${current.color}`} />
          <span className="text-sm">{current.label}</span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-lg shadow-lg p-2 w-48 z-50"
          sideOffset={5}
        >
          {STATUS_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => updateStatus(opt.value)}
              className="flex items-center gap-2 w-full px-3 py-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-sm"
            >
              <span className={`w-2 h-2 rounded-full ${opt.color}`} />
              {opt.label}
            </button>
          ))}
          <Popover.Arrow className="fill-white dark:fill-gray-900" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
