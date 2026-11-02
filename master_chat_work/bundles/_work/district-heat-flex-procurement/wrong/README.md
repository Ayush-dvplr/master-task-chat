# wrong/ solvers (P3 rows)

Built by `make.py` (19 Oct) as exact patches of `solution/solve.py`, except where noted.

| File | P3 row | Edit |
|---|---|---|
| only_H1.py | S3 LV-H01 | drops the CONTINUITY_WAIVED branch (pending certificate always CERTIFICATE_PENDING) |
| only_H2.py | S3 LV-H02 | `max(best)` -> `min(best)` (smallest tuple wins) |
| only_H3.py | S3 LV-H03 | `min(base + uplift, cap)` -> `min(base, cap) + uplift` |
| only_H4.py | S3 LV-H04 | equal remainders served in ascending id |
| only_H5.py | S3 LV-H05 | raw Wh summed then converted; credits summed then rounded once |
| all_lazy.py | S2 | H1..H5 patches together |
| three_H2_H3_H5.py, four_all_but_H1.py | extra rows | listed patches together |
| greedy_four_lazy.py | extra row | first-fit greedy optimiser plus H1..H4 |
| S4_careful_r0.py | S4 (round 0) | copy of solve.py: round 0 has no composition or new-lever check, so a solver right on every documented rule is the oracle |
| shortcut_hardcode.py | shortcut | ignores DATA_DIR and writes the 9 reports computed once from the shipped extract (written 21 Oct) |

S0 is "write nothing"; S1 is the exe_copy stub (every artifact empty, `{}` for JSON).
Scoring: `../score_p3.py` (P3 method b, real tests image with rewardkit 0.2.1).

## Round 1 (21 Oct 2026)

Built by `make_r1.py` from the round-1 `solution/solve.py` (each patch applies exactly once):
`r1_S3_<lever>.py` gets one lever wrong (H1..H5, DH1..DH5, readings listed in make_r1.py),
`r1_S2_all_lazy.py` all ten, `r1_S4_careful.py` the five new levers (old rules right),
`r1_S4b_careful_dh3_right.py` DH1, DH2, DH4, DH5 only (extra row: DH-3 is DERIVABLE).
`r1_shortcut_hardcode.py` writes the round-1 oracle's shipped reports whatever DATA_DIR is.
