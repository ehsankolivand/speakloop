"""Qwen3-8B (MLX 4-bit) LLM wrapper.

This is the ONLY file in the repo allowed to ``import mlx_lm``
(Constitution Principle V, audited by T109).

Real API (verified via ``inspect.signature`` against installed ``mlx_lm==0.31.3``):

    mlx_lm.load(path_or_hf_repo, ...) -> (nn.Module, TokenizerWrapper)
    mlx_lm.generate(model, tokenizer, prompt, verbose=False, **kwargs) -> str
        kwargs forwarded → stream_generate → generate_step.
        generate_step accepts {max_tokens, sampler, logits_processors, …};
        there is NO ``temp=`` parameter — sampling is done via a callable
        built with ``mlx_lm.sample_utils.make_sampler(temp=…, top_p=…,
        top_k=…, min_p=…)`` and passed as ``sampler=``.

Thinking mode: the Qwen3 chat template honors ``enable_thinking=False``
(verified on the live tokenizer template for ``mlx-community/Qwen3-8B-4bit``),
which suppresses the documented ``<think>`` leak. We still strip any
residual ``<think>`` blocks defensively.
"""

from __future__ import annotations

import re

from speakloop.installer.manifest import QWEN3_8B_4BIT
from speakloop.llm.interface import LLMEngineError

_THINK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL)
# A lone, unclosed ``<think>`` (no ``</think>``) — happens when generation is
# truncated at max_tokens or the chat template ignores ``enable_thinking``.
# Strip from the opening tag to end of text.
_THINK_UNCLOSED_RE = re.compile(r"<think>.*\Z", flags=re.DOTALL)


class QwenEngine:
    """Local Qwen3-8B generator. Offline-only (FR-023)."""

    # Defensive EOS (research_llm.md Rec 10 / grammar-output-schema §B): mlx-lm's
    # generation API has no `stop=` parameter, so the stop marker is applied as
    # wrapper-side truncation — any text from "<|im_end|>" onward is cut.
    _STOP = ["<|im_end|>"]

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return self._model, self._tokenizer
        try:
            from mlx_lm import load  # type: ignore
        except ImportError as e:
            raise LLMEngineError(
                "mlx_lm is not installed. Install the Phase-C model bundle."
            ) from e

        model_path = QWEN3_8B_4BIT.local_path
        if not model_path.exists():
            raise LLMEngineError(
                f"Qwen model not found at {model_path}. "
                "Run `speakloop practice` to consent and download it."
            )

        try:
            self._model, self._tokenizer = load(str(model_path))
        except Exception as e:
            raise LLMEngineError(f"Qwen load failed from {model_path}: {e}") from e
        return self._model, self._tokenizer

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        retry: bool = False,
    ) -> str:
        # _load may raise LLMEngineError or a user-supplied exception (tests
        # monkeypatch this) — let those propagate before we touch mlx_lm.
        model, tokenizer = self._load()

        try:
            from mlx_lm import generate as _mlx_generate  # type: ignore
            from mlx_lm.sample_utils import (  # type: ignore
                make_logits_processors,
                make_sampler,
            )
        except ImportError as e:  # pragma: no cover — _load would have caught it
            raise LLMEngineError("mlx_lm is not installed.") from e

        prompt = self._build_prompt(tokenizer, system_prompt, user_prompt)
        # Qwen3-8B non-thinking config (research_llm.md / grammar-output-schema §B):
        # temperature=0.7, top_p=0.8, top_k=20, min_p=0, repetition_penalty=1.05,
        # repetition_context_size=40. A bounded regenerate (retry=True) breaks a
        # repetition loop by raising repetition_penalty and lowering temperature —
        # both owned HERE so no engine config leaks to the call site (Principle V).
        temp = round(temperature - 0.1, 2) if retry else temperature
        repetition_penalty = 1.15 if retry else 1.05
        sampler = make_sampler(temp=temp, top_p=0.8, top_k=20, min_p=0.0)
        logits_processors = make_logits_processors(
            repetition_penalty=repetition_penalty,
            repetition_context_size=40,
        )
        try:
            text = _mlx_generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                sampler=sampler,
                logits_processors=logits_processors,
            )
        except Exception as e:
            raise LLMEngineError(f"Qwen generation failed: {e}") from e

        return self._strip_artefacts(text)

    @staticmethod
    def _build_prompt(tokenizer, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        if not hasattr(tokenizer, "apply_chat_template"):
            return f"{system}\n\n{user}"
        # `add_generation_prompt=True` matches the example in research_llm.md
        # so the rendered prompt ends with the assistant turn cue.
        kwargs = {"tokenize": False, "add_generation_prompt": True}
        # Belt-and-suspenders against the documented Qwen3-8B `<think>` leak.
        # Qwen3.5 templates accept the flag; older templates may not — fall
        # back rather than crash.
        try:
            return tokenizer.apply_chat_template(
                messages, enable_thinking=False, **kwargs
            )
        except TypeError:
            return tokenizer.apply_chat_template(messages, **kwargs)

    @staticmethod
    def _strip_artefacts(text: str) -> str:
        """Apply defensive EOS, then strip ``<think>`` artefacts that slip through.

        First truncates at any ``_STOP`` marker (``<|im_end|>``) — the wrapper's
        stand-in for a ``stop`` parameter the mlx-lm generate API does not expose.
        Then removes closed ``<think>...</think>`` blocks and any lone unclosed
        ``<think>`` (truncated generation / ignored ``enable_thinking``) from the
        opening tag to end of text, so no ``<think>`` substring survives to trip
        the analyzer's leakage guard.
        """
        for stop in QwenEngine._STOP:
            idx = text.find(stop)
            if idx != -1:
                text = text[:idx]
        text = _THINK_RE.sub("", text)
        text = _THINK_UNCLOSED_RE.sub("", text)
        return text.strip()
