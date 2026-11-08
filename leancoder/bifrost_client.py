"""OpenAI-compatible client for a Bifrost gateway.

Every model call goes through Bifrost, never directly to a provider.
The base URL and key come from the environment only, never hard-coded.
Token counts come from the model response usage field. If usage is
missing for a call, the call is marked estimated, never silently
presented as exact.
"""
from __future__ import annotations

import os

import requests

DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_TIMEOUT = 60

AUTH_FIX_MESSAGE = (
    "Bifrost returned 401 Unauthorized. Check the key configured in "
    "Bifrost, copy the active key from the provider dashboard, set it "
    "as BIFROST_API_KEY in your shell, and retry. Never paste a real "
    "key into source code or into a committed file."
)


class BifrostError(Exception):
    """A non-auth error from the Bifrost gateway."""


class BifrostAuthError(BifrostError):
    """Bifrost rejected the key with 401."""


class BifrostConnectionError(BifrostError):
    """Bifrost could not be reached at all."""


class ChatResult:
    """One model reply, with its measured token usage."""

    def __init__(self, content, usage, model, estimated=False):
        self.content = content or ""
        self.usage = usage or {}
        self.model = model or ""
        self.estimated = estimated

    @property
    def prompt_tokens(self):
        return int(self.usage.get("prompt_tokens") or 0)

    @property
    def completion_tokens(self):
        return int(self.usage.get("completion_tokens") or 0)

    @property
    def total_tokens(self):
        total = self.usage.get("total_tokens")
        if total is None:
            return self.prompt_tokens + self.completion_tokens
        return int(total)


def _usage_from_response(data):
    usage = data.get("usage") or {}
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0,
                "total_tokens": 0}, True
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }, False


class BifrostClient:
    """Minimal chat client for the Bifrost OpenAI-compatible endpoint."""

    def __init__(self, base_url=None, api_key=None, model=None,
                 timeout=DEFAULT_TIMEOUT, session=None):
        self.base_url = (base_url or os.environ.get("BIFROST_BASE_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get(
            "BIFROST_API_KEY", "")
        self.model = model or os.environ.get("BIFROST_MODEL", "")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        return headers

    def chat(self, messages, model=None, timeout=None):
        """Send one chat request. Retry once only on timeout, never on 401."""
        use_model = model or self.model
        if not use_model:
            raise BifrostError("No model set. Set BIFROST_MODEL or pass a model.")
        url = self.base_url + "/v1/chat/completions"
        payload = {
            "model": use_model,
            "messages": list(messages),
        }
        wait = timeout if timeout is not None else self.timeout
        last_error = None
        for attempt in range(2):
            try:
                response = self.session.post(
                    url, json=payload, headers=self._headers(),
                    timeout=wait)
            except requests.exceptions.Timeout as exc:
                last_error = exc
                continue
            except requests.exceptions.ConnectionError as exc:
                raise BifrostConnectionError(
                    "Could not reach Bifrost at " + self.base_url + ". "
                    "Start Bifrost first, then retry."
                ) from exc
            if response.status_code == 401:
                raise BifrostAuthError(AUTH_FIX_MESSAGE)
            if response.status_code >= 400:
                raise BifrostError(
                    "Bifrost returned HTTP " + str(response.status_code)
                    + ": " + response.text[:300])
            data = response.json()
            choices = data.get("choices") or []
            content = ""
            if choices:
                content = (choices[0].get("message") or {}).get("content") or ""
            usage, estimated = _usage_from_response(data)
            return ChatResult(content, usage, use_model, estimated=estimated)
        raise BifrostConnectionError(
            "Bifrost request timed out after 2 attempts at " + self.base_url
            + ". Check the gateway, then retry.")
