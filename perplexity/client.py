# Importing necessary modules
# re: Regular expressions for pattern matching
# sys: System-specific parameters and functions
# json: JSON parsing and serialization
# random: Random number generation
# mimetypes: Guessing MIME types of files
# uuid: Generating unique identifiers
# curl_cffi: HTTP requests and multipart form data handling
import json
import mimetypes
import random
import re
import sys
from uuid import uuid4

from curl_cffi import CurlMime, requests

from .config import (
    DEFAULT_HEADERS,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_AUTH_SIGNIN,
    ENDPOINT_SSE_ASK,
    ENDPOINT_UPLOAD_URL,
)
from .emailnator import Emailnator


class Client:
    """
    A client for interacting with the Perplexity AI API.
    """

    def __init__(self, cookies={}):
        # Initialize an HTTP session with default headers and optional cookies
        self.session = requests.Session(
            headers=DEFAULT_HEADERS.copy(),
            cookies=cookies,
            impersonate="chrome",
        )

        # Flags and counters for account and query management
        self.own = bool(cookies)  # Indicates if the client uses its own account
        self.copilot = 0 if not cookies else float("inf")  # Remaining pro queries
        self.file_upload = 0 if not cookies else float("inf")  # Remaining file uploads

        # Regular expression for extracting sign-in links
        self.signin_regex = re.compile(
            r'"(https://www\\.perplexity\\.ai/api/auth/callback/email\\?' r'callbackUrl=.*?)"'
        )

        # Unique timestamp for session identification
        self.timestamp = format(random.getrandbits(32), "08x")

        # Initialize session by making a GET request
        self.session.get(ENDPOINT_AUTH_SESSION)

    def create_account(self, cookies):
        """
        Creates a new account using Emailnator cookies.
        """
        while True:
            try:
                # Initialize Emailnator client
                emailnator_cli = Emailnator(cookies)

                # Send a POST request to initiate account creation
                resp = self.session.post(
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

                # Check if the response is successful
                if resp.ok:
                    # Wait for the sign-in email to arrive
                    new_msgs = emailnator_cli.reload(
                        wait_for=lambda x: x["subject"] == "Sign in to Perplexity",
                        timeout=20,
                    )

                    if new_msgs:
                        break
                else:
                    print("Perplexity account creating error:", resp)

            except Exception:
                pass

        # Extract the sign-in link from the email
        msg = emailnator_cli.get(func=lambda x: x["subject"] == "Sign in to Perplexity")
        new_account_link = self.signin_regex.search(emailnator_cli.open(msg["messageID"])).group(1)

        # Complete the account creation process
        self.session.get(new_account_link)

        # Update query and file upload limits
        self.copilot = 5
        self.file_upload = 10

        return True

    def search(
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
        Executes a search query on Perplexity AI.

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
        """
        # Validate input parameters
        assert mode in [
            "auto",
            "pro",
            "reasoning",
            "deep research",
        ], "Invalid search mode."
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
            }[mode]
            if self.own
            else True
        ), "Invalid model for the selected mode."
        assert all(
            [source in ("web", "scholar", "social") for source in sources]
        ), "Invalid sources."
        assert (
            self.copilot > 0 if mode in ["pro", "reasoning", "deep research"] else True
        ), "No remaining pro queries."
        assert self.file_upload - len(files) >= 0 if files else True, "File upload limit exceeded."

        # Update query and file upload counters
        self.copilot = (
            self.copilot - 1 if mode in ["pro", "reasoning", "deep research"] else self.copilot
        )
        self.file_upload = self.file_upload - len(files) if files else self.file_upload

        # Upload files and prepare the query payload
        uploaded_files = []
        for filename, file in files.items():
            file_type = mimetypes.guess_type(filename)[0]
            file_upload_info = (
                self.session.post(
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

            # Upload the file to the server
            mp = CurlMime()
            for key, value in file_upload_info["fields"].items():
                mp.addpart(name=key, data=value)
            mp.addpart(
                name="file",
                content_type=file_type,
                filename=filename,
                data=file,
            )

            upload_resp = self.session.post(file_upload_info["s3_bucket_url"], multipart=mp)

            if not upload_resp.ok:
                raise Exception("File upload error", upload_resp)

            # Extract the uploaded file URL
            if "image/upload" in file_upload_info["s3_object_url"]:
                uploaded_url = re.sub(
                    r"/private/s--.*?--/v\\d+/user_uploads/",
                    "/private/user_uploads/",
                    upload_resp.json()["secure_url"],
                )
            else:
                uploaded_url = file_upload_info["s3_object_url"]

            uploaded_files.append(uploaded_url)

        # Prepare the JSON payload for the query
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

        # Send the query request and handle the response
        resp = self.session.post(ENDPOINT_SSE_ASK, json=json_data, stream=True)
        chunks = []

        def stream_response(resp):
            """
            Generator for streaming responses.
            """
            for chunk in resp.iter_lines(delimiter=b"\r\n\r\n"):
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

        for chunk in resp.iter_lines(delimiter=b"\r\n\r\n"):
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
