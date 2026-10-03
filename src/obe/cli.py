"""Command line: `py -m obe.cli report --course CET3011B --marks marks.xlsx [--out report.xlsx]`.

Prints counts and the output path only, never student names or identifiers.
"""

import argparse
import sys
from pathlib import Path

from obe.config import CONFIG_DIR, ConfigError, load_course, load_program_outcomes, load_rules
from obe.ingest.marks import MarksFileError, load_marks
from obe.pipeline import calculate
from obe.reports.excel import write_master_workbook


def report(course_code: str, marks_path: Path, out: Path | None) -> int:
    rules, pos = load_rules(), load_program_outcomes()
    course = load_course(CONFIG_DIR / "courses" / f"{course_code}.yaml", rules, pos)
    result = calculate(course, rules, pos, load_marks(marks_path, course))
    out = out or CONFIG_DIR.parent / "data" / "sample" / f"{course_code}_report.xlsx"
    write_master_workbook(result, out)
    print(f"{len(result.scores)} students scored, {len(result.flagged)} flagged (blank marks, left out)")
    print(f"overall CO attainment {result.overall:.2f}; report written to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="obe")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("report", help="calculate a course from a marks file and write the master Excel")
    r.add_argument("--course", required=True, help="course code, e.g. CET3011B (config/courses/<code>.yaml)")
    r.add_argument("--marks", required=True, type=Path)
    r.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    try:
        return report(args.course, args.marks, args.out)
    except (ConfigError, MarksFileError) as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
