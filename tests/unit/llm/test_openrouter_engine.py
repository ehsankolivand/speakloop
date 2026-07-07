"""008: OpenRouterEngine — request shape, content extraction, error mapping.

Mocks the urllib boundary (no live calls — Constitution dev guideline). Asserts
the system message is the passed prompt verbatim, the Bearer header is present,
the token never leaks into errors, and HTTP statuses map to the right exceptions.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from speakloop.llm.interface import LLMEngineError
from speakloop.llm.openrouter_engine import OpenRouterAuthError, OpenRouterEngine

pytestmark = pytest.mark.unit

TOKEN = "sk-or-secret-do-not-leak"


class _FakeResp:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _install_urlopen(monkeypatch, handler):
    """Patch urlopen in the engine module; handler(req, timeout) -> resp/raises."""
    import speakloop.llm.openrouter_engine as mod

    monkeypatch.setattr(mod.urllib.request, "urlopen", handler)


def _chat_payload(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_generate_request_shape_and_content(monkeypatch):
    captured = {}

    def handler(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(_chat_payload('{"errors": []}'))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="qwen/qwen3.7-max", token=TOKEN)
    out = eng.generate("SYSTEM-PROMPT", "USER-PROMPT", max_tokens=128, temperature=0.3)

    assert out == '{"errors": []}'
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["method"] == "POST"
    # Header keys are title-cased by urllib.
    assert captured["headers"].get("Authorization") == f"Bearer {TOKEN}"
    body = captured["body"]
    assert body["model"] == "qwen/qwen3.7-max"
    assert body["max_tokens"] == 128
    assert body["temperature"] == 0.3
    # System message is the passed prompt VERBATIM (FR-012 honesty).
    assert body["messages"][0] == {"role": "system", "content": "SYSTEM-PROMPT"}
    assert body["messages"][1]["role"] == "user"
    assert body["messages"][1]["content"] == "USER-PROMPT"


def test_retry_keeps_system_verbatim_and_nudges(monkeypatch):
    captured = {}

    def handler(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(_chat_payload("{}"))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="m", token=TOKEN)
    eng.generate("SYS", "USER", temperature=0.7, retry=True)

    body = captured["body"]
    # System stays verbatim; the nudge goes to the user message + lower temp.
    assert body["messages"][0]["content"] == "SYS"
    assert "STRICT JSON" in body["messages"][1]["content"]
    assert body["temperature"] < 0.7


def test_http_401_maps_to_auth_error(monkeypatch):
    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b""))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="m", token=TOKEN)
    with pytest.raises(OpenRouterAuthError) as exc:
        eng.generate("s", "u")
    assert TOKEN not in str(exc.value)


def test_http_404_names_model(monkeypatch):
    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b""))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="acme/does-not-exist", token=TOKEN)
    with pytest.raises(LLMEngineError) as exc:
        eng.generate("s", "u")
    assert "acme/does-not-exist" in str(exc.value)
    assert not isinstance(exc.value, OpenRouterAuthError)


def test_http_500_maps_to_generic_error(monkeypatch):
    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, "Server Error", {}, io.BytesIO(b""))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="m", token=TOKEN)
    with pytest.raises(LLMEngineError) as exc:
        eng.generate("s", "u")
    assert not isinstance(exc.value, OpenRouterAuthError)
    assert TOKEN not in str(exc.value)


def test_error_body_message_is_surfaced(monkeypatch):
    """IMP-013: OpenRouter's error.message is appended so the user can diagnose (credits,
    unsupported model, provider outage) instead of seeing only a bare status code."""
    body = b'{"error": {"message": "This model requires more credits than are available."}}'

    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 402, "Payment Required", {}, io.BytesIO(body))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="m", token=TOKEN)
    with pytest.raises(LLMEngineError) as exc:
        eng.generate("s", "u")
    msg = str(exc.value)
    assert "more credits than are available" in msg
    assert "402" in msg
    assert TOKEN not in msg  # token lives only in the request header, never echoed


def test_error_body_appended_to_404(monkeypatch):
    body = b'{"error": {"message": "No endpoints found for acme/does-not-exist."}}'

    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(body))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="acme/does-not-exist", token=TOKEN)
    with pytest.raises(LLMEngineError) as exc:
        eng.generate("s", "u")
    msg = str(exc.value)
    assert "acme/does-not-exist" in msg   # still names the model
    assert "No endpoints found" in msg    # AND surfaces the body reason


def test_non_json_error_body_surfaced_as_truncated_snippet(monkeypatch):
    """A non-JSON error body (e.g. an HTML 502 page) is surfaced as a truncated snippet."""
    body = b"upstream provider timed out after 30s " * 20  # long, non-JSON

    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 502, "Bad Gateway", {}, io.BytesIO(body))

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="m", token=TOKEN)
    with pytest.raises(LLMEngineError) as exc:
        eng.generate("s", "u")
    msg = str(exc.value)
    assert "upstream provider timed out" in msg
    assert len(msg) < 300  # body detail is capped at ~200 chars


def test_network_error_maps_to_llm_engine_error(monkeypatch):
    def handler(req, timeout=None):
        raise urllib.error.URLError("Name or service not known")

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="m", token=TOKEN)
    with pytest.raises(LLMEngineError):
        eng.generate("s", "u")


def test_missing_content_maps_to_llm_engine_error(monkeypatch):
    def handler(req, timeout=None):
        return _FakeResp({"choices": []})

    _install_urlopen(monkeypatch, handler)
    eng = OpenRouterEngine(model="m", token=TOKEN)
    with pytest.raises(LLMEngineError):
        eng.generate("s", "u")


def test_check_auth_hits_key_endpoint(monkeypatch):
    captured = {}

    def handler(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return _FakeResp({"data": {"label": "ok"}})

    _install_urlopen(monkeypatch, handler)
    OpenRouterEngine(model="m", token=TOKEN).check_auth()
    assert captured["url"] == "https://openrouter.ai/api/v1/key"
    assert captured["method"] == "GET"


def test_check_auth_401_raises_auth_error(monkeypatch):
    def handler(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b""))

    _install_urlopen(monkeypatch, handler)
    with pytest.raises(OpenRouterAuthError):
        OpenRouterEngine(model="m", token=TOKEN).check_auth()
