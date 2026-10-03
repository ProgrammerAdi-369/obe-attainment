"""Step 1 (docs/PROJECT.md section 8): weight of each tool in each CO. Pure functions, plain data."""


def marks_per_co(
    co_codes: list[str],
    cca_marks: dict[str, dict[str, float]],
    lca_max: dict[str, float],
    lab_cos: list[list[str]],
) -> dict[str, dict[str, float]]:
    """Marks each tool carries per CO. Intermediate table: stored for traceability, never shown.

    cca_marks: fixed by the syllabus, tool -> CO -> marks (a missing CO means 0).
    lca_max / lab_cos: each of the N lab assignments weighs 1/N of every LCA tool's maximum, and the
    weight of an assignment with several COs is split equally between them (OPEN: O11).
    """
    out = {t: {co: marks.get(co, 0.0) for co in co_codes} for t, marks in cca_marks.items()}
    if lca_max and not lab_cos:
        raise ValueError("an LCA tool needs lab assignments to split its marks")
    for tool, total in lca_max.items():
        row = dict.fromkeys(co_codes, 0.0)
        for cos in lab_cos:
            for co in cos:
                row[co] += total / len(lab_cos) / len(cos)
        out[tool] = row
    return out


def tool_weights(marks: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Percentage weight of each tool in each CO: 100 * m_tj / sum_t m_tj, so each CO adds up to 100.

    OPEN: O12, these stated weights are used; the workbook's CO2 and CO4 student values differ.
    """
    co_codes = next(iter(marks.values())).keys()
    totals = {co: sum(row[co] for row in marks.values()) for co in co_codes}
    for co, total in totals.items():
        if total <= 0:
            raise ValueError(f"{co} has no marks allocated, so its tool weights are undefined")
    return {t: {co: 100 * row[co] / totals[co] for co in co_codes} for t, row in marks.items()}
