"""Core steps 6 and 7: hours, baseline strength, PO and PSO target, actual, gap, student PO."""

import pytest

from obe.config import CONFIG_DIR, load_course, load_program_outcomes, load_rules
from obe.core.mapping import baseline_mapping, baseline_strength, hours_summary
from obe.core.po import average_over_courses, po_results, po_targets, student_po_attainment

LEVELS, FLOOR = [3, 2, 1], 50


@pytest.fixture(scope="module")
def sample():
    rules = load_rules()
    course = load_course(CONFIG_DIR / "courses" / "CET3011B.yaml", rules, load_program_outcomes())
    bands = [(b.strength, b.min_pct, b.inclusive) for b in rules.hours_to_strength]
    return {
        "course": course,
        "bands": bands,
        "hours": hours_summary(
            [c.code for c in course.cos],
            [(u.theory_hours, u.co_codes) for u in course.units],
            [(x.lab_hours, x.co_codes) for x in course.labs],
            bands,
        ),
    }


# ------------------------------------------------------------- hours, strength


def test_hours_per_co_for_the_sample(sample):
    h = sample["hours"]
    assert [h[c].theory for c in h] == [9] * 5
    assert [h[c].lab for c in h] == [6, 8, 16, 0, 0]  # practical hours 6, 8, 16 in Table 4
    assert [h[c].share_pct for c in h] == pytest.approx([20, 22.6667, 33.3333, 12, 12], abs=1e-3)
    assert sum(r.share_pct for r in h.values()) == pytest.approx(100)


def test_baseline_strengths_for_the_sample_are_2_2_3_1_1(sample):  # OPEN: O3
    assert [r.strength for r in sample["hours"].values()] == [2, 2, 3, 1, 1]


def test_strength_band_boundaries(sample):
    shares = (30.01, 30, 29.5, 16, 15.99, 5, 4.99, 0)
    assert tuple(baseline_strength(x, sample["bands"]) for x in shares) == (3, 2, 2, 2, 1, 1, 0, 0)


def test_unit_or_lab_with_several_cos_is_split_equally():  # OPEN: O11
    h = hours_summary(["CO1", "CO2"], [(10, ["CO1", "CO2"])], [(4, ["CO2"])], [(0, 0, True)])
    assert (h["CO1"].theory, h["CO2"].theory, h["CO2"].lab) == (5, 5, 4)


def test_no_hours_is_rejected():
    with pytest.raises(ValueError, match="no instruction hours"):
        hours_summary(["CO1"], [], [], [(0, 0, True)])


def test_baseline_mapping_is_ticks_times_strength(sample):
    c = sample["course"]
    strengths = {co: r.strength for co, r in sample["hours"].items()}
    m = baseline_mapping(c.co_po_ticks, strengths)
    assert m["CO1"]["PO1"] == 2 and m["CO3"]["PO5"] == 3 and m["CO4"]["PO1"] == 1
    assert m["CO1"]["PO4"] == 0 and m["CO1"]["PO9"] == 0  # no tick, no strength


# ------------------------------------------------------------ PO and PSO table


def test_po_targets_from_final_mapping(sample):
    t = po_targets(sample["course"].co_po_final)
    assert t["PO1"] == 3
    assert t["PO8"] == pytest.approx(2.6)  # strengths 3, 3, 3, 2, 2
    assert t["PO3"] == 3  # only the non-zero entries (0, 0, 3, 3, 3) enter the average
    assert t["PO9"] == pytest.approx(2.6) and t["PSO1"] == pytest.approx(2.6)
    assert t["PO4"] is None  # no CO maps to it


def test_po_actual_and_gap_follow_overall_attainment(sample):
    final = sample["course"].co_po_final
    r = po_results(final, 2.8, 3)  # direct-only overall 2.8 from step 4
    assert (r["PO1"].target, r["PO1"].actual) == (3, pytest.approx(2.8))
    assert r["PO1"].gap == pytest.approx(0.2)
    assert r["PO8"].actual == pytest.approx(2.6 * 2.8 / 3) == pytest.approx(2.4267, abs=1e-4)
    assert r["PO8"].gap == pytest.approx(2.6 - 2.6 * 2.8 / 3)
    assert po_results(final, 2.84, 3)["PO8"].actual == pytest.approx(2.4613, abs=1e-4)
    assert r["PO4"] == (None, None, None)


def test_full_attainment_closes_every_gap(sample):
    r = po_results(sample["course"].co_po_final, 3, 3)
    assert all(v.gap == pytest.approx(0) for v in r.values() if v.target is not None)


# ---------------------------------------------------------- per-student (O9)

TARGETS = {"CO1": 60, "CO2": 50, "CO3": 55, "CO4": 50, "CO5": 50}


def student(sample, totals, enabled=True):
    return student_po_attainment(
        sample["course"].co_po_final, totals, TARGETS, LEVELS, FLOOR, enabled
    )


def test_student_po_is_off_unless_the_flag_is_on(sample):
    assert student(sample, dict.fromkeys(TARGETS, 99), enabled=False) is None
    assert load_rules().student_po_enabled is False


def test_student_po_uses_the_students_own_levels(sample):
    top = student(sample, dict.fromkeys(TARGETS, 99))
    assert top["PO1"] == 3 and top["PO8"] == pytest.approx(2.6)  # all levels 3 -> overall 3
    mixed = student(sample, {**dict.fromkeys(TARGETS, 99), "CO1": 55})  # CO1 level 2 -> 2.8
    assert mixed["PO1"] == pytest.approx(2.8)
    assert mixed["PO4"] is None


def test_roll_up_averages_courses_where_the_target_is_non_zero():
    a = {"PO1": 3.0, "PO2": 2.0, "PO3": None}
    b = {"PO1": 1.0, "PO2": None, "PO3": None}
    assert average_over_courses([a, b]) == {"PO1": 2.0, "PO2": 2.0, "PO3": None}
