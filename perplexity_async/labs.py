import asyncio
import json
import random
import socket
import ssl
from threading import Thread

from curl_cffi import requests
from websocket import WebSocketApp, WebSocketException

from perplexity.config import DEFAULT_HEADERS, ENDPOINT_SOCKET_IO


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
    A client for interacting with the Perplexity AI Labs API.
    """

    async def __ainit__(self):
        try:
            self.session = requests.AsyncSession(
                headers=DEFAULT_HEADERS.copy(),
                impersonate="chrome",
            )
            self.timestamp = format(random.getrandbits(32), "08x")
            poll_url = (
                f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling&"
                f"t={self.timestamp}"
            )
            response = await self.session.get(poll_url)
            response.raise_for_status()
            self.sid = json.loads(response.text[1:])["sid"]
            self.last_answer = None
            self.history = []

            auth_url = (
                f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling"
                f"&t={self.timestamp}&sid={self.sid}"
            )
            post_response = await self.session.post(
                auth_url, data='40{"jwt":"anonymous-ask-user"}'
            )
            post_response.raise_for_status()
            assert post_response.text == "OK"

            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            self.sock = context.wrap_socket(
                socket.create_connection(("www.perplexity.ai", 443)),
                server_hostname="www.perplexity.ai",
            )

            websocket_url = (
                "wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket"
                f"&sid={self.sid}"
            )
            cookies_string = "; ".join(
                f"{key}={value}"
                for key, value in self.session.cookies.get_dict().items()
            )
            self.ws = WebSocketApp(
                url=websocket_url,
                header={"User-Agent": self.session.headers["User-Agent"]},
                cookie=cookies_string,
                on_open=lambda ws: (ws.send("2probe"), ws.send("5")),
                on_message=self._on_message,
                on_error=self._on_error,
                socket=self.sock,
            )

            Thread(target=self.ws.run_forever, daemon=True).start()

            while not (self.ws.sock and self.ws.sock.connected):
                await asyncio.sleep(0.01)
        except (
            requests.RequestException,
            WebSocketException,
            socket.error,
            ssl.SSLError,
        ) as e:
            print(f"Initialization error: {e}")
        except Exception as e:
            print(f"Unexpected error during initialization: {e}")

    def _on_message(self, ws, message):
        """
        Websocket message handler
        """
        try:
            if message == "2":
                ws.send("3")

            if message.startswith("42"):
                response = json.loads(message[2:])[1]

                if "final" in response:
                    self.last_answer = response
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
        except Exception as e:
            print(f"Unexpected error in message handler: {e}")

    def _on_error(self, ws, error):
        """
        Websocket error handler
        """
        print(f"Websocket Error: {error}")

    async def ask(self, query, model="r1-1776", stream=False):
        """
        Query function
        """
        try:
            assert model in [
                "r1-1776",
                "sonar-pro",
                "sonar",
                "sonar-reasoning-pro",
                "sonar-reasoning",
            ], "Invalid labs model"

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

            async def stream_response(self):
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

                    await asyncio.sleep(0.01)

            while True:
                if self.last_answer and stream:
                    return stream_response(self)

                elif self.last_answer and self.last_answer.get("final"):
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

                await asyncio.sleep(0.01)
        except AssertionError as e:
            print(f"Assertion error: {e}")
        except WebSocketException as e:
            print(f"WebSocket error: {e}")
        except Exception as e:
            print(f"Unexpected error in ask method: {e}")
