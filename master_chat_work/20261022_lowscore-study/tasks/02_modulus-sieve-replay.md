# 02_modulus-sieve-replay: low-score study report

Paths: `T/` = `master_chat_work/20261022_lowscore-study/tasks_copy_20261022T0105/02_modulus-sieve-replay/`; `R/` = `T/trajectories/claude-opus-5/run_1/`. Score: overall 5.9 %, tests 6.25 % (6/96), rubric 5.56 % (4/72) (`T/trajectories/claude-opus-5/pass_summary.json`). No runs; everything is from saved files. Guesses are marked UNVERIFIED.

## 1. Shape

- Instruction `T/instruction.md`: 51 lines, 989 words. One artifact: `/app/out/sieve.py` (`T/task.toml:2`), run as `sieve.py INPUT_DIR OUTPUT_DIR`, writes `residues.jsonl`, `lanes.json`, `forms.csv`, `sieve.json` (`instruction.md:15`). Final message must also state 20 whole-number figures (`:19-47`).
- Timeouts: agent 7200 s, verifier 2700 s (`T/task.toml` [agent], [verifier]); cpus 2, 4096 MB. Expert estimate 480 min.
- Data (14 files, `T/environment/data/`): 2 docs (`engine.md` 191 lines, `reports.md` 109 lines); the recorded pass (3 moduli, 8 forms, 5 analysts, 92 lanes, 410 samples) with only two rollups surviving (`ref_forms.csv` 7 rows, `ref_sieve.json` one object); a second "carry" pass (98 lanes, 826 samples, five `carry_*` files) with no outcome at all.
- Tests `T/tests/test_output.py` (1784 lines): 35 checks = 32 positive (3 at weight 1, 26 at 3, 3 at 5 = 96) + 3 negative (-5, -3, -3) (`test_output.py:1750-1784`). Contains the reference mill (`resolve`, `:217-430`) and seeded generators (`build_probe`, `build_unseen`, `:980-1200`).
- Judge `T/tests/judge.toml`: 29 criteria, positives 72 (#1-6 w1; #7-14 w5; #15-20 w3; #21-26 w1; #28, #29 w1), negative -5 (#27). Channels weighted 0.5/96 and 0.5/72 (`T/tests/reward.toml`).
- Run: 45 steps, agent 08:20:44 to 09:52:51 (92 min of 120), 783k prompt tokens (`R/result.json`, `R/agent/trajectory.json`).

## 2. Is the low score genuine? (static screen)

ctrf: 35 tests, 7 passed (4 positive + 3 negative), 28 failed. Positive passes: `program_writes_the_four_reports` (1), `report_serialization_carries_the_documented_byte_form` (1), `empty_pass_reports_are_written` (1), `form_rows_carry_the_documented_order` (3) = 6/96 = 6.25 %. So the 3 negatives applied no penalty.

a. Classification: READ = `_hardcoded` (`:1527-1535`) and `_third_party` (`:1538-1554`), i.e. the two negatives for hardcoding and imports. EXEC = every other check: `_run` (`:1373-1391`) calls `_launch` -> `subprocess.Popen(_demoted(argv))` (`:1303-1327`), and `_demoted` prepends `setpriv --reuid=nobody --regid=nogroup --clear-groups` when root (`:1287-1290`). `negative_nondeterministic_output` is EXEC too (`:1557-1568`).

b. EXEC checks that passed: `empty_pass_reports_are_written` (`_same_reports(..., "empty", ...)`, `:1581-1583`, requires exit code 0 and byte equal reports, `:1406-1410`), `program_writes_the_four_reports` (`:1472-1487`, needs exit 0 and the documented keys on an unseen pass), `report_serialization_carries_the_documented_byte_form` (`:1490-1507`) and `form_rows_carry_the_documented_order` (`:1510-1515`, probe pass). All ran `sieve.py` as `nobody` and read its output, so the permission trap did not hit the program.

c. (not needed) The tests also grant read: `_grant_read` on workspace, `/app/out` (0o055 for dirs) and the script (0o044) (`:1279-1286, 1385-1386`); temp dirs 0777, data files 0644 (`:1361-1364`).

d. Other grade breakers: none. Passes are regenerated from seeds in the verifier (`:1330-1365`), so no `/app/data` path is read; budget 300 s (`:1303`) against a program that ran in seconds (verifier 09:52:59 to 09:53:49, `R/result.json`). The agent never referenced `/tests` or `/logs/verifier` and never wrote under `/app/data` (my grep over its tool-call arguments; one regex hit at step 44 is a write under `/app/work/empty`, not `/app/data`). No `LAN-` literal in `R/artifacts/app/out/sieve.py` (0 matches).

Label: GENUINE - four EXEC checks passed under the setpriv drop; the 28 failures are wrong constants (step 4).

## 3. Instruction anatomy

- Narrative first (`instruction.md:1`), then what the notes give and withhold: "What they do not give, apart from three figures `engine.md` says survived on a whiteboard, is any of the numbers." (`:3`).
- Evidence statement is candid: "Nothing survives at the level of one lane or one sample, so a wrong constant shows up only as a wrong figure on one of a handful of form rows or in the one whole pass rollup... Readings that reproduce both rollups and are still wrong exist, so treat agreement there as a floor rather than a proof. No lane sits on more than one of the three plain keyed values at once either, so no lane isolates one adjustment." (`:5`).
- Deliverable is exact (path, args, four files, byte form) (`:9-15`).
- A full method paragraph (`:17`): "Set a block of the recorded pass aside while you work the constants out, then replay that held back block", "build a small input of your own on which they disagree and run both over it", "Where two lanes share two keyed columns and differ on the third, use that pair to narrow the adjustment", "Work at least one figure out a second time through a calculation separate from the program you deliver", "compare both of your own rollups against the shipped reference files byte for byte". Then 20 named figures (`:19-47`) and time advice: "Give the hard part at most half your working time" (`:49`).
- Where rules live: stage order and carried state `engine.md:70-165`; the list of missing constants `engine.md:167-186`; three whiteboard facts `engine.md:188-191`; byte forms `reports.md:9-109`.
- Shape: end state plus a stated working method. Versus ours (350-571 words; no method paragraph; rules named as living in `schema.md`, `format_contract.md`, `repository_contract.md`): this instruction is MORE procedural about how to work than ours, and also more candid about the evidence limits. It still withholds every number. Evidence for the operator's "too precise" hypothesis from this task: against it. A precise method paragraph did not help (R1, R2, R5 failed); the rules were what was missing, not the procedure.

## 4. Every failed positive check and every fired negative

ctrf: 35 tests, 28 failed positives, 0 fired negatives; all covered below.

Reference constants are in the test file (not visible to the agent); the agent's are in `R/artifacts/app/out/sieve.py` (`PARAMS`, `:322-337`; offset `:64-89`). Shared core errors that feed every weight probe: modulus offset reference `entry["offset"] + 1` (`test_output.py:245`) vs agent 242 (`sieve.py:64-89`, from a wrong inference that the `family` label says whether `offset + d` is prime, composite or a prime power, see trajectory step 11 think); gain reference 900 (`:259`) vs agent 1000 (`sieve.py:324`); block factor 4 (`:97`) vs 3 (`sieve.py:323`); fallback count 1 (`:253`) vs 500 (`sieve.py:324`). Cause class for all rows below: "hidden-input generalisation failed" (constants fitted to 7 rows and 1 object are wrong), with "two rules combined wrongly" where noted. None is "never read the doc"; the agent read both notes (steps 4-5). Specific wrong values are verified by reading code against the rule; why the search settled on them is UNVERIFIED.

| Check (w) | Rule (reference line) | Agent (sieve.py line) |
|---|---|---|
| normalisation_gain (3) | gain 900 (`:259`), modulus +1 (`:245`) | 1000, 242 (`:324`, derive) |
| governing_count_columns (3) | blocks*4 when blocks>0 (`:97`), (terms+1) (`:100`) | block factor 3 (`:323`) |
| least_absolute_residue (3) | `_least_residue` (`:103-107`) | rule right (`:156-159`), modulus wrong |
| sector upper / lower / split / folded / shifted / wrapped (6 x 3) | -9 (`:112`), *3//5 (`:114`), +14 (`:116`), -(f%11) (`:118`), *7//4 (`:120`), //3 (`:122`) | additive constants 260, -139, 121, -261, 481, -201 (`:325-326`), applied as `x + adj` (`:161`) |
| kind_adjustment_cubic (3) | +21 (`:130`) | -6 (`:327`) |
| kind_adjustments_quadratic_and_linear (3) | *9//7 (`:128`), *4//3 (`:132`) | +84, +64 (`:327`) |
| charged_kind_follows_the_parent_form (3) | parent's kind (`:87-92`) | right (`sieve.py:118, 162, 330`), but core wrong |
| window_adjustments_dusk_and_night (3) | dusk *5//8, night +13 (`:138-140`), skipped on first sample (`:271`) | dusk -40, night 0 (`:328`); skip right (`:164`) |
| family_adjustment_prime / power (2 x 3) | prime *8//5, power -17 (`:146-148`) | 0, 0 (`:329`) |
| faulted_lane_is_charged_at_the_promoted_family (3) | prime from 3 faults (`:243-244`) | 'power' (`:330`) |
| repeated_tag_reuses_the_recorded_weight (3) | record of 4 (`:334`) | record_size 1 (`:334`) |
| abandoned_sample_arms_a_doubled_drift_relief (3) | void arms the relief (`:321-322`) | arm_action right (`:332`); drift values wrong |
| absent_count_columns_inherit_the_previous_count (3) | fallback 1 (`:252-253`) | 500 (`:324`) |
| drift_step_carries_the_common_divisor (3) | `gcd % 11` (`:205`), remainder `% 10` (`:326`) | gcd_mod 11 right, rem_mod 5 (`:335`) |
| drift_step_by_depth (3) | depth 3 doubles, depth 2 +7, back to back +5, ceiling 130 (`:201-207, 327`) | '2' doubles, '3' +19, back to back 7, ceiling 180 (`:334-336`) |
| credit_release_drawdown (3) | release min(credit, 16) (`:211-214`) | credit_release 0 (`:330`) |
| band_edges (3) | 400/180/60 (`:153-158`) | 504/240/6 (`:331`) |
| grade_tolerances (3) | 58/37/19/0 (`:164-169`) | 40/16/40/2 (`:333`) |
| lane_verdicts_and_counted_totals (3) | counted = kept + flagged (`:341`) | ('kept',) (`:337`) |
| residue_ledger / lane_rollup / pass_rollups on unseen passes (3 x 5) | all ten generated passes byte for byte | any wrong constant fails |

Trajectory evidence: the final reading is the step-24 fit (best sieve.json counts, `R/agent/trajectory.json` step 24), restored at step 41; later fits (steps 36, 40) were worse (fit 279 and 511). Final diff (step 43): `sieve.json` off by one on `base`, `idle`, `weight_total`; every `weight_total` in `forms.csv` wrong (e.g. FRM-L1 16736 vs 18299). UNVERIFIED: whether an additive-free model class would have fitted; the agent never tried multiplicative or floor forms (its search space is signed additive offsets, trajectory step 16).

Decisions the agent got right (match the reference): bookkeeping pair seed and close (`:173`), void abandons (`:175`), arm by void (`:322`), floor from seed (`:313`), bank by close (`:316-319`), credit ceiling 80 (`:318`), seal at 3 (`:243, 357`), held above 51 (`:359`), gcd modulus 11 (`:205`), terms offset 1 (`:100`), least-absolute reduction, parent kind, form order (`:394-395`), top_tag lowest seq (`:353-354`). These are the rules derivable from counts or documented; they earned only the form-order check.

Passed checks a lazy agent would also pass: the three format checks and `form_rows_carry_the_documented_order` (the 7 reference rows are strictly descending in `weight_total`, so the rule is visible in `ref_forms.csv`). No negative fired.

## 5. Levers

Weight share = points lost / 96 (judge shares of 72 in step 6). Overlapping.

| Lever | Family | Share | Triggered |
|---|---|---|---|
| About 52 undocumented numeric constants fitted from 7 form rows + 1 sieve object (aggregate-only evidence) | NEW (aggregate evidence destroys locality) | 90/96 = 93.8 % | yes |
| Confounded keyed axes: no lane on more than one plain value (`engine.md:63-68`) | E stacked / NEW | 36/96 = 37.5 % (sector 6, kind 3, window 1, family 2 probes + parent probe) | yes |
| Shared core (gain 900, block factor 4, offset +1) that every probe passes through | B dependent chain | about 93/96 (26 probes + 3 unseen); TRUTH.md:214-216 puts a wrong core at 0.03-0.28 | yes |
| Adjustment functional form unstated (multiplicative, floor, modular rather than additive constants) | NEW | 36/96 direct | yes |
| Stateful drift/credit/record/fault subsystem | B | 6 probes = 18/96 = 18.8 % | yes |
| Bands, tolerances, counted set | E | 9/96 = 9.4 % | yes |
| Invented constraint (family labels read as number-theoretic properties of the modulus) | NEW (label vocabulary decoy, not necessarily authored; UNVERIFIED author intent) | part of the core lever | yes |
| Unseen-pass byte checks | D (generalisation) | 15/96 = 15.6 % | yes |
| 17 carry figures answerable only by correct constants | E/NEW | 64/72 = 88.9 % of judge weight (#7-26) | yes |

No family F or C.

## 6. Judge

From `R/verifier/score.json`: rubric 4/72 = 5.56 %.
- #1 held-back block replay (w1): failed. The agent held out form rows (FRM-L2/FRM-Q2, later FRM-M1), not samples, and never replayed a held-back block and confirmed.
- #2 rival-reading input (w1): failed; only an empty-pass test input.
- #3 second calculation of one figure (w1): PASSED (the modulus offset, itself wrong).
- #4 byte comparison of both rollups (w1): PASSED (step 43).
- #5 narrow an adjustment from a lane pair (w1): failed; pairs listed, never used.
- #6 run over a carry directory (w1): PASSED.
- #7-#23 carry figures (w5 x8, w3 x6, w1 x3): all failed, e.g. carry_total_weight 301329 vs 311196, carry_cleared_weight 125203 vs 211340, carry_refused_weight 13 vs 994.
- #24-#26 recorded-pass figures (w1): failed (setup 9939 vs 8907; voided 4639 vs 4555; folded 5468 vs 8211).
- #27 (-5) editing `/app/data`: listed passed true, no penalty (arithmetic 4/72); the agent did not touch it. Semantics UNVERIFIED.
- #28 stages split across named functions (w1): failed (`resolve()` holds all stages, `sieve.py:123-233`).
- #29 constants declared once at module level (w1): PASSED (`PARAMS`, `:322-337`).
Design: no figure is in any file (`solution/TRUTH.md:145-149`); 17 of 20 are about the carry pass, which has no outcome to fit, so they are answerable only by right constants. The six trajectory criteria quote sentences of `instruction.md:17` (`TRUTH.md:198-203`), satisfying the IN-15 requirement that graded conduct rules are stated. The channels grade disjoint surfaces (`TRUTH.md:207-208`).

## 7. How it passes QC and still beats the agent

- Fully documented, so not hidden: stage order and carried state (`engine.md:70-165`), the list of missing constants (`engine.md:167-186`), three constants given outright (`:188-191`), byte forms (`reports.md`). The instruction states the evidence limits (`:5`).
- Gate 01 IN-14 forbids handing over the method; "rules of engagement" and partial direction are allowed (`Input_Bundle_QC/01_Instruction_QC.md:44`). The method paragraph (`:17`) is conduct wording and is graded by six trajectory criteria, which IN-15 requires to be stated (`:45`).
- Solvability argument (DS-21, `02_Data_Solution_QC.md:70`): the author says 50 of the 52 missing constants are pinned to one reading by the rollups (`TRUTH.md:23-26`). For a model this is a 52-dimensional fit to about 50 numbers with an unstated function family, so it holds only for an expert willing to enumerate readings; UNVERIFIED that it is practical.
- Easy to miss: the offset is "one fixed whole number offset applied" (`engine.md:32-34`) and nothing links it to `family`; adjustments are not stated as additive; counted statuses include `flagged`; record size 4.
- Anti-cheat: negatives for 5+ recorded lane ids as literals (`test_output.py:1527-1535`), third-party imports (`:1538-1554`), nondeterminism (`:1557-1568`); seeded probes; copying the shipped rollups earns only the format checks (`TRUTH.md:322-324`).

## 8. Trajectory story

45 steps, 92 min of 120.
- Steps 3-7 read the data and both notes in full.
- Steps 8-12: step 9 (think) correctly derived the action roles from `by_status` (setup 25 = seed 14 + close 11; voided 11 = void), the inert values (plain, mixed, composite) and the form order. Step 11 (think) invented the family-label constraint on the modulus offset.
- Steps 13-17: wrote a parameterised mill (additive adjustment dictionaries), put a first `/app/out/sieve.py` in place at 08:33 (12 min), ran a 11-minute coordinate descent (fit 125 with no sealed lane, inadmissible).
- Steps 18-24: added constraints (seal at 3 from the sealed lanes' opening rows), 16-minute runs; step 24 best reading (all `by_status` counts and the sealed set right).
- Steps 25-40: small-form analysis (step 26) and exact solve (step 37) exposed a contradiction (edge_base 440-601 vs 6) that was never resolved; two more search rounds (steps 36, 40) were worse.
- Step 41 reverted `sieve.py` to the step-24 reading; steps 42-44 computed figures, determinism, empty pass and carry run; step 45 final.
- Fitting ran 08:34 to 09:49 (75 min), against the instruction's "at most half your working time" (60 min). It did not build the held-back sample block, the discriminating input or the lane-pair isolation (judge #1, #2, #5).
- Final message: honest about being partial and lists the wrong areas, but files the modulus offset d=242 under "firmly established" (reference is +1), a false claim.

## 9. Reusable patterns / things to avoid

- A tiny aggregate outcome (7 rows + 1 object) against dozens of unknown constants is a strong, honest lever, and the instruction admits it.
- Qualitative decisions (roles, seal counts, form order) are derivable from counts and the agent found them, but the probe design makes the numeric core a single point of failure: one wrong core constant fails all 26 probes. Good for hardness, poor for partial credit.
- Whiteboard facts for constants no rollup shows are a fair, cheap hint.
- A carry pass with no outcome and figures in the judge only makes 17 judge points depend on already-correct constants.
- Avoid: grading conduct (held-back block, rival input) that the evidence shape makes impossible (aggregate-only references have no per-sample block to replay).
- Avoid: an unstated function family (additive vs multiplicative) combined with a fit-only discovery path; a model with an additive search space can never reach it.

```json
[
  {"task":"02_modulus-sieve-replay","name":"aggregate_only_evidence_for_52_constants","family":"NEW","mechanism":"About 52 numeric mill constants must be fitted to 7 form rows and one sieve object; nothing survives per sample or per lane","where_documented":"engine.md:50-55, 167-186; instruction.md:5","weight_share":0.938,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"28 of 32 positive checks failed; final sieve.json off by one on three fields, forms.csv weight_total wrong on all seven rows (step 43)"},
  {"task":"02_modulus-sieve-replay","name":"confounded_keyed_axes","family":"E","mechanism":"No lane carries more than one plain keyed value, so sector, kind and family adjustments cannot be read off one lane","where_documented":"engine.md:63-68","weight_share":0.375,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"sector x6, kind x3, window, family x2 probes all failed; agent's additive values 260/-139/121/-261/481/-201 vs reference -9, *3//5, +14, -(f%11), *7//4, //3"},
  {"task":"02_modulus-sieve-replay","name":"shared_core_single_point_of_failure","family":"B","mechanism":"Gain, block factor and modulus offset feed every probe; one wrong core constant fails all weight probes","where_documented":"engine.md:93-111 (stages), constants undocumented; solution/TRUTH.md:214-216","weight_share":0.97,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"gain 1000 vs 900, block factor 3 vs 4, offset 242 vs +1 (sieve.py:323-324, 64-89 vs test_output.py:97, 245, 259)"},
  {"task":"02_modulus-sieve-replay","name":"unstated_adjustment_function_family","family":"NEW","mechanism":"Adjustments are multiplicative, floor or modular but the notes say only 'adjustment'; an additive-constant model cannot represent them","where_documented":"engine.md:112-127 (stages 6-9)","weight_share":0.375,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"sieve.py:161-167 x + P[adj]; reference test_output.py:110-149"},
  {"task":"02_modulus-sieve-replay","name":"stateful_drift_credit_record_subsystem","family":"B","mechanism":"Drift per sieve from divisor count, depth rules, gcd and discarded remainder; credit release; trailing tag record; promoted family at 3 faults","where_documented":"engine.md:125-165 (structure only)","weight_share":0.188,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"record_size 1 vs 4, credit_release 0 vs 16, ceiling 180 vs 130, back_to_back 7 vs 5, rem_mod 5 vs 10 (sieve.py:330-336)"},
  {"task":"02_modulus-sieve-replay","name":"label_vocabulary_decoy_for_modulus_offset","family":"NEW","mechanism":"The family column (composite, prime, power) invites reading the modulus as a number of that kind; the agent derived offset 242 that way and presented it as firmly established","where_documented":"engine.md:32-34 says only 'one fixed whole number offset'","weight_share":0.5,"triggered":true,"cause_of_failure":"other: invented constraint, then shortcut as a verified figure","evidence":"trajectory step 11 think, sieve.py:64-89; reference offset +1 at test_output.py:245. Author intent as a decoy UNVERIFIED; weight share is the fraction of probes the offset reaches (approximate)"},
  {"task":"02_modulus-sieve-replay","name":"seventeen_carry_figures_without_outcome","family":"E","mechanism":"Seventeen judge figures are measured over a pass with no surviving rollup, so only correct constants produce them","where_documented":"instruction.md:7, 27-47; solution/TRUTH.md:145-149","weight_share":0.889,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"score.json #7-#26 all failed; share is of judge weight 72"}
]
```
