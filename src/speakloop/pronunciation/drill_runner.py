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
import logging
import os
import time
import traceback
from collections.abc import Callable
from pathlib import Path

from speakloop.pronunciation.feedback import live_flag_summary
from speakloop.pronunciation.interface import PronunciationError

_KEY_POLL_INTERVAL_SECONDS = 0.03

# Logger for drill scoring/recording diagnostics. Emits at DEBUG only (so nothing reaches
# the stderr "last resort" handler during a normal run); a handler is attached by the CLI
# when the learner opts into debug mode (``speakloop pronounce --debug`` / SPEAKLOOP_DEBUG).
logger = logging.getLogger("speakloop.pronunciation.drill")


def _debug_enabled() -> bool:
    """True when SPEAKLOOP_DEBUG is set to a truthy value — surfaces the swallowed failure
    reason inline (the score path never raises into the session, so the real cause — a mic
    error vs a model error — is otherwise invisible). ``pronounce --debug`` sets this."""
    return os.environ.get("SPEAKLOOP_DEBUG", "").strip().lower() not in ("", "0", "false", "no", "off")


def _error_hint(detail: str) -> str:
    """Map a captured failure ``detail`` to an actionable, English, non-technical hint so the
    learner knows what to DO — distinguishing a microphone problem from a scoring-model one."""
    d = detail.lower()
    if any(k in d for k in ("recording", "microphone", "portaudio", "input stream", "no audio")):
        return "couldn't reach your microphone — check it's connected and run `speakloop doctor`."
    if any(k in d for k in ("model", "transformers", "torch", "espeak", "vocab", "weights", "load")):
        return "couldn't run the scoring model — run `speakloop doctor` to check it downloaded."
    return "give it another go; if it keeps happening run `speakloop doctor`."


class DrillQuit(PronunciationError):
    """Raised when the learner presses ``q`` during a hear-first/retry wait.

    Subclasses ``PronunciationError`` so a caller that only catches the module base still
    degrades safely. The standalone command catches it to end the loop; the interview block
    catches it to stop asking for more drills (the report is still written by run_session).

    ``item`` carries the already-scored first-attempt dict when the learner quits DURING a retry
    (so a flagged drill is not silently dropped from the block result / weak-sound tally); it is
    None when the quit happened before any scoring (a never-scored drop, correctly discarded)."""

    def __init__(self, *args, item: dict | None = None) -> None:
        super().__init__(*args)
        self.item = item


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
) -> tuple[str, list[dict], str]:
    """Record one rendering and score it. Returns ``(status, flags_as_dicts, detail)``.

    ``detail`` carries the REAL reason a non-``scored`` outcome happened — the scorer's own
    ``DrillResult.detail`` (a model/scoring failure) OR the recorder/scorer exception text (a
    mic failure). The score path is designed never to raise into the session, which otherwise
    *hides* the cause behind a vague "could not score"; capturing + logging ``detail`` makes it
    visible (DEBUG log + inline when SPEAKLOOP_DEBUG). The wav is always discarded (privacy)."""
    wav_path = Path(scratch_dir) / f"drill-{drill.id}.wav"
    status, flags, detail = "error", [], ""
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
        detail = getattr(result, "detail", "") or ""
    except Exception as e:  # noqa: BLE001 — a drill must never crash the session
        status = "error"
        detail = f"{type(e).__name__}: {e}"
        logger.debug("drill %r raised during record/score:\n%s", drill.id, traceback.format_exc())
    finally:
        with contextlib.suppress(OSError):
            wav_path.unlink()
    if status != "scored" and detail:
        logger.debug("drill %r → %s: %s", drill.id, status, detail)
    return status, flags, detail


def _print_outcome(console, status: str, flags: list[dict], detail: str = "") -> None:
    """Calibrated live feedback for one attempt (detection-led, hedged — FR-006).

    A non-``scored`` outcome gets an ACTIONABLE message (not a vague "could not score"):
    ``not_captured`` points at the microphone/timing; ``error`` distinguishes a mic problem
    from a model problem via ``detail``. When SPEAKLOOP_DEBUG is set the raw ``detail`` is
    shown inline so the learner (or a maintainer) can always tell WHY it failed."""
    if status == "not_captured":
        console.print(
            "  [yellow]I didn't catch any audio[/yellow] [dim]— check your microphone and "
            "read right after the prompt.[/dim]"
        )
    elif status == "error":
        console.print(f"  [yellow]I couldn't score that one[/yellow] [dim]— {_error_hint(detail)}[/dim]")
        if detail and not _debug_enabled():
            console.print("    [dim](run `speakloop pronounce --debug` to see the reason)[/dim]")
    elif flags:
        console.print(f"  → {live_flag_summary(flags)}")
        for fl in flags:
            if fl.get("tip"):
                console.print(f"    [dim]Tip:[/dim] {fl['tip']}")
    else:
        console.print("  [green]clear ✓[/green]")
    if detail and status != "scored" and _debug_enabled():
        console.print(f"    [dim]debug: {detail}[/dim]")


