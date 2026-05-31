"""T018 (007) — token resolution + no-leak invariants.

Contracts: `contracts/token-resolution-contract.md §2` (resolution table) and §6
(5 negative tests).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from speakloop.installer.tokens import ResolvedToken, resolve_token

pytestmark = pytest.mark.unit


@pytest.fixture
def hf_token_file(monkeypatch, tmp_path):
    """Redirect `~/.cache/huggingface/token` into the tmp tree.

    Returns a (path-creator, path) pair so individual tests can populate the
    file (or leave it absent / empty) before calling `resolve_token()`.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))
    token_path = fake_home / ".cache" / "huggingface" / "token"
    token_path.parent.mkdir(parents=True, exist_ok=True)

    def _set(contents: str | None) -> Path:
        if contents is None:
            if token_path.exists():
                token_path.unlink()
        else:
            token_path.write_text(contents)
        return token_path

    return _set, token_path


# ----- resolution table (contract §2) ------------------------------------- #


def test_env_wins_over_file(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter("hf_filecontents_xyz")
    monkeypatch.setenv("HF_TOKEN", "hf_envvalue_abc")

    r = resolve_token()
    assert r.value == "hf_envvalue_abc"
    assert r.source == "env"


def test_env_set_without_file(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter(None)
    monkeypatch.setenv("HF_TOKEN", "hf_envonly")

    r = resolve_token()
    assert r.value == "hf_envonly"
    assert r.source == "env"


def test_file_only(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter("hf_fileonly\n")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    r = resolve_token()
    assert r.value == "hf_fileonly"  # trailing newline stripped
    assert r.source == "hf_cli_file"


def test_anonymous_when_nothing_set(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter(None)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    r = resolve_token()
    assert r.value is None
    assert r.source == "anonymous"


# ----- negative tests (contract §6) --------------------------------------- #


def test_empty_env_and_no_file_anonymous(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter(None)
    monkeypatch.setenv("HF_TOKEN", "")

    r = resolve_token()
    assert r.value is None
    assert r.source == "anonymous"


def test_whitespace_only_file_anonymous(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter("   \n  ")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    r = resolve_token()
    assert r.value is None
    assert r.source == "anonymous"


def test_repr_redacts_token_value(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter(None)
    monkeypatch.setenv("HF_TOKEN", "hf_secret_should_not_leak_xyz_abc")

    r = resolve_token()
    text = repr(r)
    assert "hf_secret_should_not_leak_xyz_abc" not in text
    assert "redacted" in text.lower()


def test_resolve_token_does_not_write_to_environ(monkeypatch, hf_token_file):
    setter, _ = hf_token_file
    setter(None)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    before = dict(os.environ)
    resolve_token()
    assert dict(os.environ) == before, "resolve_token must not mutate os.environ"


def test_repr_of_anonymous_is_safe():
    r = ResolvedToken(value=None, source="anonymous")
    text = repr(r)
    assert "anonymous" in text
    assert "<redacted>" in text
