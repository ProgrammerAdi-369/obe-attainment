"""Master Excel workbook (docs/PROJECT.md section 11), generated from a RunResult.

Values are written at full precision; rounding is only the cell number format. The class averages,
Table B, Table E and Table F carry Excel formulas so that faculty can trace them. Each formula is
written together with the value Python computed, so a viewer that does not recalculate still shows
the numbers. Student rows use the student id only, never the name.
"""

import time
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from obe.pipeline import RunResult

SHEETS = [
    "Summary", "CO-PO mapping", "Tool weights", "Student steps", "Table A", "Table B",
    "Table E", "Table F", "Student PO", "Config",
]
FIRST = 3  # first data row (0-based) on the sheets that have a title, a blank row and a header


def _na(v):
    return "" if v is None else v


def write_master_workbook(r: RunResult, path: Path, run_date: str | None = None) -> None:
    run_date = run_date or time.strftime("%Y-%m-%d")
    wb = xlsxwriter.Workbook(str(path))
    show_student_po = r.student_po is not None
    ws = {name: wb.add_worksheet(name) for name in SHEETS if name != "Student PO" or show_student_po}
    fmt = {
        "title": wb.add_format({"bold": True, "font_size": 14}),
        "h": wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1, "text_wrap": True, "valign": "top"}),
        "n": wb.add_format({"num_format": "0.00", "border": 1}),
        "i": wb.add_format({"num_format": "0", "border": 1}),
        "t": wb.add_format({"border": 1, "text_wrap": True, "valign": "top"}),
        "b": wb.add_format({"bold": True}),
        "bn": wb.add_format({"bold": True, "num_format": "0.00", "border": 1}),
        "note": wb.add_format({"italic": True, "font_color": "#555555"}),
        "input": wb.add_format({"border": 1, "bg_color": "#FFF2CC", "text_wrap": True}),
    }
    cos = [c.code for c in r.course.cos]
    po_codes = r.pos.codes
    lv, floor = r.rules.level_scale.levels, r.rules.level_scale.floor_pct

    def table(sheet, row, title, header, rows, formats=None):
        """Write a titled table; returns the next free row."""
        sheet.write(row, 0, title, fmt["b"])
        for c, h in enumerate(header):
            sheet.write(row + 1, c, h, fmt["h"])
        for i, vals in enumerate(rows):
            for c, v in enumerate(vals):
                f = (formats or {}).get(c) or (fmt["n"] if isinstance(v, float) else fmt["t"])
                sheet.write(row + 2 + i, c, _na(v), f)
        return row + 3 + len(rows)

    # ---- Student steps: the scored students, then the flagged ones, then the average formulas
    s = ws["Student steps"]
    s.write(0, 0, "Student steps: internal score, end-term and CO attainment per student", fmt["title"])
    head = ["student_id"] + [f"Internal {c}" for c in cos] + ["End-term (100)"] + [f"Attainment {c}" for c in cos]
    for c, h in enumerate(head):
        s.write(2, c, h, fmt["h"])
    for i, (sid, per_co) in enumerate(r.scores.items()):
        s.write(FIRST + i, 0, sid, fmt["t"])
        for j, co in enumerate(cos):
            s.write_number(FIRST + i, 1 + j, per_co[co].internal, fmt["n"])
            s.write_number(FIRST + i, 7 + j, per_co[co].total, fmt["n"])
        s.write_number(FIRST + i, 6, per_co[cos[0]].end_term, fmt["n"])
    last = FIRST + len(r.scores) - 1
    avg_row = last + 2
    s.write(avg_row, 0, "Average", fmt["b"])
    for j, co in enumerate(cos):
        for col, key in ((1 + j, "internal"), (7 + j, "total")):
            name = xl_col_to_name(col)
            value = sum(getattr(sc[co], key) for sc in r.scores.values()) / len(r.scores)
            s.write_formula(avg_row, col, f"=AVERAGE({name}{FIRST + 1}:{name}{last + 1})", fmt["bn"], value)
    if r.flagged:
        s.write(avg_row + 2, 0, f"Not scored: {len(r.flagged)} students with a blank mark (left out of every average)", fmt["b"])
        s.write(avg_row + 3, 0, "student_id", fmt["h"])
        s.write(avg_row + 3, 1, "Missing marks", fmt["h"])
        for i, (sid, missing) in enumerate(r.flagged.items()):
            s.write(avg_row + 4 + i, 0, sid, fmt["t"])
            s.write(avg_row + 4 + i, 1, ", ".join(missing), fmt["t"])
    s.set_column(0, 0, 14)
    s.set_column(1, 11, 13)
    s.freeze_panes(3, 1)

    # ---- Table A: targets, level scale, floor
    a = ws["Table A"]
    a.write(0, 0, "Table A: CO target attainment and level scale", fmt["title"])
    a.write(2, 0, "Course Outcome", fmt["h"])
    a.write(2, 1, "Target attainment (%) (Form 8)", fmt["h"])
    for i, co in enumerate(cos):
        a.write(FIRST + i, 0, co, fmt["t"])
        a.write_number(FIRST + i, 1, r.course.co_targets[co], fmt["n"])
    floor_row = FIRST + len(cos) + 1
    a.write(floor_row, 0, "Level floor (%)", fmt["h"])
    a.write_number(floor_row, 1, floor, fmt["n"])
    a.write(floor_row + 2, 0, f"Level {lv[0]} (High): direct % at or above the CO target", fmt["t"])
    a.write(floor_row + 3, 0, f"Level {lv[1]} (Medium): from the floor up to the CO target", fmt["t"])
    a.write(floor_row + 4, 0, f"Level {lv[2]} (Low): below the floor", fmt["t"])
    a.write(floor_row + 6, 0, "Targets are teacher input; the level scale is fixed in rules.yaml (open item O13).", fmt["note"])
    a.set_column(0, 0, 55)
    a.set_column(1, 1, 22)

    # ---- Table B: direct %, level, status, reason and action plan for teachers
    b = ws["Table B"]
    b.write(0, 0, "Table B: CO attainment (direct) and gap analysis", fmt["title"])
    for c, h in enumerate(["Course Outcome", "% Direct attainment", "CO attainment level", "Status of attainment",
                           "Reason for gap", "Action plan"]):
        b.write(2, c, h, fmt["h"])
    for i, co in enumerate(cos):
        row, x = FIRST + i, r.classes[co]
        d = f"B{row + 1}"
        target, flr = f"'Table A'!$B${row + 1}", f"'Table A'!$B${floor_row + 1}"
        b.write(row, 0, co, fmt["t"])
        col = xl_col_to_name(7 + i)
        b.write_formula(row, 1, f"='Student steps'!{col}{avg_row + 1}", fmt["n"], x.direct_pct)
        b.write_formula(row, 2, f"=IF({d}>={target},{lv[0]},IF({d}>={flr},{lv[1]},{lv[2]}))", fmt["i"], x.final_level)
        b.write_formula(row, 3, f'=IF({d}>={target},"Attained","Not attained")', fmt["t"], x.status)
        b.write_blank(row, 4, None, fmt["input"])
        b.write_blank(row, 5, None, fmt["input"])
    b.write(FIRST + len(cos) + 1, 0, "Indirect % and total actual % are added when the end-course survey is switched on (open item O10).", fmt["note"])
    b.set_column(0, 3, 22)
    b.set_column(4, 5, 40)

    # ---- Table E
    e = ws["Table E"]
    e.write(0, 0, "Table E: overall CO attainment of the course", fmt["title"])
    e.write(2, 0, "Average of the CO levels", fmt["h"])
    e.write_formula(2, 1, f"=AVERAGE('Table B'!C{FIRST + 1}:C{FIRST + len(cos)})", fmt["bn"], r.overall)
    e.set_column(0, 0, 34)

    # ---- Table F
    f = ws["Table F"]
    f.write(0, 0, "Table F: PO and PSO target, actual and gap", fmt["title"])
    for c, h in enumerate(["CO"] + po_codes):
        f.write(2, c, h, fmt["h"])
    for i, co in enumerate(cos):
        f.write(FIRST + i, 0, co, fmt["t"])
        for c, p in enumerate(po_codes):
            f.write_number(FIRST + i, 1 + c, r.course.co_po_final[co][p], fmt["i"])
    t_row = FIRST + len(cos)
    for k, label in enumerate(["Target", "Actual", "Gap (target - actual)"]):
        f.write(t_row + k, 0, label, fmt["h"])
    for c, p in enumerate(po_codes):
        col = xl_col_to_name(1 + c)
        res = r.po[p]
        rng = f"{col}{FIRST + 1}:{col}{FIRST + len(cos)}"
        tgt, act = f"{col}{t_row + 1}", f"{col}{t_row + 2}"
        f.write_formula(t_row, 1 + c, f'=IFERROR(AVERAGEIF({rng},">0"),"")', fmt["n"], _na(res.target))
        f.write_formula(t_row + 1, 1 + c, f'=IF({tgt}="","",{tgt}*\'Table E\'!$B$3/{lv[0]})', fmt["n"], _na(res.actual))
        f.write_formula(t_row + 2, 1 + c, f'=IF({tgt}="","",{tgt}-{act})', fmt["n"], _na(res.gap))
    f.write(t_row + 4, 0, "Rows 1 to 5 are the final CO-PO mapping (Table 7). Target is the mean of the non-zero strengths; "
            "actual is target x overall CO attainment / 3; blank means no CO maps to that outcome.", fmt["note"])
    f.set_column(0, 0, 24)
    f.set_column(1, len(po_codes), 8)

    # ---- Tool weights: percentages only
    w = ws["Tool weights"]
    w.write(0, 0, "Tool weights: percentage weight of each tool in each CO", fmt["title"])
    nxt = table(w, 2, "", ["Tool"] + cos, [[t] + [r.weights[t][co] for co in cos] for t in r.weights])
    w.write(nxt - 1, 0, "Total", fmt["h"])
    for j, co in enumerate(cos):
        w.write_number(nxt - 1, 1 + j, sum(r.weights[t][co] for t in r.weights), fmt["bn"])
    w.write(nxt + 1, 0, "The LCA split is generated from the lab assignments (1/N each). The end-term is not here: it counts "
            "equally for every CO.", fmt["note"])
    w.set_column(0, 0, 18)

    # ---- CO-PO mapping: Tables 1 to 7
    m = ws["CO-PO mapping"]
    m.write(0, 0, "CO-PO mapping and instruction hours: Tables 1 to 7", fmt["title"])
    row = table(m, 2, "Table 1: CO-PO/PSO ticks", ["CO"] + po_codes,
                [[co] + ["√" if r.course.co_po_ticks[co][p] else 0 for p in po_codes] for co in cos])
    row = table(m, row, "Table 2: theory hours per unit and CO", ["Unit", "Theory hours", "COs"],
                [[u.unit_no, float(u.theory_hours), ", ".join(u.co_codes)] for u in r.course.units])
    row = table(m, row, "Table 3: lab assignments (lab hours are the working answer for open item O5)",
                ["No", "Assignment", "Unit", "COs", "Lab hours"],
                [[x.assignment_no, x.name, x.unit_no, ", ".join(x.co_codes), float(x.lab_hours)] for x in r.course.labs])
    row = table(m, row, "Table 4: hours per CO", ["CO", "Theory hours", "Lab hours", "Total hours", "Share of hours (%)", "Baseline strength"],
                [[co, float(h.theory), float(h.lab), float(h.theory + h.lab), h.share_pct, h.strength] for co, h in r.hours.items()],
                {5: fmt["i"]})
    bands = [f"{'More than' if not b.inclusive else 'At least'} {b.min_pct:g}% of the hours: strength {b.strength}"
             for b in r.rules.hours_to_strength]
    row = table(m, row, "Table 5: hours-to-strength rule (fixed, rules.yaml)", ["Rule"], [[x] for x in bands])
    row = table(m, row, "Table 6: baseline mapping (ticks x baseline strength, for information)", ["CO"] + po_codes,
                [[co] + [float(r.baseline[co][p]) for p in po_codes] for co in cos])
    row = table(m, row, "Table 7: final mapping set by the teachers (the only mapping used in the calculation)",
                ["CO"] + po_codes, [[co] + [float(r.course.co_po_final[co][p]) for p in po_codes] for co in cos])
    m.set_column(0, 0, 14)
    m.set_column(1, len(po_codes), 9)
    m.set_column(1, 1, 16)

    # ---- Student PO (only while the O9 flag is on)
    if show_student_po:
        sp = ws["Student PO"]
        sp.write(0, 0, "Student PO: PO and PSO attainment per student for this course (open item O9, unconfirmed)", fmt["title"])
        for c, h in enumerate(["student_id"] + po_codes):
            sp.write(2, c, h, fmt["h"])
        for i, (sid, vals) in enumerate(r.student_po.items()):
            sp.write(FIRST + i, 0, sid, fmt["t"])
            for c, p in enumerate(po_codes):
                sp.write(FIRST + i, 1 + c, _na(vals[p]), fmt["n"])
        sp.freeze_panes(3, 1)

    # ---- Summary
    sm = ws["Summary"]
    c = r.course.course
    sm.write(0, 0, f"{c.code} {c.name}: attainment summary", fmt["title"])
    info = [("Program", c.program), ("Class", c.class_), ("Semester", c.semester), ("Academic year", c.academic_year),
            ("Batch", c.batch), ("Run date", run_date),
            ("Students in the marks file", len(r.scores) + len(r.flagged)), ("Scored", len(r.scores)),
            ("Flagged (blank mark, left out)", len(r.flagged))]
    for i, (k, v) in enumerate(info):
        sm.write(2 + i, 0, k, fmt["h"])
        sm.write(2 + i, 1, v, fmt["t"])
    row = table(sm, 3 + len(info), "CO attainment against target (direct only)",
                ["CO", "Target (%)", "Direct (%)", "Level", "Status"],
                [[co, float(r.course.co_targets[co]), r.classes[co].direct_pct, r.classes[co].final_level,
                  r.classes[co].status] for co in cos], {3: fmt["i"]})
    sm.write(row - 1, 0, "Overall CO attainment (Table E)", fmt["h"])
    sm.write_number(row - 1, 1, r.overall, fmt["bn"])
    row = table(sm, row + 1, "PO and PSO target against actual (positive gap needs an action plan)",
                ["PO / PSO", "Target", "Actual", "Gap"],
                [[p, r.po[p].target, r.po[p].actual, r.po[p].gap] for p in po_codes if r.po[p].target is not None])
    notes = [
        "Results use the working answers of docs/PROJECT.md section 13 until the faculty decide:",
        f"- O13: level {lv[0]} at or above the CO target, {lv[1]} from {floor:g} up to the target, {lv[2]} below {floor:g}.",
        "- O2 and O12: the stated Tab 2 tool weights are used; the workbook's CO2 and CO4 student values differ (see the discrepancy report).",
        "- O10: direct attainment only; the indirect (survey) part is switched off.",
        "- O14: the end-term counts equally for every CO.",
        "- O5: lab hours are the working answer; they affect Table 4 only.",
        "- O4: only the final mapping (Table 7) feeds Table F.",
        f"- Students with a blank mark are flagged and left out of every average ({len(r.flagged)} here).",
        "- Tables C and D are added after their content is confirmed (O1). Per-student PO attainment is off until O9 is confirmed.",
    ]
    for i, n in enumerate(notes):
        sm.write(row + i, 0, n, fmt["note"] if i else fmt["b"])
    sm.set_column(0, 0, 36)
    sm.set_column(1, 4, 16)

    # ---- Config: the rules, targets, tools and weights this run used
    cf = ws["Config"]
    cf.write(0, 0, "Config: rules, thresholds, targets and weights used by this run", fmt["title"])
    ru, ta = r.rules, r.rules.total_attainment
    rules_rows = [
        ["Internal share of the CO attainment", ru.split.internal], ["End-term share", ru.split.end_term],
        ["End-term maximum (marks)", ru.end_term_max], ["Internal tool maximums add up to", ru.internal_total_max],
        ["Direct weight in the total", ta.direct_weight], ["Indirect weight in the total", ta.indirect_weight],
        ["Indirect (survey) switched on", str(ta.indirect_enabled)],
        ["Level scale", ", ".join(str(x) for x in lv)], ["Level floor (%)", floor],
        ["Multi-CO units and labs", ru.multi_co_split], ["Absent marks scored as", ru.absent_marks],
        ["Per-student PO attainment (O9)", str(ru.student_po_enabled)],
    ]
    row = table(cf, 2, "Rules (config/rules.yaml)", ["Rule", "Value"], [[k, float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v] for k, v in rules_rows])
    row = table(cf, row, "CO targets (%)", ["CO", "Target"], [[co, float(r.course.co_targets[co])] for co in cos])
    row = table(cf, row, "Assessment tools and weights (%)", ["Tool", "Category", "Maximum"] + cos,
                [[t.name, t.category, float(t.max_marks)] + ([r.weights[t.name][co] for co in cos] if t.name in r.weights else [""] * len(cos))
                 for t in r.course.tools])
    row = table(cf, row, "Hours-to-strength bands", ["Strength", "From (%)", "Inclusive"],
                [[b.strength, float(b.min_pct), str(b.inclusive)] for b in ru.hours_to_strength])
    cf.set_column(0, 0, 40)
    cf.set_column(1, 8, 14)

    wb.close()
