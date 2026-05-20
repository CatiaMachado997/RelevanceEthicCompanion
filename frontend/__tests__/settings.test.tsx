import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SettingsPage from '../app/dashboard/settings/page'
import { settingsApi, dataSourcesApi } from '../lib/api'

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
