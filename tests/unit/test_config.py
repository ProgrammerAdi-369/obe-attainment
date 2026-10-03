import copy

import pytest
import yaml

from obe.config import (
    CONFIG_DIR,
    ConfigError,
    build_course,
    load_course,
    load_program_outcomes,
    load_rules,
)

COURSE_FILE = CONFIG_DIR / "courses" / "CET3011B.yaml"


def raw(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def rules():
    return load_rules()


@pytest.fixture
def pos():
    return load_program_outcomes()


@pytest.fixture
def data():
    return raw(COURSE_FILE)


def tool(data, name):
    return next(t for t in data["tools"] if t["name"] == name)


def fails(data, rules, pos, message):
    with pytest.raises(ConfigError, match=message):
        build_course(data, rules, pos)


# ------------------------------------------------------------------ happy path


def test_sample_course_loads(rules, pos):
    c = load_course(COURSE_FILE, rules, pos)
    assert (len(c.cos), len(c.labs), len(c.units)) == (5, 8, 5)
    assert sum(u.theory_hours for u in c.units) == 45
    assert sum(x.lab_hours for x in c.labs) == 30
    assert c.co_targets == {"CO1": 60, "CO2": 50, "CO3": 55, "CO4": 50, "CO5": 50}


def test_tool_weights_add_up_to_100_per_co(rules, pos):
    c = load_course(COURSE_FILE, rules, pos)
    alloc = c.allocation()
    for co in (x.code for x in c.cos):
        total = sum(row[co] for row in alloc.values())
        assert sum(100 * row[co] / total for row in alloc.values()) == pytest.approx(100)
    # worked example in docs section 8: CO1 total 17.5, LCA 7.5 of it
    assert alloc["LCA"] == {"CO1": 7.5, "CO2": 7.5, "CO3": 15, "CO4": 0, "CO5": 0}
    assert sum(row["CO1"] for row in alloc.values()) == 17.5


def test_rules_come_from_rules_yaml(rules):
    assert rules.level_scale.levels == [3, 2, 1]
    assert rules.level_scale.floor_pct == 50
    assert (rules.split.internal, rules.split.end_term) == (0.6, 0.4)
    assert not rules.total_attainment.indirect_enabled


# ---------------------------------------------------- course checks, one each


def test_weights_need_marks_for_every_co(rules, pos, data):
    tool(data, "PBL")["co_marks"] = {"CO1": 0, "CO2": 0, "CO3": 8, "CO4": 2, "CO5": 0}
    fails(data, rules, pos, "CO5 has no marks allocated")


def test_tool_co_marks_must_add_up_to_maximum(rules, pos, data):
    tool(data, "Assignment")["co_marks"]["CO1"] = 4
    fails(data, rules, pos, "tool Assignment: co_marks add up to 6, maximum is 5")


def test_final_mapping_must_be_0_to_3(rules, pos, data):
    data["co_po_final"]["CO1"]["PO1"] = 4
    fails(data, rules, pos, "co_po_final.CO1.PO1")


def test_ticks_must_be_0_or_1(rules, pos, data):
    data["co_po_ticks"]["CO2"]["PO2"] = 2
    fails(data, rules, pos, "co_po_ticks.CO2.PO2")


def test_mapping_columns_must_match_program_outcomes(rules, pos, data):
    del data["co_po_final"]["CO3"]["PSO3"]
    fails(data, rules, pos, r"co_po_final.CO3: .*missing \['PSO3'\]")


def test_theory_hours_must_match_expected(rules, pos, data):
    data["units"][0]["theory_hours"] = 10
    fails(data, rules, pos, "theory hours add up to 46, expected 45")


def test_lab_hours_must_match_expected(rules, pos, data):
    data["labs"][0]["lab_hours"] = 5
    fails(data, rules, pos, "lab hours add up to 32, expected 30")


def test_every_co_needs_a_target(rules, pos, data):
    del data["co_targets"]["CO4"]
    fails(data, rules, pos, "CO4 has no target")


def test_target_must_be_a_percentage(rules, pos, data):
    data["co_targets"]["CO1"] = 160
    fails(data, rules, pos, "target of CO1 must be between 0 and 100")


def test_internal_maximums_must_add_up_to_rule(rules, pos, data):
    t = tool(data, "Mid-term")
    t["max_marks"], t["co_marks"] = 20, {"CO1": 9, "CO2": 11}
    fails(data, rules, pos, "internal tool maximums add up to 65, rules.yaml expects 60")


def test_end_term_must_be_out_of_rule_maximum(rules, pos, data):
    tool(data, "End-term")["max_marks"] = 50
    fails(data, rules, pos, "end-term maximum is 50, rules.yaml expects 40")


def test_unit_and_lab_refer_to_known_cos(rules, pos, data):
    data["units"][0]["co_codes"] = ["CO9"]
    data["labs"][0]["co_codes"] = ["CO8"]
    fails(data, rules, pos, "unit 1 refers to unknown CO CO9.*lab 1 refers to unknown CO CO8")


def test_lca_and_end_term_carry_no_co_marks(rules, pos, data):
    tool(data, "LCA")["co_marks"] = {"CO1": 30}
    fails(data, rules, pos, r"tool LCA \(LCA\) must not have co_marks")


def test_unknown_course_key_is_rejected(rules, pos, data):
    data["surprise"] = 1
    fails(data, rules, pos, "surprise")


# ----------------------------------------------------------- rules.yaml checks


@pytest.fixture
def rules_data():
    return raw(CONFIG_DIR / "rules.yaml")


def rules_fail(tmp_path, d, message):
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_rules(p)


def test_level_scale_must_have_three_descending_levels(tmp_path, rules_data):
    rules_data["level_scale"]["levels"] = [3, 2]
    rules_fail(tmp_path, rules_data, "level_scale")


def test_level_floor_is_required(tmp_path, rules_data):
    del rules_data["level_scale"]["floor_pct"]
    rules_fail(tmp_path, rules_data, "level_scale.floor_pct")


def test_split_must_add_up_to_one(tmp_path, rules_data):
    rules_data["split"]["end_term"] = 0.5
    rules_fail(tmp_path, rules_data, "must add up to 1")


def test_hours_bands_must_cover_every_share(tmp_path, rules_data):
    rules_data["hours_to_strength"].pop()
    rules_fail(tmp_path, rules_data, "last hours_to_strength band must start at 0")


# ------------------------------------------------------------ files and codes


def test_program_outcomes_are_po1_to_po12_and_pso1_to_pso3(pos):
    assert pos.codes == [f"PO{i}" for i in range(1, 13)] + [f"PSO{i}" for i in range(1, 4)]


def test_missing_and_broken_files_give_a_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load_rules(tmp_path / "nope.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="cannot read"):
        load_rules(bad)


def test_validation_does_not_mutate_input(rules, pos, data):
    before = copy.deepcopy(data)
    build_course(data, rules, pos)
    assert data == before
