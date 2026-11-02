# CHECKS.md — dec345f (lever-hunt-spectral, P13)

All paths relative to `/Users/mac/Desktop/Terminal Bench/_runs/20261031/lever-hunt/blind-spectral-20261031T2300-bb34`.

| # | command | input path | what it showed |
|---|---------|-----------|----------------|
| 1 | `python3 master_chat_tasks/tools/name_session.py dec345f` | — | `codex: no match`; `opencode: ['ses_e6cfc7665ffeNmAmXNAEiYQrPS']` — session renamed on the opencode list. |
| 2 | `date` | — | `Sat Oct 31 23:01:04 IST 2026` (start). |
| 3 | `ls -la . work/ environment/ environment/data/` | repo root + `environment/data` | 50 immediate data files; empty `app/`, `out/`, `work/`. |
| 4 | read `instruction.md` | `instruction.md` | 24 JSON artifacts + `reconcile.py` at `OUT_DIR`, CLI `reconcile.py DATA_DIR OUT_DIR`, stdlib only, deterministic JSON. |
| 5 | read `environment/data/schema.md` | `environment/data/schema.md` | authoritative contract: file families, bias/calibration/weight formulas, edge propagation, matrix build, floors/caps, nearest-even ppm, all 24 artifact shapes. |
| 6 | `cat` params/priors/calibration ×4/anchors ×4/state_edges ×3/ledger ×4/sample/manifests/scope/review_note | `environment/data/*` | floor 420000 ppm, cap 350000 ppm, rounding `nearest-even-ppm`; priors atlas 9400 … draco 8050; 12 calibration rows; 12 anchor rows; 12 state edges; 24 ledger rows (12 replace, 12 void); `sample_observations.csv` is one illustrative row (excluded). |
| 7 | `wc -l field_observations_*.csv` | `environment/data` | 12 files × 85 lines = 84 observations each (1008 total). |
| 8 | `python3 -c` pair/source census on `field_observations_Arden_2026Q1.csv` | `environment/data/field_observations_Arden_2026Q1.csv` | 21 upper-triangle var pairs × 4 sources = 84; variables `hydra kepler lyra orion pavo vega` (= sorted order); no reverse-pair rows. |
| 9 | `cp app/reconcile.py out/reconcile.py` | `app/reconcile.py` | program also shipped at the contract path `OUT_DIR/reconcile.py`. |
| 10 | `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/reconcile.py environment/data out` | `environment/data` → `out` | exit 0, `wrote 24 artifacts to out`, **real 0.08 s**; no crash, so no crash fix needed. |
| 11 | `ls out/ \| wc -l` | `out/` | 25 files = 24 JSON artifacts + `reconcile.py`, matching `artifact_count` 25. |
| 12 | `cat out/global_summary.json` | `out/global_summary.json` | `cohorts 4, periods 3, variables [hydra…vega], global_mean_ppm 282775, diagonal_mean_ppm 774864, ledger_events 24, state_edges 12`. |
| 13 | `cat out/audit_state.json` | `out/audit_state.json` | `source_bias_ppm {atlas 250, beacon -150, cygnus -550, draco -950}`, `anchor_counts` 3 each — matches hand check of `target_ppm − observed_ppm` means. |
| 14 | `cat out/dependency_checks.json` | `out/dependency_checks.json` | `observation_cells 252 (=4×3×21)`, `calibration_keys 12`, `anchors 12`, `constraints_applied 12`, `complete true`. |
| 15 | `cat out/convergence_periods.json out/convergence_constraints.json` | `out/*.json` | period means 282750 / 282812 / 282763; `max_abs_edge_shift_ppm 9485`, `edge_count 12`. |
| 16 | `cat out/eigen_spectrum.json` | `out/eigen_spectrum.json` | 4 cohorts × 3 period values, monotonically rising Arden→Dorian. |
| 17 | `cat out/reproducibility.json` | `out/reproducibility.json` | `serialization json-sort-compact-newline`, `input_files 50`, `artifact_count 25`. |
| 18 | `cat out/source_atlas.json out/source_draco.json` | `out/*.json` | ranks 1 and 4 by descending `prior_bps`; `bias_ppm` equals `audit_state`. |
| 19 | `cat out/variable_hydra.json out/variable_vega.json` | `out/*.json` | diagonal mean/min/max present and ordered (hydra 649928…719984; vega 849986…920294). |
| 20 | verification script (24-artifact presence) | `out/` | all 24 named artifacts exist, none missing. |
| 21 | verification script (byte-exact reserialize) | `out/*.json` | 0 mismatches — every file is sorted-keys, compact-separator JSON with exactly one trailing newline. |
| 22 | verification script (matrix invariants) | `out/matrix_all.json` | all 12 matrices 6×6, all values `int`, symmetric, every diagonal ≥ 420000 ppm floor, every off-diagonal ≤ 350000 ppm cap. |
| 23 | verification script (cross-artifact equality) | `out/cohort_*.json` vs `out/matrix_all.json` | the 4 cohort files' `periods` matrices equal `matrix_all` exactly. |
| 24 | verification script (contract-defined control: means) | `out/*.json` | `global_mean_ppm 282775` = mean of the 3 period means (282775.0) and ≈ mean of the 4 cohort means (282775.25, rounding-consistent); `diagonal_mean_ppm 774864` ≈ mean of the 6 per-variable diagonal means (774863.83). |
| 25 | verification script (variable min/max vs matrices) | `out/variable_*.json`, `out/matrix_all.json` | each variable's `diagonal_min_ppm`/`diagonal_max_ppm` equals min/max of its 12 diagonal matrix cells. |
| 26 | verification script (records) | `out/residuals.json`, `out/ledger_effects.json` | 12 edge residuals with keys `edge_id, before_ppm, after_ppm, propagated_ppm`; 24 ledger events = 12 `voided` + 12 `replaced`, replaced records carry `before`/`after`. |
| 27 | verification script (edge-shift control) | `out/residuals.json` vs `out/convergence_constraints.json` | recomputed `max abs(after_ppm − before_ppm)` = 9485 = reported value. |
| 28 | verification script (Gershgorin control) | `out/eigen_spectrum.json` vs `out/matrix_all.json` | every radius ≥ that matrix's largest diagonal, as a Gershgorin row sum must be. |
| 29 | verification script (`input_files`) | `environment/data` | 50 immediate files = reported `input_files`. |
| 30 | `grep` for run-dir strings in program | `app/reconcile.py` | no `_runs` / `blind-spectral` substring — no hard-coded absolute run path. |
| 31 | `shasum` of all data files before run → `/tmp/dec345f_data_before.txt` | `environment/data` | baseline checksums of all 50 files. |
| 32 | `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/reconcile.py environment/data /tmp/dec345f_rerun` | `environment/data` → `/tmp/dec345f_rerun` | exit 0, **real 0.05 s**, 24 artifacts. |
| 33 | `shasum` after run + `diff` against baseline | `environment/data` | `DATA UNCHANGED` — DATA_DIR treated read-only. |
| 34 | `diff out/*.json /tmp/dec345f_rerun/*` | `out/` vs rerun | `RERUN IDENTICAL` — no diffs, run is deterministic and OUT_DIR-independent. |
| 35 | `python3 -c "ast.parse(...)"` | `app/reconcile.py` | `syntax ok`. |
| 36 | `shasum app/reconcile.py out/reconcile.py` | both copies | identical sha `8788590082e025b4f9ba843a01dd1e938eb5531b`. |
| 37 | `ps -axo pid,rss,command \| grep python` | — | no leftover python process of mine (see CHECKS tail). |
