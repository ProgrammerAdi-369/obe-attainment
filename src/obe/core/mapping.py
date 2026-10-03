"""Step 6 (docs/PROJECT.md section 8): hours per CO and baseline mapping strength (Tables 4 to 6).

Pure functions, plain data. The baseline is a proposal; only the teachers' final mapping (Table 7)
is used in the calculation.
"""

from collections.abc import Sequence
from typing import NamedTuple


class HoursRow(NamedTuple):
    theory: float
    lab: float
    share_pct: float
    strength: int  # baseline strength from the hours rule


def baseline_strength(share_pct: float, bands: Sequence[tuple[int, float, bool]]) -> int:
    """Strength of the first band the share reaches; bands are (strength, min_pct, inclusive)."""
    for strength, min_pct, inclusive in bands:
        if share_pct > min_pct or (inclusive and share_pct == min_pct):
            return strength
    raise ValueError(f"share {share_pct} is below every band")


def hours_summary(
    co_codes: list[str],
    units: list[tuple[float, list[str]]],
    labs: list[tuple[float, list[str]]],
    bands: Sequence[tuple[int, float, bool]],
) -> dict[str, HoursRow]:
    """Table 4: theory plus lab hours per CO, its share of all hours and the baseline strength.

    units / labs: (hours, COs). Hours of an item with several COs are split equally (OPEN: O11).
    OPEN: O3, the hours rule gives the baseline; the teachers' final mapping overrides it.
    """
    theory, lab = dict.fromkeys(co_codes, 0.0), dict.fromkeys(co_codes, 0.0)
    for hours, cos in units:
        for co in cos:
            theory[co] += hours / len(cos)
    for hours, cos in labs:
        for co in cos:
            lab[co] += hours / len(cos)
    total = sum(theory.values()) + sum(lab.values())
    if total <= 0:
        raise ValueError("no instruction hours to share between the COs")
    return {
        co: HoursRow(theory[co], lab[co], 100 * (theory[co] + lab[co]) / total,
                     baseline_strength(100 * (theory[co] + lab[co]) / total, bands))
        for co in co_codes
    }


def baseline_mapping(
    ticks: dict[str, dict[str, int]], strengths: dict[str, int]
) -> dict[str, dict[str, int]]:
    """Table 6: the tick table (Table 1) times each CO's baseline strength."""
    return {co: {po: tick * strengths[co] for po, tick in row.items()} for co, row in ticks.items()}
