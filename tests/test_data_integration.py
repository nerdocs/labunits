"""Integration tests against the real shipped ``analytes.json``.

These tests bypass the autouse fixture from ``conftest.py`` so they hit
the actual data file as the published library would.
"""

import json
from pathlib import Path

import pytest

from labunits import converters
from labunits.converters import (
    conversion_factor,
    si_unit,
    to_si_unit,
    to_traditional_unit,
    traditional_unit,
)


@pytest.fixture
def real_data(monkeypatch):
    """Reset the module cache and force a real load from the shipped JSON."""
    monkeypatch.setattr(converters, "_analytes_data", {})
    yield converters._load_data()


def test_shipped_json_is_valid():
    data_file = Path(converters.__file__).parent / "data" / "analytes.json"
    with data_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data) > 0


def test_shipped_entries_have_required_keys(real_data):
    required = {"name", "traditional_units", "si_units", "conversion_factor"}
    missing = [
        loinc for loinc, entry in real_data.items() if not required <= entry.keys()
    ]
    assert missing == []


# A few upstream entries (AccessMedicine HTML) ship without a numeric
# conversion factor — typically when the units are dimensionless or
# percentage-based and no factor is published. Track them explicitly
# so genuine regressions stand out.
KNOWN_NON_NUMERIC_FACTORS = {"27345-8"}  # Hemoglobin A2 (% total Hb <-> fraction)


def test_shipped_conversion_factors_are_numeric_when_present(real_data):
    bad = set()
    for loinc, entry in real_data.items():
        factor = entry["conversion_factor"]
        if factor == "":
            continue
        try:
            float(factor)
        except (TypeError, ValueError):
            bad.add(loinc)
    assert bad == set(), f"Non-numeric conversion factors: {bad}"


def test_known_non_numeric_factor_entries_are_still_in_data(real_data):
    # Documents the upstream gap so it's visible. If the source data
    # gets fixed and a factor is added, this test will fail and prompt
    # us to drop the entry from KNOWN_NON_NUMERIC_FACTORS.
    for loinc in KNOWN_NON_NUMERIC_FACTORS:
        assert loinc in real_data
        assert real_data[loinc]["conversion_factor"] == ""


def test_acetone_round_trip_against_real_data(real_data):
    # Acetone (LOINC 109547-0): 1 mg/dL -> 0.172 mmol/L
    assert "109547-0" in real_data
    assert si_unit("109547-0") == "mmol/L"
    assert traditional_unit("109547-0") == "mg/dL"
    assert conversion_factor("109547-0") == pytest.approx(0.172)
    assert to_si_unit(1.0, "109547-0") == pytest.approx(0.172)
    assert to_traditional_unit(0.172, "109547-0") == pytest.approx(1.0)
