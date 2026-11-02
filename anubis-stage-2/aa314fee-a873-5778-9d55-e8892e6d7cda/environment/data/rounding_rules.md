# Rounding

Sections of this document are amended by `errata_2031-07.md`.

## 1. Where rounding is allowed

`derivation_policy.ini` names one stage, `equivalent_conversion`, and one
rule, `half_up`. Rounding happens at that stage and nowhere else. Half up
means that a value exactly halfway between two whole numbers goes to the
larger. Every quantity on the ledger is a whole number of wafer equivalents.
No later total, rollup or comparison rounds again, and no quantity is ever
truncated on the way in.

## 2. The conversion

A quantity stated at a node reaches its wafer equivalent figure through the
conversion factors of the steps the walk took. The conversion is applied one
step at a time, each step dividing by one hundred and rounding half up before
the next step is taken.

## 3. What converts

Request quantities, entitlement ceilings and committed minimums all convert
along the walk of the request they belong to, at the one stage, each one
converted once from its stated figure. Values already stated in wafer
equivalents, such as declared capacity, do not convert.

## 4. Reporting back in wafers

The ledger also reports `granted_wafers`, the grant expressed at the node the
request was served at. That figure is the granted wafer equivalents times the
denominator of the conversion, divided by the numerator, truncated towards
zero. It is a report of the grant and never feeds a later total.
