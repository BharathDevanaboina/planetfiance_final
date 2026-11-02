"""Building a shuffled paper from a set, and grading the answers.

Sets never change after upload (they are deleted and re-uploaded instead), so a loaded
set is cached in memory by its id. This keeps exam starts fast.
"""

from __future__ import annotations

import random
import threading
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.exam.constants import SECTION_TITLES
from app.modules.exam.models import ExamPassage, ExamQuestion, ExamSet


@dataclass(frozen=True)
class OptionSnap:
    id: uuid.UUID
    content: str
    is_correct: bool


@dataclass(frozen=True)
class QuestionSnap:
    id: uuid.UUID
    section: str
    subsection: str
    position: int
    passage_id: uuid.UUID | None
    content: str
    options: tuple[OptionSnap, ...]

    @property
    def correct_option_id(self) -> uuid.UUID:
        return next(o.id for o in self.options if o.is_correct)


@dataclass(frozen=True)
class PassageSnap:
    id: uuid.UUID
    section: str
    content: str
    question_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class SetSnapshot:
    slot: int
    slot: int
    name: str
    questions: dict[uuid.UUID, QuestionSnap]
    passages: dict[uuid.UUID, PassageSnap]

    def ordered_questions(self) -> list[QuestionSnap]:
        return sorted(self.questions.values(), key=lambda q: (q.section, q.position))


_cache: dict[int, SetSnapshot] = {}
_lock = threading.Lock()


def load_snapshot(db: Session, set_slot: int) -> SetSnapshot | None:
    with _lock:
        cached = _cache.get(set_slot)
    if cached:
        return cached

    exam_set = db.get(ExamSet, set_slot)
    if exam_set is None:
        return None

    questions = list(db.scalars(select(ExamQuestion).where(ExamQuestion.exam_set_slot == set_slot)))
    passages = list(db.scalars(select(ExamPassage).where(ExamPassage.exam_set_slot == set_slot)))

    q_snaps = {
        q.id: QuestionSnap(
            id=q.id,
            section=q.section,
            subsection=q.subsection,
            position=q.position,
            passage_id=q.passage_id,
            content=q.content,
            options=tuple(OptionSnap(o.id, o.content, o.is_correct) for o in q.options),
        )
        for q in questions
    }

    p_snaps = {
        p.id: PassageSnap(
            id=p.id,
            section=p.section,
            content=p.content,
            question_ids=tuple(
                q.id for q in sorted(q_snaps.values(), key=lambda x: x.position) if q.passage_id == p.id
            ),
        )
        for p in passages
    }

    snapshot = SetSnapshot(exam_set.slot, exam_set.name, q_snaps, p_snaps)
    with _lock:
        if len(_cache) > 10:
            _cache.clear()
        _cache[set_slot] = snapshot
    return snapshot


def evict(set_slot: int) -> None:
    with _lock:
        _cache.pop(set_slot, None)


def _question_payload(q: QuestionSnap, number: int, rng: random.Random) -> dict:
    options = list(q.options)
    rng.shuffle(options)
    return {
        "id": q.id,
        "number": number,
        "subsection": q.subsection,
        "content": q.content,
        "options": [{"id": o.id, "content": o.content} for o in options],
    }


def build_paper(snapshot: SetSnapshot, rng: random.Random) -> list[dict]:
    """Sections stay in order A, B, C. Inside each section the questions (and passage groups) are
    shuffled; questions of a passage stay together, shuffled among themselves; options are shuffled."""
    sections = []
    number = 0
    for code, title in SECTION_TITLES.items():
        units: list[tuple[str, uuid.UUID]] = [
            ("question", q.id)
            for q in snapshot.questions.values()
            if q.section == code and q.passage_id is None
        ]
        units += [
            ("passage", p.id) for p in snapshot.passages.values() if p.section == code and p.question_ids
        ]
        units.sort(key=lambda u: str(u[1]))  # deterministic base order before shuffling
        rng.shuffle(units)
        items = []
        for kind, unit_id in units:
            if kind == "question":
                number += 1
                items.append(
                    {
                        "type": "question",
                        "question": _question_payload(snapshot.questions[unit_id], number, rng),
                    }
                )
            else:
                passage = snapshot.passages[unit_id]
                qids = list(passage.question_ids)
                rng.shuffle(qids)
                group = []
                for qid in qids:
                    number += 1
                    group.append(_question_payload(snapshot.questions[qid], number, rng))
                items.append(
                    {
                        "type": "passage",
                        "passage": {"id": passage.id, "content": passage.content},
                        "questions": group,
                    }
                )
        count = sum(1 if item["type"] == "question" else len(item["questions"]) for item in items)
        sections.append({"code": code, "title": title, "question_count": count, "items": items})
    return sections


def grade(
    snapshot: SetSnapshot,
    answers: dict[uuid.UUID, uuid.UUID | None],
) -> dict:
    per_section = {code: {"correct": 0, "incorrect": 0, "unanswered": 0, "max": 0} for code in SECTION_TITLES}
    review = []
    for q in snapshot.ordered_questions():
        chosen = answers.get(q.id)
        correct_id = q.correct_option_id
        stats = per_section[q.section]
        stats["max"] += 1
        if chosen is None:
            status = "unanswered"
        elif chosen == correct_id:
            status = "correct"
        else:
            status = "incorrect"
        stats[status] += 1
        review.append(
            {
                "question_id": q.id,
                "section": q.section,
                "selected_option_id": chosen,
                "correct_option_id": correct_id,
                "status": status,
                "is_correct": status == "correct",
            }
        )

    sections = [
        {
            "code": code,
            "title": SECTION_TITLES[code],
            "score": stats["correct"],
            "max_score": stats["max"],
            "correct": stats["correct"],
            "incorrect": stats["incorrect"],
            "unanswered": stats["unanswered"],
        }
        for code, stats in per_section.items()
    ]
    return {
        "total_score": sum(stats["correct"] for stats in per_section.values()),
        "max_score": sum(stats["max"] for stats in per_section.values()),
        "correct": sum(stats["correct"] for stats in per_section.values()),
        "incorrect": sum(stats["incorrect"] for stats in per_section.values()),
        "unanswered": sum(stats["unanswered"] for stats in per_section.values()),
        "sections": sections,
        "review": review,
    }
