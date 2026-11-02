# Board 9fc8d98: delivered task 5e4fd36d-f1ae-5fe6-ba83-c12436dfc083 (pa-household-ledger-reconciliation-forge)

Scratch: `/tmp/fd-pa-household-ledger-reconciliation-forge-20261024T1157`. Docker was NOT used: at 12:05 IST `docker ps` showed 3 containers I did not start (fdcgsl-patched, fdsurvey-regrade-oracle, fdsent-rg-agent), so all grading ran in a host venv (`$S/venv`, CPython 3.12.15, harbor-rewardkit==0.2.1). Commands and outputs are in `regrade.txt`, `precheck.txt` and `loss_table.md`.

## Verdict

**PARTLY.** The recorded 71.65 is real and reproducible: the delivered tests on the agent's artifacts give 0.4444 again, the oracle gives 1.0, and empty output gives 0.0. A second Opus run on the pre-delivery version also scored 71.65 with the same 12/25 pass pattern. But nearly all of the loss is a single decision. In stage S5 the agent divided by every resolved engagement in the band, not only the resolved engagements that were drawn. The spec says "sampled count over resolved count per BAND" (`spec_stage_s5_two_level_weights.md:5-6`) and never limits that "resolved count" to drawn rows. Only line 3, survey convention and the margins row definition point the right way. That one denominator scales every weight in a band by 1.875 (T1). Because the tests compare 12 downstream files byte for byte, it cost 25 of the 30 lost test points, or 23.15 of the 28.35 combined points lost. The other loss is a genuine exact-decimal half-even tie trap in q_eff (3 of 76 rows; worth 0 alone, but it must be fixed together with M1 to recover margins: 4.63 combined, split half and half). The last 0.57 comes from one final-answer conduct criterion. The judge channel (98.86) did nothing to make the task hard. The task is hard because of one under-specified multiplicative factor, multiplied across whole-document byte-exact tests on the single shipped dataset.

## Phase 1: identity, provenance, integrity

**1.1 Mapping.** `Final_Delivery_Internal/mask_map.json` maps identifier `5e4fd36d-f1ae-5fe6-ba83-c12436dfc083` to slug `pa-household-ledger-reconciliation-forge`, with source folder `Perfect_for_Delivery/Sugam_Agrawal/...`. The masking rewrite changed 8 files with 30 replacements. `task.toml:9` reads `authors = [{ name = "Shubhi Goyal", ... }]`. Category is "Personal Assistant". The QL folder is Sugam_Agrawal. The tags are python, personal-assistant, reconciliation, payroll, reimbursement and stdlib. Expert estimate 300 min, junior 1200 min.

`diff -rq` of each older copy against the delivered folder (trajectories excluded):

| Copy | Changed files and meaning |
|---|---|
| QC_Fixed_18_10_2026 (QC18) | **Masking:** env Dockerfile line 1 comment, task.toml name, solve.py docstring, TRUTH.md. **Ambiguity closure for QC:** `evaluation_policy.yaml` gains `settling_window_end_inclusive: true` and `fx_backfill_end_inclusive: true`; `fx_fallback_policy.yml` gains `window_end_inclusive: true`; spec_stage_s2 gains "exactly 45 days after anchor is inside"; spec_stage_s4 gains "reference dated exactly 10 days before anchor is still inside"; spec_stage_s3 changes "manifest base_q" to "base_q in run_profile.json"; `data_lineage.md` and `ordering_dependencies.yaml` now say to apply the stages in the listed order and not infer order from file names. **Number typing:** `output_artifact_contract.md:12-18` goes from "numbers are strings" to bare integers, with `cap`="250" as the only string. `instruction.md:15` changes from "string-typed numbers, sorted rows" to "number typing, row order". **Data:** `shift_submission_export_q1.csv` has 4 amounts changed (for example SB5000297 35754 to 40895); `perdiem_rate_reference_book.csv` has 21 lines changed; `reference_lookups.sqlite` was regenerated. **Solution:** `solve.py` reads the verdict mapping from `verdict_crosswalk.json` instead of hardcoding it. **Tests:** test_output.py (463 lines changed: b64 reference re-embedded), judge.toml (200 lines changed: mode batched, two criteria widened to accept either source file), tests/Dockerfile adds `litellm==1.105.0`, test.sh changes chmod 700 to 755. reward.toml is identical. |
| stale_Pass@1 (STALE) | Same as QC18 except judge.toml (`mode="individual"`, narrower R15/R24 source wording) and test.sh. Compared with the delivered folder: instruction line 15 and test_output.py differ. It contains a second claude-opus-5 run (21 Oct). |
| Low_Effort (Client_Fixed) | Older format (tests/rubric.json and test_weights.json, README.md "Difficulty explanation", glm-5.3 run at combined 54.55). The flux_* files were later renamed currency_*. binary_reading_notes, escalation_matrix, s7, s8 and solve.sh differ. A predecessor, `Backup_Tasks_(High_Pass_Rate_Rejected)/No_Trajectory/household-ledger-reconciliation-engine`, was rejected for a high pass rate. |

