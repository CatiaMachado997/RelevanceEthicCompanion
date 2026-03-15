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

test('test_save_button_disabled_when_clean', async () => {
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())
  const saveButton = screen.getByRole('button', { name: /save settings/i })
  expect(saveButton).toBeDisabled()
})

test('test_save_button_enabled_after_toggle', async () => {
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())

  // Toggle the Email Notifications switch (first switch, index 0 — currently off)
  const switches = screen.getAllByRole('switch')
  await userEvent.click(switches[0])

  const saveButton = screen.getByRole('button', { name: /save settings/i })
  expect(saveButton).not.toBeDisabled()
})

test('test_save_calls_api', async () => {
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())

  // Toggle the Email Notifications switch (first switch, index 0)
  const switches = screen.getAllByRole('switch')
  await userEvent.click(switches[0])

  const saveButton = screen.getByRole('button', { name: /save settings/i })
  await userEvent.click(saveButton)

  await waitFor(() => {
    expect(settingsApi.update).toHaveBeenCalledWith(
      expect.objectContaining({ email_notifications: true })
    )
  })
})
