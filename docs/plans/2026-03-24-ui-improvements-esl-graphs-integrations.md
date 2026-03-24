# UI Improvements, ESL Graphs & Chat Streaming — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Ethic Companion dashboard with streaming chat (ChatGPT/Claude-style), animated/interactive values cards with drag-and-drop reorder, ESL visualisation charts on Transparency and Dashboard pages, and mobile-responsive layout throughout.

**Architecture:** Four independent chunks. Chunk 1 adds a backend SSE streaming endpoint and rewires the frontend chat page for real-time text rendering. Chunk 2 enriches the values grid with animations, colour-coding and wired drag-and-drop reorder. Chunk 3 installs recharts and adds donut/line/bar charts to Transparency + a sparkline on Dashboard using existing transparency API endpoints. Chunk 4 wires the mobile sidebar and fixes responsive grid breakpoints.

**Tech Stack:** Next.js App Router, TypeScript, Tailwind CSS, Radix UI, `@dnd-kit/sortable` (already installed), `recharts` (to install), FastAPI StreamingResponse (SSE), Jest + React Testing Library

---

## Chunk 1: Streaming Chat Interface

### Task 1: Backend — add `/api/chat/stream` SSE endpoint

**Files:**
- Modify: `backend/routes/chat.py`
- Test: `backend/tests/test_chat_stream.py`

- [ ] **Step 1: Write a failing test**

Create `backend/tests/test_chat_stream.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from main import app

@pytest.mark.asyncio
async def test_stream_endpoint_returns_event_stream():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000")
    assert response.status_code in (200, 401)  # 401 if auth enforced
```

- [ ] **Step 2: Run test — expect FAIL or 404**

```bash
cd backend && source venv/bin/activate && pytest tests/test_chat_stream.py -v
```

- [ ] **Step 3: Add streaming endpoint to `backend/routes/chat.py`**

```python
from fastapi.responses import StreamingResponse
import json

@router.get("/stream")
async def stream_chat(
    message: str,
    user_id: str = Depends(get_current_read_user_id)
):
    """Server-Sent Events endpoint for streaming chat responses."""
    async def event_generator():
        try:
            # Stream tokens from orchestrator
            full_response = ""
            async for token in orchestrator.stream_message(user_id, message):
                full_response += token
                data = json.dumps({"token": token, "done": False})
                yield f"data: {data}\n\n"
            # Final event with ESL decision
            yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

- [ ] **Step 4: Add `stream_message` to orchestrator_v2.py**

```python
async def stream_message(self, user_id: str, message: str):
    """Yield tokens from the LLM response one by one."""
    history = await self._get_conversation_history(user_id)
    system_prompt = await self._build_system_prompt(await self._get_user_context_text(user_id))
    # Use groq streaming
    stream = await self.groq_client.chat.completions.create(
        model=self.model,
        messages=[{"role": "system", "content": system_prompt}] +
                 [{"role": m.type, "content": m.content} for m in history] +
                 [{"role": "user", "content": message}],
        stream=True
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/test_chat_stream.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/routes/chat.py backend/services/orchestrator_v2.py backend/tests/test_chat_stream.py
git commit -m "feat: add SSE streaming endpoint /api/chat/stream"
```

---

### Task 2: Frontend — streaming chat UI

**Files:**
- Modify: `frontend/app/dashboard/chat/page.tsx`
- Modify: `frontend/lib/api.ts`
- Test: `frontend/__tests__/chat-streaming.test.tsx`

- [ ] **Step 1: Add streaming method to api.ts**

In `frontend/lib/api.ts`, add to the chat object:

```typescript
stream: (message: string, onToken: (token: string) => void): Promise<void> => {
  return new Promise((resolve, reject) => {
    const url = `${API_BASE_URL}/api/chat/stream?message=${encodeURIComponent(message)}`
    const es = new EventSource(url, { withCredentials: true })
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.error) { es.close(); reject(new Error(data.error)); return }
      if (data.done) { es.close(); resolve(); return }
      onToken(data.token)
    }
    es.onerror = () => { es.close(); reject(new Error('Stream error')) }
  })
},
```

- [ ] **Step 2: Update chat page for streaming**

In `frontend/app/dashboard/chat/page.tsx`, update the send handler:

```typescript
// Replace the existing handleSend with:
const handleSend = async () => {
  if (!input.trim() || isLoading) return
  const userMessage = input.trim()
  setInput('')
  setIsLoading(true)

  // Add user message immediately
  setMessages(prev => [...prev, { role: 'user', content: userMessage, timestamp: new Date().toISOString() }])

  // Add empty assistant message for streaming
  setMessages(prev => [...prev, { role: 'assistant', content: '', timestamp: new Date().toISOString(), streaming: true }])

  try {
    await api.chat.stream(userMessage, (token) => {
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last.streaming) last.content += token
        return msgs
      })
    })
    // Mark streaming complete
    setMessages(prev => {
      const msgs = [...prev]
      const last = msgs[msgs.length - 1]
      if (last.streaming) delete last.streaming
      return msgs
    })
  } catch (e) {
    console.error(e)
  } finally {
    setIsLoading(false)
  }
}
```

- [ ] **Step 3: Add copy button and timestamp to messages**

Each message bubble should show:
- Timestamp (formatted as "HH:MM")
- Copy button (clipboard icon, shown on hover)
- User avatar (user initial in a circle) or robot icon for assistant

- [ ] **Step 4: Auto-scroll behavior**

```typescript
// Track if user has scrolled up
const [userScrolled, setUserScrolled] = useState(false)
const containerRef = useRef<HTMLDivElement>(null)