**1.2 Masking residue.** `grep -rIniE "household-ledger|pa-household|shubhi|goyal|sugam|agrawal|/Users/|kiro-staged|macbookpro|ethara|apple/Desktop"` with trajectories excluded returns one hit, `task.toml:9` (the author field, which is required). Inside trajectories there are 0 hits; paths were rewritten to `/delivery/5e4fd36d-...`. Nothing de-masks the task beyond the author field.

**1.3 Leaks into `environment/`.** No output figures are copied: 615 distinctive numbers from the 28 reference files matched only ids (7000000…) and 1.000000/0.500000. Author-note and trap content that the agent can see:
- `known_traps_and_footguns.md` lists 10 "Known Footguns" (for example "5 Allocate each stratum's rounding residue to the largest weight", "7 Threshold inclusive (>=)"). The agent read it at step 6.
- `sheet_selection_rule.yaml:3-4` has `draft_sheets_are_decoys: true` and `legacy_plaintext_multipliers_are_decoys: true`.
- `calibration_legacy_multipliers.csv` notes say `SUPERSEDED - probability-space; do not use`.
- `reconciliation_checkpoints.ndjson` checkpoint names act as a trap list (`anchor_is_first_submission_not_canonical`, `threshold_comparison_is_inclusive`, ...).
- `instruction.md:3`: "The correct reading of several stages differs from the obvious one".
- `sample_worked_records.jsonl` has 210 rows of `note: "reference worked example - see specs"` and carries no values.

## Phase 2: kit verdict

**2.1** precheck (`precheck.txt`, run on a copy named with the masked id and without trajectories):

| structure_qc | instruction_qc | tests_qc | judge_qc | fails | minors | warns | our extra hits | tests | criteria |
|---|---|---|---|---|---|---|---|---|---|
| 17 pass, 1 WARN X1 (3 binary files skipped) | 5 pass | 35 pass | 19 pass | 0 | 0 | 1 | 1: `ENV HOME not in lines 2-3 after FROM` (FC-S24) | 25 | 27 |

A first run with the folder named `bundle` raised T13 `[task] name must be 'terminal-bench/bundle'`. That is an artefact of the folder name and is not counted. The precheck author-note grep did **not** catch any of the 1.3 items: `precheck.sh:43` is case-sensitive and word-bounded (`\bTRAPS?\b|_traps\b`, which `known_traps_and` does not match), has no `decoy` term, and never greps file names.

**2.2 Team QC report: none exists** for this task. Searched `Perfect_for_Delivery` (only Poonam_Chourey reports, for 4 other slugs), `QC/reports` (9 other slugs), `QC assigned/qc_report`, and `find Anubis_Tasks_Samples -iname "*QC*Report*"`. Earlier mentions are only `master_chat_work/20261022_pl-note/passat1_scan/SCAN.md:66` ("SAFE — No uid drop") and `20261022_litellm-check/LITELLM_CHECK.md:588,693` (litellm pin missing in QC18 and STALE, now fixed). So there are no accepted warns on record to compare against. Our live kit today finds only the X1 warn.

