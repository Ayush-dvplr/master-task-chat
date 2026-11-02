# P12 r3 RECHECK_FIX: vendor-archive-roundtrip-recovery (board b2da4ee)

QC report: `QC_2026-10-21/qc_report/vendor-archive-roundtrip-recovery/v5.md` (kit 71a653b2; F/M/W 0/3/3).
Live kit HEAD: `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e`, the same kit the report used, so no rule changed wording or ID.
Scope (Ayush Q51): fix DS-4-1, JD-15-1 and TS-16-1. Keep DS-20-1, DS-6-1 and X1.
Levers (WORK/LEVERS.md:109-178): L2 (count unsigned, behind value_sum), L6 (one cumulator per field), L3 (run ledger), L5 (strict JSON type beside trim), plus the kept rule checks (REJ: reject_*, REP: report_*).

## Findings

| ID | Label | Rule quote (live kit) | Evidence quote | Decision | Effect per lever | Compensation | Files changed |
|---|---|---|---|---|---|---|---|
| DS-4-1 (warn) | REAL | 02_Data_Solution_QC.md:20 "NO ANSWERS IN DATA ... Nothing in any environment/ input directory may contain, encode, or make trivially derivable the expected final output of the task." | Before: catalog ids `cap-` (15200 decodes) and `rej-` (2500 rejects), so decoder_appendix.md:147-148 `catalog_ok_count` / `catalog_error_count` could be read off the ids. QC itself said it is not a fail because the reports are graded whole (v5:260). After: test_output.py:717 `return [{**row, "capture_id": f"cap-{k:05d}"} for k, row in enumerate(out, 1)]`, so all 17700 lines read `cap-00001`..`cap-17700` in file order (capture_catalog.jsonl:1 `{"capture_id":"cap-00001",...`) | FIX: one neutral id form, numbered after the rows are mixed | L2 none, L6 none, L3 none, L5 none, REJ none, REP harder (the counts now need real decoding) | none needed | tests/test_output.py (build_catalog :706, :717; hardcoded negative now picks its 6 visible rows by decoding, :2190), environment/data/capture_catalog.jsonl (regenerated, sha 6d17ea9e...), WORK/XREF.md (new entry, `rej-` retired), WORK/QC_DEFENCE.md D7, WORK/LEVERS.md:107 |
| JD-15-1 (minor) | REAL | 04_Judge_QC.md:92 "Where your reading and the label disagree, judge the criterion by your reading and report the label as the defect."; :99 code quality "is a CONDUCT criterion under JD-15" | Before: judge.toml:72 `type = "task completion"` on r5_code_quality. After: judge.toml:72 `type = "agent behavior"` | FIX: label only | all levers none | none needed | tests/judge.toml:72 |
| TS-16-1 (warn) | REAL | 03_Tests_QC.md:47 "Anti-cheat negatives must fire on the cheat and ONLY on the cheat. Ask for each: could an honest solution trip this? Could a cheater slip past it?" | Before: the check scanned only /app and /app/out, which the separate-mode verifier never receives beyond the six artifacts (task.toml:2), so it could never fire. After: test_output.py:2308-2325 keeps the static scan and also runs decode.py and encode.py on a fixture, then fires if a `.pth` file or a module named in `_SHADOWS` appeared in the run folder, the staged program folders, or (new since :2302 `_SHARED_AT_START`) the temp and site-packages folders. Local probe: oracle 107/107, no fire; oracle decode.py patched to write `json.py` into its cwd: "negative_rebinds_verifier_dependencies: penalty fired" (104/107) | FIX by replacement, not by drop: validate_bundle.py section 11.5 (strict) fails without a check of this name. Same act, same weight -3; the act still rests on instruction.md:11 "clean Python 3.12 with only the standard library ... cannot import helper modules left beside them" | all levers none | none needed | tests/test_output.py (`import site`, `_planted`, `_SHARED_DIRS`, `_SHARED_AT_START`, the check body and description), WORK/QC_DEFENCE.md N7, WORK/LEVERS.md:107. reward.toml unchanged: the positive total stays 107 and the -3 weight is unchanged |
| DS-20-1 (minor) | REAL, not graded | 02_Data_Solution_QC.md:68 "The oracle obeys the contract, independently of the tests ... Any divergence between stated rule and oracle behaviour is a fail, even when no current test would catch it." | QC probe: plain decode of a good-header damaged-frame segment gives `BadFrame: no frame starts here`, exit 1. format_contract.md:175-176 "A segment whose header passes all five checks is not rejected. If its frame bytes are damaged, read it through the salvage path in `escape_rules.md`." | KEEP (master decision Q51): no graded input reaches it; the contract routes damaged frames to the salvage path (format_contract.md:175-176). No test added | all levers none (unchanged) | n/a | none |
| DS-6-1 (minor) | REAL, cosmetic | 02_Data_Solution_QC.md:22 "Data files must make sense for the task story: formats parse, sizes are reasonable ..." | field_layouts.csv:3 `2,voltage_0002,celsius,2`, :5 `4,freq_0004,percent,2` | KEEP: cosmetic; regenerating units would touch every layout for no grading gain. The unit column is never graded | all levers none | n/a | none |
| X1 (warn) | REAL observation, not a defect | structure_qc "3 file(s) skipped as binary" | capture_alpha.varc 88 B, capture_beta.varc 51 B, capture_gamma.varc 74 B are the VARC1 sample captures the task decodes; QC re-checked them as genuine binary with no dash bytes (v5:41) | KEEP: tasker acknowledges; the binary format is the task | all levers none | n/a | none |

