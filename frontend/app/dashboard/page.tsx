'use client'

import { useEffect, useState } from 'react'
import { transparencyApi, goalsApi, valuesApi } from '@/lib/api'
import Link from 'next/link'
import { motion } from 'framer-motion'
import {
  MessageSquare,
  Scale,
  BarChart3,
  ShieldCheck,
  ShieldAlert,
  Activity,
  CheckCircle2,
  FileEdit,
  Sparkles,
  ArrowRight,
  Target,
  Calendar,
  TrendingUp,
  Shield,
  Plus,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TopHeader } from '@/components/top-header'
import { EmptyState } from '@/components/ui/empty-state'

interface Report {
  total_decisions: number
  approval_rate: number
  vetoed_count: number
  modified_count: number
}

interface Goal {
  id: string
  title: string
  status: string
  priority: number
}

interface Value {
  id: string
  type: string
  value: string
  priority: number
}

export default function DashboardPage() {
  const [insights, setInsights] = useState<string[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [goals, setGoals] = useState<Goal[]>([])
  const [values, setValues] = useState<Value[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [insightsData, reportData, goalsData, valuesData] = await Promise.all([
          transparencyApi.insights(),
          transparencyApi.report(7),
          goalsApi.list('active'),
          valuesApi.list(),
        ])
        setInsights(insightsData?.insights || [])
        setReport(reportData)
        setGoals(goalsData?.goals?.slice(0, 3) || [])
        setValues(valuesData?.values?.slice(0, 3) || [])
      } catch (error) {
        console.error('Failed to load dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.05 },
    },
  }

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1 },
  }

  if (loading) {
    return (
      <>
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <TopHeader />
          <div className="flex-1 overflow-y-auto p-3 md:p-4 bg-muted">
            <div className="space-y-3 max-w-7xl mx-auto">
              {/* Header Skeleton */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="space-y-1">
                  <Skeleton className="h-7 w-[180px]" />
                  <Skeleton className="h-3 w-[280px]" />
                </div>
                <Skeleton className="h-9 w-[130px] rounded-lg" />
              </div>

              {/* Stats Grid Skeleton */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[1, 2, 3, 4].map((i) => (
                  <Card key={i} className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3 px-4">
                      <Skeleton className="h-3 w-[90px]" />
                      <Skeleton className="h-7 w-7 rounded-lg" />
                    </CardHeader>
                    <CardContent className="px-4 pb-3">
                      <Skeleton className="h-7 w-[50px] mb-1" />
                      <Skeleton className="h-2.5 w-[70px]" />
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Main Content Grid Skeleton */}
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
                {/* Left Column - Main Content */}
                <div className="lg:col-span-3 space-y-3">
                  {/* Quick Actions Skeleton */}
                  <Card className="border-border rounded-lg shadow-sm bg-card">
                    <CardHeader className="pb-3 pt-4 px-4">
                      <Skeleton className="h-5 w-[120px] mb-1" />
                      <Skeleton className="h-3 w-[180px]" />
                    </CardHeader>
                    <CardContent className="grid grid-cols-2 sm:grid-cols-3 gap-2 px-4 pb-4">
                      {[1, 2, 3, 4, 5, 6].map((i) => (
                        <Skeleton key={i} className="h-20 rounded-lg" />
                      ))}
                    </CardContent>
                  </Card>

                  {/* Active Goals Skeleton */}
                  <Card className="border-border rounded-lg shadow-sm bg-card">
                    <CardHeader className="flex flex-row items-center justify-between pb-3 pt-4 px-4">
                      <div className="space-y-1">
                        <Skeleton className="h-5 w-[100px]" />
                        <Skeleton className="h-3 w-[120px]" />
                      </div>
                      <Skeleton className="h-7 w-[80px] rounded-lg" />
                    </CardHeader>
                    <CardContent className="px-4 pb-4">
                      <div className="space-y-2">
                        {[1, 2, 3].map((i) => (
                          <div
                            key={i}
                            className="flex items-center gap-2.5 p-2.5 rounded-lg border border-border"
                          >
                            <Skeleton className="w-7 h-7 rounded-full" />
                            <div className="flex-1 space-y-1.5">
                              <Skeleton className="h-3.5 w-[180px]" />
                              <Skeleton className="h-3 w-[70px]" />
                            </div>
                            <Skeleton className="h-3.5 w-3.5 rounded" />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* ESL Insights Skeleton */}
                  <Card className="border-border rounded-lg shadow-sm bg-card">
                    <CardHeader className="pb-3 pt-4 px-4">
                      <Skeleton className="h-5 w-[120px] mb-1" />
                      <Skeleton className="h-3 w-[220px]" />
                    </CardHeader>
                    <CardContent className="px-4 pb-4">
                      <div className="space-y-2">
                        {[1, 2, 3].map((i) => (
                          <div key={i} className="flex items-start gap-2.5">
                            <Skeleton className="h-1.5 w-1.5 rounded-full mt-1.5" />
                            <Skeleton className="h-3.5 flex-1" />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Right Column - Sidebar */}
                <div className="space-y-3">
                  {/* System Status Skeleton */}
                  <Card className="border-l-4 border-l-green-500 border-border rounded-lg shadow-sm bg-card">
                    <CardHeader className="pb-3 pt-4 px-4">
                      <div className="flex items-center justify-between mb-1.5">
                        <Skeleton className="h-4 w-[100px]" />
                        <Skeleton className="h-2.5 w-2.5 rounded-full" />
                      </div>
                      <div className="space-y-1.5">
                        <Skeleton className="h-6 w-[70px]" />
                        <Skeleton className="h-3 w-[160px]" />
                      </div>
                    </CardHeader>
                    <CardFooter className="px-4 pb-4 pt-0">
                      <Skeleton className="h-3 w-[100px]" />
                    </CardFooter>
                  </Card>

                  {/* Active Values Skeleton */}
                  <Card className="border-border rounded-lg shadow-sm bg-card">
                    <CardHeader className="flex flex-row items-center justify-between pb-3 pt-4 px-4">
                      <div className="space-y-1">
                        <Skeleton className="h-4 w-[90px]" />
                        <Skeleton className="h-3 w-[100px]" />
                      </div>
                      <Skeleton className="h-7 w-7 rounded" />
                    </CardHeader>
                    <CardContent className="px-4 pb-4">
                      <div className="space-y-1.5">
                        {[1, 2, 3].map((i) => (
                          <div
                            key={i}
                            className="p-2 rounded-lg bg-muted border border-border"
                          >
                            <Skeleton className="h-3.5 w-full mb-1.5" />
                            <div className="flex items-center justify-between">
                              <Skeleton className="h-3 w-[70px]" />
                              <Skeleton className="h-2.5 w-[50px]" />
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Philosophy Card Skeleton */}
                  <Card className="border-border rounded-lg shadow-sm bg-card">
                    <CardHeader className="pb-3 pt-4 px-4">
                      <Skeleton className="h-4 w-[120px]" />
                    </CardHeader>
                    <CardContent className="px-4 pb-4">
                      <div className="space-y-1.5">
                        <Skeleton className="h-3.5 w-full" />
                        <Skeleton className="h-3.5 w-full" />
                        <Skeleton className="h-3 w-[160px]" />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          </div>
        </main>
      </>
    )
  }

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-3 md:p-4 bg-muted">
          <motion.div
            className="space-y-3 max-w-7xl mx-auto"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h1 className="text-xl font-semibold tracking-tight text-foreground">
                  Welcome back
                </h1>
                <p className="text-muted-foreground text-sm mt-0.5">
                  Here's what's happening with your AI companion
                </p>
              </div>
              <Link href="/dashboard/chat">
                <Button className="!bg-[#D2691E] hover:!bg-[#B85A19] text-white rounded-lg shadow-sm h-9 text-sm">
                  <MessageSquare className="h-3.5 w-3.5 mr-2 text-white" />
                  Start Chat
                </Button>
              </Link>
            </div>

            {/* Stats Grid */}
            {report && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3 px-4">
                      <CardTitle className="text-xs font-medium text-muted-foreground">
                        Total Decisions
                      </CardTitle>
                      <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center">
                        <Activity className="h-3.5 w-3.5 text-foreground" />
                      </div>
                    </CardHeader>
                    <CardContent className="px-4 pb-3">
                      <div className="text-xl font-semibold text-foreground">
                        {report.total_decisions}
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">Last 7 days</p>
                    </CardContent>
                  </Card>
                </motion.div>

                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3 px-4">
                      <CardTitle className="text-xs font-medium text-muted-foreground">
                        Approval Rate
                      </CardTitle>
                      <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center">
                        <CheckCircle2 className="h-3.5 w-3.5 text-foreground" />
                      </div>
                    </CardHeader>
                    <CardContent className="px-4 pb-3">
                      <div className="text-xl font-semibold text-foreground">
                        {(report.approval_rate * 100).toFixed(0)}%
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">Approved by ESL</p>
                    </CardContent>
                  </Card>
                </motion.div>

                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3 px-4">
                      <CardTitle className="text-xs font-medium text-muted-foreground">
                        Protected
                      </CardTitle>
                      <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center">
                        <ShieldAlert className="h-3.5 w-3.5 text-muted-foreground" />
                      </div>
                    </CardHeader>
                    <CardContent className="px-4 pb-3">
                      <div className="text-xl font-semibold text-muted-foreground">
                        {report.vetoed_count}
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">Actions blocked</p>
                    </CardContent>
                  </Card>
                </motion.div>

                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3 px-4">
                      <CardTitle className="text-xs font-medium text-muted-foreground">
                        Modified
                      </CardTitle>
                      <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center">
                        <FileEdit className="h-3.5 w-3.5 text-muted-foreground" />
                      </div>
                    </CardHeader>
                    <CardContent className="px-4 pb-3">
                      <div className="text-xl font-semibold text-muted-foreground">
                        {report.modified_count}
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">Actions adjusted</p>
                    </CardContent>
                  </Card>
                </motion.div>
              </div>
            )}

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
              {/* Left Column - Main Content */}
              <div className="lg:col-span-3 space-y-3">
                {/* Quick Actions */}
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="pb-3 pt-4 px-4">
                      <CardTitle className="text-foreground text-base">Quick Actions</CardTitle>
                      <CardDescription className="text-muted-foreground text-xs">
                        Get started with common tasks
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid grid-cols-2 sm:grid-cols-3 gap-2 px-4 pb-4">
                      <Link href="/dashboard/chat">
                        <Button
                          variant="outline"
                          className="w-full h-20 flex flex-col gap-1.5 border-border hover:border-foreground hover:bg-muted transition-all rounded-lg"
                        >
                          <MessageSquare className="h-3.5 w-3.5 text-foreground" />
                          <span className="text-xs font-medium text-foreground">Chat</span>
                        </Button>
                      </Link>
                      <Link href="/dashboard/values">
                        <Button
                          variant="outline"
                          className="w-full h-20 flex flex-col gap-1.5 border-border hover:border-foreground hover:bg-muted transition-all rounded-lg"
                        >
                          <Shield className="h-3.5 w-3.5 text-foreground" />
                          <span className="text-xs font-medium text-foreground">Values</span>
                        </Button>
                      </Link>
                      <Link href="/dashboard/goals">
                        <Button
                          variant="outline"
                          className="w-full h-20 flex flex-col gap-1.5 border-border hover:border-foreground hover:bg-muted transition-all rounded-lg"
                        >
                          <Target className="h-3.5 w-3.5 text-foreground" />
                          <span className="text-xs font-medium text-foreground">Goals</span>
                        </Button>
                      </Link>
                      <Link href="/dashboard/search">
                        <Button
                          variant="outline"
                          className="w-full h-20 flex flex-col gap-1.5 border-border hover:border-foreground hover:bg-muted transition-all rounded-lg"
                        >
                          <BarChart3 className="h-3.5 w-3.5 text-foreground" />
                          <span className="text-xs font-medium text-foreground">Search</span>
                        </Button>
                      </Link>
                      <Link href="/dashboard/transparency">
                        <Button
                          variant="outline"
                          className="w-full h-20 flex flex-col gap-1.5 border-border hover:border-foreground hover:bg-muted transition-all rounded-lg"
                        >
                          <TrendingUp className="h-3.5 w-3.5 text-foreground" />
                          <span className="text-xs font-medium text-foreground">Reports</span>
                        </Button>
                      </Link>
                      <Link href="/dashboard/settings">
                        <Button
                          variant="outline"
                          className="w-full h-20 flex flex-col gap-1.5 border-border hover:border-foreground hover:bg-muted transition-all rounded-lg"
                        >
                          <Calendar className="h-3.5 w-3.5 text-foreground" />
                          <span className="text-xs font-medium text-foreground">Calendar</span>
                        </Button>
                      </Link>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* Active Goals */}
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="flex flex-row items-center justify-between pb-3 pt-4 px-4">
                      <div>
                        <CardTitle className="text-foreground text-base">Active Goals</CardTitle>
                        <CardDescription className="text-muted-foreground text-xs">
                          Your top priorities
                        </CardDescription>
                      </div>
                      <Link href="/dashboard/goals">
                        <Button variant="ghost" size="sm" className="text-foreground hover:bg-muted h-7 text-xs">
                          View all
                          <ArrowRight className="h-3 w-3 ml-1 text-current" />
                        </Button>
                      </Link>
                    </CardHeader>
                    <CardContent className="px-4 pb-4">
                      {goals.length === 0 ? (
                        <div className="text-center py-8">
                          <Target className="h-8 w-8 mx-auto text-muted-foreground opacity-50" />
                          <h3 className="font-medium mt-3 text-sm text-foreground">No goals yet</h3>
                          <p className="text-muted-foreground text-xs mt-1">
                            Goals help the system understand your priorities
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {goals.map((goal, index) => (
                            <div
                              key={goal.id}
                              className="flex items-center gap-2.5 p-2.5 rounded-lg border border-border hover:border-foreground transition-colors"
                            >
                              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-muted text-foreground font-semibold text-xs">
                                {index + 1}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-foreground truncate">
                                  {goal.title}
                                </p>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <Badge
                                    variant="outline"
                                    className="text-[10px] border-border text-muted-foreground px-1.5 py-0"
                                  >
                                    Priority {goal.priority}
                                  </Badge>
                                </div>
                              </div>
                              <CheckCircle2 className="h-3.5 w-3.5 text-border hover:text-foreground cursor-pointer transition-colors" />
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>

                {/* ESL Insights */}
                {insights.length > 0 && (
                  <motion.div variants={itemVariants}>
                    <Card className="bg-gradient-to-br from-muted to-muted border-border rounded-lg shadow-sm">
                      <CardHeader className="pb-3 pt-4 px-4">
                        <CardTitle className="flex items-center gap-2 text-foreground text-base">
                          <ShieldCheck className="h-3.5 w-3.5 text-foreground" />
                          ESL Insights
                        </CardTitle>
                        <CardDescription className="text-muted-foreground text-xs">
                          Recent observations from your safeguard layer
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="px-4 pb-4">
                        <ul className="space-y-1.5">
                          {insights.map((insight, i) => (
                            <li
                              key={i}
                              className="flex items-start gap-2.5 text-muted-foreground text-xs"
                            >
                              <div className="mt-1 h-1 w-1 rounded-full bg-primary shrink-0" />
                              <span>{insight}</span>
                            </li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>
                  </motion.div>
                )}
              </div>

              {/* Right Column - Sidebar */}
              <div className="space-y-3">
                {/* System Status */}
                <motion.div variants={itemVariants}>
                  <Card className="border-l-4 border-l-green-500 border-border rounded-lg shadow-sm bg-card">
                    <CardHeader className="pb-3 pt-4 px-4">
                      <div className="flex items-center justify-between mb-1.5">
                        <CardTitle className="text-sm text-foreground">
                          System Status
                        </CardTitle>
                        <span className="relative flex h-2.5 w-2.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                        </span>
                      </div>
                      <div className="space-y-0.5">
                        <div className="text-lg font-semibold text-foreground">Active</div>
                        <CardDescription className="text-muted-foreground text-xs">
                          ESL is protecting your interactions
                        </CardDescription>
                      </div>
                    </CardHeader>
                    <CardFooter className="px-4 pb-4 pt-0">
                      <Link
                        href="/dashboard/transparency"
                        className="text-xs text-foreground hover:text-muted-foreground flex items-center gap-1 transition-colors font-medium"
                      >
                        View live logs
                        <ArrowRight className="h-2.5 w-2.5 text-current" />
                      </Link>
                    </CardFooter>
                  </Card>
                </motion.div>

                {/* Active Values */}
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-border rounded-lg shadow-sm bg-card h-full">
                    <CardHeader className="flex flex-row items-center justify-between pb-3 pt-4 px-4">
                      <div>
                        <CardTitle className="text-sm text-foreground">
                          Your Values
                        </CardTitle>
                        <CardDescription className="text-muted-foreground text-xs">
                          Active boundaries
                        </CardDescription>
                      </div>
                      <Link href="/dashboard/values">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-foreground hover:bg-muted h-7"
                        >
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </Link>
                    </CardHeader>
                    <CardContent className="px-4 pb-4">
                      {values.length === 0 ? (
                        <div className="text-center py-6">
                          <Shield className="h-7 w-7 mx-auto text-muted-foreground opacity-50" />
                          <h3 className="font-medium mt-2.5 text-xs text-foreground">No values defined</h3>
                          <p className="text-muted-foreground text-[10px] mt-1">
                            Values guide the ESL to respect your boundaries
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-1.5">
                          {values.map((value) => (
                            <div
                              key={value.id}
                              className="p-2 rounded-lg bg-muted border border-border"
                            >
                              <p className="text-xs text-foreground font-medium line-clamp-2">
                                {value.value}
                              </p>
                              <div className="flex items-center justify-between mt-1">
                                <Badge
                                  variant="outline"
                                  className="text-[10px] border-border text-muted-foreground px-1.5 py-0"
                                >
                                  {value.type.replace('_', ' ')}
                                </Badge>
                                <span className="text-[10px] text-muted-foreground">
                                  Priority {value.priority}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>

                {/* Philosophy Card */}
                <motion.div variants={itemVariants}>
                  <Card className="bg-gradient-to-br from-muted to-muted text-foreground border-border rounded-lg shadow-sm">
                    <CardHeader className="pb-3 pt-4 px-4">
                      <CardTitle className="flex items-center gap-2 text-foreground text-sm">
                        <Sparkles className="h-3.5 w-3.5 text-foreground" />
                        Our Philosophy
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="px-4 pb-4">
                      <p className="text-xs text-foreground leading-relaxed font-medium">
                        "Trust over Engagement"
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1.5 leading-relaxed">
                        We prioritize your well-being and respect your boundaries over
                        maximizing screen time.
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
              </div>
            </div>
          </motion.div>
        </div>
      </main>
    </>
  )
}
