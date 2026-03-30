"""ResponseFormatter and ExplainVeto — produce final SSE event list."""
from orchestrator.state import AgentState
from esl.models import ESLDecisionStatus


async def response_formatter_node(state: AgentState) -> dict:
    """Build SSE event list from approved/modified response."""
    decision = state.get("esl_decision")
    text = state.get("proposed_content", "")

    # If MODIFIED, use the modified action content if available
    if decision and decision.status == ESLDecisionStatus.MODIFIED:
        if decision.modified_action and decision.modified_action.content:
            text = decision.modified_action.content

    events = []
    # Emit tokens (chunk into ~20-char pieces for streaming feel)
    chunk_size = 20
    for i in range(0, len(text), chunk_size):
        events.append({"event": "token", "token": text[i:i+chunk_size]})

    # Attach ESL decision metadata to done event
    esl_data = {}
    if decision:
        esl_data = {
            "status": decision.status.value,
            "reason": decision.reason,
            "violated_values": decision.violated_values,
        }
    events.append({"event": "done", "esl_decision": esl_data})

    return {"response_text": text, "response_events": events}


async def explain_veto_node(state: AgentState) -> dict:
    """Build a user-friendly veto explanation as SSE events."""
    decision = state.get("esl_decision")
    reason = decision.reason if decision else "Action blocked by ESL."
    text = f"I can't respond to that right now. {reason}"
    events = [
        {"event": "token", "token": text},
        {"event": "done", "esl_decision": {"status": "VETOED", "reason": reason}},
    ]
    return {"response_text": text, "response_events": events}
