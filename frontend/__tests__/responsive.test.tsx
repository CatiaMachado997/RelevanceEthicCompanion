import { render, screen } from '@testing-library/react'
import DashboardLayout from '../app/dashboard/layout'

jest.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ user: null, loading: false, isAuthenticated: false }),
}))

jest.mock('../lib/api', () => ({
  configureApiAuth: jest.fn(),
}))

jest.mock('../lib/supabase', () => ({
  supabase: { auth: { getSession: jest.fn().mockResolvedValue({ data: { session: null } }) } },
}))

jest.mock('../components/sidebar', () => {
  const React = jest.requireActual<typeof import('react')>('react')
  return {
    SidebarNav: function MockSidebar() { return React.createElement('nav', { 'data-testid': 'sidebar' }) },
  }
})

jest.mock('../components/top-bar', () => {
  const React = jest.requireActual<typeof import('react')>('react')
  return {
    TopBar: function MockTopBar() { return React.createElement('div', { 'data-testid': 'top-bar' }) },
  }
})

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => '/dashboard',
}))

test('test_mobile_menu_button_exists', () => {
  render(<DashboardLayout><div>content</div></DashboardLayout>)
  expect(screen.getByLabelText(/menu/i)).toBeInTheDocument()
})
