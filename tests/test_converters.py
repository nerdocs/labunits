"""Tests for ``labunits.converters``.

Function-style tests, no classes. The autouse fixture in ``conftest.py``
injects ``SAMPLE_ANALYTES`` into the module-level cache so the real JSON
file is irrelevant here.
"""

import math

import pytest

from labunits.converters import (
    Analyte,
    analytes,
    conversion_factor,
    convert,
    factor,
    si_unit,
    to_si_unit,
    to_traditional_unit,
    traditional_unit,
)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def test_si_unit_by_loinc():
    assert si_unit("5568-1") == "mmol/L"


def test_traditional_unit_by_loinc():
    assert traditional_unit("5568-1") == "mg/dL"


def test_lookup_by_exact_name():
    assert si_unit("Acetone") == "mmol/L"


def test_lookup_by_lowercase_name():
    assert si_unit("acetone") == "mmol/L"


def test_lookup_by_uppercase_name():
    assert si_unit("ACETONE") == "mmol/L"


def test_lookup_by_si_loinc():
    # 14582-1 is acetone as substance concentration (mmol/L).
    assert traditional_unit("14582-1") == "mg/dL"
    assert to_traditional_unit(0.172, "14582-1") == pytest.approx(1.0)


def test_si_loinc_that_is_a_key_means_that_record():
    assert traditional_unit("2601-3") == "meq/L"
    assert conversion_factor("2601-3") == pytest.approx(0.5)


def test_ambiguous_name_raises_with_candidates():
    with pytest.raises(ValueError, match="Ambiguous analyte name") as exc:
        si_unit("magnesium")
    assert "19123-9 (serum, mg/dL)" in str(exc.value)
    assert "2601-3 (serum, meq/L)" in str(exc.value)


def test_unknown_identifier_raises_value_error():
    with pytest.raises(ValueError, match="Unknown analyte identifier"):
        si_unit("definitely-not-a-real-analyte")


# ---------------------------------------------------------------------------
# conversion_factor
# ---------------------------------------------------------------------------


def test_conversion_factor_returns_float():
    factor = conversion_factor("5568-1")
    assert isinstance(factor, float)
    assert factor == pytest.approx(0.172)


def test_conversion_factor_for_albumin():
    assert conversion_factor("1751-7") == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# to_si_unit / to_traditional_unit
# ---------------------------------------------------------------------------


def test_to_si_unit_acetone():
    # 1.0 mg/dL * 0.172 == 0.172 mmol/L
    assert to_si_unit(1.0, "5568-1") == pytest.approx(0.172)


def test_to_si_unit_albumin():
    # 4.0 g/dL * 10 == 40 g/L
    assert to_si_unit(4.0, "1751-7") == pytest.approx(40.0)


def test_to_traditional_unit_acetone():
    # 0.172 mmol/L / 0.172 == 1.0 mg/dL
    assert to_traditional_unit(0.172, "5568-1") == pytest.approx(1.0)


def test_to_traditional_unit_albumin():
    # 40 g/L / 10 == 4.0 g/dL
    assert to_traditional_unit(40.0, "1751-7") == pytest.approx(4.0)


def test_round_trip_traditional_to_si_to_traditional():
    original = 2.5
    si = to_si_unit(original, "1751-7")
    back = to_traditional_unit(si, "1751-7")
    assert back == pytest.approx(original)


def test_zero_value_passes_through():
    assert to_si_unit(0.0, "5568-1") == 0.0
    assert to_traditional_unit(0.0, "5568-1") == 0.0


def test_negative_value_is_converted():
    assert to_si_unit(-3.0, "1751-7") == pytest.approx(-30.0)


def test_to_si_unit_returns_float():
    assert isinstance(to_si_unit(1.0, "5568-1"), float)


# ---------------------------------------------------------------------------
# Special float values
# ---------------------------------------------------------------------------


def test_positive_infinity_passes_through():
    assert to_si_unit(float("inf"), "5568-1") == float("inf")
    assert to_traditional_unit(float("inf"), "5568-1") == float("inf")


def test_negative_infinity_passes_through():
    assert to_si_unit(float("-inf"), "5568-1") == float("-inf")
    assert to_traditional_unit(float("-inf"), "5568-1") == float("-inf")


def test_nan_passes_through():
    assert math.isnan(to_si_unit(float("nan"), "5568-1"))
    assert math.isnan(to_traditional_unit(float("nan"), "5568-1"))


