import asyncio
import atexit
import json
import math
import os
import sys
import threading
from functools import wraps
from pathlib import Path
from typing import Any, Optional

try:
    # mcp >= 2.0 renamed mcp.server.fastmcp.FastMCP to
    # mcp.server.mcpserver.MCPServer and moved host/port from the
    # constructor to run().
    from mcp.server.mcpserver import MCPServer as _Server

    _HTTP_BIND_ON_RUN = True
except ImportError:
    try:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as _Server

        _HTTP_BIND_ON_RUN = False
    except ImportError:  # mcp not installed at all
        _Server = None  # type: ignore[assignment,misc]
        _HTTP_BIND_ON_RUN = False

from perplexity import Client
from perplexity.logger import setup_logger
from perplexity.research_jobs import (
    ACTIVE_STATES,
    JOURNAL_SUPPORT_MESSAGE,
    JOURNAL_SUPPORTED,
    ResearchJobManager,
)

logger = setup_logger("mcp")

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))

if _Server is None:
    mcp = None
elif _HTTP_BIND_ON_RUN:
    mcp = _Server("perplexity")
else:
    mcp = _Server("perplexity", host=HOST, port=PORT)

client: Optional[Client] = None
research_manager: Optional[ResearchJobManager] = None
_research_manager_lock = threading.Lock()


def _get_client() -> Client:
    """Lazily initialize and return the global Client instance."""
    global client
    if client is None:
        cookies_env = os.environ.get("PERPLEXITY_COOKIES")
        cookies = {}
        if cookies_env:
            try:
                cookies = json.loads(cookies_env)
            except json.JSONDecodeError:
                logger.error("PERPLEXITY_COOKIES is not valid JSON.")
        client = Client(cookies)
    return client


def _extract_answer(resp: Any) -> str:
    """Safely extract the markdown answer text from search response dict."""
    if not isinstance(resp, dict):
        return str(resp) if resp else ""
    for block in resp.get("blocks", []):
        if isinstance(block, dict) and block.get("intended_usage") == "ask_text":
            markdown_block = block.get("markdown_block", {})
            if isinstance(markdown_block, dict):
                return str(markdown_block.get("answer", ""))
    return str(resp.get("answer", ""))


