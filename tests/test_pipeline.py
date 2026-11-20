"""Tests for the checks of the data pipeline (``scripts/``).

The pipeline is not part of the published package, so its directory is put
on ``sys.path`` here.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import parse_lab_values as pipeline  # noqa: E402
from parse_lab_values import parse_interval  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_issues(monkeypatch):
    """The pipeline collects its findings in a module-level dict."""
    monkeypatch.setattr(pipeline, "issues", {key: [] for key in pipeline.issues})


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


def _factor_findings(traditional, si, factor):
    pipeline.check_factor_consistency(
        "X", parse_interval(traditional), parse_interval(si), traditional, si, factor
    )
    return pipeline.issues["inconsistent_factors"]


def test_factor_check_accepts_a_consistent_row():
    assert _factor_findings("0.6-1.2", "53-106", 88.4) == []


def test_factor_check_finds_a_factor_off_by_ten():
    # Urea nitrogen as printed in the source: 0.0357 instead of 0.357.
    assert len(_factor_findings("8-23", "2.9-8.2", 0.0357)) == 2


def test_factor_check_allows_for_the_rounding_of_the_traditional_limit():
    # Methionine: 0.1 mg/dL is anything from 0.05 to 0.15, i.e. 3.4-10 μmol/L.
    assert _factor_findings("0.1-0.6", "6-40", 67.1) == []


def test_molar_mass_check_accepts_a_matching_factor():
    pipeline.check_molar_mass(
        "Glucose", "mg/dL", "mmol/L", 0.05551, {"Glucose": 180.16}
    )
    pipeline.check_molar_mass(
        "Estradiol", "pg/mL", "pmol/L", 3.67, {"Estradiol": 272.38}
    )
    pipeline.check_molar_mass(
        "Calcium", "mg/(24.h)", "mmol/(24.h)", 0.025, {"Calcium": 40.078}
    )
    assert pipeline.issues["molar_mass_mismatch"] == []
    assert pipeline.issues["missing_molar_mass"] == []


def test_molar_mass_check_finds_a_wrong_factor():
    # Calcitriol as printed in the source: 2.6 instead of 2.4.
    pipeline.check_molar_mass(
        "Calcitriol", "pg/mL", "pmol/L", 2.6, {"Calcitriol": 416.64}
    )
    assert [f[0] for f in pipeline.issues["molar_mass_mismatch"]] == ["Calcitriol"]


def test_molar_mass_check_reports_a_missing_molar_mass():
    pipeline.check_molar_mass("Glucose", "mg/dL", "mmol/L", 0.05551, {})
    assert pipeline.issues["missing_molar_mass"] == ["Glucose"]


def test_molar_mass_check_ignores_other_unit_pairs():
    pipeline.check_molar_mass("Albumin", "g/dL", "g/L", 10.0, {})
    pipeline.check_molar_mass("Sodium", "meq/L", "mmol/L", 1.0, {})
    assert pipeline.issues["missing_molar_mass"] == []


_LOINC = {
    "1": {
        "COMPONENT": "A",
        "SYSTEM": "Ser/Plas",
        "TIME_ASPCT": "Pt",
        "PROPERTY": "MCnc",
        "METHOD_TYP": "",
        "COMMON_TEST_RANK": "5",
        "LOINC_NUM": "1",
    },
    "2": {
        "COMPONENT": "A",
        "SYSTEM": "Ser/Plas",
        "TIME_ASPCT": "Pt",
        "PROPERTY": "SCnc",
        "METHOD_TYP": "IA",
        "COMMON_TEST_RANK": "1",
        "LOINC_NUM": "2",
    },
    "3": {
        "COMPONENT": "A",
        "SYSTEM": "Ser/Plas",
        "TIME_ASPCT": "Pt",
        "PROPERTY": "SCnc",
        "METHOD_TYP": "",
        "COMMON_TEST_RANK": "9",
        "LOINC_NUM": "3",
    },
    "4": {
        "COMPONENT": "A",
        "SYSTEM": "Urine",
        "TIME_ASPCT": "Pt",
        "PROPERTY": "SCnc",
        "METHOD_TYP": "",
        "COMMON_TEST_RANK": "1",
        "LOINC_NUM": "4",
    },
}


def _siblings(loinc):
    siblings = {}
    for number, row in loinc.items():
        siblings.setdefault(pipeline._sibling_key(row), []).append(number)
    return siblings


def test_si_loinc_is_the_same_term_if_its_property_fits():
    assert pipeline._find_si_loinc("1", {"MCnc"}, _LOINC, _siblings(_LOINC)) == "1"


def test_si_loinc_prefers_the_sibling_of_the_same_method():
    assert pipeline._find_si_loinc("1", {"SCnc"}, _LOINC, _siblings(_LOINC)) == "3"


def test_si_loinc_falls_back_to_another_method():
    loinc = {k: v for k, v in _LOINC.items() if k != "3"}
    assert pipeline._find_si_loinc("1", {"SCnc"}, loinc, _siblings(loinc)) == "2"


def test_si_loinc_is_none_without_a_sibling():
    assert pipeline._find_si_loinc("4", {"MCnc"}, _LOINC, _siblings(_LOINC)) is None
