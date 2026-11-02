# A: project-schedule-feasibility (recorded 69.38 / tests 98.77 / rubric 40.00)

**Verdict: PARTLY.** Tests are genuine but nearly a full score: one 1-point check failed, and the agent's code caused that failure. The judge score is the real loss (21 of 35 points). All of those points are process criteria that ask for named self-tests on constructed edge cases. The agent did not run those self-tests, so the loss is genuine, but some criteria are weak under JD-15 and JD-7 (see below).

Run dir = `trajectories/claude-opus-5/run_1`.

## 1. Harness health
- `result.json` has `exception_info: null`. The agent ran 22 steps from 12:21:20 to 12:26:41Z (about 5.5 min) of its 7200 s budget, so it was not cut off by a timeout or step limit.
- `verifier/test-stdout.txt` has one traceback, from the agent's own program on the `bom_rules` corpus: `json.decoder.JSONDecodeError: Unexpected UTF-8 BOM (decode using utf-8-sig)`, raised at agent `derive_report.py` L30 (`read_json`, `json.load` with `encoding="utf-8"`). It shows no `Permission denied`, no `Errno 13`, no `No such file`, no import error and no collection error.
- Permissions: `tests/test.sh` sets `chown root:root /logs/verifier` and `chmod 755`, and `chmod -R go-rwx /tests`. `tests/test_output.py` handles the dropped user correctly: L77 `_SETPRIV` runs as nobody/nogroup, L583 sets the program to 0644, L587 adds +r+x on ancestors, and L617 `_make_readable_for_nobody` covers the data and out dirs. The agent program ran under nobody without access errors, and 28 of 29 positives passed through that path.

## 2. Did the verifier run the agent's program?
Yes. `run_corpus(key)` builds each corpus in `CORPORA` (L544-561) and runs the agent's `derive_report.py` on it. It then compares the result with `reference()` (L385), which the test computes itself. There are 16 generated or fixture corpora, plus 3 seeded generator corpora (`eval`, `challenge`, `boundary`).

The failed check is `test_bom_rule_tables_are_echoed` (w1). Its corpus prepends EF BB BF to `capacities.json` and `priority.json` (L555, `_with_bom` L319-323). The agent's program crashes on that input, which is an error-path failure in the agent's code, not a harness fault. The BOM CSV checks (`bom_task` w3, `bom_precedence` w3, `bom_calendar` w1) passed, because agent `read_csv_rows` uses `utf-8-sig`.

## 3. Gate
There is no gate. Tests scored 98.77 = 80/81.

## 4. Judge
The judge is `openai/gpt-5.6-sol`, batched, and reads the ATIF trajectory. It has 18 criteria with 35 positive points. It failed r6, r12, r13, r15, r16, r17 and r18, all w3, so 14/35 = 40.00. Each failure was grounded in the trajectory:

- The agent's constructed corpora at steps 13 and 15 covered an unknown crew, a cycle, a ghost predecessor, an unknown class, zero duration, overflow and an empty extract.
- They did not cover a same-rank tie (r6), a perturbed copy (r12), a relabelled copy (r15), a non-working first row (r16), a successor past the last working day (r17) or duplicate edges (r18).
- The agent never computed checksums (r13).

Doubtful criteria:
- **r13** asks for checksums before the first run. That is a preference, because a diff or read-only check would also prove the data was untouched. JD-15 step 2 says to remove such criteria. RISKY.
- **r6 and r14-r18** each name the exact edge case that a hidden test probes. They are odds-raising conduct criteria and acceptable under JD-15. However, each is worth w3 and they overlap the matching tests in topic, though not in observable. I judge that acceptable under JD-8, because the judge grades the act of running a self-test, not the output.
- **JD-7:** the oracle `solution/solve.sh` (204 B) runs `solve.py` and has no exploratory trajectory, so literally no criterion that asks for a self-test run can be met by the oracle. This is common to all 4 peer tasks. RISKY (INFERRED, because it depends on how QC reads JD-7 for conduct criteria).

## 5. Permission setup
Correct, as described in section 1. This task is not affected by our cohort `/app/out` read bug.

## Points
- Tests: 1 genuine point lost, a BOM on a JSON rule table. The rule is stated only as "Every file is UTF-8 encoded text" (`environment/data/schema.md:13-14`), with no mention of a BOM anywhere. That makes it borderline hidden (IN-15 RISKY).
- Judge: 21 genuine process points lost. The agent did not run the named edge-case self-tests.
