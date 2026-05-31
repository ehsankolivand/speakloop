"""Qwen wrapper: leading-`<think>` stripping, response shape, error wrapping,
plus regressions for the real `mlx_lm==0.31.3` API surface (load path,
sampler= kwarg, missing-model guard)."""

from __future__ import annotations

import sys
import types

import pytest

from speakloop.llm.interface import LLMEngineError
from speakloop.llm.qwen_engine import QwenEngine

pytestmark = pytest.mark.unit


# --- Leading-<think> strip (thinking mode ON; wrapper boundary) --------------


def test_strip_artefacts_removes_leading_think_block():
    raw = "<think>plan plan plan</think>\nThe answer is forty-two."
    assert QwenEngine._strip_artefacts(raw) == "The answer is forty-two."


def test_strip_artefacts_handles_no_think():
    assert QwenEngine._strip_artefacts("Just text.") == "Just text."


def test_strip_artefacts_strips_only_the_leading_block():
    # Leading-only regex: a SECOND <think>...</think> mid-text survives.
    raw = "<think>a</think>x<think>b</think>y"
    assert QwenEngine._strip_artefacts(raw) == "x<think>b</think>y"


def test_strip_artefacts_closed_block_with_json_payload():
    raw = '<think>reason here</think>{"errors": []}'
    assert QwenEngine._strip_artefacts(raw) == '{"errors": []}'


def test_strip_artefacts_unclosed_at_start_passes_through():
    # No </think> → not a match → original text passes through (modulo strip).
    # Truncated thinking is left for the analyzer's bounded regenerate to catch.
    raw = "<think>the model kept reasoning and never closed the tag"
    assert QwenEngine._strip_artefacts(raw) == raw


def test_strip_artefacts_unclosed_mid_text_passes_through():
    # A trailing unclosed <think> after valid JSON is NOT auto-scrubbed under
    # the leading-only regex (no leading <think> here at all).
    raw = '{"errors": []}\n<think>oops, ran out of tokens mid-thought'
    assert QwenEngine._strip_artefacts(raw) == raw


def test_strip_artefacts_no_think_unchanged():
    assert QwenEngine._strip_artefacts('{"errors": []}') == '{"errors": []}'


def test_strip_artefacts_leading_closed_then_trailing_unclosed():
    # Leading closed block stripped; trailing unclosed block remains.
    raw = "<think>a</think>answer<think>b truncated"
    assert QwenEngine._strip_artefacts(raw) == "answer<think>b truncated"


def test_strip_artefacts_leading_closed_block_leaves_no_think_substring():
    # The leading-closed case is the contract we DO promise.
    assert "<think>" not in QwenEngine._strip_artefacts("<think>x</think> ok")


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
    from speakloop.installer.manifest import QWEN3_14B_4BIT

    paths.set_models_dir(tmp_path / "models")
    try:
        qwen_dir = QWEN3_14B_4BIT.local_path
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
    # Two calls: first with enable_thinking=True, second without.
    assert len(tok.calls) == 2
    assert tok.calls[0].get("enable_thinking") is True
    assert "enable_thinking" not in tok.calls[1]


# --- End-to-end strip verification through generate(...) ---------------------


def test_generate_strips_leading_think_block(monkeypatch):
    """A model response with a leading <think> block must come out clean."""
    engine = QwenEngine()
    monkeypatch.setattr(engine, "_load", lambda: ("FAKE_MODEL", _FakeTokenizer()))

    def fake_generate(model, tokenizer, **kwargs):
        return '<think>I will analyze this transcript carefully</think>{"errors": []}'

    _install_fake_mlx_lm(
        monkeypatch,
        generate_impl=fake_generate,
        make_sampler_impl=lambda **k: "S",
    )

    out = engine.generate("sys", "user")
    assert out == '{"errors": []}'
    assert "<think>" not in out


def test_generate_passes_through_response_without_think_block(monkeypatch):
    """A clean (think-free) response passes through unchanged (modulo strip)."""
    engine = QwenEngine()
    monkeypatch.setattr(engine, "_load", lambda: ("FAKE_MODEL", _FakeTokenizer()))

    def fake_generate(model, tokenizer, **kwargs):
        return '{"errors": []}'

    _install_fake_mlx_lm(
        monkeypatch,
        generate_impl=fake_generate,
        make_sampler_impl=lambda **k: "S",
    )

    out = engine.generate("sys", "user")
    assert out == '{"errors": []}'
