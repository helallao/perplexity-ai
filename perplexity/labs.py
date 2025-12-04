# Importing necessary modules
# ssl: SSL/TLS support for secure connections
# json: JSON parsing and serialization
# time: Time-related functions for delays
# socket: Low-level networking interface
# random: Random number generation
# threading: For running background tasks
# curl_cffi: HTTP requests
# websocket: WebSocket client for real-time communication
import json
import random
import socket
import ssl
import time
from threading import Thread

from curl_cffi import requests
from websocket import WebSocketApp

from .config import DEFAULT_HEADERS, ENDPOINT_SOCKET_IO


class LabsClient:
    """
    A client for interacting with the Perplexity AI Labs API.
    """

    def __init__(self):
        # Initialize HTTP session with default headers
        self.session = requests.Session(headers=DEFAULT_HEADERS.copy())

        # Generate a unique timestamp for session identification
        self.timestamp = format(random.getrandbits(32), "08x")

        # Establish a session with the Perplexity Labs API
        poll_url = (
            f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling&t={self.timestamp}"
        )
        self.sid = json.loads(self.session.get(poll_url).text[1:])["sid"]
        self.last_answer = None  # Store the last response from the API
        self.history = []  # Maintain a history of queries and responses

        # Authenticate the session
        auth_url = (
            f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling"
            f"&t={self.timestamp}&sid={self.sid}"
        )
        assert (
            self.session.post(
                auth_url, data='40{"jwt":"anonymous-ask-user"}'
            ).text
            == "OK"
        )

        # Set up a secure WebSocket connection
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        self.sock = context.wrap_socket(
            socket.create_connection(("www.perplexity.ai", 443)),
            server_hostname="www.perplexity.ai",
        )

        # Initialize WebSocket client
        websocket_url = (
            "wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket"
            f"&sid={self.sid}"
        )
        self.ws = WebSocketApp(
            url=websocket_url,
            header={"User-Agent": self.session.headers["User-Agent"]},
            cookie="; ".join(
                [
                    f"{key}={value}"
                    for key, value in self.session.cookies.get_dict().items()
                ]
            ),
            on_open=lambda ws: (ws.send("2probe"), ws.send("5")),
            on_message=self._on_message,
            on_error=lambda ws, error: print(f"Websocket Error: {error}"),
            socket=self.sock,
        )

        # Run the WebSocket client in a separate thread
        Thread(target=self.ws.run_forever, daemon=True).start()

        # Wait until the WebSocket connection is established
        while not (self.ws.sock and self.ws.sock.connected):
            time.sleep(0.01)

    def _on_message(self, ws, message):
        """
        WebSocket message handler.
        """
        if message == "2":
            ws.send("3")  # Respond to ping messages

        if message.startswith("42"):
            response = json.loads(message[2:])[1]

            if "final" in response:
                self.last_answer = response

    def ask(self, query, model="r1-1776", stream=False):
        """
        Sends a query to the Perplexity Labs API.

        Parameters:
        - query: The query string.
        - model: The model to use for the query.
        - stream: Whether to stream the response.

        Returns:
        - The final response or a generator for streaming responses.
        """
        assert model in [
            "r1-1776",
            "sonar-pro",
            "sonar",
            "sonar-reasoning-pro",
            "sonar-reasoning",
        ], "Invalid model."

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

        def stream_response():
            """
            Generator for streaming responses.
            """
            answer = None

            while True:
                if self.last_answer != answer:
                    answer = self.last_answer
                    yield answer

                if self.last_answer and self.last_answer.get("final"):
                    answer = self.last_answer
                    self.last_answer = None
                    self.history.append(
                        {
                            "role": "assistant",
                            "content": answer["output"],
                            "priority": 0,
                        }
                    )

                    return

                time.sleep(0.01)

        if stream:
            return stream_response()

        while True:
            if self.last_answer and self.last_answer.get("final"):
                answer = self.last_answer
                self.last_answer = None
                self.history.append(
                    {
                        "role": "assistant",
                        "content": answer["output"],
                        "priority": 0,
                    }
                )

                return answer

            time.sleep(0.01)
