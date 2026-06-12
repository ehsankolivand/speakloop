"""Shared pytest fixtures.

Engine tests use cached fixture WAVs / transcripts committed under
`tests/fixtures/`. **No live model calls.** (Constitution Dev Guidelines.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from speakloop.config import paths

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --- 011: fake Claude Code CLI runner harness --------------------------------
# No automated test ever spawns the real `claude` binary or consumes credit
# (Constitution: "Live model calls in tests are forbidden"). Tests inject one of
# these fake runners into ClaudeCodeEngine(runner=...). Lives here (not in a
# tests/helpers module) so it is importable from every test directory via the
# `fake_claude` fixture without packaging tests/.


@dataclass
class RecordedCall:
    argv: list
    stdin: str
    timeout: float
    env: dict


@dataclass
class FakeClaudeRunner:
    """A Runner stub: records each call, then returns/raises a scripted result.

    ``results`` is either a single ``ClaudeCliResult``/exception, or a list popped
    in order (so a retry sequence can return different outputs per call)."""

    results: object
    calls: list = field(default_factory=list)

    def __call__(self, argv, stdin, timeout, env):
        self.calls.append(RecordedCall(list(argv), stdin, timeout, dict(env)))
        r = self.results
        if isinstance(r, list):
            r = r.pop(0)
        if isinstance(r, BaseException):
            raise r
        if isinstance(r, type) and issubclass(r, BaseException):
            raise r("fake claude failure")
        return r


def _cli_result(stdout: str, stderr: str = "", returncode: int = 0):
    from speakloop.llm.claude_code_engine import ClaudeCliResult

    return ClaudeCliResult(stdout=stdout, stderr=stderr, returncode=returncode)


def _success(result_text: str):
    """A success envelope (is_error False) carrying ``result_text``."""
    return _cli_result(
        json.dumps(
            {"type": "result", "subtype": "success", "is_error": False, "result": result_text}
        )
    )


def _error(result_text: str, *, api_error_status=None, returncode: int = 1):
    """An error envelope (is_error True) — note subtype stays 'success'."""
    return _cli_result(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "result": result_text,
                "api_error_status": api_error_status,
            }
        ),
        returncode=returncode,
    )


def _non_json(stderr: str = "error: unknown option '--gone'", returncode: int = 1):
    """Garbage / empty stdout with an arg-parse stderr (CLI-changed case)."""
    return _cli_result("", stderr=stderr, returncode=returncode)


@pytest.fixture
def fake_claude():
    """Builders + the FakeClaudeRunner for Claude Code engine tests (no real CLI)."""
    return SimpleNamespace(
        Runner=FakeClaudeRunner,
        success=_success,
        error=_error,
        non_json=_non_json,
        cli_result=_cli_result,
    )


@pytest.fixture(autouse=True)
def _isolate_loop_config(tmp_path_factory, monkeypatch):
    """Keep the real ``~/.speakloop/loop.yaml`` out of the test suite (011).

    Otherwise a user whose loop config sets ``engine: claude`` (or ``openrouter``)
    would make every no-flag code path (``practice``/``resume`` without ``--engine``)
    resolve to that cloud engine and attempt REAL model calls — which hang/fail under
    pytest. Pointing the loop-config path at a fresh, empty temp dir makes
    ``loop_config.load()`` return the built-in defaults (``engine=local``) everywhere.
    Tests that need a specific loop config monkeypatch ``loop_config.load`` directly
    (which overrides this) or write to the path this fixture installs.
    """
    cfg = tmp_path_factory.mktemp("loopcfg") / "loop.yaml"
    monkeypatch.setattr("speakloop.config.paths.loop_config_path", lambda: cfg)


@pytest.fixture(autouse=True)
def _isolate_keyboard(monkeypatch):
    """Keep the real controlling terminal out of the test suite (012).

    ``make_key_reader()`` returns a raw-capable ``RawKeyReader`` whenever a tty is
    reachable, and it probes ``/dev/tty`` directly (``keyboard.py:222``) — bypassing
    pytest's stdin capture. So when the suite is launched from an interactive shell the
    listen loop takes the real ``play_interruptible`` audio path instead of the injected
    ``play_fn`` / mocked ``playback.play``, and several integration tests fail with
    ``PlaybackError`` (e.g. ``asr_fallback``, ``phase_a_listen``, ``daily_loop``,
    ``followups_stage``). That made the suite pass in CI / piped runs but fail when run by
    hand in Terminal. Forcing a ``NullKeyReader`` makes the keyboard deterministic
    regardless of where pytest is launched (testing rule: never touch the real keyboard).
    Tests that exercise raw/interactive behavior construct a ``FakeKeyReader`` and inject
    it explicitly, which overrides this.
    """
    from speakloop.sessions.keyboard import NullKeyReader

    monkeypatch.setattr(
        "speakloop.sessions.keyboard.make_key_reader", lambda: NullKeyReader()
    )


@pytest.fixture
def wav_fixture():
    """Return a callable `(name) -> Path` that locates a fixture WAV.

    Looks under `tests/fixtures/wav/tts/<name>` and
    `tests/fixtures/wav/recordings/<name>` and returns the first match.
    """

    def _resolve(name: str) -> Path:
        for sub in ("tts", "recordings"):
            candidate = FIXTURES_DIR / "wav" / sub / name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"WAV fixture not found: {name}")

    return _resolve


@pytest.fixture
def transcript_fixture():
    """Return a callable `(name) -> Path` to a transcript fixture."""

    def _resolve(name: str) -> Path:
        candidate = FIXTURES_DIR / "transcripts" / name
        if not candidate.exists():
            raise FileNotFoundError(f"Transcript fixture not found: {name}")
        return candidate

    return _resolve


@pytest.fixture
def qa_fixture():
    """Return a callable `(name) -> Path` to a Q&A YAML fixture."""

    def _resolve(name: str) -> Path:
        candidate = FIXTURES_DIR / "qa" / name
        if not candidate.exists():
            raise FileNotFoundError(f"Q&A fixture not found: {name}")
        return candidate

    return _resolve


@pytest.fixture
def tmp_models_dir(tmp_path: Path) -> Path:
    """A scratch models directory rooted at tmp_path."""
    d = tmp_path / "models"
    d.mkdir(parents=True, exist_ok=True)
    paths.set_models_dir(d)
    yield d
    paths.set_models_dir(None)


@pytest.fixture
def tmp_sessions_dir(tmp_path: Path) -> Path:
    """A scratch sessions directory rooted at tmp_path."""
    d = tmp_path / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    paths.set_sessions_dir(d)
    yield d
    paths.set_sessions_dir(None)


@pytest.fixture
def tmp_qa_file(tmp_path: Path) -> Path:
    """A scratch Q&A file path rooted at tmp_path."""
    f = tmp_path / "qa.yaml"
    paths.set_qa_file_path(f)
    yield f
    paths.set_qa_file_path(None)


@pytest.fixture
def default_questions_text() -> str:
    """Text of the in-repo default question file (repo-root content/questions.yaml).

    Resolved relative to this file so it is cwd-independent. 004 relocated the
    shipped questions here from the old packaged starter.yaml.
    """
    repo_root = Path(__file__).resolve().parent.parent
    return (repo_root / "content" / "questions.yaml").read_text(encoding="utf-8")


@pytest.fixture
def starter_question_id(default_questions_text: str) -> str:
    """The first question id in the in-repo default content/questions.yaml.

    Robust to edits of the question set: tests that drive the listen flow pick a
    real id at runtime instead of hardcoding one.
    """
    import yaml

    return yaml.safe_load(default_questions_text)["questions"][0]["id"]