def _flagged_words(flags: list[dict]) -> list[str]:
    """Distinct, order-preserved target words that flagged (drives the teaching beat)."""
    words: list[str] = []
    seen: set[str] = set()
    for fl in flags:
        w = str(fl.get("word", "")).strip()
        if w and w.lower() not in seen:
            seen.add(w.lower())
            words.append(w)
    return words


def _teach_sound(
    drill,
    flags: list[dict],
    *,
    speak: Callable[[str], None] | None,
    teach_speak: Callable[[str], None] | None,
    console,
    tts_on: bool,
    ui_sleep: Callable[[float], None],
) -> None:
    """Focused per-sound coaching beat, shown BEFORE the bounded retry when a sound flagged
    (FR-006, 017 P2). A calm "let me show you" moment that actually *teaches* the sound:

    * show the curated English respelling highlighting the target sound (``drill.say_like``);
    * play JUST the flagged word(s) in ISOLATION at the slower teaching rate (``teach_speak``,
      falling back to ``speak`` when no slower voice is injected) so the learner hears the
      correct word modelled on its own — Kokoro has no phoneme-stress control, so isolation +
      a slower rendering + the respelling is the (documented) approximation of emphasis;
    * cue the learner to repeat just that.

    Best-effort and bounded: any playback failure is swallowed (never blocks the drill), and
    it is a no-op when TTS is off / unavailable apart from still showing the respelling."""
    words = _flagged_words(flags) or [drill.prompt]
    console.print("  [bold]Let me show you[/bold] [dim]— here's just that part, slower:[/dim]")
    if drill.say_like:
        console.print(f"    [dim]Say it like:[/dim] {drill.say_like}")
    play = teach_speak or speak
    if tts_on and play is not None:
        for w in words:
            with contextlib.suppress(Exception):  # best-effort, never fatal (FR-005)
                play(w)
            ui_sleep(0.12)  # a small gap so each modelled word lands distinctly


