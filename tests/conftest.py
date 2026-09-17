"""Pytest fixtures for labunits tests.

The library reads ``analytes.json`` lazily into a module-level cache
(``labunits.converters._analytes_data``). To keep tests independent of the
shipped data file we replace that cache with a small, well-known fixture
before each test and restore it afterwards.
"""

import pytest

from labunits import converters


SAMPLE_ANALYTES = {
    # Acetone: 1 mg/dL == 0.172 mmol/L
    "5568-1": {
        "name": "Acetone",
        "specimen": ["serum", "plasma"],
        "traditional_units": "mg/dL",
        "conversion_factor": 0.172,
        "si_units": "mmol/L",
        "traditional_reference_interval": {
            "lower_limit": None,
            "upper_limit": 2.0,
            "text": "",
        },
        "si_reference_interval": {
            "lower_limit": None,
            "upper_limit": 0.34,
            "text": "",
        },
        "reference_range_is_age_dependent": False,
        "loinc_num": "5568-1",
    },
    # Albumin: 1 g/dL == 10 g/L
    "1751-7": {
        "name": "Albumin",
        "specimen": ["serum"],
        "traditional_units": "g/dL",
        "conversion_factor": 10.0,
        "si_units": "g/L",
        "traditional_reference_interval": {
            "lower_limit": 3.5,
            "upper_limit": 5.0,
            "text": "",
        },
        "si_reference_interval": {
            "lower_limit": 35.0,
            "upper_limit": 50.0,
            "text": "",
        },
        "reference_range_is_age_dependent": True,
        "loinc_num": "1751-7",
    },
}


@pytest.fixture(autouse=True)
def _patch_analytes_data(monkeypatch):
    """Replace the runtime data cache with a fixed test fixture."""
    monkeypatch.setattr(converters, "_analytes_data", dict(SAMPLE_ANALYTES))
    yield
