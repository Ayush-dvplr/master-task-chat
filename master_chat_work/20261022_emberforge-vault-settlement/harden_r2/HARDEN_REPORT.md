# HARDEN_REPORT: emberforge-vault-settlement, round 2 (22 Oct 2026, IST)

Bundle edited in place: `master_chat_work/bundles/emberforge-vault-settlement/`. Pre-edit snapshot: `evidence/bundle_before_r2/` (sha list `evidence/bundle_before_r2.sha256`); after-tree `bundle_tree_after.sha256`. Per-run `reward.json`/`reward-details.json` in `evidence/runs/`, QC and validator output in `evidence/`. All scores are TESTS-ONLY. Harness clone HEAD `f3765e67` (the required one).

## Diagnosis summary (full text: `DIAGNOSIS.md`)

The run scored 146/155 because round 1 had written each lever's composition into one sentence (A4 paragraph 2, V9, the register's `consumed` scope) and the agent applied them literally; the calibration slice still pinned the draw uniquely, so its 840-draw search doubled as an end-to-end check of the engine; and 40 of 45 positive checks isolated one lever per season. The 9 points it lost were the S6 ambiguity (5, QC IN-16) and a crash on a missing forge reference in cl_quiet (4). Every round 1 lever LEAKED. No cause outside the fixes, so no conflict.

## Changes per fix

1. Verifier permissions. `_stage_program()` copies `/app/out/settle_vault.py` into a fresh `mkdtemp` folder (file 0644, folder 0755) and `_run_delivered` runs that copy, then removes it; `_end_group` still kills the process group and every process owned by uid 4001. tests_qc H6 now passes; the owner-only oracle run scored 1.0 with artifacts at 0600.
2. Recheck REAL rows, all applied:
   - IN-16 / AL-4: S6 sentence added to `rulebook_salvage.md` and RULEBOOK_TEXTS. N3 also says a salvage is tested against the window only where S6 lets it through.
   - AL-3 / CL-5 / CL-6: `record_shapes.md` now states `","` after every item but the last and no trailing whitespace.
   - AL-27: `_retire_pair` retires the most used plain reagent and a plain reagent sharing an edition with it, at the same patch. A last-not-first variant moves the finding record of closure_mix, consumed_retired_mix and plan48_mix.
   - DS-22: TRUTH states the real requisition counts (two in cl_partition, five in cl_quiet, four elsewhere among cl_*).
   - TS-20: `negative_rebinds_verifier_dependencies` is -5.
   - JD-5: R5 is split into R6, R7 and R8 at w1, important.
   - CL-5 numeric types: "Grades, tiers, ordinals and every other numeric column are written as JSON numbers."
   - JD-16: judge R7 dropped; `negative_imports_outside_standard_library` (-3) parses the program with `ast` and fires on any top-level import outside `sys.stdlib_module_names`.
3. Hardness redesign:
   - Confirming oracle removed. The 11 `calibration_*` tables, `calibration_controls.json`, `calibration_slice.md` and `example_workshop_report.json` are deleted. `council_rulings.json` holds two charge, two return and two scarcity rulings. Each ruling is one isolated reduction (operator chain, line return, index), and together they leave exactly one of the 840 draws (checked for all 13 seasons). No ruling is a figure of any season. The register describes the rulings; the instruction names only the register.
   - Instruction: the "Four conventions" sentence is gone, and the register no longer states a count. The final-reply ask is now computed figures only: total charge, credited salvages, closing balance of each scarce reagent, units granted. It also says the rulebooks and invariants govern over any other note (the CL-6 signpost for the decoy).
   - Composition: five mixed seasons, each graded by three whole-document checks at w5 (summary+vault+reconciliation; findings+every workshop report; every guild report+allocation).

     | season | levers |
     |---|---|
     | closure_mix | LV-EF-1, LV-EF-2 pair, LV-EF-5 |
     | consumed_cap_mix | LV-EF-3, LV-EF-1, LV-EF-5 |
     | consumed_retired_mix | LV-EF-3, LV-EF-2, LV-EF-5 |
     | plan48_mix | LV-EF-4 48, LV-EF-2, LV-EF-5; the Q5 limit follows the held reagent |
     | plan24_mix | LV-EF-4 24, LV-EF-3 with early closures, LV-EF-5 |

     The old lv1a to lv3b seasons, ld24, ld48a and ld48b are gone. cl_* and ld12 are kept as single-rule checks.
   - Decoy (study rule 5), LV-EF-5. The new `clerks_digest.md` gives five desk notes, four of them exact. The fifth says a salvage is credited against "the three most recent forges ... that the vault settled", which counts a same-day forge; S2 says strictly before the salvage's day. `_same_day_window` plants the boundary: three settled forges, then a fourth on the salvage's own day with a lower entry id. Shipped season: L0306 to L0310 (smith S002, cinderhall, A03, days 29 to 40). Every mixed season carries it too.
   - Rule by omission (study rule 4), LV-EF-1. A4 keeps only "The cap is judged on the charge a forge would carry if it settled." The cap-plus-floor composition now lives in N3's scope sentence: "Every other forge is tested against the charge cap, the vault floor and every retired reagent alike". V9's "never stands in for the cap or the floor" stays.
   - Judge (B.12): R1 to R5 are one shipped-season figure each: total charge 130027 (w5), 35 credited salvages, R04 closing 176, R11 closing 76, 54 units granted (w3 each). R6 to R8 are code quality at w1. Negatives: R9 /app/data write -5, R10 network -3, R11 honesty -3 (kept). `[judge] mode = "batched"` (QC G2, d9f94333).
