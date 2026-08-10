-- Capture optional user corrections so negative feedback can become regression cases.
ALTER TABLE public.relevance_feedback
    ADD COLUMN IF NOT EXISTS corrected_answer TEXT;

-- Older local schemas predate chatbot feedback. Keep legacy values readable
-- while allowing the API's current enum values.
ALTER TABLE public.relevance_feedback
    DROP CONSTRAINT IF EXISTS relevance_feedback_item_type_check;
ALTER TABLE public.relevance_feedback
    ADD CONSTRAINT relevance_feedback_item_type_check CHECK (
        item_type IN (
            'chat_response', 'search_result', 'calendar_event',
            'proactive_insight', 'memory_recall',
            'memory', 'summary', 'proactive_suggestion'
        )
    );

ALTER TABLE public.relevance_feedback
    DROP CONSTRAINT IF EXISTS relevance_feedback_feedback_type_check;
ALTER TABLE public.relevance_feedback
    ADD CONSTRAINT relevance_feedback_feedback_type_check CHECK (
        feedback_type IN (
            'thumbs_up', 'thumbs_down', 'not_relevant', 'value_conflict',
            'inaccurate', 'dismiss', 'engage'
        )
    );

CREATE INDEX IF NOT EXISTS idx_relevance_feedback_chat_negative
    ON public.relevance_feedback (timestamp DESC)
    WHERE item_type = 'chat_response'
      AND feedback_type IN ('thumbs_down', 'not_relevant', 'value_conflict', 'inaccurate');
