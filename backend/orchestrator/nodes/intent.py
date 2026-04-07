"""IntentClassifier — routes message to the correct processing path."""
import re
from orchestrator.state import AgentState

_COMMAND_MAP = {
    "/search": "search",
    "/plan": "plan",
    "/organize": "organize",
    "/breakdown": "breakdown",
    "/research": "research_deep",
}

_RESEARCH_KEYWORDS = re.compile(
    r"\b(research|investigate|find out|deep dive|comprehensive|analyze)\b", re.IGNORECASE
)


async def intent_classifier_node(state: AgentState) -> dict:
    """Classify message intent. Returns updated intent field."""
    msg = state["message"].strip()

    for cmd, intent in _COMMAND_MAP.items():
        if msg.lower().startswith(cmd):
            return {"intent": intent}

    if _RESEARCH_KEYWORDS.search(msg):
        return {"intent": "research_quick"}

    return {"intent": "chat"}
