"""Answer shadowing — Mode B pure logic (018-self-practice-modes).

Splits a question's ideal answer into sentences (abbreviation-aware) and judges a
learner's spoken repeat for content-word completeness. Pure logic only — no engine
import, deterministic and offline. The public API is wired at the bottom of this
module once the submodules land (T030).
"""

from __future__ import annotations
