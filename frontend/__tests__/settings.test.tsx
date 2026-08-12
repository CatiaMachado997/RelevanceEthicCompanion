import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SettingsPage from '../app/dashboard/settings/page'
import { settingsApi, dataSourcesApi, memoriesApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  settingsApi: {
    get: jest.fn(),
    update: jest.fn(),
  },
  dataSourcesApi: {
    list: jest.fn(),
    getAuthUrl: jest.fn(),
    disconnect: jest.fn(),
    sync: jest.fn(),
  },
  memoriesApi: {
    list: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    forget: jest.fn(),
  },
}))

jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/settings',
  useRouter: () => ({ push: jest.fn() }),
}))

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: { email: 'test@example.com' } }),
}))

jest.mock('../components/mobile-sidebar', () => ({
  MobileSidebar: () => null,
}))

const DEFAULT_SETTINGS = {
  email_notifications: false,
  push_notifications: false,
  esl_alerts: true,
  share_analytics: false,
  pii_protection: true,
}

beforeEach(() => {
  jest.resetAllMocks()
  ;(settingsApi.get as jest.Mock).mockResolvedValue(DEFAULT_SETTINGS)
  ;(settingsApi.update as jest.Mock).mockResolvedValue(DEFAULT_SETTINGS)
  ;(dataSourcesApi.list as jest.Mock).mockResolvedValue({ sources: [] })
  ;(dataSourcesApi.getAuthUrl as jest.Mock).mockResolvedValue({ authorization_url: 'http://example.com' })
  ;(dataSourcesApi.disconnect as jest.Mock).mockResolvedValue(undefined)
  ;(dataSourcesApi.sync as jest.Mock).mockResolvedValue(undefined)
  ;(memoriesApi.list as jest.Mock).mockResolvedValue({ memories: [] })
  ;(memoriesApi.update as jest.Mock).mockImplementation(async (id, changes) => ({
    id,
    content: changes.content ?? 'Prefer four-week plans.',
    kind: 'preference',
    active: true,
    created_at: '2026-08-11T10:00:00Z',
    updated_at: '2026-08-11T10:05:00Z',
  }))
})

test('test_settings_loads_on_mount', async () => {
  render(<SettingsPage />)
  await waitFor(() => {
    expect(settingsApi.get).toHaveBeenCalledTimes(1)
  })
})

test('test_save_button_hidden_when_clean', async () => {
  // The save bar is rendered only when the form is dirty — cleaner UX
  // than "disabled button always visible".
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())
  expect(
    screen.queryByRole('button', { name: /save settings/i })
  ).not.toBeInTheDocument()
})

test('test_save_button_appears_after_toggle', async () => {
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())

  await userEvent.click(
    screen.getByRole('switch', { name: /email notifications/i })
  )

  const saveButton = screen.getByRole('button', { name: /save settings/i })
  expect(saveButton).not.toBeDisabled()
})

test('test_save_calls_api', async () => {
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())

  await userEvent.click(
    screen.getByRole('switch', { name: /email notifications/i })
  )

  const saveButton = screen.getByRole('button', { name: /save settings/i })
  await userEvent.click(saveButton)

  await waitFor(() => {
    expect(settingsApi.update).toHaveBeenCalledWith(
      expect.objectContaining({ email_notifications: true })
    )
  })
})

test('test_user_can_correct_saved_memory', async () => {
  ;(memoriesApi.list as jest.Mock).mockResolvedValue({
    memories: [{
      id: 'memory-1',
      content: 'Prefer four-week plans.',
      kind: 'preference',
      active: true,
      created_at: '2026-08-11T10:00:00Z',
      updated_at: '2026-08-11T10:00:00Z',
    }],
  })

  render(<SettingsPage />)
  await screen.findByText('Prefer four-week plans.')

  await userEvent.click(screen.getByRole('button', { name: /correct memory/i }))
  const input = screen.getByRole('textbox', { name: /correct memory/i })
  await userEvent.clear(input)
  await userEvent.type(input, 'Prefer two-week plans.')
  await userEvent.click(screen.getByRole('button', { name: /save correction/i }))

  await waitFor(() => {
    expect(memoriesApi.update).toHaveBeenCalledWith('memory-1', {
      content: 'Prefer two-week plans.',
    })
  })
  expect(await screen.findByText('Prefer two-week plans.')).toBeInTheDocument()
})
