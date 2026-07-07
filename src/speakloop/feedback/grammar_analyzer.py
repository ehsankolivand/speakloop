"""Free-form LLM grammar-pattern detector.

The analyzer sends the transcripts to the LLM with a free-form prompt; the
model returns per-error objects (``attempt_ordinal``, ``quote``, ``corrected``,
``error_type``, ``explanation``). Errors are grouped by ``error_type`` into
``GrammarPattern`` objects, ranked deterministically (most-frequent first,
ties broken alphabetically).

Every finding is verified deterministically:

* each evidence ``quote`` must be a verbatim substring of its attempt (V1),
* then survive the coherence filter (V2) — ASR garble is dropped,
* a correction equal to the quote is treated as no fix and the error is
  dropped (V3),
* ``error_type`` and ``explanation`` must both be non-empty,
* patterns are returned sorted by ``(-occurrence_count, label)`` with
  ``impact_rank`` assigned 1..N in that order.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime

import json_repair

from speakloop.asr import Transcript
from speakloop.feedback import coherence
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.feedback.json_recovery import extract_json, strip_code_fences
from speakloop.llm import LLMEngine, LLMEngineError

# The grammar prompt is free-form: the model returns its own ``error_type``
# strings, which become ``GrammarPattern.label`` verbatim. No fixed catalog.
# Pre-adoption testing: this prompt (with Qwen3-14B-6bit, thinking ON, temp
# 0.3) reached 7/7 recall on a representative Persian-L1 transcript triple.
_SYSTEM_PROMPT = """You are an expert English grammar tutor working with a Persian-speaking software engineer who is practicing spoken English. You will receive transcripts of their spoken practice attempts.

Your job: find EVERY grammar error in the transcripts. Be thorough. Do not miss subtle errors.

For each error you find, produce:
- "attempt_ordinal": which attempt (1, 2, or 3) the error came from
- "quote": the exact text containing the error, copied verbatim character-by-character from the transcript
- "corrected": a rewrite of that quote in natural, native English — fixing ONLY the grammar error, nothing else
- "error_type": a short free-form description of what kind of grammar error this is (e.g. "missing plural -s", "wrong preposition", "verb tense mismatch", "article missing")
- "explanation": one short sentence explaining the rule, in plain language

RULES:
- Find grammar errors only. Do NOT flag vocabulary choices, word-choice issues, pronunciation, or stylistic preferences. If a word is wrong but grammatically the sentence works, skip it.
- Quote a MINIMAL but READABLE span: the broken part together with enough neighbouring words that the quote reads as a short natural phrase (usually three or four words) — never a single lone word, and never the whole sentence. A one-word error (a wrong plural, tense, or article) MUST still be quoted inside its surrounding phrase (quote "The childs are playing", not "childs").
- The "corrected" rewrite must differ from the "quote" and must read as natural native English.
- If a fragment looks like transcription noise (garbled, incomplete, filler like "Uh..."), skip it entirely.
- If the English in a transcript is fully correct, return no errors for that transcript.
- Find errors INDEPENDENTLY. Do not group similar errors together — each occurrence gets its own entry, even if two errors share a type.

