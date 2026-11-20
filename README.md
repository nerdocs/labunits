# Labunits


This is a simple python library for laboratory units, and to convert between them.


### Usage

```
pip install labunits
```

```python
from labunits.converters import convert, factor, si_unit, to_si_unit, to_traditional_unit

to_si_unit(1.2, "2160-0")                           # Creatinine, 1.2 mg/dL -> 106.08 umol/L
to_traditional_unit(106.08, "2160-0")               # -> 1.2 mg/dL
si_unit("2160-0")                                   # -> 'umol/L' (UCUM code)
factor("2160-0", "mg/dL", "umol/L")                 # -> 88.4
convert(106.08, "14682-9", "umol/L", "mg/dL")       # SI-side LOINC, direction from the units -> 1.2
```

Identify analytes by LOINC code; names can match several records and then raise `ValueError`.


### Intended use

`labunits` is a general-purpose unit conversion library — a lookup table of unit pairs and conversion factors keyed
by LOINC, plus one multiplication. It is **not a medical device** and has not been clinically validated. It does not
provide reference intervals, flag abnormal values or interpret results, and it is not intended for diagnosis,
monitoring, treatment decisions or any other medical purpose. Verify unit pairs and factors against your own
laboratory's data before relying on them.


### Why another library with this content?

Oh - just because - there IS NONE. I couldn't believe that.


### License

MIT. Just use it in your project and give credits.

The MIT license covers the code. The shipped analyte table contains LOINC codes, which come with their own notice:

This material contains content from LOINC (<http://loinc.org>). LOINC is copyright © 1995-2025, Regenstrief Institute,
Inc. and the Logical Observation Identifiers Names and Codes (LOINC) Committee and is available at no cost under the
license at <http://loinc.org/license>. LOINC® is a registered United States trademark of Regenstrief Institute, Inc.