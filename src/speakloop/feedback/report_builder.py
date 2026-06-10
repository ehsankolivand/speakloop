"""Composes Markdown frontmatter + body sections.

Renders the additive 002 fields (data-model §A): a "Top priority for next
session" section, the deterministic cross-attempt narrative, and impact-ranked
three-line fixes ("You said / Better / Because", FR-012). The Phase-B grammar
placeholder is preserved, and a Phase-C session that yields no actionable
patterns gets an explicit "no patterns" line (FR-009/T040).
"""

from __future__ import annotations

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import OPEN_BUCKET_IMPACT_RANK

# Exact body strings (also asserted by tests / T040).
PHASE_B_PLACEHOLDER = (
    "_Grammar feedback will appear here once Phase C (LLM analyzer) is enabled._"
)
NO_PATTERNS_LINE = "No actionable grammar patterns detected this session."


def _attempt_row(a: frontmatter.Attempt) -> str:
    m = a.metrics
    used = f"{int(a.actual_duration_seconds // 60)}:{int(a.actual_duration_seconds % 60):02d}"
    budget = f"{a.time_budget_seconds // 60}:{a.time_budget_seconds % 60:02d}"
    return (
        f"| {a.ordinal}     | {budget}   | {used} | {m.speech_rate_wpm:.0f} | "
        f"{m.filler_density_per_100_words:.1f}          | {m.pauses_count}     |"
    )


def _attempts_table(attempts: list[frontmatter.Attempt]) -> str:
    rows = [
        "| Round | Budget | Used | WPM | Fillers/100w | Pauses |",
        "|-------|--------|------|-----|--------------|--------|",
    ] + [_attempt_row(a) for a in attempts]
    return "\n".join(rows)


def _cross_attempt_paragraph(attempts: list[frontmatter.Attempt]) -> str:
    """Fallback narrative when a session carries no persisted narrative."""
    if len(attempts) < 3:
        return ""
    wpm1 = attempts[0].metrics.speech_rate_wpm
    wpm3 = attempts[-1].metrics.speech_rate_wpm
    fillers1 = attempts[0].metrics.filler_density_per_100_words
    fillers3 = attempts[-1].metrics.filler_density_per_100_words
    direction = "climbed" if wpm3 > wpm1 else "dropped" if wpm3 < wpm1 else "held steady at"
    fillers_dir = (
        "fell" if fillers3 < fillers1 else "rose" if fillers3 > fillers1 else "held steady"
    )
    return (
        f"Your speech rate {direction} from {wpm1:.0f} to {wpm3:.0f} WPM across the three "
        f"attempts. Filler density {fillers_dir} from {fillers1:.1f} to {fillers3:.1f} per "
        "100 words. The 4/3/2 design intentionally compresses time on each round — "
        "rising WPM and falling fillers together is the signature of successful proceduralization."
    )


def _rank_key(p: frontmatter.GrammarPattern):
    return (
        p.impact_rank if p.impact_rank is not None else OPEN_BUCKET_IMPACT_RANK,
        -p.occurrence_count,
    )


def _pattern_card(p: frontmatter.GrammarPattern, trend: str | None = None) -> str:
    """One impact-ranked finding rendered as "You said / Better / Because" (FR-012).

    ``trend`` (010 P2a) is the per-pattern occurrence series across recent sessions
    (e.g. "10 → 4 → 1"), shown so the learner sees the pattern improving (FR-008)."""
    lines = [f"### {p.label} *({p.occurrence_count}×)*"]
    primary = p.evidence[0] if p.evidence else {}
    you_said = (primary.get("quote") or "").strip()
    better = (primary.get("corrected") or "").strip()
    if you_said:
        lines.append(f"- **You said:** “{you_said}”")
    if better and better != you_said:
        lines.append(f"- **Better:** “{better}”")
    if p.explanation:
        lines.append(f"- **Because:** {p.explanation.strip()}")
    if trend:
        lines.append(f"- **Trend (recent sessions):** {trend}")
    # Additional examples beneath the primary three lines.
    for ev in p.evidence[1:]:
        q = (ev.get("quote") or "").strip()
        c = (ev.get("corrected") or "").strip()
        if q and c and c != q:
            lines.append(f"  - “{q}” → “{c}”")
        elif q:
            lines.append(f"  - “{q}”")
    return "\n".join(lines)


