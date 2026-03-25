# V2 Improvement Sprint — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the feedback loop, fix OAuth integrations, add semantic chat UX, and surface proactive reasoning with user-tunable relevance controls.

**Architecture:** The system is architecturally complete (M1 + M2 + ESL + Orchestrator + all API routes). This sprint focuses on hardening weak points: feedback that doesn't loop back, hardcoded relevance weights, no markdown in chat, OAuth provider quirks, and missing transparency UI for proactive suggestions.

**Tech Stack:** FastAPI (Python), Next.js 15 App Router (TypeScript), PostgreSQL (M1), Weaviate (M2), Groq/Gemini, LangChain, next-themes, react-markdown, Supabase Auth

---

## Audit Findings Summary

| Area | Status | Key Gaps |
|------|--------|----------|
| M1 (PostgreSQL) | ✅ 100% complete | None |
| M2 (Weaviate) | ✅ 100% complete | None |
| API routes (34 total) | ✅ 100% complete | None |
| Relevance scoring | ✅ Complete, ESL-integrated | Weights hardcoded, keyword-only query match |
| Orchestrator V2 | ✅ 95% complete | Streaming bypasses ESL (acknowledged), no LangChain tools |
| Feedback processor | ⚠️ 90% — stores but doesn't loop | Feedback not fed back to scoring or ESL |
| ESL engine | ✅ 100%, mandatory gateway | Regex-only patterns, no feedback learning |
| Data normalization | ⚠️ Inconsistent | Gmail + Slack stored M2-only, no M1 structure |
| OAuth: Google | ❌ "Access denied" | App in Testing mode, missing Test User setup |
| OAuth: Slack | ❌ State not returned | Backend redirects correctly; frontend detection issue |
| Chat UX | ❌ Plain text only | No markdown, no "thinking" state before first token |
| Relevance explanation | ✅ Backend generates it | Not surfaced in frontend chat UI |
| User relevance controls | ❌ Missing entirely | No settings for weight tuning |

---

## Part A — OAuth Fixes (Unblock Integrations)

### A.1 — Google OAuth: "Access Denied" Fix

**Root cause:** Google OAuth app is in "Testing" mode. Only emails explicitly added as Test Users can authorize. This is an external config issue — no code change needed.