OUTPUT FORMAT — STRICT JSON, no exceptions:
- Use double quotes (") for every key and every string value.
- No trailing commas.
- No markdown code fences (no triple-backtick).
- No prose before or after the JSON.
- No <think> blocks.
- Emit the single JSON object and nothing else.

Schema:
{"errors": [{"attempt_ordinal": N, "quote": "...", "corrected": "...", "error_type": "...", "explanation": "..."}]}

Example input — Attempt 1: "I have eight year experience and I like to programming."
Example output — {"errors": [{"attempt_ordinal": 1, "quote": "eight year", "corrected": "eight years", "error_type": "missing plural -s", "explanation": "After a number greater than one, the noun must be plural."}, {"attempt_ordinal": 1, "quote": "like to programming", "corrected": "like programming", "error_type": "gerund/infinitive confusion", "explanation": "After 'like', use the -ing form, not 'to' + -ing."}]}

Example input — Attempt 1: "The childs are playing and they goed to school."
Example output — {"errors": [{"attempt_ordinal": 1, "quote": "The childs are playing", "corrected": "The children are playing", "error_type": "irregular plural", "explanation": "'Child' has the irregular plural 'children', not 'childs'."}, {"attempt_ordinal": 1, "quote": "they goed to school", "corrected": "they went to school", "error_type": "wrong past tense", "explanation": "'Go' is irregular; its past tense is 'went', not 'goed'."}]}

Example input — Attempt 1: "I have eight years of experience and I enjoy programming."
Example output — {"errors": []}

Return STRICT JSON only."""


def _user_prompt(transcripts: list[Transcript]) -> str:
    parts = ["Three attempt transcripts follow.\n"]
    for i, t in enumerate(transcripts, start=1):
        parts.append(f"--- Attempt {i} ---\n{t.text.strip()}\n")
    parts.append(
        "\nReturn STRICT JSON only: double quotes on all keys and strings, no "
        "trailing commas, no markdown fences, no extra text."
    )
    return "\n".join(parts)


def generate_json(
    llm: LLMEngine,
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    empty_message: str,
) -> dict:
    """Generate + JSON-recover a structured-output call with ONE bounded regenerate.

    The shared recovery path for the non-grammar structured callers (coverage scoring,
    key-point derivation, follow-up generation): a single transient empty/JSON hiccup
    should not discard the whole result (IMP-011). Runs one ``generate`` + ``extract_json``;
    on an empty response OR a parse failure it does exactly one ``retry=True`` regenerate,
    mirroring ``analyze``'s bounded retry. Terminal failure keeps each caller's existing
    contract: a still-empty response raises ``LLMEngineError(empty_message)``; a still-
    unparseable response lets ``extract_json``'s ``ValueError`` propagate — so the
    coordinator degrades that ONE call gracefully rather than crashing the session.
    """
    raw = llm.generate(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)
    if raw and raw.strip():
        try:
            return extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            pass  # transient parse hiccup → one bounded regenerate below
    raw = llm.generate(
        system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature, retry=True
    )
    if not raw or not raw.strip():
        raise LLMEngineError(empty_message)
    return extract_json(raw)  # ValueError propagates on terminal parse failure


def _looks_like_repetition_loop(text: str) -> bool:
    """Detect degenerate repetition (the 4-bit loop / truncation signature) so
    the analyzer can trigger ONE bounded regenerate. Deliberately conservative
    and JSON-safe — well-formed structured output repeats *keys* with varied
    values, so neither signal below fires on it; a false positive only costs
    one extra (bounded) generation, never a hang."""
    s = (text or "").strip()
    if not s:
        return False
    words = s.split()
    run = max_run = 1  # the same token repeated many times in a row
    for a, b in zip(words, words[1:]):
        run = run + 1 if a == b else 1
        max_run = max(max_run, run)
    if max_run >= 8:
        return True
    lines = [ln.strip() for ln in s.splitlines() if len(ln.strip()) > 3]
    if lines and Counter(lines).most_common(1)[0][1] >= 6:  # one line repeated
        return True
    return False


def _debug_dump_raw(raw: str) -> str | None:
    """Diagnostic-only: when SPEAKLOOP_DEBUG_LLM=1, save the raw LLM output
    (first 8000 chars) under data/sessions/.debug-llm-raw/ so the operator can
    see what the model actually wrote. 8000 chars because parse failures often
    happen deep in the response. Never on by default; failures here are
    swallowed so debugging never breaks a session."""
    if os.environ.get("SPEAKLOOP_DEBUG_LLM") != "1":
        return None
    try:
        from speakloop.config import paths

        debug_dir = paths.sessions_dir() / ".debug-llm-raw"
        debug_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
        out = debug_dir / f"{stamp}.txt"
        out.write_text(raw[:8000], encoding="utf-8")
        return str(out)
    except Exception:  # noqa: BLE001 — diagnostics must never break the session
        return None


def _verify_and_enrich(
    errors: list[dict], transcripts: list[Transcript]
) -> list[GrammarPattern]:
    """Verify each free-form error, group by ``error_type``, rank deterministically."""
    is_coherent = coherence.make_filter(transcripts)

    verified: list[dict] = []
    for err in errors:
        if not isinstance(err, dict):
            continue  # json-repair may yield non-dict items (e.g. [1,2,3]); drop them
        try:
            ord_ = int(err.get("attempt_ordinal"))
        except (TypeError, ValueError):
            continue
        quote = str(err.get("quote") or "").strip()
        corrected = str(err.get("corrected") or "").strip()
        error_type = str(err.get("error_type") or "").strip()
        explanation = str(err.get("explanation") or "").strip()
        if ord_ < 1 or ord_ > len(transcripts):
            continue
        if not quote or quote not in transcripts[ord_ - 1].text:
            continue  # V1: verbatim substring guaranteed
        if not is_coherent(quote):
            continue  # V2: ASR-garble filter
        if not corrected or corrected == quote:
            continue  # V3: a fix equal to the quote is no fix
        if not error_type or not explanation:
            continue
        verified.append({
            "attempt_ordinal": ord_,
            "quote": quote,
            "corrected": corrected,
            "error_type": error_type,
            "explanation": explanation,
        })

    groups: dict[str, list[dict]] = defaultdict(list)
    for err in verified:
        groups[err["error_type"]].append(err)

    patterns: list[GrammarPattern] = []
    for label, items in groups.items():
        patterns.append(
            GrammarPattern(
                label=label,
                occurrence_count=len(items),
                explanation=items[0]["explanation"],  # representative — first item
                evidence=[
                    {
                        "attempt_ordinal": it["attempt_ordinal"],
                        "quote": it["quote"],
                        "corrected": it["corrected"],
                    }
                    for it in items
                ],
                # The free-form prompt doesn't ask the model for a suggested_fix;
                # the report uses the per-evidence ``corrected`` rewrite instead.
                suggested_fix=None,
                impact_rank=0,  # set below after sort
                catalog_id=None,  # free-form world — no catalog
            )
        )

    # Deterministic rank: most-frequent first, ties broken alphabetically.
    patterns.sort(key=lambda p: (-p.occurrence_count, p.label))
    for i, p in enumerate(patterns, start=1):
        p.impact_rank = i
    return patterns


def _generate_and_parse(
    transcripts: list[Transcript],
    llm: LLMEngine,
    max_tokens: int,
    system_prompt: str,
    *,
    retry: bool,
) -> tuple[dict | None, str]:
    """One generate+parse pass. Returns (payload | None, raw_text).

    Temperature 0.3 (vs the Protocol default 0.7) — pre-adoption testing showed
    materially improved recall and JSON discipline at this setting for analytic /
    structured-output tasks; the Protocol default remains 0.7 for compatibility.
    The wrapper strips any leading ``<think>`` block before returning, so the raw
    text here is the post-think payload.

    ``system_prompt`` is supplied by ``analyze(...)``: the local ``_SYSTEM_PROMPT``
    by default, or the cloud prompt in cloud mode (008) — the verify/rank pipeline
    is identical either way.
    """
    raw = llm.generate(
        system_prompt,
        _user_prompt(transcripts),
        max_tokens=max_tokens,
        temperature=0.3,
        retry=retry,
    )
    try:
        return extract_json(raw), raw
    except (ValueError, json.JSONDecodeError):
        # `extract_json` only returns dicts, so a top-level JSON LIST of error objects (the
        # model omitted the `errors` wrapper entirely) otherwise hard-fails. Recover it under
        # the wrapper key here — grammar-only, so the shared `extract_json` stays dict-only
        # for the coverage/keypoints/followups callers (IMP-027).
        listed = _extract_top_level_list(raw)
        if listed is not None:
            return {"errors": listed}, raw
        return None, raw


def _extract_top_level_list(raw: str) -> list | None:
    """Recover a top-level JSON list from ``raw`` (whole text, then the first ``[...]`` region),
    trying strict parse then ``json_repair``. Returns the list, or None when it is not a bare
    list. ``analyze`` wraps it as ``{"errors": [...]}``; V1/V2/V3 still filter the contents."""
    stripped = strip_code_fences(raw.strip())
    candidates = [stripped]
    m = re.search(r"\[.*\]", stripped, flags=re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for text in candidates:
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            try:
                obj = json_repair.loads(text)
            except Exception:  # noqa: BLE001 — json_repair is best-effort; try the next candidate
                continue
        if isinstance(obj, list):
            return obj
    return None


def analyze(
    transcripts: list[Transcript],
    llm: LLMEngine,
    *,
    max_tokens: int = 2048,
    system_prompt: str | None = None,
) -> list[GrammarPattern]:
    """Run the free-form grammar analyzer; return verified, ranked findings.

    Generation config (sampler, repetition penalty, defensive EOS) is owned by
    the LLM wrapper (Principle V) — the call site passes only ``retry`` intent.
    On a parse failure OR a detected repetition loop, ONE bounded regenerate is
    attempted; on terminal failure the existing graceful path runs (caller
    records ``phase_c_error`` and renders the Phase-B report; the session never
    crashes).

    ``system_prompt`` is additive (008): when ``None`` (every local/existing
    caller) the module-local ``_SYSTEM_PROMPT`` is used and behavior is
    byte-for-byte unchanged; cloud mode passes its own prompt so it never
    references the local one (FR-012)."""
    if not transcripts:
        return []

    prompt = _SYSTEM_PROMPT if system_prompt is None else system_prompt
    payload, raw = _generate_and_parse(transcripts, llm, max_tokens, prompt, retry=False)
    if payload is None or _looks_like_repetition_loop(raw):
        payload_retry, raw_retry = _generate_and_parse(
            transcripts, llm, max_tokens, prompt, retry=True
        )
        if payload_retry is not None:
            payload, raw = payload_retry, raw_retry
        elif payload is None:
            dump_path = _debug_dump_raw(raw)
            suffix = f" (raw saved to {dump_path})" if dump_path else ""
            raise LLMEngineError(
                f"Could not parse LLM grammar response after one bounded regenerate{suffix}"
            )
        # else: the loop-flagged original parsed fine and the retry did not
        # improve parseability — keep the original payload rather than discard
        # usable output.

    errors_raw = payload.get("errors")
    if errors_raw is None and ("quote" in payload or "attempt_ordinal" in payload):
        # The model returned ONE error object with no `errors` wrapper — recover it (IMP-027)
        # rather than silently returning zero patterns ("no actionable grammar patterns"), which
        # is worse than a graceful phase_c_error. V1/V2/V3 in _verify_and_enrich still discard
        # anything that isn't a real, verbatim, coherent error.
        errors_raw = [payload]
    errors_raw = errors_raw or []
    if not isinstance(errors_raw, list):
        raise LLMEngineError("LLM response 'errors' must be a list.")

    return _verify_and_enrich(errors_raw, transcripts)
