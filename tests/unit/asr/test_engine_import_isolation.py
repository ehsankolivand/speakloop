"""T039 — engine-specific imports are confined to their wrapper files (Principle V).

Statically scans every .py under src/speakloop and asserts that each engine-only
package is imported in exactly one allowed file (FR-011). Generalizes the guard
the v1 "T109" task intended (which covered only parakeet_mlx).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2].parent / "src" / "speakloop"

# package name -> the single file allowed to import it (relative to src/speakloop)
ENGINE_PACKAGES = {
    "mlx_whisper": "asr/whisper_mlx_engine.py",
    "parakeet_mlx": "asr/parakeet_engine.py",
    "silero_vad": "asr/vad.py",
    "onnxruntime": "asr/vad.py",
    "mlx_lm": "llm/qwen_engine.py",
    "kokoro_mlx": "tts/kokoro_engine.py",
}


def _imported_top_levels(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("package,allowed_rel", sorted(ENGINE_PACKAGES.items()))
def test_engine_package_imported_only_in_its_wrapper(package, allowed_rel):
    allowed = (SRC / allowed_rel).resolve()
    offenders = []
    for py in SRC.rglob("*.py"):
        if package in _imported_top_levels(py) and py.resolve() != allowed:
            offenders.append(str(py.relative_to(SRC)))
    assert not offenders, (
        f"{package!r} may only be imported in {allowed_rel} (Principle V); "
        f"found in: {offenders}"
    )
