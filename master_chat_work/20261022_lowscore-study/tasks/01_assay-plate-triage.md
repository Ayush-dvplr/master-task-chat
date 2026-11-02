# 01_assay-plate-triage: low-score study report

Paths used: `T/` = `master_chat_work/20261022_lowscore-study/tasks_copy_20261022T0105/01_assay-plate-triage/`; `R/` = `T/trajectories/claude-opus-5/run_1/`. Score: overall 5.51 %, tests 3.33 %, rubric 7.69 % (`T/trajectories/claude-opus-5/pass_summary.json`). No runs were made; everything below is from the saved files. Anything not read from a file is marked UNVERIFIED.

## 1. Shape

- Instruction `T/instruction.md`: 34 lines, 728 words. Deliverable: one program `/app/out/triage.py` (`T/task.toml:2`), takes input dir and output dir, writes `readings.jsonl`, `plates.json`, `bench.json` (`instruction.md:15`). Also ten named whole numbers in the final message (`:17-30`).
- Timeouts: agent 5400 s (`task.toml:35`), verifier 3600 s (`:22`); cpus 2, 4096 MB (`:42-43`). Expert estimate 240 min (`:16`).
- Data (`T/environment/data/`, 32 files): 2 docs (`engine.md` 109 lines, `reports.md` 96 lines); four runs under prefixes: unprefixed graded run (143 reads, 37 plates, manifest digests only), `trial_` (153 reads, 40 plates, digests only), `example_a_`, `example_b_` (mode 0, with the three engine output files each, 162 reads in a). CSV and JSONL, all small (largest file 22 KB).
- Tests `T/tests/test_output.py` (1250 lines): 33 checks = 30 positive (15 at weight 1, 15 at weight 5, total 90) + 3 negative (-5, -3, -3; total -11) (`test_output.py:1218-1250`). The file holds the whole reference engine (`resolve`, `:197-370`) and a seeded corpus generator (`write_case`, `:731-782`); corpora are rebuilt in the verifier, `/app/data` is never read.
- Judge `T/tests/judge.toml`: 15 criteria, positives 39 (R1 w1, R2 3, R3 3, R4 1, R5 5, R6 1, R7 1, R8 5, R9 5, R10 3, R11 5, R12 3, R15 3), negatives -8 (R13 -5, R14 -3). Channels weighted 0.5/90 and 0.5/39 (`T/tests/reward.toml:4`).
- Artifact collected: only `/app/out/triage.py` (`task.toml:2`). Separate verifier image with util-linux (setpriv) and rewardkit 0.2.1 (`T/tests/Dockerfile:2-6`).
- Run: 42 trajectory steps, agent 17:37:57 to 18:27:21 (49.4 min of 90), 724k prompt tokens (`R/result.json`, `R/agent/trajectory.json`).

## 2. Is the low score genuine? (static screen)

ctrf: 33 tests, 6 passed, 27 failed (`R/verifier/ctrf.json`). weighted_percentage 3.3333 = 3/90, so the 3 negative checks (listed "passed") applied no penalty.

a. Classification (deciding lines in `test_output.py`):
- READ: `reusable_program_is_delivered` (`:957-967`, reads source and `ast.parse`), `negative_hardcoded_sample_answers` (`:1157-1170`), `negative_third_party_dependency` (`:1173-1192`).
- EXEC (every other check; all go `_resolves` -> `_matches` -> `_run` -> `_launch` -> `subprocess.Popen(_demoted([sys.executable, SCRIPT, data, out]))`, `:797-803, 942-947, 903-923, 886-893`): the two base checks, 12 single-bit, 6 all-but-one, 9 full-mode checks, and `negative_nondeterministic_output` (`:1195-1215`).

b. EXEC checks that passed: `untrapped_run_alpha_resolves` and `untrapped_run_beta_resolves` (`:970-979`; ctrf: passed, weight 1 each). `_demoted` runs the program as `setpriv --reuid=nobody --regid=nogroup --clear-groups` when root (`:860-863`) and the check compares all three report files byte for byte (`:942-947`). So the verifier DID run the agent's program as the dropped uid and it produced exact output: the permission trap did not hit the program.

c. (Not needed since b holds.) For completeness the tests also add read bits: `_grant_read(SCRIPT)` and `_grant_read(OUT_DIR)` (`:907-909`, `:853-857`), temp dirs 0777 and data 0644 (`:917-920`).

