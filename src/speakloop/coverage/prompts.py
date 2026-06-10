"""Coverage prompt loaders (010-interview-loop, P3).

Mirror ``feedback.cloud_prompt``: each packaged default is seeded into a
user-editable file under ``~/.speakloop/`` on first use, then read verbatim.
"""

from __future__ import annotations

from pathlib import Path

from speakloop.config import paths

_KEYPOINTS_DEFAULT = Path(__file__).parent / "keypoints_prompt_default.txt"
_COVERAGE_DEFAULT = Path(__file__).parent / "coverage_prompt_default.txt"


def _seed_and_read(target: Path, default: Path) -> tuple[str, Path]:
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(default.read_text(encoding="utf-8"), encoding="utf-8")
    return target.read_text(encoding="utf-8"), target


def load_keypoints_prompt() -> tuple[str, Path]:
    return _seed_and_read(paths.openrouter_keypoints_prompt_path(), _KEYPOINTS_DEFAULT)


def load_coverage_prompt() -> tuple[str, Path]:
    return _seed_and_read(paths.openrouter_coverage_prompt_path(), _COVERAGE_DEFAULT)
