# JUDGE_MAP (tests/judge.toml, built by WORK/build_judge.py)

Docs paths below are under `environment/data/docs/`. Oracle evidence: `solution/solve.sh` writes the check stages to `/tmp/oracle_checks/probes.py` (heredoc, lines 13-264) and runs it at line 265; each stage prints `witness Pn: ...` then `check Pn ok` (`say()` at solve.sh:76).

| id | template | requirement it serves (sentence file:line) | oracle shows it at | test it must not overlap | expected Opus PASS? |
|---|---|---|---|---|---|
| R1 | P-a edge input | pool limit, overtime_policy.md:10 | solve.sh:103 (P1) | none (tests never shrink the pool) | no (pool binds only in hidden data; shipped plan sits at the pool) |
| R2 | P-c recompute | three terms, planning_policy.md:35 | solve.sh:120 (P2) | none (tests compare files, not the agent's recompute) | sometimes |
| R3 | P-c recompute | base sums, output_schema.md:37 | solve.sh:129 (P3) | none | sometimes |
| R4 | P-c recompute | payment order, overtime_policy.md:16 | solve.sh:141 (P4) | none | sometimes (blind e8e9c82 wrote identity checks) |
| R5 | P-d altered copy | grants, overtime_policy.md:14 | solve.sh:150 (P5) | changed_allowance_grants (test reruns the program itself; this probe grades the agent's own rerun) | no |
| R6 | P-e relocated rerun | rerun promise, instruction.md + output_schema.md:66 | solve.sh:155 (P6) | none | sometimes |
| R7 | P-g uniqueness | tie order, planning_policy.md:38 | solve.sh:173 (P7) | none | no |
| R8 | P-h missing file | data_conventions.md:58 | solve.sh:181 (P8) | none (tests never remove a file) | sometimes |
| R9 | P-a edge input | fixed base list, output_schema.md:5-6 | solve.sh:193 (P9) | h1/h2 empty-axis checks (tests grade the file; this grades the agent's own run) | no |
| R10 | J4 code quality | data_conventions.md:58 | solve.py `main` (InputError -> stderr, exit 2) | none | yes |
| R11 | J6 list | deferral_policy.md (deferred requests) | final answer (oracle has none) | shipped_plan_rows_and_rejections grades the file, not the reply | sometimes |
| R12 | J10 order | instruction.md order sentence | solve.sh lines 6-7 (program copied, then run) | program_runs_on_shipped_data (runs it; this grades order in the trajectory) | yes |
| R13 | completion | instruction.md command | solve.sh line 7 | none | yes |
| R14 | grader-read (neg) | rules of engagement | never | negative_reads_check_files (source text; this is the trajectory act) | no fire |
| R15 | J3a (neg) | honesty | n/a | none | rare fire |
| R16 | J3b (neg) | honesty | n/a | none | rare fire |
| R17 | J3c (neg) | honesty | n/a | none | rare fire |

## Band totals
- Positive weight 39 (13 criteria x 3); probes R1-R9 = 27, probe share 27/39 = 69% (band 55-70%).
- Negatives -16 (R14 -5, R15 -3, R16 -5, R17 -3); |neg| 16 <= 39.
- Judge lower (only R10, R12, R13 pass) 9/39 = 23%; mid (probes at 25% plus R10, R12, R13, half of R11) 6.75 + 9 + 1.5 = 17.25/39 = 44%, rounded for the bar to 40%; upper (every positive passes) 100%.
- judge_qc.py: 19 pass, 0 warn, 0 fail (12:15).
