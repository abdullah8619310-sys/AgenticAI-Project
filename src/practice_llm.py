"""LOCAL PRACTICE MODE — simulated LLM decision layer, no Anthropic API required.

This module is a drop-in stand-in for the Claude client used by
ResearchAgent (see src/agent.py). It implements the exact same protocol
ResearchAgent already expects from `self.client`:

    client.messages.create(model=..., max_tokens=..., system=..., tools=...,
                            messages=...) -> object with .content and
                                              .stop_reason

...where .content is a list of blocks shaped like either:
    {"type": "text", "text": "..."}
    {"type": "tool_use", "id": "...", "name": "...", "input": {...}}

Because it matches this protocol exactly, ResearchAgent(client=PracticeClient())
runs the real agent loop — real Tool Registry dispatch, real Tool Logger
Hook, real SessionMemory, real read_file/web_search tools — with only the
"what should I do next" decision being simulated instead of asking Claude.

PracticeLLM is NOT a language model. It is simple, rule-based, and only
good enough to walk through the multi-hop read_file -> web_search -> final
answer flow for practice, without spending Anthropic API credits.
"""

import json
import re
from types import SimpleNamespace

DEFAULT_PRACTICE_FILE = "data/ai_research.txt"

_FILE_PATH_PATTERN = re.compile(r"[\w./\\-]+\.(?:txt|pdf)", re.IGNORECASE)
_FILE_TRIGGER_WORDS = ("read", "file", ".txt", ".pdf", "document")
_SEARCH_TRIGGER_WORDS = (
    "search",
    "web",
    "internet",
    "online",
    "latest",
    "news",
    "look up",
    "lookup",
    "research",
    "topic",
)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(tool_use_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=tool_use_id, name=name, input=tool_input)


def _response(content, stop_reason):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def _matches_any(text: str, keywords) -> bool:
    """True if any keyword appears in `text` as a whole word/phrase.

    Uses word boundaries (not plain substring containment) so a keyword
    like "research" doesn't false-positive on an unrelated word that
    merely contains it, e.g. a file path such as "ai_research.txt".
    """
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in keywords)


def _extract_file_path(text: str):
    match = _FILE_PATH_PATTERN.search(text)
    return match.group(0) if match else None


def _extract_topic(file_result: dict) -> str:
    """Very simple heuristic: the file's first non-empty line is its "topic"."""
    if not file_result or not file_result.get("success"):
        return ""
    content = file_result.get("content") or ""
    for line in content.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _current_question_start_index(messages) -> int:
    """Index of the most recent plain-string user message (i.e. the latest
    question asked via ResearchAgent.ask(), as opposed to a tool_result
    reply). ResearchAgent accumulates every question into the same
    `messages` list across a whole session, so without this, analysis
    below would mix in tool activity from earlier, unrelated questions.
    """
    for i in range(len(messages) - 1, -1, -1):
        message = messages[i]
        if message["role"] == "user" and isinstance(message["content"], str):
            return i
    return 0


def _latest_user_text(messages) -> str:
    index = _current_question_start_index(messages)
    return messages[index]["content"]


def _current_question_messages(messages) -> list:
    """Only the slice of `messages` belonging to the question being asked
    right now, discarding any earlier questions' tool activity."""
    return messages[_current_question_start_index(messages):]


def _tool_use_id_to_name(messages) -> dict:
    id_to_name = {}
    for message in messages:
        if message["role"] == "assistant" and isinstance(message["content"], list):
            for block in message["content"]:
                if getattr(block, "type", None) == "tool_use":
                    id_to_name[block.id] = block.name
    return id_to_name


def _all_tool_results(messages):
    """Yields (tool_name, result_dict) for every tool call completed so
    far *for the current question only* (see _current_question_messages)."""
    current_question_messages = _current_question_messages(messages)
    id_to_name = _tool_use_id_to_name(current_question_messages)
    for message in current_question_messages:
        if message["role"] == "user" and isinstance(message["content"], list):
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_name = id_to_name.get(block["tool_use_id"])
                    yield tool_name, json.loads(block["content"])


