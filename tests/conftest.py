"""Shared pytest fixtures.

Engine tests use cached fixture WAVs / transcripts committed under
`tests/fixtures/`. **No live model calls.** (Constitution Dev Guidelines.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.config import paths

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
def starter_question_id() -> str:
    """The first question id in the shipped starter.yaml.

    Robust to edits of `starter.yaml`: tests that drive the listen flow off the
    shipped starter (which `_ensure_starter_qa` copies into a fresh qa.yaml) pick
    a real id at runtime instead of hardcoding one.
    """
    from importlib import resources

    import yaml

    text = resources.files("speakloop.content").joinpath("starter.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)["questions"][0]["id"]
