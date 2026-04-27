'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
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
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { FilterChips } from '@/components/ui/filter-chips'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  BarChart,
  Bar,
} from 'recharts'

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

interface Stats {
  decision_breakdown: Record<string, number>
  most_protected_values: Array<{ value: string; count: number }>
  most_applied_rules: Array<{ rule: string; count: number }>
}

const ESL_COLORS = {
  APPROVED: '#4A7C59',
  VETOED: '#B04A3A',
  MODIFIED: '#9B7A3D',
}

const decisionConfig = {
  APPROVED: {
    label: 'Approved',
    color: 'bg-[#f0fdf4] text-[#166534] border-[#bbf7d0]',
    icon: CheckCircle2,
  },
  VETOED: {
    label: 'Vetoed',
    color: 'bg-[#fef2f2] text-[#991b1b] border-[#fecaca]',
    icon: ShieldAlert,
  },
  MODIFIED: {
    label: 'Modified',
    color: 'bg-[#fefce8] text-[#854d0e] border-[#fef08a]',
    icon: FileEdit,
  },
}

function groupLogsByDay(logs: AuditLog[]) {
  const map: Record<string, { date: string; approved: number; vetoed: number }> = {}
  for (const log of logs) {
    const date = new Date(log.timestamp || Date.now()).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })
    if (!map[date]) map[date] = { date, approved: 0, vetoed: 0 }
    if (log.decision_status === 'APPROVED') map[date].approved++
    if (log.decision_status === 'VETOED') map[date].vetoed++
  }
  return Object.values(map).slice(-7)
}

