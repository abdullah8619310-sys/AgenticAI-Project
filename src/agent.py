"""Agent orchestration loop.

Wires together everything built in previous steps into one research agent:

    user query -> Claude -> Claude may request tool(s) -> dispatch each
    tool through the Tool Registry, executed through the logging hook ->
    tool result sent back to Claude -> repeat until Claude gives a final
    text answer (or the iteration limit is hit).

Conversation turns are recorded in SessionMemory so the agent can recall
earlier context within the same run.
"""

import json

import anthropic

from src.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from src.hooks.tool_logger import run_logged_tool_call
from src.memory.session_memory import SessionMemory
from src.tools.registry import dispatch_tool_call, get_tool_definitions

MAX_ITERATIONS = 8
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "You are a research assistant. Use the web_search tool to look up "
    "information on the internet, and the read_file tool to read local "
    ".txt or .pdf files, whenever they would help answer the user's "
    "question. Give clear, concise final answers, and cite what you found "
    "when relevant."
)


class ResearchAgent:
    """A single Claude-backed agent with web search, file reading, and memory."""

    def __init__(
        self,
        memory: SessionMemory = None,
        client=None,
        max_iterations: int = MAX_ITERATIONS,
        trace=None,
    ):
        self.client = client or anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = memory or SessionMemory()
        self.max_iterations = max_iterations
        # Optional callback(str) for step-by-step tracing (e.g. practice
        # mode). Defaults to a no-op, so real-mode behavior/output is
        # unchanged unless a caller explicitly opts in.
        self._trace = trace or (lambda message: None)
        self._messages = []  # Claude API message history for this run

    def ask(self, user_query: str) -> str:
        """Answer one user query, running the tool-calling loop to completion."""
        self.memory.add_turn("user", user_query)
        self._messages.append({"role": "user", "content": user_query})

        for _ in range(self.max_iterations):
            response = self._call_claude()
            if response is None:
                answer = "Sorry, I couldn't reach Claude right now. Please try again."
                self.memory.add_turn("assistant", answer)
                return answer

            self._messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                self._trace("[LLM] Generating final answer...")
                answer = _extract_text(response)
                self.memory.add_turn("assistant", answer)
                return answer

            self._trace("[LLM] Deciding next action...")
            tool_results = [
                self._handle_tool_use(block)
                for block in response.content
                if block.type == "tool_use"
            ]
            self._messages.append({"role": "user", "content": tool_results})

        answer = "Stopped: reached the maximum number of tool-call steps without a final answer."
        self.memory.add_turn("assistant", answer)
        return answer

    def _call_claude(self):
        try:
            return self.client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=get_tool_definitions(),
                messages=self._messages,
            )
        except Exception as exc:
            print(f"Claude API error: {_describe_api_error(exc)}")
            return None

    def _handle_tool_use(self, block) -> dict:
        tool_name = block.name
        arguments = block.input or {}

        self._trace(f"[TOOL] {tool_name}")

        try:
            result = run_logged_tool_call(
                tool_name,
                arguments,
                lambda **kwargs: dispatch_tool_call(tool_name, kwargs),
            )
        except Exception as exc:
            result = {
                "success": False,
                "tool": tool_name,
                "error": f"Tool execution failed: {type(exc).__name__}",
            }

        self._trace("[HOOK] tool call logged")

        self.memory.add_turn("tool", f"{tool_name}({arguments}) -> {result}")
        self._trace("[MEMORY] turn stored")

        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(result, default=str),
        }


def _extract_text(response) -> str:
    parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(parts).strip()


def _describe_api_error(exc: Exception) -> str:
    """A short, safe-to-print description of an API failure.

    Anthropic's structured error responses (status code + JSON error body)
    never include the API key, so it's safe to surface their message
    directly — this is what makes billing/quota/model errors distinguishable
    from real network failures. For anything else (e.g. a raw connection
    error), only the exception type name is shown, since such errors can
    otherwise embed request details.
    """
    status_code = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    message = body.get("error", {}).get("message") if isinstance(body, dict) else None

    if status_code and message:
        return f"{type(exc).__name__} (HTTP {status_code}): {message}"
    if status_code:
        return f"{type(exc).__name__} (HTTP {status_code})"
    return type(exc).__name__


def main() -> None:
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY is not set. Add it to .env before running the agent.")
        return

    agent = ResearchAgent()
    print("Research Agent — ask a question (type 'exit' or 'quit' to stop).")

    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            break

        answer = agent.ask(query)
        print(f"\nAgent: {answer}")


if __name__ == "__main__":
    main()
