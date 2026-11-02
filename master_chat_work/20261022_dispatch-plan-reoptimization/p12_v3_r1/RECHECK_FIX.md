# RECHECK_FIX 77e8554: dispatch-plan-reoptimization (P12 v3 r1, QC v6 board 2966bb2)

Session 24 Oct 2026, 12:03 to 12:40 IST. Bundle tree at issue `d2abee833b88` (matched). Kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e; GEN and QC fingerprints re-hashed, 0 mismatches. Lock `/tmp/opencode-logs/locks/dispatch-plan-reoptimization.lock` held for every bundle edit. Phase 0: xref_check `32 entries, 0 findings` before any change.

Counts: REAL 10, FALSE_POSITIVE 0, UNSURE 0. Fixed 10, kept 0, paused none.

## Findings

Levers: L1 = LV-DPR-01 tie, L2 = LV-DPR-02 fallback, L3 = LV-DPR-03 amendment, L4 = LV-DPR-04 rejection/void.

| ID | Label | Rule quote (live kit) | Evidence quote (bundle before) | Decision | Playbook row | Effect L1 / L2 / L3 / L4 | Files changed |
|---|---|---|---|---|---|---|---|
| F1 DS-22 | REAL | 02_Data_Solution_QC.md:78 "TRUTH.md describes the shipped solution, the real grading and a defect list the bundle honours" | solution/TRUTH.md:217 "Channel B holds ten judge criteria" (lists R1 to R10; R11 w5 and R12 w3 missing); :225 "Positive judge weight is 21" | FIX: Channel B paragraph rewritten to "Channel B holds twelve judge criteria", each criterion with weight as it stands after this round; "Positive judge weight is 19 and absolute negative weight is 11"; check count 35, judge denominator 19; hashes and line counts recomputed last | QC_FIX_PLAYBOOK_v2 DS-22 DO "Rewrite TRUTH.md to the shipped code and data" | none / none / none / none | solution/TRUTH.md |
| F2 TS-16 | REAL | 03_Tests_QC.md:47 "Anti-cheat negatives must fire on the cheat and ONLY on the cheat. Ask for each: could an honest solution trip this?" | test_output.py:17775 `cmd = [_sys.executable, str(wrapper), ...]` run as nobody; audit hook records every O_CREAT open outside the output dir, so `import statistics` writes `/usr/local/lib/python3.12/__pycache__/*.pyc.<n>` and fires `negative_writes_outside_output_dir` (QC probe 0.9703) | FIX option (b): grader runs the solver with `python -B` (`cmd = [_sys.executable, "-B", str(wrapper), ...]`). Chosen over (a) because it adds no path exemption (no write path is ever ignored, so the negative is not widened or opened to a cheat that names its file `.pyc`), and over (c) because it does not depend on the image's stdlib set or a build step | TS-16 DO "Narrow the trigger to the cheat only" | none / none / none / none | tests/test_output.py (via WORK/build/mktests.py) |
| F3 JD-8 | REAL | 04_Judge_QC.md:77 "NO OVERLAP WITH TESTS. Discriminator: name the observable each side reads." | judge.toml:147 R11 "...counts a row as out of scope only after that row has passed the unknown_item, retired_item and sentinel rejection checks" and :162 R12 "...writes the rejected_rows figure ... from the same list of rows it writes to rejected_records.csv": both are figures the hidden checks grade byte for byte (QC oos-first mutant moves data_quality 1835/1002 to 1863/974) | FIX (Ayush option a): R11 "The agent's solver.py applies every rejection reason before it decides that a row is out of scope." (w3, code order in solver.py); R12 "The agent checks, before finalising, how its solver.py classifies at least one demand row of a retired item whose effective_seq is above the cutoff." (w3, agent behavior, trajectory). Each carries `# instruction.md:1` and `# environment/data/handbook_ops_v9.md:329-339` / `:80-82` comments | JD-8 + JD-5 DO; side effects JD-2, JD-7, JD-9, JD-15, IN-8 rechecked | none / none / none / harder (judge column) | tests/judge.toml, tests/reward.toml, solution/TRUTH.md |
| M1 TS-15 | REAL | 03_Tests_QC.md:46 "Each negative check should carry an inline comment stating the inversion." | test_output.py:18246-18248 `negative_reads_outside_input_dir` had no comment (other negatives had it) | FIX: added `# True means the cheat happened; the negative weight applies.` | TS-15 DO add comment | none / none / none / none | tests/test_output.py |
| M2 JD-7 | REAL | 04_Judge_QC.md:76 "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle in solution/." (R9: "free of dead code") | solution/solve.py:703 `ctx.out_of_scope += 1` and :706 `ctx.void_rows += 1`, both overwritten by audit_pass :506-507 | FIX: both statements deleted. Old and new solve.py run on shipped data and H1 to H4 corpora: `diff -r proof_old proof_new` empty, 21 artifacts per set byte identical | JD-7 DO "Fix the oracle (and TRUTH.md)" | none / none / none / none | solution/solve.py, WORK/build/oracle.py |
| M3 JD-13 | REAL | 04_Judge_QC.md:90 "critically_important requires 3 or 5; important requires 1 or 3" with semantic magnitudes | judge.toml R11 w5 critically_important for one sweep-order fact | FIX: settled by F3, R11 now w3 important | JD-13 via F3 | none / none / none / none | tests/judge.toml |
| M4 JD-5 | REAL | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour ... If a judge would need to check two separate things, split it." | judge.toml:132 R10 "The agent looks up an online solution, write-up or answer key for this task. The lookup retrieves task-specific material; ordinary model API traffic is allowed." (two sentences) | FIX: one sentence "The agent looks up a task-specific online solution, write-up or answer key (ordinary model API traffic is exempt)." Same id, name, weight -3, type | JD-5 DO one act | none / none / none / none | tests/judge.toml |
| W1 DS-20 | REAL | 02_Data_Solution_QC.md:68 "oracle obeys every contract rule, wherever stated, including rules no test triggers" | solve.py:21 `SENTINELS = {"", "NA", "-", "null", "n/a", "TBD"}` while handbook_ops_v9.md:54 "The sentinel tokens are listed in the nomenclature contract." | FIX: new `sentinel_tokens(ctx)` reads `sentinel_tokens` from the manifest role `contract_nomenclature` (nomenclature.yml); `load()` fills SENTINELS. Loaded set equals old set; outputs byte identical (same proof as M2) | DS-20 DO "Fix the oracle" | none / none / none / none | solution/solve.py, WORK/build/oracle.py |
| W2 TS-14 | REAL | 03_Tests_QC.md:45 "names state properties (<property> / negative_<cheat>), prefix iff negative weight" | test_output.py:18019 `all_artifacts_exist` grades exact values of 21 artifacts, not existence | FIX: renamed `shipped_artifacts_match_contract` in test, registration, `__main__` prefix list, TRUTH.md, XREF, QC_DEFENCE (no test_weights.json in this bundle; weights are the `criteria.<name>(weight=N)` registrations) | TS-14 DO rename to property | none / none / none / none | tests/test_output.py, solution/TRUTH.md |
| W3 TS-23 | REAL | 03_Tests_QC.md:62 "at least 10 checks (fail), at most 35 (warn)" | 36 registrations (tests_qc A3) | FIX: `negative_hardcoded_sample_answers` (-5) and `negative_embedded_visible_records` (-5) merged into `negative_shipped_results_baked_into_solver` (-5): fires after a clean H1 run when the corrected shipped total or the shipped identifiers are executable constants. 35 checks; positive stays 101; negative 25 to 20 | TS-23 (see Deviations) | none / none / none / none | tests/test_output.py, solution/TRUTH.md |

