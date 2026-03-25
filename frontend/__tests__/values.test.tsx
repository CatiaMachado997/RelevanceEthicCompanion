import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ValuesPage from '../app/dashboard/values/page'
import { api } from '../lib/api'

jest.mock('../lib/api', () => ({
  __esModule: true,
  api: {
    values: {
      list: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      delete: jest.fn(),
      reorder: jest.fn(),
    },
  },
}))

const MOCK_VALUE = {
  id: 'val-1',
  type: 'boundary',
  value: 'no_work_after_19h',
  priority: 5,
  created_at: new Date().toISOString(),
}

beforeEach(() => {
  jest.resetAllMocks()
  ;(api.values.list as jest.Mock).mockResolvedValue([MOCK_VALUE])
  ;(api.values.create as jest.Mock).mockResolvedValue({ ...MOCK_VALUE, id: 'val-2' })
  ;(api.values.delete as jest.Mock).mockResolvedValue(undefined)
  ;(api.values.reorder as jest.Mock).mockResolvedValue({ status: 'ok', message: 'reordered' })
})

test('test_values_loads_on_mount', async () => {
  render(<ValuesPage />)
  await waitFor(() => expect(api.values.list).toHaveBeenCalledTimes(1))
  expect(await screen.findByText('no_work_after_19h')).toBeInTheDocument()
})

test('test_empty_state_when_no_values', async () => {
  ;(api.values.list as jest.Mock).mockResolvedValue([])
  render(<ValuesPage />)
  await waitFor(() => expect(api.values.list).toHaveBeenCalled())
  expect(await screen.findByText(/No values yet/i)).toBeInTheDocument()
})

test('test_add_value_sheet_opens', async () => {
  render(<ValuesPage />)
  await waitFor(() => expect(api.values.list).toHaveBeenCalled())
  await userEvent.click(screen.getByRole('button', { name: /add value/i }))
  expect(await screen.findByText('Add Value', { selector: 'h3' })).toBeInTheDocument()
})

test('test_create_value_calls_api', async () => {
  render(<ValuesPage />)
  await waitFor(() => expect(api.values.list).toHaveBeenCalled())
  await userEvent.click(screen.getByRole('button', { name: /add value/i }))
  await screen.findByText('Add Value', { selector: 'h3' })

  const textarea = screen.getByPlaceholderText(/e.g. no_work_after_19h/i)
  await userEvent.type(textarea, 'no_social_media')
  await userEvent.click(screen.getByRole('button', { name: /save/i }))

  await waitFor(() => {
    expect(api.values.create).toHaveBeenCalledWith(
      expect.objectContaining({ value: 'no_social_media' })
    )
  })
})

test('test_delete_value_calls_api', async () => {
  render(<ValuesPage />)
  await waitFor(() => expect(api.values.list).toHaveBeenCalled())
  await screen.findByText('no_work_after_19h')

  await userEvent.click(screen.getByRole('button', { name: /delete value/i }))

  await waitFor(() => {
    expect(api.values.delete).toHaveBeenCalledWith('val-1')
  })
})
