'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TopHeader } from '@/components/top-header'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Settings as SettingsIcon, Bell, Lock, Palette, Database, Calendar, CheckCircle2, XCircle, RefreshCw } from 'lucide-react'
import { dataSourcesApi, DataSource } from '@/lib/api'

export default function SettingsPage() {
  const [dataSources, setDataSources] = useState<DataSource[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<string | null>(null)

  useEffect(() => {
    loadDataSources()
  }, [])

  const loadDataSources = async () => {
    try {
      const { sources } = await dataSourcesApi.list()
      setDataSources(sources)
    } catch (error) {
      console.error('Failed to load data sources:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleConnect = async (sourceType: string) => {
    try {
      const { authorization_url } = await dataSourcesApi.getAuthUrl(sourceType)
      window.location.href = authorization_url
    } catch (error) {
      console.error('Failed to get auth URL:', error)
    }
  }

  const handleDisconnect = async (sourceType: string) => {
    try {
      await dataSourcesApi.disconnect(sourceType)
      await loadDataSources()
    } catch (error) {
      console.error('Failed to disconnect:', error)
    }
  }

  const handleSync = async (sourceType: string) => {
    try {
      setSyncing(sourceType)
      await dataSourcesApi.sync(sourceType)
      await loadDataSources()
    } catch (error) {
      console.error('Failed to sync:', error)
    } finally {
      setSyncing(null)
    }
  }

  const getCalendarSource = () => {
    return dataSources.find(s => s.source_type === 'google_calendar')
  }

  const calendarSource = getCalendarSource()

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-white">
          <div className="max-w-4xl space-y-4 md:space-y-6">
            {/* Header */}
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-bold tracking-tight text-[#171717]">Settings</h1>
              <p className="text-[#525252]">
                Manage your account preferences and settings
              </p>
            </div>

            {/* Connected Data Sources */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-[#171717]" />
                  <CardTitle className="text-[#171717]">Connected Data Sources</CardTitle>
                </div>
                <CardDescription className="text-[#525252]">
                  Connect external services to enhance your experience
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Google Calendar */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#F5F5F5]">
                      <Calendar className="h-4 w-4 text-[#171717]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <Label className="text-[#171717]">Google Calendar</Label>
                        {calendarSource && (
                          <div className={`flex items-center gap-1 text-xs ${
                            calendarSource.status === 'connected'
                              ? 'text-[#525252]'
                              : 'text-[#DC2626]'
                          }`}>
                            {calendarSource.status === 'connected' ? (
                              <>
                                <CheckCircle2 className="h-3 w-3" />
                                Connected
                              </>
                            ) : (
                              <>
                                <XCircle className="h-3 w-3" />
                                Disconnected
                              </>
                            )}
                          </div>
                        )}
                      </div>
                      <p className="text-sm text-[#525252]">
                        {calendarSource
                          ? `Last synced: ${calendarSource.last_sync
                              ? new Date(calendarSource.last_sync).toLocaleString()
                              : 'Never'}`
                          : 'Sync your calendar events for better context'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {calendarSource?.status === 'connected' ? (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-lg"
                          onClick={() => handleSync(calendarSource.source_type)}
                          disabled={syncing === calendarSource.source_type}
                        >
                          {syncing === calendarSource.source_type ? (
                            <RefreshCw className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <RefreshCw className="h-4 w-4 mr-1" />
                              Sync
                            </>
                          )}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-lg"
                          onClick={() => handleDisconnect(calendarSource.source_type)}
                        >
                          Disconnect
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="default"
                        size="sm"
                        className="rounded-lg bg-[#171717] hover:bg-[#404040]"
                        onClick={() => handleConnect('google_calendar')}
                      >
                        Connect
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Notifications Settings */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Bell className="h-4 w-4 text-[#171717]" />
                  <CardTitle className="text-[#171717]">Notifications</CardTitle>
                </div>
                <CardDescription className="text-[#525252]">
                  Configure how you receive notifications
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-[#171717]">Email Notifications</Label>
                    <p className="text-sm text-[#525252]">Receive updates via email</p>
                  </div>
                  <Switch />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-[#171717]">Push Notifications</Label>
                    <p className="text-sm text-[#525252]">Receive browser notifications</p>
                  </div>
                  <Switch />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-[#171717]">ESL Alerts</Label>
                    <p className="text-sm text-[#525252]">Get notified when ESL blocks an action</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </CardContent>
            </Card>

            {/* Privacy Settings */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-[#171717]" />
                  <CardTitle className="text-[#171717]">Privacy & Security</CardTitle>
                </div>
                <CardDescription className="text-[#525252]">
                  Manage your privacy settings and data
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-[#171717]">Share Usage Analytics</Label>
                    <p className="text-sm text-[#525252]">Help improve the app by sharing anonymous usage data</p>
                  </div>
                  <Switch />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-[#171717]">PII Protection</Label>
                    <p className="text-sm text-[#525252]">Auto-redact sensitive information</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </CardContent>
            </Card>

            {/* Appearance Settings */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Palette className="h-4 w-4 text-[#171717]" />
                  <CardTitle className="text-[#171717]">Appearance</CardTitle>
                </div>
                <CardDescription className="text-[#525252]">
                  Customize the look and feel
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-[#171717]">Theme</Label>
                  <p className="text-sm text-[#525252] mb-2">Coming soon: Dark mode support</p>
                  <div className="flex gap-2">
                    <Button variant="outline" className="rounded-lg" disabled>Light</Button>
                    <Button variant="outline" className="rounded-lg" disabled>Dark</Button>
                    <Button variant="outline" className="rounded-lg" disabled>Auto</Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Data Management */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-[#171717]" />
                  <CardTitle className="text-[#171717]">Data Management</CardTitle>
                </div>
                <CardDescription className="text-[#525252]">
                  Manage your data and account
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-[#171717]">Export Data</Label>
                    <p className="text-sm text-[#525252]">Download all your data</p>
                  </div>
                  <Button variant="outline" className="rounded-lg" disabled>
                    Export
                  </Button>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-[#171717]">Delete Account</Label>
                    <p className="text-sm text-[#525252]">Permanently delete your account and data</p>
                  </div>
                  <Button variant="destructive" className="rounded-lg" disabled>
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </>
  )
}
