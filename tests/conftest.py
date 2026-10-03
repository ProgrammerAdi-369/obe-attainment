"""Shared test helper: recompute the Excel formulas of a report without a spreadsheet engine.

Neither Excel nor LibreOffice is used here. This small evaluator covers only what the report writes
(cell and range references, IF, AVERAGE, AVERAGEIF, IFERROR, + - * /, comparisons), recomputes every
formula from the raw numbers in the file, and returns the cells whose recomputed value differs from
the value stored next to the formula.
"""

import re

import pytest
from openpyxl import load_workbook

ERR = object()  # an Excel error value such as #DIV/0!
REF = re.compile(r"(?:'([^']+)'!)?\$?([A-Z]{1,2})\$?(\d+)(?::\$?([A-Z]{1,2})\$?(\d+))?")


class _Text(str):
    """Text in a cell. Excel's IF only evaluates the branch it takes; ours evaluates both, so
    arithmetic on text must not raise (the untaken branch is discarded)."""

    def _any(self, other):
        return _Text("")

    __mul__ = __rmul__ = __sub__ = __rsub__ = __truediv__ = __rtruediv__ = __add__ = _any


def _average_if_positive(xs, criterion):
    assert criterion == ">0"
    pos = [x for x in xs if isinstance(x, (int, float)) and x > 0]
    return sum(pos) / len(pos) if pos else ERR


class _Sheet:
    def __init__(self, path):
        self.f = load_workbook(path)  # formulas
        self.v = load_workbook(path, data_only=True)  # stored values
        self.done = {}

    def cell(self, sheet, ref):
        key = (sheet, ref.replace("$", ""))
        if key not in self.done:
            v = self.f[sheet][key[1]].value
            v = self.evaluate(sheet, v[1:]) if isinstance(v, str) and v.startswith("=") else v
            self.done[key] = _Text(v) if isinstance(v, str) else v
        return self.done[key]

    def cells(self, sheet, ref):
        return [self.cell(sheet, c.coordinate) for row in self.f[sheet][ref.replace("$", "")] for c in row]

    def evaluate(self, sheet, expr):
        def ref(m):
            sh = m.group(1) or sheet
            if m.group(4):
                return f"R({sh!r}, '{m.group(2)}{m.group(3)}:{m.group(4)}{m.group(5)}')"
            return f"C({sh!r}, '{m.group(2)}{m.group(3)}')"

        # keep text in quotes untouched: split on string literals
        parts = re.split(r'("[^"]*")', expr)
        py = "".join(p if p.startswith('"') else re.sub(r"(?<![<>!=])=(?!=)", "==", REF.sub(ref, p)) for p in parts)
        env = {
            "C": self.cell, "R": self.cells,
            "IF": lambda c, a, b: a if c else b,
            "AVERAGE": lambda xs: sum(xs) / len(xs),
            "AVERAGEIF": _average_if_positive,
            "IFERROR": lambda x, d: d if x is ERR else x,
        }
        return eval(py, {"__builtins__": {}}, env)


def formula_mismatches(path) -> tuple[int, list[str]]:
    """(number of formula cells, descriptions of the cells whose recomputed value differs)."""
    book, n, bad = _Sheet(path), 0, []
    for ws in book.f.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    n += 1
                    got, stored = book.cell(ws.title, c.coordinate), book.v[ws.title][c.coordinate].value
                    got, stored = ("" if got is None else got), ("" if stored is None else stored)
                    same = abs(got - stored) < 1e-9 if isinstance(got, (int, float)) and isinstance(stored, (int, float)) else got == stored
                    if not same:
                        bad.append(f"{ws.title}!{c.coordinate}: recomputed {got!r}, stored {stored!r}")
    return n, bad


@pytest.fixture
def check_formulas():
    return formula_mismatches
