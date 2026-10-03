"""Pydantic models and loaders for the YAML configuration (docs/PROJECT.md section 7).

Every hardcoded value lives in config/*.yaml; this module only describes its shape and checks it.
A bad file raises ConfigError with the file name and what is wrong.
"""

from itertools import pairwise
from math import isclose
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class ConfigError(Exception):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---------------------------------------------------------------- rules.yaml


class Split(_Model):
    internal: float = Field(gt=0)
    end_term: float = Field(gt=0)

    @model_validator(mode="after")
    def _sums_to_one(self):
        if not isclose(self.internal + self.end_term, 1.0):
            raise ValueError("split.internal and split.end_term must add up to 1")
        return self


class TotalAttainment(_Model):
    direct_weight: float = Field(ge=0)
    indirect_weight: float = Field(ge=0)
    indirect_enabled: bool

    @model_validator(mode="after")
    def _sums_to_one(self):
        if not isclose(self.direct_weight + self.indirect_weight, 1.0):
            raise ValueError("direct_weight and indirect_weight must add up to 1")
        return self


class LevelScale(_Model):
    levels: list[int]
    floor_pct: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def _three_descending(self):
        lv = self.levels
        if len(lv) != 3 or not (lv[0] > lv[1] > lv[2]):
            raise ValueError("levels must be three strictly descending values (the scale is 3, 2, 1)")
        return self


class HoursBand(_Model):
    strength: int = Field(ge=0, le=3)
    min_pct: float = Field(ge=0, le=100)
    inclusive: bool


class Rules(_Model):
    split: Split
    end_term_max: float = Field(gt=0)
    internal_total_max: float = Field(gt=0)
    total_attainment: TotalAttainment
    level_scale: LevelScale
    hours_to_strength: list[HoursBand]
    multi_co_split: Literal["equal"]
    absent_marks: Literal[0]

    @model_validator(mode="after")
    def _bands_cover_all_shares(self):
        b = self.hours_to_strength
        if not b:
            raise ValueError("hours_to_strength needs at least one band")
        if any(x.min_pct <= y.min_pct or x.strength <= y.strength for x, y in pairwise(b)):
            raise ValueError("hours_to_strength bands must go from the highest to the lowest")
        if b[-1].min_pct != 0 or not b[-1].inclusive:
            raise ValueError("the last hours_to_strength band must start at 0 and be inclusive")
        return self


# ------------------------------------------------------ program_outcomes.yaml


class Outcome(_Model):
    code: str
    type: Literal["PO", "PSO"]


class ProgramOutcomes(_Model):
    outcomes: list[Outcome]

    @model_validator(mode="after")
    def _codes(self):
        codes = [o.code for o in self.outcomes]
        if len(set(codes)) != len(codes):
            raise ValueError("duplicate outcome codes")
        bad = [o.code for o in self.outcomes if not o.code.startswith(o.type)]
        if bad:
            raise ValueError(f"outcome code does not match its type: {', '.join(bad)}")
        return self

    @property
    def codes(self) -> list[str]:
        return [o.code for o in self.outcomes]


# ---------------------------------------------------------- courses/<code>.yaml


class CourseHeader(_Model):
    code: str
    name: str
    program: str
    class_: str = Field(alias="class")
    semester: str
    academic_year: str
    batch: str


class CO(_Model):
    code: str
    description: str


class Unit(_Model):
    unit_no: int
    theory_hours: float = Field(ge=0)
    co_codes: list[str] = Field(min_length=1)


class Lab(_Model):
    assignment_no: int
    name: str
    unit_no: int
    co_codes: list[str] = Field(min_length=1)
    lab_hours: float = Field(ge=0)


class Tool(_Model):
    name: str
    category: Literal["CCA", "LCA", "END_TERM"]
    max_marks: float = Field(gt=0)
    co_marks: dict[str, float] | None = None


class Expected(_Model):
    theory_hours: float
    lab_hours: float


Tick = Literal[0, 1]
Strength = Annotated[int, Field(strict=True, ge=0, le=3)]


