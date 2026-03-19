"""Research Swarm — MCP web search server for scout agents.

Stdio MCP server providing web_search and fetch_page tools.
Supports DuckDuckGo (free, no API key) and Tavily (API key required).
Provider is selected via SEARCH_PROVIDER env var or config.toml [search] section.
Spawned as a child process per scout invocation via --mcp-config.
"""

import os
import re
import time

import httpx
from ddgs import DDGS
from mcp.server.fastmcp import FastMCP


def _get_search_provider() -> str:
    """Return the configured search provider ('duckduckgo' or 'tavily').

    Priority: SEARCH_PROVIDER env var > config.toml [search].provider > 'duckduckgo'.
    """
    provider = os.environ.get("SEARCH_PROVIDER", "").strip().lower()
    if provider in ("duckduckgo", "tavily"):
        return provider
    # Fall back to config.toml
    try:
        import tomllib

        with open("config.toml", "rb") as f:
            cfg = tomllib.load(f)
        provider = cfg.get("search", {}).get("provider", "duckduckgo").strip().lower()
        if provider in ("duckduckgo", "tavily"):
            return provider
    except Exception:
        pass
    return "duckduckgo"


def _search_tavily(query: str, max_results: int) -> list[dict]:
    """Search the web using Tavily."""
    from tavily import TavilyClient

    client = TavilyClient()  # uses TAVILY_API_KEY env var
    response = client.search(query=query, max_results=max_results)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in response.get("results", [])
    ]


def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    """Search the web using DuckDuckGo."""
    results = DDGS().text(query, max_results=max_results)
    time.sleep(1)  # Rate limit: 3 scouts search in parallel
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
        }
        for r in results
    ]

mcp = FastMCP("research-search")


@mcp.tool()
def web_search(query: str, max_results: int = 10) -> list[dict]:
    """Search the web using the configured provider (DuckDuckGo or Tavily).

    Args:
        query: Search query. Use operators for precision:
               "exact phrase", site:arxiv.org, filetype:pdf, intitle:keyword
        max_results: Max results to return (default 10, max 20).

    Returns:
        List of {title, url, snippet} dicts.
    """
    max_results = min(max_results, 20)
    provider = _get_search_provider()
    try:
        if provider == "tavily":
            return _search_tavily(query, max_results)
        return _search_duckduckgo(query, max_results)
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def fetch_page(url: str) -> str:
    """Fetch a web page and return its text content.

    Use to read paper abstracts, READMEs, blog posts, documentation.
    HTML is stripped. Output truncated to 15000 chars.

    Args:
        url: Full URL to fetch.

    Returns:
        Plain text content of the page.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            resp = client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (research-swarm/1.0)"},
            )
            resp.raise_for_status()
            text = resp.text
        # Strip scripts, styles, then all HTML tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:15000]
    except Exception as e:
        return f"Error fetching {url}: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
