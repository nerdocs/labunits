"""Tests for ``labunits.ucum`` — analyte-independent UCUM handling."""

import pytest

from labunits.ucum import display, normalise, ucum_factor


@pytest.mark.parametrize(
    ("from_unit", "to_unit", "expected"),
    [
        ("mg/dL", "mg/L", 10),
        ("g/L", "mg/dL", 100),
        ("g/dL", "g/L", 10),
        ("umol/L", "mmol/L", 0.001),
        ("ug/dL", "ng/mL", 10),
        ("10*3/uL", "10*9/L", 1),
        ("10*6/uL", "10*12/L", 1),
        ("/uL", "10*9/L", 0.001),
        ("/uL", "/nL", 0.001),
        ("%", "1", 0.01),
        ("um3", "fL", 1),
        ("mL/min", "mL/s", 1 / 60),
        ("mg/(24.h)", "mg/d", 1),
        ("ng/mL/h", "ng/(mL.h)", 1),
        ("u[IU]/mL", "m[IU]/L", 1),
        ("[IU]/mL", "k[IU]/L", 1),
        ("nmol/mmol{creat}", "umol/mol{creat}", 1),
        ("mm[Hg]", "mm[Hg]", 1),
        ("mg/dl", "mg/L", 10),
    ],
)
def test_ucum_factor(from_unit, to_unit, expected):
    assert ucum_factor(from_unit, to_unit) == pytest.approx(expected, rel=1e-12)


def test_ucum_factor_is_exact_for_powers_of_ten():
    assert ucum_factor("umol/L", "mmol/L") == 0.001
    assert ucum_factor("mg/dL", "g/L") == 0.01


@pytest.mark.parametrize(
    ("from_unit", "to_unit"),
    [
        ("mg/dL", "mmol/L"),  # mass is not amount of substance
        ("meq/L", "mmol/L"),  # needs the valence
        ("mosm/kg", "mmol/kg"),
        ("U/L", "ukat/L"),  # the analyte table decides, not the units
        ("U/L", "[IU]/L"),
        ("[IU]/L", "[arb'U]/L"),
        ("g/dL", "g{Hb}/dL"),
        ("mg", "mg/L"),
        ("mg/L", "mg/kg"),
    ],
)
def test_ucum_factor_refuses_other_kinds_of_quantity(from_unit, to_unit):
    with pytest.raises(ValueError, match="different kinds of quantity"):
        ucum_factor(from_unit, to_unit)


@pytest.mark.parametrize("unit", ["", "foo", "G/L", "mg/", "mg//L", "(mg", "mg/dL)"])
def test_ucum_factor_refuses_what_it_does_not_understand(unit):
    with pytest.raises(ValueError, match="Not a UCUM unit"):
        ucum_factor(unit, "g")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mg/dl", "mg/dL"),
        ("µmol/l", "umol/L"),
        ("μmol/L", "umol/L"),
        ("mcg/dl", "ug/dL"),
        ("G/l", "10*9/L"),
        ("G/L", "10*9/L"),
        ("T/l", "10*12/L"),
        ("Tsd/µl", "10*3/uL"),
        ("Mio./µl", "10*6/uL"),
        ("/µl", "/uL"),
        ("10^3/µl", "10*3/uL"),
        ("10³/µL", "10*3/uL"),
        ("x10^9/L", "10*9/L"),
        ("U/l", "U/L"),
        ("kU/l", "kU/L"),
        ("µkat/l", "ukat/L"),
        ("IE/l", "[IU]/L"),
        ("mIU/ml", "m[IU]/mL"),
        ("µIU/ml", "u[IU]/mL"),
        ("mval/l", "meq/L"),
        ("mEq/L", "meq/L"),
        ("mosmol/kg", "mosm/kg"),
        ("mmHg", "mm[Hg]"),
        ("%", "%"),
        ("mmol/mol", "mmol/mol"),
        ("fl", "fL"),
        ("sec", "s"),
        ("mm/h", "mm/h"),
        ("g/24h", "g/(24.h)"),
        ("mg / 24 h", "mg/(24.h)"),
        ("ml/min/1,73m²", "mL/min/{1.73_m2}"),
        ("U/g Hb", "U/g{Hb}"),
        ("mg/g Krea", "mg/g{creat}"),
        (" mg/dl ", "mg/dL"),
    ],
)
def test_normalise(text, expected):
    assert normalise(text) == expected


@pytest.mark.parametrize(
    "unit", ["umol/L", "10*9/L", "m[IU]/mL", "mg/(24.h)", "U/g{Hb}", "nmol/(s.L)"]
)
def test_normalise_keeps_ucum(unit):
    assert normalise(unit) == unit


@pytest.mark.parametrize(
    "text",
    [
        "",
        "u/l",  # units or micro?
        "G",  # giga-what?
        "MG/DL",
        "mg%",
        "Sekunden",  # written-out words are not unit spellings
        "pro Tag",
        "n/a",
    ],
)
def test_normalise_returns_none_when_unsure(text):
    assert normalise(text) is None


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("10*3/uL", "10³/µL"),
        ("10*12/L", "10¹²/L"),
        ("umol/L", "µmol/L"),
        ("ug/dL", "µg/dL"),
        ("ukat/L", "µkat/L"),
        ("um3", "µm³"),
        ("m[IU]/mL", "mIU/mL"),
        ("u[IU]/mL", "µIU/mL"),
        ("k[arb'U]/L", "kU/L"),
        ("mm[Hg]", "mmHg"),
        ("mg/(24.h)", "mg/24 h"),
        ("nmol/(s.L)", "nmol/(s·L)"),
        ("U/g{Hb}", "U/g Hb"),
        ("mL/min/{1.73_m2}", "mL/min/1.73 m²"),
        ("mg/dL", "mg/dL"),
        ("%", "%"),
    ],
)
def test_display(unit, expected):
    assert display(unit) == expected
