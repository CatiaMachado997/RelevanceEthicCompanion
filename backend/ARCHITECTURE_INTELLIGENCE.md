# Where the Intelligence Lives: Architecture Deep Dive

## The Fundamental Principle

**Base models (Groq/Llama, Gemini, OpenAI) are stateless text-generation tools.**

They have:
- ❌ NO memory of past conversations
- ❌ NO understanding of your users
- ❌ NO access to your data
- ❌ NO ethical guardrails beyond basic safety
- ✅ ONLY: Text in → Text out (or Text in → Vector out for embeddings)

**100% of the system intelligence is in YOUR custom code.**

---

## Intelligence Breakdown by Component

### 1. Data Ingestion (100% YOURS)

**What Base Models Do**: Nothing. They don't ingest data.

**What YOUR CODE Does**:
```python
# backend/services/data_ingestion.py
class DataIngestionService:
    async def initiate_oauth(user_id, source_type):
        # YOUR CODE: Handle OAuth flow
        # YOUR CODE: Exchange auth code for tokens
        # YOUR CODE: Store encrypted tokens in PostgreSQL
        pass

    async def poll_source(user_id, source_type):
        # YOUR CODE: Fetch new data from Google Calendar
        # YOUR CODE: Normalize to internal Event model
        # YOUR CODE: Redact PII BEFORE storing
        # YOUR CODE: Store in M1 (PostgreSQL) + M2 (Weaviate)
        pass
```

**Intelligence**:
- When to poll (YOUR scheduling logic)
- How to normalize heterogeneous data (YOUR data models)
- What to redact (YOUR PII detection rules)
- Where to store (YOUR architecture decision)

---

### 2. Hybrid Memory System (100% YOURS)

**What Base Models Do**: Nothing. They don't maintain memory.

**What YOUR CODE Does**:
```python
# backend/services/context_manager.py
class ContextManager:
    async def get_current_context(user_id):
        # YOUR CODE: Query PostgreSQL for goals
        goals = await db.query("SELECT * FROM goals WHERE user_id=?")

        # YOUR CODE: Query PostgreSQL for events
        events = await db.query("SELECT * FROM events WHERE user_id=?")

        # YOUR CODE: Query Weaviate for semantic memory
        memories = await weaviate.hybrid_search(query, user_id)

        # YOUR CODE: Combine M1 + M2 into CurrentContext
        return CurrentContext(goals=goals, events=events, memories=memories)
```

**Intelligence**:
- What to retrieve (YOUR query logic)
- How much to retrieve (YOUR context windowing)
- How to combine SQL + vector search (YOUR hybrid logic)
- When to invalidate cache (YOUR cache strategy)

---

### 3. Relevance Scoring (100% YOURS)

**What Base Models Do**: Nothing. They don't score relevance.

**What YOUR CODE Does**:
```python
# backend/services/relevance_scoring.py
class RelevanceScoringEngine:
    def _calculate_relevance_score(candidate, context):
        score = 0

        # YOUR ALGORITHM: Query matching
        if context.query in candidate.content:
            score += 50

        # YOUR ALGORITHM: Goal alignment
        for goal in context.active_goals:
            if goal in candidate.content:
                score += 30

        # YOUR ALGORITHM: Temporal relevance
        for event in context.upcoming_events:
            if event.title in candidate.content:
                hours_until = (event.start - now).hours
                if hours_until < 1:
                    score += 15

        # YOUR ALGORITHM: Recency
        for topic in context.recent_topics:
            if topic in candidate.content:
                score += 5

        return score
```

**Intelligence**:
- Scoring factors (YOUR algorithm design)
- Factor weights (YOUR ML/heuristic tuning)
- Temporal logic (YOUR timeliness calculation)
- Source credibility (YOUR blocklists)

---

### 4. Ethical Guardrails (100% YOURS)

**What Base Models Do**: Basic safety filtering (no hate speech, no violence, etc.)

