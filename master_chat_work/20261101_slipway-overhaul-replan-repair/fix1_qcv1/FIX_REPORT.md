# FIX_REPORT: slipway-overhaul-replan-repair, fix-v1 (QC v1 findings), board 451146f

Route 1, option A (Ayush 1 Nov 17:38). All 11 fails and 3 minors are fixed. TS-20 and TS-23 stay as warns (see `KEPT.md`). Work ran from 17:45 to 18:45 IST on 1 Nov 2026.

- Bundle: `master_chat_work/bundles/slipway-overhaul-replan-repair/`, tree d3c86f82834f -> **b13e6ae6acc3**
- Tasks_INPUT copy: d3c86f82834f -> b13e6ae6acc3. `diff -rq` is empty and neither tree has a `__pycache__`.
- Changed files (6): `instruction.md`, `solution/TRUTH.md`, `solution/solve.sh`, `tests/judge.toml`, `tests/reward.toml`, `tests/test_output.py`. Nothing changed under `environment/`, and `solution/solve.py` is unchanged.
- Scratch and logs: `_runs/20261101/slipway-overhaul-replan-repair/fix1-1750/`

## Findings

| id | what changed (file:line, old -> new) | playbook row | recheck |
|---|---|---|---|
| IN-8 (fail) | judge.toml:24-35 R2. Old: "... records it in an output), and a missing or malformed declared input stops the run with a message naming the file." New: "The agent leaves /app/out/patched_engine.zip in which every exception handler acts on the error it catches (raises, logs and exits non-zero, or records it in an output)." The SELFCHECK `check_error_handling` (solve.sh:119-128) now witnesses R2 with the AST check alone; its missing-input and malformed-input runs are removed. | IN-8 / J4 (master note 4) | judge_qc PASS, precheck CLEAN |
| IN-15 (fail) | judge.toml old R18 `negative_edited_working_papers` (-3, "...including an edit the agent later put back") is deleted. instruction.md:9 binds the engine's run, and the tests already grade that through the `_drive` paper digest (test_output.py:5186-5187). | IN-15 relabel/strike | judge_qc PASS |
| DS-22 (fail) | TRUTH.md:12-16. Old: "Fifteen edits across six modules carry the faults." New: "Twenty seven repairs across nine modules (`cells`, `charge`, `graph`, `mutate`, `normalise`, `objective`, `publish`, `reading`, `search`) carry the fix: the fifteen catalogued faults `DFC-01` to `DFC-15` below, and `DFC-16` to `DFC-27`, which `solution/solve.py` applies after them." TRUTH.md:279, Solution shape step 4. Old: "Apply the fifteen repairs to the shipped modules." New: "Apply the twenty seven repairs `DFC-01` to `DFC-27` to the shipped modules." The DFC-27 line (TRUTH.md:65) now reads "read through `reading._declared`, whose handlers raise on the error they catch (judge R2)". | DS-22 rewrite TRUTH by script | structure_qc PASS, xref 0 |
| DS-27 (fail) | TRUTH.md old :50-52 ("The reference authoring holds the repaired engine once, inside `tests/test_output.py` as `PACKAGE_FILES`, and derives the shipped broken tree from it by applying every pair in reverse ...") is removed. New TRUTH.md:53: "`solution/solve.py` holds all twenty seven repairs in `REPAIRS` (solve.py:31-266) and asserts each anchor matches its module exactly once before applying it, in order." | DS-27 | PASS |
| TS-24 (fail) | test_output.py `_drive` :5147-5188 starts each run with Popen `start_new_session=True` (:5170-5173). Its `finally` calls `_stop_untrusted` (:5100), which kills the process group and then sweeps any remaining uid-65534 process (`_run_user_processes` :5080). A timeout raises "the delivered engine ran past 300 seconds". `_reference` (:5047) and `_held_reference` (:5211) are built from `_private_corpus` (:5018, a 0700 mkdtemp) **before** the run. The engine sees only a sealed public copy (`_public_copy` :5030, `_seal` :5010, 0755/0644). No 0777/0666 is left in the file (old :4950-4952, :5059-5066). | TS-24 (flood `_launch`/`_stop_untrusted`) | Fork probe (`fix1-1750/forkprobe/probe.log`), old vs new suite: `before survivors_after_drive 1 survivors_after_3s 1 paper forged`, `after survivors_after_drive 0 survivors_after_3s 0 paper original` |
| JD-8 (fail) | judge.toml old R3 `reported_amendments_reaching_no_cell` is deleted. Its fact is already paid by shipped_amendment_classification_exact / shipped_invalidation_sets_exact. Ids are renumbered R1-R16. reward.toml judge weight: 0.01282051282051282 -> 0.013888888888888888 (0.5/36). | JD-8 delete + renumber + reset weight | judge_qc PASS, JD-S13 |
| JD-15 (fail) | judge.toml old R10 `ran_with_a_declared_input_missing` is replaced. New R9 (judge.toml:115-126) `ran_with_a_legacy_identifier_in_a_paper`: "The agent ran the patched engine on a copy of /app/data in which it replaced one job identifier in a working paper with the legacy identifier that an active row of /app/data/identifier_crosswalk.tsv maps to that job, and printed which of the twenty five documents differ from its run on /app/data." It rests on p01:19-21. The oracle witness is solve.sh `check_crosswalk_copy` :131-159 ("EDG-4100 requiring JOB-1001 written as OLD-1001: differ none"). | JD-15 / J2a P-d | PASS, and a3 never performed this act |
| JD-16 (fail) | Same edit as IN-15: old R18 is deleted. | JD-16 strike | PASS |
| AL-10 (fail) | New `_echoes_shipped()` (test_output.py:5658). It is true when the engine's 18_final_selection on any minted round (EVAL/CHALLENGE/PROBE) or held round (all 11) equals the shipped round's stored one while that round's reference differs. hardcoded_sample_answers (:5679, -5) fires on it. package_ignores_its_input (:5702, -3) stays silent on it, so the two negatives are disjoint. `_shipped` (:5259) fails the 11 shipped_* checks on it. Weights are unchanged. | AL-10 | Forgery lane -0.0089 = (4 structural - 5)/112. This is at or below the stub (0.0), down from 0.318 at harden r2 and 35/110 in QC v1. |
| AL-2 (fail) | instruction.md old :21 is deleted: "Report, in your final message, the live workbook sheet with the key cell you matched it on, the register in force and the jobs it set aside under each reason code, a precinct whose accepted set uses a pool to its last unit with the pool it stands on, the amendments you classified as reaching no cell at all, and every fault you repaired beside the stage it sits in." Nothing is added. Variant (a) was chosen; see below. | AL-2 remove request | instruction_qc PASS |
| AL-27 (fail) | Held rounds now plant legacy ids in three more places. (1) Both ends of active precedence rows (`write_edge_journal` :1252, place `edges`). (2) Sealed frozen-register rows (:1210, `register`). (3) A payload job field completed from amendment_supplement.ndjson (AMD-102 required_job with an in_force provenance row, :1599, `supplement`). `_legacy` (:1234) uses its own child_seed key, and `_assert_legacy` (:1534) returns the places left bare. `write_corpus` redraws up to `LEGACY_DRAWS = 8` (:3755) and then stops with SystemExit. HELD_* (:4955-4970) name the new places. Grading stays inside the existing 12 crosswalk checks because the observable is the same, so there are no new checks. | AL-27 hidden reseeded rows | 300-seed scan: 133 build, 167 abort (pre-existing Q4 level-charge abort, the same 133/167 split as harden r2), 0 plant failures, 0 errors. Every held round plants at draw 0. SAMPLE/EVAL/CHALLENGE/PROBE corpora are byte-identical (compare_ref `corpus_same True`), so `_SHIPPED_DATA` needed no regeneration. |
| TS-13 (minor) | delivered_package_shape is split into delivered_package_layout (:5305), delivered_shipped_suite_unedited (:5315) and delivered_engine_stdlib_only (:5329), weight 1 each. Positive total 110 -> 112. reward.toml test weight 0.004545454545454545 -> 0.004464285714285714 (0.5/112). | TS-13 split | tests_qc PASS |
| JD-5 (minor) | R2 now pays a single act (see IN-8). | JD-5 drop half | judge_qc PASS |
| AL-7 (minor) | TRUTH.md:345-346. Old: `measured_oracle: 1.000` / `measured_nop: 0.000`. New: `measured_oracle_test_channel: 1.000` / `measured_nop_test_channel: 0.000`. TRUTH shas were written by script last: fix_patch_sha256 0419c9b5..., solve_py_sha256 101a83ec... | AL-7 | PASS |

