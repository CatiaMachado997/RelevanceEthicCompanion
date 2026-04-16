"""
Temporary stub for LLMService to support legacy relevance_engine.py
This will be replaced when relevance.py is updated to use relevance_scoring.py
"""


class LLMService:
    """Minimal stub for backward compatibility"""

    async def summarize_event(
        self, title: str, description: str, context: dict = None
    ) -> str:
        """Generate a simple event summary"""
        return f"Event: {title}. {description if description else 'No additional details.'}"
