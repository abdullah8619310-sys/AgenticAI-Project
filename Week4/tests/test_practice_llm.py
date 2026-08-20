"""Tests for LOCAL PRACTICE MODE (src/practice_llm.py).

Two layers are tested:
  1. PracticeLLM's decision rules in isolation (unit tests) — no real tools
     involved, just checking it returns the right tool_use/text shapes.
  2. A full integration run through the real ResearchAgent, PracticeClient,
     Tool Registry, Tool Logger Hook, SessionMemory, and the real
     file-reader plugin (src.tools.registry.search_web is mocked so this
     test makes no real SerpAPI call, keeping it fast and offline — same
     approach as tests/test_multi_hop_demo.py). No Anthropic API is ever
     involved since PracticeClient never calls it.

Run directly with:
    venv\\Scripts\\python.exe -m pytest tests\\test_practice_llm.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import ResearchAgent
from src.memory.session_memory import SessionMemory
from src.practice_llm import DEFAULT_PRACTICE_FILE, PracticeClient, PracticeLLM, _text_block

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_RESEARCH_TXT = PROJECT_ROOT / "data" / "ai_research.txt"


def _user_message(text):
    return {"role": "user", "content": text}


def _assistant_tool_use_message(tool_use_id, name, tool_input):
    from src.practice_llm import _tool_use_block

    return {"role": "assistant", "content": [_tool_use_block(tool_use_id, name, tool_input)]}


def _tool_result_message(tool_use_id, result_dict):
    return {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": json.dumps(result_dict)}
        ],
    }


# --- Unit tests: PracticeLLM decision rules ---------------------------------


def test_first_step_requests_read_file_when_question_names_a_file():
    llm = PracticeLLM()
    messages = [_user_message("Read data/ai_research.txt and summarize it.")]

    response = llm.create(messages=messages)

    assert response.stop_reason == "tool_use"
    assert response.content[0].name == "read_file"
    assert response.content[0].input == {"path": "data/ai_research.txt"}


def test_first_step_defaults_file_path_when_none_given():
    llm = PracticeLLM()
    messages = [_user_message("Please read the file and tell me about it.")]

    response = llm.create(messages=messages)

    assert response.content[0].name == "read_file"
    assert response.content[0].input == {"path": DEFAULT_PRACTICE_FILE}


def test_first_step_requests_web_search_for_search_style_question():
    llm = PracticeLLM()
    messages = [_user_message("Search the web for the latest AI news.")]

    response = llm.create(messages=messages)

    assert response.stop_reason == "tool_use"
    assert response.content[0].name == "web_search"
    assert response.content[0].input == {"query": "Search the web for the latest AI news."}


def test_first_step_gives_direct_answer_when_no_tool_needed():
    llm = PracticeLLM()
    messages = [_user_message("Hello there")]

    response = llm.create(messages=messages)

    assert response.stop_reason == "end_turn"
    assert response.content[0].type == "text"
    assert "Hello there" in response.content[0].text


def test_after_read_file_requests_web_search_when_question_asks_for_research():
    llm = PracticeLLM()
    file_result = {"success": True, "content": "Artificial Intelligence\n\nSome details."}
    messages = [
        _user_message("Read data/ai_research.txt, then research that topic on the web."),
        _assistant_tool_use_message("call_1", "read_file", {"path": "data/ai_research.txt"}),
        _tool_result_message("call_1", file_result),
    ]

    response = llm.create(messages=messages)

    assert response.stop_reason == "tool_use"
    assert response.content[0].name == "web_search"
    assert response.content[0].input == {"query": "Artificial Intelligence applications"}


def test_after_read_file_answers_directly_when_no_search_requested():
    llm = PracticeLLM()
    file_result = {"success": True, "content": "Artificial Intelligence\n\nSome details."}
    messages = [
        _user_message("Read data/ai_research.txt and summarize it."),
        _assistant_tool_use_message("call_1", "read_file", {"path": "data/ai_research.txt"}),
        _tool_result_message("call_1", file_result),
    ]

    response = llm.create(messages=messages)

    assert response.stop_reason == "end_turn"
    assert "Artificial Intelligence" in response.content[0].text


def test_after_web_search_gives_final_combined_answer():
    llm = PracticeLLM()
    file_result = {"success": True, "content": "Artificial Intelligence\n\nSome details."}
    search_result = {
        "success": True,
        "results": [{"title": "AI", "link": "https://example.com", "snippet": "AI is used everywhere."}],
    }
    messages = [
        _user_message("Read data/ai_research.txt, then research that topic on the web."),
        _assistant_tool_use_message("call_1", "read_file", {"path": "data/ai_research.txt"}),
        _tool_result_message("call_1", file_result),
        _assistant_tool_use_message("call_2", "web_search", {"query": "Artificial Intelligence applications"}),
        _tool_result_message("call_2", search_result),
    ]

    response = llm.create(messages=messages)

    assert response.stop_reason == "end_turn"
    text = response.content[0].text
    assert "Artificial Intelligence" in text
    assert "AI is used everywhere." in text


# --- Regression tests: a new question must not reuse a prior answer -------
#
# Bug: ResearchAgent accumulates every question asked in a session into one
# `messages` list. PracticeLLM used to always look at the *first* user text
# message and scan the *entire* history for tool results, so a second,
# unrelated question incorrectly reused the first question's tool results
# and answer. Fixed by scoping analysis to the messages since the most
# recent user-text message (see _current_question_messages in
# src/practice_llm.py).


def test_new_question_after_a_completed_question_is_analyzed_independently():
    llm = PracticeLLM()
    file_result = {"success": True, "content": "Artificial Intelligence\n\nSome details."}

    # A first question has already fully completed: asked, read_file called,
    # answered. Then a second, unrelated question is appended, exactly as
    # ResearchAgent.ask() would do on the same agent instance.
    messages = [
        _user_message("Read data/ai_research.txt and summarize it."),
        _assistant_tool_use_message("call_1", "read_file", {"path": "data/ai_research.txt"}),
        _tool_result_message("call_1", file_result),
        {"role": "assistant", "content": [_text_block("Some prior answer about the file.")]},
        _user_message("Search the web for information about artificial intelligence."),
    ]

    response = llm.create(messages=messages)

    # Must decide fresh based on the SECOND question, not reuse the first
    # question's already-completed read_file result.
    assert response.stop_reason == "tool_use"
    assert response.content[0].name == "web_search"
    assert response.content[0].input == {
        "query": "Search the web for information about artificial intelligence."
    }


def test_consecutive_different_questions_do_not_reuse_previous_answer():
    memory = SessionMemory()
    agent = ResearchAgent(client=PracticeClient(), memory=memory)

    file_search_result = {
        "success": True,
        "query": "irrelevant",
        "results": [{"title": "T", "link": "https://example.com", "snippet": "AI search snippet."}],
        "error": None,
    }

    answer1 = agent.ask("Read data/ai_research.txt and summarize it.")

    with patch("src.tools.registry.search_web", return_value=file_search_result) as mock_search_web:
        answer2 = agent.ask("Search the web for information about artificial intelligence.")

    assert answer1 != answer2

    # answer1 must come from the file, answer2 from the (mocked) search.
    assert "From the local file" in answer1
    assert "From the local file" not in answer2
    assert "AI search snippet." in answer2

    # web_search was called with the SECOND question's text, proving it
    # wasn't decided from stale first-question state.
    mock_search_web.assert_called_once_with(
        query="Search the web for information about artificial intelligence."
    )


def test_third_multi_hop_question_still_chains_both_tools_after_two_prior_questions():
    memory = SessionMemory()
    agent = ResearchAgent(client=PracticeClient(), memory=memory)

    search_result = {
        "success": True,
        "query": "irrelevant",
        "results": [{"title": "T", "link": "https://example.com", "snippet": "AI search snippet."}],
        "error": None,
    }

    with patch("src.tools.registry.search_web", return_value=search_result) as mock_search_web:
        agent.ask("Read data/ai_research.txt and summarize it.")
        agent.ask("Search the web for information about artificial intelligence.")
        answer3 = agent.ask(
            "Read data/ai_research.txt, identify its main topic, search the web "
            "for more information about that topic, and give me a combined summary."
        )

    # Third question must independently run BOTH read_file and web_search,
    # not be skipped because tool results already exist earlier in history.
    assert "From the local file" in answer3
    assert "From the web search" in answer3
    assert mock_search_web.call_count == 2  # once for question 2, once for question 3

    # Memory has three independent user/assistant cycles (question 3 also
    # has two "tool" turns for its own read_file + web_search).
    roles = [t["role"] for t in memory.get_turns()]
    assert roles == [
        "user", "tool", "assistant",  # question 1: read_file only
        "user", "tool", "assistant",  # question 2: web_search only
        "user", "tool", "tool", "assistant",  # question 3: read_file + web_search
    ]


# --- Integration test: real ResearchAgent + PracticeClient + real tools -----


FAKE_SEARCH_RESULT = {
    "success": True,
    "query": "Artificial Intelligence applications",
    "results": [
        {
            "title": "Applications of Artificial Intelligence",
            "link": "https://example.com/ai-applications",
            "snippet": "AI is used in healthcare, finance, and transportation.",
        }
    ],
    "error": None,
}


def test_practice_mode_runs_real_multi_hop_flow_through_real_components():
    memory = SessionMemory()
    trace_lines = []
    agent = ResearchAgent(client=PracticeClient(), memory=memory, trace=trace_lines.append)

    with patch("src.tools.registry.search_web", return_value=FAKE_SEARCH_RESULT) as mock_search_web:
        answer = agent.ask(
            "Read data/ai_research.txt, identify the main topic, research that "
            "topic using web search, and give me a combined summary."
        )

    # Both real tools were actually invoked (read_file for real, web_search
    # for real minus the outbound SerpAPI HTTP call, which is mocked here).
    mock_search_web.assert_called_once_with(query="Artificial Intelligence applications")

    assert "Artificial Intelligence" in answer
    assert "healthcare" in answer.lower()

    # Real SessionMemory recorded the whole flow.
    turns = memory.get_turns()
    roles = [t["role"] for t in turns]
    assert roles == ["user", "tool", "tool", "assistant"]
    tool_contents = " ".join(t["content"] for t in turns if t["role"] == "tool")
    assert "read_file" in tool_contents
    assert "web_search" in tool_contents

    # The optional trace callback fired with the documented labels, in order.
    assert trace_lines == [
        "[LLM] Deciding next action...",
        "[TOOL] read_file",
        "[HOOK] tool call logged",
        "[MEMORY] turn stored",
        "[LLM] Deciding next action...",
        "[TOOL] web_search",
        "[HOOK] tool call logged",
        "[MEMORY] turn stored",
        "[LLM] Generating final answer...",
    ]


if __name__ == "__main__":
    import pytest as _pytest

    raise SystemExit(_pytest.main([__file__, "-v"]))
