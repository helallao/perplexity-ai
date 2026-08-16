import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote

from curl_cffi import requests

from .config import (
    EMAILNATOR_GENERATE_ENDPOINT,
    EMAILNATOR_HEADERS,
    EMAILNATOR_MESSAGE_LIST_ENDPOINT,
)
from .exceptions import EmailnatorError
from .logger import get_logger

logger = get_logger("emailnator")


class Emailnator:
    """Disposable-email helper built on top of Emailnator."""

    def __init__(
        self,
        cookies: Dict[str, str],
        headers: Optional[Dict[str, str]] = None,
        domain: bool = False,
        plus: bool = False,
        dot: bool = False,
        google_mail: bool = True,
        max_generate_attempts: int = 10,
    ):
        # Initialize inbox and advertisement inbox
        self.inbox: List[Dict[str, Any]] = []
        self.inbox_ads: List[str] = []
        self.new_msgs: List[Dict[str, Any]] = []

        # Set default headers if not provided
        if headers is None:
            headers = EMAILNATOR_HEADERS.copy()
            xsrf = cookies.get("XSRF-TOKEN", "") if isinstance(cookies, dict) else ""
            headers["x-xsrf-token"] = unquote(xsrf)

        # Initialize HTTP session
        self.s = requests.Session(headers=headers, cookies=cookies)

        # Prepare email generation options
        data = {"email": []}
        if domain:
            data["email"].append("domain")
        if plus:
            data["email"].append("plusGmail")
        if dot:
            data["email"].append("dotGmail")
        if google_mail:
            data["email"].append("googleMail")

        # Generate a new email address
        attempts = 0
        self.email = ""
        while attempts < max_generate_attempts:
            attempts += 1
            try:
                resp = self.s.post(EMAILNATOR_GENERATE_ENDPOINT, json=data)
                if resp.ok:
                    resp_json = resp.json()
                    if isinstance(resp_json, dict) and "email" in resp_json and resp_json["email"]:
                        self.email = resp_json["email"][0]
                        break
            except Exception as e:
                logger.debug(f"Email generation attempt {attempts} error: {e}")
            time.sleep(1)

        if not self.email:
            raise EmailnatorError("Failed to generate disposable email from Emailnator")

        # Load initial inbox advertisements
        try:
            ads_resp = self.s.post(
                EMAILNATOR_MESSAGE_LIST_ENDPOINT,
                json={"email": self.email},
            )
            if ads_resp.ok:
                ads_json = ads_resp.json()
                if isinstance(ads_json, dict):
                    for ads in ads_json.get("messageData", []):
                        if isinstance(ads, dict) and "messageID" in ads:
                            self.inbox_ads.append(ads["messageID"])
        except Exception as e:
            logger.debug(f"Initial ads load notice: {e}")

    def reload(
        self,
        wait: bool = False,
        retry: float = 5,
        timeout: float = 30,
        wait_for: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Reloads the inbox to fetch new messages.

        Parameters:
        - wait: Whether to wait for new messages.
        - retry: Retry interval in seconds.
        - timeout: Maximum wait time in seconds.
        - wait_for: A function to filter messages.

        Returns:
        - List of new messages.
        """
        self.new_msgs = []
        start = time.time()
        wait_for_found = False

        while True:
            try:
                resp = self.s.post(
                    EMAILNATOR_MESSAGE_LIST_ENDPOINT,
                    json={"email": self.email},
                )
                if resp.ok:
                    resp_json = resp.json()
                    if isinstance(resp_json, dict):
                        for msg in resp_json.get("messageData", []):
                            if (
                                isinstance(msg, dict)
                                and msg.get("messageID") not in self.inbox_ads
                                and msg not in self.inbox
                            ):
                                self.new_msgs.append(msg)

                                if wait_for and wait_for(msg):
                                    wait_for_found = True
            except Exception as e:
                logger.debug(f"Error checking Emailnator messages: {e}")

            if (wait and not self.new_msgs) or wait_for:
                if wait_for_found:
                    break

                if time.time() - start > timeout:
                    return self.new_msgs

                time.sleep(retry)
            else:
                break

        self.inbox += self.new_msgs  # Update the inbox with new messages
        return self.new_msgs

    def open(self, msg_id: str) -> str:
        """
        Opens a specific message by its ID.

        Parameters:
        - msg_id: The ID of the message to open.

        Returns:
        - The content of the message.
        """
        resp = self.s.post(
            EMAILNATOR_MESSAGE_LIST_ENDPOINT,
            json={"email": self.email, "messageID": msg_id},
        )
        return resp.text

    def get(
        self,
        func: Callable[[Dict[str, Any]], bool],
        msgs: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves a message that matches a given condition.

        Parameters:
        - func: A function to filter messages.
        - msgs: List of messages to search (default: inbox).

        Returns:
        - The first message that matches the condition or None.
        """
        search_list = msgs if msgs is not None else self.inbox
        for msg in search_list:
            if isinstance(msg, dict) and func(msg):
                return msg
        return None

    def close(self) -> None:
        """Close the HTTP session."""
        try:
            self.s.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
