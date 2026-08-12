import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IntegrationsPage from '../app/dashboard/integrations/page'
import { connectorsApi, toolMarketplaceApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  connectorsApi: {
    list: jest.fn(),
    getStatus: jest.fn(),
    reindex: jest.fn(),
  },
  toolMarketplaceApi: {
    getConnected: jest.fn(),
    getCatalogue: jest.fn(),
    connectComposio: jest.fn(),
    disconnect: jest.fn(),
    syncTool: jest.fn(),
    connectMcp: jest.fn(),
  },
}))

jest.mock('next/navigation', () => ({
  useSearchParams: () => ({
    get: jest.fn(() => null),
  }),
}))

beforeEach(() => {
  jest.resetAllMocks()
  ;(connectorsApi.list as jest.Mock).mockResolvedValue({ connectors: [] })
  ;(toolMarketplaceApi.getConnected as jest.Mock).mockResolvedValue([])
  ;(toolMarketplaceApi.getCatalogue as jest.Mock).mockResolvedValue([])
})

test('test_integrations_loads_connected_sources', async () => {
  render(<IntegrationsPage />)
  await waitFor(() => expect(toolMarketplaceApi.getConnected).toHaveBeenCalled())
  expect(connectorsApi.list).toHaveBeenCalledTimes(1)
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
  ;(toolMarketplaceApi.connectComposio as jest.Mock).mockResolvedValue('https://accounts.google.com/...')

  render(<IntegrationsPage />)
  await waitFor(() => expect(toolMarketplaceApi.getConnected).toHaveBeenCalled())

  const connectBtns = await screen.findAllByRole('button', { name: /connect/i })
  await userEvent.click(connectBtns[0])

  await waitFor(() => expect(toolMarketplaceApi.connectComposio).toHaveBeenCalled())
})
