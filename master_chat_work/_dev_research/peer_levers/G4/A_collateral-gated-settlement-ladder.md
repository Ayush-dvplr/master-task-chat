# A: collateral-gated-settlement-ladder (Harsh Gupta), board 6c051f3

**Verdict: GENUINE** (tests). All 55 lost test points come from one wrong VALUE decision on a rule the spec states plainly twice. Judge lost 3 on a conduct criterion the contract does not ask for (see 4).

Recorded run: overall 62.73 / tests 30.38 / rubric 95.08 (report.json; test-stdout.txt = `reward: 0.6273`).
Paths below are relative to the task folder `.../Harsh Gupta/collateral-gated-settlement-ladder/`; run = `trajectories/claude-opus-5/run_1/`.

## 1. Run health
- `run/result.json`: `exception_info` null, reward 0.6273, agent 15:14:58Z to 15:35:02Z (about 20 min of a 7200 s budget). No timeout or step limit.
- `run/verifier/test-stdout.txt` is 15 bytes, just the reward line: no traceback, no `Permission denied`/`Errno 13`, no `No such file`, no collection/import error.
- ctrf: 22 checks, none skipped. Negatives (-5 memorized answers, -3 network/shell, -3 nondeterminism) did not fire.

## 2. Did the verifier run the agent's program, and are failures wrong values?
Yes. `tests/test_output.py` `_run_transform` (L626-668) copies the shipped book (embedded as `_SHIPPED_DATA`, L87-100, rebuilt by `_data_dir` L105) or a relocated/permuted copy, runs `/app/out/transform.py` under `setpriv --reuid=nobody` (L62, L125), 600 s timeout, and compares against an independent reference `_settle` (L435-593).

Local reproduction (scratch script, read-only import of test_output.py with a no-op rewardkit stub, ran the agent's delivered transform.py):
- agent `normalized.jsonl` = 10,998 events, reference = 10,958. The difference is exactly **40 extra events, all from `adjustments.jsonl`**. There are **zero field differences** on the 10,958 shared events, and the blocked-event set is identical.
- All 40 extras carry `amount_minor` as a JSON **string** of digits (e.g. `"-104527"`). The reference drops them as malformed (`_signed` L329: `if isinstance(minor,bool) or not isinstance(minor,int): raise _Dropped`).
- The agent's `adjustment_minor()` (`run/artifacts/app/out/transform.py` L371-384) runs `json.loads(value.strip())` on strings and accepts the result when it is an int.
- Spec: `environment/data/schema.md` L34 "`amount_minor` must be a JSON integer and carries its own sign", repeated at L148-149 in the malformed list: "an `amount_minor` that is not a JSON integer".
- The agent saw these rows. Trajectory step 10 printed `Counter({'int': 2560, 'str': 40, 'float': 34, 'bool': 18})` for the adjustments.

So every failure is a wrong value: 40 extra rows that every whole-output comparison then picks up.

## 3. Near-zero / gate analysis
Tests did not go to near 0. The score of 30.38 comes from one defect spreading through gating:
- Six whole-artifact checks failed: normalized, summary, region, segment, product, data_quality.
- Two hidden-book checks failed on the same cause: relocated book, and permuted rows with a 1.0375 rate shift (`_permute` L686-712).
- Three checks named as if they test one rule each also failed: fx carry-forward, UTC day shift/fiscal period, counterparty dedup segment. Each one also asserts that the whole event-id set equals the reference (L812 `set(got)==set(cents_by_event)`, L823, L832).
- That makes 11 × 5 = 55 points from one root cause. The gate rule is stated clearly in `instruction.md` L37-41: "An artifact counts only when every single value in it is exact, so one cent or one unit out of place costs the whole file."
- The hidden gate inside the three per-rule checks is not stated. INFERRED: an honest reader expects those three to grade only their own rule. This is a design quirk, not a harness artefact.

## 4. Judge
- score.json: the judge read the response and the trajectory. 19 criteria, 58/61.
- The only failure is R15 (+3, trajectory): "verifies the pipeline against a second copy of the book whose rows have been reordered before finishing". The justification says the second corpus had legacy.txt removed, not rows reordered.
- The agent did not do this, so the failure is about the agent's work. But no file asks for it as conduct. `schema.md` L10-11 only says "Row order in an input file is never significant except in the two places this contract names file order as the tie-break."
- So R15 grades an unstated conduct (IN-15/JD-15 risk). The oracle can meet it, so it does not break JD-7.
- R1-R9 only check that each closing figure is *stated*, not that it is correct.

## 5. Permissions
- `tests/test.sh`: removes old reward files, `mkdir -p /logs/verifier`, `chown root:root`, `chmod 755`, `chmod -R go-rwx /tests`, then `exec rewardkit`.
- `_run_transform` chmods inputs 0755/0644, the out dir 0777, and the script 0755 plus parents `|0o055`. Comment: "An agent editor leaves transform.py at mode 0600 owned by uid 1000, which the dropped uid (setpriv --reuid=nobody) could not read".
- This is the fix for our cohort bug. No permission artefact.
