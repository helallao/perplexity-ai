"""Tests for Perplexity MCP tools and extraction helpers."""

from unittest.mock import MagicMock, patch

from perplexity.mcp import (
    _extract_answer,
    _get_client,
    perplexity_ask,
    perplexity_reason,
    perplexity_research,
    perplexity_search,
)


def test_extract_answer_various_payloads() -> None:
    # None payload
    assert _extract_answer(None) == ""

    # Empty dict
    assert _extract_answer({}) == ""

    # Legacy top-level answer
    assert _extract_answer({"answer": "hello"}) == "hello"

    # Blocks structure with ask_text
    resp = {
        "blocks": [
            {"intended_usage": "status", "text": "thinking"},
            {"intended_usage": "ask_text", "markdown_block": {"answer": "Target Answer"}},
        ]
    }
    assert _extract_answer(resp) == "Target Answer"


def test_mcp_tools_with_mocked_client() -> None:
    with patch("perplexity.mcp._get_client") as mock_get_cli:
        mock_cli = MagicMock()
        mock_get_cli.return_value = mock_cli

        mock_cli.search.return_value = {
            "blocks": [{"intended_usage": "ask_text", "markdown_block": {"answer": "Result"}}]
        }

        assert perplexity_ask("test query") == "Result"
        assert perplexity_research("test query") == "Result"
        assert perplexity_reason("test query") == "Result"
        assert perplexity_search("test query") == "Result"


def test_mcp_tool_handles_exceptions_gracefully() -> None:
    with patch("perplexity.mcp._get_client") as mock_get_cli:
        mock_cli = MagicMock()
        mock_get_cli.return_value = mock_cli
        mock_cli.search.side_effect = RuntimeError("API unavailable")

        result = perplexity_ask("test query")
        assert "Error executing query" in result
