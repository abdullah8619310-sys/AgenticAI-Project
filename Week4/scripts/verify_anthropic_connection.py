"""One-off connectivity check for the Anthropic API.

Not part of the agent architecture — safe to delete this file (and the
scripts/ folder, if empty) at any time.

Usage:
    venv\\Scripts\\python.exe scripts\\verify_anthropic_connection.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from src.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL


def main() -> None:
    key_detected = bool(ANTHROPIC_API_KEY)
    print(f"Key detected: {'yes' if key_detected else 'no'}")
    print(f"Model ID: {ANTHROPIC_MODEL}")

    if not key_detected:
        print("Request succeeded: no (no key to use)")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply with just the word OK."}],
        )
    except anthropic.APIError as exc:
        print("Request succeeded: no")
        print(f"Error type: {type(exc).__name__}")
        return
    except Exception as exc:
        print("Request succeeded: no")
        print(f"Error type: {type(exc).__name__}")
        return

    print("Request succeeded: yes")
    text = "".join(block.text for block in response.content if block.type == "text")
    print(f"Model replied with {len(text)} character(s) of text.")


if __name__ == "__main__":
    main()
