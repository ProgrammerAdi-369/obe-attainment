"""Compare the finished Excel report, cell by cell, with the original course workbook.

    py tests/golden/report_vs_workbook.py [report.xlsx]

Prints one line per table: how many cells were compared, how many agree, the largest difference.
Reads no student names from the workbook and prints none: counts and numbers only.
"""

import glob
import sys
from pathlib import Path
from typing import NamedTuple

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data/sample/CET3011B_report.xlsx"
WORKBOOK = next(iter(glob.glob(str(ROOT / "data/main file/*.xlsx"))), None)


class Row(NamedTuple):
    item: str
    compared: int
    agree: int
    max_diff: float
    tol: float
    note: str


def num(v):
    if v == "√":
        return 1.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def grid(ws, r1, r2, c1, c2):
    return [[ws.cell(r, c).value for c in range(c1, c2 + 1)] for r in range(r1, r2 + 1)]


def flat(rows):
    return [v for row in rows for v in row]


def compare(item, ours, theirs, tol, note="", as_number=True):
    pairs = [(a, b) for a, b in zip(flat(ours), flat(theirs), strict=True)]
    if as_number:
        pairs = [(0.0 if num(a) is None else num(a), 0.0 if num(b) is None else num(b)) for a, b in pairs]
        diffs = [abs(a - b) for a, b in pairs]
        agree = sum(1 for d in diffs if d <= tol)
        return Row(item, len(pairs), agree, max(diffs, default=0.0), tol, note)
    agree = sum(1 for a, b in pairs if str(a).strip() == str(b).strip())
    return Row(item, len(pairs), agree, 0.0 if agree == len(pairs) else float("nan"), tol, note)


def find(ws, prefix):
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if isinstance(v, str) and v.startswith(prefix):
            return r + 2  # first data row: title, header, data
    raise KeyError(prefix)


