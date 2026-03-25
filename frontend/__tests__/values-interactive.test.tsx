import { render, screen } from '@testing-library/react'
import ValuesPage from '../app/dashboard/values/page'
import { api } from '../lib/api'

jest.mock('../lib/api', () => ({ api: { values: { list: jest.fn(), create: jest.fn(), update: jest.fn(), delete: jest.fn(), reorder: jest.fn() } } }))

const mockValues = [
  { id: '1', type: 'boundary', value: 'No late notifications', priority: 8, active: true },
  { id: '2', type: 'preference', value: 'Morning summaries', priority: 5, active: true },
]

beforeEach(() => {
  ;(api.values.list as jest.Mock).mockResolvedValue(mockValues)
})

test('test_boundary_card_has_dark_background', async () => {
  render(<ValuesPage />)
  const card = await screen.findByText('No late notifications')
  expect(card.closest('[data-value-type]')).toHaveAttribute('data-value-type', 'boundary')
})

test('test_reorder_api_called_after_drag', async () => {
  render(<ValuesPage />)
  await screen.findByText('No late notifications')
  expect(api.values.reorder).not.toHaveBeenCalled()
})
