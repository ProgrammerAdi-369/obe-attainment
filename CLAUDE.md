# CLAUDE.md

OBE attainment calculation system. Read `docs/PROJECT.md` first: section 8 (formulas),
section 7 (what is hardcoded) and section 13 (open items) are the specification. The build
order is the 12 steps of section 14.

## Ground rules

- Do not invent rules. Where an open item applies, use its working answer from section 13
  and mark the line with a comment such as `# OPEN: O2`.
- The calculation core is made of pure functions: no database, no file access, no global
  state. It keeps full precision; rounding happens only in reports.
- Every hardcoded value lives in a YAML file validated at start-up, never in the
  calculation code.
- Loads are idempotent and run in a transaction. Every run stores a snapshot of the
  configuration it used.
- Student names and identifiers never go into logs, and the sample workbook with real
  names stays out of git (`data/main file/` and `data/sample/` are git-ignored).
- Work one step at a time, commit after each step, and show the test results before
  moving on. Stop and wait for the go-ahead after each step.

## Stop and ask the faculty when

- The golden test shows differences beyond those in the discrepancy report.
- An open item changes a number in Table B or Table F (O2, O3, O4, O12, O13).
- A second course workbook arrives with other tools, no lab or no end-term (O8); extend
  the YAML shape, not the code.

## Commands

- Python is launched with `py` on this Windows machine.
- Install: `py -m pip install -e ".[dev]"`
- Test: `py -m pytest`
- Lint: `py -m ruff check .`
- Database: `docker compose up -d db` (copy `.env.example` to `.env` first)
