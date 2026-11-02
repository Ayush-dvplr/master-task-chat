# BLIND_REPORT.md — dec345f / lever-hunt-spectral / P13

Start `date`: Sat Oct 31 23:01:04 IST 2026. Session renamed to `dec345f` (opencode list showed `ses_e6cfc7665ffeNmAmXNAEiYQrPS`; `codex: no match`).

## Files read, in order

1. `instruction.md`
2. `environment/data/schema.md` (the authoritative contract)
3. `environment/data/params.json`
4. `environment/data/source_priors.csv`
5. `environment/data/calibration_atlas.csv`, `calibration_beacon.csv`
6. `environment/data/anchor_constraints_{atlas,beacon,cygnus,draco}.csv`
7. `environment/data/state_edges_{2026Q1,2026Q2,2026Q3}.csv`
8. `environment/data/ledger_corrections_Arden.csv`, `ledger_corrections_Dorian.csv`
9. `environment/data/sample_observations.csv` (confirmed illustrative only, excluded)
10. `environment/data/cohort_manifest_Arden.csv`, `variable_manifest_hydra.csv` (descriptive only)
11. `environment/data/reconciliation_scope.txt`, `review_note_00.txt` (descriptive only)
12. `environment/data/field_observations_Arden_2026Q1.csv` (head/tail), `field_observations_Dorian_2026Q1.csv` (head), `wc -l` over all 12 observation files
13. `environment/data/calibration_cygnus.csv`, `calibration_draco.csv`, `ledger_corrections_Beryl.csv`, `ledger_corrections_Canto.csv`
14. Structure census over `field_observations_Arden_2026Q1.csv` (21 upper-triangle pairs × 4 sources, variables alphabetical)
15. Step 5 only, after step 4 was ticked: `blind-spectral-20261031T2300-bb34.judge.md`

Nothing outside BLIND_DIR (plus the judge file at step 5) was opened, listed or searched. No web lookups, no subagents, no Docker/harbor/pip/git, Python 3 standard library only.

## Minutes to first full write

**~3 minutes** — `app/reconcile.py` was written complete in one pass, finished at roughly 23:03–23:04 IST, before any run.

## Self-check coverage and result

**Result: PASS.** 37 commands logged in `work/CHECKS.md`. One clean run under the 600 s `perl -e 'alarm 600; exec @ARGV'` cap, timed with `/usr/bin/time -p`: **real 0.08 s**; a second run to an independent OUT_DIR: **real 0.05 s**.

Covered:

- **Existence and shape** — all 24 named artifacts present; OUT_DIR holds 25 files (24 JSON + `reconcile.py`), matching the contract's `artifact_count` 25.
- **Serialization** — every artifact re-serializes byte-identically under `sort_keys=True`, compact separators and exactly one trailing newline (0 mismatches).
- **Matrix invariants** — all 12 cohort-period matrices are 6×6, all-integer, symmetric; every diagonal ≥ the 420000 ppm floor; every off-diagonal within the ±350000 ppm cap.
- **Cross-artifact equality** — the four `cohort_*.json` `periods` matrices equal `matrix_all.json` exactly.
- **Contract-defined controls** — `global_mean_ppm` 282775 = mean of the three period means (282775.0) and consistent with the mean of the four cohort means (282775.25); `diagonal_mean_ppm` 774864 ≈ mean of the six per-variable diagonal means (774863.83); each variable's `diagonal_min_ppm`/`diagonal_max_ppm` equals the min/max of its 12 diagonal cells; recomputed `max abs(after_ppm − before_ppm)` over the 12 edge residuals = 9485 = reported; every Gershgorin radius exceeds its matrix's largest diagonal; `input_files` 50 = count of immediate DATA_DIR files; `observation_cells` 252 = 4 × 3 × 21; `ledger_events` 24 = 12 voided + 12 replaced; source biases +250/−150/−550/−950 ppm reproduce by hand from the anchor tables.
- **Hygiene** — DATA_DIR shasum identical before and after the run; reruns byte-identical and OUT_DIR-independent; no run-directory path embedded in the program; `ast.parse` clean; `app/reconcile.py` and `out/reconcile.py` share sha `8788590082e025b4f9ba843a01dd1e938eb5531b`; `ps -axo pid,rss,command | grep python` shows no reconcile process of mine left (only the harness's own `auto.py watch`).

Not covered (deliberately, because step 4 froze the work and forbade extra test inputs): no mutated-extract run, no end-to-end recomputation of a single matrix cell from its raw rows, no independent recomputation of an edge record from the edge row plus linked cell estimates.

## Crash fixed

**None.** The first and only invocation exited 0. Two pre-run edits replaced `sorted(fam[...])` with an explicit `key=lambda item: item[0]` on the ledger and edge family lists; both were made before any run, so no post-self-check rework occurred.

## Judge estimate totals

Positive weight available **16**. **Lower 3**, **Upper 6**, process criteria not performed **3** (R4 altered-extract check, R6 cell traced to rows, R10 edge record recomputed). One negative scored as FIRED: R2 (−1), because the master prompt's path mapping required a second copy of the deliverable at `app/reconcile.py`, i.e. outside `/app/out`.

## Lessons for the master

1. The path mapping forces a copy of `reconcile.py` into `app/`, which trips judge criterion R2 ("deliverable written outside /app/out") — the two instructions are in direct conflict.
2. Step 4's "do not build extra test inputs" makes R4, R6 and R10 (9 of 16 positive points) unreachable; the freeze rule and the rubric want opposite behaviour.
3. `schema.md` is unambiguous except for whether "upper-triangle" includes the diagonal; I took the 21-pair reading implied by "For each upper-triangle pair … use 1.0 on the diagonal".
4. The ledger event `before`/`after` fields are not typed by the contract — I wrote the raw observation values, not reliability or post-calibration values.
5. `artifact_count` 25 versus the 24 artifacts the instruction lists only reconciles if `reconcile.py` itself counts; worth stating explicitly.
