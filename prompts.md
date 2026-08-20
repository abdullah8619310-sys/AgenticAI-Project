# Development Prompts Log

This file records the prompts used to build this project, in chronological order,
as required by the Week 4 assignment.

## 1. Project planning and setup

> We are starting a new Agentic AI project for my Week 4 internship assignment...
> First, only perform project planning and setup: inspect the folder, recommend a
> tech stack, recommend architecture/folder structure, recommend dependencies,
> map components to agent/skill/tools/memory/hooks/plugin, explain connections,
> and create only the basic project foundation (no feature implementation yet).

Follow-up clarifications answered: LLM provider = Anthropic Claude, Search API = Brave Search.

## 2. Python environment setup

> Yes, proceed with the Python environment setup. Create a project-local virtual
> environment named `venv`, install dependencies from requirements.txt, verify
> imports, and report versions. Do not implement any assignment features yet.

## 3. Switch search provider to SerpAPI

> We are switching the web-search provider from Brave Search to SerpAPI because
> I am using the SerpAPI free plan. Configure SerpAPI only (env var, config.py,
> docs) — do not implement the web-search logic yet.

## 4. Verify SerpAPI connection

> The SERPAPI_API_KEY is now stored in the local .env file. For the next step,
> I only want to verify that the SerpAPI connection works. Make one simple
> test request using the existing requests package, show only safe response
> info, do not implement the Web Search Skill yet, do not expose the API key.

## 5. Implement the Web Search Skill

> The SerpAPI connection test succeeded. Now implement ONLY the Web Search
> Skill in src/skills/web_search.py: accept a query, use SERPAPI_API_KEY from
> src/config.py, call the SerpAPI endpoint, handle errors safely, return a
> clean structured result (title/link/snippet), never expose the API key.
> Create a small test that verifies a real search returns results. Do not
> implement the agent loop, memory, hooks, file-reader plugin, or connect the
> skill to Claude's tool-calling loop yet.

## 6. Implement session memory

> The Web Search Skill is now implemented and tested successfully. Now
> implement ONLY the session memory component in src/memory/session_memory.py:
> session-scoped, lives only during the current agent run, stores conversation
> turns, retrieves previous context, optionally stores simple facts. Plain
> Python in-memory only — no ChromaDB/vector DB/Postgres/external service.
> Create tests/test_session_memory.py covering turn storage/retrieval, fact
> storage/retrieval, and that a new instance starts empty. Do not modify
> agent.py, web_search.py, hooks/, plugins/, or tools/registry.py, and do not
> connect memory to Claude yet.

## 7. Implement the tool-call logging hook

> The Web Search Skill and Session Memory components are now implemented and
> tested successfully. Now implement ONLY the tool-call logging hook in
> src/hooks/tool_logger.py: record timestamp, tool name, arguments, result,
> and success/failure for every tool dispatch, written to
> logs/tool_calls.log, with a clear before/after action pattern. Keep it
> independent from the Agent — do not connect it to src/agent.py yet. Do not
> expose API keys or secrets in the logs. Create tests/test_tool_logger.py
> covering log-entry creation, timestamp presence, tool name, safe argument
> recording, result/status recording, failure logging, and secret redaction.
> Use Python's standard logging module.

## 8. Implement the File Reader Plugin

> The Web Search Skill, Session Memory, and Tool-Call Logging Hook are now
> implemented and tested successfully. Now implement ONLY the File Reader
> Plugin in src/plugins/file_reader.py: support .txt and .pdf (using the
> existing pypdf dependency), accept a file path, validate existence and
> extension, return a clear error for unsupported extensions, handle
> unreadable/corrupt files safely, add file-size/path safety checks. Keep
> independent from the Agent — do not connect it yet. Create
> tests/test_file_reader.py and small sample files under data/ (.txt, .pdf)
> covering TXT reading, PDF extraction, nonexistent files, unsupported
> extensions, and corrupt files.

## 9. Implement the Tool Registry

> The Web Search Skill, Session Memory, Tool-Call Logging Hook, and File
> Reader Plugin are now implemented and tested successfully. Now implement
> ONLY the Tool Registry in src/tools/registry.py: register web_search and
> read_file with Claude-compatible tool definitions/schemas (name,
> description, required parameters, types), a way to retrieve all
> definitions, and a way to dispatch a tool call by name and arguments.
> Unknown tool names and invalid/missing arguments must be handled safely,
> not crash. Do not implement the Claude API or agent loop yet, do not
> connect the logging hook yet. Create tests/test_tool_registry.py covering
> registration, Claude-compatible definitions, dispatching both tools, and
> safe handling of unknown tools/invalid arguments.

