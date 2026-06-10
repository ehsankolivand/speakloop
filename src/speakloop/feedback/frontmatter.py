"""Versioned YAML frontmatter serializer. Matches contracts/report-frontmatter.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import yaml

SCHEMA_VERSION = 1

# Fallback impact rank for grammar patterns parsed from legacy reports that
# pre-date the per-pattern impact_rank field (or sessions where impact_rank is
# missing for any reason). New sessions always set a 1..N rank in the analyzer;
# this constant only matters for backward-compat parse paths.
OPEN_BUCKET_IMPACT_RANK = 99


@dataclass
class GrammarPattern:
    label: str
    occurrence_count: int
    evidence: list[dict] = field(default_factory=list)
    suggested_fix: str | None = None
    # --- Additive (002-post-session-debrief; schema_version stays 1) ----------
    # The "Because:" transfer reason (data-model §A.1). Catalog patterns inherit
    # it from the catalog transfer_reason; open-bucket patterns get an
    # LLM-supplied, non-empty value.
    explanation: str | None = None
    # 1 = highest impact on interview comprehensibility (FR-005). Resolved
    # deterministically at build time and persisted so render/read-aloud order is
    # reproducible from the file alone.
    impact_rank: int | None = None
    # The catalog entry id when this is a catalog match; None for open-bucket.
    catalog_id: str | None = None
    # Each evidence dict MAY additionally carry a "corrected" key (the "Better:"
    # line, data-model §A.2); evidence remains a list[dict] for back-compat.


@dataclass
class AsrProvenance:
    """ASR provenance for one session (003-asr-l2-accent-accuracy, data-model §A.5).

    Additive: serialized as the single top-level `asr:` key, emitted only when
    present. `schema_version` stays 1 (FR-007/FR-008). Records the engine that
    actually ran (so a fallback is debuggable), the model id, the exact domain
    context (verbatim + sha256), the VAD settings (or None when disabled / when
    the fallback engine ran no VAD), and whether a fallback occurred.
    """

    engine: str
    model: str
    initial_prompt: str | None = None
    initial_prompt_sha256: str = ""
    vad: dict | None = None
    fell_back: bool = False


@dataclass
class AttemptMetrics:
    words_total: int = 0
    speech_rate_wpm: float = 0.0
    filler_words_count: int = 0
    filler_density_per_100_words: float = 0.0
    pauses_count: int = 0
    mean_pause_ms: float = 0.0
    self_corrections_count: int = 0


@dataclass
class Attempt:
    ordinal: int
    time_budget_seconds: int
    actual_duration_seconds: float
    transcript: str = ""
    metrics: AttemptMetrics = field(default_factory=AttemptMetrics)


@dataclass
class Session:
    session_id: str
    started_at: datetime
    question_id: str
    question_text: str
    attempts: list[Attempt]
    grammar_patterns: list[GrammarPattern] = field(default_factory=list)
    generated_by_phase: Literal["A", "B", "C"] = "B"
    # Static reference copy of the Q&A file's ideal_answer for the human reader.
    # Additive optional; the AI model never receives it (grammar analyzer takes
    # transcripts only; narrative is deterministic over metrics). Pre-feature
    # reports parse with this as None and render unchanged.
    ideal_answer: str | None = None
    # --- Additive top-level keys (002-post-session-debrief) -------------------
    # Deterministic prose: what improved across the 4/3/2 rounds (data-model §A.3,
    # FR-008). Phase-B reports may carry a fluency-only narrative.
    cross_attempt_narrative: str | None = None
    # The single most important thing to fix next session (FR-008), chosen by the
    # most-impactful-wins rule across grammar + fluency. Rendered as the banner.
    top_priority: str | None = None
    # --- Additive ASR provenance (003-asr-l2-accent-accuracy) -----------------
    # Emitted as the top-level `asr:` key only when present; schema_version stays 1.
    asr: AsrProvenance | None = None
    # The Phase-C grammar analyzer's exception message when it raised and the
    # session fell back to Phase B (so the failure is diagnosable from the saved
    # report alone, not just transient console output). Emitted only when present.
    phase_c_error: str | None = None
    # --- Additive cloud coaching layer (009-cloud-coaching-feedback) ----------
    # The free-form coaching Markdown (corrected answer + focused teaching + Anki
    # cards) from the cloud coach call. BODY-only: rendered into the report body
    # between the grammar section and the transcripts, NOT serialized to
    # frontmatter (like the per-attempt transcript text). Cloud-only; None in
    # local mode and when the coach call degraded.
    coaching: str | None = None
    # The coach call's exception message when it raised and coaching was skipped
    # (graceful degradation — the grammar report is unaffected). Emitted into
    # frontmatter only when present; round-trips like phase_c_error.
    coach_error: str | None = None
    # --- Additive Interview Loop keys (010-interview-loop) ---------------------
    # All additive optional; emitted only when present; schema_version STAYS 1.
    # The structured payloads are stored as plain dict/list[dict] (like
    # GrammarPattern.evidence) so this serializer stays decoupled from the new
    # interviewer/coverage/triage/srs modules — those modules convert their own
    # dataclasses to dicts before assigning here. Free-text transcripts inside
    # `warmup`/`follow_ups` are BODY-only (rendered by report_builder, not stored
    # here), like the attempt transcripts and `coaching`.
    question_type: str = "definition"  # definition | behavioral | hypothetical (P5)
    warmup: dict | None = None  # P2c: target_pattern + items[] (pass/fail/incomplete)
    follow_ups: list[dict] = field(default_factory=list)  # P1: per follow-up metadata
    coverage: list[dict] = field(default_factory=list)  # P3: per-attempt key-point coverage
    content_errors: list[dict] = field(default_factory=list)  # P3: mutually-exclusive contradictions
    pronunciation_flags: list[dict] = field(default_factory=list)  # P4: mishearings (never grammar)
    key_points: dict | None = None  # P3: the KeyPointSet scored against (text + version + hash)
    answer_grade: str | None = None  # poor|fair|good|strong — drives SRS scheduling
    analysis_pending: bool = False  # P-degradation: `speakloop resume` re-runs analysis (FR-035a)
    triage_summary: dict | None = None  # P4: counts of real/mishearing/hallucination spans
    # P2a: per-pattern occurrence trend strings for patterns shown this session
    # (label -> "10 → 4 → 1"), derived from the cross-session store (FR-008).
    pattern_trends: dict | None = None
    # --- Additive per-stage timings (012-responsive-session-flow) --------------
    # A machine-only wall-clock breakdown (StageTimer.to_frontmatter()); emitted only
    # when present so a no-timings report is byte-identical to before. NOT rendered
    # into the human body. schema_version STAYS 1 (additive optional key).
    timings: dict | None = None


class _LiteralStr(str):
    """A str subclass that PyYAML renders as a block scalar (|)."""


def _literal_representer(dumper: yaml.Dumper, data: _LiteralStr):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


yaml.add_representer(_LiteralStr, _literal_representer)


def _attempt_to_dict(a: Attempt) -> dict:
    return {
        "ordinal": a.ordinal,
        "time_budget_seconds": a.time_budget_seconds,
        "actual_duration_seconds": round(a.actual_duration_seconds, 1),
        "metrics": {
            "words_total": int(a.metrics.words_total),
            "speech_rate_wpm": float(a.metrics.speech_rate_wpm),
            "filler_words_count": int(a.metrics.filler_words_count),
            "filler_density_per_100_words": float(a.metrics.filler_density_per_100_words),
            "pauses_count": int(a.metrics.pauses_count),
            "mean_pause_ms": float(a.metrics.mean_pause_ms),
            "self_corrections_count": int(a.metrics.self_corrections_count),
        },
    }


def _evidence_to_dict(ev: dict) -> dict:
    """Normalise one evidence item, preserving the additive `corrected` key."""
    out: dict = {
        "attempt_ordinal": int(ev.get("attempt_ordinal", 0)),
        "quote": str(ev.get("quote", "")),
    }
    corrected = ev.get("corrected")
    if corrected:
        out["corrected"] = str(corrected)
    return out


def _pattern_to_dict(p: GrammarPattern) -> dict:
    out: dict = {"label": p.label, "occurrence_count": int(p.occurrence_count)}
    # Additive fields are emitted only when present so Phase-B / pre-feature
    # readers see no change (schema_version stays 1).
    if p.impact_rank is not None:
        out["impact_rank"] = int(p.impact_rank)
    if p.catalog_id:
        out["catalog_id"] = p.catalog_id
    if p.explanation:
        out["explanation"] = p.explanation.strip()
    if p.evidence:
        out["evidence"] = [_evidence_to_dict(ev) for ev in p.evidence]
    if p.suggested_fix:
        out["suggested_fix"] = p.suggested_fix
    return out


def dump(session: Session) -> str:
    """Render a `---`-delimited YAML block. Key order is stable.

    `dump` is normalised (strings are stripped before block-scalar emission) so a
    `dump → parse → dump` round-trip is idempotent (see `parse`).
    """
    payload: dict = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session.session_id,
        "started_at": session.started_at.isoformat(),
        "question_id": session.question_id,
        "question": _LiteralStr(session.question_text.strip() + "\n"),
    }
    # Static reference answer (human-only): emitted right after `question` when
    # present so reader and frontmatter pair them. AI-facing modules never read
    # this field (grammar analyzer sees transcripts only; narrative is metrics).
    if session.ideal_answer:
        payload["ideal_answer"] = _LiteralStr(session.ideal_answer.strip() + "\n")
    payload["attempts"] = [_attempt_to_dict(a) for a in session.attempts]
    payload["grammar_patterns"] = [_pattern_to_dict(p) for p in session.grammar_patterns]
    payload["generated_by_phase"] = session.generated_by_phase
    # Additive top-level keys — emitted only when present so existing readers and
    # Phase-B reports are byte-identical to before (FR-031).
    if session.cross_attempt_narrative:
        payload["cross_attempt_narrative"] = _LiteralStr(session.cross_attempt_narrative.strip())
    if session.top_priority:
        payload["top_priority"] = _LiteralStr(session.top_priority.strip())
    if session.asr is not None:
        payload["asr"] = _asr_to_dict(session.asr)
    if session.phase_c_error:
        payload["phase_c_error"] = _LiteralStr(session.phase_c_error.strip())
    # 009: a non-fatal note when the cloud coach call failed. The coaching text
    # itself lives in the report body, not here.
    if session.coach_error:
        payload["coach_error"] = _LiteralStr(session.coach_error.strip())
    # 010: additive Interview Loop keys — emitted only when present so existing
    # readers and pre-feature reports stay byte-identical (schema_version stays 1).
    if session.question_type and session.question_type != "definition":
        payload["question_type"] = session.question_type
    if session.warmup:
        payload["warmup"] = session.warmup
    if session.follow_ups:
        payload["follow_ups"] = session.follow_ups
    if session.coverage:
        payload["coverage"] = session.coverage
    if session.content_errors:
        payload["content_errors"] = session.content_errors
    if session.pronunciation_flags:
        payload["pronunciation_flags"] = session.pronunciation_flags
    if session.key_points:
        payload["key_points"] = session.key_points
    if session.answer_grade:
        payload["answer_grade"] = session.answer_grade
    if session.analysis_pending:
        payload["analysis_pending"] = True
    if session.triage_summary:
        payload["triage_summary"] = session.triage_summary
    if session.pattern_trends:
        payload["pattern_trends"] = session.pattern_trends
    # 012: per-stage timings — machine-only, additive optional (schema_version stays 1).
    if session.timings:
        payload["timings"] = session.timings
    body = yaml.dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{body}---\n"


def _asr_to_dict(a: AsrProvenance) -> dict:
    out: dict = {"engine": a.engine, "model": a.model}
    if a.initial_prompt is not None:
        # block scalar so the multi-line prompt renders readably in the report.
        out["initial_prompt"] = _LiteralStr(a.initial_prompt.strip() + "\n")
    out["initial_prompt_sha256"] = a.initial_prompt_sha256
    out["vad"] = a.vad  # mapping or None
    out["fell_back"] = bool(a.fell_back)
    return out


def _asr_from_dict(d: dict) -> AsrProvenance:
    vad = d.get("vad")
    return AsrProvenance(
        engine=str(d.get("engine", "")),
        model=str(d.get("model", "")),
        initial_prompt=_opt_str(d.get("initial_prompt")),
        initial_prompt_sha256=str(d.get("initial_prompt_sha256", "")),
        vad=vad if isinstance(vad, dict) else None,
        fell_back=bool(d.get("fell_back", False)),
    )


def _frontmatter_dict(text: str) -> dict:
    """Extract the YAML frontmatter mapping from a report (or a bare block)."""
    stripped = text.lstrip()
    if stripped.startswith("---"):
        # `---\n<yaml>\n---\n<body>` → take the block between the first two `---`.
        parts = text.split("---\n", 2)
        if len(parts) >= 2:
            loaded = yaml.safe_load(parts[1])
            return loaded if isinstance(loaded, dict) else {}
    loaded = yaml.safe_load(text)
    return loaded if isinstance(loaded, dict) else {}


def _opt_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).rstrip("\n")
    return s or None


def _evidence_from_dict(ev: dict) -> dict:
    out: dict = {
        "attempt_ordinal": int(ev.get("attempt_ordinal", 0)),
        "quote": str(ev.get("quote", "")),
    }
    if ev.get("corrected"):
        out["corrected"] = str(ev["corrected"])
    return out


def _pattern_from_dict(d: dict) -> GrammarPattern:
    impact = d.get("impact_rank")
    return GrammarPattern(
        label=str(d.get("label", "")),
        occurrence_count=int(d.get("occurrence_count", 0)),
        evidence=[_evidence_from_dict(ev) for ev in (d.get("evidence") or [])],
        suggested_fix=d.get("suggested_fix") or None,
        explanation=_opt_str(d.get("explanation")),
        impact_rank=int(impact) if impact is not None else None,
        catalog_id=d.get("catalog_id") or None,
    )


def _attempt_from_dict(a: dict) -> Attempt:
    m = a.get("metrics") or {}
    return Attempt(
        ordinal=int(a.get("ordinal", 0)),
        time_budget_seconds=int(a.get("time_budget_seconds", 0)),
        actual_duration_seconds=float(a.get("actual_duration_seconds", 0.0)),
        # `transcript` is intentionally not serialised into frontmatter (it lives
        # in the report body), so it does not round-trip here.
        transcript="",
        metrics=AttemptMetrics(
            words_total=int(m.get("words_total", 0)),
            speech_rate_wpm=float(m.get("speech_rate_wpm", 0.0)),
            filler_words_count=int(m.get("filler_words_count", 0)),
            filler_density_per_100_words=float(m.get("filler_density_per_100_words", 0.0)),
            pauses_count=int(m.get("pauses_count", 0)),
            mean_pause_ms=float(m.get("mean_pause_ms", 0.0)),
            self_corrections_count=int(m.get("self_corrections_count", 0)),
        ),
    )


def parse(text: str) -> Session:
    """Inverse of `dump`: reconstruct a `Session` from report frontmatter.

    Unknown keys are ignored (forward-compat) and missing additive keys default
    to empty (a pre-feature report still parses). `transcript` is not stored in
    frontmatter, so attempts come back with empty transcript text; `dump → parse
    → dump` is therefore idempotent at the serialized level.
    """
    data = _frontmatter_dict(text)
    raw_started = data.get("started_at")
    if isinstance(raw_started, datetime):
        started_at = raw_started
    elif isinstance(raw_started, str):
        try:
            started_at = datetime.fromisoformat(raw_started)
        except ValueError:
            started_at = datetime.fromtimestamp(0)
    else:
        started_at = datetime.fromtimestamp(0)
    phase = data.get("generated_by_phase", "B")
    if phase not in ("A", "B", "C"):
        phase = "B"
    return Session(
        session_id=str(data.get("session_id", "")),
        started_at=started_at,
        question_id=str(data.get("question_id", "")),
        question_text=str(data.get("question", "")).rstrip("\n"),
        attempts=[_attempt_from_dict(a) for a in (data.get("attempts") or [])],
        grammar_patterns=[_pattern_from_dict(p) for p in (data.get("grammar_patterns") or [])],
        generated_by_phase=phase,
        ideal_answer=_opt_str(data.get("ideal_answer")),
        cross_attempt_narrative=_opt_str(data.get("cross_attempt_narrative")),
        top_priority=_opt_str(data.get("top_priority")),
        asr=_asr_from_dict(data["asr"]) if isinstance(data.get("asr"), dict) else None,
        phase_c_error=_opt_str(data.get("phase_c_error")),
        # `coaching` is not serialized to frontmatter (it lives in the report
        # body), so it does not round-trip here — like the attempt transcripts.
        coach_error=_opt_str(data.get("coach_error")),
        # 010: additive Interview Loop keys; missing keys default so pre-feature
        # reports parse unchanged (SC-012). Structured payloads stay as dict/list.
        question_type=str(data.get("question_type") or "definition"),
        warmup=data.get("warmup") if isinstance(data.get("warmup"), dict) else None,
        follow_ups=list(data.get("follow_ups") or []),
        coverage=list(data.get("coverage") or []),
        content_errors=list(data.get("content_errors") or []),
        pronunciation_flags=list(data.get("pronunciation_flags") or []),
        key_points=data.get("key_points") if isinstance(data.get("key_points"), dict) else None,
        answer_grade=_opt_str(data.get("answer_grade")),
        analysis_pending=bool(data.get("analysis_pending", False)),
        triage_summary=(
            data.get("triage_summary") if isinstance(data.get("triage_summary"), dict) else None
        ),
        pattern_trends=(
            data.get("pattern_trends") if isinstance(data.get("pattern_trends"), dict) else None
        ),
        timings=data.get("timings") if isinstance(data.get("timings"), dict) else None,
    )
