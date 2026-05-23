"""T082 — Qwen wrapper: think-tag stripping, response shape, error wrapping,
plus regressions for the real `mlx_lm==0.31.3` API surface (load path,
sampler= kwarg, missing-model guard)."""

from __future__ import annotations

import sys
import types

import pytest

from speakloop.llm.interface import LLMEngineError
from speakloop.llm.qwen_engine import QwenEngine

pytestmark = pytest.mark.unit


def test_strip_artefacts_removes_think_blocks():
    raw = "<think>plan plan plan</think>\nThe answer is forty-two."
    assert QwenEngine._strip_artefacts(raw) == "The answer is forty-two."


def test_strip_artefacts_handles_no_think():
    assert QwenEngine._strip_artefacts("Just text.") == "Just text."


def test_strip_artefacts_handles_multiple_blocks():
    raw = "<think>a</think>x<think>b</think>y"
    assert QwenEngine._strip_artefacts(raw) == "xy"


# --- Unclosed <think> hardening (truncated generation / ignored enable_thinking) --


def test_strip_artefacts_closed_block():
    # (i) closed block — removed, surrounding text kept.
    raw = '<think>reason here</think>{"patterns": []}'
    assert QwenEngine._strip_artefacts(raw) == '{"patterns": []}'


def test_strip_artefacts_unclosed_at_start():
    # (ii) unclosed <think> at the start, no </think> → strip to end (empty).
    raw = "<think>the model kept reasoning and never closed the tag"
    assert QwenEngine._strip_artefacts(raw) == ""


def test_strip_artefacts_unclosed_mid_text():
    # (iii) valid output, then a truncated unclosed <think> → keep the prefix,
    # drop from the lone <think> to end of text.
    raw = '{"patterns": []}\n<think>oops, ran out of tokens mid-thought'
    assert QwenEngine._strip_artefacts(raw) == '{"patterns": []}'


def test_strip_artefacts_no_think_unchanged():
    # (iv) no <think> at all → unchanged (modulo strip).
    assert QwenEngine._strip_artefacts('{"patterns": []}') == '{"patterns": []}'


def test_strip_artefacts_closed_then_unclosed():
    raw = "<think>a</think>answer<think>b truncated"
    assert QwenEngine._strip_artefacts(raw) == "answer"


def test_strip_artefacts_leaves_no_think_substring():
    # The whole point: nothing that would trip analyze()'s leakage guard survives.
    for raw in (
        "<think>x</think> ok",
        "<think>unclosed",
        "prefix <think>unclosed tail",
    ):
        assert "<think>" not in QwenEngine._strip_artefacts(raw)


def test_engine_failure_wraps_into_llm_engine_error(monkeypatch):
    """If _load raises, the wrapper propagates the underlying exception
    (the wrapper only wraps mlx_lm generation failures into LLMEngineError
    — load failures are already LLMEngineError or test-injected exceptions)."""
    engine = QwenEngine()

    def boom(*args, **kwargs):
        raise RuntimeError("mlx_lm not importable")

    monkeypatch.setattr(QwenEngine, "_load", boom)

    with pytest.raises(RuntimeError):
        engine.generate("sys", "user")


# ---------------------------------------------------------------------------
# Regression tests for the real mlx_lm 0.31.3 surface.
# ---------------------------------------------------------------------------


class _FakeTokenizer:
    def apply_chat_template(self, messages, **kwargs):
        # Match the real signature: must accept tokenize, add_generation_prompt,
        # and (for Qwen3.x) enable_thinking.
        assert kwargs.get("tokenize") is False
        assert kwargs.get("add_generation_prompt") is True
        return "RENDERED_PROMPT"


def _install_fake_mlx_lm(
    monkeypatch, *, generate_impl, make_sampler_impl, load_impl=None, make_logits_impl=None
):
    """Install a stand-in `mlx_lm` (and `mlx_lm.sample_utils`) in sys.modules."""
    fake_mlx_lm = types.ModuleType("mlx_lm")
    fake_mlx_lm.generate = generate_impl
    if load_impl is not None:
        fake_mlx_lm.load = load_impl
    fake_sample_utils = types.ModuleType("mlx_lm.sample_utils")
    fake_sample_utils.make_sampler = make_sampler_impl
    # The wrapper now also builds repetition logits processors (006); provide a
    # default stub so callers that don't care about it still work.
    fake_sample_utils.make_logits_processors = make_logits_impl or (lambda **k: [])
    fake_mlx_lm.sample_utils = fake_sample_utils
    monkeypatch.setitem(sys.modules, "mlx_lm", fake_mlx_lm)
    monkeypatch.setitem(sys.modules, "mlx_lm.sample_utils", fake_sample_utils)