def run_drill_block(
    base,
    *,
    bank,
    scorer,
    speak: Callable[[str], None] | None,
    record: Callable[[Path, str], None],
    key_reader,
    console,
    scratch_dir: Path,
    retries: int = 1,
    tts_on: bool = True,
    max_followons: int = 2,
    ui_sleep: Callable[[float], None] = time.sleep,
    should_abort: Callable[[], bool] | None = None,
    teach_speak: Callable[[str], None] | None = None,
) -> tuple[list[dict], bool]:
    """Run a block of base drills, routing a flagged base drill into bounded follow-on minimal
    pairs (016 routing, FR-009/024). Shared by the interview block and the standalone command.

    Returns ``(items, quit)``: ``items`` are the per-drill dicts in run order; ``quit`` is True
    when the learner ended the block with ``q`` (``DrillQuit``). ``should_abort`` (e.g. the
    session abort flag) stops asking for more between drills. Never raises into the caller."""
    items: list[dict] = []
    seen_ids: set[str] = set()
    state = {"followons_left": max(0, max_followons)}

    def _run(drill, *, is_follow_on: bool) -> None:
        if should_abort is not None and should_abort():
            return
        seen_ids.add(drill.id)
        try:
            item = run_drill_item(
                drill, contrast=bank.contrast(drill.contrast_id), scorer=scorer, speak=speak,
                record=record, key_reader=key_reader, console=console, scratch_dir=scratch_dir,
                retries=retries, tts_on=tts_on, is_follow_on=is_follow_on, ui_sleep=ui_sleep,
                teach_speak=teach_speak,
            )
        except DrillQuit as quit_exc:
            # The learner quit; a first attempt scored DURING a retry is preserved on the
            # exception so it stays in the report + the weak-sound tally (not silently dropped).
            if quit_exc.item is not None:
                items.append(quit_exc.item)
            raise
        items.append(item)
        if (
            not is_follow_on
            and item["status"] == "scored"
            and item.get("flags")
            and state["followons_left"] > 0
        ):
            for nxt in bank.next_drills(
                drill.contrast_id, exclude_ids=seen_ids, max=state["followons_left"]
            ):
                if state["followons_left"] <= 0 or (should_abort is not None and should_abort()):
                    break
                state["followons_left"] -= 1
                _run(nxt, is_follow_on=True)

    try:
        for drill in base:
            if should_abort is not None and should_abort():
                break
            _run(drill, is_follow_on=False)
    except DrillQuit:
        return items, True
    return items, False


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
    teach_speak: Callable[[str], None] | None = None,
) -> dict:
    """Run hear → say → see → retry for ONE drill; return the additive item dict (data-model §2).

    The first attempt's ``flags`` are preserved as the item ``flags`` (016 ``with_flags``
    semantics). When the target is flagged AND the terminal is interactive AND ``retries`` > 0,
    a focused per-sound teaching beat runs first (``_teach_sound`` — respelling + the flagged
    word modelled in isolation at the slower ``teach_speak`` rate), then up to ``retries`` more
    passes on the SAME item (hear → record → score), stopping early once the target clears; a
    ``retry`` sub-dict records the outcome. ``DrillQuit`` propagates (the caller decides what
    quit means)."""
    tag = " [dim](follow-up)[/dim]" if is_follow_on else ""
    console.print(f"\n[bold]Read aloud{tag}:[/bold] [cyan]{drill.prompt}[/cyan]")
    if drill.say_like:
        console.print(f"  [dim]Say it like:[/dim] {drill.say_like}")

    _hear_first(drill, speak=speak, key_reader=key_reader, console=console, tts_on=tts_on, ui_sleep=ui_sleep)
    status, flags, detail = _score_once(
        drill, contrast=contrast, scorer=scorer, record=record, scratch_dir=scratch_dir,
        label=f"drill: {drill.prompt}",
    )
    _print_outcome(console, status, flags, detail)

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
        # Focused per-sound teaching beat FIRST: show the respelling + model the flagged
        # word(s) in isolation at the slower rate, then run the bounded retry (FR-006, P2).
        _teach_sound(
            drill, flags, speak=speak, teach_speak=teach_speak, console=console,
            tts_on=tts_on, ui_sleep=ui_sleep,
        )
        attempts, outcome, final_flags = 1, "still_off", flags
        try:
            for _ in range(retries):
                console.print("  [dim]Now once more — listen and repeat.[/dim]")
                _hear_first(drill, speak=speak, key_reader=key_reader, console=console, tts_on=tts_on, ui_sleep=ui_sleep)
                r_status, r_flags, r_detail = _score_once(
                    drill, contrast=contrast, scorer=scorer, record=record, scratch_dir=scratch_dir,
                    label=f"retry: {drill.prompt}",
                )
                attempts += 1
                final_flags = r_flags
                if r_status == "not_captured":
                    outcome = "not_captured"
                    break
                if r_status == "error":
                    # Surface the real reason instead of pretending it was "still a bit off".
                    # A scoring/mic failure is its OWN outcome — never conflate it with a
                    # scored-but-still-flagged result (would print a contradictory "still off"
                    # line and persist a false verdict to the report).
                    _print_outcome(console, "error", [], r_detail)
                    outcome = "error"
                    break
                if r_status == "scored" and not r_flags:
                    outcome = "improved"
                    break
                outcome = "still_off"
        except DrillQuit as quit_exc:
            # Quit during a retry: keep the already-scored first attempt + the retry progress so
            # far on the exception, so run_drill_block preserves this flagged drill (not dropped).
            item["retry"] = {"attempts": attempts, "outcome": outcome, "final_flags": final_flags}
            quit_exc.item = item
            raise
        if outcome == "improved":
            console.print("  [green]Better — that sound is clear now ✓[/green]")
        elif outcome == "not_captured":
            console.print("  [dim]not captured — moving on[/dim]")
        elif outcome == "error":
            pass  # the actionable "couldn't score" reason was already printed above (no verdict)
        else:
            console.print("  [dim]Still a little off — keep practising; moving on.[/dim]")
        item["retry"] = {"attempts": attempts, "outcome": outcome, "final_flags": final_flags}

    return item
