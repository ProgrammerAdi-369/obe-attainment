"""Marks ingest: row-level errors load nothing; blanks are flagged by the core, not rejected."""

import csv

import pytest
from openpyxl import Workbook

from obe.config import CONFIG_DIR, load_course, load_program_outcomes, load_rules
from obe.core.attainment import score_students
from obe.core.weights import tool_weights
from obe.ingest.marks import MarksFileError, load_marks, parse_marks

HEADER = ["student_id", "student_name", "Assignment", "PBL", "Mid-term", "LCA", "End-term"]
SAMPLE_FILE = CONFIG_DIR.parent / "data" / "sample" / "CET3011B_marks.xlsx"


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture(scope="module")
def course(rules):
    return load_course(CONFIG_DIR / "courses" / "CET3011B.yaml", rules, load_program_outcomes())


def errors_of(table, course):
    with pytest.raises(MarksFileError) as e:
        parse_marks(table, course)
    return e.value.errors


# ------------------------------------------------------------------ good files


def test_valid_rows_load(course):
    t = [HEADER, [1, "A", 3, 3, 6, 12, 22], [2, "B", 0, 10, 15, 30, 40]]
    data = parse_marks(t, course)
    assert data.students["1"] == ({"Assignment": 3, "PBL": 3, "Mid-term": 6, "LCA": 12}, 22)
    assert data.students["2"][1] == 40 and data.names == {"1": "A", "2": "B"}


def test_real_zero_and_both_ends_of_the_range_are_valid(course):
    parse_marks([HEADER, [1, "A", 0, 0, 0, 0, 0], [2, "B", 5, 10, 15, 30, 40]], course)


def test_empty_rows_short_rows_and_text_ids_are_handled(course):
    t = [HEADER, ["R-1", None, 3, 3, 6, 12, 22], [None] * 7, [2.0, "B", 1, 1, 1, 1]]
    data = parse_marks(t, course)
    assert set(data.students) == {"R-1", "2"}
    assert data.students["2"][1] is None  # short row: the missing end-term is a blank


def test_blank_marks_load_and_are_flagged_by_the_core(course, rules):
    t = [HEADER, [1, "A", None, 3, 6, 12, 22], [2, "B", 3, 3, 6, 12, None], [3, "C", 3, 3, 6, 12, 22]]
    data = parse_marks(t, course)
    internal = [x for x in course.tools if x.category != "END_TERM"]
    scores, flagged = score_students(
        data.students,
        {x.name: x.max_marks for x in internal},
        tool_weights(course.allocation()),
        40,
        rules.split.internal,
        rules.split.end_term,
    )
    assert set(scores) == {"3"}
    assert flagged == {"1": ["Assignment"], "2": ["end_term"]}


# ----------------------------------------------------- bad files, one per error


def test_mark_above_maximum(course):
    e = errors_of([HEADER, [1, "A", 6, 3, 6, 12, 22]], course)
    assert e == [(2, "Assignment", "mark is outside 0 to 5")]


def test_negative_mark(course):
    assert errors_of([HEADER, [1, "A", -1, 3, 6, 12, 22]], course)[0].column == "Assignment"


def test_end_term_above_maximum(course):
    assert errors_of([HEADER, [1, "A", 3, 3, 6, 12, 41]], course)[0].column == "End-term"


def test_non_numeric_mark(course):
    e = errors_of([HEADER, [1, "A", "AB", 3, 6, 12, 22]], course)
    assert e == [(2, "Assignment", "mark is not a number")]


def test_duplicate_student_id(course):
    t = [HEADER, [1, "A", 3, 3, 6, 12, 22], [2, "B", 3, 3, 6, 12, 22], [1, "C", 3, 3, 6, 12, 22]]
    e = errors_of(t, course)
    assert e == [(4, "student_id", "duplicate student id (first seen in row 2)")]


def test_blank_student_id(course):
    assert errors_of([HEADER, [None, "A", 3, 3, 6, 12, 22]], course)[0].message == "student id is blank"


def test_unknown_column(course):
    e = errors_of([HEADER + ["MCQ"], [1, "A", 3, 3, 6, 12, 22, 0]], course)
    assert e == [(1, "MCQ", "unknown column")]


def test_missing_column(course):
    e = errors_of([[h for h in HEADER if h != "LCA"], [1, "A", 3, 3, 6, 22]], course)
    assert e == [(1, "LCA", "missing column")]


def test_duplicate_column(course):
    assert (1, "PBL", "duplicate column") in errors_of([HEADER + ["PBL"], [1, "A", 3, 3, 6, 12, 22, 3]], course)


def test_all_errors_are_reported_and_nothing_loads(course):
    t = [HEADER, [1, "A", 9, 3, 6, 12, 22], [2, "B", 3, 99, 6, 12, 22], [3, "C", 3, 3, 6, 12, 22]]
    assert [(e.row, e.column) for e in errors_of(t, course)] == [(2, "Assignment"), (3, "PBL")]


def test_error_report_never_contains_ids_or_names(course):
    with pytest.raises(MarksFileError) as e:
        parse_marks([HEADER, ["SECRET-ID", "Secret Name", 9, 3, 6, 12, 22]], course)
    assert "SECRET" not in str(e.value) and "Secret" not in str(e.value)


# ------------------------------------------------------------------ file types


def test_reads_xlsx_and_csv(course, tmp_path):
    rows = [HEADER, [1, "A", 3, 3, 6, 12, 22], [2, "B", 3, 3, 6, 12, None]]
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(tmp_path / "m.xlsx")
    with open(tmp_path / "m.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    for name in ("m.xlsx", "m.csv"):
        data = load_marks(tmp_path / name, course)
        assert data.students["1"][1] == 22 and data.students["2"][1] is None


# --------------------------------------------------------------- the sample file


@pytest.mark.skipif(not SAMPLE_FILE.exists(), reason="sample marks file is not in git")
def test_sample_marks_file_loads_291_students(course, rules):
    data = load_marks(SAMPLE_FILE, course)
    assert len(data.students) == 291
    internal = [x for x in course.tools if x.category != "END_TERM"]
    scores, flagged = score_students(
        data.students,
        {x.name: x.max_marks for x in internal},
        tool_weights(course.allocation()),
        40,
        rules.split.internal,
        rules.split.end_term,
    )
    assert (len(scores), len(flagged)) == (288, 3)  # three blank assignment marks
    assert all(v == ["Assignment"] for v in flagged.values())
