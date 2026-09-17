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


def test_shipped_conversion_factors_are_numeric(real_data):
    bad = {
        loinc: entry["conversion_factor"]
        for loinc, entry in real_data.items()
        if not isinstance(entry["conversion_factor"], (int, float))
    }
    assert bad == {}, f"Non-numeric conversion factors: {bad}"


def test_acetone_round_trip_against_real_data(real_data):
    # Acetone (LOINC 5568-1): 1 mg/dL -> 0.172 mmol/L
    assert "5568-1" in real_data
    assert si_unit("5568-1") == "mmol/L"
    assert traditional_unit("5568-1") == "mg/dL"
    assert conversion_factor("5568-1") == pytest.approx(0.172)
    assert to_si_unit(1.0, "5568-1") == pytest.approx(0.172)
    assert to_traditional_unit(0.172, "5568-1") == pytest.approx(1.0)