**Points where the delivered task breaks OUR rules yet was delivered:**

| # | Break | Our rule (file:line) |
|---|---|---|
| 1 | Overall 71.65 on both Opus runs (delivered run and STALE run) | `_COMMON_RULES_v3.md:55` "tests < 100, rubric < 100, overall < 70, on 2 runs" |
| 2 | Kit WARN X1 left open | `_COMMON_RULES_v3.md:56` "zero findings, warns included (dec 101)" |
| 3 | No ENV HOME after FROM in env Dockerfile | `_COMMON_RULES_v3.md:38` (Always 7) |
| 4 | Agent-visible trap list `known_traps_and_footguns.md`; "trap" in a file name; checkpoint names that list traps | `_COMMON_RULES_v3.md:27` (Never 8, "no trap lists") and `:28` (Never 9, "including in ... file names and data fields") |
| 5 | `decoys: true` data fields; "SUPERSEDED ... do not use"; instruction "differs from the obvious one", "leaving every superseded sheet ... aside" | `_COMMON_RULES_v3.md:27` ("no sentence that names the wrong reading"), `:28` ("decoy") |
| 6 | 100% of test points are byte-exact comparisons on the shipped dataset; no hidden reseeded inputs; the agent's program is never run | `P2_build_v3.md:80-82` ("shipped-only <= 5%", hidden inputs from seed) |
| 7 | Negative test `negative_artifacts_contradict_each_other` (-3) grades internal consistency, not a cheating act | `P2_build_v3.md:85` ("negatives: only cheating acts") |
| 8 | About 5,455 text lines in total (all far under 2,000 per file) | `P2_build_v3.md:70` (20,000 total) |
| 9 | Data file that carries no values (`sample_worked_records.jsonl`) | `P2_build_v3.md:68-69` ("every file must matter to a graded result") |
| 10 | Rubric 98.86, so the judge channel adds no difficulty | Not broken (`<100` holds), but it would fail the beta gate rubric < 90 (`knowledge/KNOWLEDGE.md:45`) |

**What bar it met:** tests 44.44 < 100 and rubric 98.86 < 100 hold; overall < 70 does not. It is the only one of the 6 Final_Delivery tasks above 70 (the others score 41.22, 34.52, 19.76, 17.64 and 60.27, per the `pass_summary.json` files). The delivery-side bar actually applied is UNVERIFIED: no document in `Anubis_Tasks_Samples` states it.

## Phase 3: scores, re-graded

**3.1** `reward.toml`: weights test_output = 1/108 and judge = 1/176. The positive test weights total 54 and the judge weights total 88, so each channel is worth 0.5. Combined = 0.5·24/54 + 0.5·87/88 = 0.22222 + 0.49432 = 0.71654. That matches `pass_summary.json` 71.65, `verifier/reward.json` `{"reward": 71.65}`, `result.json` `verifier_result.reward 0.7165` and `test-stdout.txt` `reward: 0.7165`. There is no mismatch: the only difference is scale (0-1 against 0-100). `reward-details.json` is not synthesized.

**3.2** The full table is in `loss_table.md`. Summary: 12 tests lost, 30 of 54 test points (margins 5, settlement 5, metrics_json 5, incurred_shares 3, weight_diagnostics 3, per_stratum_metrics 3, and six 1-point documents). The negative test did not fire. The judge lost only R5 (1 of 88), and the negative R27 did not fire.

**3.3** Re-grade (`regrade.txt`; host venv, rewardkit with the delivered `test_output.py` unchanged and the test channel only):

| Workspace | Result |
|---|---|
| Agent artifacts (`run_1/artifacts/app/out`) | 0.4444 (24/54): **matches the recorded score** |
| Oracle (`solve.py environment/data out`, 0.07 s) | 1.0; 28/28 files byte-identical to the embedded reference |
| nop (empty out/) | 0.0; the negative does not fire |
| STALE second-run artifacts | 0.4444 |

## Phase 4: where Opus lost

