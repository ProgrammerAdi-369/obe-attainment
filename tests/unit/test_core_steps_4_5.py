"""Core steps 4 and 5: class average, level, status, 80/20 total, Table E; missing marks flagged."""

import pytest

from obe.config import CONFIG_DIR, load_course, load_program_outcomes, load_rules
from obe.core.attainment import (
    class_co_result,
    co_level,
    overall_co_attainment,
    score_students,
    total_attainment,
)
from obe.core.weights import tool_weights

LEVELS, FLOOR = [3, 2, 1], 50


def level(pct, target):
    return co_level(pct, target, LEVELS, FLOOR)


# ------------------------------------------------------------------ level rule


def test_level_boundaries_for_target_60():
    assert level(59.99, 60) == 2
    assert level(60, 60) == 3
    assert level(49.99, 60) == 1
    assert level(50, 60) == 2


def test_level_boundaries_for_target_50():
    assert level(50, 50) == 3
    assert level(49.99, 50) == 1  # the middle level does not occur when target is at the floor


def test_level_scale_and_floor_come_from_the_arguments():
    assert co_level(45, 60, [3, 2, 1], 40) == 2
    assert co_level(45, 60, [3, 2, 1], 50) == 1


# --------------------------------------------------------------- total, status


def test_total_equals_direct_when_indirect_is_off():
    assert total_attainment(57.3, 100, 0.8, 0.2, False) == 57.3
    assert total_attainment(57.3, None, 0.8, 0.2, False) == 57.3


def test_total_is_80_20_when_indirect_is_on():
    assert total_attainment(50, 100, 0.8, 0.2, True) == pytest.approx(60)
    with pytest.raises(ValueError, match="no survey value"):
        total_attainment(50, None, 0.8, 0.2, True)


def test_indirect_level_is_not_built_until_faculty_explain_it():  # OPEN: O10
    with pytest.raises(NotImplementedError):
        class_co_result([50], 50, LEVELS, FLOOR, 0.8, 0.2, True, 80)


def class_co(values, target):
    return class_co_result(values, target, LEVELS, FLOOR, 0.8, 0.2, False)


def test_class_result_is_average_level_and_status():
    r = class_co([40, 60, 80], 60)  # average 60 reaches the target exactly
    assert (r.direct_pct, r.direct_level, r.total_pct, r.final_level) == (60, 3, 60, 3)
    assert r.status == "Attained"
    r = class_co([58, 60], 60)
    assert (r.direct_level, r.status) == (2, "Not attained")
    r = class_co([10, 20], 60)
    assert (r.direct_level, r.status) == (1, "Not attained")


def test_empty_class_is_rejected():
    with pytest.raises(ValueError, match="no student values"):
        class_co([], 60)


# ------------------------------------------------------------------- Table E


def test_overall_attainment_for_the_sample_averages():
    # docs section 8: formula-based averages 58.65, 57.15, 55.69, 55.16, 55.16 with targets
    # 60, 50, 55, 50, 50 give levels 2, 3, 3, 3, 3 and an overall attainment of 2.8
    averages = [58.65, 57.15, 55.69, 55.16, 55.16]
    targets = [60, 50, 55, 50, 50]
    res = {f"CO{i + 1}": class_co([a], t) for i, (a, t) in enumerate(zip(averages, targets))}
    assert [r.final_level for r in res.values()] == [2, 3, 3, 3, 3]
    assert [r.status for r in res.values()] == ["Not attained"] + ["Attained"] * 4
    assert overall_co_attainment(res) == pytest.approx(2.8)


# --------------------------------------------------------------- missing marks


@pytest.fixture(scope="module")
def setup():
    rules = load_rules()
    course = load_course(CONFIG_DIR / "courses" / "CET3011B.yaml", rules, load_program_outcomes())
    return {
        "weights": tool_weights(course.allocation()),
        "max": {t.name: t.max_marks for t in course.tools if t.category != "END_TERM"},
        "split": (rules.split.internal, rules.split.end_term),
    }


FULL = {"Assignment": 3, "PBL": 3, "Mid-term": 6, "LCA": 12}


def test_students_with_missing_marks_are_flagged_and_left_out(setup):
    students = {
        "a": (dict(FULL), 22),
        "b": ({**FULL, "Assignment": None}, 22),  # blank cell
        "c": ({k: v for k, v in FULL.items() if k != "LCA"}, 22),  # column absent
        "d": (dict(FULL), None),  # no end-term
        "e": ({**FULL, "Assignment": 0}, 22),  # a real zero is a mark, not a missing one
    }
    scores, flagged = score_students(
        students, setup["max"], setup["weights"], 40, *setup["split"]
    )
    assert set(scores) == {"a", "e"}
    assert flagged == {"b": ["Assignment"], "c": ["LCA"], "d": ["end_term"]}
    assert scores["a"]["CO1"].total == pytest.approx(48.0571, abs=1e-4)
    # flagged students are not in the class average
    avg = class_co([s["CO1"].total for s in scores.values()], 60)
    assert avg.direct_pct == pytest.approx((scores["a"]["CO1"].total + scores["e"]["CO1"].total) / 2)
