"""Cloud-mode coaching layer (feature 009).

A SECOND, additive OpenRouter call that runs AFTER the strict grammar analyzer
in cloud mode. It produces a free-form Markdown teaching section — a corrected
version of the speaker's OWN answer, focused teaching of their top habits, and
paste-ready Anki cards — which the coordinator appends to the report between the
grammar section and the transcripts.

Design invariants:

* This output is NEVER parsed by the grammar verify pipeline (V1–V3), so it
  cannot affect the grammar findings or their verbatim guarantee. The two calls
  are independent; this one only reads the verified/grouped patterns as input.
* The reference / ideal answer is deliberately NOT passed in, so the model fixes
  the speaker's own words instead of parroting the model answer.
* Cloud-only: the local Qwen flow never builds or calls this. It reuses the same
  injected ``LLMEngine`` (the ``OpenRouterEngine`` instance) the grammar call
  used, with its OWN system prompt (``feedback/openrouter_coach_prompt_default.txt``
  → ``~/.speakloop/openrouter_coach_prompt.txt``).
* Failures raise ``LLMEngineError``; the caller degrades gracefully (no coaching
  section, a non-fatal ``coach_error`` note) — the grammar report is never
  blocked.
"""

from __future__ import annotations

from speakloop.asr import Transcript
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.llm import LLMEngine, LLMEngineError

# Coaching is long-form prose (corrected answer + teaching + cards); give it room.
_COACH_MAX_TOKENS = 2048
# Modest temperature: natural, warm prose without drifting into invented facts
# (the prompt forbids adding technical content the speaker never attempted).
_COACH_TEMPERATURE = 0.4


def _format_patterns(patterns: list[GrammarPattern]) -> str:
    """Render the verified, grouped grammar patterns as a compact bullet list:
    each ``label`` followed by its evidence ``quote -> corrected`` pairs. This is
    the only grammar-call output the coach sees (label + per-quote correction)."""
    if not patterns:
        return "(No grammar issues were detected in the attempts this round.)"
    lines: list[str] = []
    for p in patterns:
        lines.append(f"- {p.label}:")
        for ev in p.evidence:
            quote = (ev.get("quote") or "").strip()
            corrected = (ev.get("corrected") or "").strip()
            if quote and corrected:
                lines.append(f'    - "{quote}" -> "{corrected}"')
            elif quote:
                lines.append(f'    - "{quote}"')
    return "\n".join(lines)


def build_user_prompt(
    question_text: str,
    transcripts: list[Transcript],
    patterns: list[GrammarPattern],
) -> str:
    """Assemble the coach USER message: the question, the three attempt
    transcripts, and the detected grammar issues. The ideal/reference answer is
    intentionally excluded (see module docstring)."""
    parts = [f"Interview question:\n{question_text.strip()}\n"]
    for i, t in enumerate(transcripts, start=1):
        parts.append(f"Attempt {i}:\n{t.text.strip()}\n")
    parts.append("Grammar issues already detected in their speech:\n" + _format_patterns(patterns))
    return "\n".join(parts)


def coach(
    question_text: str,
    transcripts: list[Transcript],
    patterns: list[GrammarPattern],
    llm: LLMEngine,
    *,
    system_prompt: str,
) -> str:
    """Run the coaching call and return its free-form Markdown section.

    Raises ``LLMEngineError`` on a transient API failure, a timeout, or an empty
    response — the caller catches it and degrades gracefully. The returned text
    already begins at level-2 headings, so the report appends it verbatim."""
    user_prompt = build_user_prompt(question_text, transcripts, patterns)
    markdown = llm.generate(
        system_prompt,
        user_prompt,
        max_tokens=_COACH_MAX_TOKENS,
        temperature=_COACH_TEMPERATURE,
    )
    if not markdown or not markdown.strip():
        raise LLMEngineError("Coach returned an empty response.")
    return markdown.strip()