## 10. Implement the Agent (integration step)

> The Web Search Skill, Session Memory, Tool-Call Logging Hook, File Reader
> Plugin, and Tool Registry are now implemented and tested. Now implement
> the actual Agent in src/agent.py: a real Claude tool-calling loop (user
> query -> Claude -> tool request(s) -> dispatch via the Tool Registry ->
> log via the Tool Logger Hook -> store in SessionMemory -> send tool
> result back to Claude -> repeat -> stop on final response), using the
> existing registry/memory/hook rather than duplicating their logic, with a
> max-iteration limit, graceful API/tool error handling, no secret
> exposure, no other agent framework. Create tests/test_agent.py mocking
> the Claude API to cover the orchestration logic, and add a
> `python -m src.agent` CLI entry point. Do not implement the multi-hop
> demo yet.

## 11. Verify the Anthropic API connection

> The ANTHROPIC_API_KEY has now been added to the project's .env file.
> Verify it is loading correctly, make one minimal real Anthropic API
> request using the configured model, and verify the model ID is valid.
> Do not print/expose the key. Report only: key detected (yes/no), request
> succeeded (yes/no), model ID used, error type if it failed.

## 12. Multi-hop demonstration

> We are now implementing the final practical requirement of Week 4: "Demo:
> single agent answers multi-hop questions using all of the above." Create
> data/ai_research.txt (a short factual AI document) and
> tests/test_multi_hop_demo.py simulating: Claude requests read_file(...),
> receives file content, requests web_search(topic from the file), receives
> results, produces a final combined answer. Must verify both tools were
> called, the tool-call hook logged both with timestamps, SessionMemory
> contains the expected turns, the Tool Registry dispatched both tools, and
> the agent did not stop after the first tool call. Mock the Claude API and
> the SerpAPI call — no real API credits/network calls in this test. No
> LangChain/LlamaIndex/other framework. Add a demonstration section to
> README.md with the full component flow diagram. Run the complete suite
> with pytest and report totals.

## 13. Solve real-mode BadRequestError

> (venv) PS ... python -m src.agent ... "Claude API error: BadRequestError" /
> "Agent: Sorry, I couldn't reach Claude right now." — solve this error and
> make it proper working.

## 14. Add Local Practice Mode

> I want to add a LOCAL PRACTICE MODE to my Week 4 Agentic AI project. I
> currently cannot use the real Anthropic API because my account has no API
> credits. Do NOT remove, replace, or weaken the existing real Claude API
> implementation. Instead, add a separate practice/demo LLM implementation
> (src/practice_llm.py) that simulates Claude's tool-calling decisions,
> integrates with the existing ResearchAgent's tool-calling protocol, and
> only simulates the LLM decision layer — read_file, web_search, the Tool
> Registry, the Tool Logger Hook, and SessionMemory must all be real, not
> mocked. Add a `python -m src.practice` CLI clearly labeled "LOCAL
> PRACTICE MODE — no Anthropic API required", with exit/quit and visible
> optional tracing ([LLM]/[TOOL]/[HOOK]/[MEMORY] lines). No API keys
> exposed, no LangChain/LlamaIndex, no real Anthropic calls. Add tests, run
> the complete pytest suite, update README.md explaining real mode vs
> practice mode, and update prompts.md.

## 15. Fix practice-mode bug: stale answer reused on new questions

> There is a bug in local practice mode: the first query works correctly,
> but subsequent different queries incorrectly return the same previous
> answer instead of running their own tool calls. Investigate the actual
> cause (whether PracticeLLM keeps stale state, whether the current query
> is passed to PracticeLLM.create(), whether SessionMemory is treated as
> the current query, whether the practice client generates a response from
> old messages) before changing anything, then fix the root cause. Keep
> the real Tool Registry, Tool Logger Hook, SessionMemory, SerpAPI web
> search, and file reader; only the LLM decision logic may remain
> simulated. Every new question must be independently processed, and
> multi-step (read_file + web_search) behavior must still work. Add
> regression tests proving two consecutive different questions don't reuse
> the first answer, and run the complete pytest suite.
