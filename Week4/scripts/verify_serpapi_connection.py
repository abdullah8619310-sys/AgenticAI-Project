"""One-off connectivity check for SerpAPI.

Not part of the agent architecture — safe to delete this file (and the
scripts/ folder, if empty) once the real web-search skill is implemented.

Usage:
    venv\\Scripts\\python.exe scripts\\verify_serpapi_connection.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from src.config import SERPAPI_API_KEY

TEST_QUERY = "what is artificial intelligence"
SERPAPI_URL = "https://serpapi.com/search.json"


def main() -> None:
    if not SERPAPI_API_KEY:
        print("FAILED: SERPAPI_API_KEY is not set in .env")
        return

    try:
        response = requests.get(
            SERPAPI_URL,
            params={"q": TEST_QUERY, "engine": "google", "api_key": SERPAPI_API_KEY},
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"FAILED: request error ({type(exc).__name__})")
        return

    print(f"HTTP status: {response.status_code}")

    if response.status_code != 200:
        print("FAILED: non-200 response")
        return

    data = response.json()
    results = data.get("organic_results", [])

    print(f"Success: {bool(results)}")
    print(f"Number of results: {len(results)}")
    if results:
        print(f"First result title: {results[0].get('title')}")


if __name__ == "__main__":
    main()
