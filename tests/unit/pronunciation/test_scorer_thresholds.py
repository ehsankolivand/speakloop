"""017 — calibrated flag thresholds + the espeak-free load contract (no model loaded).

The flag decision is exercised on SYNTHETIC posteriors fed straight to
``Wav2Vec2Scorer._score_against_canonical`` (``_sym2id``/``_blank_id`` set by hand), so this
needs no model, no torch, no espeak — it pins the calibration in place:

* a CLEAN target (expected phone dominates its span) → NO flag (the loose bound);
* a CLEAR substitution (a competitor dominates the span) → flagged (the tight bound);
* a BORDERLINE-but-acceptable target (mild competitor, decent GOP) → NO flag — this is the
  fix for the over-flagging the learner hit on /w/ (the first-pass margin of 0.5 flagged it).
"""

from __future__ import annotations

import numpy as np
import pytest

from speakloop.pronunciation import wav2vec2_engine
from speakloop.pronunciation.wav2vec2_engine import Wav2Vec2Scorer

pytestmark = pytest.mark.unit

# Tiny vocab: blank(pad)=0, the target /w/, its competitor /ɹ/, and a following vowel /iː/.
_VOCAB = {"<pad>": 0, "w": 1, "ɹ": 2, "iː": 3}
_CANON = ["w", "iː"]
_TARGETS = [{"index": 0, "word": "we"}]
_COMPETS = ["ɹ"]


def _scorer() -> Wav2Vec2Scorer:
    s = Wav2Vec2Scorer()
    s._sym2id = dict(_VOCAB)
    s._blank_id = 0
    return s


def _logp(rows: list[list[float]]) -> np.ndarray:
    p = np.array(rows, dtype=float)
    p = p / p.sum(axis=1, keepdims=True)
    return np.log(p)


def _score(rows):
    s = _scorer()
    logp = _logp(rows)
    return s._score_against_canonical(
        logp, _CANON, _TARGETS, tip="t", competitors=_COMPETS,
        drill_id="d", text="we", contrast_id="w_r",
    )


def test_clean_target_is_not_flagged():
    # /w/ dominates frames 0-2, /iː/ frames 3-5 → high GOP, competitor loses.
    res = _score([[0.02, 0.94, 0.02, 0.02]] * 3 + [[0.02, 0.02, 0.02, 0.94]] * 3)
    assert res.status == "scored"
    assert not res.flags, "a cleanly-pronounced target must never flag"


def test_clear_substitution_is_flagged():
    # The learner said /ɹ/ where /w/ was expected → /w/ GOP collapses, /ɹ/ wins big.
    res = _score([[0.02, 0.05, 0.91, 0.02]] * 3 + [[0.02, 0.01, 0.01, 0.96]] * 3)
    assert res.flags, "a clear substitution on the target must be flagged"
    fl = res.flags[0]
    assert fl.expected == "w"
    assert fl.competitor == "ɹ" and fl.competitor_margin > wav2vec2_engine._COMPETITOR_FLAG_MARGIN


def test_borderline_acceptable_target_is_not_overflagged():
    # GOP decent (> the flag bound) and the competitor only mildly ahead (margin in the old
    # 0.5..new 1.5 dead-band) → NOT flagged. This is the calibration that stops an accented-
    # but-fine /w/ from over-flagging (the learner's reported symptom).
    res = _score([[0.10, 0.28, 0.60, 0.02]] * 3 + [[0.02, 0.02, 0.02, 0.94]] * 3)
    fl_w = [f for f in res.flags if f.expected == "w"]
    margin_would_trip_old = 0.5  # the first-pass value
    # sanity: this case sits in the dead-band the new threshold opened up
    assert wav2vec2_engine._COMPETITOR_FLAG_MARGIN > margin_would_trip_old
    assert not fl_w, "a borderline-but-acceptable target must not over-flag under the new margin"


def test_strong_substitution_still_caught_by_margin_when_gop_is_borderline():
    # GOP just above the bound but the competitor dominates by > the margin → still flagged
    # (the corroborating competitor signal is retained, just set higher).
    res = _score([[0.03, 0.15, 0.80, 0.02]] * 3 + [[0.02, 0.02, 0.02, 0.94]] * 3)
    assert any(f.expected == "w" for f in res.flags)


def test_threshold_constants_are_the_calibrated_values():
    # Lock the calibration: GOP bound separates clean (≳ -0.9) from substituted (≲ -2.4); the
    # competitor margin sits between the clean (≤ 0) and substitution (≥ +2.0) clusters.
    assert wav2vec2_engine._GOP_FLAG_THRESHOLD == -2.0
    assert wav2vec2_engine._COMPETITOR_FLAG_MARGIN == 1.5


