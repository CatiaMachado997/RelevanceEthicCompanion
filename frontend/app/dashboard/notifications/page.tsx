'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Bell, CheckCircle2, Info, AlertTriangle, ShieldAlert } from 'lucide-react'
import { notificationsApi, Notification } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { PageHeader } from '@/components/ui/page-header'
import { FilterChips } from '@/components/ui/filter-chips'

type ReadFilter = 'unread' | 'read'

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function iconForType(type: string) {
  if (type === 'goal_completed') return CheckCircle2
  if (type.includes('esl') || type.includes('block') || type.includes('shield')) return ShieldAlert
  if (type === 'warning') return AlertTriangle
  return Info
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [markingAll, setMarkingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [readFilter, setReadFilter] = useState<ReadFilter | null>(null)

  const load = useCallback(async () => {
    try {
      const { notifications: data, unread_count } = await notificationsApi.list()
      setNotifications(data)
      setUnreadCount(unread_count)
      setError(null)
    } catch {
      setError('Failed to load notifications.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleMarkRead = async (id: string) => {
    try {
      await notificationsApi.markRead(id)
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch {
      setError('Failed to mark as read.')
    }
  }

  const handleMarkAllRead = async () => {
    setMarkingAll(true)
    try {
      await notificationsApi.markAllRead()
      setNotifications(prev => prev.map(n => ({ ...n, read: true })))
      setUnreadCount(0)
    } catch {
      setError('Failed to mark all as read.')
    } finally {
      setMarkingAll(false)
    }
  }

  const displayedNotifications = readFilter
    ? notifications.filter(n => readFilter === 'unread' ? !n.read : n.read)
    : notifications

  return (
    <div className="max-w-4xl space-y-5">
      <PageHeader
        title="Notifications"
        subtitle="Stay updated with your activity and ESL decisions"
        action={
          unreadCount > 0 ? (
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="bg-[#1a1a1a]/10 text-[#1a1a1a] border-[#1a1a1a]/20 rounded-full">
                {unreadCount} unread
              </Badge>
              <button
                className="px-4 py-1.5 rounded-full text-sm font-medium border border-[#e0e0e0] text-[#6b6b6b] hover:bg-[#f5f5f5] transition-colors disabled:opacity-50"
                disabled={markingAll}
                onClick={handleMarkAllRead}
              >
                {markingAll ? 'Marking…' : 'Mark all read'}
              </button>
            </div>
          ) : undefined
        }
      />

      <FilterChips<ReadFilter>
        chips={[
          { value: null, label: 'All', count: notifications.length },
          { value: 'unread', label: 'Unread', count: unreadCount },
          { value: 'read', label: 'Read', count: notifications.length - unreadCount },
        ]}
        selected={readFilter}
        onChange={setReadFilter}
      />

      {error && <p className="text-sm text-[#DC2626]">{error}</p>}

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full rounded-2xl" />)}
        </div>
      )}

      {!loading && displayedNotifications.length > 0 && (
        <div className="space-y-3">
          {displayedNotifications.map((notification) => {
            const Icon = iconForType(notification.type)
            return (
              <Card
                key={notification.id}
                className={`border-[#e0e0e0] rounded-2xl transition-all hover:shadow-md cursor-pointer ${
                  !notification.read ? 'bg-[#f5f5f5]' : ''
                }`}
                onClick={() => !notification.read && handleMarkRead(notification.id)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start gap-4">
                    <div className={`mt-1 ${notification.read ? 'text-[#6b6b6b]' : 'text-[#1a1a1a]'}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <CardTitle className="text-base text-[#1a1a1a]">
                          {notification.title}
                        </CardTitle>
                        {!notification.read && (
                          <div className="h-2 w-2 rounded-full bg-[#1a1a1a]" />
                        )}
                      </div>
                      <p className="text-sm text-[#6b6b6b]">{notification.message}</p>
                      <p className="text-xs text-[#9e9e9e]">{timeAgo(notification.created_at)}</p>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            )
          })}
        </div>
      )}

      {!loading && displayedNotifications.length === 0 && (
        <Card className="border-[#e0e0e0] rounded-2xl p-12 text-center">
          <Bell className="h-10 w-10 mx-auto text-[#9e9e9e]" />
          <h3 className="font-semibold mt-4 text-lg text-[#1a1a1a]">All caught up!</h3>
          <p className="text-[#6b6b6b] mt-2">You have no notifications</p>
        </Card>
      )}
    </div>
  )
}
