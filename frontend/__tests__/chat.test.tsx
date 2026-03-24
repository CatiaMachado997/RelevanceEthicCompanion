import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatPage from '../app/dashboard/chat/page'
import api from '../lib/api'

jest.mock('../lib/api', () => ({
  __esModule: true,
  default: {
    chat: {
      history: jest.fn(),
      send: jest.fn(),
    },
  },
}))

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    value: jest.fn(),
    writable: true,
  })
})

beforeEach(() => {
  jest.resetAllMocks()
  ;(api.chat.history as jest.Mock).mockResolvedValue({ messages: [] })
  ;(api.chat.send as jest.Mock).mockResolvedValue({
    response: 'Hello from AI',
    timestamp: new Date().toISOString(),
    esl_decision: null,
  })
})

test('test_chat_loads_history_on_mount', async () => {
  render(<ChatPage />)
  await waitFor(() => expect(api.chat.history).toHaveBeenCalledTimes(1))
})

test('test_empty_chat_shows_example_prompts', async () => {
  render(<ChatPage />)
  await waitFor(() => expect(api.chat.history).toHaveBeenCalled())
  expect(await screen.findByText("What's on my agenda today?")).toBeInTheDocument()
})

test('test_send_message_calls_api', async () => {
  render(<ChatPage />)
  await waitFor(() => expect(api.chat.history).toHaveBeenCalled())

  const textarea = screen.getByPlaceholderText(/message your companion/i)
  await userEvent.type(textarea, 'Hello{Enter}')

  await waitFor(() => {
    expect(api.chat.send).toHaveBeenCalledWith('Hello')
  })
})

test('test_assistant_response_renders', async () => {
  render(<ChatPage />)
  await waitFor(() => expect(api.chat.history).toHaveBeenCalled())

  const textarea = screen.getByPlaceholderText(/message your companion/i)
  await userEvent.type(textarea, 'Hi{Enter}')

  expect(await screen.findByText('Hello from AI')).toBeInTheDocument()
})