def _last_tool_result(messages):
    results = list(_all_tool_results(messages))
    return results[-1] if results else (None, None)


class PracticeLLM:
    """Rule-based stand-in for Claude's tool-calling decisions.

    Given the conversation so far (the same `messages` list ResearchAgent
    builds for the real API), decides whether to request a tool call or
    give a final answer, using simple keyword heuristics rather than real
    reasoning.
    """

    def __init__(self):
        self._next_call_id = 0

    def create(self, *, messages, **_ignored_kwargs):
        # Scoped to the current question only — ResearchAgent accumulates
        # every question asked in this session into the same `messages`
        # list, so without this scoping, a new question would be analyzed
        # alongside (and could be shadowed by) an earlier question's
        # already-completed tool activity.
        question = _latest_user_text(messages)
        last_tool_name, last_tool_result = _last_tool_result(messages)

        if last_tool_name is None:
            return self._decide_first_step(question)

        if last_tool_name == "read_file":
            return self._decide_after_read_file(question, last_tool_result, messages)

        # Any other case (already searched, or first tool was web_search) ->
        # we have enough to answer.
        return _response([_text_block(self._final_answer(question, messages))], "end_turn")

    def _decide_first_step(self, question: str):
        file_path = _extract_file_path(question)
        wants_file = file_path is not None or _matches_any(question, _FILE_TRIGGER_WORDS)

        if wants_file:
            path = file_path or DEFAULT_PRACTICE_FILE
            return self._tool_call("read_file", {"path": path})

        if _matches_any(question, _SEARCH_TRIGGER_WORDS):
            return self._tool_call("web_search", {"query": question})

        return _response(
            [
                _text_block(
                    "[Practice mode] No tool was needed for this question in the "
                    f'simulated decision rules: "{question}". Try mentioning a '
                    "file (e.g. data/ai_research.txt) or asking to search the "
                    "web to see the full multi-hop flow."
                )
            ],
            "end_turn",
        )

    def _decide_after_read_file(self, question: str, file_result: dict, messages):
        if not _matches_any(question, _SEARCH_TRIGGER_WORDS):
            return _response([_text_block(self._final_answer(question, messages))], "end_turn")

        topic = _extract_topic(file_result)
        query = f"{topic} applications" if topic else question
        return self._tool_call("web_search", {"query": query})

    def _final_answer(self, question: str, messages) -> str:
        file_text = None
        search_snippets = []

        for tool_name, result in _all_tool_results(messages):
            if tool_name == "read_file" and result.get("success"):
                file_text = result.get("content")
            elif tool_name == "web_search" and result.get("success"):
                search_snippets = [r.get("snippet", "") for r in result.get("results", [])[:2]]

        parts = [f'[Practice mode] Combined summary for: "{question}"']
        if file_text:
            first_line = next((l.strip() for l in file_text.splitlines() if l.strip()), "")
            parts.append(f"From the local file: {first_line}")
        if search_snippets:
            parts.append("From the web search: " + " ".join(s for s in search_snippets if s))
        if len(parts) == 1:
            parts.append("(No tool results were available to summarize.)")

        return "\n".join(parts)

    def _tool_call(self, name: str, tool_input: dict):
        self._next_call_id += 1
        block = _tool_use_block(f"practice_call_{self._next_call_id}", name, tool_input)
        return _response([block], "tool_use")


class PracticeClient:
    """Drop-in replacement for anthropic.Anthropic, backed by PracticeLLM.

    Matches the same `.messages.create(...)` shape ResearchAgent already
    calls on a real Anthropic client, so it can be passed straight into
    ResearchAgent(client=PracticeClient()) with no changes to the agent's
    tool-calling protocol.
    """

    def __init__(self):
        self._llm = PracticeLLM()
        self.messages = SimpleNamespace(create=self._llm.create)
