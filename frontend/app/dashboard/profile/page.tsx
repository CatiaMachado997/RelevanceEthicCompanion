'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TopHeader } from '@/components/top-header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useAuth } from '@/hooks/useAuth'
import { User, Mail, Calendar, Shield } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export default function ProfilePage() {
  const { user } = useAuth()

  const getInitials = (email: string) => {
    return email
      .split('@')[0]
      .substring(0, 2)
      .toUpperCase()
  }

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <div className="max-w-4xl space-y-6">
            {/* Header */}
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-bold tracking-tight text-[#171717]">Profile</h1>
              <p className="text-[#525252]">
                Manage your personal information
              </p>
            </div>

            {/* Profile Card */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-4">
                  <Avatar className="h-20 w-20">
                    <AvatarFallback className="bg-[#171717] text-white text-2xl font-semibold">
                      {user?.email ? getInitials(user.email) : 'U'}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <CardTitle className="text-[#171717]">
                      {user?.email?.split('@')[0] || 'User'}
                    </CardTitle>
                    <CardDescription className="text-[#525252]">
                      {user?.email || 'user@example.com'}
                    </CardDescription>
                    <div className="flex gap-2 mt-2">
                      <Badge variant="outline" className="bg-[#171717]/10 text-[#171717] border-[#171717]/20 rounded-full">
                        <Shield className="h-3 w-3 mr-1" />
                        Protected by ESL
                      </Badge>
                    </div>
                  </div>
                  <Button variant="outline" className="rounded-lg" disabled>
                    Change Avatar
                  </Button>
                </div>
              </CardHeader>
            </Card>

            {/* Personal Information */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-[#171717]" />
                  <CardTitle className="text-[#171717]">Personal Information</CardTitle>
                </div>
                <CardDescription className="text-[#525252]">
                  Update your personal details
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="name" className="text-[#171717]">Full Name</Label>
                  <Input
                    id="name"
                    placeholder="Enter your name"
                    className="rounded-lg"
                    disabled
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="email" className="text-[#171717]">Email</Label>
                  <div className="flex gap-2">
                    <Input
                      id="email"
                      type="email"
                      value={user?.email || ''}
                      className="rounded-lg"
                      disabled
                    />
                    <Button variant="outline" className="rounded-lg" disabled>
                      Verify
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="timezone" className="text-[#171717]">Timezone</Label>
                  <Input
                    id="timezone"
                    placeholder="UTC-5 (EST)"
                    className="rounded-lg"
                    disabled
                  />
                </div>
              </CardContent>
            </Card>

            {/* Account Stats */}
            <Card className="border-[#E5E5E5] rounded-lg shadow-md">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-[#171717]" />
                  <CardTitle className="text-[#171717]">Account Statistics</CardTitle>
                </div>
                <CardDescription className="text-[#525252]">
                  Your activity summary
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-4 rounded-lg bg-[#FAFAFA]">
                    <div className="text-2xl font-bold text-[#171717]">12</div>
                    <div className="text-sm text-[#525252] mt-1">Values Set</div>
                  </div>
                  <div className="text-center p-4 rounded-lg bg-[#FAFAFA]">
                    <div className="text-2xl font-bold text-[#171717]">5</div>
                    <div className="text-sm text-[#525252] mt-1">Active Goals</div>
                  </div>
                  <div className="text-center p-4 rounded-lg bg-[#FAFAFA]">
                    <div className="text-2xl font-bold text-[#171717]">87%</div>
                    <div className="text-sm text-[#525252] mt-1">ESL Approval Rate</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <Button className="bg-[#171717] hover:bg-[#404040] rounded-full" disabled>
                Save Changes
              </Button>
              <Button variant="outline" className="rounded-full" disabled>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
