"""Small, real (non-mocked) test for the web-search skill.

Uses the existing .env configuration to make one real SerpAPI call and
checks that the result is well-formed. Run directly with:

    venv\\Scripts\\python.exe tests\\test_web_search.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.skills.web_search import search_web


def test_search_web_returns_results():
    result = search_web("what is artificial intelligence")

    assert result["success"] is True, result["error"]
    assert result["query"] == "what is artificial intelligence"
    assert isinstance(result["results"], list)
    assert len(result["results"]) > 0

    first = result["results"][0]
    assert "title" in first
    assert "link" in first
    assert "snippet" in first

    print(f"success: {result['success']}")
    print(f"number of results: {len(result['results'])}")
    print(f"first result title: {first['title']}")


if __name__ == "__main__":
    test_search_web_returns_results()
    print("PASSED: test_search_web_returns_results")
