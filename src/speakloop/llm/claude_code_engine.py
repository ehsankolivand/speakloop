"""Claude Code CLI LLM wrapper (opt-in engine, feature 011).

This is the ONLY file in the repo that spawns the ``claude`` subprocess
(Constitution Principle V — mirrors ``openrouter_engine.py`` being the only
``urllib`` caller). It implements the stable ``LLMEngine`` Protocol by driving the
learner's locally installed, logged-in **Claude Code** product in non-interactive
print mode, so a full analysis session bills to their subscription instead of a
pay-per-token API. No new dependency — standard library ``subprocess`` only.

The subprocess is spawned only inside ``generate()`` / ``doctor_probe()`` — never
at import time — so ``speakloop --help`` stays model-free (Principle VIII).

CLI contract pinned to the observed version below: every flag, envelope field, and
error behavior used here was verified empirically against that CLI (see
``specs/011-claude-code-engine/research.md``). They are named constants so a future
incompatible CLI change fails loudly in exactly one place (FR-009).

Billing safety (FR-007): the subprocess environment is built from a COPY of
``os.environ`` with ``ANTHROPIC_API_KEY`` and related override variables removed —
Claude Code prefers such a key over subscription auth, so leaving it set would
silently switch billing to pay-per-token. ``--safe-mode`` (not ``--bare``) keeps the
subscription OAuth working after the strip; ``--bare`` would instead REQUIRE the
stripped key.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from speakloop.llm.interface import LLMEngineError

# --- Pinned CLI contract (observed `claude --version` == 2.1.170) -------------

OBSERVED_CLI_VERSION = "2.1.170"  # the Claude Code CLI this engine was written against
_BINARY = "claude"

# Flags — each verified against `claude --help` on 2.1.170.
_FLAG_PRINT = "--print"  # non-interactive single response
_FLAG_OUTPUT_FORMAT = "--output-format"
_OUTPUT_FORMAT_JSON = "json"  # single JSON envelope (see _ENV_* below)
_FLAG_MODEL = "--model"  # alias (haiku/sonnet/opus) or full id
_FLAG_SAFE_MODE = "--safe-mode"  # isolates CLAUDE.md/skills/MCP/hooks; KEEPS subscription OAuth.
#   NOTE: deliberately NOT `--bare` — `--bare` forces auth to be strictly
#   ANTHROPIC_API_KEY/apiKeyHelper (OAuth + keychain never read), which is
#   incompatible with stripping ANTHROPIC_API_KEY for billing safety.
_FLAG_TOOLS = "--tools"
_TOOLS_NONE = ""  # `--tools ""` disables all tools → guarantees a text-only response, no tool use
_FLAG_NO_SESSION = "--no-session-persistence"  # don't litter session history
_FLAG_SYSTEM_PROMPT = "--system-prompt"  # REPLACE the default system prompt with our analysis prompt

# Success envelope fields (observed 2.1.170). Success is keyed on `is_error`,
# NOT `subtype` (which stays "success" even on error).
_ENV_IS_ERROR = "is_error"
_ENV_RESULT = "result"  # the model's text output (may be wrapped in ```json fences)
_ENV_API_ERROR_STATUS = "api_error_status"

# Billing-safety: variables that would route billing off the subscription.
STRIPPED_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_API_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)

_DEFAULT_TIMEOUT = 90.0

# Error-classification substrings, matched (lowercased) against the error envelope's
# `result` / `api_error_status` text. Observed auth message: "Not logged in · Please
# run /login".
_AUTH_MARKERS = ("not logged in", "logged out", "/login", "please log in", "unauthorized")
_RATE_MARKERS = (
    "rate limit",
    "rate-limit",
    "usage limit",
    "quota",
    "credit",
    "insufficient",
    "overloaded",
    "too many requests",
)


# --- Error taxonomy (all subclass LLMEngineError so coordinator degradation works) ---


class ClaudeCodeError(LLMEngineError):
    """Base class for Claude Code engine failures (a kind of ``LLMEngineError``)."""


class ClaudeCodeNotInstalledError(ClaudeCodeError):
    """The ``claude`` binary was not found on PATH."""


class ClaudeCodeAuthError(ClaudeCodeError):
    """Claude Code is not logged in (or logged out mid-session)."""


class ClaudeCodeRateLimitError(ClaudeCodeError):
    """Claude Code usage/rate/credit window is exhausted."""


class ClaudeCodeTimeoutError(ClaudeCodeError):
    """A single call exceeded the hard per-call timeout."""


class ClaudeCodeBadOutputError(ClaudeCodeError):
    """The CLI returned non-JSON / truncated / unexpected output (likely a CLI change)."""


# --- Runner abstraction (the seam tests inject a fake at) ---------------------


@dataclass(frozen=True)
class ClaudeCliResult:
    """What a runner returns — decouples the engine from ``subprocess``."""

    stdout: str
    stderr: str
    returncode: int


# A runner spawns one CLI call: (argv, stdin_text, timeout_s, env) -> ClaudeCliResult.
# It MUST raise FileNotFoundError when the binary is absent and
# subprocess.TimeoutExpired on timeout; the engine maps both into the taxonomy.
Runner = Callable[[list[str], str, float, "dict[str, str]"], ClaudeCliResult]


def build_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Return a copy of the environment with billing-override vars removed (FR-007)."""
    base = dict(os.environ if environ is None else environ)
    for var in STRIPPED_ENV_VARS:
        base.pop(var, None)
    return base


