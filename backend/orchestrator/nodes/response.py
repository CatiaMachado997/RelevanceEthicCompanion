"""ResponseFormatter and ExplainVeto — produce SSE metadata for done event."""

from orchestrator.state import AgentState
from esl.models import ESLDecisionStatus


async def response_formatter_node(state: AgentState) -> dict:
    """
    Post-ESL formatter: handles MODIFIED case; produces done-event metadata.

    With astream_events() streaming, tokens have already been yielded by
    stream_langgraph() as on_chat_model_stream events. This node computes
    the final ESL metadata for the done event and handles the MODIFIED case.
    """
    decision = state.get("esl_decision")
    text = state.get("proposed_content", "")

    # If MODIFIED, use the modified action content if available
    if decision and decision.status == ESLDecisionStatus.MODIFIED:
        if decision.modified_action and decision.modified_action.content:
            text = decision.modified_action.content

    esl_data = {}
    if decision:
        esl_data = {
            "status": decision.status.value,
            "reason": decision.reason,
            "violated_values": getattr(decision, "violated_values", []),
        }

    # response_events only carries the done event metadata now;
    # actual tokens already streamed via astream_events.
    return {
        "response_text": text,
        "response_events": [{"event": "done", "esl_decision": esl_data}],
    }


async def explain_veto_node(state: AgentState) -> dict:
    """Build a user-friendly veto explanation."""
    decision = state.get("esl_decision")
    reason = decision.reason if decision else "Action blocked by ESL."
    text = f"I can't respond to that right now. {reason}"
    return {
        "response_text": text,
        "response_events": [
            {"event": "token", "token": text},
            {"event": "done", "esl_decision": {"status": "VETOED", "reason": reason}},
        ],
    }