// On new token, only auto-scroll if user hasn't scrolled up
useEffect(() => {
  if (!userScrolled) {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
}, [messages, userScrolled])
```

- [ ] **Step 5: Add Stop button**

While `isLoading && streamingActive`, show a Stop button that calls `eventSource.close()`.

- [ ] **Step 6: Run frontend tests**

```bash
cd frontend && npx jest --no-coverage
```

- [ ] **Step 7: Commit**

```bash
git add frontend/app/dashboard/chat/page.tsx frontend/lib/api.ts
git commit -m "feat: streaming chat UI with real-time token display and copy/stop controls"
```

---

## Chunk 2: Interactive Values Cards

### Task 3: Animated values cards with colour-coding and drag-and-drop reorder

**Files:**
- Modify: `frontend/app/dashboard/values/page.tsx`
- Test: `frontend/__tests__/values-interactive.test.tsx`

- [ ] **Step 1: Write failing test for colour-coded cards**

Create `frontend/__tests__/values-interactive.test.tsx`:

```typescript
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
  // Tests that reorder is called when drag ends
  render(<ValuesPage />)
  await screen.findByText('No late notifications')
  expect(api.values.reorder).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd frontend && npx jest __tests__/values-interactive.test.tsx --no-coverage
```

- [ ] **Step 3: Update values page with colour-coded cards**

Type-to-color mapping:
```typescript
const TYPE_COLORS = {
  boundary: { bg: '#0a0a0a', text: '#ffffff', badge: 'bg-black text-white' },
  preference: { bg: '#f0f7f2', text: '#0a0a0a', badge: 'bg-[#4A7C59]/10 text-[#4A7C59]' },
  topic_filter: { bg: '#fdf8ee', text: '#0a0a0a', badge: 'bg-[#9B7A3D]/10 text-[#9B7A3D]' },
  time_window: { bg: '#eef4fb', text: '#0a0a0a', badge: 'bg-[#5B7FA6]/10 text-[#5B7FA6]' },
}
```

Add `data-value-type={value.type}` to card container.

- [ ] **Step 4: Wire drag-and-drop reorder**

The `@dnd-kit/sortable` is already installed. Wire it up:

```typescript
import { DndContext, closestCenter } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

// In component:
const handleDragEnd = async (event) => {
  const { active, over } = event
  if (!over || active.id === over.id) return
  const oldIndex = values.findIndex(v => v.id === active.id)
  const newIndex = values.findIndex(v => v.id === over.id)
  const reordered = arrayMove(values, oldIndex, newIndex)
  setValues(reordered)
  await api.values.reorder(reordered.map(v => v.id))
}
```

- [ ] **Step 5: Add smooth add/delete animations**

Use CSS transition classes:
```typescript
// On add: start with opacity-0 scale-95, animate to opacity-100 scale-100
// On delete: animate to opacity-0 scale-95 then remove from state
```

- [ ] **Step 6: Responsive 1-col on mobile**

```typescript
<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
```

- [ ] **Step 7: Run all frontend tests**

```bash
cd frontend && npx jest --no-coverage
```

- [ ] **Step 8: Commit**

```bash
git add frontend/app/dashboard/values/page.tsx frontend/__tests__/values-interactive.test.tsx
git commit -m "feat: colour-coded value cards, wired drag-and-drop reorder, animated add/delete"
```

---

## Chunk 3: ESL Charts on Transparency & Dashboard

### Task 4: Install recharts and add ESL donut + line + bar charts

**Files:**
- Modify: `frontend/app/dashboard/transparency/page.tsx`
- Modify: `frontend/app/dashboard/page.tsx`
- Test: `frontend/__tests__/esl-charts.test.tsx`

- [ ] **Step 1: Install recharts**

```bash
cd frontend && npm install recharts
```

- [ ] **Step 2: Write failing tests**

Create `frontend/__tests__/esl-charts.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import TransparencyPage from '../app/dashboard/transparency/page'
import { api } from '../lib/api'

jest.mock('../lib/api', () => ({
  api: {
    transparency: {
      report: jest.fn(),
      stats: jest.fn(),
      logs: jest.fn(),
      insights: jest.fn(),
    }
  }
}))

jest.mock('recharts', () => ({
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => null,
  Cell: () => null,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
}))

beforeEach(() => {
  ;(api.transparency.report as jest.Mock).mockResolvedValue({
    total_decisions: 42, approved_count: 35, vetoed_count: 5, modified_count: 2, approval_rate: 83.3
  })
  ;(api.transparency.stats as jest.Mock).mockResolvedValue({
    decision_breakdown: { APPROVED: 35, VETOED: 5, MODIFIED: 2 },
    most_protected_values: [{ value: 'No late notifications', count: 3 }],
    most_applied_rules: []
  })
  ;(api.transparency.logs as jest.Mock).mockResolvedValue([])
  ;(api.transparency.insights as jest.Mock).mockResolvedValue([])
})

test('test_transparency_shows_pie_chart', async () => {
  render(<TransparencyPage />)
  await waitFor(() => expect(screen.getByTestId('pie-chart')).toBeInTheDocument())
})

test('test_transparency_shows_line_chart', async () => {
  render(<TransparencyPage />)
  await waitFor(() => expect(screen.getByTestId('line-chart')).toBeInTheDocument())
})

test('test_transparency_shows_bar_chart', async () => {
  render(<TransparencyPage />)
  await waitFor(() => expect(screen.getByTestId('bar-chart')).toBeInTheDocument())
})
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
cd frontend && npx jest __tests__/esl-charts.test.tsx --no-coverage
```

- [ ] **Step 4: Add charts to transparency page**

After the existing stats grid, add three chart cards:

**Donut chart (APPROVED/VETOED/MODIFIED breakdown):**
```typescript
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, BarChart, Bar } from 'recharts'

