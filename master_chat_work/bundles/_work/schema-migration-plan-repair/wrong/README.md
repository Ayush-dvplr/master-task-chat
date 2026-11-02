# wrong/ (hardness round 1, auditor)

`auditor_r1/make_solvers.py` writes every auditor solver into `auditor_r1/solvers/` as a small edit of `solution/solve.py`: one variant block after `FIX_NOTES` that drops repairs (the shipped defect stays), replaces or adds repairs, and for planner variants a swapped body of the repaired `plan_migration`. All variants also ship when their own visible run crashes or takes over 600 s (`summary.json` = `{"records": 0}`). The builder's `make_wrong.py` and `r3/` were not read before these were scored.

| solver | one-line edit |
|---|---|
| S0_nop | writes nothing (harness mode `nop`) |
| S1_stub | every artifact empty, `{}` for JSON (harness mode `stub`, same as QC exe_copy --stub) |
| S1b_stub_default | shipped repo.zip copied as patched-repo.zip, every JSON in its K19 shape with empty lists (harness mode `stub_default`) |
| S2_lazy | every repair dropped except the CLI fix and `__main__.py` (the only defects the visible tests show); honest reports |
| S2_shipped | every repair dropped, no `__main__.py`, ships with 2 visible tests failing; honest reports (builder's S2) |
| S3_LV-MR-1 | oracle product-graph search, but prerequisites checked on the received state (`zip(names, start)`) |
| S3_LV-MR-2 | product-graph Dijkstra with parent pointers; equal cost keeps the smaller last edge |
| S3_D | exhaustive DFS over product-graph paths (state-aware, exact lexicographic tie); correct but exponential |
| S3_LV-MR-4 | drops the null_counts_as, fill_mode and token-list repairs (ini only, merged token lists) |
| S3_LV-MR-5 | drops the `_admit` and `_ordered` repairs (fingerprint after migration, raw partner key, file order) |
| S3_LV-MR-6 | `FieldView.from_payload` still drops nulls; signature, rename and add fixed at their call sites |
| S3_LV-MR-7 | drops the executor and classify repairs (corrections up front, no re-check, planned = migrated) |
| S3_F | drops the merge-chain and bad-line repairs (one merge hop, loop undetected, abort on bad line) |
| S3_REPORT | drops the summary repair (category = status, partners by id) |
| S3_C | drops the CLI repair and `__main__.py`; ships with 2 visible tests failing |
| S3_LV-MR-1+LV-MR-6 | S3_LV-MR-1 and S3_LV-MR-6 together (independence pair) |
| S3_LV-MR-5+LV-MR-7 | S3_LV-MR-5 and S3_LV-MR-7 together (independence pair) |
| S4_careful | Dijkstra on schema ids carrying the best path's state, equal cost keeps the smaller last edge (LV-MR-1, LV-MR-2 reflex); FieldView nulls fixed at call sites (C); ini-only presence and fill (LV-MR-4); fingerprint after token replacement (LV-MR-5); corrections applied at the top of every step for the current schema (LV-MR-7); everything else right |
| S4b_composition_only | exhaustive state-aware enumeration (right on every gadget, D x rule on ladders), call-site null fix (LV-MR-6 x 1/7/D), fingerprint after tokens (LV-MR-5 x 4); everything else right |
| SC1_claim_padding | S2_lazy plus a docstring added to one core and one report function, so all three module claims pay (shortcut) |
| S5_oracle | `solution/solve.py` unchanged |

Scoring note: S2_lazy, S2_shipped, S3_LV-MR-1, S3_LV-MR-2 and S3_LV-MR-4 were scored by the first generator version (visible-run cap 1,800 s, no timeout catch). Their visible runs took 9 to 81 s, so the later 600 s cap and catch change nothing for them. `solvers/` holds the final version.
