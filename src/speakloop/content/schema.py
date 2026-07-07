"""Q&A dataclasses + validation per data-model.md §1, §2."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_ID_LEN = 40
MAX_QUESTION_LEN = 1000
MAX_IDEAL_ANSWER_LEN = 4000


class QASchemaError(ValueError):
    """Schema-level validation error. Includes the offending entry id."""

    def __init__(
        self,
        message: str,
        *,
        entry_id: str | None = None,
        missing_field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.entry_id = entry_id
        self.missing_field = missing_field


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    ideal_answer: str
    tags: list[str] = field(default_factory=list)
    difficulty: str | None = None
    voice_override: str | None = None
    # 010-interview-loop (P5): additive optional question type. Absent → definition,
    # so existing question files load unchanged. The question-file `schema_version`
    # is NOT bumped (it is separate from the report schema_version).
    type: str = "definition"


@dataclass(frozen=True)
class QAFile:
    schema_version: int
    questions: list[Question]
    warnings: list[str] = field(default_factory=list)


_REQUIRED_FIELDS = ("id", "question", "ideal_answer")
_KNOWN_FIELDS = {"id", "question", "ideal_answer", "tags", "difficulty", "voice_override", "type"}
_VALID_DIFFICULTIES = {"easy", "medium", "hard"}
_VALID_TYPES = {"definition", "behavioral", "hypothetical"}


def parse(doc: dict) -> QAFile:
    """Validate a parsed YAML mapping; return a QAFile or raise QASchemaError."""
    if not isinstance(doc, dict):
        raise QASchemaError(f"Q&A file root must be a mapping (got {type(doc).__name__}).")

    schema_version = doc.get("schema_version")
    if schema_version != 1:
        raise QASchemaError(f"Unsupported schema_version: {schema_version!r}; expected 1.")

    raw_questions = doc.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise QASchemaError("`questions` must be a non-empty list.")

    questions: list[Question] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for idx, entry in enumerate(raw_questions):
        if not isinstance(entry, dict):
            raise QASchemaError(
                f"questions[{idx}] is not a mapping.",
                entry_id=str(idx),
            )

        entry_id = entry.get("id")
        # Required fields
        for field_name in _REQUIRED_FIELDS:
            if entry.get(field_name) is None or (
                isinstance(entry.get(field_name), str) and not entry.get(field_name).strip()
            ):
                raise QASchemaError(
                    f"Question {entry_id!r}: missing or empty required field {field_name!r}.",
                    entry_id=str(entry_id) if entry_id else f"index {idx}",
                    missing_field=field_name,
                )

        qid = str(entry["id"]).strip()
        if len(qid) > MAX_ID_LEN:
            raise QASchemaError(
                f"Question {qid!r}: `id` exceeds {MAX_ID_LEN} chars.",
                entry_id=qid,
            )
        if not KEBAB_CASE.match(qid):
            raise QASchemaError(
                f"Question {qid!r}: `id` must be kebab-case (lowercase letters, digits, hyphens).",
                entry_id=qid,
            )
        if qid in seen_ids:
            raise QASchemaError(f"Question {qid!r}: duplicate id.", entry_id=qid)
        seen_ids.add(qid)

        q_text = str(entry["question"]).strip()
        a_text = str(entry["ideal_answer"]).strip()
        if len(q_text) > MAX_QUESTION_LEN:
            raise QASchemaError(
                f"Question {qid!r}: `question` exceeds {MAX_QUESTION_LEN} chars.",
                entry_id=qid,
            )
        if len(a_text) > MAX_IDEAL_ANSWER_LEN:
            raise QASchemaError(
                f"Question {qid!r}: `ideal_answer` exceeds {MAX_IDEAL_ANSWER_LEN} chars.",
                entry_id=qid,
            )

        difficulty = entry.get("difficulty")
        # `not isinstance(..., str)` short-circuits before the set-membership test so a
        # list/dict value (unhashable) degrades to a warning + default instead of TypeError.
        if difficulty is not None and (
            not isinstance(difficulty, str) or difficulty not in _VALID_DIFFICULTIES
        ):
            warnings.append(f"Question {qid!r}: unknown difficulty {difficulty!r}; ignored.")
            difficulty = None

        tags = entry.get("tags") or []
        if not isinstance(tags, list):
            warnings.append(f"Question {qid!r}: `tags` is not a list; ignored.")
            tags = []
        tags = [str(t) for t in tags]

        voice_override = entry.get("voice_override")
        if voice_override is not None:
            voice_override = str(voice_override)

        qtype = entry.get("type") or "definition"
        # Same guard as `difficulty`: a non-str (list/dict) `type` is unhashable, so
        # short-circuit before the membership test → warning + "definition" default.
        if not isinstance(qtype, str) or qtype not in _VALID_TYPES:
            warnings.append(f"Question {qid!r}: unknown type {qtype!r}; treated as definition.")
            qtype = "definition"

        unknown = set(entry.keys()) - _KNOWN_FIELDS
        if unknown:
            warnings.append(f"Question {qid!r}: unknown keys ignored: {sorted(unknown)}.")

        questions.append(
            Question(
                id=qid,
                question=q_text,
                ideal_answer=a_text,
                tags=tags,
                difficulty=difficulty,
                voice_override=voice_override,
                type=qtype,
            )
        )

    return QAFile(schema_version=1, questions=questions, warnings=warnings)