const ESL_COLORS = {
  APPROVED: '#4A7C59',
  VETOED: '#B04A3A',
  MODIFIED: '#9B7A3D',
}

// Donut chart data from report:
const donutData = [
  { name: 'Approved', value: report.approved_count, color: ESL_COLORS.APPROVED },
  { name: 'Vetoed', value: report.vetoed_count, color: ESL_COLORS.VETOED },
  { name: 'Modified', value: report.modified_count, color: ESL_COLORS.MODIFIED },
]

<ResponsiveContainer width="100%" height={200}>
  <PieChart>
    <Pie data={donutData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} dataKey="value">
      {donutData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
    </Pie>
    <Tooltip formatter={(value, name) => [value, name]} />
  </PieChart>
</ResponsiveContainer>
```

**Line chart (decisions over time from logs):**
```typescript
// Group logs by date:
const timeData = groupLogsByDay(logs, days) // returns [{date: 'Mar 20', approved: 5, vetoed: 1}]

<ResponsiveContainer width="100%" height={200}>
  <LineChart data={timeData}>
    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9e9e9e' }} />
    <YAxis tick={{ fontSize: 11, fill: '#9e9e9e' }} />
    <Tooltip />
    <Line type="monotone" dataKey="approved" stroke={ESL_COLORS.APPROVED} strokeWidth={2} dot={false} />
    <Line type="monotone" dataKey="vetoed" stroke={ESL_COLORS.VETOED} strokeWidth={2} dot={false} />
  </LineChart>
</ResponsiveContainer>
```

**Bar chart (most protected values from stats):**
```typescript
<ResponsiveContainer width="100%" height={200}>
  <BarChart data={stats.most_protected_values}>
    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
    <XAxis dataKey="value" tick={{ fontSize: 10, fill: '#9e9e9e' }} />
    <YAxis tick={{ fontSize: 11, fill: '#9e9e9e' }} />
    <Tooltip />
    <Bar dataKey="count" fill={ESL_COLORS.VETOED} radius={[4,4,0,0]} />
  </BarChart>
</ResponsiveContainer>
```

- [ ] **Step 5: Add mini approval rate sparkline to dashboard page**

In `frontend/app/dashboard/page.tsx`, after the ESL activity strip:

```typescript
// Mini donut showing today's approval rate
<div className="rounded-2xl p-4" style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.08)' }}>
  <p className="text-xs font-medium text-[#6b6b6b] mb-2">ESL Approval Rate</p>
  <div className="flex items-center gap-3">
    <ResponsiveContainer width={60} height={60}>
      <PieChart>
        <Pie data={[{value: approvalRate}, {value: 100-approvalRate}]} cx="50%" cy="50%" innerRadius={20} outerRadius={28} dataKey="value" startAngle={90} endAngle={-270}>
          <Cell fill="#4A7C59" />
          <Cell fill="#f5f5f5" />
        </Pie>
      </PieChart>
    </ResponsiveContainer>
    <span className="text-2xl font-bold text-[#0a0a0a]">{approvalRate.toFixed(0)}%</span>
  </div>
