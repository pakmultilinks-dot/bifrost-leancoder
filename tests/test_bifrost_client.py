"""Tests for the Bifrost client. All HTTP is mocked, no live call."""
import os
import unittest
from unittest import mock

import requests

from leancoder.bifrost_client import (
    BifrostAuthError,
    BifrostClient,
    BifrostConnectionError,
    BifrostError,
)


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


def _ok_response(content="hello", prompt=10, completion=5):
    return FakeResponse(200, {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion,
                  "total_tokens": prompt + completion},
    })


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestBifrostClient(unittest.TestCase):
    def test_ok_parses_content_and_usage(self):
        client = BifrostClient(
            base_url="http://localhost:8080", api_key="test-key",
            model="gemini/gemini-2.5-flash",
            session=FakeSession([_ok_response("done", 12, 7)]))
        result = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result.content, "done")
        self.assertEqual(result.prompt_tokens, 12)
        self.assertEqual(result.completion_tokens, 7)
        self.assertEqual(result.total_tokens, 19)
        self.assertFalse(result.estimated)

    def test_missing_usage_is_marked_estimated(self):
        resp = FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})
        client = BifrostClient(base_url="http://localhost:8080",
                               model="gemini/gemini-2.5-flash",
                               session=FakeSession([resp]))
        result = client.chat([{"role": "user", "content": "hi"}])
        self.assertTrue(result.estimated)
        self.assertEqual(result.total_tokens, 0)

    def test_401_raises_auth_error_with_fix_and_no_key(self):
        client = BifrostClient(
            base_url="http://localhost:8080", api_key="secret-key-123",
            model="gemini/gemini-2.5-flash",
            session=FakeSession([FakeResponse(401, {}, "Unauthorized")]))
        with self.assertRaises(BifrostAuthError) as ctx:
            client.chat([{"role": "user", "content": "hi"}])
        self.assertIn("BIFROST_API_KEY", str(ctx.exception))
        self.assertNotIn("secret-key-123", str(ctx.exception))

    def test_timeout_retries_once_then_succeeds(self):
        session = FakeSession([
            requests.exceptions.Timeout("slow"),
            _ok_response("back", 3, 2),
        ])
        client = BifrostClient(base_url="http://localhost:8080",
                               model="gemini/gemini-2.5-flash", session=session)
        result = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result.content, "back")
        self.assertEqual(len(session.calls), 2)

    def test_timeout_twice_raises_connection_error(self):
        session = FakeSession([
            requests.exceptions.Timeout("slow"),
            requests.exceptions.Timeout("slow"),
        ])
        client = BifrostClient(base_url="http://localhost:8080",
                               model="gemini/gemini-2.5-flash", session=session)
        with self.assertRaises(BifrostConnectionError):
            client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(len(session.calls), 2)

    def test_connection_error(self):
        session = FakeSession([
            requests.exceptions.ConnectionError("refused"),
        ])
        client = BifrostClient(base_url="http://localhost:8080",
                               model="gemini/gemini-2.5-flash", session=session)
        with self.assertRaises(BifrostConnectionError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_no_model_raises(self):
        # A client with no model must raise even when the shell happens
        # to have BIFROST_MODEL set, so clear that variable for this test.
        env = dict(os.environ)
        env.pop("BIFROST_MODEL", None)
        with mock.patch.dict("os.environ", env, clear=True):
            client = BifrostClient(base_url="http://localhost:8080", model="",
                                   session=FakeSession([_ok_response()]))
            with self.assertRaises(BifrostError):
                client.chat([{"role": "user", "content": "hi"}])

    def test_500_raises(self):
        client = BifrostClient(
            base_url="http://localhost:8080", model="gemini/gemini-2.5-flash",
            session=FakeSession([FakeResponse(500, {}, "boom")]))
        with self.assertRaises(BifrostError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_auth_header_uses_key_without_logging_it(self):
        session = FakeSession([_ok_response()])
        client = BifrostClient(base_url="http://localhost:8080",
                               api_key="my-key", model="m",
                               session=session)
        client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(session.calls[0]["headers"]["Authorization"],
                         "Bearer my-key")


if __name__ == "__main__":
    unittest.main()
