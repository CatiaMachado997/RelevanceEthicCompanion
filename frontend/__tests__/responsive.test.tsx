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

jest.mock('../components/sidebar', () => ({
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  SidebarNav: function MockSidebar() { return require('react').createElement('nav', { 'data-testid': 'sidebar' }) },
}))

jest.mock('../components/top-bar', () => ({
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  TopBar: function MockTopBar() { return require('react').createElement('div', { 'data-testid': 'top-bar' }) },
}))

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => '/dashboard',
}))

test('test_mobile_menu_button_exists', () => {
  render(<DashboardLayout><div>content</div></DashboardLayout>)
  expect(screen.getByLabelText(/menu/i)).toBeInTheDocument()
})
