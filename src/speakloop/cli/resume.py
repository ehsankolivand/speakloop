"""`speakloop resume` — finish analysis-pending sessions (010, FR-035a).

When the language model was unavailable mid-session the report was written with
the deterministic parts and marked ``analysis_pending``. This command re-runs the
missing analysis (grammar + coverage) over the PRESERVED transcripts in the report
body, rewrites the report atomically, clears the flag, and advances the SRS
schedule. Engines are imported lazily (Principle VIII).
"""

from __future__ import annotations

import re
from datetime import date as _date
from pathlib import Path

import typer
from rich.console import Console

from speakloop.config import paths
from speakloop.feedback import frontmatter, markdown_writer, narrative, report_builder

_ATTEMPT_RE = re.compile(r"^### Attempt (\d+)\s*$")


def _extract_attempt_transcripts(body: str) -> dict[int, str]:
    """Recover attempt transcripts from the report's ## Transcripts section."""
    out: dict[int, str] = {}
    lines = body.splitlines()
    in_transcripts = False
    current: int | None = None
    buf: list[str] = []

    def _flush():
        if current is not None:
            text = "\n".join(buf).strip()
            out[current] = "" if text == "_(silent)_" else text

    for line in lines:
        if line.strip().startswith("## ") and line.strip() != "## Transcripts":
            if in_transcripts:
                break  # left the transcripts section
            continue
        if line.strip() == "## Transcripts":
            in_transcripts = True
            continue
        if not in_transcripts:
            continue
        m = _ATTEMPT_RE.match(line.strip())
        if m:
            _flush()
            current = int(m.group(1))
            buf = []
        elif current is not None:
            buf.append(line)
    _flush()
    return out


def run(*, cloud: bool = False) -> None:
    console = Console()
    sessions_dir = paths.sessions_dir()
    if not sessions_dir.exists():
        console.print("[yellow]No sessions directory — nothing to resume.[/yellow]")
        return

    pending: list[Path] = []
    for path in sorted(sessions_dir.glob("*.md")):
        try:
            session = frontmatter.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if session.analysis_pending:
            pending.append(path)

    if not pending:
        console.print("[green]No analysis-pending sessions.[/green]")
        return

    # Build the analysis runners over one engine (lazy; mirrors practice).
    from speakloop.cli import practice as _practice

    if cloud:
        grammar_analyzer, _coach = _practice._build_cloud_grammar_analyzer(console)
    else:
        grammar_analyzer = _practice._build_grammar_analyzer()
    if grammar_analyzer is None:
        console.print(
            "[red]No analysis model available.[/red] Install the local model or pass --cloud."
        )
        raise typer.Exit(1)
    runners = getattr(grammar_analyzer, "runners", None)

    from speakloop.asr import Transcript

    resolved = 0
    for path in pending:
        text = path.read_text(encoding="utf-8")
        session = frontmatter.parse(text)
        transcripts_by_ord = _extract_attempt_transcripts(text)
        if not transcripts_by_ord:
            console.print(f"[yellow]{path.name}: no transcripts found in body; skipping.[/yellow]")
            continue
        # Restore transcript text onto the parsed attempts (body-only field).
        for a in session.attempts:
            a.transcript = transcripts_by_ord.get(a.ordinal, "")
        transcripts = [
            Transcript(text=transcripts_by_ord.get(a.ordinal, "")) for a in session.attempts
        ]

        try:
            session.grammar_patterns = grammar_analyzer(transcripts)
        except Exception as e:  # noqa: BLE001 — still pending if it fails again
            console.print(f"[yellow]{path.name}: analysis still failing ({e}); left pending.[/yellow]")
            continue
        session.generated_by_phase = "C"
        session.phase_c_error = None
        session.analysis_pending = False

        coverage_aggregate = None
        if runners and runners.coverage and session.key_points and session.ideal_answer:
            try:
                result = runners.coverage(
                    session.key_points.get("points", []), transcripts, session.ideal_answer,
                    session.key_points.get("version", 1),
                )
                session.coverage = result.attempt_records
                session.content_errors = result.content_errors
                coverage_aggregate = result.final_aggregate
            except Exception:  # noqa: BLE001 — coverage best-effort on resume
                pass

        from speakloop.srs import grade as _srs_grade

        session.answer_grade = _srs_grade.grade_session(
            coverage_aggregate=coverage_aggregate,
            content_error_count=len(session.content_errors),
            grammar_patterns=session.grammar_patterns,
        )
        session.cross_attempt_narrative = narrative.build_narrative(
            session.attempts, session.grammar_patterns
        )
        session.top_priority = narrative.select_top_priority(
            session.grammar_patterns, session.attempts
        )

        markdown_writer.write_atomic(path, report_builder.build(session))
        _advance_schedule(session, today=session.started_at.date() if session.started_at else _date.today())
        console.print(f"[green]Resumed:[/green] {path.name} (grade: {session.answer_grade})")
        resolved += 1

    console.print(f"\nResumed {resolved} of {len(pending)} pending session(s).")


def _advance_schedule(session: frontmatter.Session, *, today) -> None:
    if not session.answer_grade:
        return
    from speakloop.srs import schedule as _srs_schedule
    from speakloop.store import io as _store_io
    from speakloop.store.model import ScheduleEntry

    store_path = paths.store_path()
    store = _store_io.load(store_path)
    entry = store.schedule.get(session.question_id) or ScheduleEntry(question_id=session.question_id)
    store.schedule[session.question_id] = _srs_schedule.next_due(entry, session.answer_grade, today=today)
    _store_io.save_atomic(store_path, store)
