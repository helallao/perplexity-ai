"""Tests for LabsClient and async LabsClient."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from perplexity.config import LABS_MODELS
from perplexity.exceptions import ValidationError
from perplexity.labs import LabsClient
from perplexity_async.labs import LabsClient as AsyncLabsClient


def test_labs_models_validation() -> None:
    mock_ws = MagicMock()
    mock_ws.sock = MagicMock()
    mock_ws.sock.connected = True

    with patch("perplexity.labs.requests.Session") as mock_session_cls, patch(
        "perplexity.labs.socket.create_connection"
    ), patch("perplexity.labs.ssl.create_default_context"), patch(
        "perplexity.labs.Thread"
    ), patch("perplexity.labs.WebSocketApp", return_value=mock_ws):

        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock(text='0{"sid":"test_sid"}')
        mock_session.post.return_value = MagicMock(text="OK")
        mock_session.headers = {"User-Agent": "test"}
        mock_session.cookies.get_dict.return_value = {}
        mock_session_cls.return_value = mock_session

        client = LabsClient()

        def fake_send(msg):
            client.last_answer = {"final": True, "output": "Labs response"}

        mock_ws.send.side_effect = fake_send

        # Valid model should succeed and return answer
        resp = client.ask("What is AI?", model="r1-1776", timeout=1.0)
        assert isinstance(resp, dict)
        assert resp.get("output") == "Labs response"

        # Invalid model must raise ValidationError
        with pytest.raises(ValidationError, match="Invalid model"):
            client.ask("What is AI?", model="invalid-model-name")

        client.close()


@pytest.mark.asyncio
async def test_async_labs_models_validation() -> None:
    mock_ws = MagicMock()
    mock_ws.sock = MagicMock()
    mock_ws.sock.connected = True

    with patch("perplexity_async.labs.requests.AsyncSession") as mock_session_cls, patch(
        "perplexity_async.labs.socket.create_connection"
    ), patch("perplexity_async.labs.ssl.create_default_context"), patch(
        "perplexity_async.labs.Thread"
    ), patch("perplexity_async.labs.WebSocketApp", return_value=mock_ws):

        mock_session = MagicMock()
        mock_get_resp = MagicMock(text='0{"sid":"test_sid"}')
        mock_get_resp.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_get_resp)

        mock_post_resp = MagicMock(text="OK")
        mock_post_resp.raise_for_status = MagicMock()
        mock_session.post = AsyncMock(return_value=mock_post_resp)
        mock_session.close = AsyncMock()

        mock_session.headers = {"User-Agent": "test"}
        mock_session.cookies.get_dict.return_value = {}
        mock_session_cls.return_value = mock_session

        client = await AsyncLabsClient()

        def fake_send(msg):
            client.last_answer = {"final": True, "output": "Async Labs response"}

        mock_ws.send.side_effect = fake_send

        resp = await client.ask("Test query", model="sonar-pro", timeout=1.0)
        assert isinstance(resp, dict)
        assert resp.get("output") == "Async Labs response"

        with pytest.raises(ValidationError, match="Invalid model"):
            await client.ask("Test query", model="unsupported-model")

        await client.close()