**4.1 Timeline.** 29 steps, 11:00:33 to 11:08:11 (agent execution 11:00:19 to 11:08:16, about 8 min). Tokens: 1,656,331 input (1,562,233 cached) and 34,242 output, $2.23 (`trajectory_usage.json`).

| Steps | What the agent did |
|---|---|
| 3 | `find /app` |
| 4 | Read readme, overview and s1..s8 |
| 5 | Read the output contract |
| 6 | Read 27 small rule files, including known_traps_and_footguns.md |
| 7 | `head -4` of 17 data files |
| 8-10 | xlsx and PDF extraction |
| 11-16 | Data probes and sqlite schemas |
| 17 | `grep -rn "nonresponse\|resolved count…"`, which surfaced s5:4-7 |
| 18 | First output code (`/app/solve.py`, 531 lines) |
| 19, 21 | Two fixes |
| 20, 21 | Runs |
| 22-27 | Self-checks: gap counts, residue sums, byte hygiene, determinism md5. No comparison against any reference was possible, because `unit_test_vectors.json` holds only toy vectors and `sample_worked_records.jsonl` has no values. |
| 28 | Wrote AGENTS.md |
| 29 | Final message |

It never touched `/tests`, `/logs/verifier` or `solution/` (grep over all steps; the only hits are generic words in steps 1-2).

**4.2 Losses**

| Lost item | Points | What the agent did | Right answer and settling line | Class |
|---|---|---|---|---|
| margins, settlement, metrics_json, incurred_shares, weight_diagnostics, per_stratum_metrics, settlement_breakdown, settlement_ledger, net_benefit_summary, overall_metrics_md, reconciliation_report, audit_summary | 25 tests (+ half of margins) | Step 18, solve.py:216-217: `resolved_by_band = Counter(band for k in POP_KEYS if resolved)`, which counts all 135 resolved rows instead of the 76 drawn ones. Its own weighted set (lines 219-221) does apply `drawn=="1"`. | Oracle solve.py:361-377 counts resolved AND drawn per band. The spec, s5:3, says "Only engagements that are resolved AND drawn (drawn=1) carry a weight", and s5:5-6 says "nonresponse factor is sampled count over resolved count per BAND". No line says that the "resolved count" in the denominator is limited to drawn rows. Contract :69-70 (margins rows are `drawn == "1"`) and :331 `resolved_weighted` are indirect. | AMBIGUITY + AMPLIFICATION |
| margins (q_eff) | 5 shared with M1 | Floats in the S3 recurrence (agent lines 176-188) | Decimal arithmetic, 8 dp half-even (`rounding_and_precision.yml:2-3`, contract :22). Ties at 0.143210375, 0.431007625 and 0.412560075. | GENUINE |
| R5 judge (settling file per stage) | 1 of 88 | Step 29: the S3, S5, S7 and S8 bullets do not name a file (score.json reasoning) | `instruction.md:15` "say plainly which reading you chose for each interacting stage and what in the corpus told you so" | CONDUCT |

No losses were JUDGE ERROR or ARTEFACT. The judge did pass R17 (the nonresponse-partition criterion) although M1 sits inside that same factor. That is a judge blind spot that worked in the agent's favour, not a lost point.

**4.3 Distinct mistakes: 3.**
- **M1:** 25 test points across 11 tests, plus a share of margins. Patching only M1 in the reconstructed agent solver (which reproduces the recorded artifacts 28/28 byte-identically) scores 0.9074 (49/54): +25 points.
- **M2:** 0 points alone. M1 + M2 patched scores 1.0 (54/54), so margins (+5) needs both.
- **M3 (R5):** 1 judge point.
- Combined loss by class: AMBIGUITY/AMPLIFICATION 25.46, GENUINE 2.31, CONDUCT 0.57, total 28.35.
- Second run (STALE): M1 again (HOUSE-T1 weight 2.755553 against 5.166665), no M2 (0 q_eff diffs), R5 lost again.

**4.4 Did it read the saving line?** Yes. It read s5 in full at step 4, and its step-17 grep quoted s5:4-7 verbatim. The final message (step 29) restates "nonresponse = sampled(band)/resolved(band)" and gives no drawn qualifier. It read the line but took "resolved" literally. For M2 it read `rounding_and_precision.yml` at step 6 and applied half-even only when formatting floats.