Noise check (Always 13): bundle equals the v6 copy 2966bb2; against the v4 copy 3a23fca only tests/judge.toml differs. M2 and W1 lines and the TS-15/TS-14/TS-23/JD-5 lines did not change since v4. M2 and W1 are provable defects (dead stores overwritten at :506-507; set hard-coded against handbook :54), so they are detection variance on a real defect, fixed, not NOISE keeps. TS-15, TS-14, TS-23 and JD-5 repeat from v4 unchanged and are real.

## R11 / R12 paper scores

New judge positive 19 (R1 5, R2 to R5 1 each, R6 1, R9 3, R11 3, R12 3); negatives R7 -5, R8 -3, R10 -3.

| Run | R11 | R12 | Rubric | Tests | Overall |
|---|---|---|---|---|---|
| a2 (traj_a2 Run 1) | FAIL: solver.py:1280-1293 `def sweep(self):` ... `if self.above_cutoff(rec): self.out_of_scope_rows += 1; continue` runs before `reason = None` and the unknown_item / retired_item / sentinel tests at :1294-1302 | FAIL: trajectory checks only aggregates: step 37 prints `{'out_of_scope_rows': 1863, 'rejected_rows': 974, ...}` and `Counter({'sentinel': 797, 'retired_item': 123, 'unknown_item': 54})`; step 55 cross-check repeats the same cutoff-first order; no step looks at one retired-item demand row above the cutoff | 10/19 = 52.63 (R1, R2 to R5, R6 pass; R9, R11, R12 fail, as R9 failed in judge_a2) | 67.33 | 59.98 |
| Reference (oracle way of working, trap fixed) | PASS: solve.py audit_pass applies unknown_item, retired_item, sentinel and `continue`s before the `effective_seq > cutoff` count | PASS: TRUTH.md Ordered plan step 8 checks one K07 or K19 retired-item row above cutoff 8140 is in rejected_records.csv as `retired_item` and outside `out_of_scope_rows` (28 such rows exist) | 16/19 = 84.21 (R9 fails as in the cc4bb7f reference case) | 100 | 92.11 |

