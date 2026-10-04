"""Tests for Perplexity MCP tools and extraction helpers."""

import pytest

pytest.importorskip("mcp")

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
    with (
        patch("perplexity.mcp._get_client") as mock_get_cli,
        patch("perplexity.mcp._get_research_manager") as mock_get_manager,
    ):
        mock_cli = MagicMock()
        mock_get_cli.return_value = mock_cli
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        mock_manager.start.return_value = {"id": "local-id"}
        mock_manager.wait.return_value = {
            "delivery_state": "completed",
            "result": "Result",
        }

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


def test_blocking_research_fails_closed_when_journal_initialization_fails() -> None:
    with (
        patch("perplexity.mcp._get_research_manager", side_effect=RuntimeError("store failed")),
        patch("perplexity.mcp._get_client") as mock_get_client,
    ):
        result = perplexity_research("do not duplicate")

    assert result == "Error executing research query: Research could not be completed"
    mock_get_client.assert_not_called()
