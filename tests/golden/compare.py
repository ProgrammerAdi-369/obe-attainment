"""Golden comparison: recompute the sample course from the marks file and compare it with the workbook.

    py tests/golden/compare.py        writes docs/discrepancy_report.md

Reads only numbers from the original workbook (never the name column) and returns and writes
aggregates only: no names and no student identifiers.
"""

import glob
from pathlib import Path

from openpyxl import load_workbook

from obe.config import CONFIG_DIR, load_course, load_program_outcomes, load_rules
from obe.core.attainment import class_co_result, overall_co_attainment, score_students
from obe.core.weights import tool_weights
from obe.ingest.marks import load_marks

ROOT = Path(__file__).resolve().parents[2]
MARKS = ROOT / "data/sample/CET3011B_marks.xlsx"
WORKBOOK = next(iter(glob.glob(str(ROOT / "data/main file/*.xlsx"))), None)
REPORT = ROOT / "docs/discrepancy_report.md"
TOL = 0.1

# Tab 3 of the workbook (1-based columns): step-3 student table rows 661 to 951
FIRST, LAST = 661, 951
SERIAL, END_TERM = 1, 8
INTERNAL_COLS = [3, 4, 5, 6, 7]  # C to G, internal score per CO
TOTAL_COLS = [13, 17, 21, 25, 29]  # M, Q, U, Y, AC, CO attainment per CO
AVERAGE_ROW, TABLE_B_FIRST, OVERALL_ROW = 980, 995, 1000


def available() -> bool:
    return WORKBOOK is not None and MARKS.exists()