Targets: a2 rubric 52.63 <= 66.67 and a2 overall 59.98 < 70 (10.02 to spare); reference overall 92.11 >= 85. First try, inside {1, 3, 5}.

## Gate results

Docker block 12:19 to 12:23 IST, one nohup chain (`/tmp/opencode-logs/dpr-v3r1-20261024T121915-f88f/chain.sh`, runs.log ends ALL_DONE), copies built by live kit `exe_copy.py` at `/tmp/dpr-v3r1-20261024T121915-f88f` (plain, `--owner-only`, `--stub`). Verifier image warmed first (WARM rc=0).

| Run | Reward | Detail |
|---|---|---|
| oracle x3 (plain) | 1.0, 1.0, 1.0 | 35 criteria, 101/101, no negative |
| owner-only oracle x1 | 1.0 | |
| nop x1 | 0.0 | |
| stub x1 | 0.0 | 0/101 positive points (share of P 0.00), 29 positives failed, no negative |
| honest stdlib TS-16 program, BEFORE tests (no `-B`) | 0.9703 | 98/101, `negative_writes_outside_output_dir` fired (QC finding reproduced) |
| honest stdlib TS-16 program, AFTER tests (`-B`) | 1.0 | 101/101, no negative fired |

TS-16 cheat side (local scorer, after tests): `ts16_cheat_tmp.py` writing `/tmp/x.txt` still fires `negative_writes_outside_output_dir` (-3, 0.9703).

Static gates: `PRECHECK CLEAN` (tests 35, judge criteria 12); xref_check `35 entries, 0 findings`; STACKING PASS (tool output corrected by hand in OUT/STACKING_CHECK.md: tool counted structure as isolated and said "J2 conduct criteria: none"; conduct criterion is R12). Generator diff before rebuild: mktests.py output equalled bundle test_output.py byte for byte (Always 11); bundle tests regenerated from edited source. Final tree sha `cc3a0ebba1cb`.

## Deviations from master directions

- W3: playbook TS-23 DO says merge w1 format or presence checks first. The only non-hidden positive is `shipped_artifacts_match_contract` (w1); every other positive is a hidden_h1..h4 check the master forbids merging and that carries the a2 loss. The two static baked-answer negatives were merged instead: same -5 on every program (the old embedded check already stood down when the hardcoded check fired), no trap variant fires either, so trap value is unchanged.
- M4 / F3 wording: the master's R10 text "does not count" failed precheck J10 (negative-grammar token "not") and the R12 text "Before finalising, the agent..." failed J9 (trajectory criterion must start with "The agent"). Shipped: R10 "...(ordinary model API traffic is exempt)." and R12 "The agent checks, before finalising, how its solver.py classifies at least one demand row of a retired item whose effective_seq is above the cutoff." Meaning unchanged.
- F3 R12 type: agent behavior, trajectory (it is conduct). The oracle's way of working shows it through TRUTH.md Ordered plan step 8 (JD-7, JD-15).

## Side effects

Rechecked per Always 14 and FIX_SIDE_EFFECTS.md; 0 new findings.

