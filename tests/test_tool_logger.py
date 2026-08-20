"""Tests for the tool-call logging hook.

Each test uses a unique tool name so it can find its own entries in the
shared logs/tool_calls.log file without being confused by entries from
other test runs. Run directly with:

    venv\\Scripts\\python.exe tests\\test_tool_logger.py
"""

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.hooks.tool_logger import LOG_FILE, log_tool_start, run_logged_tool_call


def _read_entries_for_tool(tool_name: str) -> list:
    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("tool") == tool_name:
                entries.append(entry)
    return entries


def _unique_tool_name(label: str) -> str:
    return f"test_tool_{label}_{uuid.uuid4().hex[:8]}"


def test_tool_call_creates_log_entry():
    tool_name = _unique_tool_name("creates_entry")

    run_logged_tool_call(tool_name, {"query": "hello"}, lambda query: f"echo:{query}")

    entries = _read_entries_for_tool(tool_name)
    assert len(entries) == 2  # one "start", one "end"


def test_timestamp_is_present():
    tool_name = _unique_tool_name("timestamp")

    log_tool_start(tool_name, {})

    entries = _read_entries_for_tool(tool_name)
    assert len(entries) == 1
    # Should be a valid ISO 8601 timestamp.
    datetime.fromisoformat(entries[0]["timestamp"])


def test_tool_name_is_recorded():
    tool_name = _unique_tool_name("name_recorded")

    run_logged_tool_call(tool_name, {}, lambda: "ok")

    entries = _read_entries_for_tool(tool_name)
    assert all(e["tool"] == tool_name for e in entries)


def test_arguments_recorded_safely():
    tool_name = _unique_tool_name("args_recorded")

    run_logged_tool_call(tool_name, {"query": "capital of France"}, lambda query: query)

    entries = _read_entries_for_tool(tool_name)
    start_entry = next(e for e in entries if e["event"] == "start")
    assert start_entry["arguments"] == {"query": "capital of France"}


def test_result_and_status_recorded():
    tool_name = _unique_tool_name("result_status")

    run_logged_tool_call(tool_name, {"n": 2}, lambda n: n * 2)

    entries = _read_entries_for_tool(tool_name)
    end_entry = next(e for e in entries if e["event"] == "end")
    assert end_entry["result"] == 4
    assert end_entry["success"] is True


def test_failures_can_be_logged():
    tool_name = _unique_tool_name("failure")

    def broken_tool():
        raise ValueError("something went wrong")

    try:
        run_logged_tool_call(tool_name, {}, broken_tool)
        raised = False
    except ValueError:
        raised = True

    assert raised, "run_logged_tool_call should re-raise the original exception"

    entries = _read_entries_for_tool(tool_name)
    end_entry = next(e for e in entries if e["event"] == "end")
    assert end_entry["success"] is False
    assert "something went wrong" in end_entry["error"]


def test_secrets_not_written_to_log():
    tool_name = _unique_tool_name("secrets")
    secret_value = "super-secret-value-should-not-appear"

    run_logged_tool_call(
        tool_name,
        {"query": "test", "api_key": secret_value, "password": secret_value},
        lambda query, api_key, password: {"api_key": api_key, "status": "done"},
    )

    entries = _read_entries_for_tool(tool_name)

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        raw_log_text = f.read()
    assert secret_value not in raw_log_text

    start_entry = next(e for e in entries if e["event"] == "start")
    assert start_entry["arguments"]["api_key"] == "***REDACTED***"
    assert start_entry["arguments"]["password"] == "***REDACTED***"
    assert start_entry["arguments"]["query"] == "test"

    end_entry = next(e for e in entries if e["event"] == "end")
    assert end_entry["result"]["api_key"] == "***REDACTED***"


if __name__ == "__main__":
    tests = [
        test_tool_call_creates_log_entry,
        test_timestamp_is_present,
        test_tool_name_is_recorded,
        test_arguments_recorded_safely,
        test_result_and_status_recorded,
        test_failures_can_be_logged,
        test_secrets_not_written_to_log,
    ]
    for test in tests:
        test()
        print(f"PASSED: {test.__name__}")
