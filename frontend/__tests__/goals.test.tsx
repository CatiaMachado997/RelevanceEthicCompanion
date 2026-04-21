import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GoalsPage from '../app/dashboard/goals/page'
import { goalsApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  goalsApi: {
    list: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
}))

const MOCK_GOAL = {
  id: 'goal-1',
  title: 'Launch MVP',
  description: 'Ship version 1',
  priority: 3,
  status: 'active',
  target_date: null,
  created_at: new Date().toISOString(),
}

beforeEach(() => {
  jest.resetAllMocks()
  ;(goalsApi.list as jest.Mock).mockResolvedValue({ goals: [MOCK_GOAL] })
  ;(goalsApi.create as jest.Mock).mockResolvedValue({ ...MOCK_GOAL, id: 'goal-2', title: 'New Goal' })
  ;(goalsApi.update as jest.Mock).mockResolvedValue({ ...MOCK_GOAL, status: 'completed' })
  ;(goalsApi.delete as jest.Mock).mockResolvedValue(undefined)
})

test('test_goals_loads_on_mount', async () => {
  render(<GoalsPage />)
  await waitFor(() => expect(goalsApi.list).toHaveBeenCalledTimes(1))
  expect(await screen.findByText('Launch MVP')).toBeInTheDocument()
})

test('test_empty_state_when_no_goals', async () => {
  ;(goalsApi.list as jest.Mock).mockResolvedValue({ goals: [] })
  render(<GoalsPage />)
  await waitFor(() => expect(goalsApi.list).toHaveBeenCalled())
  expect(await screen.findByText(/No active goals/i)).toBeInTheDocument()
})

test('test_add_goal_sheet_opens', async () => {
  render(<GoalsPage />)
  await waitFor(() => expect(goalsApi.list).toHaveBeenCalled())
  await userEvent.click(screen.getByRole('button', { name: /add goal/i }))
  expect(await screen.findByText('Add Goal', { selector: 'h3' })).toBeInTheDocument()
})

test('test_save_disabled_when_title_empty', async () => {
  render(<GoalsPage />)
  await waitFor(() => expect(goalsApi.list).toHaveBeenCalled())
  await userEvent.click(screen.getByRole('button', { name: /add goal/i }))
  await screen.findByText('Add Goal', { selector: 'h3' })
  const saveBtn = screen.getByRole('button', { name: /save/i })
  expect(saveBtn).toBeDisabled()
})

test('test_create_goal_calls_api', async () => {
  render(<GoalsPage />)
  await waitFor(() => expect(goalsApi.list).toHaveBeenCalled())
  await userEvent.click(screen.getByRole('button', { name: /add goal/i }))
  await screen.findByText('Add Goal', { selector: 'h3' })

  const titleInput = screen.getByPlaceholderText(/e\.g\. Ship new feature/i)
  await userEvent.type(titleInput, 'New Goal')
  await userEvent.click(screen.getByRole('button', { name: /save/i }))

  await waitFor(() => {
    expect(goalsApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'New Goal' })
    )
  })
})
