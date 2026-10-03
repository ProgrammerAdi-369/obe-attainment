"""The finished report against the original workbook: what agrees, and what is a known difference."""

import re

import pytest
from compare import MARKS, available
from report_vs_workbook import compare_report

from obe.config import CONFIG_DIR, load_course, load_program_outcomes, load_rules
from obe.ingest.marks import load_marks
from obe.pipeline import calculate
from obe.reports.excel import write_master_workbook

pytestmark = pytest.mark.skipif(not available(), reason="workbook or marks file is not in git")


@pytest.fixture(scope="module")
def rows(tmp_path_factory):
    rules, pos = load_rules(), load_program_outcomes()
    course = load_course(CONFIG_DIR / "courses" / "CET3011B.yaml", rules, pos)
    path = tmp_path_factory.mktemp("cmp") / "report.xlsx"
    write_master_workbook(calculate(course, rules, pos, load_marks(MARKS, course)), path)
    return {re.sub(r" \(\d+ students\)", "", r.item): r for r in compare_report(path)}


FULL_AGREEMENT = [
    "Table 1 ticks", "Table 2 theory hours", "Table 2 unit COs", "Table 3 assignment names",
    "Table 3 unit and CO", "Table 4 theory hours", "Table 4 practical (lab) hours",
    "Table 4 total hours", "Table 4 share % hours", "Table 7 final mapping",
    "Table F rows 1-5 (final mapping)", "Tool weights %", "Table A targets",
    "Student CO1 internal score", "Student CO1 CO attainment",
    "Student CO3 internal score", "Student CO3 CO attainment",
    "Student CO5 internal score", "Student CO5 CO attainment", "Student end-term converted (100)",
]


@pytest.mark.parametrize("item", FULL_AGREEMENT)
def test_report_agrees_with_the_workbook(rows, item):
    r = rows[item]
    assert r.agree == r.compared, f"{item}: {r.compared - r.agree} of {r.compared} cells differ"


def test_known_differences_are_exactly_the_documented_ones(rows):
    assert (rows["Student CO2 CO attainment"].agree, rows["Student CO4 CO attainment"].agree) == (21, 1)  # O2, O12
    assert rows["Table 4 mapping strength"].agree == 1  # O3: 3,3,3,2,2 in the workbook, 2,2,3,1,1 by the rule
    assert rows["Table 6 baseline mapping"].agree == 32  # O3, O4
    assert rows["Table B direct %"].agree == 0 and rows["Table B level"].agree == 3  # O2, O12, O13
    assert rows["Table E overall"].agree == 0  # 2.80 against the workbook's 2.84
    assert rows["Table F target"].agree == 12  # PO4, PSO1, PSO2 typed differently (O4)
    assert rows["Student CO1 CO attainment"].compared == 288  # the 3 blank-mark students are left out