def _phase_c_error_note(session: frontmatter.Session) -> str:
    """A diagnostic note when the Phase-C analyzer raised and we fell back."""
    if not session.phase_c_error:
        return ""
    return (
        "\n\n> ⚠️ **Phase C analysis failed; this report fell back to Phase B.**\n>\n"
        f"> `{session.phase_c_error.strip()}`\n>\n"
        "> No grammar patterns were produced for this session. Re-run once the "
        "analyzer issue is resolved."
    )


def _grammar_section(session: frontmatter.Session) -> str:
    patterns = sorted(session.grammar_patterns, key=_rank_key)
    trends = session.pattern_trends or {}
    if patterns:
        parts = ["## Grammar patterns"]
        parts.extend("\n" + _pattern_card(p, trends.get(p.label)) for p in patterns)
        return "\n".join(parts) + _phase_c_error_note(session)
    # No patterns: distinguish "LLM ran, found nothing" from "Phase C not enabled".
    placeholder = NO_PATTERNS_LINE if session.generated_by_phase == "C" else PHASE_B_PLACEHOLDER
    return f"## Grammar patterns\n\n{placeholder}{_phase_c_error_note(session)}"


def _top_priority_section(session: frontmatter.Session) -> str | None:
    if not session.top_priority:
        return None
    return f"## Top priority for next session\n\n{session.top_priority.strip()}"


def _question_reference_section(session: frontmatter.Session) -> str | None:
    """Static Question + Reference answer block for the human reader.

    The reference answer is a verbatim copy of the Q&A file's ``ideal_answer``.
    It is NOT a feedback dimension — no semantic-equivalence judging, no
    scoring, no LLM input. The AI grammar analyzer sees only the transcripts.
    Pre-feature reports (no ``ideal_answer``) skip this section entirely so the
    output stays byte-identical to before.
    """
    question = (session.question_text or "").strip()
    answer = (session.ideal_answer or "").strip()
    if not answer:
        return None
    lines = ["## Question & reference answer", ""]
    if question:
        lines += [f"**Question:** {question}", ""]
    lines += ["**Reference answer:**", "", answer]
    return "\n".join(lines)


def _coaching_section(session: frontmatter.Session) -> str | None:
    """The cloud coaching Markdown (009), appended verbatim between the grammar
    section and the transcripts.

    The coach model already emits level-2 headings ("## Your answer, improved",
    "## What to focus on", "## Anki cards"), so it is rendered as-is — never
    re-wrapped or re-formatted. Body-only and additive: absent (local mode, or a
    coach call that degraded) → the report is byte-identical to the pre-009
    layout."""
    coaching = (session.coaching or "").strip()
    return coaching or None


# --- Interview Loop sections (010) -----------------------------------------
# Additive, body-only sections rendered AFTER grammar/coaching and BEFORE the
# transcripts, in a fixed order (data-model §10). Each renderer returns None when
# its data is absent, so a pre-feature report (and any session missing the data)
# is byte-identical to before. Story phases append their own renderers to
# `_INTERVIEW_LOOP_RENDERERS`.


def _warmup_section(session: frontmatter.Session) -> str | None:
    """P2c: the warm-up drill items with their pass/fail/incomplete verdicts."""
    warmup = session.warmup
    if not warmup or not warmup.get("items"):
        return None
    lines = ["## Warm-up drill", ""]
    target = warmup.get("target_pattern")
    if target:
        lines.append(f"_Exercising your recurring pattern: **{target}**._")
        lines.append("")
    marks = {"pass": "✓", "fail": "✗", "incomplete": "…"}
    for it in warmup["items"]:
        result = str(it.get("result", "")).strip()
        mark = marks.get(result, "•")
        lines.append(f"- {mark} {str(it.get('target_sentence', '')).strip()} — **{result}**")
    return "\n".join(lines)


_COVERAGE_MARK = {"covered": "✓", "partial": "~", "missed": "✗"}


