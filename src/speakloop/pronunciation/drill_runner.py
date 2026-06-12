"""Pure, UI-agnostic hear → say → see → retry loop for ONE drill (017).

Shared by the interview drill block (``sessions/coordinator.py``, concurrent with feedback)
and the standalone command (``cli/pronounce.py``). It owns the *loop logic* — hear-first +
replay-on-demand + bounded automatic retry + improvement detection + calibrated live prints —
while the caller injects everything that touches the world:

* ``speak(text)``  — synthesize + play the target (or a no-op when TTS is unavailable/off),
* ``record(wav_path, label)`` — capture audio with whatever recording UI the caller provides,
* ``scorer`` — a ``PronunciationScorer`` (duck-typed; never raises into the session),
* ``key_reader`` — a ``sessions.keyboard.KeyReader`` (``raw_capable`` gates replay/retry),
* ``console`` — a ``rich.Console`` for the calibrated wording.

Because of this injection it imports **no** engine package and **no** ``sessions``/``tts``/
``audio`` module, so it is unit-tested with fakes (no model/mic/tty/network) and creates no
import cycle. See ``specs/017-pronunciation-trainer/contracts/drill-runner.md``.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from pathlib import Path

from speakloop.pronunciation.feedback import live_flag_summary
from speakloop.pronunciation.interface import PronunciationError

_KEY_POLL_INTERVAL_SECONDS = 0.03


class DrillQuit(PronunciationError):
    """Raised when the learner presses ``q`` during a hear-first/retry wait.

    Subclasses ``PronunciationError`` so a caller that only catches the module base still
    degrades safely. The standalone command catches it to end the loop; the interview block
    catches it to stop asking for more drills (the report is still written by run_session)."""


def contrast_label(contrast) -> str:
    """Human-readable label for a contrast, e.g. ``"v vs w"`` (expected vs top competitor)."""
    if contrast is None:
        return ""
    comp = contrast.competitors[0] if getattr(contrast, "competitors", None) else ""
    return f"{contrast.expected} vs {comp}" if comp else str(contrast.expected)


def flagged_contrast_counts(items: list[dict]) -> dict[str, int]:
    """Per-contrast count of items whose FIRST attempt flagged — feeds the weak-sound tally."""
    counts: dict[str, int] = {}
    for it in items:
        if it.get("flags"):
            cid = it.get("contrast_id", "")
            counts[cid] = counts.get(cid, 0) + 1
    return counts


def build_block_result(items: list[dict], *, bank, engine_note: str = "") -> dict | None:
    """Assemble the drill-block result dict (data-model §3) shared by the interview block and
    the standalone command. ``None`` when no items ran (⇒ no report section, byte-identical)."""
    if not items:
        return None
    counts = flagged_contrast_counts(items)
    tricky_ids = sorted(counts, key=lambda c: (-counts[c], c))[:3]
    tricky_labels = [lbl for c in tricky_ids if (lbl := contrast_label(bank.contrast(c)))]
    return {
        "engine_note": engine_note,
        "items": items,
        "summary": {
            "drills": len(items),
            "with_flags": sum(1 for it in items if it.get("flags")),
            "contrasts_practiced": sorted({it["contrast_id"] for it in items}),
            "retried": sum(1 for it in items if it.get("retry")),
            "improved_on_retry": sum(
                1 for it in items if (it.get("retry") or {}).get("outcome") == "improved"
            ),
            "tricky_sounds": tricky_labels,
        },
    }


def _flag_to_dict(flag) -> dict:
    """Serialise a ``PhoneFlag`` for the report frontmatter (plain dict). Mirrors 016."""
    return {
        "expected": flag.expected,
        "word": flag.word,
        "gop": flag.gop,
        "competitor": flag.competitor,
        "competitor_margin": flag.competitor_margin,
        "confident_diagnosis": flag.confident_diagnosis,
        "tip": flag.tip,
    }


def select_drills(bank, *, weak_contrasts: list[str], max_base: int):
    """Order base drills with historically-weak contrasts first (FR-015/016).

    Drills whose ``contrast_id`` is in ``weak_contrasts`` come first, in ``weak_contrasts``
    order; the bank's curated order is preserved within ties and for non-weak contrasts.
    Empty ``weak_contrasts`` ⇒ the curated order unchanged (the 016 ``base_drills()`` slice).
    Pure; no I/O."""
    base = bank.base_drills()
    if not weak_contrasts:
        return base[: max_base if max_base > 0 else 0]
    rank = {cid: i for i, cid in enumerate(weak_contrasts)}
    # Stable sort: weak contrasts (by rank) first, everything else keeps curated order.
    ordered = sorted(
        enumerate(base),
        key=lambda iv: (rank.get(iv[1].contrast_id, len(rank)), iv[0]),
    )
    return [d for _, d in ordered][: max_base if max_base > 0 else 0]


def _hear_first(
    drill,
    *,
    speak: Callable[[str], None],
    key_reader,
    console,
    tts_on: bool,
    ui_sleep: Callable[[float], None],
) -> None:
    """Play the target (best-effort) and, when interactive, let the learner replay it with
    ``r`` before recording. ``q`` raises ``DrillQuit``. No-op when TTS is off/absent."""
    if not tts_on or speak is None:
        return
    with contextlib.suppress(Exception):  # playback is best-effort, never fatal (FR-005)
        speak(drill.prompt)
    if not getattr(key_reader, "raw_capable", False):
        return  # non-interactive: played once, proceed straight to recording
    console.print("  [dim]Press[/dim] R [dim]to hear it again, or[/dim] Space [dim]to read it aloud.[/dim]")
    with key_reader:
        while True:
            key = key_reader.poll()
            if key in ("space", "enter"):
                return
            if key == "q":
                raise DrillQuit()
            if key in ("r", "R"):
                with contextlib.suppress(Exception):
                    speak(drill.prompt)
            ui_sleep(_KEY_POLL_INTERVAL_SECONDS)


def _score_once(
    drill,
    *,
    contrast,
    scorer,
    record: Callable[[Path, str], None],
    scratch_dir: Path,
    label: str,
) -> tuple[str, list[dict]]:
    """Record one rendering and score it. Returns ``(status, flags_as_dicts)``. The wav is
    always discarded after scoring (privacy). Never raises (degrades to ``error``)."""
    wav_path = Path(scratch_dir) / f"drill-{drill.id}.wav"
    status, flags = "error", []
    try:
        record(wav_path, label)
        result = scorer.score(
            wav_path,
            canonical=drill.canonical,
            targets=drill.targets,
            tip=contrast.tip if contrast else "",
            competitors=contrast.competitors if contrast else [],
            drill_id=drill.id,
            text=drill.prompt,
            contrast_id=drill.contrast_id,
        )
        status = result.status
        flags = [_flag_to_dict(f) for f in result.flags]
    except Exception:  # noqa: BLE001 — a drill must never crash the session
        status = "error"
    finally:
        with contextlib.suppress(OSError):
            wav_path.unlink()
    return status, flags


def _print_outcome(console, status: str, flags: list[dict]) -> None:
    """Calibrated live feedback for one attempt (detection-led, hedged — FR-006)."""
    if status == "not_captured":
        console.print("  [dim]not captured — read right after the prompt[/dim]")
    elif status == "error":
        console.print("  [dim]could not score this one[/dim]")
    elif flags:
        console.print(f"  → {live_flag_summary(flags)}")
        for fl in flags:
            if fl.get("tip"):
                console.print(f"    [dim]Tip:[/dim] {fl['tip']}")
    else:
        console.print("  [green]clear ✓[/green]")


def run_drill_item(
    drill,
    *,
    contrast,
    scorer,
    speak: Callable[[str], None] | None,
    record: Callable[[Path, str], None],
    key_reader,
    console,
    scratch_dir: Path,
    retries: int = 1,
    tts_on: bool = True,
    is_follow_on: bool = False,
    ui_sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Run hear → say → see → retry for ONE drill; return the additive item dict (data-model §2).

    The first attempt's ``flags`` are preserved as the item ``flags`` (016 ``with_flags``
    semantics). When the target is flagged AND the terminal is interactive AND ``retries`` > 0,
    up to ``retries`` more passes run on the SAME item (hear → record → score), stopping early
    once the target clears; a ``retry`` sub-dict records the outcome. ``DrillQuit`` propagates
    (the caller decides what quit means)."""
    tag = " [dim](follow-up)[/dim]" if is_follow_on else ""
    console.print(f"\n[bold]Read aloud{tag}:[/bold] [cyan]{drill.prompt}[/cyan]")

    _hear_first(drill, speak=speak, key_reader=key_reader, console=console, tts_on=tts_on, ui_sleep=ui_sleep)
    status, flags = _score_once(
        drill, contrast=contrast, scorer=scorer, record=record, scratch_dir=scratch_dir,
        label=f"drill: {drill.prompt}",
    )
    _print_outcome(console, status, flags)

    item = {
        "drill_id": drill.id,
        "text": drill.prompt,
        "prompt": drill.prompt,
        "status": status,
        "flags": flags,
        "is_follow_on": is_follow_on,
        "contrast_id": drill.contrast_id,
    }

    # Bounded automatic retry — interactive only, so the default suite / piped runs behave
    # exactly like 016 (one attempt, no retry). FR-003/004/025.
    interactive = getattr(key_reader, "raw_capable", False)
    if status == "scored" and flags and interactive and retries > 0:
        attempts, outcome, final_flags = 1, "still_off", flags
        for _ in range(retries):
            console.print("  [dim]Let's try that once more — listen and repeat.[/dim]")
            _hear_first(drill, speak=speak, key_reader=key_reader, console=console, tts_on=tts_on, ui_sleep=ui_sleep)
            r_status, r_flags = _score_once(
                drill, contrast=contrast, scorer=scorer, record=record, scratch_dir=scratch_dir,
                label=f"retry: {drill.prompt}",
            )
            attempts += 1
            final_flags = r_flags
            if r_status == "not_captured":
                outcome = "not_captured"
                break
            if r_status == "scored" and not r_flags:
                outcome = "improved"
                break
            outcome = "still_off"
        if outcome == "improved":
            console.print("  [green]Better — that sound is clear now ✓[/green]")
        elif outcome == "not_captured":
            console.print("  [dim]not captured — moving on[/dim]")
        else:
            console.print("  [dim]Still a little off — keep practising; moving on.[/dim]")
        item["retry"] = {"attempts": attempts, "outcome": outcome, "final_flags": final_flags}

    return item
