"""Tests for perplexity_async.labs.LabsClient."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from perplexity.exceptions import AuthenticationError, NetworkError, ValidationError
from perplexity_async.labs import LabsClient as AsyncLabsClient


@pytest.fixture
def mock_ws() -> MagicMock:
    """Fixture providing a mock WebSocketApp with connected socket."""
    ws = MagicMock()
    ws.sock = MagicMock()
    ws.sock.connected = True
    return ws


@pytest.fixture
def mock_labs_env(mock_ws: MagicMock):
    """Fixture configuring mocked environment for LabsClient initialization."""
    with (
        patch("perplexity_async.labs.requests.AsyncSession") as mock_session_cls,
        patch("perplexity_async.labs.socket.create_connection"),
        patch("perplexity_async.labs.ssl.create_default_context"),
        patch("perplexity_async.labs.Thread"),
        patch("perplexity_async.labs.WebSocketApp", return_value=mock_ws),
    ):
        mock_session = MagicMock()
        mock_get_resp = MagicMock(text='0{"sid":"test_sid_123"}')
        mock_get_resp.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_get_resp)

        mock_post_resp = MagicMock(text="OK")
        mock_post_resp.raise_for_status = MagicMock()
        mock_session.post = AsyncMock(return_value=mock_post_resp)
        mock_session.close = AsyncMock()

        mock_session.headers = {"User-Agent": "test-agent"}
        mock_session.cookies.get_dict.return_value = {"cookie_key": "cookie_val"}
        mock_session_cls.return_value = mock_session

        yield {
            "session": mock_session,
            "session_cls": mock_session_cls,
            "ws": mock_ws,
        }


@pytest.mark.asyncio
async def test_async_labs_init_success(mock_labs_env: dict) -> None:
    """Verify successful Socket.IO handshake and WebSocket initialization."""
    client = await AsyncLabsClient()

    assert client.sid == "test_sid_123"
    assert client.last_answer is None
    assert client.history == []
    mock_labs_env["session"].get.assert_awaited_once()
    mock_labs_env["session"].post.assert_awaited_once()
    await client.close()


@pytest.mark.asyncio
async def test_async_labs_init_auth_failure(mock_labs_env: dict) -> None:
    """Raise AuthenticationError when auth POST response does not return OK."""
    fail_post = MagicMock(text="Unauthorized", raise_for_status=MagicMock())
    mock_labs_env["session"].post.return_value = fail_post

    with pytest.raises(AuthenticationError, match="Labs authentication failed: Unauthorized"):
        await AsyncLabsClient()


@pytest.mark.asyncio
async def test_async_labs_init_socket_timeout(mock_labs_env: dict) -> None:
    """Raise NetworkError when websocket connection times out."""
    mock_labs_env["ws"].sock.connected = False

    with pytest.raises(NetworkError, match="WebSocket connection to Perplexity Labs timed out"):
        await AsyncLabsClient(connect_timeout=0.01)


def test_async_labs_on_message_ping_pong() -> None:
    """Respond with '3' (pong) when '2' (ping) message frame is received."""
    mock_client = MagicMock(spec=AsyncLabsClient)
    mock_ws = MagicMock()
    AsyncLabsClient._on_message(mock_client, mock_ws, "2")
    mock_ws.send.assert_called_once_with("3")


def test_async_labs_on_message_final_response() -> None:
    """Parse '42' message frame and update last_answer when final is True."""
    mock_client = MagicMock(spec=AsyncLabsClient)
    mock_client.last_answer = None

    payload = json.dumps(["perplexity_labs", {"final": True, "output": "Parsed response"}])
    AsyncLabsClient._on_message(mock_client, MagicMock(), f"42{payload}")

    assert mock_client.last_answer == {"final": True, "output": "Parsed response"}


def test_async_labs_on_error_logging() -> None:
    """Handle error callback without raising unhandled exception."""
    mock_client = MagicMock(spec=AsyncLabsClient)
    AsyncLabsClient._on_error(mock_client, MagicMock(), Exception("WS connection dropped"))


@pytest.mark.asyncio
async def test_async_labs_ask_model_validation(mock_labs_env: dict) -> None:
    """Raise ValidationError when unsupported model is requested."""
    client = await AsyncLabsClient()

    with pytest.raises(ValidationError, match="Invalid model 'unsupported-model'"):
        await client.ask("Hello", model="unsupported-model", timeout=0.01)

    await client.close()


@pytest.mark.asyncio
async def test_async_labs_ask_success_non_streaming(mock_labs_env: dict) -> None:
    """Send formatted query and return final answer dict while recording history."""
    client = await AsyncLabsClient()

    def fake_send(msg: str) -> None:
        if msg.startswith("42"):
            client.last_answer = {"final": True, "output": "Labs answer output"}

    mock_labs_env["ws"].send.side_effect = fake_send

    response = await client.ask("What is AI?", model="r1-1776")

    assert response == {"final": True, "output": "Labs answer output"}
    assert len(client.history) == 2
    assert client.history[0] == {"role": "user", "content": "What is AI?"}
    assert client.history[1] == {
        "role": "assistant",
        "content": "Labs answer output",
        "priority": 0,
    }
    await client.close()


@pytest.mark.asyncio
async def test_async_labs_ask_success_streaming(mock_labs_env: dict) -> None:
    """Stream answers yielding items until final answer is processed."""
    client = await AsyncLabsClient()

    def fake_send(msg: str) -> None:
        if msg.startswith("42"):
            client.last_answer = {"final": True, "output": "Streamed final output"}

    mock_labs_env["ws"].send.side_effect = fake_send

    stream = await client.ask("Stream query", model="sonar-pro", stream=True)
    results = [item async for item in stream]

    assert len(results) == 1
    assert results[0] == {"final": True, "output": "Streamed final output"}
    assert len(client.history) == 2
    await client.close()


@pytest.mark.asyncio
async def test_async_labs_ask_timeout(mock_labs_env: dict) -> None:
    """Raise TimeoutError when query response exceeds specified timeout."""
    client = await AsyncLabsClient()
    mock_labs_env["ws"].send.side_effect = None

    with pytest.raises(TimeoutError, match="timed out waiting for final answer"):
        await client.ask("Timeout query", timeout=0.01)

    with pytest.raises(TimeoutError, match="timed out waiting for response"):
        stream = await client.ask("Timeout stream", stream=True, timeout=0.01)
        _ = [item async for item in stream]

    await client.close()


@pytest.mark.asyncio
async def test_async_labs_context_manager_close(mock_labs_env: dict) -> None:
    """Ensure async context manager invokes close on session and websocket."""
    client = await AsyncLabsClient()
    async with client:
        assert client.sid == "test_sid_123"

    mock_labs_env["ws"].close.assert_called_once()
    mock_labs_env["session"].close.assert_awaited_once()
