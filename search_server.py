"""Research Swarm — MCP web search server for scout agents.

Stdio MCP server providing web_search and fetch_page tools.
Uses DuckDuckGo via ddgs (free, no API key, no limits).
Spawned as a child process per scout invocation via --mcp-config.
"""

import re
import time

import httpx
from ddgs import DDGS
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("research-search")


@mcp.tool()
def web_search(query: str, max_results: int = 10) -> list[dict]:
    """Search the web using DuckDuckGo.

    Args:
        query: Search query. Use operators for precision:
               "exact phrase", site:arxiv.org, filetype:pdf, intitle:keyword
        max_results: Max results to return (default 10, max 20).

    Returns:
        List of {title, url, snippet} dicts.
    """
    max_results = min(max_results, 20)
    try:
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
