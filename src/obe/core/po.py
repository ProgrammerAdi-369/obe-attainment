"""Step 7 (docs/PROJECT.md section 8): PO and PSO target, actual and gap (Table F).

Pure functions, plain data, full precision.
"""

from typing import NamedTuple

from obe.core.attainment import co_level


class PoResult(NamedTuple):
    target: float | None  # None when no CO maps to the PO
    actual: float | None
    gap: float | None  # target - actual; positive means an action plan


def po_targets(final_map: dict[str, dict[str, int]]) -> dict[str, float | None]:
    """Target_p: the mean of the non-zero final mapping strengths of the PO across the COs."""
    pos = next(iter(final_map.values())).keys()
    out: dict[str, float | None] = {}
    for p in pos:
        vals = [row[p] for row in final_map.values() if row[p] > 0]
        out[p] = sum(vals) / len(vals) if vals else None
    return out


def po_results(
    final_map: dict[str, dict[str, int]], overall_co: float, max_level: int
) -> dict[str, PoResult]:
    """Actual_p = Target_p * overall CO attainment / max level, and Gap_p = Target_p - Actual_p."""
    return {
        p: PoResult(t, None, None) if t is None
        else PoResult(t, t * overall_co / max_level, t - t * overall_co / max_level)
        for p, t in po_targets(final_map).items()
    }


def student_po_attainment(
    final_map: dict[str, dict[str, int]],
    totals: dict[str, float],
    targets: dict[str, float],
    levels: list[int],
    floor_pct: float,
    enabled: bool,
) -> dict[str, float | None] | None:
    """One course, one student: step 7 with the student's own overall CO attainment.

    The student's overall value is the average of the levels of their own CO values A_ij against
    the CO targets. OPEN: O9, off until the faculty confirm; returns None while disabled.
    """
    if not enabled:
        return None
    overall = sum(co_level(totals[co], targets[co], levels, floor_pct) for co in totals) / len(totals)
    return {
        p: None if t is None else t * overall / levels[0]
        for p, t in po_targets(final_map).items()
    }


def average_over_courses(per_course: list[dict[str, float | None]]) -> dict[str, float | None]:
    """Batch roll-up for one student: each PO averaged over the courses where its target is non-zero."""
    out: dict[str, float | None] = {}
    for p in per_course[0]:
        vals = [c[p] for c in per_course if c[p] is not None]
        out[p] = sum(vals) / len(vals) if vals else None
    return out
