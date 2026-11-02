# Field glossary and column aliases

Observation columns appear under different names in different files. These refer
to the SAME reading:

| canonical        | aliases                          |
|------------------|----------------------------------|
| raw_counts       | adu                              |
| instrument       | instr                            |
| quality_flag     | csv_quality, csv_quality_flag    |
| gain_label       | written_label, written_gain_label|

Scale factor storage: `factor_micro` is the per-instrument scale factor stored
as an integer multiplied by 1e6. Divide by 1e6 before applying.

Gain storage: quantum yield is stored as micro-e-per-count (integer x 1e6).
Divide by 1e6 before applying.

Drift: `drift_ppm` is a parts-per-million correction that is SUBTRACTED after
scaling.

Epoch: intervals are half-open `[mjd_start, mjd_end)`.
