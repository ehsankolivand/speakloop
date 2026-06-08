"""008: OpenRouter token resolution + storage (env > file > None; 0600)."""

from __future__ import annotations

import os
import stat

import pytest

from speakloop.llm import openrouter_credentials as creds

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return tmp_path


def test_resolve_none_when_unset(_home):
    assert creds.resolve_token() is None


def test_env_takes_precedence(monkeypatch, _home):
    creds.store_token("from-file")
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert creds.resolve_token() == "from-env"


def test_empty_env_treated_as_unset(monkeypatch, _home):
    creds.store_token("from-file")
    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
    assert creds.resolve_token() == "from-file"


def test_file_used_when_no_env(_home):
    creds.store_token("  stored-token\n")
    assert creds.resolve_token() == "stored-token"


def test_store_writes_0600(_home):
    p = creds.store_token("sk-or-xyz")
    assert p.exists()
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600
    assert creds.resolve_token() == "sk-or-xyz"


def test_store_refuses_empty(_home):
    with pytest.raises(ValueError):
        creds.store_token("   ")


def test_no_import_time_io(monkeypatch, tmp_path):
    # Importing the module must not read or create anything.
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "fresh"))
    import importlib

    importlib.reload(creds)
    assert not (tmp_path / "fresh").exists()
