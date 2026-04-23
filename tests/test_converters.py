"""Tests for ``labunits.converters``.

Function-style tests, no classes. The autouse fixture in ``conftest.py``
injects ``SAMPLE_ANALYTES`` into the module-level cache so the real JSON
file is irrelevant here.
"""

import math

import pytest

from labunits.converters import (
    conversion_factor,
    si_unit,
    to_si_unit,
    to_traditional_unit,
    traditional_unit,
)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def test_si_unit_by_loinc():
    assert si_unit("109547-0") == "mmol/L"


def test_traditional_unit_by_loinc():
    assert traditional_unit("109547-0") == "mg/dL"


def test_lookup_by_exact_name():
    assert si_unit("Acetone") == "mmol/L"


def test_lookup_by_lowercase_name():
    assert si_unit("acetone") == "mmol/L"


def test_lookup_by_uppercase_name():
    assert si_unit("ACETONE") == "mmol/L"


def test_unknown_identifier_raises_value_error():
    with pytest.raises(ValueError, match="Unknown analyte identifier"):
        si_unit("definitely-not-a-real-analyte")


# ---------------------------------------------------------------------------
# conversion_factor
# ---------------------------------------------------------------------------


def test_conversion_factor_returns_float():
    factor = conversion_factor("109547-0")
    assert isinstance(factor, float)
    assert factor == pytest.approx(0.172)


def test_conversion_factor_for_albumin():
    assert conversion_factor("100158-5") == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# to_si_unit / to_traditional_unit
# ---------------------------------------------------------------------------


def test_to_si_unit_acetone():
    # 1.0 mg/dL * 0.172 == 0.172 mmol/L
    assert to_si_unit(1.0, "109547-0") == pytest.approx(0.172)


def test_to_si_unit_albumin():
    # 4.0 g/dL * 10 == 40 g/L
    assert to_si_unit(4.0, "100158-5") == pytest.approx(40.0)


def test_to_traditional_unit_acetone():
    # 0.172 mmol/L / 0.172 == 1.0 mg/dL
    assert to_traditional_unit(0.172, "109547-0") == pytest.approx(1.0)


def test_to_traditional_unit_albumin():
    # 40 g/L / 10 == 4.0 g/dL
    assert to_traditional_unit(40.0, "100158-5") == pytest.approx(4.0)


def test_round_trip_traditional_to_si_to_traditional():
    original = 2.5
    si = to_si_unit(original, "100158-5")
    back = to_traditional_unit(si, "100158-5")
    assert back == pytest.approx(original)


def test_zero_value_passes_through():
    assert to_si_unit(0.0, "109547-0") == 0.0
    assert to_traditional_unit(0.0, "109547-0") == 0.0


def test_negative_value_is_converted():
    assert to_si_unit(-3.0, "100158-5") == pytest.approx(-30.0)


def test_to_si_unit_returns_float():
    assert isinstance(to_si_unit(1.0, "109547-0"), float)


# ---------------------------------------------------------------------------
# Special float values
# ---------------------------------------------------------------------------


def test_positive_infinity_passes_through():
    assert to_si_unit(float("inf"), "109547-0") == float("inf")
    assert to_traditional_unit(float("inf"), "109547-0") == float("inf")


def test_negative_infinity_passes_through():
    assert to_si_unit(float("-inf"), "109547-0") == float("-inf")
    assert to_traditional_unit(float("-inf"), "109547-0") == float("-inf")


def test_nan_passes_through():
    assert math.isnan(to_si_unit(float("nan"), "109547-0"))
    assert math.isnan(to_traditional_unit(float("nan"), "109547-0"))


# ---------------------------------------------------------------------------
# Missing conversion factor
# ---------------------------------------------------------------------------


def test_missing_factor_raises_on_conversion_factor():
    with pytest.raises(ValueError, match="No conversion factor available"):
        conversion_factor("27345-8")


def test_missing_factor_raises_on_to_si_unit():
    with pytest.raises(ValueError, match="No conversion factor available"):
        to_si_unit(2.5, "27345-8")


def test_missing_factor_raises_on_to_traditional_unit():
    with pytest.raises(ValueError, match="No conversion factor available"):
        to_traditional_unit(0.025, "27345-8")


def test_missing_factor_does_not_block_unit_lookup():
    # The analyte is still known — only the factor is missing.
    assert si_unit("27345-8") == "Fraction of 1.0"
    assert traditional_unit("27345-8") == "% total Hb"
