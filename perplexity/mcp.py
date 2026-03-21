import json
import os
import sys

from mcp.server.fastmcp import FastMCP

from perplexity import Client
from perplexity.logger import setup_logger

logger = setup_logger("mcp")

mcp = FastMCP(
    "perplexity",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)


def perplexity_ask(query: str) -> str:
    """Ask Perplexity a question and get a concise AI-generated answer.

    Uses Perplexity's auto mode, which selects the best approach for the query.
    This is the default general-purpose tool — use it for factual questions,
    explanations, summaries, and most everyday queries.

    Limitations:
    - Does not support follow-up context, file uploads, or source filtering.
    - Returns plain text only (no citations, images, or structured results).
    - Answers may not reflect the very latest real-time information.
    """
    return client.search(query, mode="auto").get("answer", "")


def perplexity_research(query: str) -> str:
    """Conduct deep, multi-step research on a topic using Perplexity.

    Uses Perplexity's deep research mode, which autonomously breaks the query
    into sub-questions, searches broadly, and synthesizes a comprehensive report.
    Best for complex topics requiring thorough investigation across many sources.

    Limitations:
    - Significantly slower than other tools (may take 30–120 seconds).
    - Does not support follow-up context, file uploads, or source filtering.
    - Returns plain text only (no citations, images, or structured results).
    - Only one model is available in this mode (cannot select a specific model).
    """
    return client.search(query, mode="deep research").get("answer", "")


def perplexity_reason(query: str) -> str:
    """Ask Perplexity to reason step-by-step through a complex problem.

    Uses Perplexity's reasoning mode, which applies chain-of-thought reasoning
    before producing an answer. Best for logic puzzles, math problems, multi-step
    analysis, coding questions, and decisions requiring structured thinking.

    Limitations:
    - Slower than auto mode due to the reasoning step.
    - Does not support follow-up context, file uploads, or source filtering.
    - Returns plain text only (no citations, images, or structured results).
    """
    return client.search(query, mode="reasoning").get("answer", "")


def perplexity_search(query: str) -> str:
    """Search the web using Perplexity and get an AI-synthesized answer.

    Uses Perplexity's Pro mode with web sources, providing a more thorough
    web search than auto mode. Best for current events, recent developments,
    and queries where up-to-date web results are important.

    Limitations:
    - Only searches the web (no academic/scholar or social sources).
    - Does not support follow-up context or file uploads.
    - Returns plain text only (no citations, images, or structured results).
    """
    return client.search(query, mode="pro", sources=["web"]).get("answer", "")


def main():
    global client

    cookies_env = os.environ.get("PERPLEXITY_COOKIES")
    if cookies_env:
        try:
            cookies = json.loads(cookies_env)
        except json.JSONDecodeError:
            sys.exit("ERROR: PERPLEXITY_COOKIES is not valid JSON.")
    else:
        cookies = {}

    client = Client(cookies)

    mcp.tool()(perplexity_ask)

    if client.own:
        logger.info("Authenticated — all 4 tools available.")
        mcp.tool()(perplexity_research)
        mcp.tool()(perplexity_reason)
        mcp.tool()(perplexity_search)
    else:
        logger.warning(
            "No PERPLEXITY_COOKIES set — running anonymously. "
            "Only perplexity_ask is available. "
            "Set PERPLEXITY_COOKIES to enable perplexity_search, perplexity_reason, and perplexity_research."
        )

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport not in ("stdio", "http"):
        sys.exit("ERROR: MCP_TRANSPORT must be 'stdio' or 'http'")

    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