def read_workbook() -> dict:
    wb = load_workbook(WORKBOOK, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[2]
        rows = {n: r for n, r in enumerate(ws.iter_rows(min_row=660, max_row=1000, max_col=29, values_only=True), 660)}
    finally:
        wb.close()
    cell = lambda r, c: rows[r][c - 1]
    assert cell(660, SERIAL) == "Sr.No" and cell(AVERAGE_ROW, 2) == "Average", "workbook layout changed"
    assert cell(OVERALL_ROW, 10) == "Average CO Attainment", "workbook layout changed"
    students = {}
    for n in range(FIRST, LAST + 1):
        if isinstance(cell(n, SERIAL), (int, float)):
            students[str(int(cell(n, SERIAL)))] = {
                "end_term": cell(n, END_TERM),
                "internal": [cell(n, c) for c in INTERNAL_COLS],
                "total": [cell(n, c) for c in TOTAL_COLS],
            }
    return {
        "students": students,
        "typed_average": [cell(AVERAGE_ROW, c) for c in TOTAL_COLS],
        "table_b_direct": [cell(TABLE_B_FIRST + i, 11) for i in range(5)],
        "table_b_level": [int(cell(TABLE_B_FIRST + i, 14)) for i in range(5)],
        "table_b_status": [cell(TABLE_B_FIRST + i, 20) for i in range(5)],
        "table_b_overall": cell(OVERALL_ROW, 16),
    }


def compare(marks_path: Path = MARKS) -> dict:
    rules = load_rules()
    course = load_course(CONFIG_DIR / "courses" / "CET3011B.yaml", rules, load_program_outcomes())
    cos = [c.code for c in course.cos]
    internal = [t for t in course.tools if t.category != "END_TERM"]
    end_max = next(t.max_marks for t in course.tools if t.category == "END_TERM")
    args = (
        {t.name: t.max_marks for t in internal},
        tool_weights(course.allocation()),
        end_max,
        rules.split.internal,
        rules.split.end_term,
    )
    data = load_marks(marks_path, course)
    scores, flagged = score_students(data.students, *args)
    # diagnostic only, not the policy: the flagged students scored with blank marks as 0
    zeroed = {s: ({t: 0 if v is None else v for t, v in m.items()}, 0 if e is None else e)
              for s, (m, e) in data.students.items()}
    scores_blank0, _ = score_students(zeroed, *args)

    wb = read_workbook()
    wbs = wb["students"]
    missing = set(data.students) - set(wbs)
    end_term_mismatch = sum(
        1 for s, (_, e) in data.students.items() if s in wbs and e is not None and abs(e - wbs[s]["end_term"]) > 1e-9
    )

    def diffs(j, kind, ids):
        key = "internal" if kind == "internal" else "total"
        return [abs(getattr(scores_blank0[s][cos[j]], key) - wbs[s][key][j]) for s in ids]

    def stats(ids):
        out = []
        for j, co in enumerate(cos):
            row = {"co": co}
            for kind in ("internal", "total"):
                d = diffs(j, kind, ids)
                row[kind] = (max(d), sum(1 for x in d if x > TOL))
            out.append(row)
        return out

    def level_info(sc):
        res = {
            co: class_co_result(
                [s[co].total for s in sc.values()], course.co_targets[co], rules.level_scale.levels,
                rules.level_scale.floor_pct, rules.total_attainment.direct_weight,
                rules.total_attainment.indirect_weight, rules.total_attainment.indirect_enabled,
            )
            for co in cos
        }
        return {
            "average": [res[c].direct_pct for c in cos],
            "level": [res[c].final_level for c in cos],
            "status": [res[c].status for c in cos],
            "overall": overall_co_attainment(res),
        }

    return {
        "cos": cos,
        "targets": [course.co_targets[c] for c in cos],
        "loaded": len(data.students),
        "scored": len(scores),
        "flagged": len(flagged),
        "not_in_workbook": len(missing),
        "end_term_mismatch": end_term_mismatch,
        "scored_stats": stats(list(scores)),
        "flagged_vs_workbook": stats(list(flagged)),
        "student1": {
            "ours_internal": [scores["1"][c].internal for c in cos],
            "workbook_internal": wbs["1"]["internal"],
        },
        "policy": level_info(scores),
        "blank0": level_info(scores_blank0),
        "workbook_column_mean": [sum(w["total"][j] for w in wbs.values()) / len(wbs) for j in range(5)],
        "workbook": {k: wb[k] for k in ("typed_average", "table_b_direct", "table_b_level",
                                         "table_b_status", "table_b_overall")},
        "scores": scores,  # for the tests; not written to the report
        "workbook_students": wbs,
    }


def _f(xs, nd=2):
    return " | ".join(f"{x:.{nd}f}" if isinstance(x, float) else str(x) for x in xs)


def write_report(r: dict, path: Path = REPORT) -> None:
    cos = r["cos"]
    head = "| | " + " | ".join(cos) + " |\n|---|" + "---|" * len(cos) + "\n"
    rows = lambda label, xs: f"| {label} | {_f(xs)} |\n"
    s = r["scored_stats"]
    f0 = r["flagged_vs_workbook"]
    cell = lambda st, k: [f"{x[k][0]:.2f} max, {x[k][1]} over {TOL}" for x in st]
    w, p, b = r["workbook"], r["policy"], r["blank0"]
    by = {x["co"]: x["total"][1] for x in s}
    fb = {x["co"]: x["total"][1] for x in f0}
    all_over = {co: by[co] + fb[co] for co in cos}
    blank_note = (
        "- CO1, CO3 and CO5 also match for them, so the workbook treats a blank assignment mark as 0.\n"
        if all(fb[co] == 0 for co in ("CO1", "CO3", "CO5")) else ""
    ) + (
        f"- Over all {r['loaded']} students (blanks as 0), {all_over['CO2']} differ for CO2 and "
        f"{all_over['CO4']} for CO4 (docs section 8: 270 and 290).\n"
    )
    text = f"""# Discrepancy report: sample course CET3011B

Generated by `py tests/golden/compare.py`. Aggregates only: no student names or identifiers.
Compares the formulas of docs/PROJECT.md section 8 (recomputed from the marks file) with the original
workbook, tolerance {TOL}. Open items refer to section 13.

## Scope

- Students in the marks file: {r["loaded"]}; scored: {r["scored"]}; flagged for a blank mark and left out: {r["flagged"]} (a blank assignment mark).
- Marks-file students not found in the workbook: {r["not_in_workbook"]}; end-term marks that differ from the workbook's: {r["end_term_mismatch"]}.

## Student values, recomputed against the workbook

Largest absolute difference and number of scored students ({r["scored"]}) differing by more than {TOL}.

{head}{rows("Internal score (steps 1 and 2)", cell(s, "internal"))}{rows("CO attainment (step 3)", cell(s, "total"))}
CO1, CO3 and CO5 match for every scored student. CO2 and CO4 do not: the workbook applies smaller
effective weights than its own Tab 2 (open items O2 and O12). The stated Tab 2 weights are used.

Student serial 1, internal score per CO: workbook {_f(r["student1"]["workbook_internal"])} against formula {_f(r["student1"]["ours_internal"])}.

The {r["flagged"]} flagged students are not scored. Scored with blank marks as 0 (a diagnostic, not the rule) they compare with the workbook like this:

{head}{rows("CO attainment (step 3)", cell(f0, "total"))}
{blank_note}
## Class results

{head}{rows("Target (%)", r["targets"])}{rows(f"Formula average, {r['scored']} students", p["average"])}{rows(f"Formula average, blanks as 0, {r['loaded']} students (diagnostic)", b["average"])}{rows("Workbook Average row (typed)", w["typed_average"])}{rows("Mean of the workbook's own student column", r["workbook_column_mean"])}{rows("Workbook Table B, direct %", w["table_b_direct"])}
## Levels and status (O2, O12, O13)

{head}{rows("Workbook Table B level", w["table_b_level"])}{rows(f"Step 4 rule, {r['scored']} students", p["level"])}{rows("Step 4 rule, blanks as 0 (diagnostic)", b["level"])}
- Workbook Table B status: {_f(w["table_b_status"])}.
- Step 4 rule status, {r["scored"]} students: {_f(p["status"])}.
- Overall CO attainment (Table E): workbook {w["table_b_overall"]}, step 4 rule {p["overall"]:.2f} ({r["scored"]} students), {b["overall"]:.2f} (blanks as 0).
- Leaving out the {r["flagged"]} flagged students {"changes" if p["level"] != b["level"] else "does not change"} any CO level.

## Open items behind these differences

- O2 and O12: CO2 and CO4 student values and the typed Average row do not follow the stated weights; the workbook's Table B levels and the overall 2.84 cannot be reproduced.
- O13: the level rule of step 4 (3 at or above the target, 2 from 50 up to the target, 1 below 50) differs from the workbook's fixed 60/50/40 bands.
- O7: no absent marker; the {r["flagged"]} students with a blank mark are flagged, not scored as 0.
"""
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if not available():
        raise SystemExit("workbook or marks file missing")
    result = compare()
    write_report(result)
    print(f"wrote {REPORT.name}: {result['loaded']} loaded, {result['scored']} scored, {result['flagged']} flagged")
