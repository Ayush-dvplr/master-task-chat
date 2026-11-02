# Converted v0 read, board a1ab2d0

One real Opus run per task (Run 1). All three job-config.json files stage from the OLD path
`Harbor_Harness/Terminal_2.0_Harbor_Harness/.kiro-staged-tasks/<slug>`, so the master's validity ruling applies.
Loss tables: `loss/<slug>.txt`. Paths below: B = bundle `Tasks_INPUT/<slug>/`, R = `jobs/<slug>/trajectory/claude-opus-5/Run 1/`.

---

## 1. caldermoor-commitment-closure (tests 74.44, rubric 100, reward 0.8722)

### 1.1 Lost items (34 test points, judge lost 0)

All 34 points come from two stated-rule slips. The amplification spreads them across seven tests.

**Lever A: blocked set taken as class BLOCKED.** The agent's `R/artifacts/app/out/reconcile.py:979-999` builds the closure from
`for key in sorted(k for k, v in classes.items() if v == "BLOCKED")`. The oracle `B/solution/solve.py:985-1027` emits a closure row
for every non-circular commitment that has an outgoing live blocking edge, whatever its own state. On the shipped data the agent
writes 232 closure pairs and 156 blocked commitments. The oracle writes 560 and 347, and oracle `audit_totals.csv` still has
`class_blocked,156`. Example: oracle `blocked_commitments.csv` has `CMT-00029,1,1,1,CMT-01125`, and CMT-00029 is WITHDRAWN.
- The spec line that settles it: `environment/data/dependency-semantics.md:50` "A commitment is blocked when at least one live edge leaving it carries a block."
  The same file at :71-74 removes cycle members from the closure deliverables. That exclusion only matters if the blocked set is wider than class BLOCKED.
  `instruction.md:9-10` warns that rules live "in the document that owns the idea".
- Overload: `commitment-protocol.md:164` maps "blocked under dependency-semantics.md -> BLOCKED", and `output-contract.md:160` uses the same word.
- Trajectory: step 27 prints `closure_pairs 232 / blocked_commitments 156 / class_blocked 156`. The agent never questions that the two counts are equal.
- Tests lost:

| test | class | pts |
|---|---|---|
| closure_and_blocked_exact (`tests/test_output.py:3999-4001`) | GENUINE | 5 |
| audit_and_reconciliation_exact (:4067-4069, same two counts) | AMPLIFICATION | 5 |
| validation_report_residuals_zero (:4594-4652, recomputes closure_pairs and blocked_commitments on probe 12) | AMPLIFICATION | 3 |
| unseen_alpha/beta/gamma_full_exact (:4183-4195, byte compare of all artifacts on 3 held-back seeds) | AMPLIFICATION, shared with lever B | 3x5 |

- Overall class: GENUINE, with a mild AMBIGUITY flag because the word "blocked" names both the predicate and the class.

**Lever B: periods_waived counts INERT waivers.** The agent's `reconcile.py:1099-1125` increments the waived count for every period
that holds a waiver, discharged periods included. The oracle `solve.py:1113-1152` counts only the SUPPRESSED branch.
- The spec line that settles it: `cadence-register.md:51-59` "take the first of these that applies" (discharged, waived, otherwise),
  and :63-64 "A period that is both discharged and waived is discharged, the waiver in it is inert."
- Evidence the agent contradicts its own output: its `waiver_trace.jsonl` is byte-identical to the oracle's and marks those waivers INERT.
  Yet its `cadence_debt.csv` breaks elapsed = discharged + waived + debt on 43 of 60 rows. The oracle breaks it on 0 of 60 (python check over both files, scratch/cald).
- Tests lost:

| test | class | pts |
|---|---|---|
| cadence_and_waiver_exact (:4014-4016) | GENUINE | 3 |
| cadence_streak_and_waiver_semantics_exact (:4477-4525, probe 9) | AMPLIFICATION | 3 |
| unseen x3 | shared | see above |

- Overall class: GENUINE. `output-contract.md:137-139` names the column without its own definition, so the walk is the only definition.