4. `tests/Dockerfile` pip line is now `harbor-rewardkit==0.2.1 litellm==1.105.0` (K8); `tests/test.sh` keeps `chmod 755 /logs/verifier`.

Also: `task.toml` description no longer mentions a slice. `solve.py` recovers the draw from the rulings. `environment/data/` was regenerated from the grader's `main()` and matches it byte for byte. `reward.toml` = `{ test_output = 0.0049504950495049506, judge = 0.025 }` (0.5/101, 0.5/20). TRUTH.md was rewritten with new digests (solve.py `a646fbac...`, test_output.py `aaa72b5c...`). The stale `_work` scripts are listed in `_work/.../README_STALE.md`.

## Lever table, before and after

Before: the real run on the round 1 suite (points of 155). After: the round 2 suite, scored for a program that is right everywhere except one wrong reading. Method: grader variants built by source substitution, comparing graded observables (`evidence/variants.py`, `evidence/variants_v2.json`); points are of 101. This is a differential design check, not a solver run.

| lever | before: points / earned / status | after: wrong reading | points lost | seasons hit | moves shipped season |
|---|---|---|---|---|---|
| LV-EF-1 cap and floor | 38 / 33 / LEAKED | floor or retired refusal skips the cap | 45 | 3 | yes (charge 161271 vs 130027) |
| LV-EF-L7 every condition a finding | 30 / 25 / LEAKED | closed workshop gives CAP only | 15 | 3 | findings only |
| LV-EF-2 retired reagent | 38 / 38 / LEAKED | retirement as early refusal / returns held back / last detail | 30 / 45 / 15 | 2 / 3 / 3 | findings only / no / no |
| LV-EF-3 consumed reference | 38 / 38 / LEAKED | settled consumption only / every forge with an edition | 45 / 45 | 3 / 3 | no (shipped draw uses opening-plus-acquired) |
| LV-EF-4 ladder | 18 / 18 / LEAKED | exhaustive plan search | not measured (time lever; the run never used it) | 2 mixed + ld12 | - |
| LV-EF-5 decoy window (new) | - | digest reading (same-day forge counted) | 78 | 6 (all mixed + cl_quiet) | yes (credited 34 vs 35, R04 170 vs 176) |
| hardcoded shipped draw | - | TRUE draw on every season | 96 | 12 | - |

## Checks and weights

Before: 33 registered checks (27 positive, total 101) plus 6 negatives (-14).

| group | checks | weight each | total | share |
|---|---|---|---|---|
| mixed seasons, whole documents | 15 | 5 | 75 | 74.3% |
| single-rule (cl_* x6, ld12) | 7 | 3 | 21 | 20.8% |
| structure | 5 | 1 | 5 | 5.0% |

Isolated plus structure: 26 of 101 (25.7%), under the 30% limit. Checks that read only the shipped-data outputs: 2 of 101 (2.0%; `structure_records_delivered`, `structure_canonical_serialisation`). Negatives: hardcoded -3, filename -1, nondeterministic -1, reads /app/data -1, rebinds -5, non-stdlib import -3. The five run-based ones return False when the program does not run cleanly.

Judge: 11 criteria, positive 20, negative -11.

## Gate results (each run once)

| gate | result |
|---|---|
| structure_qc | PASS, 17 pass 0 warn 0 fail |
| instruction_qc | PASS, 5 pass 0 warn 0 fail |
| tests_qc | PASS, 37 pass 0 warn 0 fail (33 checks, no A3 warn) |
| judge_qc | PASS, 19 pass 0 warn 0 fail |
| validate_bundle.py (advisory, no archetype, Q23) | 47 pass, 3 FAIL: §1.12 (no archetype manifest, N/A), §15.5 and §15.7 (`fix_patch_sha256` provenance key, open conflict Q18, unchanged since round 1). None fixed; adding the key conflicts with the live QC's TRUTH key set |
| local oracle vs grader, 13 seasons (scratch) | 13/13 byte-identical |
| exe_copy oracle-1 / oracle-2 (Docker, harbor 0.24.0) | 1.0 / 1.0 |
| exe_copy `--owner-only` oracle (artifacts confirmed 0600) | 1.0 |
| nop | 0.0 |
| forgery (stub program replaying the shipped season's correct records) | 0.0198: only the 5 structure points paid, and `negative_hardcoded_sample_answers` fired (-3) |
| judge | not run (no API key). Checked against B.12 by reading: one figure per positive outcome criterion, each needs the full chain, 130027 appears in no shipped file, no multi-figure or echo criteria, honesty negative kept |

QC changes since 2690e960 (`git diff 2690e960 HEAD -- Input_Bundle_QC/`):

| change | status |
|---|---|
| TS-2 / K8 litellm pin | FIXED |
| TS-30 / H6 readable program, plus TS-S16 | FIXED: stage-copy shape, H6 pass |
| H6 interpreter switches (f3765e67) | PASS: no switches used |
| G2 `mode = "batched"` and the Final_checklist template | FIXED |
| Step 10 `--owner-only` run | PASS 1.0 |
| TS-S11 K8 rebuild note | PASS: copies built fresh |

Not run: PL QC model gates (Ayush), any real trajectory, the judge, hardness solvers (round notes D), time-limit re-measurement. The 38 s limit is kept. The oracle now settles a 48-requisition season in about 0.1 s locally, so the round 1 "10x slowest oracle" derivation no longer applies; the limit is still stated and enforced.

Caveats:
- One harbor process was still downloading artifacts when the owner-only and nop runs started, so three harbor processes overlapped for about 15 s.
- The decoy and the omission sentence keep every rule documented. A careful literal reader still gets them right. What changed is the cost of a miss and the absence of a shipped confirmation; how often a frontier agent misses is unmeasured.
