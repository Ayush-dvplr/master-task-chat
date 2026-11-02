# flood-repair-portfolio: scoring paid attempt a3 (board ea9239d)

Bundle tree 931f8f817d76 (= Tasks_INPUT). No bundle edits. Program scored = a3 `artifacts/app/out/derive_report.py` (sha 69670ef2…, mtime 16:02 IST) with the nine reports as the agent left them (mtime 15:19). Copy with sha256s: `a3_out/`, `a3_out_sha256.txt`. Scratch and logs: `_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/`.

## 1. Tests-only score (verifier lane): 108/108 = 100.00
Method: live kit `Input_Bundle_QC/exe_copy.py` (sha 931637ce) -> copy with judge.toml removed; image built from copy/tests (python:3.12-slim + rewardkit 0.2.1); container `--cpus 2 --memory 4g`; /app/data = shipped data, /app/out = a3_out unchanged (PRE sha lines in the log match a3_out_sha256.txt). Log `logs/v_a3.log` (ALL_DONE, container_rc 0):

    VERIFIER_SECONDS 96.56
    REWARD {"reward": 1.0}
    SCORE 108.0 FAILED [] NEG_FIRED []

Every positive check scored 1.0 (artifacts_present 1, shipped_* 5x3, h1/h2/h3 feasible 3 + optimal 5 + summary 5 + policy_audit 3 + data_quality 3 + regions 3 + segments 3, scaled_shuffled_summary 5, rotated_summary 3, relocated_copy 3, missing_input_is_named 3, reruns_identical 3). Negatives (reads verifier files -5, hardcoded sample answers -3) both 0.0. **Lost checks: none.**

## 2. Kill-table driver (h2_a1/drive2.sh, a3 program swapped in, Docker 4g/2cpu, cap 60 s)
Log `logs/kill_a3.log` (ALL_DONE). Books N1-N3 = pinned H1-H3 (seeds 815301/822402/833503, 100 rounds, 60 large, mean 358-384 conflict edges in large rounds).

| book | ref unbusy | a3 unbusy | ref busy | a3 busy run 1 / 2 | peak MB | verdict |
|---|---|---|---|---|---|---|
| shipped (vs 15:19 docs) | - | 0.33 s | - | - | 24.9 | EXACT |
| N1 | 1.23 | 5.16 | 1.78 | 6.96 / 7.32 | 60.0 | EXACT |
| N2 | 1.92 | 8.28 | 1.93 | 7.29 / 7.58 | 73.0 | EXACT |
| N3 | 1.53 | 5.23 | 2.11 | 5.21 / 5.29 | 54.4 | EXACT |

Lever points kept **78/78** (3 fresh books x 25 + reruns_identical 3). Worst time 8.28 s = 41% of the 20 s cap (`tests/test_output.py:39 BOOK_SECONDS = 20`). The 16:02 program reproduces the 15:19 reports byte for byte, so the stale-report question is moot.
Both methods agree. Caveat: a3 sits in the same 5-8 s band as harden r2's `elim` program (7.93/7.55/6.51 EXACT) which once lost one book (25 pts, 83/108) under verifier load; `vebest` (6.86/6.51/5.93) kept 108. Under that tail risk tests would be 83/108 = 76.85.

## 3. Did the lever hold? Yes for a1-style programs, no as a difficulty lever for a3
The lever (fresh dense books under 20 s) killed a1 (0/78). a3 built reductions + an elimination DP with a branch-and-bound fallback and kept all 78. a3 would have passed the full test file had it stopped.

## 4. Judge prediction (judge.toml read against openhands_sdk.txt; same method as harden r2)
- R1 VALUE rows, R2 PAIR rows, R4 region, R5 segment rollups: 0. Only cross-foot of region totals (L6080-6087) and one VALUE row by hand (L5922-6071).
- R3 rejection codes outside the program: borderline. Step 40 (L5707-5753) imports `derive_report` check functions, but steps 41-42 (L5771-5869) print the raw offending rows of the 19 rejected rounds by sed/awk.
- R6 small rounds by enumeration: 0. Brute force runs on random graphs (check_mwis.py L4421-4533), and check_big.py imports derive_report (L5347-5355). a1 failed R6 for the same import.
- R7 altered copy: 0 (synthetic gen_book only).
- R8 timed shipped book: yes (`time` 0.409 s after the last edit, L8633-8674). The 20 s compare is only in reasoning (L6096 "plenty of headroom").
- R9 maintainable program: yes. R10 lists rejected rounds: depends on the final reply, which never came; a finished run would list them (the 19 ids are at L5611).
- R11 -5: not expected, because the shipped run and both check suites were re-run after the 16:02 edit (L8633-8700).