def _raw_score(w_logp: float, comp_logp: float):
    """Hand-build a log-posterior matrix so /w/ aligns to frames 0-2 with an EXACT GOP
    (``w_logp``) and an EXACT competitor (/ɹ/) value (``comp_logp``); /iː/ owns 3-5. Lets us
    land precisely on a flag threshold (the rule uses strict `<` / `>`, so a value exactly at
    the bound must NOT flag)."""
    import numpy as np

    lo = -8.0
    rows = []
    for _ in range(3):  # /w/ span: w=w_logp, competitor /ɹ/=comp_logp, rest low
        rows.append([lo, w_logp, comp_logp, lo])
    for _ in range(3):  # /iː/ span
        rows.append([lo, lo, lo, -0.1])
    logp = np.array(rows, dtype=np.float64)
    s = _scorer()
    return s._score_against_canonical(
        logp, _CANON, _TARGETS, tip="t", competitors=_COMPETS,
        drill_id="d", text="we", contrast_id="w_r",
    )


def test_gop_exactly_at_threshold_does_not_flag_but_just_below_does():
    g = wav2vec2_engine._GOP_FLAG_THRESHOLD  # -2.0
    # GOP exactly at the bound, competitor well below (no margin trip) → NOT flagged (strict <).
    assert not _raw_score(w_logp=g, comp_logp=g - 2.0).flags
    # A hair below the bound → flagged.
    assert _raw_score(w_logp=g - 0.01, comp_logp=g - 2.0).flags


def test_competitor_margin_exactly_at_threshold_does_not_flag_but_just_above_does():
    m = wav2vec2_engine._COMPETITOR_FLAG_MARGIN  # 1.5
    w = -0.3  # GOP well above the bound, so only the margin clause can decide
    # margin == m exactly → NOT flagged (strict >); a hair above → flagged.
    assert not _raw_score(w_logp=w, comp_logp=w + m).flags
    assert _raw_score(w_logp=w, comp_logp=w + m + 0.05).flags


def test_out_of_vocab_target_errors_instead_of_false_clear():
    """IMP-007: when the TARGET phone is absent from the model vocab, the model never
    evaluated the very sound being taught — the drill must report `error` (actionable),
    NOT `scored` with empty flags (which the runner renders as a false "clear ✓")."""
    s = Wav2Vec2Scorer()
    # Vocab lacks the target /w/ but has the rest of the canonical (/iː/) + competitor.
    s._sym2id = {"<pad>": 0, "ɹ": 1, "iː": 2}
    s._blank_id = 0
    logp = _logp([[0.02, 0.02, 0.96]] * 3 + [[0.02, 0.02, 0.96]] * 3)
    res = s._score_against_canonical(
        logp, _CANON, _TARGETS, tip="t", competitors=_COMPETS,
        drill_id="d", text="we", contrast_id="w_r",
    )
    assert res.status == "error"
    assert res.detail and "not in model vocab" in res.detail
    assert "w" in res.detail  # names the out-of-vocab target phone


def test_read_vocab_reads_json_without_a_tokenizer(tmp_path):
    # The espeak-free load path reads vocab.json DIRECTLY (no Wav2Vec2Processor / phonemizer).
    (tmp_path / "vocab.json").write_text('{"<pad>": 0, "w": 1, "\\u0279": 2}', encoding="utf-8")
    vocab = Wav2Vec2Scorer._read_vocab(tmp_path)
    assert vocab == {"<pad>": 0, "w": 1, "ɹ": 2}


def test_read_vocab_surfaces_a_specific_reason_when_malformed(tmp_path):
    from speakloop.pronunciation.interface import PronunciationError

    # Missing file → its own clear error.
    with pytest.raises(PronunciationError, match="vocab.json not found"):
        Wav2Vec2Scorer._read_vocab(tmp_path)
    # Malformed (non-int ids) → the SPECIFIC "could not read model vocab.json" reason, not a
    # generic load error (the type coercion is inside the handler).
    (tmp_path / "vocab.json").write_text('{"w": "notanint"}', encoding="utf-8")
    with pytest.raises(PronunciationError, match="could not read model vocab.json"):
        Wav2Vec2Scorer._read_vocab(tmp_path)


def test_load_path_does_not_use_the_espeak_phoneme_processor():
    # Regression for the P0 root cause: building Wav2Vec2Processor / the phoneme tokenizer
    # eagerly inits the espeak phonemizer and crashes the model load when espeak is absent.
    # The scorer must load only the feature extractor + the CTC model + vocab.json. (Match the
    # IMPORT + CONSTRUCTION, not bare names — the code comments explain *why* we avoid them.)
    import inspect

    src = inspect.getsource(wav2vec2_engine)
    import_lines = [ln for ln in src.splitlines() if "from transformers import" in ln]
    assert import_lines, "expected a function-local transformers import"
    imported = " ".join(import_lines)
    assert "Wav2Vec2FeatureExtractor" in imported
    assert "Wav2Vec2Processor" not in imported, "the espeak-coupled processor must not be imported"
    assert "Wav2Vec2Processor.from_pretrained" not in src
    assert "Wav2Vec2PhonemeCTCTokenizer(" not in src
