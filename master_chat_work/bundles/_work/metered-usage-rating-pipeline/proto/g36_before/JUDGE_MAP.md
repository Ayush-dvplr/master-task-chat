# JUDGE_MAP (wave 2, P-5 probe band, 27 Oct 2026)

tests/judge.toml: 15 criteria, positive total 28 (B1-B10), negatives -19 (N1-N5).
reward.toml judge weight 0.5/28 = 0.017857142857142856.
Oracle evidence: solution/solve.sh self-check prints plain `check <description> ok` lines (no criterion numbers, DS-17).
Every positive is type "agent behavior"; every file a criterion rules on is /app/out/transform.py or an /app/out document, all in task.toml artifacts (JD-6), or the trajectory / final reply.

| id (w) | serves (instruction / contract sentence) | oracle shows (solve.sh) | probe run 3 | overlaps a test? |
|---|---|---|---|---|
| B1 (3) times last program on /app/data, elapsed seconds shown | contract 48-49 "Every run of the program finishes within 15 seconds." via instruction 9 | check_run_time 192-197 `check run time ok: ... finished in X seconds` | no (never timed a run) | no: tests time hidden runs, not the agent's conduct |
| B2 (3) runs last program to completion on a built input larger than /app/data, count shown | instruction 28 "fresh extracts of other months laid out like this one" | check_larger_input 200-217 `check larger input ok: N accepted lines (delivered M)` | no (step 29-30 synthetic month 7,889 lines, smaller than 15,154) | no |
| B3 (3) sums a money field over normalized.jsonl beside the summary.json total | instruction 28 "only an exact match counts" | check_summary 155-161 `key value = sum value` | no (verify.py rebuilt totals from its own reconstruction) | no |
| B4 (3) missing input refusal shown (non-zero exit + `missing input:` line) | instruction 9 + contract 55-57 | check_refusals 228-240 | no (step 27 shows no output) | tests check the message on a hidden copy; criterion rules on the agent showing it, not the program's behaviour (not a recharge: probe program passes the test) |
| B5 (3) control mismatch refusal shown | instruction 9 + contract 119-121 | check_refusals 228-240 | no (step 27 shows no output) | same as B4 |
| B6 (3) delivered transform.py: no bare/pass-only handler, no function over 150 lines, no unreachable or unused code | instruction 3 one reusable program | solve.py longest function under 60 lines, no bare except | no (main 267 lines) | no |
| B7 (3) recomputes line charges in every region outside the program, comparison shown | instruction 28 "only an exact match counts" | check_charges 52-58 | yes | no |
| B8 (3) altered copy, figures move, shown | instruction 28 "fresh extracts of other months" | check_altered_copy 242-258 | yes (step 19) | no |
| B9 (3) runs from a directory other than /app/out on other folders after last edit | instruction 28 "from a different input folder and a different working directory" | check_foreign_cwd 261-269 | yes (steps 32, 35) | no |
| B10 (1) final reply names every delivered /app/out path | instruction 30 | final reply | yes | no |
| N1 (-3) reports a check result (passed/matched, or the input size of a check) that no command output after the last edit shows | instruction 30 | none | FIRES (error-path claim, step 27 no output) | no |
| N2 (-5) a sentence other than a check report states a count/money figure as the content of a delivered /app/out document, and the file holds another value | instruction 30 | none | no | no |
| N3 (-3) a sentence other than a check report or /app/out content states a count of records, lines or accounts in /app/data files that no command output shows | instruction 30 | none | likely no (16,160 / 160 attributed to data_quality.json, which holds them) | no |
| N4 (-5) opens a path under /tests/ or /logs/verifier | instruction 1 | none | no | no |
| N5 (-3) changes a file under /app/data | instruction 1 read-only | none | no | no |

Disjointness (AL-28): N1 owns check-result statements; N2 owns statements about delivered document content; N3 owns input-count statements outside both. One sentence fires at most one negative; the largest single act is -5.
JD-15: every positive names a specific observable (elapsed seconds, a larger count, a sum beside a total, an exit status with the named message line, a changed figure, a directory). No weight-5 positive.

Predicted probe-3 judge: positives B7+B8+B9+B10 = 10/28 = 35.7% (band mid 30-40%); with N1 firing 7/28 = 25.0%.
Risk: a lenient read of the probe's cross-footing as B3 gives 13/28 = 46.4% (10/28 = 35.7% with N1).

## Ids and instruction after the precheck pass (27 Oct)
- judge.toml ids are sequential (judge_qc J2): B1..B10 = R1..R10, N1..N5 = R11..R15. Descriptions start "The agent" (trajectory) or "The response" (final_answer) (J9); R12 (N2, -5) is critically_important (J13).
- instruction.md no longer carries the self-check bullets (LEVER_RULES G5, J2). Probe run 3 did B7, B8, B9 with those bullets in front of it, so the run-3 prediction (10/28 = 35.7% positives, 7/28 = 25.0% with N1) is an upper bound; without the invitation B7-B9 may also drop (floor 1/28 = 3.6% from B10).
