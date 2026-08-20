"""Tests for the in-session memory component.

Run directly with:
    venv\\Scripts\\python.exe tests\\test_session_memory.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.memory.session_memory import SessionMemory


def test_store_and_retrieve_conversation_turn():
    memory = SessionMemory()
    memory.add_turn("user", "What is the capital of France?")

    turns = memory.get_turns()

    assert len(turns) == 1
    assert turns[0] == {"role": "user", "content": "What is the capital of France?"}


def test_retrieve_previous_turns_in_order():
    memory = SessionMemory()
    memory.add_turn("user", "What is the capital of France?")
    memory.add_turn("assistant", "Paris.")
    memory.add_turn("user", "What is its population?")

    turns = memory.get_turns()

    assert len(turns) == 3
    assert [t["role"] for t in turns] == ["user", "assistant", "user"]
    assert turns[1]["content"] == "Paris."


def test_store_and_retrieve_fact():
    memory = SessionMemory()
    memory.store_fact("capital_of_france", "Paris")

    assert memory.get_fact("capital_of_france") == "Paris"
    assert memory.get_facts() == {"capital_of_france": "Paris"}


def test_unknown_fact_returns_none():
    memory = SessionMemory()

    assert memory.get_fact("does_not_exist") is None


def test_new_instance_starts_empty():
    memory = SessionMemory()

    assert memory.get_turns() == []
    assert memory.get_facts() == {}


if __name__ == "__main__":
    tests = [
        test_store_and_retrieve_conversation_turn,
        test_retrieve_previous_turns_in_order,
        test_store_and_retrieve_fact,
        test_unknown_fact_returns_none,
        test_new_instance_starts_empty,
    ]
    for test in tests:
        test()
        print(f"PASSED: {test.__name__}")