</div>
```

- [ ] **Step 6: Run all tests**

```bash
cd frontend && npx jest --no-coverage
```

- [ ] **Step 7: Commit**

```bash
git add frontend/app/dashboard/transparency/page.tsx frontend/app/dashboard/page.tsx frontend/__tests__/esl-charts.test.tsx
git commit -m "feat: add ESL donut/line/bar charts to transparency page and sparkline to dashboard"
```

---

## Chunk 4: Mobile Responsiveness

### Task 5: Mobile sidebar and responsive grid breakpoints

**Files:**
- Modify: `frontend/app/dashboard/layout.tsx`
- Modify: `frontend/components/sidebar.tsx`
- Modify: `frontend/app/dashboard/page.tsx`
- Modify: `frontend/app/dashboard/goals/page.tsx`
- Test: `frontend/__tests__/responsive.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/__tests__/responsive.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react'
import DashboardLayout from '../app/dashboard/layout'

test('test_mobile_menu_button_exists', () => {
  render(<DashboardLayout><div>content</div></DashboardLayout>)
  expect(screen.getByLabelText(/menu/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd frontend && npx jest __tests__/responsive.test.tsx --no-coverage
```

- [ ] **Step 3: Add mobile hamburger menu to layout**

In `frontend/app/dashboard/layout.tsx`:

```typescript
const [sidebarOpen, setSidebarOpen] = useState(false)

// Mobile overlay sidebar
{sidebarOpen && (
  <div className="fixed inset-0 z-50 lg:hidden">
    <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
    <div className="absolute left-0 top-0 h-full w-64 bg-white shadow-xl">
      <SidebarNav onClose={() => setSidebarOpen(false)} />
    </div>
  </div>
)}

// Hamburger button in top bar (visible on mobile only)
<button aria-label="menu" className="lg:hidden p-2" onClick={() => setSidebarOpen(true)}>
  <Menu size={20} />
</button>
```

- [ ] **Step 4: Fix dashboard stats grid responsiveness**

In `frontend/app/dashboard/page.tsx`, stats row:
```typescript
<div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
```

In transparency page stats grid:
```typescript
<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
```

- [ ] **Step 5: Touch-friendly tap targets**

Ensure all interactive elements have `min-h-[44px] min-w-[44px]` or equivalent padding. Update small icon buttons in values/goals pages.

- [ ] **Step 6: Run all tests**

```bash
cd frontend && npx jest --no-coverage
```

- [ ] **Step 7: Commit**

```bash
git add frontend/app/dashboard/layout.tsx frontend/components/sidebar.tsx frontend/app/dashboard/page.tsx frontend/app/dashboard/goals/page.tsx frontend/__tests__/responsive.test.tsx
git commit -m "feat: mobile responsive sidebar, hamburger menu, responsive grid breakpoints"
```

---

## Final Verification

- [ ] Run all frontend tests: `cd frontend && npx jest --no-coverage`
- [ ] Run all backend tests: `cd backend && source venv/bin/activate && pytest --no-header -q`
- [ ] Manual test: resize browser to 375px width — sidebar should hide, hamburger should appear
- [ ] Manual test: send a chat message — response should stream in word-by-word
- [ ] Manual test: go to Transparency page — three charts should render with real data
- [ ] Manual test: drag a value card to reorder — position should save
