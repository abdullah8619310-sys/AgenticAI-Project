"""Tests for the agent orchestration loop in src/agent.py.

These tests mock the Claude API (no real network calls to Anthropic) so
they run fast and don't need ANTHROPIC_API_KEY configured. They focus on
the orchestration logic: single-turn answers, tool-call handling, multiple
tool calls across iterations, the iteration limit, unknown-tool safety,
API-error handling, and session memory persistence.

Run directly with:
    venv\\Scripts\\python.exe tests\\test_agent.py
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import ResearchAgent
from src.memory.session_memory import SessionMemory


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(tool_use_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=tool_use_id, name=name, input=tool_input)


def _response(content, stop_reason):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def _fake_client(responses):
    """A stand-in for anthropic.Anthropic that returns `responses` in order."""
    client = SimpleNamespace()
    client.messages = SimpleNamespace(create=Mock(side_effect=responses))
    return client


def test_agent_returns_final_answer_without_tool_use():
    client = _fake_client(
        [_response([_text_block("Paris is the capital of France.")], "end_turn")]
    )
    agent = ResearchAgent(client=client)

    answer = agent.ask("What is the capital of France?")

    assert answer == "Paris is the capital of France."
    assert client.messages.create.call_count == 1


def test_agent_executes_single_tool_call_and_continues_loop():
    responses = [
        _response(
            [_tool_use_block("call_1", "web_search", {"query": "capital of France"})],
            "tool_use",
        ),
        _response([_text_block("Paris.")], "end_turn"),
    ]
    client = _fake_client(responses)
    agent = ResearchAgent(client=client)

    fake_result = {"success": True, "query": "capital of France", "results": [], "error": None}
    with patch("src.agent.dispatch_tool_call", return_value=fake_result) as mock_dispatch:
        answer = agent.ask("What is the capital of France?")

    assert answer == "Paris."
    assert client.messages.create.call_count == 2
    mock_dispatch.assert_called_once_with("web_search", {"query": "capital of France"})


def test_agent_supports_multiple_tool_calls_across_iterations():
    responses = [
        _response([_tool_use_block("call_1", "web_search", {"query": "step one"})], "tool_use"),
        _response([_tool_use_block("call_2", "web_search", {"query": "step two"})], "tool_use"),
        _response([_text_block("Final combined answer.")], "end_turn"),
    ]
    client = _fake_client(responses)
    agent = ResearchAgent(client=client)

    fake_result = {"success": True, "query": "x", "results": [], "error": None}
    with patch("src.agent.dispatch_tool_call", return_value=fake_result) as mock_dispatch:
        answer = agent.ask("A multi-hop question")

    assert answer == "Final combined answer."
    assert client.messages.create.call_count == 3
    assert mock_dispatch.call_count == 2


def test_agent_stops_at_max_iterations():
    def always_tool_use(**kwargs):
        return _response(
            [_tool_use_block("call_x", "web_search", {"query": "loop forever"})], "tool_use"
        )

    client = SimpleNamespace()
    client.messages = SimpleNamespace(create=Mock(side_effect=lambda **kwargs: always_tool_use()))
    agent = ResearchAgent(client=client, max_iterations=3)

    fake_result = {"success": True, "query": "x", "results": [], "error": None}
    with patch("src.agent.dispatch_tool_call", return_value=fake_result):
        answer = agent.ask("Never-ending question")

    assert "maximum" in answer.lower()
    assert client.messages.create.call_count == 3


def test_agent_handles_unknown_tool_without_crashing():
    responses = [
        _response(
            [_tool_use_block("call_1", "does_not_exist", {"foo": "bar"})],
            "tool_use",
        ),
        _response([_text_block("I could not use that tool, but here is my best answer.")], "end_turn"),
    ]
    client = _fake_client(responses)
    agent = ResearchAgent(client=client)

    # No mocking here: the real registry already handles unknown tools safely
    # and makes no network calls, so this exercises the real dispatch path.
    answer = agent.ask("Do something unsupported")

    assert answer == "I could not use that tool, but here is my best answer."
    assert client.messages.create.call_count == 2


def test_agent_handles_claude_api_error_gracefully():
    client = SimpleNamespace()
    client.messages = SimpleNamespace(create=Mock(side_effect=RuntimeError("connection failed")))
    agent = ResearchAgent(client=client)

    answer = agent.ask("Anything")

    assert "couldn't reach claude" in answer.lower()


def test_session_memory_persists_across_multiple_asks():
    memory = SessionMemory()
    responses = [
        _response([_text_block("Paris.")], "end_turn"),
        _response([_text_block("About 2.1 million.")], "end_turn"),
    ]
    client = _fake_client(responses)
    agent = ResearchAgent(client=client, memory=memory)

    agent.ask("What is the capital of France?")
    agent.ask("What is its population?")

    turns = memory.get_turns()
    roles = [t["role"] for t in turns]

    assert roles == ["user", "assistant", "user", "assistant"]
    assert turns[1]["content"] == "Paris."
    assert turns[3]["content"] == "About 2.1 million."


def test_session_memory_records_tool_turns():
    memory = SessionMemory()
    responses = [
        _response(
            [_tool_use_block("call_1", "web_search", {"query": "test"})],
            "tool_use",
        ),
        _response([_text_block("Done.")], "end_turn"),
    ]
    client = _fake_client(responses)
    agent = ResearchAgent(client=client, memory=memory)

    fake_result = {"success": True, "query": "test", "results": [], "error": None}
    with patch("src.agent.dispatch_tool_call", return_value=fake_result):
        agent.ask("Search for something")

    roles = [t["role"] for t in memory.get_turns()]
    assert "tool" in roles


if __name__ == "__main__":
    tests = [
        test_agent_returns_final_answer_without_tool_use,
        test_agent_executes_single_tool_call_and_continues_loop,
        test_agent_supports_multiple_tool_calls_across_iterations,
        test_agent_stops_at_max_iterations,
        test_agent_handles_unknown_tool_without_crashing,
        test_agent_handles_claude_api_error_gracefully,
        test_session_memory_persists_across_multiple_asks,
        test_session_memory_records_tool_turns,
    ]
    for test in tests:
        test()
        print(f"PASSED: {test.__name__}")