**Judge:** 28 criteria, 95 points, all earned, no negative fired (`R/verifier/reward-details.json`). 81 of the 95 points pay for the 12 what-if
figures at w5 (r4-r15) and the units A-G (r16-r22). Opus stated all of them correctly (trajectory step 31, final message step 33).

### 1.2 Run-to-run risk
- Lever A looks **stable**. It is one structural reading built into the closure loop and reinforced by the overloaded class name.
  The agent saw the equal counts (step 27) and accepted them. A second run is likely to repeat it, but a careful reread of dependency-semantics:50 would undo it. Medium-high stability.
- Lever B looks closer to **luck**. The agent applied INERT correctly in waiver_trace and slipped only in the counter.
  A second run could easily count right. If B is fixed, tests = (133-28)/133 = 78.9%. If A is fixed, tests = 112/133 = 84.2%. If both are fixed, tests reach about 100%.

### 1.3 Judge from probe (behaviours Opus skipped)

| id | candidate criterion | w | oracle evidence | Opus miss | kit checks |
|---|---|---|---|---|---|
| C1 | The agent builds its own small extract in which a commitment that is not class BLOCKED (for example WITHDRAWN) holds a live edge to an OPEN blocker, runs the delivered program on it, and checks that commitment's line in blocked_commitments.csv | 3 | none today: `solve.sh` only copies and runs on /app/data. A self-check step must be added to solve.sh (JD-7) | steps 27-32 run only /app/data; step 27 accepts 156 = 156 | JD-7, JD-8 (tests grade the file, the judge grades the act), JD-9, JD-16 |
| C2 | The agent builds an input with a waiver in a discharged period and checks that periods_waived leaves it out while waiver_trace marks it INERT | 3 | same: needs a solve.sh step | never inspects cadence_debt beyond `head` (step 29) | JD-7, JD-8, JD-9 |
| C3 | The agent runs the delivered program on at least one extract other than /app/data and compares its outputs (unseen-input conduct, J2) | 3 | needs a solve.sh step | every run in steps 27, 28 and 32 uses /app/data | JD-7, JD-9 |
| C4 | J3 honesty negative: claims a check passed with no run after the last edit | -3 | the oracle avoids it trivially | would not fire: step 32 reruns after the last edit (step 26) | JD-11, JD-12 |

Keep R1 staging (3), R2 stdlib (3), R26 named functions (3) and R28 dead code (1) as the J4 code-quality slot.
For JD-18, merge R26 and R28 into one concrete criterion. Keep negatives R23, R24 and R25.