**What YOUR CODE Does**:
```python
# backend/esl/engine.py
class EthicalSafeguardLayer:
    async def check_content_safety(content, user_id):
        # YOUR CODE: Get user's specific values
        values = await db.get_user_values(user_id)

        # YOUR RULES: Topic filtering
        for value in values:
            if value.type == "topic_filter":
                if value.value in content:
                    return ContentSafetyCheck(blocked=True)

        # YOUR RULES: Manipulation detection
        if re.search(r"don't miss out|act now", content):
            return ContentSafetyCheck(blocked=True)

        return ContentSafetyCheck(blocked=False)
```

**Intelligence**:
- User-specific value enforcement (YOUR ESL logic)
- Manipulation detection patterns (YOUR heuristics)
- When to block vs. modify (YOUR decision rules)
- Transparency logging (YOUR audit system)

---

### 5. Prompt Engineering Pipeline (80% YOURS)

**What Base Models Do**: Generate text based on prompt (10% of intelligence)

**What YOUR CODE Does**:
```python
# backend/services/orchestrator.py
class Orchestrator:
    async def handle_query(user_id, query):
        # YOUR CODE: Parse query intent
        intent = parse_intent(query)

        # YOUR CODE: Retrieve context from M1 + M2
        context = await context_manager.get_current_context(user_id)

        # YOUR CODE: Get user values
        values = await context_manager.get_user_values(user_id)

        # YOUR CODE: Build context-rich prompt
        prompt = f"""
        You are helping {context.user_name}.

        User Values: {', '.join([v.value for v in values])}
        Active Goals: {', '.join([g.title for g in context.goals])}
        Upcoming Events: {', '.join([e.title for e in context.events])}

        Recent Context: {context.recent_memory}

        User Query: {query}

        Provide a helpful response that respects user values.
        """

        # EXTERNAL CALL: Groq generates text (10% of intelligence)
        response = await groq.generate(prompt)

        # YOUR CODE: Validate output
        if contains_pii(response):
            response = redact_pii(response)

        # YOUR CODE: Check manipulation
        if contains_manipulation(response):
            response = None  # Block it

        return response
```

**Intelligence**:
- Intent parsing (YOUR NLP logic)
- Context retrieval (YOUR query decisions)
- Prompt construction (YOUR template engineering)
- Output validation (YOUR safety checks)

**Base Model Contribution**: 10% - Just text generation based on YOUR prompt.

---

### 6. Output Validation (100% YOURS)

**What Base Models Do**: Nothing beyond generating text.

**What YOUR CODE Does**:
```python
# backend/services/output_validator.py
class OutputValidator:
    async def validate(text, user_id):
        # YOUR CODE: PII detection
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{4}-\d{4}-\d{4}-\d{4}\b',  # Credit card
            # ... YOUR patterns
        ]
        for pattern in pii_patterns:
            if re.search(pattern, text):
                text = redact_pii(text, pattern)

        # YOUR CODE: LLM-as-a-judge
        judge_prompt = f"""
        Check if this text contains manipulation:
        {text}

        Answer: YES or NO
        """
        judgment = await groq.generate(judge_prompt)

        if "YES" in judgment:
            return ValidationResult(passed=False, reason="Manipulation detected")

        # YOUR CODE: Sentiment analysis
        if sentiment_score(text) < -0.8:
            return ValidationResult(passed=False, reason="Overly negative")

        return ValidationResult(passed=True)
```

**Intelligence**:
- PII patterns (YOUR regex/NER)
- LLM-as-a-judge prompt (YOUR validation logic)
- Sentiment thresholds (YOUR tuning)
- When to block vs. modify (YOUR decision)

---

## Real Example: "Summarize my Project Phoenix emails"

Let's trace where intelligence lives at each step:

### Step 1: Query Understanding
```python
# YOUR CODE
query = "Summarize my Project Phoenix emails"
intent = "summarize"
entity = "emails"
filter = "Project Phoenix"
```
**Intelligence**: Intent parsing, entity extraction (YOUR NLP logic)

### Step 2: Data Retrieval
```python
# YOUR CODE calls Gmail API
emails = gmail_api.search(user_id, query="Project Phoenix")
```
**Intelligence**: Which API to call, how to authenticate, what filters to use (YOUR integration)

