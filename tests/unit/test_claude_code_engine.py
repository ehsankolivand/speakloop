"""Unit tests for the Claude Code engine (011) — fake runner only, never the real CLI."""

from __future__ import annotations

import subprocess

import pytest

from speakloop.llm.claude_code_engine import (
    OBSERVED_CLI_VERSION,
    STRIPPED_ENV_VARS,
    ClaudeCodeAuthError,
    ClaudeCodeBadOutputError,
    ClaudeCodeEngine,
    ClaudeCodeError,
    ClaudeCodeNotInstalledError,
    ClaudeCodeRateLimitError,
    ClaudeCodeTimeoutError,
    build_env,
    doctor_probe,
)
from speakloop.llm.interface import LLMEngineError

pytestmark = pytest.mark.unit


def _engine(fake_claude, results, **kw):
    return ClaudeCodeEngine(model="haiku", runner=fake_claude.Runner(results), **kw)


# --- success path ------------------------------------------------------------


def test_success_returns_result_stripped(fake_claude):
    eng = _engine(fake_claude, fake_claude.success("  {\"a\": 1}  "))
    assert eng.generate("sys", "user") == '{"a": 1}'


def test_fenced_output_passes_through_for_the_recovery_ladder(fake_claude):
    # The engine returns the model text verbatim (minus outer whitespace); the
    # caller's _extract_json ladder strips ```json fences — NOT the engine.
    fenced = "```json\n{\"ok\": true}\n```"
    eng = _engine(fake_claude, fake_claude.success(fenced))
    assert eng.generate("sys", "user") == fenced


def test_argv_carries_the_pinned_flags(fake_claude):
    runner = fake_claude.Runner(fake_claude.success("{}"))
    ClaudeCodeEngine(model="sonnet", runner=runner).generate("SYS", "USER")
    argv = runner.calls[0].argv
    assert argv[0] == "claude"
    assert "--print" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert "--safe-mode" in argv and "--bare" not in argv
    assert argv[argv.index("--tools") + 1] == ""  # disables all tools
    assert "--no-session-persistence" in argv
    assert argv[argv.index("--system-prompt") + 1] == "SYS"
    # user prompt goes on stdin, not argv
    assert runner.calls[0].stdin == "USER"
    assert "USER" not in argv


def test_max_tokens_and_temperature_are_ignored(fake_claude):
    runner = fake_claude.Runner(fake_claude.success("{}"))
    ClaudeCodeEngine(model="haiku", runner=runner).generate(
        "sys", "user", max_tokens=99, temperature=0.0
    )
    argv = runner.calls[0].argv
    assert "--max-tokens" not in argv and "--temperature" not in argv
    assert "99" not in argv and "0.0" not in argv


def test_custom_timeout_is_threaded_to_the_runner(fake_claude):
    runner = fake_claude.Runner(fake_claude.success("{}"))
    ClaudeCodeEngine(model="haiku", runner=runner, timeout=42.0).generate("sys", "user")
    assert runner.calls[0].timeout == 42.0


def test_retry_nudges_user_prompt_keeping_system_verbatim(fake_claude):
    runner = fake_claude.Runner(fake_claude.success("{}"))
    ClaudeCodeEngine(model="haiku", runner=runner).generate("SYS", "USER", retry=True)
    call = runner.calls[0]
    assert call.argv[call.argv.index("--system-prompt") + 1] == "SYS"  # system unchanged
    assert call.stdin.startswith("USER")
    assert "STRICT JSON" in call.stdin  # reminder appended to USER prompt


# --- error taxonomy ----------------------------------------------------------


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        (FileNotFoundError(), ClaudeCodeNotInstalledError),
        (subprocess.TimeoutExpired(cmd="claude", timeout=90), ClaudeCodeTimeoutError),
    ],
)
def test_subprocess_exceptions_map_to_taxonomy(fake_claude, results, expected):
    eng = _engine(fake_claude, results)
    with pytest.raises(expected):
        eng.generate("sys", "user")


@pytest.mark.parametrize(
    ("result_text", "expected"),
    [
        ("Not logged in · Please run /login", ClaudeCodeAuthError),
        ("You are logged out", ClaudeCodeAuthError),
        ("Usage limit reached", ClaudeCodeRateLimitError),
        ("Rate limit exceeded", ClaudeCodeRateLimitError),
        ("Insufficient credit balance", ClaudeCodeRateLimitError),
        ("Model is overloaded", ClaudeCodeRateLimitError),
        ("Some other unexpected failure", ClaudeCodeError),
    ],
)
def test_error_envelope_classified_by_result_text(fake_claude, result_text, expected):
    eng = _engine(fake_claude, fake_claude.error(result_text))
    with pytest.raises(expected):
        eng.generate("sys", "user")


