import type { PropsWithChildren } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import TransparencyPage from '../app/dashboard/transparency/page'
import { api } from '../lib/api'

jest.mock('../lib/api', () => ({
  api: {
    transparency: {
      report: jest.fn(),
      stats: jest.fn(),
      logs: jest.fn(),
      insights: jest.fn(),
    }
  },
  transparencyApi: {
    report: jest.fn(),
    stats: jest.fn(),
    logs: jest.fn(),
    insights: jest.fn(),
  },
}))

jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/transparency',
  useRouter: () => ({ push: jest.fn() }),
}))

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: { email: 'test@example.com' } }),
}))

jest.mock('../components/mobile-sidebar', () => ({
  MobileSidebar: () => null,
}))

jest.mock('recharts', () => {
  // jest.mock factories are hoisted above imports and may not reference
  // out-of-scope variables (unless prefixed `mock*`). Lazy-require React
  // here so it resolves at factory-run time.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mockReact: typeof import('react') = require('react')
  return {
    PieChart: ({ children }: PropsWithChildren) =>
      mockReact.createElement('div', { 'data-testid': 'pie-chart' }, children),
    Pie: () => null,
    Cell: () => null,
    LineChart: ({ children }: PropsWithChildren) =>
      mockReact.createElement('div', { 'data-testid': 'line-chart' }, children),
    Line: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    ResponsiveContainer: ({ children }: PropsWithChildren) =>
      mockReact.createElement('div', null, children),
    BarChart: ({ children }: PropsWithChildren) =>
      mockReact.createElement('div', { 'data-testid': 'bar-chart' }, children),
    Bar: () => null,
  }
})

beforeEach(() => {
  ;(api.transparency.report as jest.Mock).mockResolvedValue({
    total_decisions: 42, approved_count: 35, vetoed_count: 5, modified_count: 2, approval_rate: 83.3
  })
  ;(api.transparency.stats as jest.Mock).mockResolvedValue({
    decision_breakdown: { APPROVED: 35, VETOED: 5, MODIFIED: 2 },
    most_protected_values: [{ value: 'No late notifications', count: 3 }],
    most_applied_rules: []
  })
  ;(api.transparency.logs as jest.Mock).mockResolvedValue([])
  ;(api.transparency.insights as jest.Mock).mockResolvedValue([])
})

test('test_transparency_shows_pie_chart', async () => {
  render(<TransparencyPage />)
  await waitFor(() => expect(screen.getByTestId('pie-chart')).toBeInTheDocument())
})

test('test_transparency_shows_line_chart', async () => {
  render(<TransparencyPage />)
  await waitFor(() => expect(screen.getByTestId('line-chart')).toBeInTheDocument())
})

test('test_transparency_shows_bar_chart', async () => {
  render(<TransparencyPage />)
  await waitFor(() => expect(screen.getByTestId('bar-chart')).toBeInTheDocument())
})
