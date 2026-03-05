'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TopHeader } from '@/components/top-header'
import { Badge } from '@/components/ui/badge'
import { Bell, CheckCircle2, Info, AlertTriangle, ShieldAlert } from 'lucide-react'

export default function NotificationsPage() {
  // Mock notifications data
  const notifications = [
    {
      id: '1',
      type: 'esl_block',
      title: 'ESL Protected You',
      message: 'Blocked a notification during your focus time (9am-11am)',
      timestamp: '2 hours ago',
      read: false,
      icon: ShieldAlert,
      color: 'text-[#525252]',
    },
    {
      id: '2',
      type: 'success',
      title: 'Goal Completed',
      message: 'You completed "Finish project proposal"',
      timestamp: '5 hours ago',
      read: false,
      icon: CheckCircle2,
      color: 'text-[#171717]',
    },
    {
      id: '3',
      type: 'info',
      title: 'New Insight Available',
      message: 'ESL has new suggestions based on your recent activity',
      timestamp: '1 day ago',
      read: true,
      icon: Info,
      color: 'text-[#525252]',
    },
    {
      id: '4',
      type: 'warning',
      title: 'Boundary Check',
      message: 'Work notification attempted after 7pm',
      timestamp: '2 days ago',
      read: true,
      icon: AlertTriangle,
      color: 'text-[#525252]',
    },
  ]

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <div className="max-w-4xl space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-1">
                <h1 className="text-2xl font-bold tracking-tight text-[#171717]">
                  Notifications
                </h1>
                <p className="text-[#525252]">
                  Stay updated with your activity and ESL decisions
                </p>
              </div>
              <Badge variant="outline" className="bg-[#171717]/10 text-[#171717] border-[#171717]/20 rounded-full">
                {notifications.filter(n => !n.read).length} unread
              </Badge>
            </div>

            {/* Notifications List */}
            <div className="space-y-3">
              {notifications.map((notification) => {
                const Icon = notification.icon
                return (
                  <Card
                    key={notification.id}
                    className={`border-[#E5E5E5] rounded-lg shadow-md transition-all hover:shadow-md ${
                      !notification.read ? 'bg-[#FAFAFA]' : ''
                    }`}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start gap-4">
                        <div className={`mt-1 ${notification.color}`}>
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
                          <p className="text-sm text-[#525252]">
                            {notification.message}
                          </p>
                          <p className="text-xs text-[#A3A3A3]">
                            {notification.timestamp}
                          </p>
                        </div>
                      </div>
                    </CardHeader>
                  </Card>
                )
              })}
            </div>

            {/* Empty State for All Read */}
            {notifications.filter(n => !n.read).length === 0 && (
              <Card className="border-[#E5E5E5] rounded-lg shadow-md p-12 text-center">
                <Bell className="h-10 w-10 mx-auto text-[#A3A3A3]" />
                <h3 className="font-semibold mt-4 text-lg text-[#171717]">
                  All caught up!
                </h3>
                <p className="text-[#525252] mt-2">
                  You have no unread notifications
                </p>
              </Card>
            )}
          </div>
        </div>
      </main>
    </>
  )
}
