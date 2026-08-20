"""Tool registry.

Bridges Claude's tool-calling format and our local Python capabilities:
- TOOL_DEFINITIONS: Claude-compatible tool schemas (name, description,
  input_schema) for every registered tool, ready to send to the API.
- dispatch_tool_call: looks up a tool by name and runs it with the given
  arguments, returning a safe error result instead of raising for unknown
  tools or bad arguments.

This module does not call the Claude API and is not wired into the logging
hook yet — it only provides registration and dispatch at this stage.
"""

from src.plugins.file_reader import read_file
from src.skills.web_search import search_web

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for information on a given query. Returns a "
            "list of results, each with a title, link, and snippet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query text.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read the text content of a local file. Supports .txt and .pdf "
            "files only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Filesystem path to a .txt or .pdf file.",
                }
            },
            "required": ["path"],
        },
    },
]

# Maps each tool name to a function that takes the raw arguments dict (as
# Claude would send it) and calls the real implementation.
_TOOL_IMPLEMENTATIONS = {
    "web_search": lambda arguments: search_web(query=arguments["query"]),
    "read_file": lambda arguments: read_file(path=arguments["path"]),
}


def get_tool_definitions() -> list:
    """Return the Claude-compatible tool schemas for every registered tool."""
    return list(TOOL_DEFINITIONS)


def dispatch_tool_call(tool_name: str, arguments: dict) -> dict:
    """Run the tool named `tool_name` with `arguments` and return its result.

    Never raises: unknown tool names and invalid/missing arguments are
    reported as a {"success": False, "tool": ..., "error": ...} dict
    instead of crashing the caller.
    """
    if tool_name not in _TOOL_IMPLEMENTATIONS:
        return {
            "success": False,
            "tool": tool_name,
            "error": f"Unknown tool '{tool_name}'",
        }

    if not isinstance(arguments, dict):
        return {
            "success": False,
            "tool": tool_name,
            "error": "Tool arguments must be a dict",
        }

    try:
        return _TOOL_IMPLEMENTATIONS[tool_name](arguments)
    except KeyError as exc:
        return {
            "success": False,
            "tool": tool_name,
            "error": f"Missing required argument: {exc}",
        }
    except TypeError as exc:
        return {
            "success": False,
            "tool": tool_name,
            "error": f"Invalid arguments for tool '{tool_name}': {exc}",
        }
