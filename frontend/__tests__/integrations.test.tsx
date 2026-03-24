import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IntegrationsPage from '../app/dashboard/integrations/page'
import { dataSourcesApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  dataSourcesApi: {
    list: jest.fn(),
    getAuthUrl: jest.fn(),
    disconnect: jest.fn(),
    sync: jest.fn(),
  },
}))

jest.mock('next/navigation', () => ({
  useSearchParams: () => ({
    get: jest.fn(() => null),
  }),
}))

beforeEach(() => {
  jest.resetAllMocks()
  ;(dataSourcesApi.list as jest.Mock).mockResolvedValue({ sources: [] })
})

test('test_integrations_loads_connected_sources', async () => {
  render(<IntegrationsPage />)
  await waitFor(() => expect(dataSourcesApi.list).toHaveBeenCalledTimes(1))
})

test('test_shows_google_calendar_card', async () => {
  render(<IntegrationsPage />)
  expect(await screen.findByText('Google Calendar')).toBeInTheDocument()
})

test('test_shows_gmail_card', async () => {
  render(<IntegrationsPage />)
  expect(await screen.findByText('Gmail')).toBeInTheDocument()
})

test('test_shows_slack_card', async () => {
  render(<IntegrationsPage />)
  expect(await screen.findByText('Slack')).toBeInTheDocument()
})

test('test_connect_button_calls_auth_url', async () => {
  ;(dataSourcesApi.getAuthUrl as jest.Mock).mockResolvedValue({ authorization_url: 'https://accounts.google.com/...' })

  render(<IntegrationsPage />)
  await waitFor(() => expect(dataSourcesApi.list).toHaveBeenCalled())

  const connectBtns = await screen.findAllByRole('button', { name: /connect/i })
  await userEvent.click(connectBtns[0])

  await waitFor(() => expect(dataSourcesApi.getAuthUrl).toHaveBeenCalled())
})