d. Other grade breakers: none found. Corpora are regenerated from seeds (`:731-782`), so no hardcoded `/app/data` paths; per-run budget 240 s (`:876`) against a tiny program (verifier total about 35 s, `R/result.json` verifier 18:27:25 to 18:28:00); only stdlib needed. The agent did not touch `/tests` or `/app/data` (my grep over its tool-call arguments: 0 hits for `/tests` and `/logs/verifier`; writes only in `/app/work`, `/app/out/data_report`) and has no `PLT-` literals in `R/artifacts/app/out/triage.py` (0 matches). The master's claim "file modes were lost" does not matter here (EXEC checks passed).

Label: GENUINE - two EXEC checks passed under the setpriv drop, and the 27 failures are exactly the checks that need the twelve undocumented mode bits, which the agent's own final message says it did not recover.

Master review (22 Oct 01:42 IST), design cap found while verifying task 06: the same bit-position identifiability gap as task 06 applies here. The only mode words that ship are 0 (`example_a_manifest.json:3`, `example_b_manifest.json:3`) and 4095 = 0xfff (`manifest.json:3`, `trial_manifest.json:3`); `engine.md:37-41` says each bit acts independently and "Nothing in this directory says which bit is which". So any permutation of the 12 alterations over the 12 positions gives identical output at both shipped mode words, yet the 12 `mode_bit_*` checks (weight 1 each) and the 6 `every_bit_except_*` checks (weight 5 each) run single-flag or all-but-one corpora keyed on fixed positions (`tests/test_output.py:15-26`, `MODE_BITS` :819-831, :985 onward). That is 42/90 = 46.7 % of test weight that a perfect solver of the alteration set reaches only by guessing the order; reachable by reasoning: 3 + 45 = 48/90 = 53 %. `instruction.md:7` "decidable one plate at a time rather than a guess" is true for alterations and false for positions. This did not change this run's score (the agent recovered 0 of 12 bits, so the 9 full-mode checks failed too). Label stays GENUINE for this run, with DESIGN CAP noted; no Phase B run can test it (it is a property of the shipped data, argued logically, not observed in a run).

## 3. Instruction anatomy

- Story first (`instruction.md:1`), then what survives and what the notes give: "They give none of the numbers, and they do not say what any bit of the run's mode word does." (`:3`).
- The target run has mode `0xfff`; "Those digests are how a reading of the mode word is settled: resolve the run under a candidate reading, digest the result, and compare... A wrong reading of any bit moves at least one plate digest across the two runs, so the search is decidable one plate at a time rather than a guess." (`:7`). That is a method hint (for a search), not the answer.
- Deliverable is fully pinned: exact path, two CLI args, three file names, byte form in `reports.md:24-25, 56-57`, determinism ("Running it twice over the same input directory must write byte identical files", `:15`), stdlib only, "keep precomputed answers out of the program" (`:15`). It also says the program "will be driven over runs you have never seen, at mode words you have never seen" (`:15`).
- Closing report: ten named whole numbers, each with an exact definition (`:17-30`).
- Time advice: "A partial engine that is written down and reported on is worth more than a perfect one that never gets written" (`:32`).
- Where rules live: stage order and status ladder in `engine.md:63-96`; byte forms and digest definitions in `reports.md:7-96`; constants and bit meanings nowhere (`engine.md:40-41`: "Nothing in this directory says which bit is which").
- Shape: goal/end state plus an evidence channel; no procedure for the chain. Tone: neutral narrative, 728 words.
- Versus ours (`bundles/*/instruction.md`, 350-571 words): ours say where the rules are and that the job is to apply them ("The container format has fifteen rules you must work out and apply; they are all stated in those files", vendor-archive line 3; "Treat schema.md as the authority on every rule", district-heat line 1). Ours also pin report shape by pointing at a shape file. This task is equally precise about the deliverable and output bytes, but withholds both the constants and the 12 behaviours; the agent must infer rules, not read them. It is not an "over-specified" instruction: the specificity is in the output contract, not in the rules. Evidence for the operator's hypothesis here: weak/against (specific about outputs, silent about rules).

## 4. Every failed positive check and every fired negative

ctrf: 33 tests, 27 failed positives, 0 fired negatives; all covered below.

Common mechanism for all 27: the delivered program implements only the mode-zero chain. `ALTERATIONS = [_unidentified] * 12` (`R/artifacts/app/out/triage.py:89`) and `_unidentified` returns `cfg` unchanged (`:75-86`). Every corpus with a nonzero mode word therefore differs from the reference in at least one byte. Cause class for all: hidden-input generalisation failed, because the rules were never recovered (class "other: rule discovery abandoned"; the agent decided to stop at trajectory step 37). Nothing in the docs states any of these rules (`engine.md:34-41`); the reference rule lines below are in the test file the agent could not see. Hardcoding was not involved.

