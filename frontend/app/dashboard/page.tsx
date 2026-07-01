'use client'

import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ToolsLauncher } from '@/components/tools-launcher'
import { DashboardHero, RecentConversations } from '@/components/dashboard-hero'
import { WeeklyReviewCard } from '@/components/dashboard/WeeklyReviewCard'

/**
 * Dashboard home — three sections only:
 *
 *   1. Hero        — greeting + quick actions, with today's next event
 *                    and the daily insight folded in (one line each).
 *   2. Tools       — launcher tiles for Goals/Tasks/Projects/etc.
 *   3. Recent chat — last 5 conversations.
 *
 * The earlier "Today" / "Daily insight" / "ESL activity" sections have
 * been retired:
 *   - Today's tasks-due-soon and active-projects duplicated /dashboard/tasks
 *     and /dashboard/projects respectively.
 *   - Today's upcoming-events moved into the hero ("Next up:" chip).
 *   - The daily insight moved into the hero (italic line).
 *   - The ESL activity card collapsed into the Transparency tile, which
 *     now shows "{rate}% approved · 7d" as its subtitle.
 *
 * Net effect: less scroll, no redundancy, a single decision per row.
 */
export default function DashboardPage() {
  return (
    <ErrorBoundary>
      <div className="p-6 max-w-4xl mx-auto space-y-8">
        <DashboardHero />
        <WeeklyReviewCard />
        <ToolsLauncher />
        <RecentConversations />
      </div>
    </ErrorBoundary>
  )
}
