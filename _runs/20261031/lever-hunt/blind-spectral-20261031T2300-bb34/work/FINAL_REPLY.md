# Final reply — spectral covariance repair

## What I built

A single reusable program, `reconcile.py`, runnable as `python3 reconcile.py DATA_DIR OUT_DIR`. It is shipped at `app/reconcile.py` and at the contract path `out/reconcile.py` (byte-identical, sha `8788590082e025b4f9ba843a01dd1e938eb5531b`). Python standard library only, no network, no writes outside OUT_DIR, no reads outside DATA_DIR, and no absolute run path baked in.

Inputs are discovered by **file family** inside DATA_DIR, never by fixed names: `params.json`, `source_priors.csv`, `calibration_<source>.csv`, `anchor_constraints_<source>.csv`, `state_edges_<period>.csv`, `ledger_corrections_<cohort>.csv`, `field_observations_<cohort>_<period>.csv`. `sample_observations.csv` is excluded from the corpus (it matches no family); `schema.md`, `reconciliation_scope.txt`, `review_note_*.txt` and the cohort/variable manifests are descriptive only, but are still counted in `input_files`. Cohorts, periods, sources and variables are derived from the extract itself and ordered deterministically, so the program works on an unseen extract of the same format.

Pipeline, in contract order:

1. **Anchor-derived source bias** — mean of `target_ppm − observed_ppm` per source; the reported `source_bias_ppm` is rounded nearest-even from the exact integer-difference mean.
2. **Ledger corrections**, matched by `observation_id` *before* calibration — `void` drops the observation and records `effect: voided`; `replace` substitutes `replacement_value` and `replacement_reliability_bps` and records `effect: replaced` with `before`/`after`.
3. **Calibration** — `corrected = raw × scale_ppm/1e6 + offset_ppm/1e6 + source_bias`.
4. **Weighted cross-source reconciliation** — `weight = reliability_bps/1e4 × prior_bps/1e4 × stability_bps/1e4`; each cohort/period/var_i/var_j cell is the weighted average.
5. **State-edge propagation** — `propagated = source × multiplier_ppm/1e6 + delta_ppm/1e6`; destination becomes the mean of its prior value and the propagated value; each applied edge is recorded.
6. **Matrix build** — 6×6 per cohort-period in fixed variable order, upper-triangle pairs averaged with their reverse, diagonal floored at `420000 ppm`, off-diagonals clipped to `±350000 ppm`, upper triangle mirrored to the lower.
7. **Summaries** — every mean/min/max is computed from the full-precision Decimal cell values and rounded to nearest-even ppm exactly once at output; the already-rounded matrix integers are never re-averaged. All arithmetic runs in `Decimal` at 60 digits of precision.

JSON is written with `sort_keys=True`, `separators=(",", ":")` and exactly one trailing newline.

## Artifacts produced

All 24 named artifacts in OUT_DIR: `global_summary.json`, `audit_state.json`, `dependency_checks.json`, `matrix_all.json`, `cohort_{Arden,Beryl,Canto,Dorian}.json`, `source_{atlas,beacon,cygnus,draco}.json`, `variable_{hydra,kepler,lyra,orion,pavo,vega}.json`, `convergence_periods.json`, `convergence_constraints.json`, `eigen_spectrum.json`, `residuals.json`, `ledger_effects.json`, `reproducibility.json` — plus `reconcile.py` itself, so OUT_DIR holds 25 files, matching the contract's `artifact_count`.

## Key figures

| figure | value |
|---|---|
| cohorts × periods × variables | 4 × 3 × 6 |
| `global_mean_ppm` (upper-triangle cells, all cohorts/periods) | **282775** |
| `diagonal_mean_ppm` (72 diagonal cells) | **774864** |
| `period_mean_ppm` | 2026Q1 **282750**, 2026Q2 **282812**, 2026Q3 **282763** |
| cohort `mean_ppm` | Arden **269586**, Beryl **278146**, Canto **287200**, Dorian **296169** |
| `source_bias_ppm` | atlas **+250**, beacon **−150**, cygnus **−550**, draco **−950** |
| `prior_bps` / `relative_rank` | atlas 9400/1, beacon 8950/2, cygnus 8500/3, draco 8050/4 |
| `anchor_counts` / `anchors` | 3 per source / 12 total |
| `observation_cells` | **252** (= 4 × 3 × 21 upper-triangle pairs) |
| `calibration_keys` | 12 (4 sources × 3 periods) |
| `ledger_events` | **24** (12 `voided` + 12 `replaced`) |
| applied `state_edges` / `edge_count` | **12** |
| `max_abs_edge_shift_ppm` | **9485** |
| `complete` | `true` (every cohort/period/variable diagonal cell has an estimate) |
| per-variable diagonal mean (min…max) | hydra 684958 (649928…719984), kepler 700557 (665262…736504), lyra 746852 (711517…781528), orion 792955 (757715…827369), pavo 839189 (803444…872933), vega 884672 (849986…920294) |
| Gershgorin radii (ppm) | Arden 1260311/1253027/1239284 … Dorian 1393834/1381573/1369940 |
| `input_files` / `artifact_count` / `serialization` | 50 / 25 / `json-sort-compact-newline` |

## What I checked

Self-check on the shipped extract only (37 logged commands in `work/CHECKS.md`), one clean run at **0.08 s** wall (`/usr/bin/time -p`), plus a 0.05 s rerun to a second OUT_DIR. No crash occurred, so nothing was fixed after the self-check.

- All 24 named artifacts exist; OUT_DIR holds 25 files.
- Every artifact re-serializes **byte-identically** under sorted-keys/compact/one-trailing-newline — 0 mismatches.
- All 12 matrices are 6×6, all-integer, symmetric, every diagonal ≥ the 420000 ppm floor and every off-diagonal within the ±350000 ppm cap.
- The 4 cohort files' `periods` matrices equal `matrix_all.json` exactly.
- Contract-internal controls agree: `global_mean_ppm` equals the mean of the three period means (282775.0) and matches the mean of the four cohort means (282775.25, consistent to rounding); `diagonal_mean_ppm` matches the mean of the six per-variable diagonal means (774863.83); each variable's `diagonal_min_ppm`/`diagonal_max_ppm` equals the min/max of its 12 diagonal cells; recomputed `max abs(after_ppm − before_ppm)` over the 12 edge residuals is 9485, the reported value; every Gershgorin radius exceeds its matrix's largest diagonal.
- Source biases reproduce by hand from the anchor tables (+250 / −150 / −550 / −950 ppm).
- DATA_DIR is untouched: shasum of all 50 files before and after the run is identical.
- Reruns are deterministic and OUT_DIR-independent: `diff` across the two output directories shows no differences.
- No hard-coded run path in the program; `ast.parse` clean; no stray python process of mine left running.