| Check (weight) | Rule (reference, `test_output.py`) | What the agent did (step) |
|---|---|---|
| mode_bit_chain_blank (1) | `:224-225` blank starts at previous plate's blank on same instrument | no code; probe at mode zero (step 17-18) matched 0/37 plates |
| mode_bit_drift_echo (1) | `:285-289` charge lands one read late | no code |
| mode_bit_role_lookback (1) | `:240-241` tolerance of previous read's operator | no code |
| mode_bit_band_tier_shift (1) | `:245` band edges + 15*tier | no code (its own PLT-29 grid, steps 19-23, did not find it) |
| mode_bit_exposure_floor (1) | `:208-213, 243-244` divide by plate's minimum exposure | no code |
| mode_bit_panel_parity (1) | `:182-185` odd replicates -> no adjustment | no code |
| mode_bit_baseline_delta (1) | `:159-169` last instrument stores delta baseline | no code |
| mode_bit_exposure_order (1) | `:188-194` order by (exposure, seq) | no code |
| mode_bit_mask_absolves (1) | `:278-279` a mask removes a strike (plates.json only) | no code |
| mode_bit_count_bias (1) | `:190-191` drop last 1 + plate_count % 4 reads | no code; `declared_reads` equals line count (reads.jsonl 143 lines) |
| mode_bit_matrix_alias (1) | `:172-179` alias index + tier + operator_count | no code |
| mode_bit_quarantine_span (1) | `:322-323` quarantine adds previous plate's strikes (plates.json only) | no code |
| every_bit_except_{chain_blank, role_lookback, exposure_floor, baseline_delta, mask_absolves, matrix_alias} (5 each) | mask `ALL_FLAGS & ~bit` (`:1054-1087`): need the other 11 bits right | fail; agent has 0 of 12 |
| full_mode_run_alpha..theta (5 each, 8 checks) | all 12 bits (`:1090-1135`) | fail |
| full_mode_run_with_a_grown_operator_table (5) | all 12 bits with operators > 5 so the alias reads the operator count (`:1138-1154`) | fail |

Trajectory facts: probe with the mode-zero config matched 0 of 37 graded and 0 of 40 trial plate digests (step 18); four brute-force searches on single plates PLT-29, PLT-17 (twice), PLT-35 found nothing (steps 19-23, 26-28, 30-32, 35-36); step 34 noticed 35 of 37 shared plates have different digests in the two runs though their reads are identical, i.e. cross-plate coupling, but no hypothesis was built from it; step 37 "Decision: stop the bit search". UNVERIFIED: whether hypothesis-driven attempts per bit would have succeeded in the roughly 40 min left (agent ended at 49 of 90 min).

Passed checks a lazy agent would also pass: `reusable_program_is_delivered`, `untrapped_run_alpha_resolves`, `untrapped_run_beta_resolves` (3/90, the "trap-blind ceiling", `solution/TRUTH.md:122-123`). The three negatives did not fire (no third-party import, no plate literals, deterministic).

## 5. Levers

Weight share = points lost / 90 positive test weight (judge shares of 39 given in step 6). Levers overlap (one failed check sits under several).

| Lever | Family | Share lost | Triggered |
|---|---|---|---|
| 12 undocumented mode-word alterations found only through plate digests at one fixed point (all bits set) | NEW (rule discovery by hash oracle; includes A-style hidden composition) | 87/90 = 96.7 % | yes |
| Conjunction ladder: 12 single bits (1 each), 6 all-but-one (5 each), 9 full-mode (5 each) | D + E (stacked constraints) | 12 + 30 + 45 = 87 of 90; 75/90 = 83.3 % sit on checks needing 11 or 12 bits at once | yes |
| Stateful cross-plate or cross-record bits (chain_blank, drift_echo, role_lookback, exposure_order, quarantine_span) | B dependent chain | single checks 5/90 = 5.6 % (more through the conjunctions) | yes |
| Bits visible only in plates.json (mask_absolves, quarantine_span) | NEW (hidden output channel) | 2/90 = 2.2 % single, plus conjunctions | yes |
| Size-dependent bits (count_bias via plate count, matrix_alias via operator count) and the grown-operator corpus | D size ladder | 7/90 = 7.8 % | yes |
| Ten closing figures measured at 0xfff, in no file | E (derived from all bits) | 32/39 = 82.1 % of judge weight (R2-R11) | yes |

