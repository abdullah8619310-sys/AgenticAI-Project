"""LOCAL PRACTICE MODE CLI — no Anthropic API required.

Runs the real ResearchAgent (src/agent.py) with PracticeClient
(src/practice_llm.py) standing in for the Claude API. Every other
component is real: the Tool Registry, the Tool Logger Hook (writes to
logs/tool_calls.log), SessionMemory, the file-reader plugin, and the
SerpAPI-backed web-search skill. Only the "which tool should I call next"
decision is simulated.

Usage:
    python -m src.practice
"""

from src.agent import ResearchAgent
from src.practice_llm import PracticeClient


def main() -> None:
    print("=" * 68)
    print("LOCAL PRACTICE MODE — no Anthropic API required")
    print("Real Tool Registry, Tool Logger Hook, Session Memory, and the")
    print("real SerpAPI-backed web search / file reader all run for real.")
    print("Only the LLM decision layer is simulated.")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 68)

    agent = ResearchAgent(client=PracticeClient(), trace=print)

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
