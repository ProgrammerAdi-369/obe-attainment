"""Steps 2 to 5 (docs/PROJECT.md section 8): student scores, class CO attainment, level, Table E.

Pure functions, full precision; rounding happens only in reports.
"""

from typing import NamedTuple


class CoScore(NamedTuple):
    internal: float  # I_ij, 0 to 100
    end_term: float  # E_i, 0 to 100, the same for every CO (OPEN: O14)
    total: float  # A_ij = split_internal * I_ij + split_end_term * E_i


def internal_scores(
    marks: dict[str, float],
    max_marks: dict[str, float],
    weights: dict[str, dict[str, float]],
) -> dict[str, float]:
    """I_ij = sum_t (x_it / M_t) * w_tj. A tool with weight 0 in a CO adds 0 whatever the marks."""
    co_codes = next(iter(weights.values())).keys()
    return {
        co: sum(marks[t] / max_marks[t] * w[co] for t, w in weights.items()) for co in co_codes
    }


def co_scores(
    marks: dict[str, float],
    max_marks: dict[str, float],
    weights: dict[str, dict[str, float]],
    end_term_marks: float,
    end_term_max: float,
    split_internal: float,
    split_end_term: float,
) -> dict[str, CoScore]:
    """Per CO: internal score and attainment. The end-term is converted to 100 (x2.5 for 40 marks)."""
    end_term = 100 * end_term_marks / end_term_max
    return {
        co: CoScore(i, end_term, split_internal * i + split_end_term * end_term)
        for co, i in internal_scores(marks, max_marks, weights).items()
    }


def score_students(
    students: dict[str, tuple[dict[str, float | None], float | None]],
    max_marks: dict[str, float],
    weights: dict[str, dict[str, float]],
    end_term_max: float,
    split_internal: float,
    split_end_term: float,
) -> tuple[dict[str, dict[str, CoScore]], dict[str, list[str]]]:
    """Score every student; a student with a missing mark is flagged and left out of the processing.

    students: id -> (marks by tool, end-term marks). A mark is missing when it is None or absent.
    Returns (scores of the complete students, flagged id -> names of the missing marks). The caller
    keeps the flagged list; flagged students are not in the scores, so they are not in any average.
    """
    scores, flagged = {}, {}
    for sid, (marks, end_term) in students.items():
        missing = [t for t in weights if marks.get(t) is None]
        if end_term is None:
            missing.append("end_term")
        if missing:
            flagged[sid] = missing
        else:
            scores[sid] = co_scores(
                marks, max_marks, weights, end_term, end_term_max, split_internal, split_end_term
            )
    return scores, flagged


# ------------------------------------------------ steps 4 and 5: class level (Tables A, B, E)


class ClassCo(NamedTuple):
    direct_pct: float  # D_j, average of the student values
    direct_level: int  # level of D_j against the target
    total_pct: float  # Total_j; equals D_j while the indirect part is off
    final_level: int  # F_j
    status: str  # "Attained" when Total_j reaches the target


def co_level(pct: float, target: float, levels: list[int], floor_pct: float) -> int:
    """Highest level at or above the target, middle from the floor up to the target, else lowest.

    OPEN: O13. With a target at or below the floor the middle level never occurs.
    """
    if pct >= target:
        return levels[0]
    return levels[1] if pct >= floor_pct else levels[2]


def total_attainment(
    direct: float,
    indirect: float | None,
    direct_weight: float,
    indirect_weight: float,
    indirect_enabled: bool,
) -> float:
    """80% direct plus 20% indirect; while the survey is off the total is the direct value."""
    if not indirect_enabled:  # OPEN: O10
        return direct
    if indirect is None:
        raise ValueError("indirect attainment is enabled but no survey value was given")
    return direct_weight * direct + indirect_weight * indirect


def class_co_result(
    totals: list[float],
    target: float,
    levels: list[int],
    floor_pct: float,
    direct_weight: float,
    indirect_weight: float,
    indirect_enabled: bool,
    indirect_pct: float | None = None,
) -> ClassCo:
    """Class average of one CO's student values, its level, total and status."""
    if not totals:
        raise ValueError("no student values to average")
    direct = sum(totals) / len(totals)
    level = co_level(direct, target, levels, floor_pct)
    if indirect_enabled:  # OPEN: O10, how the indirect value is levelled is not yet explained
        raise NotImplementedError("indirect level is not defined until the faculty explain it")
    total = total_attainment(direct, indirect_pct, direct_weight, indirect_weight, indirect_enabled)
    return ClassCo(direct, level, total, level, "Attained" if total >= target else "Not attained")


def overall_co_attainment(results: dict[str, ClassCo]) -> float:
    """Table E: the average of the final CO levels."""
    return sum(r.final_level for r in results.values()) / len(results)