def default_runner(
    argv: list[str], stdin: str, timeout: float, env: dict[str, str]
) -> ClaudeCliResult:
    """Spawn ``claude`` once. The ONLY subprocess spawn of the binary (Principle V).

    Raises ``FileNotFoundError`` if the binary is absent and
    ``subprocess.TimeoutExpired`` on timeout — the engine translates both."""
    proc = subprocess.run(  # noqa: S603 — argv is built from pinned constants + our prompts
        argv,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return ClaudeCliResult(
        stdout=proc.stdout or "", stderr=proc.stderr or "", returncode=proc.returncode
    )


# --- The engine --------------------------------------------------------------


class ClaudeCodeEngine:
    """LLM generator backed by the local Claude Code CLI.

    Satisfies the ``LLMEngine`` Protocol; the analyzer/runners are engine-agnostic
    and depend only on that interface.

    NOTE: the Claude Code CLI exposes neither a temperature nor a max-tokens flag,
    so ``generate()`` IGNORES both ``max_tokens`` and ``temperature`` (the engine
    owns generation details — Principle V). Output quality relies on strict-JSON
    prompting plus the caller's existing JSON-recovery ladder (which already strips
    markdown code fences). ``retry=True`` maps to one bounded re-invocation with a
    STRICT-JSON reminder appended to the USER prompt — the SYSTEM prompt is kept
    verbatim — mirroring ``OpenRouterEngine``.
    """

    def __init__(
        self,
        *,
        model: str,
        runner: Runner = default_runner,
        timeout: float = _DEFAULT_TIMEOUT,
        binary: str = _BINARY,
    ) -> None:
        self._model = model
        self._runner = runner
        self._timeout = timeout
        self._binary = binary

    def _argv(self, system_prompt: str) -> list[str]:
        return [
            self._binary,
            _FLAG_PRINT,
            _FLAG_OUTPUT_FORMAT,
            _OUTPUT_FORMAT_JSON,
            _FLAG_MODEL,
            self._model,
            _FLAG_SAFE_MODE,
            _FLAG_TOOLS,
            _TOOLS_NONE,
            _FLAG_NO_SESSION,
            _FLAG_SYSTEM_PROMPT,
            system_prompt,
        ]

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,  # ignored — see class docstring
        temperature: float = 0.7,  # ignored — see class docstring
        retry: bool = False,
    ) -> str:
        user = user_prompt
        if retry:
            user = (
                f"{user_prompt}\n\nReminder: return STRICT JSON only — a single object, "
                "no prose, no markdown code fences."
            )
        argv = self._argv(system_prompt)
        env = build_env()
        try:
            result = self._runner(argv, user, self._timeout, env)
        except FileNotFoundError:
            raise ClaudeCodeNotInstalledError(
                f"Claude Code CLI ({self._binary!r}) was not found on PATH. Install Claude "
                "Code and run `claude /login`, or choose another engine."
            ) from None
        except subprocess.TimeoutExpired:
            raise ClaudeCodeTimeoutError(
                f"Claude Code call exceeded the {self._timeout:g}s timeout and was aborted."
            ) from None
        return self._parse(result)

    def _parse(self, result: ClaudeCliResult) -> str:
        try:
            envelope = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            stderr_lines = (result.stderr or "").strip().splitlines()
            hint = stderr_lines[0] if stderr_lines else "(no stderr)"
            raise ClaudeCodeBadOutputError(
                f"Claude Code returned no JSON envelope (exit {result.returncode}); the CLI "
                f"may have changed since {OBSERVED_CLI_VERSION}. First stderr line: {hint}"
            ) from None
        if not isinstance(envelope, dict):
            raise ClaudeCodeBadOutputError(
                f"Claude Code returned a non-object JSON envelope "
                f"(CLI may have changed since {OBSERVED_CLI_VERSION})."
            )
        if envelope.get(_ENV_IS_ERROR):
            self._raise_for_error(envelope)
        text = envelope.get(_ENV_RESULT)
        if not isinstance(text, str):
            raise ClaudeCodeBadOutputError(
                f"Claude Code envelope missing a string {_ENV_RESULT!r} field "
                f"(CLI may have changed since {OBSERVED_CLI_VERSION})."
            )
        return text.strip()

    def _raise_for_error(self, envelope: dict) -> None:
        haystack = " ".join(
            str(envelope.get(k, "")) for k in (_ENV_RESULT, _ENV_API_ERROR_STATUS)
        ).lower()
        if any(m in haystack for m in _AUTH_MARKERS):
            raise ClaudeCodeAuthError(
                "Claude Code is not logged in (run `claude /login`) — analysis left pending."
            )
        if any(m in haystack for m in _RATE_MARKERS):
            raise ClaudeCodeRateLimitError(
                "Claude Code usage/rate limit reached — analysis left pending."
            )
        detail = (
            envelope.get(_ENV_RESULT) or envelope.get(_ENV_API_ERROR_STATUS) or "unknown error"
        )
        raise ClaudeCodeError(f"Claude Code returned an error: {detail}")


