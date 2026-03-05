'use client'

import { useEffect, useState } from 'react'
import { transparencyApi } from '@/lib/api'
import { motion } from 'framer-motion'
import {
  Activity,
  CheckCircle2,
  ShieldAlert,
  FileEdit,
  ShieldCheck,
  Clock,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TopHeader } from '@/components/top-header'

interface Report {
  total_decisions: number
  approved_count: number
  vetoed_count: number
  modified_count: number
  approval_rate: number
}

interface AuditLog {
  id: string
  action_type: string
  decision_status: 'APPROVED' | 'VETOED' | 'MODIFIED'
  reason: string
  timestamp: string
  confidence_score?: number
}

const decisionConfig = {
  APPROVED: {
    label: 'Approved',
    color: 'bg-green-100 text-[#171717] border-[#E5E5E5]',
    icon: CheckCircle2,
  },
  VETOED: {
    label: 'Vetoed',
    color: 'bg-red-100 text-red-700 border-red-200',
    icon: ShieldAlert,
  },
  MODIFIED: {
    label: 'Modified',
    color: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    icon: FileEdit,
  },
}

export default function TransparencyPage() {
  const [report, setReport] = useState<Report | null>(null)
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [insights, setInsights] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState('7')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [days, statusFilter])

  const loadData = async () => {
    setLoading(true)
    try {
      const [reportData, logsData, insightsData] = await Promise.all([
        transparencyApi.report(parseInt(days)),
        transparencyApi.logs(parseInt(days), statusFilter || undefined),
        transparencyApi.insights(),
      ])
      setReport(reportData || null)
      setLogs((logsData?.logs as AuditLog[]) || [])
      setInsights(insightsData?.insights || [])
    } catch (error) {
      console.error('Failed to load transparency data:', error)
      setReport(null)
      setLogs([])
      setInsights([])
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  }

  const formatActionType = (actionType: string) => {
    return actionType
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1 },
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
          <div className="flex-1 overflow-y-auto p-6 bg-white">
            <div className="space-y-6 max-w-6xl">
              <div className="flex flex-col space-y-2">
                <Skeleton className="h-8 w-[200px]" />
                <Skeleton className="h-4 w-[300px]" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-[120px] rounded-lg" />
                ))}
              </div>
              <Skeleton className="h-[200px] rounded-lg" />
              <Skeleton className="h-[400px] rounded-lg" />
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
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <motion.div
            className="space-y-6 max-w-6xl"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {/* Header */}
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-bold tracking-tight text-[#171717]">Transparency</h1>
              <p className="text-[#525252]">
                See how ESL protects your boundaries
              </p>
            </div>

            {/* Stats Grid */}
            {report && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-[#E5E5E5] rounded-lg shadow-md h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium text-[#525252]">
                        Total Decisions
                      </CardTitle>
                      <div className="w-8 h-8 rounded-lg bg-[#FAFAFA] flex items-center justify-center">
                        <Activity className="h-4 w-4 text-[#171717]" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-[#171717]">{report.total_decisions}</div>
                      <p className="text-xs text-[#525252]">
                        Last {days} days
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-[#E5E5E5] rounded-lg shadow-md h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium text-[#525252]">
                        Approval Rate
                      </CardTitle>
                      <div className="w-8 h-8 rounded-lg bg-[#F5F5F5] flex items-center justify-center">
                        <CheckCircle2 className="h-4 w-4 text-[#171717]" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-[#171717]">
                        {(report.approval_rate * 100).toFixed(0)}%
                      </div>
                      <p className="text-xs text-[#525252]">
                        {report.approved_count} approved
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-[#E5E5E5] rounded-lg shadow-md h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium text-[#525252]">Protected</CardTitle>
                      <div className="w-8 h-8 rounded-lg bg-[#F5F5F5] flex items-center justify-center">
                        <ShieldAlert className="h-4 w-4 text-[#525252]" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-[#525252]">
                        {report.vetoed_count}
                      </div>
                      <p className="text-xs text-[#525252]">Actions blocked</p>
                    </CardContent>
                  </Card>
                </motion.div>
                <motion.div variants={itemVariants} className="h-full">
                  <Card className="border-[#E5E5E5] rounded-lg shadow-md h-full">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium text-[#525252]">Modified</CardTitle>
                      <div className="w-8 h-8 rounded-lg bg-[#171717]/10 flex items-center justify-center">
                        <FileEdit className="h-4 w-4 text-[#171717]" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-[#171717]">
                        {report.modified_count}
                      </div>
                      <p className="text-xs text-[#525252]">Actions adjusted</p>
                    </CardContent>
                  </Card>
                </motion.div>
              </div>
            )}

            {/* ESL Insights */}
            {insights.length > 0 && (
              <motion.div variants={itemVariants}>
                <Card className="bg-gradient-to-br from-[#171717]/5 to-[#171717]/10 border-[#171717]/20 rounded-lg">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-[#171717]">
                      <ShieldCheck className="h-4 w-4" />
                      ESL Insights
                    </CardTitle>
                    <CardDescription className="text-[#525252]">
                      Recent observations from the safeguard layer
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-3">
                      {insights.map((insight, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-3 text-[#525252] text-sm"
                        >
                          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#171717] shrink-0" />
                          {insight}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Audit Log */}
            <motion.div variants={itemVariants}>
              <Card className="border-[#E5E5E5] rounded-lg shadow-md">
                <CardHeader>
                  <div>
                    <CardTitle className="text-[#171717]">Audit Log</CardTitle>
                    <CardDescription className="text-[#525252]">
                      Detailed record of all ESL decisions
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  {logs.length === 0 ? (
                    <div className="text-center py-12">
                      <Activity className="h-10 w-10 mx-auto text-[#A3A3A3]" />
                      <h3 className="font-semibold mt-4 text-lg text-[#171717]">No logs found</h3>
                      <p className="text-[#525252] mt-2">
                        {statusFilter
                          ? `No ${statusFilter.toLowerCase()} decisions in the last ${days} days.`
                          : `No ESL decisions in the last ${days} days.`}
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-[#E5E5E5]">
                            <th className="text-left py-3 px-4 text-sm font-medium text-[#525252]">
                              Time
                            </th>
                            <th className="text-left py-3 px-4 text-sm font-medium text-[#525252]">
                              Action
                            </th>
                            <th className="text-left py-3 px-4 text-sm font-medium text-[#525252]">
                              Decision
                            </th>
                            <th className="text-left py-3 px-4 text-sm font-medium text-[#525252]">
                              Reason
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {logs.map((log) => {
                            const config = decisionConfig[log.decision_status]
                            const Icon = config.icon
                            return (
                              <tr key={log.id} className="border-b border-[#E5E5E5] last:border-0">
                                <td className="py-3 px-4 text-sm">
                                  <div className="flex items-center gap-2 text-[#525252]">
                                    <Clock className="h-3 w-3" />
                                    {formatTime(log.timestamp)}
                                  </div>
                                </td>
                                <td className="py-3 px-4 text-sm font-medium text-[#171717]">
                                  {formatActionType(log.action_type)}
                                </td>
                                <td className="py-3 px-4">
                                  <Badge variant="outline" className={`${config.color} rounded-full`}>
                                    <Icon className="h-3 w-3 mr-1" />
                                    {config.label}
                                  </Badge>
                                </td>
                                <td className="py-3 px-4 text-sm text-[#525252] max-w-xs truncate">
                                  {log.reason}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>
        </div>
      </main>
    </>
  )
}
