# Agentic AI Project — Week 4

A single research agent (Anthropic Claude) that can search the web, read local
`.txt`/`.pdf` files, remember facts within a session, and log every tool call
it makes.

## Architecture

```
User query
   |
   v
src/agent.py  <-- reads/updates --> src/memory/session_memory.py
   |
   | (sends message + tool schemas from src/tools/registry.py to Claude)
   v
Claude decides to call a tool
   |
   v
src/hooks/tool_logger.py  --wraps-->  logs/tool_calls.log (timestamped)
   |
   v
src/tools/registry.py dispatches to:
   - src/skills/web_search.py   (SerpAPI Search API)
   - src/plugins/file_reader.py (.txt / .pdf reading)
   |
   v
Result returned to Claude -> loop continues (multi-hop) -> final answer
```

## Component roles

- **Agent** (`src/agent.py`): the orchestration loop.
- **Skill** (`src/skills/web_search.py`): web-search research capability.
- **Plugin** (`src/plugins/file_reader.py`): local file-reading capability.
- **Tools/functions** (`src/tools/registry.py`): Claude-facing tool schemas + dispatch.
- **Memory** (`src/memory/session_memory.py`): in-session conversation/fact store.
- **Hooks** (`src/hooks/tool_logger.py`): logs every tool call with a timestamp.

## Setup

1. `python -m venv venv` and activate it.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` and `SERPAPI_API_KEY`.
4. Run interactively (real Claude): `python -m src.agent`
5. Run interactively (no API credits needed): `python -m src.practice`
6. Run the test suite: `pytest`

## Two ways to run the agent

| | `python -m src.agent` (real mode) | `python -m src.practice` (practice mode) |
|---|---|---|
| Requires `ANTHROPIC_API_KEY` | Yes | No |
| Requires Anthropic API credits | Yes | No |
| Requires `SERPAPI_API_KEY` | Yes, for web search | Yes, for web search |
| Tool Registry, Tool Logger Hook, Session Memory | Real | Real |
| File Reader Plugin (.txt/.pdf) | Real | Real |
| Web Search Skill (SerpAPI) | Real | Real |
| What decides which tool to call next | Claude (Anthropic API) | `src/practice_llm.py` — simple keyword rules, not a language model |

**Local Practice Mode** (`src/practice.py` + `src/practice_llm.py`) exists
because Anthropic API credits aren't always available while developing.
`PracticeClient` in `src/practice_llm.py` implements the exact same
`client.messages.create(...)` shape `ResearchAgent` already expects from a
real Anthropic client, so `ResearchAgent(client=PracticeClient())` runs
through the *unmodified* real agent loop — real Tool Registry dispatch,
real Tool Logger Hook (writes real entries to `logs/tool_calls.log`), real
`SessionMemory`, the real file-reader plugin, and the real SerpAPI-backed
web-search skill. The **only** simulated piece is the decision of which
tool to call next, which `PracticeLLM` makes with simple keyword rules
(e.g. "mentions a file path or the word 'read'" → call `read_file`;
"mentions 'search'/'web'/'research'" → call `web_search`) instead of asking
Claude. Practice mode also passes a `trace=print` callback into
`ResearchAgent` (an optional, no-op-by-default hook added to `src/agent.py`
for this purpose) so each step prints live, e.g.:

```
[LLM] Deciding next action...
[TOOL] read_file
[HOOK] tool call logged
[MEMORY] turn stored
[LLM] Deciding next action...
[TOOL] web_search
[HOOK] tool call logged
[MEMORY] turn stored
[LLM] Generating final answer...
```

## Multi-hop demonstration

`tests/test_multi_hop_demo.py` proves a single agent run chains every
component together — reading a local file, then searching the web on the
topic it found, then combining both into one answer — using the *real*
integration between all the pieces (only the Claude API and the outbound
SerpAPI HTTP call are mocked, so the test needs no API credits/keys):

```
User Question
  ("Read data/ai_research.txt, identify the main topic,
    research it with web search, give me a combined summary.")
     |
     v
Claude requests: read_file(data/ai_research.txt)
     |
     v
Tool Registry (src/tools/registry.py) dispatches to ->
File Reader Plugin (src/plugins/file_reader.py) reads the real file
     |
     v
Tool Logger Hook (src/hooks/tool_logger.py) logs the call
  (timestamp, tool name, arguments, result, success)  --> logs/tool_calls.log
     |
     v
Session Memory (src/memory/session_memory.py) records the "tool" turn
     |
     v
File content sent back to Claude
     |
     v
Claude analyzes the file, identifies the topic ("artificial intelligence"),
and requests: web_search("artificial intelligence applications")
     |
     v
Tool Registry dispatches to -> Web Search Skill (src/skills/web_search.py)
     |
     v
Tool Logger Hook logs this second call too --> logs/tool_calls.log
     |
     v
Session Memory records this second "tool" turn
     |
     v
Search results sent back to Claude
     |
     v
Claude combines the file content + search results into one final answer
     |
     v
Session Memory records the final "assistant" turn
     |
     v
Final Answer (returned to the user)
```

The agent loop does **not** stop after the first tool call — it only stops
when Claude's response has no more tool requests, which is exactly what
`src/agent.py`'s `ResearchAgent.ask()` loop implements generically (this
demo just happens to take two hops).

Run just this demo with:
```
venv\Scripts\python.exe -m pytest tests/test_multi_hop_demo.py -v
```