# --- Doctor probe (credit-free; no model call) -------------------------------


def _status_run(argv: list[str], timeout: float) -> ClaudeCliResult:
    proc = subprocess.run(  # noqa: S603 — argv is the pinned binary + fixed subcommands
        argv, capture_output=True, text=True, timeout=timeout
    )
    return ClaudeCliResult(
        stdout=proc.stdout or "", stderr=proc.stderr or "", returncode=proc.returncode
    )


def doctor_probe() -> dict:
    """Probe the Claude Code CLI for ``speakloop doctor`` — makes NO model call.

    Uses ``claude --version`` (local) and ``claude auth status --json`` (the
    credit-free auth check). Returns a dict; the doctor renders rows from it.
    Tests monkeypatch this whole function so no automated test runs the real binary.
    """
    info = {
        "installed": False,
        "binary": None,
        "version": None,
        "logged_in": None,
        "auth_method": None,
        "subscription_type": None,
        "api_key_in_env": "ANTHROPIC_API_KEY" in os.environ,
        "error": None,
    }
    path = shutil.which(_BINARY)
    if not path:
        return info
    info["installed"] = True
    info["binary"] = path
    try:
        v = _status_run([path, "--version"], timeout=10)
        info["version"] = v.stdout.strip().split()[0] if v.stdout.strip() else None
    except (OSError, subprocess.SubprocessError) as e:
        info["error"] = f"version probe failed: {e}"
    try:
        s = _status_run([path, "auth", "status", "--json"], timeout=15)
        data = json.loads(s.stdout) if s.stdout.strip() else {}
        info["logged_in"] = bool(data.get("loggedIn"))
        info["auth_method"] = data.get("authMethod")
        info["subscription_type"] = data.get("subscriptionType")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        info["error"] = f"auth probe failed: {e}"
    return info