def _coverage_section(session: frontmatter.Session) -> str | None:
    """P3: per-attempt key-point coverage with the first→final delta (FR-020/SC-009)."""
    records = session.coverage or []
    if not records:
        return None
    records = sorted(records, key=lambda r: r.get("attempt_ordinal", 0))
    point_text = {}
    if session.key_points:
        for p in session.key_points.get("points", []):
            point_text[int(p["id"])] = str(p.get("text", "")).strip()
    point_ids = [int(p["id"]) for p in (session.key_points or {}).get("points", [])]
    if not point_ids and records:
        point_ids = [int(pp["id"]) for pp in records[0].get("per_point", [])]

    ordinals = [r.get("attempt_ordinal") for r in records]
    goal_unit = "STAR components" if session.question_type == "behavioral" else "key points"
    lines = ["## Content coverage", ""]
    lines.append(f"_Final-round goal: all {goal_unit} within the time budget._")
    lines.append("")
    header = "| Key point | " + " | ".join(f"R{o}" for o in ordinals) + " |"
    sep = "|" + "---|" * (len(ordinals) + 1)
    lines += [header, sep]
    state_by_round = {r.get("attempt_ordinal"): {int(pp["id"]): pp["state"] for pp in r.get("per_point", [])} for r in records}
    for pid in point_ids:
        cells = [_COVERAGE_MARK.get(state_by_round.get(o, {}).get(pid, "missed"), "✗") for o in ordinals]
        label = point_text.get(pid, f"point {pid}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    first = records[0].get("aggregate", 0.0)
    final = records[-1].get("aggregate", 0.0)
    lines.append("")
    lines.append(f"**Coverage:** {first:.0%} (R{ordinals[0]}) → {final:.0%} (R{ordinals[-1]}), Δ {final - first:+.0%}")
    return "\n".join(lines)


def _content_errors_section(session: frontmatter.Session) -> str | None:
    """P3: factual contradictions vs the ideal answer, SEPARATE from grammar."""
    errors = session.content_errors or []
    if not errors:
        return None
    lines = ["## Content errors (vs. reference answer)", ""]
    for e in errors:
        learner = str(e.get("learner_claim", "")).strip()
        ideal = str(e.get("ideal_claim", "")).strip()
        if not learner and not ideal:
            continue
        ordinal = e.get("attempt_ordinal")
        where = f" *(round {ordinal})*" if ordinal else ""
        lines.append(f"- You said **{learner}**, but the reference answer says **{ideal}**.{where}")
    return "\n".join(lines) if len(lines) > 2 else None


def _pronunciation_flags_section(session: frontmatter.Session) -> str | None:
    """P4: likely pronunciation mishearings, reported here — NEVER as grammar."""
    flags = session.pronunciation_flags or []
    if not flags:
        return None
    lines = [
        "## Pronunciation flags",
        "",
        "_These look like the recognizer mishearing a word you said — practice the "
        "pronunciation; they are not grammar mistakes._",
        "",
    ]
    for f in flags:
        heard = str(f.get("heard", "")).strip()
        intended = str(f.get("likely_intended", "")).strip()
        if heard and intended:
            lines.append(f"- heard **“{heard}”** — likely you meant **“{intended}”**")
    return "\n".join(lines) if len(lines) > 4 else None


def _follow_ups_section(session: frontmatter.Session) -> str | None:
    """P1: the interactive follow-ups, each with the spoken question, the learner's
    transcribed answer (or a timed-out note), and its grammar feedback."""
    follow_ups = session.follow_ups or []
    if not follow_ups:
        return None
    lines = ["## Follow-ups", ""]
    for f in follow_ups:
        idx = f.get("index", "")
        lines.append(f"### Follow-up {idx}")
        lines.append("")
        lines.append(f"**Interviewer:** {str(f.get('question_text', '')).strip()}")
        lines.append("")
        if f.get("answered"):
            answer = str(f.get("transcript", "")).strip() or "_(no transcript)_"
            lines.append(f"**You said:** {answer}")
            patterns = f.get("grammar_patterns") or []
            if patterns:
                lines.append("")
                for p in patterns:
                    label = str(p.get("label", "")).strip()
                    count = p.get("occurrence_count", 0)
                    if label:
                        lines.append(f"- {label} *({count}×)*")
        else:
            lines.append("_No answer — timed out._")
        lines.append("")
    return "\n".join(lines).rstrip()


_CONDITIONAL_MARKERS = (" if ", " would ", " could ", " were ", " might ")


def _type_guidance_section(session: frontmatter.Session) -> str | None:
    """P5: type-specific guidance — STAR-structure check (behavioral) or
    conditional/future-form guidance (hypothetical). Definition questions get none."""
    qtype = session.question_type
    if qtype == "behavioral":
        # The key points ARE the STAR components for behavioral questions; report
        # which were present in the final round (covered/partial = present, FR-031).
        records = session.coverage or []
        if not records or not session.key_points:
            return None
        final = max(records, key=lambda r: r.get("attempt_ordinal", 0))
        text_by_id = {int(p["id"]): str(p.get("text", "")) for p in session.key_points.get("points", [])}
        lines = ["## STAR structure check", ""]
        for pp in final.get("per_point", []):
            present = pp.get("state") in ("covered", "partial")
            mark = "✓ present" if present else "✗ missing"
            lines.append(f"- **{text_by_id.get(int(pp['id']), pp['id'])}:** {mark}")
        return "\n".join(lines)

    if qtype == "hypothetical":
        lines = ["## Hypothetical — conditional & future forms", ""]
        final = max(session.attempts, key=lambda a: a.ordinal) if session.attempts else None
        transcript = (final.transcript if final else "") or ""
        lowered = f" {transcript.lower()} "
        used = [m.strip() for m in _CONDITIONAL_MARKERS if m in lowered]
        if used:
            lines.append(
                f"Good — you used conditional/future forms ({', '.join(sorted(set(used)))}). "
                "Keep framing scenario answers as *if … I would …*."
            )
        else:
            lines.append(
                "Your answer used few conditional forms. A hypothetical answer should be framed "
                "with conditionals and future modals — e.g. *if the app ANRs, I **would** capture a trace*."
            )
        return "\n".join(lines)

    return None


# Ordered list of section renderers (data-model §10): warm-up → (coverage, P3) →
# content-errors → pronunciation-flags → follow-ups → type-guidance (P5).
_INTERVIEW_LOOP_RENDERERS = [
    _warmup_section,
    _coverage_section,
    _content_errors_section,
    _pronunciation_flags_section,
    _follow_ups_section,
    _type_guidance_section,
]


def _interview_loop_sections(session: frontmatter.Session) -> list[str]:
    """Render all present Interview Loop sections, in order; [] when none apply."""
    out: list[str] = []
    for renderer in _INTERVIEW_LOOP_RENDERERS:
        section = renderer(session)
        if section:
            out += ["", section]
    return out


def _transcripts_section(attempts: list[frontmatter.Attempt]) -> str:
    parts = ["## Transcripts"]
    for a in attempts:
        parts.append(f"\n### Attempt {a.ordinal}\n\n{a.transcript.strip() or '_(silent)_'}\n")
    return "\n".join(parts)


def build(session: frontmatter.Session, *, title: str | None = None) -> str:
    fm = frontmatter.dump(session)
    title = title or f"{session.question_id} — {session.started_at.date().isoformat()}"
    narrative = session.cross_attempt_narrative or _cross_attempt_paragraph(session.attempts)

    parts = [fm, f"# {title}", ""]

    qa_ref = _question_reference_section(session)
    if qa_ref is not None:
        parts += [qa_ref, ""]

    top_priority = _top_priority_section(session)
    if top_priority is not None:
        parts += [top_priority, ""]

    parts += [
        "## Attempt-by-attempt summary",
        "",
        _attempts_table(session.attempts),
        "",
        "## Cross-attempt comparison",
        "",
        narrative,
        "",
        _grammar_section(session),
    ]

    # 009: cloud coaching section, AFTER grammar and BEFORE transcripts. When
    # absent, the join below is byte-identical to the pre-009 layout.
    coaching = _coaching_section(session)
    if coaching is not None:
        parts += ["", coaching]

    # 010: additive Interview Loop sections, AFTER grammar/coaching and BEFORE the
    # transcripts. Empty when no such data is present → byte-identical to before.
    parts += _interview_loop_sections(session)

    parts += ["", _transcripts_section(session.attempts)]
    return "\n".join(parts)
