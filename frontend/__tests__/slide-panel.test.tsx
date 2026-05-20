import { useState } from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SlidePanel } from '../components/slide-panel'

// Minimal harness: a button that opens the panel — gives us a real
// "previously focused" element so the focus-restore assertion is meaningful.
function Harness({ initialOpen = false }: { initialOpen?: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  return (
    <>
      <button onClick={() => setOpen(true)}>Open Panel</button>
      <SlidePanel open={open} onClose={() => setOpen(false)} title="Test panel">
        <button>Inside A</button>
        <button>Inside B</button>
        <button>Inside C</button>
      </SlidePanel>
    </>
  )
}

test('focus moves into the panel on open', async () => {
  render(<Harness />)
  const opener = screen.getByRole('button', { name: 'Open Panel' })
  opener.focus()
  expect(opener).toHaveFocus()

  await userEvent.click(opener)

  // First focusable inside the panel is the close (X) button —
  // it has aria-label="Close panel".
  expect(screen.getByLabelText('Close panel')).toHaveFocus()
})

test('Tab from the last focusable wraps to the first', async () => {
  render(<Harness initialOpen />)
  // After mount, focus has been moved to the close button.
  const close = screen.getByLabelText('Close panel')
  expect(close).toHaveFocus()

  // Walk to the last focusable inside the panel.
  const last = screen.getByRole('button', { name: 'Inside C' })
  last.focus()
  expect(last).toHaveFocus()

  // Tab should wrap back to the close button (the first focusable).
  await userEvent.tab()
  expect(close).toHaveFocus()
})

test('Shift+Tab from the first focusable wraps to the last', async () => {
  render(<Harness initialOpen />)
  const close = screen.getByLabelText('Close panel')
  close.focus()
  expect(close).toHaveFocus()

  await userEvent.tab({ shift: true })

  const last = screen.getByRole('button', { name: 'Inside C' })
  expect(last).toHaveFocus()
})

test('focus is restored to the trigger when the panel closes', async () => {
  render(<Harness />)
  const opener = screen.getByRole('button', { name: 'Open Panel' })
  opener.focus()
  await userEvent.click(opener)

  // Sanity: focus is now inside the panel.
  expect(screen.getByLabelText('Close panel')).toHaveFocus()

  // Closing via Escape — already supported, used here as the trigger.
  await act(async () => {
    fireEvent.keyDown(window, { key: 'Escape' })
  })

  expect(opener).toHaveFocus()
})
