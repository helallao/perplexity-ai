"""
Test CLI functionality.

This test verifies that the CLI module can be imported and basic commands work.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from perplexity.cli import app

runner = CliRunner()


def test_cli_help():
    """Test that CLI help command works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Perplexity AI" in result.stdout
    assert "search" in result.stdout
    assert "create-account" in result.stdout
    assert "info" in result.stdout


def test_search_help():
    """Test that search command help works."""
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0
    assert "Search using Perplexity AI" in result.stdout
    # Check for mode and source options (accounting for potential ANSI codes)
    assert "mode" in result.stdout
    assert "source" in result.stdout


def test_info_command():
    """Test that info command works."""
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Search Modes" in result.stdout
    assert "auto" in result.stdout
    assert "pro" in result.stdout
    assert "reasoning" in result.stdout


def test_create_account_help():
    """Test that create-account command help works."""
    result = runner.invoke(app, ["create-account", "--help"])
    assert result.exit_code == 0
    assert "Create a new Perplexity account" in result.stdout
    assert "emailnator" in result.stdout.lower()


@patch("perplexity.cli.Client")
def test_search_basic(mock_client_class):
    """Test basic search command with mocked client."""
    # Mock the client
    mock_client = MagicMock()
    mock_client.search.return_value = {"answer": "Test answer"}
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["search", "test query"])

    # Should successfully invoke search
    assert result.exit_code == 0
    assert "Test answer" in result.stdout
    mock_client.search.assert_called_once()


@patch("perplexity.cli.Client")
def test_search_with_mode(mock_client_class):
    """Test search command with mode option."""
    mock_client = MagicMock()
    mock_client.search.return_value = {"answer": "Pro answer"}
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["search", "test query", "--mode", "pro"])

    assert result.exit_code == 0
    assert "Pro answer" in result.stdout
    # Verify mode was passed correctly
    call_kwargs = mock_client.search.call_args[1]
    assert call_kwargs["mode"] == "pro"


@patch("perplexity.cli.Client")
def test_search_with_streaming(mock_client_class):
    """Test search command with streaming enabled."""
    mock_client = MagicMock()
    # Mock streaming response
    mock_client.search.return_value = iter(
        [{"answer": "Part 1 "}, {"answer": "Part 2 "}, {"answer": "Part 3"}]
    )
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["search", "test query", "--stream"])

    assert result.exit_code == 0
    # Check that streaming parts are in output
    assert "Part 1" in result.stdout or "Part 2" in result.stdout or "Part 3" in result.stdout


@patch("perplexity.cli.Client")
def test_search_with_invalid_mode(mock_client_class):
    """Test search command with invalid mode raises error."""
    mock_client = MagicMock()
    # Mock an assertion error for invalid mode
    mock_client.search.side_effect = AssertionError("Invalid search mode.")
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["search", "test query", "--mode", "invalid"])

    assert result.exit_code == 1
    assert "Error" in result.stdout


def test_search_with_cookies_file(tmp_path):
    """Test search command with cookies file."""
    # Create a temporary cookies file
    cookies_file = tmp_path / "cookies.json"
    cookies_data = {"cookie1": "value1", "cookie2": "value2"}
    cookies_file.write_text(json.dumps(cookies_data))

    with patch("perplexity.cli.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "Authenticated answer"}
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["search", "test query", "--cookies", str(cookies_file)])

        assert result.exit_code == 0
        # Verify cookies were passed to client
        mock_client_class.assert_called_once_with(cookies_data)


def test_search_with_missing_cookies_file(tmp_path):
    """Test search command with non-existent cookies file."""
    non_existent_file = tmp_path / "non_existent.json"

    result = runner.invoke(app, ["search", "test query", "--cookies", str(non_existent_file)])

    assert result.exit_code == 1
    assert "Cookies file not found" in result.stdout


def test_search_with_sources():
    """Test search command with multiple sources."""
    with patch("perplexity.cli.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "Scholar answer"}
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app, ["search", "test query", "--source", "web", "--source", "scholar"]
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.search.call_args[1]
        assert "web" in call_kwargs["sources"]
        assert "scholar" in call_kwargs["sources"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