| | points/30 | judge % | predicted final (tests 100) |
|---|---|---|---|
| low (a1 profile: R8,R9,R10, R11 fired) | 4 | 13.33 | 56.67 |
| **mid (R8,R9,R10, no R11)** | 9 | 30.00 | **65.00** |
| high (mid + R3) | 12 | 40.00 | 70.00 |

With the one-book load loss, mid final = (76.85+30)/2 = 53.43. The actual paid a3 got no reward file: the judge needs `/logs/agent/trajectory.json`, which is written only at a clean finish (`verifier/test-stdout.txt`: Trajectory not found). So **a3 actual = no score**.

## 5. Where the 2 hours went (TIMELINE.md)
- 14:54-15:22 (28 min): correct program and nine reports (first written 15:10 in /tmp, 15:19 in /app/out), brute-force and cross-check suites, rejected-round inspection. Correctness checking stopped at step 43 (~15:22).
- 15:22-16:54 (**~92 min**): performance work on synthetic worst-case books (`/tmp/gen_book.py`, 200 rounds x 160 proposals x 900 records, step 44 L6073).
  - About 68 of those minutes were waiting on `timeout 600/1800/900` runs that ran out (L6370, L8813, L9079).
  - The last program edit was at 16:02.
  - The last command (L9505) was `timeout 900 python3 frontier.py` with a tool timeout of 1000 s, started ~16:51 and cut off by the 7200 s limit.
  - There was no final reply.

## 6. Will a4 unchanged time out again? Risk: medium (about 50%: a1 finished, a3 timed out)
What pulls the agent into performance work:
- `environment/data/contract.md:11` "at most 200 rounds in a book and at most 160 proposal rows in a round"
- `contract.md:12` "at most 900 conflict records in a round"
- `contract.md:15` "The program must write all documents for a book inside these limits within 20 seconds of wall time."
- `instruction.md:11` "Each output document is graded whole on fresh books, and only an exact match counts."

A careful agent reads these as a worst-case guarantee and tries to prove it: an exact max-weight independent set on 160 nodes with 900 records is exponential in the worst case. The shipped largest round has 483 records, so the agent cannot tell how dense fresh books will be. a1 ignored the limits and failed the lever. a3 honoured them and ran out of agent time. Long `timeout N` commands with N ≥ 600 burn the budget with nothing to show for it.

## 7. a4 options (cost in one line each)
1. **Unchanged rerun.** Cost: one paid run. Likely 56-65 if it finishes, but roughly a coin flip on the same perf rabbit hole (no reward file at all).
2. **One instruction sentence on the time budget**, e.g. "Leave enough of that time to finish and write your final reply." Cost: one-line edit plus re-QC. It touches 01_Instruction_QC IN-1/IN-S4 (the mandatory seconds sentence must stay exact and natural; instruction_qc.py C1 regex `[Yy]ou have ([\d,]+) seconds`). It risks IN-17 (pre-announcing) only if it mentions speed. The tree sha changes, so the harden r2 kill table needs a digest re-check, but tests are unchanged.
3. **Tighten the contract limits** to what the hidden books use (e.g. 600 records instead of 900, contract.md:12). This removes the worst-case pull. Cost: contract.md + test_output.py LIMITS L85 + hidden-book/oracle re-check, a full harden gate re-run (DS rows on contract vs tests alignment). Highest cost.
4. **Harness-side: no bundle edit.** Accept that an agent timeout leaves no judge score. Cost: zero, but the outcome stays random.

**Pick: option 2.** It is the cheapest change that targets the actual failure (no final reply → no trajectory → no reward). It does not soften the lever: a3's program already passes 108/108. If the master wants zero edits, option 1, knowing the timeout risk is about 50%.

## Session
Rename ran at 17:32 (opencode `ses_e6902ea47ffe6FmAZIGmMS5yUo` matched).

## Lessons for the master
- An agent timeout leaves no trajectory.json, so the judge crashes and there is no reward | no change: harness behaviour, flag it in run triage instead.
- Worst-case limits in contract.md plus "fresh books" pull careful agents into unbounded worst-case perf work | template_change: 01_Instruction_QC.md:31 (IN-1), allow a budget-reminder clause after the seconds sentence.
- Score a timed-out run from artifacts with exe_copy plus the kill-table driver; the two agreed here | no change: the method already exists in harden r2.
