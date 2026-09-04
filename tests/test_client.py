"""Tests for Client and AsyncClient classes."""

import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from perplexity.client import Client
from perplexity.config import DEFAULT_HEADERS, SSE_ASK_HEADERS
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


def test_client_init_custom_headers_and_proxy() -> None:
    with patch("perplexity.client.requests.Session") as mock_session_cls:
        mock_session_cls.return_value.get.return_value = MagicMock(ok=True)

        Client(
            headers={"X-Corporate-Auth": "test-token", "User-Agent": "custom-agent"},
            proxy="http://127.0.0.1:8080",
        )

        kwargs = mock_session_cls.call_args.kwargs
        assert kwargs["headers"]["accept"] == DEFAULT_HEADERS["accept"]
        assert kwargs["headers"]["x-corporate-auth"] == "test-token"
        assert kwargs["headers"]["user-agent"] == "custom-agent"
        assert kwargs["proxies"] == {
            "http": "http://127.0.0.1:8080",
            "https": "http://127.0.0.1:8080",
        }


@pytest.mark.asyncio
async def test_async_client_init_custom_headers_and_proxy() -> None:
    with patch("perplexity_async.client.requests.AsyncSession") as mock_session_cls:
        session = MagicMock()
        session.get = AsyncMock(return_value=MagicMock(ok=True))
        mock_session_cls.return_value = session

        await AsyncClient(
            headers={"X-Corporate-Auth": "test-token"},
            proxy="socks5://127.0.0.1:1080",
        )

        kwargs = mock_session_cls.call_args.kwargs
        assert kwargs["headers"]["accept"] == DEFAULT_HEADERS["accept"]
        assert kwargs["headers"]["x-corporate-auth"] == "test-token"
        assert kwargs["proxies"] == {
            "http": "socks5://127.0.0.1:1080",
            "https": "socks5://127.0.0.1:1080",
        }


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


def test_client_search_uses_sse_headers() -> None:
    """search() must pass SSE_ASK_HEADERS to the perplexity_ask POST so the
    request looks like a browser fetch() call rather than a page navigation,
    which is the primary cause of Perplexity blocking the request (issue #70)."""
    with patch("curl_cffi.requests.Session.get") as mock_get, patch(
        "curl_cffi.requests.Session.post"
    ) as mock_post:
        mock_get.return_value = MagicMock(ok=True)

        final_data = json.dumps({"answer": "test", "chunks": []})
        nested_text = json.dumps([{"step_type": "FINAL", "content": {"answer": final_data}}])
        mock_response_data = {
            "text": nested_text,
            "blocks": [{"intended_usage": "ask_text", "markdown_block": {"answer": "test"}}],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            f"data: {json.dumps(mock_response_data)}".encode("utf-8"),
            b"event: end_of_stream",
        ]
        mock_post.return_value = mock_resp

        cli = Client(
            headers={"X-Corporate-Auth": "test-token", "User-Agent": "custom-agent"}
        )
        cli.search("hello")

        # The last POST call (to ENDPOINT_SSE_ASK) must carry SSE_ASK_HEADERS.
        sse_call_kwargs = mock_post.call_args_list[-1][1]
        expected_headers = SSE_ASK_HEADERS.copy()
        expected_headers.update(
            {"x-corporate-auth": "test-token", "user-agent": "custom-agent"}
        )
        assert sse_call_kwargs.get("headers") == expected_headers, (
            "search() did not pass SSE_ASK_HEADERS to the perplexity_ask POST; "
            "stale sec-fetch-mode/dest values will be rejected by Perplexity's anti-bot layer"
        )
