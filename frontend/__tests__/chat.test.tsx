import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatPage from '../app/dashboard/chat/page'
import api from '../lib/api'

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: null }),
}))

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/dashboard/chat',
  useSearchParams: () => new URLSearchParams(),
}))

jest.mock('../lib/api', () => ({
  __esModule: true,
  default: {
    chat: {
      history: jest.fn(),
      send: jest.fn(),
      stream: jest.fn(),
      conversations: {
        create: jest.fn(),
        list: jest.fn(),
        delete: jest.fn(),
        update: jest.fn(),
      },
    },
  },
}))

// react-markdown and its remark plugins are ESM-only, which Jest's default
// CJS transform can't load. Mock it with a trivial passthrough — chat tests
// only care that the assistant text is rendered, not that Markdown syntax
// produces HTML.
jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }: { children: string }) => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mockReact: typeof import('react') = require('react')
    return mockReact.createElement('div', null, children)
  },
}))
jest.mock('remark-gfm', () => ({ __esModule: true, default: () => {} }))

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
  ;(api.chat.conversations.create as jest.Mock).mockResolvedValue({
    id: 'test-conv-id',
    title: 'New conversation',
  })
  // api.chat.stream signature: (message, options) where options includes
  // onToken, onToolUse, etc.
  ;(api.chat.stream as jest.Mock).mockImplementation(
    (_msg: string, opts: { onToken?: (t: string) => void }) => {
      let cancelled = false
      const promise = new Promise<void>((resolve) => {
        Promise.resolve().then(() => {
          if (!cancelled) {
            opts.onToken?.('Hello from AI')
            resolve()
          }
        })
      }) as Promise<void> & { cancel: () => void }
      promise.cancel = () => {
        cancelled = true
      }
      return promise
    }
  )
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
    expect(api.chat.stream).toHaveBeenCalledWith(
      'Hello',
      expect.objectContaining({ onToken: expect.any(Function) })
    )
  })
})

test('test_assistant_response_renders', async () => {
  render(<ChatPage />)
  await waitFor(() => expect(api.chat.history).toHaveBeenCalled())

  const textarea = screen.getByPlaceholderText(/message your companion/i)
  await userEvent.type(textarea, 'Hi{Enter}')

  expect(await screen.findByText('Hello from AI')).toBeInTheDocument()
})
