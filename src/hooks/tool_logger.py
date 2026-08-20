"""Tool-call logging hook.

Wraps tool dispatch so every call is recorded to logs/tool_calls.log with a
timestamp, the tool name, its arguments, its result, and a success/failure
status. Uses Python's standard `logging` module to append one JSON object
per line, which keeps entries both human-readable and easy to parse later.

This module is intentionally standalone: it does not import src.agent or
anything else. It is not wired into the agent yet — that happens when the
agent loop is implemented.
"""

import json
import logging
from datetime import datetime, timezone

from src.config import LOGS_DIR

LOG_FILE = LOGS_DIR / "tool_calls.log"

# Any argument/result key containing one of these substrings (case-insensitive)
# has its value replaced before it is ever written to the log.
_SENSITIVE_KEY_MARKERS = ("key", "token", "secret", "password")
_REDACTED = "***REDACTED***"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("agentic_ai.tool_logger")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False


def _redact(value):
    """Recursively replace values of sensitive-looking keys with a placeholder."""
    if isinstance(value, dict):
        return {
            k: _REDACTED
            if any(marker in k.lower() for marker in _SENSITIVE_KEY_MARKERS)
            else _redact(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


def _write(entry: dict) -> None:
    _logger.info(json.dumps(entry, default=str))


def log_tool_start(tool_name: str, arguments: dict) -> None:
    """Record that a tool call is about to run (the "before" half)."""
    _write(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "start",
            "tool": tool_name,
            "arguments": _redact(arguments),
        }
    )


def log_tool_end(
    tool_name: str,
    arguments: dict,
    result=None,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Record that a tool call has finished (the "after" half)."""
    _write(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "end",
            "tool": tool_name,
            "arguments": _redact(arguments),
            "result": _redact(result),
            "success": success,
            "error": error,
        }
    )


def run_logged_tool_call(tool_name: str, arguments: dict, func):
    """Run func(**arguments), logging a start entry before and an end entry after.

    On success, logs the return value and success=True, then returns it.
    On exception, logs success=False with the error message, then re-raises.
    """
    log_tool_start(tool_name, arguments)
    try:
        result = func(**arguments)
    except Exception as exc:
        log_tool_end(tool_name, arguments, result=None, success=False, error=str(exc))
        raise
    else:
        log_tool_end(tool_name, arguments, result=result, success=True)
        return result
