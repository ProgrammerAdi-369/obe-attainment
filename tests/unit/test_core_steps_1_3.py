"""Core steps 1 to 3, checked against the worked example in docs/PROJECT.md section 8."""

import copy

import pytest

from obe.config import CONFIG_DIR, load_course, load_program_outcomes, load_rules
from obe.core.attainment import co_scores, internal_scores
from obe.core.weights import marks_per_co, tool_weights

COS = ["CO1", "CO2", "CO3", "CO4", "CO5"]


@pytest.fixture(scope="module")
def setup():
    rules = load_rules()
    course = load_course(CONFIG_DIR / "courses" / "CET3011B.yaml", rules, load_program_outcomes())
    internal = [t for t in course.tools if t.category != "END_TERM"]
    end_term = next(t for t in course.tools if t.category == "END_TERM")
    return {
        "weights": tool_weights(course.allocation()),
        "max": {t.name: t.max_marks for t in internal},
        "end_max": end_term.max_marks,
        "split": (rules.split.internal, rules.split.end_term),
    }


def scores(setup, marks, end_term):
    return co_scores(
        marks, setup["max"], setup["weights"], end_term, setup["end_max"], *setup["split"]
    )


# docs section 8: assignment 3/5, PBL 3/10, mid-term 6/15, LCA 12/30, end-term 22/40
STUDENT_1 = {"Assignment": 3, "PBL": 3, "Mid-term": 6, "LCA": 12}


# ------------------------------------------------------------- step 1: weights


def test_weights_match_worked_example(setup):
    w = setup["weights"]
    assert w["Assignment"]["CO1"] == pytest.approx(17.142857, abs=1e-5)
    assert w["Mid-term"]["CO1"] == pytest.approx(40)
    assert w["LCA"]["CO1"] == pytest.approx(42.857143, abs=1e-5)
    assert w["Assignment"]["CO2"] == pytest.approx(11.428571, abs=1e-5)
    assert w["Mid-term"]["CO2"] == pytest.approx(45.714286, abs=1e-5)
    assert w["PBL"]["CO3"] == pytest.approx(25)
    assert w["LCA"]["CO3"] == pytest.approx(75)
    assert w["PBL"]["CO4"] == w["PBL"]["CO5"] == 100
    assert w["PBL"]["CO1"] == w["PBL"]["CO2"] == 0


def test_weights_add_up_to_100_per_co(setup):
    for co in COS:
        assert sum(row[co] for row in setup["weights"].values()) == pytest.approx(100)


def test_lca_is_split_one_over_n_per_assignment():
    # 8 assignments: 2 for CO1, 2 for CO2, 4 for CO3 -> 30 * n_j / N
    m = marks_per_co(COS, {}, {"LCA": 30}, [["CO1"]] * 2 + [["CO2"]] * 2 + [["CO3"]] * 4)
    assert m["LCA"] == {"CO1": 7.5, "CO2": 7.5, "CO3": 15, "CO4": 0, "CO5": 0}


def test_lab_with_several_cos_is_split_equally():  # OPEN: O11
    m = marks_per_co(["CO1", "CO2"], {}, {"LCA": 30}, [["CO1", "CO2"], ["CO2"]])
    assert m["LCA"] == {"CO1": 7.5, "CO2": 22.5}


def test_lca_without_labs_and_co_without_marks_are_rejected():
    with pytest.raises(ValueError, match="needs lab assignments"):
        marks_per_co(COS, {}, {"LCA": 30}, [])
    with pytest.raises(ValueError, match="CO2 has no marks"):
        tool_weights({"A": {"CO1": 5, "CO2": 0}})


# ------------------------------------------------- steps 2 and 3: student values


def test_student_1_matches_worked_example(setup):
    s = scores(setup, STUDENT_1, 22)
    assert s["CO1"].internal == pytest.approx(43.43, abs=0.005)
    assert s["CO1"].total == pytest.approx(48.06, abs=0.005)
    assert s["CO3"].internal == pytest.approx(37.5)
    assert s["CO3"].total == pytest.approx(44.5)
    assert s["CO1"].end_term == s["CO3"].end_term == pytest.approx(55)


def test_pbl_contributes_zero_to_co1_and_co2(setup):
    low = internal_scores({**STUDENT_1, "PBL": 0}, setup["max"], setup["weights"])
    high = internal_scores({**STUDENT_1, "PBL": 10}, setup["max"], setup["weights"])
    for co in ("CO1", "CO2"):
        assert high[co] == low[co]
    assert high["CO3"] > low["CO3"]


def test_end_term_is_times_2_5_and_equal_for_all_cos(setup):
    zero = {t: 0 for t in setup["max"]}
    s = scores(setup, zero, 40)
    assert all(v.end_term == 100 and v.internal == 0 and v.total == pytest.approx(40) for v in s.values())
    assert all(v.total == 0 for v in scores(setup, zero, 0).values())


def test_full_marks_give_100(setup):
    full = scores(setup, dict(setup["max"]), 40)
    assert all(v.total == pytest.approx(100) for v in full.values())


def test_inputs_are_not_modified(setup):
    marks = dict(STUDENT_1)
    weights = copy.deepcopy(setup["weights"])
    scores(setup, marks, 22)
    assert marks == STUDENT_1 and weights == setup["weights"]
