"""Pure-numpy CTC forced alignment + Goodness-of-Pronunciation (016).

NO torch / transformers / k2 / ctc_segmentation — just numpy. The acoustic model
(``wav2vec2_engine.py``) produces a ``[T, V]`` log-posterior matrix; this module
force-aligns a KNOWN canonical phoneme-id sequence to it (standard CTC Viterbi over
the blank-extended label sequence) and scores each canonical phone by the mean
log-posterior over its aligned frames (GOP). The top competing phone over those
frames is the diagnosis suggestion.

Kept dependency-free on purpose (constitution: "standard library over dependencies;
boring over novel") so it installs with zero build risk and is unit-tested exactly
with synthetic posteriors — no model needed. See research.md D4.
"""

from __future__ import annotations

import numpy as np

_NEG = -1e30


def _extended(canonical_ids: list[int], blank_id: int) -> list[int]:
    """Blank-extended label sequence: blank, l1, blank, l2, ..., ln, blank (len 2n+1)."""
    ext = [blank_id]
    for c in canonical_ids:
        ext.append(c)
        ext.append(blank_id)
    return ext


def forced_align(
    canonical_ids: list[int], logp: np.ndarray, blank_id: int
) -> list[tuple[int, int]]:
    """Return an inclusive ``(start_frame, end_frame)`` per canonical token.

    Standard CTC forced alignment by Viterbi over the blank-extended sequence. A
    token that collapses to zero frames (e.g. fewer frames than tokens) falls back
    to its single best frame so every token gets a usable span. Monotonic,
    non-overlapping for the assigned (non-fallback) tokens.
    """
    logp = np.asarray(logp, dtype=np.float64)
    T = int(logp.shape[0])
    n = len(canonical_ids)
    if n == 0 or T == 0:
        return []

    ext = _extended(canonical_ids, blank_id)
    S = len(ext)
    alpha = np.full((T, S), _NEG)
    back = np.zeros((T, S), dtype=np.int64)

    # t = 0: only the first blank or the first label is reachable.
    alpha[0, 0] = logp[0, ext[0]]
    if S > 1:
        alpha[0, 1] = logp[0, ext[1]]

    for t in range(1, T):
        for s in range(S):
            best_prev = s
            best_val = alpha[t - 1, s]
            if s - 1 >= 0 and alpha[t - 1, s - 1] > best_val:
                best_val, best_prev = alpha[t - 1, s - 1], s - 1
            # skip-blank transition: only into a non-blank state whose label differs
            # from the label two states back (standard CTC rule).
            if (
                s - 2 >= 0
                and ext[s] != blank_id
                and ext[s] != ext[s - 2]
                and alpha[t - 1, s - 2] > best_val
            ):
                best_val, best_prev = alpha[t - 1, s - 2], s - 2
            if best_val <= _NEG / 2:
                alpha[t, s] = _NEG
                back[t, s] = s
            else:
                alpha[t, s] = best_val + logp[t, ext[s]]
                back[t, s] = best_prev

    # Termination: the path ends on the last label or the trailing blank.
    end_state = S - 2 if (S >= 2 and alpha[T - 1, S - 2] >= alpha[T - 1, S - 1]) else S - 1

    states = np.zeros(T, dtype=np.int64)
    s = end_state
    for t in range(T - 1, -1, -1):
        states[t] = s
        s = int(back[t, s])

    spans: list[tuple[int, int]] = []
    for i in range(n):
        st = 2 * i + 1
        frames = np.where(states == st)[0]
        if len(frames) == 0:
            f = int(np.argmax(logp[:, canonical_ids[i]]))
            spans.append((f, f))
        else:
            spans.append((int(frames[0]), int(frames[-1])))
    return spans


def gop_scores(
    canonical_ids: list[int], spans: list[tuple[int, int]], logp: np.ndarray
) -> list[float]:
    """Per-token GOP = mean log-posterior of the canonical phone over its frames.

    Values are <= 0; nearer 0 = better pronounced. A collapsed single-frame span
    still yields a value (that frame's log-posterior)."""
    logp = np.asarray(logp, dtype=np.float64)
    out: list[float] = []
    for cid, (a, b) in zip(canonical_ids, spans, strict=True):
        a, b = (a, b) if a <= b else (b, a)
        out.append(float(np.mean(logp[a : b + 1, cid])))
    return out


def top_competitor(
    span: tuple[int, int], logp: np.ndarray, blank_id: int, exclude_id: int
) -> tuple[int, float]:
    """Best non-blank phone over a span (excluding the expected phone) + its margin.

    Returns ``(competitor_id, margin)`` where ``margin = mean logp[competitor] -
    mean logp[expected]`` over the span (positive ⇒ the competitor beat the expected
    phone, i.e. a likely substitution). Diagnosis is a *suggestion* (FR-009)."""
    logp = np.asarray(logp, dtype=np.float64)
    a, b = (span[0], span[1]) if span[0] <= span[1] else (span[1], span[0])
    window = logp[a : b + 1]  # [L, V]
    mean_over_window = window.mean(axis=0)  # [V]
    masked = mean_over_window.copy()
    masked[blank_id] = _NEG
    if 0 <= exclude_id < masked.shape[0]:
        masked[exclude_id] = _NEG
    comp_id = int(np.argmax(masked))
    margin = float(mean_over_window[comp_id] - mean_over_window[exclude_id])
    return comp_id, margin
