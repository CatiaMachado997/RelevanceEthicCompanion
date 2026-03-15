'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { TopHeader } from '@/components/top-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Bell, CheckCircle2, Info, AlertTriangle, ShieldAlert } from 'lucide-react'
import { notificationsApi, Notification } from '@/lib/api'

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
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

  const load = useCallback(async () => {
    try {
      const { notifications: data, unread_count } = await notificationsApi.list()
      setNotifications(data)
      setUnreadCount(unread_count)
    } catch (error) {
      console.error('Failed to load notifications:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleMarkRead = async (id: string) => {
    try {
      await notificationsApi.markRead(id)
      await load()
    } catch (error) {
      console.error('Failed to mark notification as read:', error)
    }
  }

  const handleMarkAllRead = async () => {
    setMarkingAll(true)
    try {
      await notificationsApi.markAllRead()
      await load()
    } catch (error) {
      console.error('Failed to mark all as read:', error)
    } finally {
      setMarkingAll(false)
    }
  }

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <div className="max-w-4xl space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-1">
                <h1 className="text-2xl font-bold tracking-tight text-[#171717]">Notifications</h1>
                <p className="text-[#525252]">Stay updated with your activity and ESL decisions</p>
              </div>
              <div className="flex items-center gap-3">
                {unreadCount > 0 && (
                  <Badge variant="outline" className="bg-[#171717]/10 text-[#171717] border-[#171717]/20 rounded-full">
                    {unreadCount} unread
                  </Badge>
                )}
                {unreadCount > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-lg"
                    disabled={markingAll}
                    onClick={handleMarkAllRead}
                  >
                    {markingAll ? 'Marking…' : 'Mark all read'}
                  </Button>
                )}
              </div>
            </div>

            {/* Loading */}
            {loading && (
              <p className="text-sm text-[#525252]">Loading notifications…</p>
            )}

            {/* Notifications List */}
            {!loading && notifications.length > 0 && (
              <div className="space-y-3">
                {notifications.map((notification) => {
                  const Icon = iconForType(notification.type)
                  return (
                    <Card
                      key={notification.id}
                      className={`border-[#E5E5E5] rounded-lg shadow-md transition-all hover:shadow-md cursor-pointer ${
                        !notification.read ? 'bg-[#FAFAFA]' : ''
                      }`}
                      onClick={() => !notification.read && handleMarkRead(notification.id)}
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-start gap-4">
                          <div className={`mt-1 ${notification.read ? 'text-[#525252]' : 'text-[#171717]'}`}>
                            <Icon className="h-4 w-4" />
                          </div>
                          <div className="flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              <CardTitle className="text-base text-[#171717]">
                                {notification.title}
                              </CardTitle>
                              {!notification.read && (
                                <div className="h-2 w-2 rounded-full bg-[#171717]" />
                              )}
                            </div>
                            <p className="text-sm text-[#525252]">{notification.message}</p>
                            <p className="text-xs text-[#A3A3A3]">{timeAgo(notification.created_at)}</p>
                          </div>
                        </div>
                      </CardHeader>
                    </Card>
                  )
                })}
              </div>
            )}

            {/* Empty state */}
            {!loading && notifications.length === 0 && (
              <Card className="border-[#E5E5E5] rounded-lg shadow-md p-12 text-center">
                <Bell className="h-10 w-10 mx-auto text-[#A3A3A3]" />
                <h3 className="font-semibold mt-4 text-lg text-[#171717]">All caught up!</h3>
                <p className="text-[#525252] mt-2">You have no notifications</p>
              </Card>
            )}
          </div>
        </div>
      </main>
    </>
  )
}
