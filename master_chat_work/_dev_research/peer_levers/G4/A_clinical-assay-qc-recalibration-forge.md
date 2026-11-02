# A: clinical-assay-qc-recalibration-forge (56.72 / 42.00 / 71.43)

Run dir: `trajectories/claude-opus-5/run_1/`. Task dir below = `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Aryan Mehta/clinical-assay-qc-recalibration-forge/`.

## Verdict: PARTLY (genuine wrong values, but from one under-specified sentence, amplified by gating)

The loss is real: the agent's program ran, produced wrong numbers, and the verifier read them. No harness problem. But the single rule that cost all 58 test points is not stated unambiguously (see item 2), and it is NOT one of the eight designed levers listed in `solution/TRUTH.md` L6-13. I count it as PARTLY: real lever mechanism (cascade + gate), doubtful rule clarity.

## 1. Run health
- `result.json`: `exception_info` null; agent ran 16:40:31Z to 16:58:43Z (about 18 min); no timeout or step limit. 34 trajectory steps; agent's working steps 2 to 33 span 16:46:49 to 16:56:12 (trajectory timestamps).
- `verifier/test-stdout.txt` is 15 bytes, just `reward: 0.5671`. No traceback, no Errno 13, no collection errors.
- `ctrf.json`: 35 tests, 16 passed, 19 failed. 5 of the "failed" are negative checks that did not fire (good for the agent). So 14 positive checks failed.

## 2. Did the verifier run the agent's program, and are the failures wrong VALUES?
Yes. `test_output.py` L1393-1422 `_run_agent` copies the program, runs it on a regenerated corpus and compares bytes. I reproduced this locally (read-only, scratch dir, stubbed rewardkit):
- Agent's shipped `/app/out` vs `reference()` on shipped data: 17 of 21 artifacts differ. Same 4 match: `tier_analyte_membership.json`, `ordered_reading_index.json`, `excluded_readings.json`, `carryover_ledger.xml`.
- Example of wrong value: reference `summary.json` b_open allocations `{"calcium":691,"creatinine":0,"glucose":245,"lactate":264}`; agent `{"calcium":1200,"creatinine":0,"glucose":0,"lactate":0}`. Reference tier totals `routine 773, stat 2827`; agent `routine 81, stat 3519`. Batch totals and carryover ledger agree (both 1200 per batch).
- Root cause found by diff of convergence code: the reference computes the fair share ONCE before the rounds (`test_output.py` L252-262, outside the `while` at L270), the agent recomputes it every round from the current masses (`derive_report.py` L306, inside the loop at L297).
- Proof it is the only fault: I moved the agent's `fair_share` call outside its loop (one line, scratch copy only). Result: 0 of 21 artifacts differ on the shipped run, 0 of 21 on EVAL_SEED/120, 0 on CHALLENGE_SEED/80, 0 on the cycling probe corpus (CHALLENGE_SEED^0x2B2B/96). Original program: 17 of 21 differ on each.

## 3. Gate check
Not near zero, but `_full_core_matches` (L1517-1525: summary.json, policy_audit.json, panel_analyte_glucose.json exact on visible run) gates the whole-doc @5 checks (carry, round_control, sparse probes). Because convergence feeds everything downstream, one misreading failed 14 positive checks = 18 points at @3 plus 40 at @5 = 58 points. The gate is stated: instruction says one wrong reading "shows up as many wrong figures at once".

Rule clarity (why PARTLY): `environment/data/stage_note_convergence.md` L3 "settle the admitted analyte masses by damped proportional rebalance toward the fair share"; L5 "The fair share splits a target mass across the analytes in proportion to what they already hold." No sentence says whether the fair share is fixed at the admitted masses or redone each round. "What they already hold" can be read as "at admission" (reference) or "now" (agent). Definite singular "the fair share" leans to fixed (INFERRED). The agent's own trace at trajectory step 25 shows its reading: `fair=d.fair_share(m,an,cap)` inside `for r in range(14)`, and the fair share changes every round (`fair [391,0,245,264]` then `[1088,0,-91,-97]`, with negative masses). It saw negative masses and kept going.

## 4. Judge
`verifier/score.json`: judge read the trajectory and response. 9 criteria; failed R4 and R8 (6 of 21 points).
- R4 "runs derive_report.py at least twice on the shipped run and compares the outputs" (`tests/judge.toml` L50-61, type "agent behavior"). Failed on agent's work (it re-ran but never compared two runs; step 28 ran a perturbed copy instead). Rule is NOT stated in instruction.md or the data files (grep for twice/determinis finds nothing). It is a conduct criterion, so per JD-15 it needs to hold for every competent route; RISKY.
- R8 code quality (L102-113): failed on the agent's work (judge: `load_governance` catches `zlib.error` and treats failed decompress as raw data). Meetable by the oracle (INFERRED, not checked line by line).

## 5. Permissions
`tests/test.sh`: `mkdir -p /logs/verifier; chown root:root; chmod 755`, `chmod -R go-rwx /tests`, then `rewardkit`. `test_output.py` L1398-1402 docstring: copies the script with mode 0644 and makes the out dir 0777 before running it under `setpriv --reuid=nobody` (L68, L1387-1390), explicitly so an owner-only 0600 save does not break grading. This is the fix our cohort bug needed.
