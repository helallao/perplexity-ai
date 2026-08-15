"""Tests for Emailnator and async Emailnator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from perplexity.emailnator import Emailnator
from perplexity.exceptions import EmailnatorError
from perplexity_async.emailnator import Emailnator as AsyncEmailnator


def test_emailnator_lifecycle() -> None:
    with patch("perplexity.emailnator.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # Mock email generation
        gen_resp = MagicMock(ok=True)
        gen_resp.json.return_value = {"email": ["testuser@gmail.com"]}

        # Mock initial ads list
        ads_resp = MagicMock(ok=True)
        ads_resp.json.return_value = {"messageData": [{"messageID": "ad1"}]}

        mock_session.post.side_effect = [gen_resp, ads_resp]

        email_cli = Emailnator(cookies={"XSRF-TOKEN": "test_token"})
        assert email_cli.email == "testuser@gmail.com"
        assert "ad1" in email_cli.inbox_ads

        # Mock reload message fetching
        msg_resp = MagicMock(ok=True)
        msg_resp.json.return_value = {
            "messageData": [
                {"messageID": "ad1", "subject": "Ad"},
                {"messageID": "msg1", "subject": "Sign in to Perplexity"},
            ]
        }
        mock_session.post.side_effect = None
        mock_session.post.return_value = msg_resp

        new_msgs = email_cli.reload(wait_for=lambda x: x.get("subject") == "Sign in to Perplexity", timeout=1.0)
        assert len(new_msgs) == 1
        assert new_msgs[0]["messageID"] == "msg1"

        matched = email_cli.get(func=lambda x: x.get("subject") == "Sign in to Perplexity")
        assert matched is not None
        assert matched["messageID"] == "msg1"

        email_cli.close()


@pytest.mark.asyncio
async def test_async_emailnator_lifecycle() -> None:
    with patch("perplexity_async.emailnator.requests.AsyncSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        gen_resp = MagicMock(ok=True)
        gen_resp.json.return_value = {"email": ["testuser_async@gmail.com"]}

        ads_resp = MagicMock(ok=True)
        ads_resp.json.return_value = {"messageData": [{"messageID": "ad1"}]}

        mock_session.post = AsyncMock(side_effect=[gen_resp, ads_resp])
        mock_session.close = AsyncMock()

        email_cli = await AsyncEmailnator(cookies={"XSRF-TOKEN": "test_token"})
        assert email_cli.email == "testuser_async@gmail.com"

        msg_resp = MagicMock(ok=True)
        msg_resp.json.return_value = {
            "messageData": [
                {"messageID": "msg2", "subject": "Sign in to Perplexity"},
            ]
        }
        mock_session.post = AsyncMock(return_value=msg_resp)

        new_msgs = await email_cli.reload(
            wait_for=lambda x: x.get("subject") == "Sign in to Perplexity",
            timeout=1.0,
        )
        assert len(new_msgs) == 1
        assert new_msgs[0]["messageID"] == "msg2"

        await email_cli.close()
