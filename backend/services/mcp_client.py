"""
MCP Client — connects to an MCP server and wraps discovered tools as LangChain tools.
Falls back gracefully if the server is unreachable or mcp package not installed.
"""
from __future__ import annotations

import logging
from typing import Any, ClassVar, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPClient:
    """Discover and wrap tools from an MCP server URL."""

    def __init__(self, server_url: str):
        self.server_url = server_url

    async def get_tools(self) -> list[BaseTool]:
        """
        Connect to the MCP server, list tools, and return LangChain wrappers.
        Returns [] if the server is unreachable or returns no tools.
        """
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    mcp_tools = tools_response.tools

            lc_tools = [_wrap_mcp_tool(t, server_url=self.server_url) for t in mcp_tools]
            logger.info(f"MCP: loaded {len(lc_tools)} tools from {self.server_url}")
            return lc_tools

        except ImportError:
            logger.warning("mcp package not installed — pip install mcp")
            return []
        except Exception as e:
            logger.warning(f"MCP server unreachable at {self.server_url}: {e}")
            return []


def _wrap_mcp_tool(mcp_tool: Any, server_url: str) -> BaseTool:
    """Wrap a single MCP tool as a LangChain BaseTool with a unique Pydantic class name."""
    tool_name = f"mcp__{mcp_tool.name}".replace("-", "_")
    tool_description = getattr(mcp_tool, "description", mcp_tool.name)

    # Unique class names required by Pydantic v2 registry
    safe_name = tool_name.replace("/", "_")
    InputCls = type(
        f"_MCPInput_{safe_name}",
        (BaseModel,),
        {
            "__annotations__": {"params": dict},
            "params": Field(default_factory=dict, description="Parameters for the MCP tool"),
        },
    )

    class _MCPTool(BaseTool):
        name: str = tool_name
        description: str = tool_description
        args_schema: type[BaseModel] = InputCls
        metadata: ClassVar[dict] = {
            "tool_id": "mcp_custom",
            "action_name": mcp_tool.name,
            "risk_level": "medium",
        }

        def _run(self, params: Optional[dict] = None) -> str:  # type: ignore[override]
            raise NotImplementedError("Use _arun")

        async def _arun(self, params: Optional[dict] = None) -> str:  # type: ignore[override]
            try:
                from mcp import ClientSession
                from mcp.client.sse import sse_client

                async with sse_client(server_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(mcp_tool.name, params or {})
                return str(result.content)
            except Exception as e:
                return f"MCP tool error: {e}"

    _MCPTool.__name__ = f"_MCPTool_{safe_name}"
    _MCPTool.__qualname__ = _MCPTool.__name__
    return _MCPTool()
