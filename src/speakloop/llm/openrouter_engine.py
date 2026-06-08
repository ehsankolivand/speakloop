"""OpenRouter cloud LLM wrapper (opt-in cloud mode, feature 008).

This is the ONLY file in the repo that talks to OpenRouter. It implements the
stable ``LLMEngine`` Protocol (Constitution Principle V) over the standard
library (``urllib``) so adding a cloud provider touches exactly one file and
needs **no new dependency**. Network calls happen only inside ``generate()`` /
``check_auth()`` — never at import time — so ``speakloop --help`` stays offline
and model-free (Principle VIII).

The token is never logged and never included in any raised error message.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from speakloop.llm.interface import LLMEngineError

_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_TIMEOUT = 30.0


class OpenRouterAuthError(LLMEngineError):
    """Raised on a 401/403 from OpenRouter — token missing-permission/rejected.

    A distinct subclass so the CLI can fail FAST with an actionable message at
    preflight time, while every other failure stays a generic ``LLMEngineError``
    that the session degrades gracefully into ``phase_c_error`` (FR-014)."""


class OpenRouterEngine:
    """Cloud LLM generator backed by OpenRouter's OpenAI-compatible API.

    Satisfies the ``LLMEngine`` Protocol; the analyzer is engine-agnostic and
    depends only on that interface.
    """

    def __init__(
        self,
        *,
        model: str,
        token: str,
        base_url: str = _BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._model = model
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # --- transport (the only place urllib is used) --------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            # Optional attribution headers OpenRouter recommends; harmless.
            "HTTP-Referer": "https://github.com/speakloop/speakloop",
            "X-Title": "speakloop",
        }

    def _send(self, req: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status = e.code
            if status in (401, 403):
                raise OpenRouterAuthError(
                    f"OpenRouter rejected the request (HTTP {status}); the API token "
                    "is missing or invalid."
                ) from None
            if status == 404:
                raise LLMEngineError(
                    f"OpenRouter returned HTTP 404 for model {self._model!r}. "
                    "Check the `model:` value in ~/.speakloop/openrouter.yaml."
                ) from None
            raise LLMEngineError(f"OpenRouter request failed (HTTP {status}).") from None
        except urllib.error.URLError as e:
            raise LLMEngineError(f"Could not reach OpenRouter: {e.reason}.") from None
        except (TimeoutError, OSError) as e:
            raise LLMEngineError(f"OpenRouter request errored: {e}.") from None
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            raise LLMEngineError(f"OpenRouter returned a non-JSON response: {e}.") from None

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        return self._send(req)

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(
            f"{self._base_url}{path}", headers=self._headers(), method="GET"
        )
        return self._send(req)

    # --- LLMEngine Protocol -------------------------------------------------

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        retry: bool = False,
    ) -> str:
        """One chat-completion. Returns ``choices[0].message.content`` stripped.

        ``retry=True`` is intent only (Principle V): the wrapper owns the nudge —
        a small temperature drop plus a STRICT-JSON reminder appended to the USER
        message, so the **system** message always equals ``system_prompt``
        verbatim (the cloud prompt the caller supplied)."""
        temp = max(0.0, round(temperature - 0.2, 2)) if retry else temperature
        user = user_prompt
        if retry:
            user = (
                f"{user_prompt}\n\nReminder: return STRICT JSON only — a single "
                "object, no prose, no markdown code fences."
            )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user},
            ],
            "temperature": temp,
            "max_tokens": max_tokens,
        }
        data = self._post("/chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMEngineError(
                f"OpenRouter response missing choices[0].message.content: {e}."
            ) from None
        if not isinstance(content, str):
            raise LLMEngineError("OpenRouter response 'content' was not a string.")
        return content.strip()

    def check_auth(self) -> None:
        """Preflight token validation via ``GET /key``.

        Raises ``OpenRouterAuthError`` if the token is rejected, ``LLMEngineError``
        on transport failure. Cheap; run once before the timed session so a bad
        token surfaces an actionable error up front (FR-006)."""
        self._get("/key")
