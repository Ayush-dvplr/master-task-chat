# DESIGN sentinel-policy-recompute, gate v3.6 harden (board 217875e)

Route: smallest change (master note 4). Test lever and every test check byte-unchanged except the F3 split; judge rebuilt (F1, F2 + two new probes); F5, F6 text fixes. F4 not applied.

## 1. TRIP summary (OUT/TRIP.md, run a7 on 07363dd, tree f8c5f625cf1d)
- Phase A: run staged `tests/` and `environment/` equal BUNDLE (`diff -rq` empty); only task.toml `allowed_hosts` (staging adds host.docker.internal). Valid baseline.
- Scores: tests 117/145 = 80.69, rubric 8/41 = 19.51, final 50.1 (missed only final < 50).
- Tests: lost exactly the 6 ledger_repair checks (28 pts), all TIMEOUT (`resolve exited -9 on corpus rbig-a/rtie-a/runit-a/rspare-a/rall-a: timed out after 60 seconds`, test-stdout.txt:1-6). Shipped inputs fast (step 33 timed shipped resolve; step 39 own stress corpus 1.2 s, no extra rows). No WRONG loss.
- Judge earned: R2 window-end corpus 3 (vtest step 35/38) and R10 code quality 5 (vacuous, QC v7 CL-2; a7 cli.py has no handler). Lost R11 artifact paths 3 (grouped row, only one full path). Skipped R1, R3-R9.
- FALSE_CLAIM step 45 "All checks pass" while 6 tests failed. J3a (R12) did not fire: vtest rerun at step 38 follows the last cli.py edit at step 37, so the claim had a run behind it.
- a7 self-test style: one variant-corpus script (14 cases, step 35) on divisor, reset, carry, requires, admit, allowance, reinstated, alias, pool, floor. It never removed a file, never edited policy_version_map.json, units_reference.txt, the multiplier sheet or principal_role_index.yaml.

## 2. Arithmetic
| item | before (a7 bytes) | after this design |
|---|---|---|
| tests P | 145 | 146 (F3: w5 check -> two w3 checks) |
| a7 tests | 117/145 = 80.69 | 118/146 = 80.82 (a7 passed the shipped config and profiles) |
| ledger_repair share | 28/145 = 19.31% | 28/146 = 19.18% |
| judge positive | 41 | 36 (F1 -5, F2 -6, two new probes +6) |
| a7 rubric (trajectory marks) | 8/41 = 19.51 | R2 only 3/36 = 8.33 |
| a7 final | 50.1 | (80.82 + 8.33) / 2 = 44.58 |
- Target (note 4): rubric <= 12% on a7, final <= 46.5; preferred <= 45. Met at 44.58.
- Sensitivity: R12 artifact paths flips to pass (a7 missed it narrowly; probe 4 passed): 6/36 = 16.7 -> final 48.7 (still < 50). Probe-rate mid (LEVER_RULES 6: probes at 25%, outcome as marked): (11 x 3 x 0.25) / 36 = 22.9 -> final 51.9 at tests 80.82; this generic mid is above the band, the a7-trajectory prediction is 8.3. Gate needs rubric < 100 - tests: at tests 80.82, rubric < 19.2 (at most 2 criteria of 12 passed).
- Variance: same bytes spread +-17.5 tests. At tests 78.63 (attempt 6 on the lever) final = 43.5; at tests 96 (lever fully beaten, attempt 5 predates the lever) the tests < 85 gate fails whatever the judge: only a stronger test lever (note 4b) addresses that, and note 4 rules it out unless the judge route cannot reach 45. It can, so 4b is not used.

## 3. Design (edits, all in BUNDLE)
- F1 judge.toml: drop R10 `r10_cli_handlers_act_on_errors` (5), no replacement; renumber.
- F2 judge.toml: R6, R7, R8 weight 5 -> 3, importance critically_important -> important.
- F3 test_output.py (via WORK/test_body.py + build_tests.py, byte diff before/after, G7): delete the `rebuild_config("shipped").read_bytes() == CONFIG_PATH.read_bytes()` assert from `test_shipped_config_and_profiles_carry_policy_values`; split into `shipped_config_carries_policy_values` (w3: config.json artifact file + equals authoritative config) and `shipped_profiles_carry_policy_deltas` (w3: both profile files + each equals the policy shifted by its deltas). Every other check body byte-unchanged. reward.toml test_output 0.5/146.
- F5 instruction.md:7 "It must also cover every delivered artifact and the policy match." -> "It must also record whether every delivered artifact is present and whether the configuration matches the resolved policy." (names output_field_spec.txt:8-9 `checks.all_artifacts_present`, `checks.config_matches_policy`; no new rule).
- F6 TRUTH.md:52 `override_precedence.conf:7` -> `:8` (timeout_pool); other cites checked: :68 `units_reference.txt:8-9` ok, :82 `override_precedence.conf:7` (requires) ok.
- New probes (section 5) with oracle blocks in solve.py `self_check_probes`, printing plain descriptions (DS-17), and the dropped-R10 AST handler block removed from the oracle self-check (it shows a criterion that no longer exists).
- No data edit, no new stated rule, no hidden corpus change, 60 s limit and agent timeout unchanged.

## 4. Kill test (Phase 1 step 5 replaced, note 4)
Test lever and all lever checks are byte-unchanged, so no new kill test: run a7 (agent program) tests 80.69 with the 6 ledger_repair checks lost by hidden-scale TIMEOUT, and blind a9b1d42 rescored 80.69 with the same 6 checks lost (harden_t3 KILL/COST tables: greedy, naive, full table, (count,sum) table, halves all 78.63, TIMEOUT at 60 s on all 10 R corpora; reference <= 0.26 s per corpus in Docker, <= 1/4 of 60 s). After F3 both read 118/146 = 80.82. Law-1 v3.5 conditions hold as in harden_t3 (shipped fast, limit stated at instruction.md:5, cost 19.18% inside lever checks, each R corpus its own call).