def test_generate_passes_sampler_not_temp_kwarg(monkeypatch):
    """generate_step has no `temp=` parameter — the wrapper must construct a
    sampler via make_sampler and pass `sampler=` instead. Regression for the
    runtime TypeError that the old wrapper would have produced."""
    engine = QwenEngine()
    monkeypatch.setattr(
        engine, "_load", lambda: ("FAKE_MODEL", _FakeTokenizer())
    )

    captured_generate_kwargs: dict = {}
    captured_sampler_kwargs: list[dict] = []

    def fake_generate(model, tokenizer, **kwargs):
        captured_generate_kwargs.update(kwargs)
        # Mirror the real generate_step strictness so future regressions are caught.
        if "temp" in kwargs or "temperature" in kwargs:
            raise TypeError(
                "generate_step() got an unexpected keyword argument 'temp'"
            )
        return "GENERATED"

    def fake_make_sampler(**kwargs):
        captured_sampler_kwargs.append(kwargs)
        return "SAMPLER_CALLABLE"

    _install_fake_mlx_lm(
        monkeypatch,
        generate_impl=fake_generate,
        make_sampler_impl=fake_make_sampler,
    )

    result = engine.generate("sys", "user", max_tokens=128, temperature=0.5)

    assert result == "GENERATED"
    assert captured_generate_kwargs.get("sampler") == "SAMPLER_CALLABLE"
    assert captured_generate_kwargs.get("max_tokens") == 128
    assert captured_generate_kwargs.get("prompt") == "RENDERED_PROMPT"
    assert "temp" not in captured_generate_kwargs
    assert "temperature" not in captured_generate_kwargs

    # The sampler is built from the user-supplied temperature plus the
    # Qwen non-thinking defaults from research_llm.md.
    assert captured_sampler_kwargs == [
        {"temp": 0.5, "top_p": 0.8, "top_k": 20, "min_p": 0.0}
    ]


def test_load_uses_manifest_local_path_not_parent(monkeypatch, tmp_path):
    """_load must pass the Qwen-specific subdirectory to mlx_lm.load, not the
    parent models_dir (which contains Kokoro/Parakeet/Qwen siblings)."""
    from speakloop.config import paths
    from speakloop.installer.manifest import QWEN3_8B_4BIT

    paths.set_models_dir(tmp_path / "models")
    try:
        qwen_dir = QWEN3_8B_4BIT.local_path
        qwen_dir.mkdir(parents=True, exist_ok=True)
        # Sanity: it must be a subdir of models_dir, not models_dir itself.
        assert qwen_dir.parent == paths.models_dir()
        assert qwen_dir != paths.models_dir()

        captured: dict = {}

        def fake_load(path, **kwargs):
            captured["path"] = path
            return "MODEL", "TOKENIZER"

        _install_fake_mlx_lm(
            monkeypatch,
            generate_impl=lambda *a, **k: "",
            make_sampler_impl=lambda **k: "S",
            load_impl=fake_load,
        )

        engine = QwenEngine()
        engine._load()

        assert captured["path"] == str(qwen_dir)
        assert captured["path"] != str(paths.models_dir())
    finally:
        paths.set_models_dir(None)


def test_load_raises_llmengineerror_when_model_dir_missing(monkeypatch, tmp_path):
    """A missing model directory must produce LLMEngineError ('not found'),
    not a raw mlx_lm FileNotFoundError. Mirrors the Kokoro/Parakeet guard."""
    from speakloop.config import paths

    paths.set_models_dir(tmp_path / "models")  # parent exists but Qwen subdir does not
    try:
        _install_fake_mlx_lm(
            monkeypatch,
            generate_impl=lambda *a, **k: "",
            make_sampler_impl=lambda **k: "S",
            load_impl=lambda *a, **k: ("M", "T"),
        )

        engine = QwenEngine()
        with pytest.raises(LLMEngineError, match="not found"):
            engine._load()
    finally:
        paths.set_models_dir(None)


def test_build_prompt_falls_back_when_template_rejects_enable_thinking():
    """Older tokenizer templates may not accept `enable_thinking=`. The
    wrapper must fall back to a templated call without the flag rather
    than crash."""

    class _StrictTokenizer:
        def __init__(self):
            self.calls: list[dict] = []

        def apply_chat_template(self, messages, **kwargs):
            self.calls.append(dict(kwargs))
            if "enable_thinking" in kwargs:
                raise TypeError(
                    "apply_chat_template() got an unexpected keyword argument "
                    "'enable_thinking'"
                )
            return "FALLBACK_PROMPT"

    tok = _StrictTokenizer()
    rendered = QwenEngine._build_prompt(tok, "sys", "user")

    assert rendered == "FALLBACK_PROMPT"
    # Two calls: first with enable_thinking=False, second without.
    assert len(tok.calls) == 2
    assert tok.calls[0].get("enable_thinking") is False
    assert "enable_thinking" not in tok.calls[1]