No family F (rejection paths) lever; C (audit/repair) absent.

## 6. Judge

From `R/verifier/score.json`: 15 criteria, rubric 7.69 % = 3/39.
- R1 names all ten figures (w1): failed. Judge: figures are labelled mode-zero, not figures "for the unprefixed shipped run at 0xfff".
- R2 trace_rejects 14 (3): agent 12, failed. R3 technician_reviews 17 (3): agent 37, failed. R4 off_role_reviews 5 (1): 11, failed. R5 hold_plates 23 (5): 30, failed. R6 saturated_reads 4 (1): 6, failed. R7 thin_matrix_total 2036 (1): 1880, failed. R8 rich_matrix_total 3104 (5): 3370, failed. R9 assay_family_total 4969 (5): 3666, failed. R10 high_reads 75 (3): 71, failed. R11 blank_end_total 4120 (5): 3490, failed.
- R12 recomputes manifest digests from its own resolution (3): PASSED (the only rubric points; probe.py steps 17-18).
- R13 edits `/app/data` (-5) and R14 opens `/tests` or `/logs/verifier` (-3): listed `passed: true`, yet rubric = 3/39, so no penalty was applied; meaning of "passed" on a negative: UNVERIFIED (arithmetic implies "no violation"), and my trajectory grep confirms no violation.
- R15 clean delivered code (3): failed. Judge cites unused constants, twelve no-op alterations, `_unidentified` scaffolding. This penalises a consequence of the same failure (non-recovery), a partial double count.
Design: the figures exist in no shipped file (`solution/TRUTH.md:90-91`), so copying docs earns nothing; the test channel never grades the figures (`TRUTH.md:141-143`). Overlap in cause, not in fact. R12 and R15 are conduct criteria; R12 pays for the attempt.

## 7. How it passes QC and still beats the agent

- Documented, so not hidden: stage order (`engine.md:63-96`), byte forms (`reports.md:24-25, 56-57`), digest definition (`reports.md:79-92`), the fact that there are 12 bits each altering reads, carries, walked reads or rollup (`engine.md:34-38`), and that the mode-zero examples pin the plain chain (`instruction.md:5`).
- Withheld: the constants (fittable from the examples) and the twelve meanings. Live QC allows withholding if the shipped data lets a solver test a guess (IN-9, `Input_Bundle_QC/01_Instruction_QC.md:39`; DS-21 asks whether an expert could reach the graded answer, `02_Data_Solution_QC.md:70`). Here the digest oracle (37 + 40 plate digests, 2 run digests) is the solvability argument.
- What makes it hard anyway: the oracle exists only at 0xfff, so a guess for one bit shows only through plates untouched by the other eleven; the agent's argument at step 37 (no gradient) shows how that reads in practice. The author's expected path is a bit-by-bit climb on matching plate digests (`TRUTH.md:175-179`); UNVERIFIED that this path works for a model.
- Easy to miss: bits visible only in `plates.json` (`TRUTH.md:40-42`), `declared_reads` as a false consistency field (`TRUTH.md:34-36`), bits interacting through carried state (`TRUTH.md:43-45`).
- Anti-cheat: negative checks for literal plate ids (>= 5 of the shipped ids as string constants, `test_output.py:1157-1170`), third-party imports (`:1173-1192`), nondeterminism (`:1195-1215`); seeds-based corpora; reference engine only in `tests/`; ten figures only in `judge.toml`; judge negatives for editing `/app/data` and opening `/tests`.
- Standard weight set {5,3,1,-1,-3,-5} and negatives <= positives are respected (`Final_checklist.md:201, 204`).

## 8. Trajectory story

42 steps, 49 min of 90.
- Steps 3-4 read `engine.md` and `reports.md` in full; steps 5-8 per-plate dumps of example_a; step 9 (think) derived the whole mode-zero chain; step 10 wrote `triage.py` at about 6 min in (following `instruction.md:32`); steps 11-12 `verify.py`: both examples byte-identical.
- Steps 13-16 inspected the graded and trial inputs; step 17-18 digest probe: 0 matches.
- Steps 19-36: four brute-force searches on single "immune" plates (PLT-29, PLT-17, PLT-17 again with free drift start, PLT-35), all 0 hits or no output; step 24 compared digests across the two 0xfff runs; step 34 inferred cross-plate coupling.
- Step 37 decided to stop; steps 38-41 cleaned the code, rechecked determinism and ran a synthetic unseen run; step 42 final message.
- Docs never opened: none relevant. It never built candidate readings for the bits named in `engine.md:34-37` one at a time (UNVERIFIED if that would have worked).
- Self-test: verify against both example outputs, determinism diff, synthetic run. Final message is honest about the bits ("This part of the task is unfinished") and about the figures being mode-zero, but closes with "generalizes to unseen plates, instruments, operators and mode words" (step 42), which the 27 failed checks contradict at the byte level (mild overclaim).

