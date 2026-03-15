import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NotificationsPage from '../app/dashboard/notifications/page'
import { notificationsApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  notificationsApi: {
    list: jest.fn(),
    markRead: jest.fn(),
    markAllRead: jest.fn(),
  },
}))

jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/notifications',
  useRouter: () => ({ push: jest.fn() }),
}))

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: { email: 'test@example.com' } }),
}))

jest.mock('../components/mobile-sidebar', () => ({
  MobileSidebar: () => null,
}))

const MOCK_NOTIFICATION = {
  id: 'notif-1',
  user_id: 'user-1',
  type: 'goal_completed',
  title: 'Goal achieved!',
  message: 'You completed your first goal.',
  read: false,
  created_at: new Date().toISOString(),
}

beforeEach(() => {
  jest.resetAllMocks()
  ;(notificationsApi.list as jest.Mock).mockResolvedValue({
    notifications: [MOCK_NOTIFICATION],
    unread_count: 1,
  })
  ;(notificationsApi.markRead as jest.Mock).mockResolvedValue(undefined)
  ;(notificationsApi.markAllRead as jest.Mock).mockResolvedValue(undefined)
})

test('test_notifications_loads_on_mount', async () => {
  render(<NotificationsPage />)
  await waitFor(() => {
    expect(notificationsApi.list).toHaveBeenCalledTimes(1)
  })
  expect(await screen.findByText('Goal achieved!')).toBeInTheDocument()
})

test('test_mark_all_read_hidden_when_no_unread', async () => {
  ;(notificationsApi.list as jest.Mock).mockResolvedValue({
    notifications: [{ ...MOCK_NOTIFICATION, read: true }],
    unread_count: 0,
  })

  render(<NotificationsPage />)
  await waitFor(() => expect(notificationsApi.list).toHaveBeenCalled())

  expect(screen.queryByRole('button', { name: /mark all read/i })).not.toBeInTheDocument()
})

test('test_mark_all_read_visible_when_unread', async () => {
  render(<NotificationsPage />)
  await waitFor(() => expect(notificationsApi.list).toHaveBeenCalled())

  expect(await screen.findByRole('button', { name: /mark all read/i })).toBeInTheDocument()
})

test('test_click_unread_card_marks_read', async () => {
  render(<NotificationsPage />)
  const card = await screen.findByText('Goal achieved!')
  await userEvent.click(card)

  await waitFor(() => {
    expect(notificationsApi.markRead).toHaveBeenCalledWith('notif-1')
  })
})