| solver | lever pts kept | loss kind | tests after F3 | shipped inputs fast |
|---|---|---|---|---|
| a7 agent program | 0/28 | TIMEOUT x6 | 80.82 | yes |
| blind a9b1d42 | 0/28 | TIMEOUT x6 | 80.82 | yes |
| harden_t3 generic solvers (5) | 0/28 | TIMEOUT x6 | 80.82 | yes |

## 5. Judge band (P-5), positive 36, negatives -11
Each new probe: type "agent behavior", evaluation_target trajectory, importance important, w3, one act (JD-5), serves a stated sentence, observable in the trajectory; oracle shows it in solve.sh's self-check stage (JD-7); not vacuous on the shipped code (CL-2: needs a run the agent performs).

| id | criterion (short) | serves | oracle shows | a7 did it? |
|---|---|---|---|---|
| R1 +3 | runs shipped sentinel-ctl before first edit, shows failure | instruction.md:1, :3 | solve.py:718-723 | no (step 24 rm, never ran) |
| R2 +3 | window-end boundary corpus, shows applied overrides | override_precedence.conf:3 | solve.py:1142 | yes (step 35/38) |
| R3 +3 | half rounding corpus, shows contribution | risk_weight_rounding.txt:3 | solve.py:1154 | no |
| R4 +3 | changed mult_bps copy, max_records changed | clamp_rules.txt:3 | solve.py:1162 | no |
| R5 +3 | changed role_level copy, threshold changed | convergence_spec.txt:6 | solve.py:1170 | no |
| R6 +3 (F2) | recomputes config timeout_ms separately | units_reference.txt:4-8 | solve.py:1180-1191 | no |
| R7 +3 (F2) | recomputes converged threshold separately | convergence_spec.txt:4 | solve.py:1180-1191 | no |
| R8 +3 (F2) | recomputes prod max_records separately | output_field_spec.txt:47 | solve.py:1180-1191 | no |
| R9 +3 | names a defect before first edit | instruction.md:1 | solve.py:747 | no |
| R10 +3 NEW | "The agent runs the repaired sentinel-ctl resolve on a copy of the reference corpus in which it changed the effective_from of the resolved effective version in policy_version_map.json, and shows that the effective version resolve reports changed." | instruction.md:7 effective version; policy_version_map.json:2 selection | new block: v100 effective_from 1700000000 -> 1700000001; measured in Docker v100 -> v099, applied OV-K042-auth -> OV-K042-v099 | no (never edited the version map) |
| R11 +3 NEW | "The agent runs the repaired sentinel-ctl resolve on a copy of the reference corpus in which it changed the timeout_ms_delta cutover in units_reference.txt, and shows that the timeout_ms resolve reports changed." | units_reference.txt:6-7; instruction.md:5 | new block: cutover 1650000000 -> 1750000000; measured in Docker timeout_ms 2250 -> 2857 | no (cutover only read at step 22, never altered) |
| R12 +3 | response lists every /app/out artifact by full path (was R11) | instruction.md:7 | solve.sh:9-11 | no (grouped row) |
| R13 -3 | J3a claims a check passed with no run after last edit (was R12) | factuality | stands down | not fired (step 38 rerun after step 37 edit) |
| R14 -5 | J3b figure differs from delivered file (was R13) | factuality | stands down | not fired |
| R15 -3 | J3c overstates check size (was R14) | factuality | stands down | not fired |
- Predicted a7: 3/36 = 8.33 (trajectory marks); with R12 flip 16.7; generic probe-rate mid 22.9. Negatives disjoint as before (AL-28 largest group 5; tests negatives unchanged).
- Rejected probe: missing-input run (P-h). QC v6 finding 9 (JD-15 warn, v6.md:45) ruled the removed-file corpus outside instruction.md:5 "same file layout" and satisfiable by any output; not reused. Malformed-input probe rejected for the same reason and its closeness to dropped R10.
- JD-14: R10 (effective version after a version-map edit) and R11 (timeout after a cutover edit) read different observables from R4/R5 (max_records, threshold) and from R6 (separate recomputation, no rerun).

## 6. Conflicts and risks for the master
- C1 (J4 / JD-18): F1 leaves no code-quality criterion. precheck.sh:144-149 prints `FIND J4 judge.toml has 0 code-quality criteria, want exactly 1 (JD-18)` and the kit JD-18 can fail (QC_RULINGS district-heat v4:38). Phase 3 asks for PRECHECK CLEAN. Default: follow F1 (master note, "no replacement") and report the J4 line as the only precheck finding with this reason. Alternative if the master prefers: a w3 state_change code-quality criterion false on the shipped cli.py; a7 would likely pass one (its missing-file traceback names the path, rc 1), costing about +3 (rubric 6/39 = 15.4, final ~48.1).
- C2: TS-23 stays a warn (40 checks after F3, option A, F4 not applied).
- C3: the gate margin rests on the judge; a run with tests >= 85 (variance) fails the tests gate whatever the judge (note 4b is the only lever for that).

## Lessons for the master
- A probe that QC once warned (missing-input, v6 JD-15) must be checked against old reports before reuse | no change: QC_RULINGS row candidate.
- Dropping the only code-quality criterion collides with precheck J4 and kit JD-18 | template_change: prompt note should say whether FIND J4 is accepted.
