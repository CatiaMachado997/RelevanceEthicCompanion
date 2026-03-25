import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatPage from '../app/dashboard/chat/page'
import api from '../lib/api'

// Helper to create a mock stream that immediately resolves with given tokens
function makeMockStream(tokens: string[] = ['Hello from AI']) {
  let cancelled = false
  const promise = new Promise<void>((resolve) => {
    // Use a microtask so onToken fires after the promise is returned
    Promise.resolve().then(() => {
      if (!cancelled) {
        tokens.forEach(t => {
          // invoke the onToken callback stored on the mock
          const calls = (api.chat.stream as jest.Mock).mock.calls
          if (calls.length > 0) {
            const onToken = calls[calls.length - 1][1]
            if (onToken) onToken(t)
          }
        })
        resolve()
      }
    })
  }) as Promise<void> & { cancel: () => void }
  promise.cancel = () => { cancelled = true }
  return promise
}

jest.mock('../lib/api', () => ({
  __esModule: true,
  default: {
    chat: {
      history: jest.fn(),
      send: jest.fn(),
      stream: jest.fn(),
    },
  },
}))

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    value: jest.fn(),
    writable: true,
  })
  // Mock clipboard
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: jest.fn().mockResolvedValue(undefined) },
    writable: true,
  })
})

beforeEach(() => {
  jest.resetAllMocks()
  ;(api.chat.history as jest.Mock).mockResolvedValue({ messages: [] })
  ;(api.chat.stream as jest.Mock).mockImplementation((_msg: string, onToken: (t: string) => void) => {
    let cancelled = false
    const promise = new Promise<void>((resolve) => {
      Promise.resolve().then(() => {
        if (!cancelled) {
          onToken('Hello from AI')
          resolve()
        }
      })
    }) as Promise<void> & { cancel: () => void }
    promise.cancel = () => { cancelled = true }
    return promise
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
    expect(api.chat.stream).toHaveBeenCalledWith('Hello', expect.any(Function))
  })
})

test('test_assistant_response_renders', async () => {
  render(<ChatPage />)
  await waitFor(() => expect(api.chat.history).toHaveBeenCalled())

  const textarea = screen.getByPlaceholderText(/message your companion/i)
  await userEvent.type(textarea, 'Hi{Enter}')

  expect(await screen.findByText('Hello from AI')).toBeInTheDocument()
})
