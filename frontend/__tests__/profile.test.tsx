import { render, screen } from '@testing-library/react'
import ProfilePage from '../app/dashboard/profile/page'

jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/profile',
  useRouter: () => ({ push: jest.fn() }),
}))

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: { email: 'jane@example.com' } }),
}))

jest.mock('../components/mobile-sidebar', () => ({
  MobileSidebar: () => null,
}))

test('test_renders_user_email', () => {
  render(<ProfilePage />)
  expect(screen.getByText('jane@example.com')).toBeInTheDocument()
})

test('test_renders_avatar_initials', () => {
  render(<ProfilePage />)
  expect(screen.getAllByText('JA').length).toBeGreaterThan(0)
})

test('test_renders_static_stats', () => {
  render(<ProfilePage />)
  expect(screen.getByText('Values Set')).toBeInTheDocument()
  expect(screen.getByText('Active Goals')).toBeInTheDocument()
  expect(screen.getByText('ESL Approval Rate')).toBeInTheDocument()
})
