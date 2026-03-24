import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SearchPage from '../app/dashboard/search/page'
import { valuesApi, goalsApi, chatApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  valuesApi: { list: jest.fn() },
  goalsApi: { list: jest.fn() },
  chatApi: { history: jest.fn() },
}))

beforeEach(() => {
  jest.resetAllMocks()
  localStorage.clear()
  ;(valuesApi.list as jest.Mock).mockResolvedValue({ values: [] })
  ;(goalsApi.list as jest.Mock).mockResolvedValue({ goals: [] })
  ;(chatApi.history as jest.Mock).mockResolvedValue({ messages: [] })
})

test('test_shows_empty_state_initially', () => {
  render(<SearchPage />)
  expect(screen.getByText('Start searching')).toBeInTheDocument()
})

test('test_search_returns_value_results', async () => {
  ;(valuesApi.list as jest.Mock).mockResolvedValue({
    values: [{
      id: 'v1',
      type: 'boundary',
      value: 'no_work_after_19h',
      priority: 5,
      created_at: new Date().toISOString(),
    }]
  })

  render(<SearchPage />)
  const input = screen.getByPlaceholderText('Search...')
  await userEvent.type(input, 'boundary{Enter}')

  expect(await screen.findByText('no_work_after_19h')).toBeInTheDocument()
})

test('test_clear_button_resets_query', async () => {
  render(<SearchPage />)
  const input = screen.getByPlaceholderText('Search...')
  await userEvent.type(input, 'hello')

  await userEvent.click(screen.getByRole('button', { name: '' })) // X button

  expect(input).toHaveValue('')
})

test('test_recent_searches_shown_from_localstorage', () => {
  localStorage.setItem('recentSearches', JSON.stringify(['my old search']))
  render(<SearchPage />)
  expect(screen.getByText('my old search')).toBeInTheDocument()
})
