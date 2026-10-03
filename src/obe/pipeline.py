"""Calculate a whole course from validated config and marks. No database yet: plain data in and out.

The database steps (validate, load, store) come later; this is the calculate part, so the report can
be produced from a marks file and the course YAML alone. Student names are not part of the result.
"""

from dataclasses import dataclass

from obe.config import CourseConfig, ProgramOutcomes, Rules
from obe.core.attainment import (
    ClassCo,
    CoScore,
    class_co_result,
    overall_co_attainment,
    score_students,
)
from obe.core.mapping import HoursRow, baseline_mapping, hours_summary
from obe.core.po import PoResult, po_results, student_po_attainment
from obe.core.weights import tool_weights
from obe.ingest.marks import MarksData


@dataclass
class RunResult:
    course: CourseConfig
    rules: Rules
    pos: ProgramOutcomes
    weights: dict[str, dict[str, float]]  # tool -> CO -> weight %, the output of step 1
    hours: dict[str, HoursRow]  # Table 4 with the baseline strength (Table 5)
    baseline: dict[str, dict[str, int]]  # Table 6
    scores: dict[str, dict[str, CoScore]]  # student id -> CO -> score, scored students only
    flagged: dict[str, list[str]]  # student id -> missing marks; left out of the processing
    classes: dict[str, ClassCo]  # Tables A and B
    overall: float  # Table E
    po: dict[str, PoResult]  # Table F
    student_po: dict[str, dict[str, float | None]] | None  # None while the O9 flag is off
    snapshot: dict  # configuration used by this run


def calculate(course: CourseConfig, rules: Rules, pos: ProgramOutcomes, marks: MarksData) -> RunResult:
    cos = [c.code for c in course.cos]
    max_marks = {t.name: t.max_marks for t in course.tools if t.category != "END_TERM"}
    end_max = next(t.max_marks for t in course.tools if t.category == "END_TERM")
    weights = tool_weights(course.allocation())
    scores, flagged = score_students(
        marks.students, max_marks, weights, end_max, rules.split.internal, rules.split.end_term
    )

    lv, floor, ta = rules.level_scale.levels, rules.level_scale.floor_pct, rules.total_attainment
    classes = {
        co: class_co_result(
            [s[co].total for s in scores.values()],
            course.co_targets[co],
            lv,
            floor,
            ta.direct_weight,
            ta.indirect_weight,
            ta.indirect_enabled,
        )
        for co in cos
    }
    overall = overall_co_attainment(classes)

    bands = [(b.strength, b.min_pct, b.inclusive) for b in rules.hours_to_strength]
    hours = hours_summary(
        cos,
        [(u.theory_hours, u.co_codes) for u in course.units],
        [(x.lab_hours, x.co_codes) for x in course.labs],
        bands,
    )
    student_po = (
        {
            sid: student_po_attainment(
                course.co_po_final,
                {co: sc.total for co, sc in per_co.items()},
                course.co_targets,
                lv,
                floor,
                True,
            )
            for sid, per_co in scores.items()
        }
        if rules.student_po_enabled
        else None
    )
    return RunResult(
        course=course,
        rules=rules,
        pos=pos,
        weights=weights,
        hours=hours,
        baseline=baseline_mapping(course.co_po_ticks, {co: h.strength for co, h in hours.items()}),
        scores=scores,
        flagged=flagged,
        classes=classes,
        overall=overall,
        po=po_results(course.co_po_final, overall, lv[0]),
        student_po=student_po,
        snapshot={
            "rules": rules.model_dump(),
            "course": course.model_dump(by_alias=True),
            "programme_outcomes": pos.codes,
        },
    )