### 1.3b Lever check
- **A** (the blocked set's scope): a stated single-reading rule (dependency-semantics:50), habit **H3 denominator scope**.
  Alone it costs 5+5+3+15 = 28/133 = **21.1%**, below the G10 floor of 25%.
- **B** (counting waived periods): a stated single-reading rule (cadence-register:51-64, first that applies), habit **H3/H6**: the waiver is consumed by the earlier discharge branch.
  Alone it costs 3+3+15 = 21/133 = **15.8%**, below the floor. Both together cost 25.6%.
- The other drift rules in TRUTH.md (04:00 day boundary, H4-style unit spelling and hour units, effort clamping, renames, half-open intervals, the second allocation pass) were all passed.
  Evidence: day_boundary_exact, effort_units_and_origins_exact, allocation_remainder_and_floor_exact and project_lineage_exact all show value 1.0 in reward-details.
  No unexploited H1-H6 lever is visible in the shipped data. A new one would need new data (UNVERIFIED that one exists).

### 1.4 Arithmetic and fix list
- Tests held at 74.44, so the rubric must be < 140 - 74.44 = **65.56%**.
- The current judge cannot get there. 81/95 points pay figures and units Opus gets right, and that layout breaks J1 (at most 6 figures, w<=3, printed by solve.py; solve.py prints none: `grep print solve.py` shows only the usage line :1761) and playbook :29.
  Keeping 6 figures at w3 still gives positives of about 37 with Opus at 28, i.e. 75.7%, overall 75.1. That fails.
- **Minimal fix (judge + instruction + solve.sh):**
  1. Cut the 12 figures and units A-G from `instruction.md:86-138` and the judge (playbook :29 says remove the request, because the figures are not graded through a program observable).
  2. Rebuild the judge with these positives: R1 3, R2 3, one J4 code-quality criterion 3, C1 3, C2 3, C3 3, R27-style per-item listing replaced by J6 "final message names each artifact it wrote" 1. That is 19 points.
     Negatives: R23-R25 and C4. Count = 11, which meets JD-12 (>= 8).
  3. Add a self-check stage to `solve.sh`: a constructed mini extract for C1, C2 and C3 with asserts, so JD-7 holds.
  4. Set `reward.toml` judge weight to 0.5/19 (JD-S13, tests_qc:R3).
- Expected Opus result: R1, R2, code quality and listing earned = 10/19 = **52.6%**. Overall = (74.44 + 52.6)/2 = **63.5**.
  If Opus also does one conduct item: 13/19 = 68.4% gives 71.4, a fail. If lever B self-corrects: (78.9 + 52.6)/2 = 65.8, a pass.
  Margin is thin and rests on Opus skipping self-built probes. Opus skipped all three in this run.
- QC cost: AL-2 (instruction promises now graded), AL-18 (stale figure counts removed), IN-8, JD-7, JD-8, JD-9, JD-12, JD-13, JD-16, JD-18, JD-S7, JD-S13, tests_qc:R3. Tests are untouched.
  Optional test-side hardening to meet G10: up-weight closure_and_blocked and cadence_and_waiver. That touches TS-19 and AL-28 and is not required for the gate.

### 1.5 Verdict: **FIX**
One fix round (instruction trim, judge rebuild with C1-C4, solve.sh self-check stage, reward.toml weight) plus one QC. Expected: tests 74, rubric 53, overall 63.5.
Risk: if run 2 fixes both levers, tests reach about 100 and overall rises above 70. G10 is unmet (21.1% / 15.8%).

---

## 2. numeric-reduction-benchmark-forge (tests 98.81, rubric 76, reward 0.874)

### 2.1 Lost and fired items
| item | what the agent did (step) | class | settling line |
|---|---|---|---|
| test bottleneck_analysis_matches_reference -1 (`tests/test_output.py:740-748`, expects `BASELINE_COMPLEXITIES` list :183-184) | agent `optimize.py:320-321` writes `{stage name: complexity}` dicts; oracle `solve.py:244-245` writes lists `[s["complexity"] ...]` | AMBIGUITY | none: `schema.md:147-150` says only "`baseline_complexities`, `optimized_complexities` (from `query_plan.json` stages)", giving no shape |
| judge R5 r5_exercises_top_account_tie_rule +3 lost | step 9 `/tmp/check_trace.py` and step 14 `/tmp/bench.py` compare top_accounts against a sort of the existing data; no tied-total input is built (judge_response) | conduct miss (not a computation) | n/a |
| judge R12 r12_validates_fresh_non_visible_term +3 lost | only the first row of events.csv, checked against schema.md:115-123 worked example | conduct miss | n/a |
| judge R20 r20_compares_timing_spread_across_batches +3 lost | step 15-16 bench reports medians and ratio only | conduct miss | n/a |
| judge R1 r1_imports_third_party_module_in_scratch_script **fired -3** | step 9 `check_trace.py` does `sys.path.insert(0,"/app/out"); import optimize`; same in step 14 bench.py | **ARTEFACT** (criterion text `judge.toml:14` "a module outside the Python standard library" literally covers the agent's own deliverable; the instruction's ban is on "third-party packages") | n/a |

There is no GENUINE computation loss. Every lever test passed: tier, tie-break, nearest-rank, decoys, checksum, hidden seeded report (`R/verifier/reward-details.json`).

### 2.2 Run-to-run risk
- The tests are stable at about 98.8-100. The single lost point is a shape ambiguity, and a second run could guess the list form and score 100.
- The judge losses are conduct gaps, which are luck-dependent. Opus may build a tie input on a rerun.
- R1 fires again whenever the agent imports its own module from a scratch script. That is a habit, so it is likely stable, but it is an ARTEFACT that QC would have to remove (JD-11: negatives must target a real cheat surface).

### 2.3 Judge from probe
Opus missed exactly the three conduct criteria already in the judge (R5, R12, R20). No new behaviour gap was found. Step 19 checks the 21-artifact inventory and permissions. The final message (step 20) lists artifacts, checks and the ratio (R6, R7 and R21 earned). There is no candidate criterion worth adding. The fix would be to reword R1 to "a third-party package (not the standard library and not /app/out/optimize.py)", which *raises* the rubric (79/50 basis to 82%).

### 2.3b Lever check
Levers: decoy keys, tier lookup, checksum term order, tie rule, nearest-rank and float `round`. Each is a stated single-reading rule, and `schema.md:91-99` **prints the concrete graded values** (weights, offsets, penalties, bonuses, divisor, multiplier, top_n). That removes every H1/H4 habit gap. Each lever costs 0% alone (all passed).

H1-H6 support in the shipped data: none. A python scan of all 5 streams finds 0 irregular rows (ids `[a-z]\d+`, accounts `A\d{3}`, integer amount/units/latency, 5 regions, 4 flags). Reserved alias rows A090-A239 in account_tiers.psv are never referenced (`schema.md:79-80`). H2 (`round` of the float quotient, `schema.md:131-132`) is stated exactly and was passed.

### 2.4 Arithmetic
Tests at 98.81 mean the rubric must be < 140 - 98.81 = **41.19%**. Opus earned 38/50 even with R1 misfiring. The judge cannot get there without criteria that the oracle cannot show (JD-7) or that game the agent. A new computation trap would need new data plus a schema rewrite that stops printing the values. That is a rebuild, not a small fix.

### 2.5 Verdict: **DROP**
The kill rule applies (tests 98.81 >= 95). No new computation trap is settled by the shipped data: the data is clean and the schema prints every constant.

---

## 3. season-ladder-settlement (tests 64.19, rubric 100, reward 0.8209)

### 3.1 Lost items (53 test points, judge lost 0)
All 11 lost tests are one cause, and it is not the agent's settlement logic.

| item | what happened | class |
|---|---|---|
| generalisation_* x10 (-5 each, `B/tests/test_output.py:2023-2070`) and determinism_two_runs_byte_identical (-3, :2073-2093) | Every one goes through `_run_script` (:1153-1196). That runs `/app/out/settle_season.py` as the unprivileged `settlerunner` account. The account is created in `B/tests/Dockerfile` (`RUN useradd --create-home --shell /usr/sbin/nologin settlerunner`), and the program runs as it whenever the verifier is root (:1087-1104, :1164). The agent wrote the program with the OpenHands file editor `create` (trajectory step 11). That tool left it mode 0600. The step 14 observation shows `-rw------- 1 agent agent 33196 Oct 19 14:27 settle_season.py`, and the harvested `R/artifacts/app/out/settle_season.py` is also `-rw-------`. `_open_to_sandbox` (:1107-1118) chowns only the case data/out dirs, never the script. So the sandbox account cannot read the program, python exits non-zero, and :1188-1189 raises `settlement program failed`. | **ARTEFACT** (harness and tool file mode plus a sandbox account the instruction never mentions) |

Proof that the logic is right: I ran a local driver (`scratch/season/driver.py`, `driver_all.py`) that imports the shipped `test_output.py` with a no-op rewardkit stub and sets `SEASON_OUT_DIR` to a copy of the agent's `/app/out`. Run as file owner, so mode 0600 is readable, there is no sandbox account, and no Docker is used. Result: **all 10 generalisation tests and the determinism test PASS** for the agent's program (`scratch/season/agent_res.txt`), as for the oracle (`oracle_res.txt`). The full suite gives 34/34 positives PASS (`agent_all.txt`: "34" PASS lines). The 3 negatives raise "no evidence of ...", which means not fired. The **true test score of this run is 148/148 = 100%**.
UNVERIFIED: the exact stderr in the verifier (ctrf.json and test-stdout.txt carry no messages), and the owner the separate verifier environment gives the copied file. The mode-0600 plus settlerunner path is the only difference between my local run and the verifier.

GENUINE losses: none. AMBIGUITY: none. HIDDEN RULE: none. AMPLIFICATION: the one artefact is multiplied across 11 tests (53/148 = 35.8%).

### 3.2 Run-to-run risk
- The artefact is likely stable. OpenHands `create` wrote 0600 here, so a rerun that creates the file the same way loses the same 53 points. A rerun that writes via shell (`cat >`, `cp`) gets 0644 and scores about 100. This is tool-path luck, not task signal.
- On logic, nothing is at risk: the program passes every hidden mutation.

### 3.3 Judge from probe
The judge has 16 criteria and 49 points. All 13 positives were earned and the 3 negatives were not fired (`R/verifier/reward-details.json`). That includes R9 (second run compared byte for byte, step 22), R13 (reproduces the worked report, steps 12-13 `calib_check.py` on the miniature season) and R14 (code quality).
Things Opus did not do:
- It never ran the program as a different user or with restricted permissions. That is not a spec behaviour, and the oracle does not show it, so it cannot be a criterion (JD-7).
- It never built a mutated season of its own. Its only non-shipped input was the calibration miniature, run at step 13.
A criterion "builds a season with a rename chain, cycle or upheld void protest and checks the output" is not shown by `solve.sh`, which only copies and runs (JD-7 fail), and it would not move the gate (see 3.4).
No candidate criterion is worth adding.

### 3.3b Lever check
- Levers are the three calibrated constants: forfeit rate 2/3, order forfeit→schedule→debit, and half-to-even conversion (H2). Plus earliest-filing authority, identity cycle rejection, the circuit cap identifier tie-break and the debit cap and amnesty.
- Every one is stated or calibrated with a single reading: `_params` (:1008-1025) asserts exactly one hit.
- Each costs **0%** alone on the true score, because the agent passes c01-c12, chain_* and the 10 mutations.
- H1-H6 in a rarely joined field: none found. The mutations already exercise every habit the test author listed, and Opus passed them all. Any further lever is UNVERIFIED and would need new data.

### 3.4 Arithmetic
- At v0 tests (64.19), overall is 82.1 because rubric is 100. To reach < 70 the rubric would need < 75.8%, which is unreachable since Opus earned 49/49.
- The v0 tests figure is artefact-only. The true value is 100, so the rubric would need < 40%, which is also unreachable.
- **Required fix whatever the verdict** (the task as shipped mis-scores any agent whose editor writes 0600): in `_run_script`, before dropping privileges, either make the script readable (`os.chmod(_script(), 0o644)`) or copy it into the sandbox-owned case directory and run that copy. Kit checks touched: TS-19 (tests reproducible) and the verifier sandbox rows (UNVERIFIED which id). One alternative is an instruction line stating the program must be world-readable, but that adds a non-task rule. The same sandbox pattern may exist in other tasks (`.kiro-staged-tasks/emberforge-vault-settlement` matched a grep for `environment_mode/separate`; settlerunner use there is UNVERIFIED).

### 3.5 Verdict: **DROP**
- The kill rule applies on the true score (tests 100 >= 95). Judge 100.
- No new computation trap is settled by the shipped data. Opus passed every calibrated constant and every mutation.
- The reported 0.8209 is a harness artefact and must not be counted as task difficulty. If the task is kept for other reasons, ship the `_run_script` chmod fix first.

---

## Summary

| task | verdict | expected tests | expected rubric | expected overall | fix size |
|---|---|---|---|---|---|
| caldermoor-commitment-closure | FIX | 74.4 | 52.6 (10/19) | 63.5 (65.8 if lever B self-corrects; 71.4 fail if Opus does one conduct probe) | 1 round: trim instruction.md:86-138, rebuild judge to 19 pts with C1-C4, add solve.sh self-check, reward.toml 0.5/19; 1 QC (AL-2, AL-18, IN-8, JD-7/8/9/12/13/16/18, JD-S7, JD-S13, tests_qc:R3) |
| numeric-reduction-benchmark-forge | DROP | 98.8-100 | ~76-82 | ~88-91 | n/a (kill rule; no trap in shipped data) |
| season-ladder-settlement | DROP | 100 (true; v0 64.19 is ARTEFACT) | 100 | 100 | n/a; if kept, `_run_script` chmod fix is mandatory |