def compare_report(report=REPORT, workbook=WORKBOOK) -> list[Row]:
    rep = load_workbook(report, data_only=True)
    wb = load_workbook(workbook, data_only=True)
    t1, t2, t3 = wb.worksheets[0], wb.worksheets[1], wb.worksheets[2]
    out: list[Row] = []
    m = rep["CO-PO mapping"]

    # ---- Tab 1
    r = find(m, "Table 1:")
    out.append(compare("Table 1 ticks", grid(m, r, r + 4, 2, 16), grid(t1, 19, 23, 3, 17), 0,
                       "blank cells read as 0 (O4)"))
    r = find(m, "Table 2:")
    out.append(compare("Table 2 theory hours", grid(m, r, r + 4, 2, 2), grid(t1, 28, 32, 3, 3), 0))
    out.append(compare("Table 2 unit COs", grid(m, r, r + 4, 3, 3), grid(t1, 28, 32, 4, 4), 0, as_number=False))
    r = find(m, "Table 3:")
    out.append(compare("Table 3 assignment names", grid(m, r, r + 7, 2, 2), grid(t1, 37, 44, 3, 3), 0, as_number=False))
    out.append(compare("Table 3 unit and CO", [[*a, *b] for a, b in zip(grid(m, r, r + 7, 3, 3), grid(m, r, r + 7, 4, 4), strict=True)],
                       [[int(a), b] for a, b in zip(flat(grid(t1, 37, 44, 4, 4)), flat(grid(t1, 37, 44, 5, 5)), strict=True)], 0, as_number=False))
    r = find(m, "Table 4:")
    for label, col_r, col_w in (("theory", 2, 3), ("practical (lab)", 3, 4), ("total", 4, 5), ("share %", 5, 6)):
        out.append(compare(f"Table 4 {label} hours", grid(m, r, r + 4, col_r, col_r), grid(t1, 48, 52, col_w, col_w), 0.01,
                           "lab hours: working answer O5" if label.startswith("practical") else ""))
    strengths_wb = [[int(str(v).split("=")[1])] for v in flat(grid(t1, 48, 52, 7, 7))]
    out.append(compare("Table 4 mapping strength", grid(m, r, r + 4, 6, 6), strengths_wb, 0,
                       "workbook Table 4 shows 3,3,3,2,2; the Table 5 rule gives 2,2,3,1,1 (O3)"))
    r = find(m, "Table 6:")
    out.append(compare("Table 6 baseline mapping", grid(m, r, r + 4, 2, 16), grid(t1, 73, 77, 3, 17), 0,
                       "workbook Table 6 equals its Table 7, not ticks x strength (O3, O4)"))
    r = find(m, "Table 7:")
    out.append(compare("Table 7 final mapping", grid(m, r, r + 4, 2, 16), grid(t1, 81, 85, 3, 17), 0))
    ft = rep["Table F"]
    out.append(compare("Table F rows 1-5 (final mapping)", grid(ft, 4, 8, 2, 16), grid(t1, 81, 85, 3, 17), 0))

    # ---- Tab 2: percentage weights (assignment, PBL, mid-term, LCA) x CO1..CO5
    w = rep["Tool weights"]
    ours = [[w.cell(r, c).value for r in range(5, 9)] for c in range(2, 7)]  # per CO: 4 tools
    theirs = [[t2.cell(r, c).value for c in (2, 3, 4, 7)] for r in range(57, 62)]  # per CO: A, PBL, mid, LCA
    out.append(compare("Tool weights %", ours, theirs, 0.01, "workbook rounds to 2 decimals"))

    # ---- Tab 3
    wbs = {}
    for r_ in range(661, 952):
        row = [t3.cell(r_, c).value for c in (1, 3, 4, 5, 6, 7, 9, 13, 17, 21, 25, 29)]  # never the name column
        if isinstance(row[0], (int, float)):
            wbs[str(int(row[0]))] = row[1:]
    st = rep["Student steps"]
    ids, mine = [], []
    for r_ in range(4, st.max_row + 1):
        sid = st.cell(r_, 1).value
        if sid == "Average":  # the flagged students listed below are not scored
            break
        if sid in wbs:
            ids.append(sid)
            mine.append([st.cell(r_, c).value for c in range(2, 13)])
    theirs = [wbs[s] for s in ids]
    cos = ["CO1", "CO2", "CO3", "CO4", "CO5"]
    for j, co in enumerate(cos):
        note = "" if co in ("CO1", "CO3", "CO5") else "O2 and O12: workbook uses smaller effective weights"
        out.append(compare(f"Student {co} internal score ({len(ids)} students)", [[x[j]] for x in mine], [[x[j]] for x in theirs], 0.1, note))
        out.append(compare(f"Student {co} CO attainment", [[x[6 + j]] for x in mine], [[x[6 + j]] for x in theirs], 0.1, note))
    out.append(compare("Student end-term converted (100)", [[x[5]] for x in mine], [[x[5]] for x in theirs], 1e-9))

    # ---- Table A, B, E, F against the workbook's typed tables
    a, b = rep["Table A"], rep["Table B"]
    out.append(compare("Table A targets", grid(a, 4, 8, 2, 2), grid(t3, 995, 999, 3, 3), 0))
    out.append(compare("Table B direct %", grid(b, 4, 8, 2, 2), grid(t3, 995, 999, 11, 11), 0.1,
                       "workbook value is typed; formula averages differ (O2, O12); 3 blank-mark students left out"))
    out.append(compare("Table B level", grid(b, 4, 8, 3, 3), grid(t3, 995, 999, 14, 14), 0,
                       "O13: new target-based level rule; workbook used 60/50/40"))
    out.append(compare("Table B status", grid(b, 4, 8, 4, 4), [[str(v).strip().capitalize()] for v in flat(grid(t3, 995, 999, 20, 20))], 0,
                       "", as_number=False))
    out.append(compare("Table E overall", [[rep["Table E"]["B3"].value]], [[t3.cell(1000, 16).value]], 0.01,
                       "workbook 2.84 is not reproducible (O2); ours 2.80 from the 3,2,1 level rule"))
    out.append(compare("Table F target", grid(ft, 9, 9, 2, 16), grid(t3, 1009, 1009, 3, 17), 0.01,
                       "workbook row is typed; PO4, PSO1 and PSO2 differ (O4)"))
    out.append(compare("Table F actual", grid(ft, 10, 10, 2, 16), grid(t3, 1010, 1010, 3, 17), 0.01,
                       "follows from the overall CO attainment, 2.80 against 2.84"))
    return out


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPORT
    print(f"{'item':44} {'cells':>5} {'agree':>5} {'max diff':>9}  note")
    for r in compare_report(path):
        print(f"{r.item:44} {r.compared:5d} {r.agree:5d} {r.max_diff:9.3f}  {r.note}")


if __name__ == "__main__":
    main()