**Why the lever is unaffected by the doc edits.**
- The instruction.md deletion removes only a report request. The crosswalk rule (p01:19-21) and every graded fact stay in the shipped docs and data.
- The TRUTH.md edits are author-side only.
- The R9 judge text names the crosswalk file the agent already reads, and the stage papers are untouched.
- No trap wording, method word or size bound was added (IN-17). precheck shows 0 IN17 warns.

**Deviation from note 3.** `carried_commitment_ledger.csv` (`commitment_id,precinct,pool,quantity,state,note`) and `licence_validity_register.csv` (`licence_code,state,valid_from_round,valid_to_round,note`) have no job identifier column. p01:19 therefore names nothing in them, and they are not planted. Adding a job column would need new doc text, which risks IN-17 and route-1 R2. This is recorded in EVIDENCE_MAP.

**AL-2 variant choice.**
- (a) Delete instruction.md:21 together with R3: a3 judge mid **9/36 = 25.0%**.
- (b) Three reply-consistency criteria at weight 1 for the kept promises: mid 12/39 = 30.8%. a3's final message reports all five promises, so it earns all three. These criteria would also double-pay R14 "stated a figure other than its file" (JD-14).
- Variant (a) was taken.

## Counts

- **Tests:** 49 registrations: 32 positive weighing 112 and 17 negative weighing -63. Was 47 / 110 / -63. TS-23 is still a warn and is kept.
- **Judge:** 16 criteria: 12 positive weighing 36 and 4 negative weighing -14. Was 18 / 39 / -17.
- **Probes:** 9 probes (R4-R12, weight 3), 27/36 = **75.0%** of positive judge weight, up from 69.2%. This is above the LEVER_RULES J2 band top of 70%. The kit does not check the band.
- **Annotations:** keys are only mode, type, evaluation_target and importance.
- **Lever:** 12 crosswalk checks at weight 5 = 60/112 = 53.6%.

