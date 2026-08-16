import json
import mimetypes
import random
import re
import sys
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from uuid import uuid4

from curl_cffi import CurlMime, requests

from perplexity.config import (
    DEFAULT_HEADERS,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_AUTH_SIGNIN,
    ENDPOINT_SSE_ASK,
    ENDPOINT_UPLOAD_URL,
    MODEL_MAPPINGS,
    SIGNIN_URL_PATTERN,
)
from perplexity.exceptions import (
    AccountCreationError,
    AuthenticationError,
    FileUploadError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from perplexity.logger import get_logger
from perplexity.utils import (
    parse_nested_json_response,
    validate_file_data,
    validate_query_limits,
    validate_search_params,
)
from .emailnator import Emailnator

logger = get_logger("async_client")


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
    A client for interacting with the Perplexity AI API asynchronously.
    """

    async def __ainit__(self, cookies: Optional[Dict[str, str]] = None):
        if cookies is None:
            cookies = {}
        self.session = requests.AsyncSession(
            headers=DEFAULT_HEADERS.copy(),
            cookies=cookies,
            impersonate="chrome",
        )
        self.own = bool(cookies)
        self.copilot = 0 if not cookies else float("inf")
        self.file_upload = 0 if not cookies else float("inf")
        self.signin_regex = re.compile(SIGNIN_URL_PATTERN)
        self.timestamp = format(random.getrandbits(32), "08x")
        try:
            await self.session.get(ENDPOINT_AUTH_SESSION)
        except Exception as e:
            logger.warning(f"Initial async session handshake notice: {e}")

    async def create_account(self, cookies: Dict[str, str], max_attempts: int = 5) -> bool:
        """
        Function to create a new account asynchronously.

        Args:
            cookies: Emailnator cookies dictionary
            max_attempts: Maximum attempts to create account

        Returns:
            True if account creation succeeded

        Raises:
            AccountCreationError: If account creation fails
        """
        attempts = 0
        emailnator_cli = None

        while attempts < max_attempts:
            attempts += 1
            try:
                emailnator_cli = await Emailnator(cookies)

                cookie_csrf = self.session.cookies.get_dict().get("next-auth.csrf-token", "")
                csrf_token = cookie_csrf.split("%")[0] if cookie_csrf else ""

                resp = await self.session.post(
                    ENDPOINT_AUTH_SIGNIN,
                    data={
                        "email": emailnator_cli.email,
                        "csrfToken": csrf_token,
                        "callbackUrl": "https://www.perplexity.ai/",
                        "json": "true",
                    },
                )

                if resp.ok:
                    new_msgs = await emailnator_cli.reload(
                        wait_for=lambda x: x.get("subject") == "Sign in to Perplexity",
                        timeout=20,
                    )

                    if new_msgs:
                        break
                else:
                    logger.warning(f"Async Perplexity account creation failed: {resp.status_code}")

            except Exception as e:
                logger.debug(f"Async account creation attempt {attempts} error: {e}")

        if not emailnator_cli:
            raise AccountCreationError("Failed to initialize Emailnator client")

        msg = emailnator_cli.get(func=lambda x: x.get("subject") == "Sign in to Perplexity")
        if not msg:
            raise AccountCreationError("Sign-in email not received from Perplexity")

        msg_body = await emailnator_cli.open(msg["messageID"])
        match = self.signin_regex.search(msg_body)
        if not match:
            raise AccountCreationError("Could not extract sign-in callback link from email")

        new_account_link = match.group(1)

        resp = await self.session.get(new_account_link)
        if not resp.ok:
            raise AccountCreationError(f"Failed to authenticate with callback link: {resp.status_code}")

        self.copilot = 5
        self.file_upload = 10

        return True

    async def search(
        self,
        query: str,
        mode: str = "auto",
        model: Optional[str] = None,
        sources: Optional[List[str]] = None,
        files: Optional[Dict[str, Union[bytes, str]]] = None,
        stream: bool = False,
        language: str = "en-US",
        follow_up: Optional[Dict[str, Any]] = None,
        incognito: bool = False,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        Query function asynchronously.

        Parameters:
        - query: The search query string.
        - mode: Search mode ('auto', 'pro', 'reasoning', 'deep research').
        - model: Specific model to use for the query.
        - sources: List of sources ('web', 'scholar', 'social').
        - files: Dictionary of files to upload.
        - stream: Whether to stream the response.
        - language: Language code (ISO 639).
        - follow_up: Information for follow-up queries.
        - incognito: Whether to enable incognito mode.

        Returns:
        - Response dict or async generator yielding response dicts if streaming.
        """
        if sources is None:
            sources = ["web"]
        if files is None:
            files = {}

        # Validate input parameters and query limits
        validate_search_params(mode=mode, model=model, sources=sources, own_account=self.own)
        if files:
            validate_file_data(files)
        validate_query_limits(
            copilot_remaining=self.copilot,
            file_upload_remaining=self.file_upload,
            mode=mode,
            files_count=len(files),
        )

        if mode in ["pro", "reasoning", "deep research"]:
            self.copilot = max(0, self.copilot - 1) if self.copilot != float("inf") else self.copilot
        if files:
            self.file_upload = (
                max(0, self.file_upload - len(files))
                if self.file_upload != float("inf")
                else self.file_upload
            )

        uploaded_files = []

        for filename, file in files.items():
            file_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            file_size = len(file) if isinstance(file, (bytes, str)) else sys.getsizeof(file)
            file_upload_resp = await self.session.post(
                ENDPOINT_UPLOAD_URL,
                params={"version": "2.18", "source": "default"},
                json={
                    "content_type": file_type,
                    "file_size": file_size,
                    "filename": filename,
                    "force_image": False,
                    "source": "default",
                },
            )
            if not file_upload_resp.ok:
                raise FileUploadError(f"Failed to get upload URL: {file_upload_resp.status_code}")

            file_upload_info = file_upload_resp.json()

            mp = CurlMime()
            for key, value in file_upload_info.get("fields", {}).items():
                mp.addpart(name=key, data=value)
            mp.addpart(
                name="file",
                content_type=file_type,
                filename=filename,
                data=file,
            )

            upload_resp = await self.session.post(file_upload_info["s3_bucket_url"], multipart=mp)

            if not upload_resp.ok:
                raise FileUploadError(f"File upload to storage failed: {upload_resp.status_code}")

            if "image/upload" in file_upload_info.get("s3_object_url", ""):
                uploaded_url = re.sub(
                    r"/private/s--.*?--/v\d+/user_uploads/",
                    "/private/user_uploads/",
                    upload_resp.json().get("secure_url", file_upload_info.get("s3_object_url", "")),
                )
            else:
                uploaded_url = file_upload_info.get("s3_object_url", "")

            uploaded_files.append(uploaded_url)

        model_pref = MODEL_MAPPINGS.get(mode, {}).get(model, "turbo")

        json_data = {
            "query_str": query,
            "params": {
                "attachments": (
                    uploaded_files + follow_up.get("attachments", [])
                    if follow_up and isinstance(follow_up, dict)
                    else uploaded_files
                ),
                "frontend_context_uuid": str(uuid4()),
                "frontend_uuid": str(uuid4()),
                "is_incognito": incognito,
                "language": language,
                "last_backend_uuid": (
                    follow_up.get("backend_uuid") if follow_up and isinstance(follow_up, dict) else None
                ),
                "mode": "concise" if mode == "auto" else "copilot",
                "model_preference": model_pref,
                "source": "default",
                "sources": sources,
                "version": "2.18",
            },
        }

        resp = await self.session.post(ENDPOINT_SSE_ASK, json=json_data, stream=True)

        if resp.status_code == 429:
            raise RateLimitError("Perplexity rate limit reached. Please wait before retrying.")
        if resp.status_code in (401, 403):
            raise AuthenticationError(f"Authentication failed: status code {resp.status_code}")
        if resp.status_code >= 400:
            raise NetworkError(f"Perplexity request failed with status code {resp.status_code}")

        chunks: List[Dict[str, Any]] = []

        async def stream_response(resp_obj):
            async for chunk in resp_obj.aiter_lines(delimiter=b"\r\n\r\n"):
                content = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)

                if "data: " in content:
                    try:
                        data_str = content.split("data: ", 1)[1]
                        content_json = json.loads(data_str)
                        content_json = parse_nested_json_response(content_json)
                        chunks.append(content_json)
                        yield chunks[-1]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

                elif "event: end_of_stream" in content:
                    return

        if stream:
            return stream_response(resp)

        async for chunk in resp.aiter_lines(delimiter=b"\r\n\r\n"):
            content = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)

            if "data: " in content:
                try:
                    data_str = content.split("data: ", 1)[1]
                    content_json = json.loads(data_str)
                    content_json = parse_nested_json_response(content_json)
                    chunks.append(content_json)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            elif "event: end_of_stream" in content:
                return chunks[-1] if chunks else {}

        return chunks[-1] if chunks else {}
