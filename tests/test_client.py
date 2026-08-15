"""Tests for Client and AsyncClient classes."""

import json
from unittest.mock import MagicMock, patch

import pytest

from perplexity.client import Client
from perplexity.exceptions import (
    AuthenticationError,
    FileUploadError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from perplexity_async.client import Client as AsyncClient


def test_client_init_defaults() -> None:
    with patch("curl_cffi.requests.Session.get") as mock_get:
        mock_get.return_value = MagicMock(ok=True)
        cli = Client()
        assert not cli.own
        assert cli.copilot == 0
        assert cli.file_upload == 0

        cli_auth = Client(cookies={"session": "test"})
        assert cli_auth.own
        assert cli_auth.copilot == float("inf")
        assert cli_auth.file_upload == float("inf")


def test_client_search_validation() -> None:
    with patch("curl_cffi.requests.Session.get") as mock_get:
        mock_get.return_value = MagicMock(ok=True)
        cli = Client()

        with pytest.raises(ValidationError, match="Invalid mode"):
            cli.search("test", mode="non_existent")

        with pytest.raises(ValidationError, match="requires an account"):
            cli.search("test", mode="pro", model="sonar")

        with pytest.raises(ValidationError, match="No remaining enhanced queries"):
            cli.search("test", mode="pro")


def test_client_search_success_mock() -> None:
    with patch("curl_cffi.requests.Session.get") as mock_get, patch(
        "curl_cffi.requests.Session.post"
    ) as mock_post:
        mock_get.return_value = MagicMock(ok=True)

        final_data = json.dumps({"answer": "Python is a language", "chunks": []})
        nested_text = json.dumps([
            {"step_type": "FINAL", "content": {"answer": final_data}}
        ])
        mock_response_data = {
            "text": nested_text,
            "blocks": [{"intended_usage": "ask_text", "markdown_block": {"answer": "Python is a language"}}]
        }

        sse_chunk = f"data: {json.dumps(mock_response_data)}\r\n\r\nevent: end_of_stream\r\n\r\n".encode("utf-8")
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            f"data: {json.dumps(mock_response_data)}".encode("utf-8"),
            b"event: end_of_stream",
        ]
        mock_post.return_value = mock_resp

        cli = Client()
        result = cli.search("What is Python?", mode="auto")
        assert isinstance(result, dict)
        assert result.get("answer") == "Python is a language"


def test_client_search_http_errors() -> None:
    with patch("curl_cffi.requests.Session.get") as mock_get, patch(
        "curl_cffi.requests.Session.post"
    ) as mock_post:
        mock_get.return_value = MagicMock(ok=True)

        cli = Client()

        # Test 429 RateLimitError
        mock_429 = MagicMock(status_code=429)
        mock_post.return_value = mock_429
        with pytest.raises(RateLimitError):
            cli.search("test")

        # Test 403 AuthenticationError
        mock_403 = MagicMock(status_code=403)
        mock_post.return_value = mock_403
        with pytest.raises(AuthenticationError):
            cli.search("test")

        # Test 500 NetworkError
        mock_500 = MagicMock(status_code=500)
        mock_post.return_value = mock_500
        with pytest.raises(NetworkError):
            cli.search("test")
