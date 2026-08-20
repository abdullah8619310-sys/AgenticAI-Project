"""Tests for the tool registry.

test_dispatch_web_search_tool makes a real SerpAPI call (consistent with
how the rest of this project tests its skills — no mocking), so it needs
SERPAPI_API_KEY configured in .env, same as tests/test_web_search.py.

Run directly with:
    venv\\Scripts\\python.exe tests\\test_tool_registry.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.registry import dispatch_tool_call, get_tool_definitions

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TXT = PROJECT_ROOT / "data" / "sample.txt"


def test_both_tools_are_registered():
    definitions = get_tool_definitions()
    names = {tool["name"] for tool in definitions}

    assert names == {"web_search", "read_file"}


def test_definitions_are_claude_compatible():
    for tool in get_tool_definitions():
        assert isinstance(tool["name"], str)
        assert isinstance(tool["description"], str) and tool["description"]

        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert isinstance(schema["properties"], dict)
        assert isinstance(schema["required"], list)
        for required_param in schema["required"]:
            assert required_param in schema["properties"]


def test_dispatch_web_search_tool():
    result = dispatch_tool_call("web_search", {"query": "what is artificial intelligence"})

    assert result["success"] is True, result.get("error")
    assert len(result["results"]) > 0


def test_dispatch_read_file_tool():
    result = dispatch_tool_call("read_file", {"path": str(SAMPLE_TXT)})

    assert result["success"] is True, result.get("error")
    assert "sample text file" in result["content"]


def test_unknown_tool_handled_safely():
    result = dispatch_tool_call("does_not_exist", {"foo": "bar"})

    assert result["success"] is False
    assert "unknown tool" in result["error"].lower()


def test_missing_required_argument_handled_safely():
    result = dispatch_tool_call("web_search", {})  # missing "query"

    assert result["success"] is False
    assert "missing required argument" in result["error"].lower()


def test_non_dict_arguments_handled_safely():
    result = dispatch_tool_call("read_file", "not-a-dict")

    assert result["success"] is False
    assert "must be a dict" in result["error"].lower()


if __name__ == "__main__":
    tests = [
        test_both_tools_are_registered,
        test_definitions_are_claude_compatible,
        test_dispatch_web_search_tool,
        test_dispatch_read_file_tool,
        test_unknown_tool_handled_safely,
        test_missing_required_argument_handled_safely,
        test_non_dict_arguments_handled_safely,
    ]
    for test in tests:
        test()
        print(f"PASSED: {test.__name__}")
