import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

jest.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      onAuthStateChange: jest.fn(() => ({
        data: { subscription: { unsubscribe: jest.fn() } },
      })),
      signInWithOtp: jest.fn(),
      signOut: jest.fn(),
    },
  },
}))

import { supabase } from '../lib/supabase'
import { useAuth } from '../hooks/useAuth'

function TestComponent() {
  const { user, loading, isAuthenticated, signIn, signOut } = useAuth()
  if (loading) return <div>Loading</div>
  if (!isAuthenticated) return (
    <div>
      <span>Not signed in</span>
      <button onClick={() => signIn('test@example.com')}>Sign In</button>
    </div>
  )
  return (
    <div>
      <span>{user!.email}</span>
      <button onClick={signOut}>Sign Out</button>
    </div>
  )
}

beforeEach(() => jest.resetAllMocks())

test('test_shows_loading_then_unauthenticated', async () => {
  ;(supabase.auth.onAuthStateChange as jest.Mock).mockImplementation((cb) => {
    cb('INITIAL_SESSION', null)
    return { data: { subscription: { unsubscribe: jest.fn() } } }
  })
  render(<TestComponent />)
  expect(await screen.findByText('Not signed in')).toBeInTheDocument()
})

test('test_shows_user_when_authenticated', async () => {
  const mockUser = { id: 'user-1', email: 'jane@example.com' }
  ;(supabase.auth.onAuthStateChange as jest.Mock).mockImplementation((cb) => {
    cb('SIGNED_IN', { user: mockUser })
    return { data: { subscription: { unsubscribe: jest.fn() } } }
  })
  render(<TestComponent />)
  expect(await screen.findByText('jane@example.com')).toBeInTheDocument()
})

test('test_signIn_calls_supabase_otp', async () => {
  ;(supabase.auth.onAuthStateChange as jest.Mock).mockImplementation((cb) => {
    cb('INITIAL_SESSION', null)
    return { data: { subscription: { unsubscribe: jest.fn() } } }
  })
  ;(supabase.auth.signInWithOtp as jest.Mock).mockResolvedValue({ error: null })
  render(<TestComponent />)
  await screen.findByText('Not signed in')
  await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
  expect(supabase.auth.signInWithOtp).toHaveBeenCalledWith(
    expect.objectContaining({ email: 'test@example.com' })
  )
})

test('test_signOut_calls_supabase_signOut', async () => {
  const mockUser = { id: 'user-1', email: 'jane@example.com' }
  ;(supabase.auth.onAuthStateChange as jest.Mock).mockImplementation((cb) => {
    cb('SIGNED_IN', { user: mockUser })
    return { data: { subscription: { unsubscribe: jest.fn() } } }
  })
  ;(supabase.auth.signOut as jest.Mock).mockResolvedValue({ error: null })
  render(<TestComponent />)
  await screen.findByText('jane@example.com')
  await userEvent.click(screen.getByRole('button', { name: 'Sign Out' }))
  expect(supabase.auth.signOut).toHaveBeenCalledTimes(1)
})
