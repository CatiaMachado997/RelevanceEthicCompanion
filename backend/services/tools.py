from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional

from pydantic import BaseModel, Field


class Tool(ABC):
    """
    Base abstract class for all tools available to the Orchestrator.

    Tools allow the AI to interact with the external environment or perform specific actions.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the tool. Must be unique."""

    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of what the tool does."""

    @property
    @abstractmethod
    def parameters(self) -> Type[BaseModel]:
        """
        Pydantic model defining the input parameters for the tool's execute method.
        This will be converted into a JSON schema for the LLM.
        """

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute the tool with the given parameters.

        Args:
            **kwargs: Parameters for tool execution, conforming to the `parameters` schema.

        Returns:
            A dictionary containing the result of the tool's execution.
        """


class ExampleToolParameters(BaseModel):
    """Example parameters for a generic tool."""

    query: str = Field(..., description="The query string to use for the tool.")
    limit: int = Field(5, description="The maximum number of results to return.")


class ExampleTool(Tool):
    """An example tool implementation."""

    name: str = "example_tool"
    description: str = "A generic example tool that echoes its input."
    parameters: Type[BaseModel] = ExampleToolParameters

    # Concrete tools declare their own param signature; the base class uses **kwargs
    # as a generic dispatch contract.
    async def execute(  # type: ignore[override]
        self, query: str, limit: int = 5, **kwargs: Any
    ) -> Dict[str, Any]:
        print(f"Executing ExampleTool with query: {query}, limit: {limit}")
        return {"result": f"Echoing: {query[:limit]}", "tool_name": self.name}


# ==================== Email Search Tool ====================


class EmailSearchToolParameters(BaseModel):
    """Parameters for searching emails."""

    query: str = Field(
        ..., description="The search query for emails (e.g., 'Project Phoenix')."
    )
    date_range: Optional[str] = Field(
        "last 7 days",
        description="The date range for the search (e.g., 'today', 'last 7 days', 'this month').",
    )
    sender: Optional[str] = Field(
        None, description="Filter emails by sender email address."
    )


class EmailSearchTool(Tool):
    """
    A tool to search and retrieve a summary of emails.

    This is a mock implementation.
    """

    name: str = "email_search"
    description: str = "Searches for emails based on a query and returns a summary."
    parameters: Type[BaseModel] = EmailSearchToolParameters

    async def execute(  # type: ignore[override]
        self,
        query: str,
        date_range: Optional[str] = "last 7 days",
        sender: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        print(
            f"Executing EmailSearchTool with query: '{query}', date_range: '{date_range}', sender: '{sender}'"
        )
        # Mock implementation: return hardcoded summary
        mock_summary = (
            f"Summary of emails for '{query}' from {date_range}"
            f"{f' by {sender}' if sender else ''}: "
            "Found 3 relevant emails about 'Project Phoenix'. "
            "Key points: Meeting scheduled for next Tuesday, budget review needed, "
            "and a new team member joined. Action items: Prepare budget report, "
            "update project timeline."
        )
        return {"summary": mock_summary, "email_count": 3, "tool_name": self.name}


# ==================== Calendar Query Tool ====================


class CalendarQueryToolParameters(BaseModel):
    """Parameters for querying the user's calendar."""

    time_frame: str = Field(
        "today",
        description="The time frame for the calendar query (e.g., 'today', 'tomorrow', 'next week').",
    )
    event_type: Optional[str] = Field(
        None,
        description="Filter calendar events by type (e.g., 'meeting', 'appointment').",
    )


class CalendarQueryTool(Tool):
    """
    A tool to query the user's calendar for events.

    This is a mock implementation.
    """

    name: str = "calendar_query"
    description: str = (
        "Queries the user's calendar for upcoming events within a specified time frame."
    )
    parameters: Type[BaseModel] = CalendarQueryToolParameters

    async def execute(
        self, time_frame: str = "today", event_type: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        print(
            f"Executing CalendarQueryTool for time_frame: '{time_frame}', event_type: '{event_type}'"
        )
        # Mock implementation: return hardcoded events
        mock_events = [
            {"title": "Project Stand-up", "time": "10:00 AM", "location": "Zoom"},
            {"title": "1:1 with Manager", "time": "02:00 PM", "location": "Office"},
        ]
        summary = (
            f"You have {len(mock_events)} events {time_frame}"
            f"{f' of type {event_type}' if event_type else ''}. "
            f"First event: {mock_events[0]['title']} at {mock_events[0]['time']}."
        )
        return {"summary": summary, "events": mock_events, "tool_name": self.name}
