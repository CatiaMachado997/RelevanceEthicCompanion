import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SearchPage from '../app/dashboard/search/page'
import { searchApi } from '../lib/api'

// The search page now uses Weaviate semantic search via `searchApi.query`
// (no more values/goals/chat fan-out from the old UI).
jest.mock('../lib/api', () => ({
  searchApi: { query: jest.fn() },
}))

beforeEach(() => {
  jest.resetAllMocks()
  localStorage.clear()
  ;(searchApi.query as jest.Mock).mockResolvedValue([])
})

test('test_renders_search_input', () => {
  render(<SearchPage />)
  expect(
    screen.getByPlaceholderText(/search your memories/i)
  ).toBeInTheDocument()
})

test('test_search_calls_api_on_enter', async () => {
  render(<SearchPage />)
  const input = screen.getByPlaceholderText(/search your memories/i)
  await userEvent.type(input, 'boundary{Enter}')

  await waitFor(() => {
    expect(searchApi.query).toHaveBeenCalledWith('boundary', 20)
  })
})

test('test_clear_button_resets_query', async () => {
  render(<SearchPage />)
  const input = screen.getByPlaceholderText(/search your memories/i)
  await userEvent.type(input, 'hello')

  await userEvent.click(
    screen.getByRole('button', { name: /clear search/i })
  )

  expect(input).toHaveValue('')
})

test('test_recent_searches_shown_from_localstorage', () => {
  localStorage.setItem('recentSearches', JSON.stringify(['my old search']))
  render(<SearchPage />)
  expect(screen.getByText('my old search')).toBeInTheDocument()
})