## Gates (run once each, logs in fix1-1750/gates/)

- **xref_check:** 11 entries, 0 findings (`WORK/XREF.md`).
- **stacking_check:** 49 checks, positive 112, negative -63. G3 hidden/mutated 67.9% PASS. AL-28 by hand: every act is at most 5 (`OUT/STACKING_CHECK.md`).
- **precheck:** last line `PRECHECK CLEAN`. Remaining warns are X1 (4 binary files) and A3 (49 checks, TS-23 kept). There are 0 IN17 and 0 G5 warns.
- **Kit 5574d77e:** structure_qc, instruction_qc, tests_qc and judge_qc each rc 0 with 0 FAIL. structure_qc gives WARN on X1 and tests_qc gives WARN on A3.
- **validate_bundle `--archetype build-repair`:** 38 passed, 1 failed (§1.12), no new FAIL. §1.12 (validate_bundle.py:823-855) requires task.toml artifacts to equal the build-repair template list (`/app/out/package.zip`, `selftest.json`, ...). This bundle declares its own 26 artifacts (patched_engine.zip and the 01-25 documents). The failure is a template mismatch present since harden r2, not a bundle defect; renaming the deliverables would break the task.

## Lanes

Copies were made with the live kit's `exe_copy.py` (tests-only reward 1/112). Docker 8g/4cpu, with dockfree START=yes before each lane. Logs are in `fix1-1750/lanes/logs/lanes.log` (ALL_DONE).

