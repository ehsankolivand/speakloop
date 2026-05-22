"""T-G4 — the wrapper applies the Qwen3-8B non-thinking generation config
(grammar-output-schema §B). Asserted via a monkeypatched `mlx_lm` — no live model.

Default:  temperature=0.7, top_p=0.8, top_k=20, min_p=0, repetition_penalty=1.05,
          repetition_context_size=40, stop=["<|im_end|>"], enable_thinking=False.
Retry:    repetition_penalty raised (~1.15), temperature lowered (~-0.1) — the
          wrapper owns these (no call-site engine-config leakage, Principle V).
"""

from __future__ import annotations

import sys
import types

import pytest

from speakloop.llm.qwen_engine import QwenEngine

pytestmark = pytest.mark.unit


class _FakeTokenizer:
    def __init__(self) -> None:
        self.template_kwargs: dict = {}

    def apply_chat_template(self, messages, **kwargs):
        self.template_kwargs = dict(kwargs)
        return "RENDERED_PROMPT"


def _install_fake_mlx_lm(monkeypatch, *, generate_impl, make_sampler_impl, make_logits_impl):
    fake = types.ModuleType("mlx_lm")
    fake.generate = generate_impl
    su = types.ModuleType("mlx_lm.sample_utils")
    su.make_sampler = make_sampler_impl
    su.make_logits_processors = make_logits_impl
    fake.sample_utils = su
    monkeypatch.setitem(sys.modules, "mlx_lm", fake)
    monkeypatch.setitem(sys.modules, "mlx_lm.sample_utils", su)


def _wire(monkeypatch):
    engine = QwenEngine()
    tok = _FakeTokenizer()
    monkeypatch.setattr(engine, "_load", lambda: ("FAKE_MODEL", tok))
    gen_kwargs: dict = {}
    sampler_calls: list[dict] = []
    logits_calls: list[dict] = []

    def fake_generate(model, tokenizer, **kwargs):
        gen_kwargs.update(kwargs)
        return "GENERATED<|im_end|> leaked tail that must be cut"

    _install_fake_mlx_lm(
        monkeypatch,
        generate_impl=fake_generate,
        make_sampler_impl=lambda **k: sampler_calls.append(k) or "SAMPLER",
        make_logits_impl=lambda **k: logits_calls.append(k) or ["LOGITS_PROC"],
    )
    return engine, tok, gen_kwargs, sampler_calls, logits_calls


def test_default_generation_config(monkeypatch):
    engine, tok, gen_kwargs, sampler_calls, logits_calls = _wire(monkeypatch)
    out = engine.generate("sys", "user", max_tokens=512)

    assert sampler_calls == [{"temp": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0}]
    assert logits_calls == [{"repetition_penalty": 1.05, "repetition_context_size": 40}]
    assert gen_kwargs.get("sampler") == "SAMPLER"
    assert gen_kwargs.get("logits_processors") == ["LOGITS_PROC"]
    assert gen_kwargs.get("max_tokens") == 512
    assert gen_kwargs.get("prompt") == "RENDERED_PROMPT"
    assert "temp" not in gen_kwargs and "temperature" not in gen_kwargs
    assert tok.template_kwargs.get("enable_thinking") is False
    # Defensive EOS: output is truncated at the stop marker.
    assert QwenEngine._STOP == ["<|im_end|>"]
    assert out == "GENERATED"


def test_retry_raises_repetition_penalty_and_lowers_temperature(monkeypatch):
    engine, _tok, _gen, sampler_calls, logits_calls = _wire(monkeypatch)
    engine.generate("sys", "user", retry=True)

    assert sampler_calls == [{"temp": 0.6, "top_p": 0.8, "top_k": 20, "min_p": 0.0}]
    assert logits_calls == [{"repetition_penalty": 1.15, "repetition_context_size": 40}]


def test_stop_marker_truncates_even_without_think(monkeypatch):
    engine, _t, _g, _s, _l = _wire(monkeypatch)
    out = engine.generate("sys", "user")
    assert "<|im_end|>" not in out
    assert out == "GENERATED"