| Fixed ID | Side-effect id | Kit line | Result |
|---|---|---|---|
| TS-16 | TS-14, TS-15 | 03_Tests_QC.md:45, :46 | names unchanged for writes negative; comment present on all 6 negatives |
| TS-23 | TS-13, TS-26, TS-25 | 03_Tests_QC.md:44, :53, :52 | merged negative grades one property (shipped-set answers carried as constants); incumbent negative stands down when it fires (one act costs at most 5); no new positive absence check |
| JD-5 / JD-8 | JD-2, JD-7, JD-9, JD-15, IN-8, JD-16 | 04_Judge_QC.md:68, :76, :86, :92; 01_Instruction_QC.md:38; 04_Judge_QC.md:93 | positive grammar passes J10; oracle meets R11 in code and R12 in TRUTH step 8; R11 reads solver.py code order, R12 reads trajectory, tests read output figures; R12 labelled agent behavior; R11 knowable from handbook :329-339 and :80-82; R10 cites instruction.md:15 |
| TS-13 hygiene | TS-25, TS-15 | 03_Tests_QC.md:52, :46 | as above |
| DS-22 (common) | DS-22 | 02_Data_Solution_QC.md:78 | TRUTH.md rewritten last; solve.py and test_output.py hashes recomputed; precheck CLEAN; xref `35 entries, 0 findings` |

## Noise keeps

none

## Trap survival

Local scorer (tests channel, tests-only), earned points of P = 101. Before = WORK/trap/before_v3 tests; after = bundle tests.

| Variant | Before loss of P | After loss of P | Ratio | Separating cases kept | Verdict |
|---|---|---|---|---|---|
| agent_v0 (reflex) | 85/101 = 84.16% | 85/101 = 84.16% | 1.00 | y | PASS |
| m_fallback (L2) | 70/101 = 69.31% | 70/101 = 69.31% | 1.00 | y | PASS |
| m_tie (L1) | 70/101 = 69.31% | 70/101 = 69.31% | 1.00 | y | PASS |
| m_amend (L3) | 69/101 = 68.32% | 69/101 = 68.32% | 1.00 | y | PASS |
| m_rejnorm (L4) | 33/101 = 32.67% | 33/101 = 32.67% | 1.00 | y | PASS |
| m_voidlog (L4) | 13/101 = 12.87% | 13/101 = 12.87% | 1.00 | y | PASS |
| a2 solver (score share) | 68/101 = 0.6733 | 68/101 = 0.6733 | 1.00 | y | PASS (<= before + 0.02) |
| oracle | 0 | 0 | n/a | n/a | PASS |
| ts16_honest (stdlib statistics, pprint) | n/a | 0 (no negative) | n/a | n/a | PASS |
| ts16_cheat_tmp (writes /tmp/x.txt) | n/a | -3 `negative_writes_outside_output_dir` fired (0.9703) | n/a | n/a | PASS |

Trap survival PASS. No hidden case was removed; hidden_h1..h4 (the 32 points a2 lost) and `shipped_artifacts_match_contract` (the 1 point a2 lost) are kept.

## QC_RULINGS rows

- 77e8554 | dispatch-plan-reoptimization | TS-16 | Bytecode cache writes under the stdlib tree tripped the writes-outside negative; fixed by running the solver with `python -B`, no path exemption added.
- 77e8554 | dispatch-plan-reoptimization | TS-23 | When every positive except one w1 is a lever hidden check, merge two static anti-cheat negatives of equal weight that can only fire together-or-alternatively, rather than any lever check.
- 77e8554 | dispatch-plan-reoptimization | JD-8 | A criterion that names a sweep order is still a figure criterion if a hidden check fails the same mutant; rewrite to code order (solver.py) or a trajectory act.

## Lessons for the master

- Master wording for judge criteria can fail judge_qc grammar (J10 'not', J9 trajectory must open with 'The agent') | template_change: P12 template F3 wording block: run judge_qc on suggested wording before issuing
- TS-23 playbook DO assumes a w1 non-lever pair exists; here every positive but one is a lever hidden check | template_change: QC_FIX_PLAYBOOK_v2.md TS-23 row: allow merging equal-weight static anti-cheat negatives when no w1 pair exists
- Honest-solver probes for audit-hook negatives need root plus python:3.12-slim; a non-root host cannot reproduce pycache writes | template_change: _COMMON_RULES_v3.md Always 12 TS-16 line: name a Docker probe as the proof channel
- Bundle has no tests/test_weights.json; weights live in criteria registrations | no change: prompt already lets the agent follow the bundle's real layout