## Phase 5: design anatomy

1. **Instruction:** 19 lines, 5,672 B, six prose paragraphs, then the 28 output paths and the timeout. Every rule is stated by reference ("documented ...") and points into `/app/data`. It names every concept: economic key, first-submission anchor, review_seq, running baseline, minor-unit exponents, live sheet, per-diem backfill, frozen stratum, two partitions, log-odds, inclusive threshold, overall ratio, macro means, PDF-only constants and the ESS denominator. It hints at the difficulty ("differs from the obvious one"). It deliberately leaves out the drawn restriction on the nonresponse denominator and every number.
2. **Data:** 57 files, 568 KB, about 5,455 text lines. Formats: md ×18, json 7, txt 5, tsv 4, psv 4, csv 4, yaml/yml 5, xml 2, ndjson 2, jsonl 2, xlsx, pdf (6 pages), sqlite and db. Decoys: a DRAFT xlsx sheet, `calibration_legacy_multipliers.csv`, sqlite files that duplicate flat files (`binary_reading_notes.md`), `sample_worked_records.jsonl`, and many 217-line filler tables. Trap locations: s1 key, s2 anchor/review_seq/45-day window, s3 recurrence (M2), s4 per-diem backfill and minor units, s5 two partitions (M1), s6 log-odds and inclusive threshold, xlsx LIVE gain, PDF cost/beta/z. There is no hidden or next-period tier.
3. **Tests:** 25 (24 positive worth 54, plus one negative at -3). Weights are 5 (3 tests), 3 (9) and 1 (12). Every value test is a byte-exact `_same` comparison against an embedded gzip+b64 reference of one shipped dataset (test_output.py:49-268), which is whole-population grading. The b64 reference has no digest; `manifest_digest_covers_delivered_core` checks self-consistency. One concept (the band factor) touches 12 tests. Ratio outputs (CIs, stream, rollup) are scale-invariant, so they survive M1. There is no anti-hardcode check; the tests are unreadable to the agent (`test.sh` runs `chmod -R go-rwx /tests` and the verifier is separate). Verifier timeout 3600 s.
4. **Judge:** 27 criteria (26 positive worth 88, plus one -3 honesty negative), batched, gpt-5.6-sol. Targets: 23 trajectory, 3 final answer. 18 criteria (R6-R23) restate a method the tests already grade. They are cheap for an agent that read the specs: 87/88 on both runs. Whether the oracle passes is UNVERIFIED and not applicable, because there is no oracle trajectory. R1 (read specs before code) and R5 depend on agent conduct.
5. **Solution:** `solve.py` 690 lines / 28,001 B, stdlib with Decimal, single pass, 0.07 s. `solve.sh` (22 lines) copies it to `/app/solver/reconcile.py` and checks the manifest digest.
6. **Robustness:** 2 Opus runs, both at 71.65 with an identical pass/fail pattern, so the observed spread is 0. The score is bimodal on one yes/no: the drawn filter in the S5 denominator decides 23.15 combined points (or 27.78 together with M2). An Opus run that gets M1 right lands at about 95.4 (M2 still wrong) to 99.4 (M2 right too). Estimate: P(M1 wrong) is high (2/2 runs), so the expected score is about 72 with occasional runs near 95-99. M2 alone moves 0 points unless M1 is fixed.

## Phase 6: what we take from it