def test_analytes_enumerates_fixture():
    records = analytes()
    assert [r.loinc_num for r in records] == ["5568-1", "1751-7", "19123-9", "2601-3"]
    acetone = records[0]
    assert acetone == Analyte(
        loinc_num="5568-1",
        si_loinc_num="14582-1",
        name="Acetone",
        specimen=("serum", "plasma"),
        traditional_unit="mg/dL",
        si_unit="mmol/L",
        conversion_factor=0.172,
    )


def test_analytes_reuses_records_but_not_the_list():
    first = analytes()
    first.clear()  # a caller may do whatever it likes with its list
    second = analytes()
    assert len(second) == 4
    assert all(a is b for a, b in zip(second, analytes()))


# ---------------------------------------------------------------------------
# factor / convert (direction given by units)
# ---------------------------------------------------------------------------


def test_factor_traditional_to_si():
    assert factor("5568-1", "mg/dL", "mmol/L") == pytest.approx(0.172)


def test_factor_si_to_traditional_is_reciprocal():
    assert factor("5568-1", "mmol/L", "mg/dL") == pytest.approx(1 / 0.172)


def test_factor_accepts_si_loinc():
    assert factor("14582-1", "mg/dL", "mmol/L") == pytest.approx(0.172)


def test_factor_same_unit_is_one():
    assert factor("5568-1", "mg/dL", "mg/dL") == 1.0
    assert factor("5568-1", "mmol/L", "mmol/L") == 1.0


def test_factor_foreign_unit_raises_naming_known_units():
    with pytest.raises(ValueError, match="known units: mg/dL <-> mmol/L"):
        factor("5568-1", "U/L", "mmol/L")
    with pytest.raises(ValueError, match="Cannot convert"):
        factor("5568-1", "s", "s")
    with pytest.raises(ValueError, match="Cannot convert"):
        factor("5568-1", "not a unit", "mmol/L")


def test_factor_scales_prefix_variants_of_the_same_side():
    assert factor("5568-1", "mg/dL", "mg/L") == pytest.approx(10)
    assert factor("5568-1", "mmol/L", "umol/L") == pytest.approx(1000)
    assert factor("5568-1", "g/L", "g/L") == 1.0


def test_factor_combines_scaling_with_the_record_factor():
    # g/L -> mg/dL (x100) -> mmol/L (x0.172) -> umol/L (x1000)
    assert factor("5568-1", "g/L", "umol/L") == pytest.approx(17200)
    assert factor("5568-1", "umol/L", "g/L") == pytest.approx(1 / 17200)
    assert convert(2.0, "1751-7", "g/dL", "mg/dL") == pytest.approx(2000)


def test_factor_never_scales_between_kinds_of_quantity():
    # meq/L is not mmol/L without the analyte's valence: only the
    # magnesium record that holds this pair may answer.
    assert factor("2601-3", "meq/L", "umol/L") == pytest.approx(500)
    with pytest.raises(ValueError, match="Cannot convert"):
        factor("19123-9", "meq/L", "mmol/L")


def test_factor_unknown_analyte_raises():
    with pytest.raises(ValueError, match="Unknown analyte identifier"):
        factor("nope", "mg/dL", "mmol/L")


def test_factor_units_pick_the_record_of_a_shared_loinc():
    # 2601-3 is the meq/L record, and the SI side of the mg/dL record.
    assert factor("2601-3", "meq/L", "mmol/L") == pytest.approx(0.5)
    assert factor("2601-3", "mg/dL", "mmol/L") == pytest.approx(0.4114)
    assert factor("2601-3", "mmol/L", "mg/dL") == pytest.approx(1 / 0.4114)


def test_convert_both_directions():
    assert convert(4.0, "1751-7", "g/dL", "g/L") == pytest.approx(40.0)
    assert convert(40.0, "1751-7", "g/L", "g/dL") == pytest.approx(4.0)
    assert convert(4.0, "1751-7", "g/dL", "g/dL") == 4.0


def test_convert_matches_dedicated_functions():
    assert convert(0.172, "5568-1", "mmol/L", "mg/dL") == to_traditional_unit(
        0.172, "5568-1"
    )


def test_convert_passes_special_floats_through():
    assert convert(float("inf"), "5568-1", "mg/dL", "mmol/L") == float("inf")
    assert math.isnan(convert(float("nan"), "5568-1", "mmol/L", "mg/dL"))
