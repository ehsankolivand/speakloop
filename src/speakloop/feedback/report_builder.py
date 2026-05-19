"""Composes Markdown frontmatter + body sections."""

from __future__ import annotations

from speakloop.feedback import frontmatter


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


def _grammar_section(patterns: list[frontmatter.GrammarPattern]) -> str:
    if not patterns:
        return (
            "## Grammar patterns\n\n"
            "_Grammar feedback will appear here once Phase C (LLM analyzer) is enabled._"
        )
    parts = ["## Grammar patterns"]
    for p in patterns:
        parts.append(f"\n### {p.label} *({p.occurrence_count}×)*")
        for ev in p.evidence:
            parts.append(f"> {ev.get('quote', '').strip()}")
        if p.suggested_fix:
            parts.append(f"Suggested: {p.suggested_fix}")
    return "\n".join(parts)


def _transcripts_section(attempts: list[frontmatter.Attempt]) -> str:
    parts = ["## Transcripts"]
    for a in attempts:
        parts.append(f"\n### Attempt {a.ordinal}\n\n{a.transcript.strip() or '_(silent)_'}\n")
    return "\n".join(parts)


def build(session: frontmatter.Session, *, title: str | None = None) -> str:
    fm = frontmatter.dump(session)
    title = title or f"{session.question_id} — {session.started_at.date().isoformat()}"
    parts = [
        fm,
        f"# {title}",
        "",
        "## Attempt-by-attempt summary",
        "",
        _attempts_table(session.attempts),
        "",
        "## Cross-attempt comparison",
        "",
        _cross_attempt_paragraph(session.attempts),
        "",
        _grammar_section(session.grammar_patterns),
        "",
        _transcripts_section(session.attempts),
    ]
    return "\n".join(parts)
