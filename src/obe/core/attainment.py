"""Steps 2 and 3 (docs/PROJECT.md section 8): student internal score and CO attainment.

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
