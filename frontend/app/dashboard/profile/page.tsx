'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useAuth } from '@/hooks/useAuth'
import { User, Mail, Calendar, Shield } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/ui/page-header'

export default function ProfilePage() {
  const { user } = useAuth()

  const getInitials = (email: string) => {
    return email
      .split('@')[0]
      .substring(0, 2)
      .toUpperCase()
  }

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Profile" subtitle="Your personal information" />

      {/* Profile Card */}
      <Card className="border-[#e0e0e0] rounded-2xl">
        <CardHeader>
          <div className="flex items-center gap-4">
            <Avatar className="h-20 w-20">
              <AvatarFallback className="bg-[#1a1a1a] text-white text-2xl font-semibold">
                {user?.email ? getInitials(user.email) : 'U'}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1">
              <CardTitle className="text-[#1a1a1a]">
                {user?.email?.split('@')[0] || 'User'}
              </CardTitle>
              <CardDescription className="text-[#6b6b6b]">
                {user?.email || 'user@example.com'}
              </CardDescription>
              <div className="flex gap-2 mt-2">
                <Badge variant="outline" className="bg-[#1a1a1a]/10 text-[#1a1a1a] border-[#1a1a1a]/20 rounded-full">
                  <Shield className="h-3 w-3 mr-1" />
                  Protected by ESL
                </Badge>
              </div>
            </div>
            <Button variant="outline" className="rounded-full" disabled>
              Change Avatar
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* Personal Information */}
      <Card className="border-[#e0e0e0] rounded-2xl">
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-[#1a1a1a]" />
            <CardTitle className="text-[#1a1a1a]">Personal Information</CardTitle>
          </div>
          <CardDescription className="text-[#6b6b6b]">
            Update your personal details
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="name" className="text-[#1a1a1a]">Full Name</Label>
            <Input
              id="name"
              placeholder="Enter your name"
              className="rounded-xl"
              disabled
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="email" className="text-[#1a1a1a]">Email</Label>
            <div className="flex gap-2">
              <Input
                id="email"
                type="email"
                value={user?.email || ''}
                className="rounded-xl"
                disabled
              />
              <Button variant="outline" className="rounded-full" disabled>
                Verify
              </Button>
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="timezone" className="text-[#1a1a1a]">Timezone</Label>
            <Input
              id="timezone"
              placeholder="UTC-5 (EST)"
              className="rounded-xl"
              disabled
            />
          </div>
        </CardContent>
      </Card>

      {/* Account Stats */}
      <Card className="border-[#e0e0e0] rounded-2xl">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-[#1a1a1a]" />
            <CardTitle className="text-[#1a1a1a]">Account Statistics</CardTitle>
          </div>
          <CardDescription className="text-[#6b6b6b]">
            Your activity summary
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 rounded-2xl bg-[#f5f5f5]">
              <div className="text-2xl font-bold text-[#1a1a1a]">12</div>
              <div className="text-sm text-[#6b6b6b] mt-1">Values Set</div>
            </div>
            <div className="text-center p-4 rounded-2xl bg-[#f5f5f5]">
              <div className="text-2xl font-bold text-[#1a1a1a]">5</div>
              <div className="text-sm text-[#6b6b6b] mt-1">Active Goals</div>
            </div>
            <div className="text-center p-4 rounded-2xl bg-[#f5f5f5]">
              <div className="text-2xl font-bold text-[#1a1a1a]">87%</div>
              <div className="text-sm text-[#6b6b6b] mt-1">ESL Approval Rate</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button className="bg-[#1a1a1a] hover:bg-[#333333] rounded-full" disabled>
          Save Changes
        </Button>
        <Button variant="outline" className="rounded-full" disabled>
          Cancel
        </Button>
      </div>
    </div>
  )
}