| lane | reward | verifier s |
|---|---|---|
| oracle-1 / -2 / -3 | 1.0 / 1.0 / 1.0 | 128.0 / 124.3 / 116.7 |
| owner-only | 1.0 | 131.3 |
| nop | 0.0 | 110.3 |
| stub | 0.0 | 120.2 |
| forgery (copier of 25 shipped documents) | -0.0089 | 145.8 |

The maximum verifier time is 145.8 s of 5400 s (2.7%, under the 90% limit).

The forgery passes only present, layout, suite and stdlib (4 points). It loses all 11 shipped_* checks and all package checks, and negative_hardcoded_sample_answers fires (-5).

## Kill table (final tests, 15 rounds, harden r2 method; fix1-1750/kill_score.txt)

| row | fix-v1 tests | harden r2 | crosswalk kept |
|---|---|---|---|
| a3_program | **52/112 = 46.43%** | 45.45% | 0/60 |
| oracle_fixed | 112/112 = 100% | 100% | 60/60 |
| oracle_program (first write) | 37/112 = 33.04% | 31.82% | 0/60 |
| engine_orig | 4/112 = 3.57% | 1.82% | 0/60 |
| a3_groups | 67/112 = 59.82% | 59.09% | 15/60 |
| a3_rules | 67/112 = 59.82% | 59.09% | 15/60 |
| a3_amendments | 67/112 = 59.82% | 59.09% | 15/60 |
| oracle_less_groups (all-but-one) | 82/112 = 73.21% | 72.73% | 30/60 |
| oracle_less_rules | 82/112 = 73.21% | 72.73% | 30/60 |
| oracle_less_amendments | 82/112 = 73.21% | 72.73% | 30/60 |
| a3_careful | 112/112 = 100% | 100% | 60/60 |

Lever share is 53.6% (was 54.5%), and a3 keeps 0 of 60 crosswalk points. Every row moves up by about 1 point because of the two new structural points from the TS-13 split; that split adds 2 points every engine earns.

## a3 on the final judge (harden r2 method)

a3 earns R1 (repaired in place) and R3 (opened the two papers first). R2 (handlers) is uncertain. It performs none of the nine probes, including the new R9. R13 (claim without a later run) fires on the brute-force claim in the low case.

- **low** 3/36 = 8.3%
- **mid** 9/36 = **25.0%**
- **high** 9/36 = 25.0%

Old R3, which was the high case, is gone.

**Predicted final = (46.43 + 25.0)/2 = 35.71.** This is above 35; harden r2 was 34.27. The rise comes from two changes:
- **Judge (+1.92 points of mid):** deleting R3 and R18 (needed for JD-8, AL-2, IN-15 and JD-16) shrinks the positive judge denominator from 39 to 36 while a3 keeps its 9 points.
- **Tests (+0.98):** the TS-13 split adds 2 structural points that a3 earns.

**Fix on offer (not applied).** Add one more probe at weight 3 that a3 lacks, grounded in a doc a3 can read. Example: worked_examples.md:73-82, where a withdrawn crosswalk row makes a precedence row EDG-UNKNOWNJOB. The agent would run on a copy whose legacy id rests on a withdrawn crosswalk row and print the 19_rejected_register row. That makes the positive judge 39, so mid = 9/39 = 23.08% and the predicted final = 34.75. Probe share would become 30/39 = 76.9%.

## Not run

- No paid or agent run of a3: the judge was graded by hand from the harden r2 trajectory.
- QC v2 is for the master.
- The harbor lanes ran tests-only copies, so the judge was not exercised in Docker.

## Lessons for the master
- Deleting dead judge criteria shrinks the denominator, so a3's judge mid rises even though a3 earns nothing new. Price the judge with a3 after every deletion.
- A structural split (TS-13) gives every engine the extra points, which nudges all kill rows up by about 1 point.
- An "echo the shipped answers" detector that runs over the held rounds closes the forgery cheaply once the references come from a private corpus.
- Check the paper headers before planting under AL-27: two of the five named papers had no job column.
