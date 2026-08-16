import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote

from curl_cffi import requests

from perplexity.config import (
    EMAILNATOR_GENERATE_ENDPOINT,
    EMAILNATOR_HEADERS,
    EMAILNATOR_MESSAGE_LIST_ENDPOINT,
)
from perplexity.exceptions import EmailnatorError
from perplexity.logger import get_logger

logger = get_logger("async_emailnator")


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


class Emailnator(AsyncMixin):
    async def __ainit__(
        self,
        cookies: Dict[str, str],
        headers: Optional[Dict[str, str]] = None,
        domain: bool = False,
        plus: bool = False,
        dot: bool = False,
        google_mail: bool = True,
        max_generate_attempts: int = 10,
    ):
        self.inbox: List[Dict[str, Any]] = []
        self.inbox_ads: List[str] = []
        self.new_msgs: List[Dict[str, Any]] = []

        if headers is None:
            headers = EMAILNATOR_HEADERS.copy()
            xsrf = cookies.get("XSRF-TOKEN", "") if isinstance(cookies, dict) else ""
            headers["x-xsrf-token"] = unquote(xsrf)

        self.s = requests.AsyncSession(headers=headers, cookies=cookies, impersonate="chrome")

        data = {"email": []}
        if domain:
            data["email"].append("domain")
        if plus:
            data["email"].append("plusGmail")
        if dot:
            data["email"].append("dotGmail")
        if google_mail:
            data["email"].append("googleMail")

        attempts = 0
        self.email = ""
        while attempts < max_generate_attempts:
            attempts += 1
            try:
                resp = await self.s.post(EMAILNATOR_GENERATE_ENDPOINT, json=data)
                if resp.ok:
                    resp_json = resp.json()
                    if isinstance(resp_json, dict) and "email" in resp_json and resp_json["email"]:
                        self.email = resp_json["email"][0]
                        break
            except Exception as e:
                logger.debug(f"Async email generation attempt {attempts} error: {e}")
            await asyncio.sleep(1)

        if not self.email:
            raise EmailnatorError("Failed to generate disposable email from Emailnator")

        try:
            ads_resp = await self.s.post(
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
            logger.debug(f"Async initial ads load notice: {e}")

    async def reload(
        self,
        wait: bool = False,
        retry: float = 5,
        timeout: float = 30,
        wait_for: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Dict[str, Any]]:
        self.new_msgs = []
        start = time.time()
        wait_for_found = False

        while True:
            try:
                resp = await self.s.post(
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
                logger.debug(f"Error checking async Emailnator messages: {e}")

            if (wait and not self.new_msgs) or wait_for:
                if wait_for_found:
                    break

                if time.time() - start > timeout:
                    return self.new_msgs

                await asyncio.sleep(retry)
            else:
                break

        self.inbox += self.new_msgs
        return self.new_msgs

    async def open(self, msg_id: str) -> str:
        resp = await self.s.post(
            EMAILNATOR_MESSAGE_LIST_ENDPOINT,
            json={"email": self.email, "messageID": msg_id},
        )
        return resp.text

    def get(
        self,
        func: Callable[[Dict[str, Any]], bool],
        msgs: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        search_list = msgs if msgs is not None else self.inbox
        for msg in search_list:
            if isinstance(msg, dict) and func(msg):
                return msg
        return None

    async def close(self) -> None:
        """Close the HTTP session."""
        try:
            await self.s.close()
        except Exception:
            pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
