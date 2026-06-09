"""008: cloud-mode wiring — `_build_cloud_grammar_analyzer` + its runner.

Exercises the full cloud feedback path with the OpenRouter HTTP boundary mocked
(no live calls): token resolution, fail-fast preflight, first-run capture/reuse,
model swap via YAML, and prompt-file editing. The local Qwen model is never
loaded.
"""

from __future__ import annotations

import io
import json
import sys

import pytest
import typer
from rich.console import Console

from speakloop.asr import Transcript
from speakloop.cli import practice
from speakloop.config import paths
from speakloop.llm import openrouter_credentials

pytestmark = pytest.mark.integration


# A transcript with a verbatim grammar error; its words are attested, so the
# coherence filter passes and the pipeline yields one GrammarPattern.
TS = [Transcript(text="I have eight year experience here.", audio_duration_seconds=30.0)]
_ERRORS = json.dumps(
    {
        "errors": [
            {
                "attempt_ordinal": 1,
                "quote": "eight year",
                "corrected": "eight years",
                "error_type": "missing plural -s",
                "explanation": "Use the plural after a number greater than one.",
            }
        ]
    }
)


class _FakeResp:
    def __init__(self, payload: dict):
        self._b = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeHTTP:
    def __init__(self, *, content: str = _ERRORS, auth_status: int = 200):
        self.content = content
        self.auth_status = auth_status
        self.requests: list[tuple[str, str, dict | None]] = []

    def __call__(self, req, timeout=None):
        import urllib.error

        method, url = req.get_method(), req.full_url
        body = json.loads(req.data.decode("utf-8")) if req.data else None
        self.requests.append((method, url, body))
        if url.endswith("/key"):
            if self.auth_status != 200:
                raise urllib.error.HTTPError(url, self.auth_status, "x", {}, io.BytesIO(b""))
            return _FakeResp({"data": {"label": "ok"}})
        return _FakeResp({"choices": [{"message": {"content": self.content}}]})

    def chat_bodies(self):
        return [b for (m, u, b) in self.requests if u.endswith("/chat/completions")]


@pytest.fixture
def http(monkeypatch):
    fake = _FakeHTTP()
    import speakloop.llm.openrouter_engine as eng

    monkeypatch.setattr(eng.urllib.request, "urlopen", fake)
    return fake


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return tmp_path


def _console():
    return Console(file=io.StringIO(), force_terminal=False)


# --- US1: cloud feedback runs without the local Qwen model ------------------


def test_cloud_runner_produces_feedback_without_local_qwen(home, http, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-valid")
    mlx_before = "mlx_lm" in sys.modules

    runner, _coach = practice._build_cloud_grammar_analyzer(_console())
    patterns = runner(TS)

    assert len(patterns) == 1
    assert patterns[0].label == "missing plural -s"
    # Cloud mode must not newly import the local LLM engine package (SC-002).
    assert ("mlx_lm" in sys.modules) == mlx_before
    # Preflight hit /key before any chat call.
    assert http.requests[0][1].endswith("/key")


# --- US2: first-run capture, silent reuse, invalid-token handling -----------


def test_first_run_prompts_then_stores_token(home, http):
    assert openrouter_credentials.resolve_token() is None
    inputs = iter(["sk-or-entered"])
    runner, _coach = practice._build_cloud_grammar_analyzer(
        _console(), input_fn=lambda _prompt="": next(inputs)
    )
    runner(TS)
    # Stored for reuse.
    assert openrouter_credentials.resolve_token() == "sk-or-entered"
    assert paths.openrouter_token_path().exists()


def test_second_run_is_silent(home, http):
    openrouter_credentials.store_token("sk-or-stored")

    def _no_input(_prompt=""):
        raise AssertionError("should not prompt when a token is stored")

    runner, _coach = practice._build_cloud_grammar_analyzer(_console(), input_fn=_no_input)
    assert runner(TS)  # completes without prompting


def test_declined_empty_token_exits(home, http):
    with pytest.raises(typer.Exit):
        practice._build_cloud_grammar_analyzer(_console(), input_fn=lambda _p="": "")


def test_invalid_token_reprompts_then_exits(home, monkeypatch):
    fake = _FakeHTTP(auth_status=401)  # every preflight rejects
    import speakloop.llm.openrouter_engine as eng

    monkeypatch.setattr(eng.urllib.request, "urlopen", fake)
    openrouter_credentials.store_token("sk-or-bad")

    prompts: list[str] = []

    def _input(_prompt=""):
        prompts.append(_prompt)
        return "sk-or-still-bad"

    with pytest.raises(typer.Exit):
        practice._build_cloud_grammar_analyzer(_console(), input_fn=_input)
    # Exactly one re-prompt on rejection (then exit).
    assert len(prompts) == 1


# --- US4: model swap via YAML ----------------------------------------------


def test_model_id_from_yaml_used_in_request(home, http, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-valid")
    paths.openrouter_config_path().write_text("model: acme/custom-model\n", encoding="utf-8")

    runner, _coach = practice._build_cloud_grammar_analyzer(_console())
    runner(TS)

    bodies = http.chat_bodies()
    assert bodies and bodies[0]["model"] == "acme/custom-model"


def test_default_model_when_no_yaml(home, http, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-valid")
    runner, _coach = practice._build_cloud_grammar_analyzer(_console())
    runner(TS)
    assert http.chat_bodies()[0]["model"] == "qwen/qwen3.7-max"


# --- US5: editable cloud prompt file ---------------------------------------


def test_edited_prompt_file_is_sent(home, http, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-valid")
    # Seed then edit the cloud prompt file.
    paths.openrouter_prompt_path().parent.mkdir(parents=True, exist_ok=True)
    paths.openrouter_prompt_path().write_text("MY EDITED CLOUD PROMPT", encoding="utf-8")

    runner, _coach = practice._build_cloud_grammar_analyzer(_console())
    runner(TS)

    system_msg = http.chat_bodies()[0]["messages"][0]
    assert system_msg["role"] == "system"
    assert system_msg["content"] == "MY EDITED CLOUD PROMPT"


# --- 009: the additive coaching runner is built over the SAME engine ---------


def test_build_returns_coach_runner_sending_coach_prompt_over_same_engine(
    home, http, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-valid")
    paths.openrouter_coach_prompt_path().parent.mkdir(parents=True, exist_ok=True)
    paths.openrouter_coach_prompt_path().write_text("MY COACH PROMPT", encoding="utf-8")

    grammar, coach = practice._build_cloud_grammar_analyzer(_console())
    assert callable(grammar) and callable(coach)

    # The coach call goes over the same engine (one preflight /key, then a chat
    # completion carrying the coach system prompt verbatim).
    result = coach("Tell me about coroutines.", TS, [])
    assert result  # non-empty markdown (the fake echoes content back)
    body = http.chat_bodies()[-1]
    system_msg = body["messages"][0]
    assert system_msg["role"] == "system"
    assert system_msg["content"] == "MY COACH PROMPT"
    # The same model id resolved for the grammar call is reused for coaching.
    assert body["model"] == "qwen/qwen3.7-max"