class CourseConfig(_Model):
    course: CourseHeader
    cos: list[CO]
    co_targets: dict[str, float]
    units: list[Unit]
    labs: list[Lab]
    tools: list[Tool]
    co_po_ticks: dict[str, dict[str, Tick]]
    co_po_final: dict[str, dict[str, Strength]]
    expected: Expected

    def allocation(self) -> dict[str, dict[str, float]]:
        """Marks each non-end-term tool carries per CO; the LCA is split 1/N per lab assignment."""
        co_codes = [c.code for c in self.cos]
        out: dict[str, dict[str, float]] = {}
        for t in self.tools:
            if t.category == "CCA":
                out[t.name] = {co: (t.co_marks or {}).get(co, 0.0) for co in co_codes}
            elif t.category == "LCA":
                row = dict.fromkeys(co_codes, 0.0)
                for lab in self.labs:
                    for co in lab.co_codes:  # OPEN: O11, equal split between the COs of a lab
                        row[co] += t.max_marks / len(self.labs) / len(lab.co_codes)
                out[t.name] = row
        return out

    @model_validator(mode="after")
    def _checks(self):
        errs: list[str] = []
        co_codes = [c.code for c in self.cos]
        known = set(co_codes)
        if len(known) != len(co_codes):
            errs.append("duplicate CO codes")

        def refs(owner: str, codes: list[str]):
            errs.extend(f"{owner} refers to unknown CO {c}" for c in codes if c not in known)

        unit_nos = [u.unit_no for u in self.units]
        if len(set(unit_nos)) != len(unit_nos):
            errs.append("duplicate unit numbers")
        for u in self.units:
            refs(f"unit {u.unit_no}", u.co_codes)
        lab_nos = [x.assignment_no for x in self.labs]
        if len(set(lab_nos)) != len(lab_nos):
            errs.append("duplicate lab assignment numbers")
        for lab in self.labs:
            refs(f"lab {lab.assignment_no}", lab.co_codes)
            if lab.unit_no not in unit_nos:
                errs.append(f"lab {lab.assignment_no} refers to unknown unit {lab.unit_no}")

        theory = sum(u.theory_hours for u in self.units)
        if not isclose(theory, self.expected.theory_hours):
            errs.append(f"theory hours add up to {theory:g}, expected {self.expected.theory_hours:g}")
        lab_hours = sum(x.lab_hours for x in self.labs)
        if not isclose(lab_hours, self.expected.lab_hours):
            errs.append(f"lab hours add up to {lab_hours:g}, expected {self.expected.lab_hours:g}")

        names = [t.name for t in self.tools]
        if len(set(names)) != len(names):
            errs.append("duplicate tool names")
        for t in self.tools:
            if t.category == "CCA":
                if t.co_marks is None:
                    errs.append(f"tool {t.name} (CCA) needs co_marks")
                    continue
                refs(f"tool {t.name}", list(t.co_marks))
                if any(v < 0 for v in t.co_marks.values()):
                    errs.append(f"tool {t.name} has negative co_marks")
                if not isclose(sum(t.co_marks.values()), t.max_marks):
                    errs.append(
                        f"tool {t.name}: co_marks add up to {sum(t.co_marks.values()):g}, "
                        f"maximum is {t.max_marks:g}"
                    )
            elif t.co_marks is not None:
                errs.append(f"tool {t.name} ({t.category}) must not have co_marks")
        if any(t.category == "LCA" for t in self.tools) and not self.labs:
            errs.append("an LCA tool needs lab assignments to split its marks")

        for co in co_codes:
            if co not in self.co_targets:
                errs.append(f"{co} has no target")
        errs.extend(f"target given for unknown CO {co}" for co in self.co_targets if co not in known)
        errs.extend(
            f"target of {co} must be between 0 and 100"
            for co, v in self.co_targets.items()
            if not 0 <= v <= 100
        )

        for table in ("co_po_ticks", "co_po_final"):
            rows = getattr(self, table)
            for co in co_codes:
                if co not in rows:
                    errs.append(f"{table} has no row for {co}")
            errs.extend(f"{table} has a row for unknown CO {co}" for co in rows if co not in known)

        if not errs:  # the weights of every CO must be defined, so each CO needs marks in some tool
            alloc = self.allocation()
            for co in co_codes:
                if sum(row[co] for row in alloc.values()) <= 0:
                    errs.append(f"{co} has no marks allocated, so its tool weights cannot add up to 100")

        if errs:
            raise ValueError("; ".join(errs))
        return self


# -------------------------------------------------------------------- loaders


def _parse(model, data, source: str):
    try:
        return model.model_validate(data)
    except ValidationError as e:
        lines = []
        for err in e.errors():
            where = ".".join(str(x) for x in err["loc"])
            msg = err["msg"].removeprefix("Value error, ")
            lines.append(f"{where}: {msg}" if where else msg)
        raise ConfigError(f"{source}:\n  " + "\n  ".join(lines)) from None


def _read(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"{path}: cannot read ({e})") from None


def load_rules(path: Path = CONFIG_DIR / "rules.yaml") -> Rules:
    return _parse(Rules, _read(path), str(path))


def load_program_outcomes(path: Path = CONFIG_DIR / "program_outcomes.yaml") -> ProgramOutcomes:
    return _parse(ProgramOutcomes, _read(path), str(path))


def build_course(data, rules: Rules, pos: ProgramOutcomes, source: str = "course") -> CourseConfig:
    """Validate course data, then the checks that need rules.yaml and program_outcomes.yaml."""
    course = _parse(CourseConfig, data, source)
    errs: list[str] = []
    codes = set(pos.codes)
    for table in ("co_po_ticks", "co_po_final"):
        for co, row in getattr(course, table).items():
            missing, unknown = sorted(codes - set(row)), sorted(set(row) - codes)
            if missing or unknown:
                errs.append(f"{table}.{co}: columns must be the codes in program_outcomes.yaml "
                            f"(missing {missing}, unknown {unknown})")
    internal = sum(t.max_marks for t in course.tools if t.category != "END_TERM")
    if not isclose(internal, rules.internal_total_max):
        errs.append(f"internal tool maximums add up to {internal:g}, rules.yaml expects "
                    f"{rules.internal_total_max:g}")
    for t in course.tools:
        if t.category == "END_TERM" and not isclose(t.max_marks, rules.end_term_max):
            errs.append(f"end-term maximum is {t.max_marks:g}, rules.yaml expects {rules.end_term_max:g}")
    if errs:
        raise ConfigError(f"{source}:\n  " + "\n  ".join(errs))
    return course


def load_course(path: Path, rules: Rules, pos: ProgramOutcomes) -> CourseConfig:
    return build_course(_read(path), rules, pos, str(path))