def _bounded_env_number(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    try:
        value = float(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _get_research_manager(cli: Optional[Client] = None) -> ResearchJobManager:
    """Return the server-wide authenticated research manager."""
    global research_manager
    if research_manager is not None:
        return research_manager
    with _research_manager_lock:
        if research_manager is not None:
            return research_manager
        cli = cli or _get_client()
        if not cli.own:
            raise PermissionError("research journal tools require an authenticated server")

        state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
        db_path = os.environ.get(
            "PERPLEXITY_RESEARCH_DB",
            str(Path(state_home) / "perplexity-ai" / "research-jobs.sqlite3"),
        )
        provider_timeout = _bounded_env_number(
            "PERPLEXITY_RESEARCH_PROVIDER_TIMEOUT", 900.0, 30.0, 3600.0
        )
        max_queue = _bounded_env_int("PERPLEXITY_RESEARCH_MAX_QUEUE", 8, 1, 100)

        def run_research(query: str, observe) -> Any:
            response = cli.search(
                query,
                mode="deep research",
                provider_timeout=provider_timeout,
                require_complete=True,
                event_callback=observe,
            )
            if isinstance(response, dict) and not response.get("answer"):
                response = {**response, "answer": _extract_answer(response)}
            return response

        manager = ResearchJobManager(
            db_path,
            run_research,
            owner_scope="authenticated-mcp-server",
            max_queue=max_queue,
        )
        research_manager = manager
        return manager


def _shutdown_research_manager() -> None:
    global research_manager
    with _research_manager_lock:
        manager = research_manager
        research_manager = None
    if manager is not None:
        manager.close()


atexit.register(_shutdown_research_manager)


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
    cli = _get_client()
    try:
        resp = cli.search(query, mode="auto")
        return _extract_answer(resp)
    except Exception as e:
        logger.error(f"perplexity_ask error: {e}")
        return f"Error executing query: {e}"


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
    try:
        manager = _get_research_manager()
        job = manager.start(query)
        finished = manager.wait(job["id"])
        return _research_result_text(finished)
    except Exception as e:
        logger.error("perplexity_research failed: %s", e.__class__.__name__)
        return "Error executing research query: Research could not be completed"


def perplexity_research_start(query: str, idempotency_key: Optional[str] = None) -> dict[str, Any]:
    """Start durable local research and return its stable local ID immediately.

    `idempotency_key` is recommended when retrying a start whose response may have
    been lost. The same key and query return the same record; a different query
    conflicts. This records work launched through this MCP server only.
    """
    return _get_research_manager().start(query, idempotency_key=idempotency_key)


def perplexity_research_list(
    query: Optional[str] = None,
    status: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search this server's local research records with bounded pagination."""
    return _get_research_manager().list(
        query=query,
        status=status,
        cursor=cursor,
        limit=limit,
    )


def perplexity_research_get(research_id: str) -> dict[str, Any]:
    """Get local delivery status and the exact result when completed."""
    return _get_research_manager().get(research_id)


def _research_result_text(finished: dict[str, Any]) -> str:
    if finished["delivery_state"] == "completed":
        return str(finished["result"])
    error = finished.get("error") or {}
    return f"Error executing research query: {error.get('message', 'Research interrupted')}"


@wraps(perplexity_research)
async def _perplexity_research_mcp(query: str) -> str:
    """Async MCP adapter; cancellation abandons only this nonblocking waiter."""
    try:
        manager = await asyncio.to_thread(_get_research_manager)
        job = await asyncio.to_thread(manager.start, query)
        while True:
            finished = await asyncio.to_thread(manager.get, job["id"])
            if finished["delivery_state"] not in ACTIVE_STATES:
                return _research_result_text(finished)
            await asyncio.sleep(0.05)
    except Exception as exc:
        logger.error("perplexity_research failed: %s", exc.__class__.__name__)
        return "Error executing research query: Research could not be completed"


@wraps(perplexity_research_start)
async def _perplexity_research_start_mcp(
    query: str, idempotency_key: Optional[str] = None
) -> dict[str, Any]:
    return await asyncio.to_thread(perplexity_research_start, query, idempotency_key)


@wraps(perplexity_research_list)
async def _perplexity_research_list_mcp(
    query: Optional[str] = None,
    status: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> dict[str, Any]:
    return await asyncio.to_thread(perplexity_research_list, query, status, cursor, limit)


@wraps(perplexity_research_get)
async def _perplexity_research_get_mcp(research_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(perplexity_research_get, research_id)


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
    cli = _get_client()
    try:
        resp = cli.search(query, mode="reasoning")
        return _extract_answer(resp)
    except Exception as e:
        logger.error(f"perplexity_reason error: {e}")
        return f"Error executing reasoning query: {e}"


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
    cli = _get_client()
    try:
        resp = cli.search(query, mode="pro", sources=["web"])
        return _extract_answer(resp)
    except Exception as e:
        logger.error(f"perplexity_search error: {e}")
        return f"Error executing search query: {e}"


def _register_tools(
    server: Any,
    authenticated: bool,
    *,
    journal_supported: bool = JOURNAL_SUPPORTED,
) -> None:
    """Register the exact tool set allowed by this server's provider session."""
    server.tool()(perplexity_ask)
    if authenticated and journal_supported:
        server.tool(name="perplexity_research")(_perplexity_research_mcp)
        server.tool(name="perplexity_research_start")(_perplexity_research_start_mcp)
        server.tool(name="perplexity_research_list")(_perplexity_research_list_mcp)
        server.tool(name="perplexity_research_get")(_perplexity_research_get_mcp)
    if authenticated:
        server.tool()(perplexity_reason)
        server.tool()(perplexity_search)


def main():
    global client

    if mcp is None:
        sys.exit(
            "ERROR: the 'mcp' package is required to run the MCP server. "
            "Install it with: pip install 'perplexity-api[mcp]'"
        )

    cookies_env = os.environ.get("PERPLEXITY_COOKIES")
    if cookies_env:
        try:
            cookies = json.loads(cookies_env)
        except json.JSONDecodeError:
            sys.exit("ERROR: PERPLEXITY_COOKIES is not valid JSON.")
    else:
        cookies = {}

    client = Client(cookies)

    _register_tools(mcp, client.own, journal_supported=JOURNAL_SUPPORTED)

    if client.own and JOURNAL_SUPPORTED:
        _get_research_manager(client)
        logger.info("Authenticated — all search and local research journal tools available.")
    elif client.own:
        logger.warning(
            "Authenticated — search and reasoning tools available; %s.",
            JOURNAL_SUPPORT_MESSAGE,
        )
    else:
        logger.warning(
            "No PERPLEXITY_COOKIES set — running anonymously. "
            "Only perplexity_ask is available. "
            "Set PERPLEXITY_COOKIES to enable perplexity_search, "
            "perplexity_reason, and perplexity_research."
        )

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport not in ("stdio", "http"):
        sys.exit("ERROR: MCP_TRANSPORT must be 'stdio' or 'http'")

    try:
        if transport == "stdio":
            mcp.run()
        elif _HTTP_BIND_ON_RUN:
            mcp.run(transport="streamable-http", host=HOST, port=PORT)
        else:
            mcp.run(transport="streamable-http")
    finally:
        _shutdown_research_manager()


if __name__ == "__main__":
    main()
