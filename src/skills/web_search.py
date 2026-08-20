"""Web-search skill, backed by the SerpAPI Search API.

Given a query string, returns a small list of search results (title, link,
snippet) for the agent to reason over.

This module only knows how to search the web — it is not wired into the
Claude tool-calling loop yet. That happens later, in src/tools/registry.py.
"""

import requests

from src.config import SERPAPI_API_KEY

SERPAPI_URL = "https://serpapi.com/search.json"
DEFAULT_NUM_RESULTS = 5
REQUEST_TIMEOUT_SECONDS = 10


def search_web(query: str, num_results: int = DEFAULT_NUM_RESULTS) -> dict:
    """Search the web for `query` using SerpAPI.

    Returns a dict shaped like:
        {
            "success": bool,
            "query": str,
            "results": [{"title": str, "link": str, "snippet": str}, ...],
            "error": str | None,
        }

    The API key is read from config and is never included in the returned
    dict, in any error message, or printed anywhere.
    """
    if not SERPAPI_API_KEY:
        return _error_result(query, "SERPAPI_API_KEY is not configured")

    try:
        response = requests.get(
            SERPAPI_URL,
            params={
                "q": query,
                "engine": "google",
                "api_key": SERPAPI_API_KEY,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        # Never include the exception's request/response details here, since
        # they can contain the request URL (and therefore the API key).
        return _error_result(query, "Network error while contacting SerpAPI")

    if response.status_code != 200:
        return _error_result(query, f"SerpAPI returned HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError:
        return _error_result(query, "SerpAPI returned an invalid response")

    organic_results = data.get("organic_results", [])
    results = [
        {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        }
        for item in organic_results[:num_results]
    ]

    return {
        "success": True,
        "query": query,
        "results": results,
        "error": None,
    }


def _error_result(query: str, message: str) -> dict:
    return {
        "success": False,
        "query": query,
        "results": [],
        "error": message,
    }
