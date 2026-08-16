import asyncio
import json
import random
import socket
import ssl
import time
from threading import Thread
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from curl_cffi import requests
from websocket import WebSocketApp, WebSocketException

from perplexity.config import DEFAULT_HEADERS, ENDPOINT_SOCKET_IO, LABS_MODELS
from perplexity.exceptions import AuthenticationError, NetworkError, ValidationError
from perplexity.logger import get_logger

logger = get_logger("async_labs")


class AsyncMixin:
    def __init__(self, *args, **kwargs):
        self.__storedargs = args, kwargs
        self.async_initialized = False

    async def __ainit__(self, *args, **kwargs):
        pass

    async def __initobj(self):
        assert not self.async_initialized
        self.async_initialized = True
        # pass the parameters to __ainit__ that passed to __init__
        await self.__ainit__(*self.__storedargs[0], **self.__storedargs[1])
        return self

    def __await__(self):
        return self.__initobj().__await__()


class LabsClient(AsyncMixin):
    """
    A client for interacting with the Perplexity AI Labs API asynchronously.
    """

    async def __ainit__(self, connect_timeout: float = 15.0):
        try:
            self.session = requests.AsyncSession(
                headers=DEFAULT_HEADERS.copy(),
                impersonate="chrome",
            )
            self.timestamp = format(random.getrandbits(32), "08x")
            poll_url = f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling&t={self.timestamp}"
            response = await self.session.get(poll_url)
            response.raise_for_status()
            self.sid = json.loads(response.text[1:])["sid"]
            self.last_answer: Optional[Dict[str, Any]] = None
            self.history: List[Dict[str, Any]] = []

            auth_url = (
                f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling"
                f"&t={self.timestamp}&sid={self.sid}"
            )
            post_response = await self.session.post(auth_url, data='40{"jwt":"anonymous-ask-user"}')
            post_response.raise_for_status()
            if post_response.text != "OK":
                raise AuthenticationError(f"Labs authentication failed: {post_response.text}")

            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            self.sock = context.wrap_socket(
                socket.create_connection(("www.perplexity.ai", 443)),
                server_hostname="www.perplexity.ai",
            )

            websocket_url = (
                "wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket" f"&sid={self.sid}"
            )
            cookies_string = "; ".join(
                f"{key}={value}" for key, value in self.session.cookies.get_dict().items()
            )
            self.ws = WebSocketApp(
                url=websocket_url,
                header={"User-Agent": self.session.headers.get("User-Agent", "")},
                cookie=cookies_string,
                on_open=lambda ws: (ws.send("2probe"), ws.send("5")),
                on_message=self._on_message,
                on_error=self._on_error,
                socket=self.sock,
            )

            Thread(target=self.ws.run_forever, daemon=True).start()

            start_time = time.time()
            while not (self.ws.sock and self.ws.sock.connected):
                if time.time() - start_time > connect_timeout:
                    raise NetworkError("WebSocket connection to Perplexity Labs timed out")
                await asyncio.sleep(0.01)
        except (AuthenticationError, NetworkError):
            raise
        except (
            requests.RequestException,
            WebSocketException,
            socket.error,
            ssl.SSLError,
        ) as e:
            raise NetworkError(f"Initialization error in LabsClient: {e}") from e
        except Exception as e:
            raise NetworkError(f"Unexpected error during LabsClient initialization: {e}") from e

    def _on_message(self, ws, message: str) -> None:
        """
        Websocket message handler
        """
        try:
            if message == "2":
                ws.send("3")

            elif message.startswith("42"):
                response = json.loads(message[2:])[1]

                if isinstance(response, dict) and "final" in response:
                    self.last_answer = response
        except Exception as e:
            logger.debug(f"Error in async Labs WebSocket message handler: {e}")

    def _on_error(self, ws, error) -> None:
        """
        Websocket error handler
        """
        logger.error(f"WebSocket Error: {error}")

    async def ask(
        self,
        query: str,
        model: str = "r1-1776",
        stream: bool = False,
        timeout: float = 60.0,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        Query function asynchronously.

        Parameters:
        - query: The query string.
        - model: The model to use for the query.
        - stream: Whether to stream the response.
        - timeout: Maximum time in seconds to wait for response.

        Returns:
        - The final response dict or an async generator for streaming responses.
        """
        if model not in LABS_MODELS:
            raise ValidationError(
                f"Invalid model '{model}'. Must be one of: {', '.join(LABS_MODELS)}"
            )

        self.last_answer = None
        self.history.append({"role": "user", "content": query})

        self.ws.send(
            "42"
            + json.dumps(
                [
                    "perplexity_labs",
                    {
                        "messages": self.history,
                        "model": model,
                        "source": "default",
                        "version": "2.18",
                    },
                ]
            )
        )

        async def stream_response() -> AsyncGenerator[Dict[str, Any], None]:
            answer = None
            start_wait = time.time()

            while True:
                if time.time() - start_wait > timeout:
                    raise TimeoutError("Perplexity Labs query timed out waiting for response")

                if self.last_answer != answer:
                    answer = self.last_answer
                    start_wait = time.time()
                    if answer is not None:
                        yield answer

                if self.last_answer and self.last_answer.get("final"):
                    answer = self.last_answer
                    self.last_answer = None
                    self.history.append(
                        {
                            "role": "assistant",
                            "content": answer.get("output", ""),
                            "priority": 0,
                        }
                    )
                    return

                await asyncio.sleep(0.01)

        if stream:
            return stream_response()

        start_wait = time.time()
        while True:
            if time.time() - start_wait > timeout:
                raise TimeoutError("Perplexity Labs query timed out waiting for final answer")

            if self.last_answer and self.last_answer.get("final"):
                answer = self.last_answer
                self.last_answer = None
                self.history.append(
                    {
                        "role": "assistant",
                        "content": answer.get("output", ""),
                        "priority": 0,
                    }
                )

                return answer

            await asyncio.sleep(0.01)

    async def close(self) -> None:
        """Close the WebSocket connection and HTTP session."""
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        try:
            if self.session:
                await self.session.close()
        except Exception:
            pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
