import json
import mimetypes
import random
import re
import sys
from uuid import uuid4

from curl_cffi import CurlMime, requests

from perplexity.config import (
    DEFAULT_HEADERS,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_AUTH_SIGNIN,
    ENDPOINT_SSE_ASK,
    ENDPOINT_UPLOAD_URL,
)

from .emailnator import Emailnator


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


class Client(AsyncMixin):
    """
    A client for interacting with the Perplexity AI API.
    """

    async def __ainit__(self, cookies={}):
        self.session = requests.AsyncSession(
            headers=DEFAULT_HEADERS.copy(),
            cookies=cookies,
            impersonate="chrome",
        )
        self.own = bool(cookies)
        self.copilot = 0 if not cookies else float("inf")
        self.file_upload = 0 if not cookies else float("inf")
        self.signin_regex = re.compile(
            r'"(https://www\.perplexity\.ai/api/auth/callback/email\?' r'callbackUrl=.*?)"'
        )
        self.timestamp = format(random.getrandbits(32), "08x")
        await self.session.get(ENDPOINT_AUTH_SESSION)

    async def create_account(self, cookies):
        """
        Function to create a new account
        """
        while True:
            try:
                emailnator_cli = await Emailnator(cookies)

                resp = await self.session.post(
                    ENDPOINT_AUTH_SIGNIN,
                    data={
                        "email": emailnator_cli.email,
                        "csrfToken": self.session.cookies.get_dict()["next-auth.csrf-token"].split(
                            "%"
                        )[0],
                        "callbackUrl": "https://www.perplexity.ai/",
                        "json": "true",
                    },
                )

                if resp.ok:
                    new_msgs = await emailnator_cli.reload(
                        wait_for=lambda x: x["subject"] == "Sign in to Perplexity",
                        timeout=20,
                    )

                    if new_msgs:
                        break
                else:
                    print("Perplexity account creating error:", resp)

            except Exception:
                pass

        msg = emailnator_cli.get(func=lambda x: x["subject"] == "Sign in to Perplexity")
        new_account_link = self.signin_regex.search(
            await emailnator_cli.open(msg["messageID"])
        ).group(1)

        await self.session.get(new_account_link)

        self.copilot = 5
        self.file_upload = 10

        return True

    async def search(
        self,
        query,
        mode="auto",
        model=None,
        sources=["web"],
        files={},
        stream=False,
        language="en-US",
        follow_up=None,
        incognito=False,
    ):
        """
        Query function
        """
        assert mode in [
            "auto",
            "pro",
            "reasoning",
            "deep research",
        ], 'Search modes -> ["auto", "pro", "reasoning", "deep research"]'
        assert (
            model
            in {
                "auto": [None],
                "pro": [
                    None,
                    "sonar",
                    "gpt-5.2",
                    "claude-4.5-sonnet",
                    "grok-4.1",
                ],
                "reasoning": [
                    None,
                    "gpt-5.2-thinking",
                    "claude-4.5-sonnet-thinking",
                    "gemini-3.0-pro",
                    "kimi-k2-thinking",
                    "grok-4.1-reasoning",
                ],
                "deep research": [None],
                "copilot": [None, "gemini-3.0-pro", "kimi-k2-thinking"],
            }[mode]
            if self.own
            else True
        ), "Invalid model for selected mode"
        assert all(
            [source in ("web", "scholar", "social") for source in sources]
        ), 'Sources -> ["web", "scholar", "social"]'
        assert (
            self.copilot > 0 if mode in ["pro", "reasoning", "deep research"] else True
        ), "You have used all of your enhanced (pro) queries"
        assert self.file_upload - len(files) >= 0 if files else True, (
            f"You tried to upload {len(files)} files but only "
            f"{self.file_upload} upload(s) remain."
        )

        self.copilot = (
            self.copilot - 1 if mode in ["pro", "reasoning", "deep research"] else self.copilot
        )
        self.file_upload = self.file_upload - len(files) if files else self.file_upload

        uploaded_files = []

        for filename, file in files.items():
            file_type = mimetypes.guess_type(filename)[0]
            file_upload_info = (
                await self.session.post(
                    ENDPOINT_UPLOAD_URL,
                    params={"version": "2.18", "source": "default"},
                    json={
                        "content_type": file_type,
                        "file_size": sys.getsizeof(file),
                        "filename": filename,
                        "force_image": False,
                        "source": "default",
                    },
                )
            ).json()

            mp = CurlMime()
            for key, value in file_upload_info["fields"].items():
                mp.addpart(name=key, data=value)
            mp.addpart(
                name="file",
                content_type=file_type,
                filename=filename,
                data=file,
            )

            upload_resp = await self.session.post(file_upload_info["s3_bucket_url"], multipart=mp)

            if not upload_resp.ok:
                raise Exception("File upload error", upload_resp)

            if "image/upload" in file_upload_info["s3_object_url"]:
                uploaded_url = re.sub(
                    r"/private/s--.*?--/v\d+/user_uploads/",
                    "/private/user_uploads/",
                    upload_resp.json()["secure_url"],
                )
            else:
                uploaded_url = file_upload_info["s3_object_url"]

            uploaded_files.append(uploaded_url)

        json_data = {
            "query_str": query,
            "params": {
                "attachments": (
                    uploaded_files + follow_up["attachments"] if follow_up else uploaded_files
                ),
                "frontend_context_uuid": str(uuid4()),
                "frontend_uuid": str(uuid4()),
                "is_incognito": incognito,
                "language": language,
                "last_backend_uuid": (follow_up["backend_uuid"] if follow_up else None),
                "mode": "concise" if mode == "auto" else "copilot",
                "model_preference": {
                    "auto": {None: "turbo"},
                    "pro": {
                        None: "pplx_pro",
                        "sonar": "experimental",
                        "gpt-5.2": "gpt52",
                        "claude-4.5-sonnet": "claude45sonnet",
                        "grok-4.1": "grok41nonreasoning",
                    },
                    "reasoning": {
                        None: "pplx_reasoning",
                        "gpt-5.2-thinking": "gpt52_thinking",
                        "claude-4.5-sonnet-thinking": "claude45sonnetthinking",
                        "gemini-3.0-pro": "gemini30pro",
                        "kimi-k2-thinking": "kimik2thinking",
                        "grok-4.1-reasoning": "grok41reasoning",
                    },
                    "deep research": {None: "pplx_alpha"},
                }[mode][model],
                "source": "default",
                "sources": sources,
                "version": "2.18",
            },
        }

        resp = await self.session.post(ENDPOINT_SSE_ASK, json=json_data, stream=True)
        chunks = []

        async def stream_response(resp):
            async for chunk in resp.aiter_lines(delimiter=b"\r\n\r\n"):
                content = chunk.decode("utf-8")

                if content.startswith("event: message\r\n"):
                    try:
                        content_json = json.loads(content[len("event: message\r\ndata: ") :])

                        # Parse the nested 'text' field if it exists
                        if "text" in content_json and content_json["text"]:
                            try:
                                text_parsed = json.loads(content_json["text"])
                                # Extract answer from FINAL step if available
                                if isinstance(text_parsed, list):
                                    for step in text_parsed:
                                        if step.get("step_type") == "FINAL":
                                            final_content = step.get("content", {})
                                            if "answer" in final_content:
                                                answer_data = json.loads(final_content["answer"])
                                                content_json["answer"] = answer_data.get(
                                                    "answer", ""
                                                )
                                                content_json["chunks"] = answer_data.get(
                                                    "chunks", []
                                                )
                                                break
                                content_json["text"] = text_parsed
                            except (json.JSONDecodeError, TypeError, KeyError):
                                pass

                        chunks.append(content_json)
                        yield chunks[-1]
                    except (json.JSONDecodeError, KeyError):
                        continue

                elif content.startswith("event: end_of_stream\r\n"):
                    return

        if stream:
            return stream_response(resp)

        async for chunk in resp.aiter_lines(delimiter=b"\r\n\r\n"):
            content = chunk.decode("utf-8")

            if content.startswith("event: message\r\n"):
                try:
                    content_json = json.loads(content[len("event: message\r\ndata: ") :])

                    # Parse the nested 'text' field if it exists
                    if "text" in content_json and content_json["text"]:
                        try:
                            text_parsed = json.loads(content_json["text"])
                            # Extract answer from FINAL step if available
                            if isinstance(text_parsed, list):
                                for step in text_parsed:
                                    if step.get("step_type") == "FINAL":
                                        final_content = step.get("content", {})
                                        if "answer" in final_content:
                                            answer_data = json.loads(final_content["answer"])
                                            content_json["answer"] = answer_data.get("answer", "")
                                            content_json["chunks"] = answer_data.get("chunks", [])
                                            break
                            content_json["text"] = text_parsed
                        except (json.JSONDecodeError, TypeError, KeyError):
                            pass

                    chunks.append(content_json)
                except (json.JSONDecodeError, KeyError):
                    continue

            elif content.startswith("event: end_of_stream\r\n"):
                return chunks[-1] if chunks else {}
