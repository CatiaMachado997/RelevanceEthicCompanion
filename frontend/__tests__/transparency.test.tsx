import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TransparencyPage from '../app/dashboard/transparency/page'
import { transparencyApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  transparencyApi: {
    report: jest.fn(),
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

const MOCK_REPORT = {
  total_decisions: 42,
  approved_count: 35,
  vetoed_count: 4,
  modified_count: 3,
  approval_rate: 0.83,
}

const MOCK_LOG = {
  id: 'log-1',
  action_type: 'push_notification',
  decision_status: 'APPROVED' as const,
  reason: 'Within working hours',
  timestamp: new Date().toISOString(),
}

beforeEach(() => {
  jest.resetAllMocks()
  ;(transparencyApi.report as jest.Mock).mockResolvedValue(MOCK_REPORT)
  ;(transparencyApi.logs as jest.Mock).mockResolvedValue({ logs: [MOCK_LOG] })
  ;(transparencyApi.insights as jest.Mock).mockResolvedValue({ insights: [] })
})

test('test_transparency_loads_on_mount', async () => {
  render(<TransparencyPage />)
  await waitFor(() => {
    expect(transparencyApi.report).toHaveBeenCalledTimes(1)
    expect(transparencyApi.logs).toHaveBeenCalledTimes(1)
    expect(transparencyApi.insights).toHaveBeenCalledTimes(1)
  })
})

test('test_stats_render_after_load', async () => {
  render(<TransparencyPage />)
  expect(await screen.findByText('42')).toBeInTheDocument()
  expect(screen.getByText('Total Decisions')).toBeInTheDocument()
})

test('test_audit_log_entry_renders', async () => {
  render(<TransparencyPage />)
  expect(await screen.findByText('Push Notification')).toBeInTheDocument()
  expect(screen.getByText('Within working hours')).toBeInTheDocument()
})

test('test_empty_logs_state', async () => {
  ;(transparencyApi.logs as jest.Mock).mockResolvedValue({ logs: [] })
  render(<TransparencyPage />)
  expect(await screen.findByText('No logs found')).toBeInTheDocument()
})

test('test_status_filter_refetches_with_filter', async () => {
  render(<TransparencyPage />)
  await waitFor(() => expect(transparencyApi.logs).toHaveBeenCalledTimes(1))

  await userEvent.click(screen.getByRole('button', { name: /vetoed/i }))

  await waitFor(() => {
    expect(transparencyApi.logs).toHaveBeenCalledWith(7, 'VETOED')
  })
})