export default function TransparencyPage() {
  const [report, setReport] = useState<Report | null>(null)
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [insights, setInsights] = useState<string[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState('7')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [days, statusFilter])

  const loadData = async () => {
    setLoading(true)
    try {
      const [reportData, logsData, insightsData, statsData] = await Promise.all([
        api.transparency.report(parseInt(days)),
        api.transparency.logs(parseInt(days), statusFilter || undefined),
        api.transparency.insights(),
        api.transparency.stats(),
      ])
      setReport(reportData || null)
      setLogs((logsData?.logs as AuditLog[]) || [])
      setInsights(insightsData?.insights || [])
      setStats(statsData || null)
    } catch (error) {
      console.error('Failed to load transparency data:', error)
      setReport(null)
      setLogs([])
      setInsights([])
      setStats(null)
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

  const donutData = report
    ? [
        { name: 'Approved', value: report.approved_count, color: ESL_COLORS.APPROVED },
        { name: 'Vetoed', value: report.vetoed_count, color: ESL_COLORS.VETOED },
        { name: 'Modified', value: report.modified_count, color: ESL_COLORS.MODIFIED },
      ]
    : []

  const timeData = groupLogsByDay(logs)

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Transparency"
        subtitle="See how ESL protects you"
        action={
          <Select value={days} onValueChange={setDays}>
            <SelectTrigger className="w-[130px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="14">Last 14 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
            </SelectContent>
          </Select>
        }
      />

      {loading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-[120px] rounded-2xl" />
            ))}
          </div>
          <Skeleton className="h-[200px] rounded-2xl" />
        </div>
      ) : (
        <motion.div
          className="space-y-6"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {/* Stats Grid */}
          {report && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              <motion.div variants={itemVariants} className="h-full">
                <Card className="rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] shadow-[var(--ec-card-shadow)] h-full">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">
                      Total Decisions
                    </CardTitle>
                    <div className="w-8 h-8 rounded-xl bg-[#f5f5f5] flex items-center justify-center">
                      <Activity className="h-4 w-4 text-[#0a0a0a]" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#0a0a0a]">{report.total_decisions}</div>
                    <p className="text-xs text-[#9e9e9e]">Last {days} days</p>
                  </CardContent>
                </Card>
              </motion.div>
              <motion.div variants={itemVariants} className="h-full">
                <Card className="rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] shadow-[var(--ec-card-shadow)] h-full">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">
                      Approval Rate
                    </CardTitle>
                    <div className="w-8 h-8 rounded-xl bg-[#f5f5f5] flex items-center justify-center">
                      <CheckCircle2 className="h-4 w-4 text-[#0a0a0a]" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#0a0a0a]">
                      {(report.approval_rate * 100).toFixed(0)}%
                    </div>
                    <p className="text-xs text-[#9e9e9e]">{report.approved_count} approved</p>
                  </CardContent>
                </Card>
              </motion.div>
              <motion.div variants={itemVariants} className="h-full">
                <Card className="rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] shadow-[var(--ec-card-shadow)] h-full">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Protected</CardTitle>
                    <div className="w-8 h-8 rounded-xl bg-[#f5f5f5] flex items-center justify-center">
                      <ShieldAlert className="h-4 w-4 text-[#6b6b6b]" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#0a0a0a]">{report.vetoed_count}</div>
                    <p className="text-xs text-[#9e9e9e]">Actions blocked</p>
                  </CardContent>
                </Card>
              </motion.div>
              <motion.div variants={itemVariants} className="h-full">
                <Card className="rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] shadow-[var(--ec-card-shadow)] h-full">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Modified</CardTitle>
                    <div className="w-8 h-8 rounded-xl bg-[#f5f5f5] flex items-center justify-center">
                      <FileEdit className="h-4 w-4 text-[#0a0a0a]" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#0a0a0a]">{report.modified_count}</div>
                    <p className="text-xs text-[#9e9e9e]">Actions adjusted</p>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          )}

          {/* Charts Grid */}
          {report && stats && (
            <motion.div variants={itemVariants}>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-2xl p-5" style={{ background: 'var(--ec-card-bg)', border: '1px solid #e5e5e5' }}>
                  <p className="text-sm font-medium mb-3" style={{ color: 'var(--ec-text)' }}>Decision Breakdown</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie data={donutData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} dataKey="value">
                        {donutData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value, name) => [value, name]} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="rounded-2xl p-5" style={{ background: 'var(--ec-card-bg)', border: '1px solid #e5e5e5' }}>
                  <p className="text-sm font-medium mb-3" style={{ color: 'var(--ec-text)' }}>Decisions Over Time</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={timeData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9e9e9e' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#9e9e9e' }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="approved" stroke={ESL_COLORS.APPROVED} strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="vetoed" stroke={ESL_COLORS.VETOED} strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="rounded-2xl p-5" style={{ background: 'var(--ec-card-bg)', border: '1px solid #e5e5e5' }}>
                  <p className="text-sm font-medium mb-3" style={{ color: 'var(--ec-text)' }}>Most Protected Values</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={stats.most_protected_values}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                      <XAxis dataKey="value" tick={{ fontSize: 10, fill: '#9e9e9e' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#9e9e9e' }} />
                      <Tooltip />
                      <Bar dataKey="count" fill={ESL_COLORS.VETOED} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </motion.div>
          )}

          {/* ESL Insights */}
          {insights.length > 0 && (
            <motion.div variants={itemVariants}>
              <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#fafafa] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-[#0a0a0a] text-base">
                    <ShieldCheck className="h-4 w-4" />
                    ESL Insights
                  </CardTitle>
                  <CardDescription className="text-[#6b6b6b]">
                    Recent observations from the safeguard layer
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {insights.map((insight, i) => (
                      <li key={i} className="flex items-start gap-3 text-[#6b6b6b] text-sm">
                        <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#0a0a0a] shrink-0" />
                        {insight}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Audit Log — always rendered so filter chips are accessible */}
      <Card className="rounded-2xl border border-[var(--ec-card-border)] bg-[var(--ec-card-bg)] shadow-[var(--ec-card-shadow)]">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <CardTitle className="text-[#0a0a0a]">Audit Log</CardTitle>
              <CardDescription className="text-[#6b6b6b]">
                Detailed record of all ESL decisions
              </CardDescription>
            </div>
            <FilterChips
              chips={[
                { value: null, label: 'All' },
                { value: 'APPROVED', label: 'Approved' },
                { value: 'VETOED', label: 'Vetoed' },
                { value: 'MODIFIED', label: 'Modified' },
              ]}
              selected={statusFilter}
              onChange={setStatusFilter}
            />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-[200px] rounded-xl" />
          ) : logs.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="h-10 w-10 mx-auto text-[#9e9e9e]" />
              <h3 className="font-semibold mt-4 text-lg text-[#0a0a0a]">No logs found</h3>
              <p className="text-[#6b6b6b] mt-2">
                {statusFilter
                  ? `No ${statusFilter.toLowerCase()} decisions in the last ${days} days.`
                  : `No ESL decisions in the last ${days} days.`}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[rgba(0,0,0,0.06)]">
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Time</th>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Action</th>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Decision</th>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => {
                    const config = decisionConfig[log.decision_status]
                    const Icon = config.icon
                    return (
                      <tr key={log.id} className="border-b border-[rgba(0,0,0,0.04)] last:border-0">
                        <td className="py-3 px-4 text-sm">
                          <div className="flex items-center gap-2 text-[#6b6b6b]">
                            <Clock className="h-3 w-3" />
                            {formatTime(log.timestamp)}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-sm font-medium text-[#0a0a0a]">
                          {formatActionType(log.action_type)}
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant="outline" className={`${config.color} rounded-full px-2.5 py-0.5 text-xs`}>
                            <Icon className="h-3 w-3 mr-1" />
                            {config.label}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-sm text-[#6b6b6b] max-w-xs truncate">
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
    </div>
  )
}
