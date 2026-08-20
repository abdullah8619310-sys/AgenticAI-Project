"""Session memory.

Holds conversation turns and simple facts for the lifetime of a single
SessionMemory instance (i.e. one agent run). Everything lives in plain
Python data structures in process memory — nothing is written to disk or
any external store, and nothing survives past the instance being garbage
collected.
"""


class SessionMemory:
    """In-memory store of conversation turns and simple facts."""

    def __init__(self):
        self._turns = []
        self._facts = {}

    def add_turn(self, role: str, content: str) -> None:
        """Record one conversation turn, e.g. add_turn("user", "hi")."""
        self._turns.append({"role": role, "content": content})

    def get_turns(self) -> list:
        """Return all conversation turns recorded so far, in order."""
        return list(self._turns)

    def store_fact(self, key: str, value) -> None:
        """Remember a simple fact under `key` for later recall in this session."""
        self._facts[key] = value

    def get_fact(self, key: str):
        """Recall a fact previously stored with store_fact, or None if unknown."""
        return self._facts.get(key)

    def get_facts(self) -> dict:
        """Return all facts stored so far."""
        return dict(self._facts)
