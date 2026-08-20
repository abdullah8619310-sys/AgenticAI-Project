"""Multi-hop demonstration: one agent using file reading + web search + the
tool registry + the logging hook + session memory, chained across multiple
tool-calling iterations, to answer a single question.

This does NOT rebuild or replace any component. It exercises the real
integration:
    - src/agent.py's real loop (ResearchAgent.ask)
    - the real src/tools/registry.py (dispatch_tool_call is spied on with
      wraps=..., not replaced, so it genuinely runs)
    - the real src/plugins/file_reader.py (read_file actually reads
      data/ai_research.txt from disk)
    - the real src/hooks/tool_logger.py (both tool calls are actually
      logged to logs/tool_calls.log)
    - the real src/memory/session_memory.py (the agent's own SessionMemory
      instance is inspected afterwards)

Only two things are mocked, both required by the assignment constraints
(no real Anthropic credits, no real SerpAPI calls in this test):
    - the Claude API client (anthropic.Anthropic.messages.create)
    - src.tools.registry.search_web (the function that would otherwise
      make a real SerpAPI HTTP request)

Run the whole project's test suite with:
    venv\\Scripts\\python.exe -m pytest
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import ResearchAgent
from src.hooks.tool_logger import LOG_FILE
from src.memory.session_memory import SessionMemory
from src.tools.registry import dispatch_tool_call as real_dispatch_tool_call

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_RESEARCH_TXT = PROJECT_ROOT / "data" / "ai_research.txt"

MULTI_HOP_QUESTION = (
    "Read data/ai_research.txt, identify the main topic, research that "
    "topic using web search, and give me a combined summary."
)

# The topic Claude would identify from the file content, used as the
# (simulated) web_search query in step 3 of the scenario.
SEARCH_QUERY = "artificial intelligence applications"

FAKE_SEARCH_RESULT = {
    "success": True,
    "query": SEARCH_QUERY,
    "results": [
        {
            "title": "Applications of Artificial Intelligence",
            "link": "https://example.com/ai-applications",
            "snippet": "AI is used in healthcare, finance, transportation, and more.",
        }
    ],
    "error": None,
}

FINAL_ANSWER_TEXT = (
    "Based on the local document, Artificial Intelligence (AI) is the "
    "simulation of human intelligence by machines, covering capabilities "
    "like natural language processing and computer vision. A web search on "
    "the topic confirms real-world applications in healthcare, finance, "
    "transportation, and customer service."
)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(tool_use_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=tool_use_id, name=name, input=tool_input)


def _response(content, stop_reason):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def _fake_client():
    """Simulates Claude's side of the 5-step multi-hop scenario.

    Step 1: Claude requests read_file(data/ai_research.txt)
    Step 3: after receiving the file content, Claude requests web_search(...)
    Step 5: after receiving the search results, Claude gives a final answer
    """
    responses = [
        _response(
            [_tool_use_block("call_1", "read_file", {"path": str(AI_RESEARCH_TXT)})],
            "tool_use",
        ),
        _response(
            [_tool_use_block("call_2", "web_search", {"query": SEARCH_QUERY})],
            "tool_use",
        ),
        _response([_text_block(FINAL_ANSWER_TEXT)], "end_turn"),
    ]
    client = SimpleNamespace()
    client.messages = SimpleNamespace(create=Mock(side_effect=responses))
    return client


def _log_offset() -> int:
    return LOG_FILE.stat().st_size if LOG_FILE.exists() else 0


def _read_log_entries_since(offset: int) -> list:
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        f.seek(offset)
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture
def multi_hop_result():
    """Run the full multi-hop scenario once; every test below inspects a
    different facet of the same run (final answer, tool calls, logs,
    memory, registry dispatch)."""
    client = _fake_client()
    memory = SessionMemory()
    agent = ResearchAgent(client=client, memory=memory)

    offset_before = _log_offset()

    with patch(
        "src.agent.dispatch_tool_call", wraps=real_dispatch_tool_call
    ) as mock_dispatch, patch(
        "src.tools.registry.search_web", return_value=FAKE_SEARCH_RESULT
    ) as mock_search_web:
        answer = agent.ask(MULTI_HOP_QUESTION)

    new_log_entries = _read_log_entries_since(offset_before)

    return {
        "answer": answer,
        "client": client,
        "memory": memory,
        "mock_dispatch": mock_dispatch,
        "mock_search_web": mock_search_web,
        "log_entries": new_log_entries,
    }


def test_agent_produces_final_combined_answer(multi_hop_result):
    assert multi_hop_result["answer"] == FINAL_ANSWER_TEXT


def test_agent_did_not_stop_after_first_tool_call(multi_hop_result):
    # 3 Claude calls = read_file request -> web_search request -> final
    # answer. If the loop stopped after the first tool call, this would be 1.
    assert multi_hop_result["client"].messages.create.call_count == 3


def test_both_tools_were_actually_called(multi_hop_result):
    multi_hop_result["mock_search_web"].assert_called_once_with(query=SEARCH_QUERY)

    called_tool_names = [call.args[0] for call in multi_hop_result["mock_dispatch"].call_args_list]
    assert called_tool_names == ["read_file", "web_search"]


def test_tool_registry_dispatched_both_tools(multi_hop_result):
    # dispatch_tool_call is patched with wraps=..., i.e. it is spied on but
    # genuinely still runs — this proves the real Tool Registry handled
    # both dispatches, not a stand-in.
    mock_dispatch = multi_hop_result["mock_dispatch"]

    assert mock_dispatch.call_count == 2
    assert mock_dispatch.call_args_list[0].args == ("read_file", {"path": str(AI_RESEARCH_TXT)})
    assert mock_dispatch.call_args_list[1].args == ("web_search", {"query": SEARCH_QUERY})


def test_tool_logger_hook_logged_both_tools_with_timestamps(multi_hop_result):
    entries = multi_hop_result["log_entries"]

    read_file_entries = [e for e in entries if e["tool"] == "read_file"]
    web_search_entries = [e for e in entries if e["tool"] == "web_search"]

    assert len(read_file_entries) == 2  # one "start", one "end"
    assert len(web_search_entries) == 2

    for entry in entries:
        assert entry.get("timestamp")
        datetime.fromisoformat(entry["timestamp"])  # must be a valid ISO timestamp

    read_file_end = next(e for e in read_file_entries if e["event"] == "end")
    web_search_end = next(e for e in web_search_entries if e["event"] == "end")
    assert read_file_end["success"] is True
    assert web_search_end["success"] is True

    # The real file content really did flow through the logged result.
    assert "Artificial Intelligence" in read_file_end["result"]["content"]


def test_session_memory_contains_expected_turns(multi_hop_result):
    turns = multi_hop_result["memory"].get_turns()
    roles = [t["role"] for t in turns]

    assert roles == ["user", "tool", "tool", "assistant"]
    assert turns[0]["content"] == MULTI_HOP_QUESTION
    assert turns[-1]["content"] == FINAL_ANSWER_TEXT

    tool_turn_contents = [t["content"] for t in turns if t["role"] == "tool"]
    assert any("read_file" in content for content in tool_turn_contents)
    assert any("web_search" in content for content in tool_turn_contents)


if __name__ == "__main__":
    # Allow running this file directly too, matching the other test files'
    # convention, even though `pytest` (which understands the fixture
    # above) is the intended way to run it.
    import pytest as _pytest

    raise SystemExit(_pytest.main([__file__, "-v"]))