## 9. Reusable patterns / things to avoid

- A digest oracle with documented construction lets withheld rules be tested, but if the oracle is available at only one fully-stacked point, a conjunction of unknowns gives the agent almost no gradient (96.7 % of test weight sat behind it).
- A 1/5/5 weight ladder makes the score near-binary: the cheap single-bit checks are 12/90, the checks needing 11 or 12 correct bits are 75/90.
- Cross-run oracle (`trial_` with different instrument, operator and plate counts) is a good way to make size-dependent rules decidable.
- Hidden output-channel rules (plates.json only) and a false consistency field (`declared_reads`) are good, cheap traps.
- Judge figures that exist in no file are robust against copying; a conduct criterion (R12) pays for the attempt.
- Avoid: a judge criterion that double-penalises the same failure (R15 on dead no-op code) and the instruction sentence "decidable one plate at a time" if the oracle is joint; it reads as a promise the agent could not use.

```json
[
  {"task":"01_assay-plate-triage","name":"undocumented_12_bit_mode_word_via_digest_oracle","family":"NEW","mechanism":"Twelve independent alterations to reads, carried state, walk order and rollups are named nowhere; only plate and run digests at the all-bits-set mode word say whether a reading is right","where_documented":"engine.md:34-41 (existence only), instruction.md:7 (digest method); meanings only in tests/test_output.py:172-323","weight_share":0.967,"triggered":true,"cause_of_failure":"hidden-input generalisation failed: rules never recovered, search abandoned at step 37","evidence":"ALTERATIONS = [_unidentified] * 12 (artifacts/app/out/triage.py:89); 87 of 90 test points lost; step 18 probe 0/37 plate digests"},
  {"task":"01_assay-plate-triage","name":"conjunction_weight_ladder_1_5_5","family":"E","mechanism":"12 single-bit checks weight 1, 6 all-but-one weight 5, 9 full-mode weight 5: any wrong bit breaks byte equality","where_documented":"tests/test_output.py:1218-1247 (not agent visible)","weight_share":0.833,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"all 6 all-but-one and all 9 full-mode checks failed in ctrf.json (75/90 weight)"},
  {"task":"01_assay-plate-triage","name":"stateful_cross_plate_carry_bits","family":"B","mechanism":"chain_blank, drift_echo, role_lookback, exposure_order, quarantine_span need the run walked in resolution order with per-instrument or previous-read carry","where_documented":"not in agent-visible docs; engine.md:55-61 gives only per-plate state","weight_share":0.056,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"step 34: 35 of 37 shared plates have different digests across graded and trial runs with identical reads; no hypothesis built"},
  {"task":"01_assay-plate-triage","name":"rollup_only_bits","family":"NEW","mechanism":"mask_absolves and quarantine_span change plates.json but not readings.jsonl, so a readings-only check calls them free","where_documented":"not documented; solution/TRUTH.md:40-42","weight_share":0.022,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"mode_bit_mask_absolves and mode_bit_quarantine_span failed (ctrf.json)"},
  {"task":"01_assay-plate-triage","name":"corpus_size_dependent_bits","family":"D","mechanism":"count_bias drops 1 + plate_count % 4 reads; matrix_alias uses operator_count; a grown-operator corpus tests it","where_documented":"not documented; test_output.py:172-179, 190-191, 1138-1154","weight_share":0.078,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"mode_bit_count_bias, mode_bit_matrix_alias, full_mode_run_with_a_grown_operator_table failed"},
  {"task":"01_assay-plate-triage","name":"ten_figures_at_all_bits_set","family":"E","mechanism":"Ten closing figures exist in no file and depend on every bit being right; graded one by one by the judge","where_documented":"instruction.md:17-30 (definitions); values only in tests/judge.toml","weight_share":0.821,"triggered":true,"cause_of_failure":"hidden-input generalisation failed; agent reported mode-zero figures","evidence":"score.json R2-R11 all false (12/37/11/30/6/1880/3370/3666/71/3490 vs 14/17/5/23/4/2036/3104/4969/75/4120); share is of judge weight 39"}
]
```