def test_non_json_output_is_bad_output_with_version_hint(fake_claude):
    eng = _engine(fake_claude, fake_claude.non_json(stderr="error: unknown option '--gone'"))
    with pytest.raises(ClaudeCodeBadOutputError) as ei:
        eng.generate("sys", "user")
    assert OBSERVED_CLI_VERSION in str(ei.value)
    assert "unknown option" in str(ei.value)


def test_non_object_json_is_bad_output(fake_claude):
    eng = _engine(fake_claude, fake_claude.cli_result("[1, 2, 3]"))
    with pytest.raises(ClaudeCodeBadOutputError):
        eng.generate("sys", "user")


def test_success_envelope_missing_result_is_bad_output(fake_claude):
    eng = _engine(fake_claude, fake_claude.cli_result('{"is_error": false}'))
    with pytest.raises(ClaudeCodeBadOutputError):
        eng.generate("sys", "user")


@pytest.mark.parametrize("result_json", ['123', 'true', '{}', '[1, 2]', 'null'])
def test_non_string_result_is_bad_output(fake_claude, result_json):
    # The .result field must be a string; numbers/bools/objects/null are rejected.
    eng = _engine(fake_claude, fake_claude.cli_result(f'{{"is_error": false, "result": {result_json}}}'))
    with pytest.raises(ClaudeCodeBadOutputError):
        eng.generate("sys", "user")


def test_all_errors_are_llm_engine_errors(fake_claude):
    # The coordinator catches LLMEngineError/Exception → analysis_pending; every
    # taxonomy class MUST be an LLMEngineError so that degradation is unchanged.
    for cls in (
        ClaudeCodeNotInstalledError,
        ClaudeCodeAuthError,
        ClaudeCodeRateLimitError,
        ClaudeCodeTimeoutError,
        ClaudeCodeBadOutputError,
        ClaudeCodeError,
    ):
        assert issubclass(cls, LLMEngineError)


# --- billing safety: ANTHROPIC_API_KEY never reaches the subprocess ----------


def test_build_env_strips_all_billing_override_vars(monkeypatch):
    for var in STRIPPED_ENV_VARS:
        monkeypatch.setenv(var, "should-be-removed")
    monkeypatch.setenv("PATH", "/keep/me")
    env = build_env()
    for var in STRIPPED_ENV_VARS:
        assert var not in env
    assert env["PATH"] == "/keep/me"  # unrelated vars preserved


def test_generate_never_passes_anthropic_api_key_to_runner(fake_claude, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-pay-per-token")
    runner = fake_claude.Runner(fake_claude.success("{}"))
    ClaudeCodeEngine(model="haiku", runner=runner).generate("sys", "user")
    assert "ANTHROPIC_API_KEY" not in runner.calls[0].env


# --- doctor probe (monkeypatched; no real binary) ----------------------------


def test_doctor_probe_not_installed(monkeypatch):
    monkeypatch.setattr("speakloop.llm.claude_code_engine.shutil.which", lambda _b: None)
    info = doctor_probe()
    assert info["installed"] is False
    assert info["binary"] is None


def test_doctor_probe_logged_in(monkeypatch, fake_claude):
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.shutil.which", lambda _b: "/opt/claude"
    )

    def fake_status_run(argv, timeout):
        if "--version" in argv:
            return fake_claude.cli_result("2.1.170 (Claude Code)")
        return fake_claude.cli_result(
            '{"loggedIn": true, "authMethod": "claude.ai", "subscriptionType": "max"}'
        )

    monkeypatch.setattr("speakloop.llm.claude_code_engine._status_run", fake_status_run)
    info = doctor_probe()
    assert info["installed"] is True
    assert info["binary"] == "/opt/claude"
    assert info["version"] == "2.1.170"
    assert info["logged_in"] is True
    assert info["auth_method"] == "claude.ai"
    assert info["subscription_type"] == "max"


def test_doctor_probe_logged_out(monkeypatch, fake_claude):
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.shutil.which", lambda _b: "/opt/claude"
    )

    def fake_status_run(argv, timeout):
        if "--version" in argv:
            return fake_claude.cli_result("2.1.170 (Claude Code)")
        return fake_claude.cli_result('{"loggedIn": false}')

    monkeypatch.setattr("speakloop.llm.claude_code_engine._status_run", fake_status_run)
    info = doctor_probe()
    assert info["logged_in"] is False


def test_doctor_probe_flags_api_key_in_env(monkeypatch):
    monkeypatch.setattr("speakloop.llm.claude_code_engine.shutil.which", lambda _b: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert doctor_probe()["api_key_in_env"] is True