| Design choice | Evidence (file:line, points) | Kit check that allows it | Our v3 templates | Verdict |
|---|---|---|---|---|
| One multiplicative factor whose wrong reading scales absolute totals but leaves ratios intact | s5:3-7; M1 = 25 test points over 12 tests; CIs/stream/rollup still pass | DS-21 (02:70 "Default to pass"); TS-26 not-a-duplicate clause; CL-4 not_required "weight distribution by itself is fine" | `P2_build_v3.md:41` demands one reading (IN-16); a scale lever with a fully stated denominator is allowed | **adapt**: keep the scale lever but state the denominator; add a test that pins the absolute total |
| Byte-exact whole-document tests on the single shipped dataset | test_output.py:49-268, 653-677; 100% of test points | TS-5 (ground truth in tests/); CL-4 exemption when exactness is stated (instruction:15-17 names the contract) | `P2_build_v3.md:80-82` requires hidden reseeded inputs and shipped-only <= 5% | **avoid** as-is (one bug zeroes 12 docs; the CL-4 risk is noted at LEVER_COMPAT:30). Keep G1 cascades on hidden inputs. |
| Decimal half-even on a chained recurrence with real ties in the data | rounding_and_precision.yml:2-3; 3 tie rows; M2 seen in 1 of 2 runs | LEVER_COMPAT:21/24 (L7 rounding, computation trap LEGAL) | Not named in the P2 lever menu | **adopt** |
| Final-answer criterion "name the settling file for every stage" | judge R5; lost on 2/2 runs (score.json #5) | JD-7/JD-15 (true of any correct solution) | `P2_build_v3.md:91` J1-J5 have no exhaustive per-item disclosure criterion | **adopt** (a reliable non-100 rubric) |
| Process-restating judge rubric (18 of 27 criteria, R6-R23, restate test-graded methods) | 87/88 on both runs | JD-8 should catch the overlap (it did not here) | `P2_build_v3.md:92` "reads nothing a test reads" (JD-8) | **avoid** |
| Agent-visible trap list, decoy flags, "differs from the obvious" | known_traps_and_footguns.md; sheet_selection_rule.yaml:3-4; instruction:3 | No kit check fired (precheck.sh:43 grep misses it); AL-9 does not cover it | `_COMMON_RULES_v3.md:27-28` forbid it | **avoid** (ours is stricter; the low score happened despite the hints, not because of them) |
| Small corpus (about 5.5k lines) with xlsx and PDF constants | Opus still lost; binary values read correctly at steps 8-10 | DS-21 | `P2_build_v3.md:70` requires 20k lines | **adapt** (volume did not drive difficulty) |
| Negative test for internal contradictions | test_output.py:602-650, -3, never fired | AL-28 | `P2_build_v3.md:85` forbids it | **avoid** |

**Template edits (proposals only; none made):**
1. `P2_build_v3.md:91`: add J6, "one w1 final-answer criterion that requires a per-item enumeration (each stage or lever names its settling file)". Evidence: R5 row, lost on 2/2 runs.
2. `P2_build_v3.md:41` (lever design): add "prefer at least one lever that is a multiplicative factor (a denominator or partition) whose wrong reading leaves ratio outputs intact but moves absolute totals; state the denominator's population in one clause (IN-16) and grade one absolute total per downstream document." Evidence: M1, 25 points; scale-invariant tests passed.
3. `P2_build_v3.md:82` (G3): add "a whole-document test on hidden inputs must not be the only check of a scale-type lever; pair it with one isolated absolute-total check (G2), so that one wrong factor cannot zero more than 50% of the test channel (CL-4, LEVER_COMPAT:30)." Evidence: one mistake took 25 of 54 points across 12 tests.
4. `P2_build_v3.md` lever menu (near :49): add L7-style lever "exact-decimal recurrence with half-even ties planted (at least 3 rows land exactly on a 5 at dp+1)". Evidence: M2 rows 0.143210375, 0.431007625, 0.412560075.
5. `master_chat_tasks/tools/precheck.sh:43` (playbook leak audit): make the grep case-insensitive with `traps?|decoys?|footguns?|superseded|do not use`, and also grep `ls -R environment` file names. Evidence: 1.3 items missed by the current grep.
6. `_COMMON_RULES_v3.md:55` / `knowledge/KNOWLEDGE.md:8`: add the arithmetic note "with 0.5/0.5 channels, overall < 70 needs tests < 140 − rubric; with a judge near 99, tests must be ≤ 40." Evidence: 44.44 + 98.86 gave 71.65.

Earlier peer mining: none listed, so there is nothing to agree or disagree with.
