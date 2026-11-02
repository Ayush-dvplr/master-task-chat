# LEVERS - district-heat-flex-procurement

Round 0 table: `LEVERS_r0.md`. Round 1 table (41 checks, positive 139): `LEVERS_r1.md`.

## Round 2 (22 Oct 2026): 32 checks, positive total 100, negative total -16

Why: both real claude-opus-5 runs timed out at 7200 s while load-testing their own 20 and 22 site
stress cases against the stated 30 s limit (DIAGNOSIS.md). Round 2 removes the size lever LV-DH-1
(exact search at 22 sites in 30 s): an event-region now has at most 8 sites with at most 3 offers
(65,536 portfolios), the stated limit is 120 s, and the oracle's slowest graded case takes well under
a second. Difficulty comes from composition: four composed extracts are graded as whole documents.

Check layout (weight):
- Format, shipped /app/out (4): artifact set, canonical form, schema keys, array order (1 each).
- Composed extracts A grants, B search, C rejects, D mixed (72): per extract, four region files (5),
  both segment files (5), summary.json with policy_audit.json (5), data_quality.json (3).
- One rule family each (24): waiver_labels_case, tie_break_greatest_tuple_case, cap_after_uplift_case,
  residual_ties_descending_id_case, tick_feasibility_case, objective_component_order_case,
  rejected_profile_rows_case, unknown_region_site_rows_case (3 each).
- Negatives (-16): hardcoded sample (-5), reads grader (-5), external dependency (-3), hollow summary (-3).

Isolated weight share: 24 / 100 = 0.24. Shipped-data reads: 4 / 100 = 0.04. DH-3 (funded pool) is read
only through composed documents.

## Weight lost by one wrong reading (arithmetic, not a solver run)

Each row plays the verifier's own reference with exactly one wrong reading through the real check
functions (`lever_table.py`, raw output `harden_r2/lever_table.json`). "Isolated" is weight lost on the
eight single-rule checks, "composed" on the sixteen composed-extract checks. Shipped visibility is whether
the wrong reading changes any of the nine reports of the shipped data.

| Flag | Wrong reading | Lost (of 100) | Isolated | Composed | Shipped data |
|---|---|---|---|---|---|
| `C5drop` | LV-DH-7 offer count ignored | 63 | 3 | 60 | HIDDEN-ONLY |
| `H3` | LV-H03 cap applied to the base, uplift added after | 63 | 3 | 60 | HIDDEN-ONLY |
| `H5t` | LV-H05 energy sums rounded after adding raw Wh | 60 | 0 | 60 | HIDDEN-ONLY |
| `DH2` | LV-DH-2 raw Wh added inside the search | 48 | 3 | 45 | HIDDEN-ONLY |
| `H2` | LV-H02 smallest tuple wins a tie | 48 | 3 | 45 | HIDDEN-ONLY |
| `H5c` | LV-H05 credits summed before per-site rounding | 45 | 0 | 45 | HIDDEN-ONLY |
| `H1` | LV-H01 valid waiver never recognised | 43 | 3 | 40 | DERIVABLE |
| `H1order` | LV-H01 waived label ranked above a hold or cooldown | 43 | 3 | 40 | DERIVABLE |
| `H1pend` | LV-H01 pending certificate labelled CLEAR | 43 | 3 | 40 | DERIVABLE |
| `SIGNEDY` | LV-DH-6 blank waiver_signed read as Y (decoy `[export]` default) | 43 | 3 | 40 | DERIVABLE |
| `DH4range` | LV-DH-4 out-of-range interval wraps or is kept | 42 | 3 | 39 | HIDDEN-ONLY |
| `DH3` | LV-DH-3 raw pool shared (funded pool ignored) | 40 | 0 | 40 | DERIVABLE |
| `DH4unknown` | LV-DH-4 unknown-region site row kept | 35 | 3 | 32 | HIDDEN-ONLY |
| `C34` | LV-DH-7 overdelivery compared before cost | 33 | 3 | 30 | DERIVABLE |
| `C45` | LV-DH-7 offer count compared before overdelivery | 33 | 3 | 30 | DERIVABLE |
| `H1hc` | LV-H01 cooldown ranked above a hold | 33 | 3 | 30 | DERIVABLE |
| `DH4dup` | LV-DH-4 last duplicate profile row wins | 30 | 3 | 27 | HIDDEN-ONLY |
| `DH5raw` | LV-DH-5 weight doubled from the raw waiver fields | 30 | 0 | 30 | DERIVABLE |
| `H4` | LV-H04 leftover cents by ascending id | 23 | 3 | 20 | DERIVABLE |
| `W0LIST` | LV-H04 zero-weight beneficiaries listed | 23 | 3 | 20 | DERIVABLE |

Removed in round 2: LV-DH-1 (exact search at 20 and 22 sites within 30 s) and its six checks (26 of 139),
the five standalone tick checks except tick_feasibility_case, the five funded_pool_* checks, the two waived
weight checks, the one-case-per-count rejected-row checks (merged), `per_value_tick_quantisation_case`
(now read through the composed segment documents), and `ordinary_extract_*` (replaced by the composed
extracts). New: SIGNEDY (decoy), H1hc, H1pend, W0LIST, C34, C45, C5drop.