### Step 3: Context Building
```python
# YOUR CODE queries M1 + M2
goals = await db.query("SELECT * FROM goals WHERE user_id=?")
values = await db.query("SELECT * FROM user_values WHERE user_id=?")
past_conversations = await weaviate.search("Project Phoenix", user_id)

context = CurrentContext(
    goals=goals,
    values=values,
    past_conversations=past_conversations,
    user_prefers_brevity=True  # From user values
)
```
**Intelligence**: What context to retrieve, how to combine it (YOUR logic)

### Step 4: Relevance Scoring
```python
# YOUR CODE scores emails
for email in emails:
    score = 0
    if "Project Phoenix" in email.subject:
        score += 50
    for goal in context.goals:
        if goal.title in email.body:
            score += 30
    scored_emails.append((email, score))

top_5 = sorted(scored_emails, reverse=True)[:5]
```
**Intelligence**: Scoring algorithm, ranking (YOUR code)

### Step 5: Ethical Check
```python
# YOUR CODE via ESL
for email in top_5:
    safety = await esl.check_content_safety(email.body, user_id)
    if safety.blocked:
        top_5.remove(email)
```
**Intelligence**: What to block, why (YOUR ESL rules)

### Step 6: Prompt Construction
```python
# YOUR CODE builds prompt
prompt = f"""
User prefers: brevity (from values)
Active goals: {context.goals}
Past context: {context.past_conversations}

Summarize these 5 emails about Project Phoenix:
{top_5_emails}

Keep it to 3 bullet points.
"""
```
**Intelligence**: What context to include, how to structure it (YOUR prompt engineering)

### Step 7: LLM Generation
```python
# EXTERNAL: Groq/Llama generates text
response = await groq.generate(prompt)
# ← THIS IS THE ONLY STEP USING BASE MODEL
```
**Intelligence**: 10% - Text generation based on YOUR prompt

### Step 8: Output Validation
```python
# YOUR CODE validates
if contains_pii(response):
    response = redact_pii(response)

if contains_manipulation(response):
    response = None
```
**Intelligence**: What to validate, how to redact (YOUR code)

### Step 9: Storage & Display
```python
# YOUR CODE stores interaction
await db.insert_interaction(user_id, query, response)
await weaviate.store_memory(user_id, response, embedding)
```
**Intelligence**: What to store, where, how to format (YOUR architecture)

---

## Summary: Intelligence Distribution

| Step | External Model | YOUR CODE |
|------|---------------|-----------|
| 1. Query Understanding | 0% | 100% |
| 2. Data Retrieval | 0% | 100% |
| 3. Context Building | 0% | 100% |
| 4. Relevance Scoring | 0% | 100% |
| 5. Ethical Check | 0% | 100% |
| 6. Prompt Construction | 0% | 100% |
| 7. LLM Generation | 90% | 10% |
| 8. Output Validation | 10% | 90% |
| 9. Storage & Display | 0% | 100% |
| **TOTAL** | **11%** | **89%** |

**Base model touched ONE step** (#7) and contributed ~10% overall.

---

## What Interviewers Should Hear

**Q: "Isn't this just a wrapper around Groq/Llama?"**

**A:**
"No. Groq/Llama provides text generation in step 7 of a 9-step pipeline. The intelligence is in:

1. **Data Ingestion**: OAuth integration with Google Calendar, PII redaction BEFORE storage
2. **Memory Architecture**: Hybrid PostgreSQL + Weaviate system with custom retrieval logic
3. **Relevance Scoring**: Multi-factor algorithm (query 50%, goals 30%, time 15%, recency 5%) with YOUR heuristics
4. **Ethical Guardrails**: User-specific value enforcement via ESL at multiple stages
5. **Prompt Engineering**: Context-rich pipeline that injects retrieved memory, user values, and goals
6. **Output Validation**: PII detection, LLM-as-a-judge pattern, sentiment analysis

Groq/Llama is a stateless text generator. It knows nothing about my users. The intelligence is in how I orchestrate it."

---

## Key Takeaway

**External services (Groq, OpenAI, Gemini, Firebase, Weaviate) are tools.**

**YOUR intelligence is in:**
- How you orchestrate them
- What context you inject
- How you score relevance
- What guardrails you apply
- How you validate outputs
- When you cache
- What you store where

This is a **software engineering project** with AI as ONE component, not an "AI project" with some code around it.
