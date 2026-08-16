import json
import random
import socket
import ssl
import time
from threading import Thread
from typing import Any, Dict, Generator, List, Optional, Union

from curl_cffi import requests
from websocket import WebSocketApp

from .config import DEFAULT_HEADERS, ENDPOINT_SOCKET_IO, LABS_MODELS
from .exceptions import AuthenticationError, NetworkError, ValidationError
from .logger import get_logger

logger = get_logger("labs")


class LabsClient:
    """
    A client for interacting with the Perplexity AI Labs API.
    """

    def __init__(self, connect_timeout: float = 15.0):
        # Initialize HTTP session with default headers
        self.session = requests.Session(headers=DEFAULT_HEADERS.copy(), impersonate="chrome")

        # Generate a unique timestamp for session identification
        self.timestamp = format(random.getrandbits(32), "08x")

        # Establish a session with the Perplexity Labs API
        poll_url = f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling&t={self.timestamp}"
        try:
            resp = self.session.get(poll_url)
            self.sid = json.loads(resp.text[1:])["sid"]
        except Exception as e:
            raise NetworkError(f"Failed to establish Labs polling session: {e}") from e

        self.last_answer: Optional[Dict[str, Any]] = None  # Store the last response from the API
        self.history: List[Dict[str, Any]] = []  # Maintain a history of queries and responses

        # Authenticate the session
        auth_url = (
            f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling" f"&t={self.timestamp}&sid={self.sid}"
        )
        auth_resp = self.session.post(auth_url, data='40{"jwt":"anonymous-ask-user"}')
        if auth_resp.text != "OK":
            raise AuthenticationError(f"Labs authentication failed: {auth_resp.text}")

        # Set up a secure WebSocket connection
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        self.sock = context.wrap_socket(
            socket.create_connection(("www.perplexity.ai", 443)),
            server_hostname="www.perplexity.ai",
        )

        # Initialize WebSocket client
        websocket_url = (
            "wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket" f"&sid={self.sid}"
        )
        self.ws = WebSocketApp(
            url=websocket_url,
            header={"User-Agent": self.session.headers.get("User-Agent", "")},
            cookie="; ".join(
                [f"{key}={value}" for key, value in self.session.cookies.get_dict().items()]
            ),
            on_open=lambda ws: (ws.send("2probe"), ws.send("5")),
            on_message=self._on_message,
            on_error=lambda ws, error: logger.error(f"WebSocket error: {error}"),
            socket=self.sock,
        )

        # Run the WebSocket client in a separate thread
        Thread(target=self.ws.run_forever, daemon=True).start()

        # Wait until the WebSocket connection is established
        start_time = time.time()
        while not (self.ws.sock and self.ws.sock.connected):
            if time.time() - start_time > connect_timeout:
                raise NetworkError("WebSocket connection to Perplexity Labs timed out")
            time.sleep(0.01)

    def _on_message(self, ws, message: str) -> None:
        """
        WebSocket message handler.
        """
        try:
            if message == "2":
                ws.send("3")  # Respond to ping messages

            elif message.startswith("42"):
                response = json.loads(message[2:])[1]

                if isinstance(response, dict) and "final" in response:
                    self.last_answer = response
        except Exception as e:
            logger.debug(f"Error handling WebSocket message: {e}")

    def ask(
        self,
        query: str,
        model: str = "r1-1776",
        stream: bool = False,
        timeout: float = 60.0,
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Sends a query to the Perplexity Labs API.

        Parameters:
        - query: The query string.
        - model: The model to use for the query.
        - stream: Whether to stream the response.
        - timeout: Maximum time in seconds to wait for response.

        Returns:
        - The final response dict or a generator for streaming responses.
        """
        if model not in LABS_MODELS:
            raise ValidationError(
                f"Invalid model '{model}'. Must be one of: {', '.join(LABS_MODELS)}"
            )

        self.last_answer = None
        self.history.append({"role": "user", "content": query})

        # Send the query via WebSocket
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

        def stream_response() -> Generator[Dict[str, Any], None, None]:
            """
            Generator for streaming responses.
            """
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

                time.sleep(0.01)

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

            time.sleep(0.01)

    def close(self) -> None:
        """Close the WebSocket connection and HTTP session."""
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