Suggestion test (Ayush 10:05): DS-4-1 fix makes the task harder (removes a giveaway); JD-15-1 is a label; TS-16-1 adds a runtime scan the honest solution never trips. None reveals a lever, states a rule beside its use, or gives a figure (LEVER_RULES W1, W2, W6, J1).

## Gate results (after fixes)

- xref_check.py: `54 entries, 0 findings` (53 before; new entry "catalog id field").
- structure_qc: 17 pass, 1 warn (X1, binary .varc), 0 fail. instruction_qc 5/0/0. tests_qc 37/0/0. judge_qc 19/0/0.
- validate_bundle.py --archetype format-recovery: 49 passed, 0 failed, 0 warnings, GATE PASS.
- stacking_check.py: 32 tests, 8 criteria; AL-28 groups <= 5 PASS; no TS-26 duplicates; whole documents 68/107 = 63.6% PASS; isolated 30 = 28.0% PASS; shipped only 2.8% PASS. The tool also prints "isolated+mutation 33.6% FAIL"; this is unchanged from before this round (no weight moved), and LEVER_RULES_v1.md:38 G3 limits isolated rule checks alone (28.0%). OUT/STACKING_CHECK.md verdict: STACKING PASS.
- Reflex (a2 agent program, tests channel, local rewardkit stub): before 0.1682 (18/107), after 0.1682 (18/107). Oracle locally 1.000 before and after; nop 0.000.
- Docker (exe_copy.py plain and --owner-only, tests image warmed first): see the Docker section below.

## QC_RULINGS rows

- TS-16 | negative_rebinds_verifier_dependencies scanned /app only, could not fire in separate mode | QC v5 warn TS-16-1 | REAL | replaced trigger with a run-time plant scan (run folder, staged folder, temp and site-packages diff); name and -3 kept because validate_bundle.py section 11.5 strict requires it.
- JD-15 | r5_code_quality (bare except / except Exception) labelled task completion | QC v5 minor JD-15-1 | REAL | code quality is conduct (04_Judge_QC.md:99); relabelled agent behavior.
- TS-19 | plain decode of damaged-frame segment ungraded, oracle crashes (DS-20-1) | QC v5 minor | REAL, kept | no graded input reaches it; contract routes damaged frames to salvage (format_contract.md:175-176).
- AL-28 | penalty groups -5/-3/-3/-5/-3 tests, R7 -3, R8 -5 | QC v5 pass | agree | unchanged; rebinds stays one -3 check.
- IN-15, IN-16, TS-13, TS-20, TS-26, JD-7 | QC v5 pass | agree | no change.

## Docker (tests only, copies from live exe_copy.py)

Tests image warmed first (`warm_tests.log`: tests exit 0). One nohup chain, log `/tmp/opencode-logs/vendor-archive-roundtrip-recovery-p12r3-20261023T105619-7629/chain.log`, ends ALL_DONE.
- oracle x3: 1.000, 1.000, 1.000 (no negative fired, so the new run-time rebinds scan does not trip the honest oracle under setpriv).
- owner-only oracle x1: 1.000.
- nop x1: 0.000.
Tree sha (sorted paths + contents, first 12): a8aa369483ee.

## Trap survival

Measured, not carried over. Before = the QC_2026-10-23_lp1 copy of the bundle (post lp1 r1, pre P12: its tests/test_output.py and environment/data, copied read only into WORK/trap/). After = the current BUNDLE tests/test_output.py and data. Each reading is a fresh one-edit copy of solution/solve.py (WORK/trap/mkvar.py), built with `--build` and `--emit-reports` on the matching data and scored with the local rewardkit stub (WORK/trap/run.py), unprivileged. Before losses equal the lp1 r1 STACKING_CHECK numbers for all seven readings that had one; L2e had no single score there and measures 15 (the three encode docs).

| Reading | Before loss of 107 | After loss of 107 | Ratio | Separating cases kept | Rebinds fired | Verdict |
|---|---|---|---|---|---|---|
| L2s | 36 | 36 | 1.00 | y | n | PASS |
| L2u | 56 | 56 | 1.00 | y | n | PASS |
| L2e | 15 | 15 | 1.00 | y | n | PASS |
| L6 | 59 | 59 | 1.00 | y | n | PASS |
| L3 | 18 | 18 | 1.00 | y | n | PASS |
| L5c | 33 | 33 | 1.00 | y | n | PASS |
| L5i | 26 | 26 | 1.00 | y | n | PASS |
| L5n | 8 | 8 | 1.00 | y | n | PASS |

- Separating cases: every hidden case each reading failed before still fails it after (same sets, test by test).
- Reflex (a2 agent program, its make_reports.py from trajectory step 20 rerun on the matching data): before 0.1682 (18/107), after 0.1682 (18/107); limit 0.20 and before + 0.05. Stale a2 out: 0.1402 both.
- negative_rebinds_verifier_dependencies fired on no reading, not on a2, not on the oracle (1.000). Planting cheat (oracle decode.py that writes json.py into its cwd) on the current tests: fired, all 27 positives still pass.
- Trap survival: **PASS**. No compensation needed; no bundle file changed, so no Docker re-run.

## Lessons for the master
- A negative the validator requires by name can be fixed by giving it a run-time trigger instead of dropping it; keep a local cheat probe that proves it fires.
- Catalog ids must be numbered after rows are mixed, or the prefix or order leaks the ok/error split.
- stacking_check.py prints an "isolated+mutation" G3 hint that is stricter than LEVER_RULES_v1.md:38; the master may want to align the tool or the rule.
