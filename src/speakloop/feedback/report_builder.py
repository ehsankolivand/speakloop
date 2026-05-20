"""Composes Markdown frontmatter + body sections.

Renders the additive 002 fields (data-model §A): a "Top priority for next
session" section, the deterministic cross-attempt narrative, and impact-ranked
three-line fixes ("You said / Better / Because", FR-012). The Phase-B grammar
placeholder is preserved, and a Phase-C session that yields no actionable
patterns gets an explicit "no patterns" line (FR-009/T040).
"""

from __future__ import annotations

from speakloop.feedback import frontmatter
from speakloop.feedback.catalog import OPEN_BUCKET_IMPACT_RANK

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


def _pattern_card(p: frontmatter.GrammarPattern) -> str:
    """One impact-ranked finding rendered as "You said / Better / Because" (FR-012)."""
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
    if patterns:
        parts = ["## Grammar patterns"]
        parts.extend("\n" + _pattern_card(p) for p in patterns)
        return "\n".join(parts) + _phase_c_error_note(session)
    # No patterns: distinguish "LLM ran, found nothing" from "Phase C not enabled".
    placeholder = NO_PATTERNS_LINE if session.generated_by_phase == "C" else PHASE_B_PLACEHOLDER
    return f"## Grammar patterns\n\n{placeholder}{_phase_c_error_note(session)}"


def _top_priority_section(session: frontmatter.Session) -> str | None:
    if not session.top_priority:
        return None
    return f"## Top priority for next session\n\n{session.top_priority.strip()}"


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
        "",
        _transcripts_section(session.attempts),
    ]
    return "\n".join(parts)