**User action required (not code):**
1. Go to [console.cloud.google.com](https://console.cloud.google.com) → **APIs & Services → OAuth consent screen**
2. Scroll to **Test users** section → click **+ Add Users**
3. Add your Google account email
4. Save — OAuth will now work for your account

**Also check:** The app's scopes include `calendar.readonly` and `gmail.readonly` — both are sensitive scopes. Until the app is published (requires Google review), only test users can use it. For production, you'd need to submit for verification.

**No code changes needed for this fix.**

---

### A.2 — Slack OAuth: State Not Returned to App

**Root cause:** The backend correctly redirects to `{FRONTEND_URL}/dashboard/integrations?connected=slack`. The issue is most likely that `FRONTEND_URL` in `.env` is still `http://localhost:3000` but Slack's redirect goes to the backend at `localhost:8000`, and then the backend must redirect the browser back to `localhost:3000`. If the backend is not reachable from the browser context (e.g., CORS issue on the redirect), the redirect fails silently.

**Files to modify:**
- `backend/routes/data_sources.py` — add error param handling + verify redirect
- `backend/.env` — verify FRONTEND_URL value

**Step A.2.1 — Add error query param handling in OAuth callback**

**File:** `backend/routes/data_sources.py`

- [ ] Read lines 78–130 of `data_sources.py`
- [ ] Add `error: Optional[str] = None` query param to callback handler
- [ ] If `error` is present (e.g. `access_denied`), redirect to frontend with `?error={source_type}_denied`

```python
@router.get("/oauth/{source_type}/callback")
async def oauth_callback(
    source_type: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,   # ADD THIS
    db=Depends(get_db),
):
    if error:
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/dashboard/integrations?error={source_type}_{error}"
        )
    # ... existing code
```

**Step A.2.2 — Show error banner in integrations page when error param present**

**File:** `frontend/app/dashboard/integrations/page.tsx`

- [ ] Read the `useEffect` that handles `searchParams.get('connected')`
- [ ] Add parallel handling for `searchParams.get('error')`
- [ ] Show red flash banner: "Could not connect [Service]. Try again."

```typescript
const errorParam = searchParams.get('error')
if (errorParam) {
  setErrorFlash(errorParam)  // show for 4 seconds
}
```

**Step A.2.3 — Verify FRONTEND_URL in .env**

- [ ] Open `backend/.env` and confirm: `FRONTEND_URL=http://localhost:3000`
- [ ] Open browser DevTools → Network tab → click Connect on Slack → watch the redirect chain
- [ ] If the final redirect to `localhost:3000` fails, check that `npm run dev` is running

---

## Part B — Chat UX: Markdown + Loading States

### B.1 — Add Markdown Rendering to Chat

**Problem:** Assistant messages are rendered as plain text. `**bold**`, code blocks, bullet lists from the LLM all display as raw syntax.

**Files to modify:**
- `frontend/app/dashboard/chat/page.tsx`
- `frontend/package.json` (add react-markdown)

**Step B.1.1 — Install react-markdown**

- [ ] Run: `cd frontend && npm install react-markdown`
- [ ] Verify it appears in `package.json` dependencies

**Step B.1.2 — Import and use in chat message rendering**

**File:** `frontend/app/dashboard/chat/page.tsx`

- [ ] Add import: `import ReactMarkdown from 'react-markdown'`
- [ ] Find the assistant message content div (currently renders `{msg.content}` as plain text)
- [ ] Replace with `<ReactMarkdown>` only for assistant messages:

```tsx
{msg.role === 'assistant' ? (
  <ReactMarkdown
    components={{
      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
      code: ({ children, className }) => {
        const isBlock = className?.includes('language-')
        return isBlock ? (
          <pre className="my-2 overflow-x-auto rounded-lg p-3 text-xs"
            style={{ background: 'var(--ec-surface)', color: 'var(--ec-text)' }}>
            <code>{children}</code>
          </pre>
        ) : (
          <code className="rounded px-1 py-0.5 text-xs font-mono"
            style={{ background: 'var(--ec-surface)', color: 'var(--ec-text)' }}>
            {children}
          </code>
        )
      },
      ul: ({ children }) => <ul className="ml-4 list-disc space-y-1 my-2">{children}</ul>,
      ol: ({ children }) => <ol className="ml-4 list-decimal space-y-1 my-2">{children}</ol>,
      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
    }}
  >
    {msg.content}
  </ReactMarkdown>
) : (
  <span>{msg.content}</span>
)}
```

- [ ] Run `npm run build` — confirm no TypeScript errors
- [ ] Test: send a message asking for a bullet list → verify markdown renders

---

### B.2 — "Thinking" Loading State Before First Token

**Problem:** When a message is sent, an empty assistant bubble appears immediately. There's no indication the LLM is working before the first token arrives. Users see a blank bubble and a pulsing cursor — confusing.

**Files to modify:**
- `frontend/app/dashboard/chat/page.tsx`

**Step B.2.1 — Add `thinking` phase to Message interface**

- [ ] Add `thinking?: boolean` to the `Message` interface alongside `streaming`
- [ ] When a new assistant message is created (before streaming starts), set `thinking: true, streaming: false`
- [ ] When first token arrives, flip to `thinking: false, streaming: true`

```typescript
// In sendMessage(), before streaming starts:
const pendingMsg: Message = {
  id: tempId,
  role: 'assistant',
  content: '',
  timestamp: new Date().toISOString(),
  thinking: true,   // new
  streaming: false,
}

// In onToken callback, on first token:
setMessages(prev => prev.map(m =>
  m.id === tempId
    ? { ...m, thinking: false, streaming: true, content: m.content + token }
    : m
))
```

**Step B.2.2 — Render "Thinking…" UI in place of empty bubble**

- [ ] Find the assistant message bubble render
- [ ] When `msg.thinking`, show 3 animated dots instead of content:

```tsx
{msg.thinking ? (
  <div className="flex items-center gap-1 py-1">
    {[0, 1, 2].map(i => (
      <span
        key={i}
        className="w-1.5 h-1.5 rounded-full animate-bounce"
        style={{
          background: 'var(--ec-text-subtle)',
          animationDelay: `${i * 150}ms`,
        }}
      />
    ))}
  </div>
) : /* existing content render */}
```

- [ ] Test: send a message, confirm dots appear before text begins streaming

---

## Part C — Feedback Loop Closure

**Problem:** `FeedbackProcessor` stores feedback (thumbs up/down) but never uses it to adjust relevance scoring or ESL rules. The feedback is an orphan — collected but ignored.

### C.1 — Feedback → Relevance Score Adjustment

**Architecture:** When a user gives thumbs_down on a response, the relevance scorer should penalize similar content in future. When thumbs_up, boost. Use a simple user-specific multiplier stored in PostgreSQL.

**Files to modify:**
- `backend/services/feedback_processor.py` — add `apply_feedback_to_scorer()` method
- `backend/services/relevance_scoring.py` — read feedback multipliers
- `backend/database/schema.sql` — add `relevance_adjustments` table
- `backend/routes/feedback.py` — trigger adjustment on submit

**Step C.1.1 — Add relevance_adjustments table**

**File:** `backend/database/schema.sql` (also apply to schema_local.sql)

- [ ] Add table:

```sql
CREATE TABLE IF NOT EXISTS relevance_adjustments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  signal_type TEXT NOT NULL,  -- 'goal_alignment', 'timeliness', 'recency', 'query_match'
  multiplier FLOAT NOT NULL DEFAULT 1.0,  -- 1.0 = neutral, >1 = boost, <1 = reduce
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, signal_type)
);
```

- [ ] Run migration in local database: `psql -U postgres -d ethic-companion < backend/database/schema.sql`

**Step C.1.2 — Add `get_user_adjustments()` to FeedbackProcessor**

**File:** `backend/services/feedback_processor.py`

```python
async def get_user_adjustments(self, user_id: str) -> Dict[str, float]:
    """Get user-specific relevance multipliers from feedback history."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT signal_type, multiplier FROM relevance_adjustments WHERE user_id = %s",
                (user_id,)
            )
            rows = cur.fetchall()
    return {row[0]: row[1] for row in rows} if rows else {}

async def adjust_signal_from_feedback(
    self,
    user_id: str,
    feedback_type: str,  # 'thumbs_up' or 'thumbs_down'
    item_type: str,
):
    """Nudge relevance weights based on feedback pattern."""
    # Only adjust on repeated feedback (3+ same-direction signals on same item_type)
    analytics = await self.get_feedback_analytics(user_id, days=30)
    satisfaction = analytics.get("satisfaction_rate", 50)

    # If satisfaction < 40%, boost goal_alignment (signals user wants more focused responses)
    # If satisfaction > 80%, it's working well — no change
    if satisfaction < 40 and feedback_type == 'thumbs_down':
        await self._upsert_adjustment(user_id, 'goal_alignment', 1.3)
        await self._upsert_adjustment(user_id, 'query_match', 0.8)

async def _upsert_adjustment(self, user_id: str, signal_type: str, multiplier: float):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO relevance_adjustments (user_id, signal_type, multiplier)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, signal_type)
                DO UPDATE SET multiplier = %s, updated_at = NOW()
            """, (user_id, signal_type, multiplier, multiplier))
        conn.commit()
```

**Step C.1.3 — Apply adjustments in RelevanceScoring**

**File:** `backend/services/relevance_scoring.py`

- [ ] In `score_items()` method, after computing each sub-score, multiply by user adjustment:

```python
# At top of score_items():
adjustments = await feedback_processor.get_user_adjustments(user_id)

# When building final score:
goal_score *= adjustments.get('goal_alignment', 1.0)
timeliness_score *= adjustments.get('timeliness', 1.0)
recency_score *= adjustments.get('recency', 1.0)
query_score *= adjustments.get('query_match', 1.0)
```

- [ ] Pass `feedback_processor` as dependency or instantiate in `score_items()`
- [ ] Run backend: confirm no import errors

---

### C.2 — User-Tunable Relevance Weights in Settings

**Problem:** Relevance weights (50% query match, 30% goal alignment, 15% timeliness, 5% recency) are hardcoded. The spec explicitly requires user controls to adjust these.

**Architecture:** Add four float fields to the `user_settings` table. Expose them in the settings API. Surface sliders in the settings page.

**Files to modify:**
- `backend/database/schema.sql` — add columns to `user_settings`
- `backend/routes/settings.py` — expose new fields
- `backend/models/settings.py` (or wherever UserSettings is defined) — add fields
- `backend/services/relevance_scoring.py` — read user weights
- `frontend/app/dashboard/settings/page.tsx` — add relevance weight sliders

**Step C.2.1 — Add weight columns to user_settings table**

```sql
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_goal_alignment FLOAT DEFAULT 1.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_timeliness FLOAT DEFAULT 1.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_query_match FLOAT DEFAULT 1.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_recency FLOAT DEFAULT 1.0;
```

- [ ] Apply migration to local DB

**Step C.2.2 — Add fields to UserSettings model and settings route**

**File:** `backend/routes/settings.py` (check exact model location first)

```python
class UserSettings(BaseModel):
    # ... existing fields ...
    weight_goal_alignment: float = Field(1.0, ge=0.0, le=3.0)
    weight_timeliness: float = Field(1.0, ge=0.0, le=3.0)
    weight_query_match: float = Field(1.0, ge=0.0, le=3.0)
    weight_recency: float = Field(1.0, ge=0.0, le=3.0)
```

**Step C.2.3 — Read user weights in RelevanceScoring**

**File:** `backend/services/relevance_scoring.py`

- [ ] In `score_items()`, fetch user settings before scoring
- [ ] Multiply each sub-score by the user's weight factor:

```python
settings = await settings_service.get_user_settings(user_id)
w_goal = settings.weight_goal_alignment
w_time = settings.weight_timeliness
w_query = settings.weight_query_match
w_recency = settings.weight_recency

total = (
    query_score * w_query +
    goal_score * w_goal +
    timeliness_score * w_time +
    recency_score * w_recency
    - untrusted_penalty
)
```

**Step C.2.4 — Add relevance weight sliders to settings page**

**File:** `frontend/app/dashboard/settings/page.tsx`

- [ ] Add a new card "Relevance Tuning" with 4 sliders:
  - Goal Alignment weight (label: "Prioritize Goal Alignment")
  - Timeliness weight (label: "Reduce/Increase Urgency")
  - Query Match weight (label: "Prioritize What I Ask")
  - Recency weight (label: "Prioritize Recent Context")
- [ ] Each slider range: 0.0 (off) → 2.0 (double weight), step 0.1
- [ ] Show current value next to each slider
- [ ] Wire to `settingsApi.update()` on Save

```tsx
function WeightSlider({
  label, description, value, onChange
}: { label: string; description: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span style={{ color: 'var(--ec-text)' }}>{label}</span>
        <span style={{ color: 'var(--ec-text-subtle)' }}>{value.toFixed(1)}x</span>
      </div>
      <p className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>{description}</p>
      <input
        type="range" min={0} max={2} step={0.1}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full accent-black"
      />
    </div>
  )
}
```

- [ ] Update `frontend/lib/api.ts` → `UserSettings` interface to include the 4 weight fields

---

## Part D — Proactive Explanation UI ("Why Am I Seeing This?")

**Problem:** The backend generates rich `explanation` and `score_breakdown` fields in `ScoredItem`. These are never surfaced in the frontend. Users don't know why content is being shown.

**What to build:**
- Info icon (ⓘ) on dashboard proactive/upcoming cards
- Tooltip or expandable panel showing the explanation
- Example: _"Showing this because your 'Project Phoenix Sync' meeting is in 15 minutes, and this relates to your active goal 'Finalize Phoenix Proposal'."_

**Files to modify:**
- `backend/routes/data_sources.py` — include `explanation` in upcoming events response
- `frontend/app/dashboard/page.tsx` — add info icon + tooltip to Upcoming card
- `frontend/lib/api.ts` — add `explanation` field to CalendarEvent interface

### D.1 — Surface Explanation in Upcoming Events API

**File:** `backend/routes/data_sources.py`

- [ ] In `GET /api/data-sources/events/upcoming`, after fetching events, run them through `relevance_scoring.score_items()` to get explanations
- [ ] Include `explanation` field in response:

```python
# In upcoming events route:
scored = await relevance_scorer.score_items(
    candidates=[CandidateItem(id=e.id, title=e.title, content=e.description or '', ...) for e in events],
    context=await context_manager.get_current_context(user_id),
    user_id=user_id,
)
scored_by_id = {s.id: s for s in scored}

return [
    {
        "id": e.id,
        "title": e.title,
        "start_time": e.start_time.isoformat(),
        "end_time": e.end_time.isoformat(),
        "explanation": scored_by_id.get(e.id, {}).explanation if e.id in scored_by_id else None,
    }
    for e in events
]
```

### D.2 — Add Explanation Tooltip to Dashboard Upcoming Card

**File:** `frontend/app/dashboard/page.tsx`

- [ ] Add `explanation?: string` to `CalendarEvent` interface in `frontend/lib/api.ts`
- [ ] In the Upcoming card, add an ⓘ icon next to each event title
- [ ] On hover/click, show the explanation text as a tooltip:

```tsx
{event.explanation && (
  <div className="group relative">
    <button
      className="ml-1 text-[#9e9e9e] hover:text-[#6b6b6b] transition-colors"
      aria-label="Why is this shown?"
    >
      <Info size={12} />
    </button>
    <div className="absolute left-0 bottom-full mb-1 z-10 hidden group-hover:block
      w-64 p-3 rounded-xl text-xs shadow-lg border"
      style={{
        background: 'var(--ec-card-bg)',
        border: '1px solid var(--ec-card-border)',
        color: 'var(--ec-text-muted)',
      }}
    >
      {event.explanation}
    </div>
  </div>
)}
```

### D.3 — Add ESL Reason Tooltip to Chat Messages

**File:** `frontend/app/dashboard/chat/page.tsx`

- [ ] The `esl_decision` already includes `reason` field
- [ ] Currently the `ESLTag` component shows the badge — expand it to show the full reason on hover/click
- [ ] Add "Why was this modified/vetoed?" expandable section below the message

---

## Part E — ESL Ethical Monitoring Improvements

**Current weaknesses:**
1. Manipulation detection uses simple regex patterns only
2. Rules are static — never update from user feedback
3. Focus mode is binary (on/off) with no urgency levels

### E.1 — Feedback → ESL Rules Update

**Files to modify:**
- `backend/services/feedback_processor.py` — detect value conflicts from feedback
- `backend/esl/engine.py` — method to update user value weights

**Step E.1.1 — Detect value conflict feedback patterns**

When a user marks feedback as `value_conflict`, the feedback processor should signal the ESL to increase sensitivity for that category of content.

```python
# In feedback_processor.submit_feedback():
if feedback_type == FeedbackType.value_conflict:
    # Increase ESL confidence threshold for this user
    await esl_engine.note_user_sensitivity(user_id, item_type=item_type, increment=0.1)
```

**Step E.1.2 — Add `user_esl_sensitivity` table**

```sql
CREATE TABLE IF NOT EXISTS user_esl_sensitivity (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_category TEXT NOT NULL,
  sensitivity_boost FLOAT DEFAULT 0.0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, content_category)
);
```

**Step E.1.3 — Apply sensitivity boost in ESL engine**

**File:** `backend/esl/engine.py`

- [ ] In `evaluate_action()`, before final decision, check user sensitivity:

```python
sensitivity = await self._get_user_sensitivity(user_id, action.content_type)
if sensitivity > 0.3 and confidence < 0.7:
    # User has flagged this content type multiple times — be more cautious
    decision.status = 'MODIFIED'
    decision.reason = f"Applying extra caution based on your previous feedback"
```

### E.2 — Semantic Manipulation Detection (Improvement)

**Current:** ManipulationDetector uses regex keyword lists.
**Improvement:** Add a secondary check using the LLM itself to evaluate if a response has manipulative framing.

**Files to modify:**
- `backend/esl/rules.py` — add `semantic_manipulation_check()` async method
- `backend/esl/engine.py` — call semantic check for high-stakes actions

```python
async def semantic_manipulation_check(self, content: str, llm) -> bool:
    """Ask the LLM to evaluate if content is manipulative."""
    prompt = f"""Evaluate if this content uses psychological manipulation (FOMO, guilt, false urgency, social pressure):

Content: "{content[:500]}"

Answer only: YES or NO"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return "YES" in response.content.upper()
```

- [ ] Only call for content longer than 100 chars (too expensive for every token)
- [ ] Cache result per content hash to avoid repeated calls

---

## Part F — Data Normalization Improvements

**Problem:** Gmail and Slack messages are stored only in M2 (Weaviate). This means you can't do structured queries like "show me all Gmail messages from last week" — you can only semantic search.

### F.1 — Add Gmail Messages M1 Table

**Files to modify:**
- `backend/database/schema.sql`
- `backend/services/data_ingestion.py` — save to M1 as well as M2
- `backend/routes/data_sources.py` — add `GET /api/data-sources/messages/gmail` endpoint

```sql
CREATE TABLE IF NOT EXISTS email_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source TEXT NOT NULL DEFAULT 'gmail',
  external_id TEXT NOT NULL,  -- Gmail message ID
  subject TEXT,
  sender TEXT,
  snippet TEXT,
  received_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_email_messages_user_received ON email_messages(user_id, received_at DESC);
```

### F.2 — Add Slack Messages M1 Table

```sql
CREATE TABLE IF NOT EXISTS slack_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  sender_id TEXT,
  text TEXT,
  ts TEXT NOT NULL,  -- Slack timestamp (unique per channel)
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, channel, ts)
);
CREATE INDEX IF NOT EXISTS idx_slack_messages_user_created ON slack_messages(user_id, created_at DESC);
```

---

## Implementation Order

| Priority | Part | Why | Est. Effort |
|---|---|---|---|
| 🔴 Immediate | A.1 (Google test user) | Blocking — external config | 5 min (manual) |
| 🔴 Immediate | A.2 (Slack error handling) | Blocking — user can't see errors | 1h |
| 🟠 High | B.1 (Markdown in chat) | Very visible UX gap | 45 min |
| 🟠 High | B.2 (Thinking state) | Perceived performance | 30 min |
| 🟡 Medium | C.2 (User relevance weights) | Key spec requirement | 2h |
| 🟡 Medium | D.2 + D.3 (Explanation UI) | Key spec requirement | 2h |
| 🟡 Medium | C.1 (Feedback loop) | Architecture completeness | 2h |
| 🟢 Lower | E.1 (Feedback→ESL) | Nice to have for v1 | 2h |
| 🟢 Lower | E.2 (Semantic manipulation) | Enhancement | 1.5h |
| 🟢 Lower | F.1 + F.2 (M1 for Gmail/Slack) | Data completeness | 2h |

---

## Verification Checklist

### OAuth
- [ ] Google: Click "Connect Calendar" → Google consent screen appears → Authorize → `/dashboard/integrations?connected=google_calendar` → "Connected" badge shown
- [ ] Google Gmail: Same flow → `?connected=gmail`
- [ ] Slack: Click "Connect Slack" → Slack auth page → Authorize → `?connected=slack` → badge shown
- [ ] Test denial: Click Connect → deny on Google → returns to `/dashboard/integrations?error=google_calendar_access_denied` → red banner shown

### Chat UX
- [ ] Send message → 3 bouncing dots appear → first token arrives → dots replace with streaming text
- [ ] Ask LLM for a bulleted list → rendered as `<ul><li>` items, not `- item` text
- [ ] Ask for code example → rendered in code block with monospace font
- [ ] Bold text renders as `<strong>`, not `**text**`

### Relevance Weights
- [ ] Open Settings → "Relevance Tuning" card visible with 4 sliders
- [ ] Set Goal Alignment to 2.0x → Save → upcoming events/proactive content should be more goal-oriented
- [ ] Weights persist on page reload

### Explanation UI
- [ ] Dashboard Upcoming card: hover ⓘ icon → tooltip shows explanation string
- [ ] Chat message with MODIFIED ESL decision: click/hover badge → full reason visible
- [ ] Explanation example: "Showing because your 'Team Sync' meeting starts in 20 minutes"

### Feedback Loop
- [ ] Give 3 thumbs_down on assistant messages → check `relevance_adjustments` table → `goal_alignment` multiplier should be > 1.0
- [ ] Backend log: `[FeedbackProcessor] Adjusted goal_alignment to 1.3 for user X`

---

## Files Map

| File | Change |
|---|---|
| `backend/routes/data_sources.py` | Add `error` param to OAuth callback; add explanation to upcoming events |
| `backend/database/schema.sql` | Add `relevance_adjustments`, `user_esl_sensitivity`, `email_messages`, `slack_messages` tables |
| `backend/database/schema_local.sql` | Same additions |
| `backend/services/feedback_processor.py` | Add `get_user_adjustments()`, `adjust_signal_from_feedback()`, `_upsert_adjustment()` |
| `backend/services/relevance_scoring.py` | Read user adjustments + user weight settings in `score_items()` |
| `backend/routes/settings.py` | Add 4 weight fields to UserSettings model and DB read/write |
| `backend/esl/rules.py` | Add `semantic_manipulation_check()` async method |
| `backend/esl/engine.py` | Add `note_user_sensitivity()`, apply sensitivity boost |
| `frontend/lib/api.ts` | Add `explanation` to CalendarEvent; add weight fields to UserSettings |
| `frontend/app/dashboard/page.tsx` | Add ⓘ tooltip with explanation on Upcoming card |
| `frontend/app/dashboard/chat/page.tsx` | Add `thinking` state + dots; add react-markdown rendering |
| `frontend/app/dashboard/settings/page.tsx` | Add "Relevance Tuning" card with 4 weight sliders |
| `frontend/app/dashboard/integrations/page.tsx` | Handle `error` query param; show error flash banner |
