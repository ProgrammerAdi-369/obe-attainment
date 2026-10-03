"""Golden test: the sample course recomputed from the marks file against the original workbook."""

import pytest
from compare import TOL, available, compare

pytestmark = pytest.mark.skipif(not available(), reason="workbook or marks file is not in git")


@pytest.fixture(scope="module")
def result():
    return compare()


def test_all_students_load_and_line_up_with_the_workbook(result):
    assert result["loaded"] == 291
    assert (result["scored"], result["flagged"]) == (288, 3)  # three blank assignment marks
    assert result["not_in_workbook"] == 0
    assert result["end_term_mismatch"] == 0


@pytest.mark.parametrize("co", ["CO1", "CO3", "CO5"])
def test_co1_co3_co5_match_the_workbook_for_every_scored_student(result, co):
    row = next(x for x in result["scored_stats"] if x["co"] == co)
    assert row["total"][1] == 0, f"{co}: {row['total'][1]} students differ by more than {TOL}"
    assert row["total"][0] <= TOL
    assert row["internal"][1] == 0


def test_co2_and_co4_differences_are_reported_not_hidden(result):
    # open items O2 and O12: the workbook applies smaller effective weights than its Tab 2
    by_co = {x["co"]: x for x in result["scored_stats"]}
    assert by_co["CO2"]["total"][1] > 0 and by_co["CO4"]["total"][1] > 0
    s1 = result["student1"]
    assert s1["ours_internal"][3] == pytest.approx(30)
    assert s1["workbook_internal"][3] == pytest.approx(22.5)


def test_worked_example_student_1_matches_the_workbook(result):
    s = result["scores"]["1"]
    wb = result["workbook_students"]["1"]
    assert s["CO3"].total == pytest.approx(wb["total"][2], abs=TOL) == pytest.approx(44.5, abs=TOL)
    assert s["CO1"].total == pytest.approx(48.06, abs=0.005)
    assert wb["total"][0] == pytest.approx(48.04, abs=0.005)  # the workbook rounds the weights


def test_levels_and_overall_follow_step_4_rule(result):
    assert result["workbook"]["table_b_level"] == [3, 3, 3, 2, 3]  # the workbook's own Table B
    assert result["policy"]["overall"] == pytest.approx(2.8, abs=0.1)
    assert result["policy"]["level"] == [2, 3, 3, 3, 3]
