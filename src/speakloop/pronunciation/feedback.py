"""Calibrated drill-feedback wording (016, FR-009).

Turns the drill-block result dict into Markdown for the report's Pronunciation
section, and shorter lines for the live terminal. Calibration rule: LEAD WITH
DETECTION ("this sound was off"); present any phone DIAGNOSIS as a hedged
SUGGESTION, never a verdict. Pure formatter — no engine import.
"""

from __future__ import annotations

_HEADER = "## Pronunciation drills"
_DISCLAIMER = (
    "_Read-aloud practice. Detection (a sound was off) is reliable; any specific "
    '"heard as …" guess is a suggestion, not a verdict._'
)


def _flag_line(flag: dict) -> str:
    """One detection-led line; diagnosis only when confident, always hedged."""
    expected = str(flag.get("expected", "")).strip()
    word = str(flag.get("word", "")).strip()
    where = f" in *{word}*" if word else ""
    line = f"The **{expected}** sound{where} sounded off."
    if flag.get("confident_diagnosis") and flag.get("competitor"):
        comp = str(flag["competitor"]).strip()
        line += f" _(suggestion: it may have come out closer to **{comp}**)_"
    return line


def _retry_line(retry: dict) -> str | None:
    """One additive, encouraging line summarising a bounded retry (017, FR-006). None when
    no retry ran. Detection-level — never a graded verdict."""
    outcome = str(retry.get("outcome", "")).strip()
    if outcome == "improved":
        return "  - On retry: better — that sound is clear now ✓"
    if outcome == "still_off":
        return "  - On retry: still a little off — worth more practice."
    if outcome == "not_captured":
        return "  - On retry: not captured."
    # "error" (the retry could not be scored) carries NO pronunciation verdict — the report
    # must not claim the sound is "still off". Returning None omits the retry line entirely.
    return None


def render_drills_section(drills: dict | None) -> str | None:
    """Markdown for the report (data-model §4). None when there are no items.

    Additive over 016: a per-item retry line (when a retry ran) and a closing "tricky sounds"
    line (when the summary has them). Both omitted when absent → a no-retry/no-tricky report is
    byte-identical to a 016 report."""
    if not drills or not drills.get("items"):
        return None
    lines = [_HEADER, "", _DISCLAIMER, ""]
    note = str(drills.get("engine_note", "")).strip()
    if note:
        lines += [f"_{note}_", ""]
    for it in drills["items"]:
        prompt = str(it.get("text") or it.get("prompt") or "").strip()
        tag = " *(follow-up)*" if it.get("is_follow_on") else ""
        status = it.get("status")
        retry = it.get("retry") if isinstance(it.get("retry"), dict) else None
        if status == "not_captured":
            lines.append(f"- **{prompt}**{tag} — _not captured (read right after the prompt)_")
            continue
        if status == "error":
            lines.append(f"- **{prompt}**{tag} — _could not score this one_")
            continue
        flags = it.get("flags") or []
        if not flags:
            lines.append(f"- **{prompt}**{tag} — clear ✓")
            continue
        lines.append(f"- **{prompt}**{tag}")
        for fl in flags:
            lines.append(f"  - {_flag_line(fl)}")
            tip = str(fl.get("tip", "")).strip()
            if tip:
                lines.append(f"    - Tip: {tip}")
        if retry and (rl := _retry_line(retry)):
            lines.append(rl)
    tricky = (drills.get("summary") or {}).get("tricky_sounds") or []
    tricky = [str(t).strip() for t in tricky if str(t).strip()]
    if tricky:
        lines += ["", f"_Tricky sounds this session: {', '.join(tricky)}._"]
    return "\n".join(lines)


def live_flag_summary(flags: list[dict]) -> str:
    """A short one/two-line summary for the terminal right after a drill."""
    if not flags:
        return "clear ✓"
    return "; ".join(_flag_line(fl).rstrip(".") for fl in flags)
