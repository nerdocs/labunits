"""Tests for ``parse_interval`` of the data pipeline (``scripts/``).

The pipeline is not part of the published package, so its directory is put
on ``sys.path`` here.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from parse_lab_values import parse_interval  # noqa: E402


@pytest.mark.parametrize(
    ("cell", "lower", "upper"),
    [
        ("40-90", 40.0, 90.0),
        ("0.40 - 1.40", 0.4, 1.4),
        ("<3.45", None, 3.45),
        ("≤3.45", None, 3.45),
        (">200", 200.0, None),
        ("≥0.1", 0.1, None),
        # A single value (e.g. the mean of a differential count) is a
        # degenerate interval, so the factor check can still use it.
        ("56", 56.0, 56.0),
        ("0.003", 0.003, 0.003),
    ],
)
def test_parse_interval(cell, lower, upper):
    interval = parse_interval(cell)
    assert (interval.lower_limit, interval.upper_limit) == (lower, upper)
    assert interval.text == ""


@pytest.mark.parametrize(
    "cell", ["Negative (<500)", "<50% of 08:00", ">25 mg/dL", "40–90", "n/a"]
)
def test_unparseable_cell_is_kept_as_text(cell):
    # Never an empty interval without a trace: the caller reports ``text``.
    interval = parse_interval(cell)
    assert (interval.lower_limit, interval.upper_limit) == (None, None)
    assert interval.text == cell
