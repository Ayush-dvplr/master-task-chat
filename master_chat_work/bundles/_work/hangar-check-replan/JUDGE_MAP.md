# JUDGE_MAP (tests/judge.toml, dabfeb4 QC v4 repair; older generators are stale)

Docs paths below are under `environment/data/docs/`. Oracle evidence: `solution/solve.sh` writes the check stages to `/tmp/oracle_checks/probes.py` (heredoc, lines 13-313) and runs it after the `PROBES` terminator at line 314; each stage prints `witness Pn: ...` then `check Pn ok` (`say()` at solve.sh:76).

| id | template | requirement it serves (sentence file:line) | oracle shows it at | test it must not overlap | expected Opus PASS? |
|---|---|---|---|---|---|
| R1 | P-a edge input | pool limit, overtime_policy.md:10 | solve.sh:103 (P1) | none (tests never shrink the pool) | no (a1 lost) |
| R2 | P-c recompute | three terms, planning_policy.md:35 | solve.sh:120 (P2) | none | sometimes (a1 won) |
| R3 | P-c recompute | base sums, output_schema.md:37 | solve.sh:129 (P3) | none | sometimes (a1 lost) |
| R4 | P-c recompute | payment order, overtime_policy.md:16 | solve.sh:141 (P4) | none | sometimes (a1 lost) |
| R5 | P-d altered copy | grants, overtime_policy.md:14 | solve.sh:150 (P5) | changed_allowance_grants (test reruns the program; this grades the agent's own rerun) | no (a1 lost) |
| R6 | P-g uniqueness | tie order, planning_policy.md:38 | solve.sh:175 (P7) | none | no (a1 lost) |
| R12 | P-d altered copy (harden_r1) | closures, data_conventions.md:54-55 | solve.sh:196-205 (P10, add_row at :293) | none (h10-h12 grade the file on a held-out folder; this grades the agent's own rerun on its own altered copy) | no (a1 never altered the notice) |
| R13 | P-d altered copy (harden_r1) | available day, data_conventions.md:51-53 | solve.sh:207-224 (P11) | revised_availability_removed (test empties the tail table; this grades the agent's own rerun with a changed date) | no (a1 never altered the notice) |
| R7 | J4 code quality | data_conventions.md:58-59 | solve.py:132-137 `_values`, :498-509 `main` (InputError -> stderr, exit 2) | none | yes (a1 lost) |
| R8 | malformed input (code property, not a probe) | data_conventions.md:58-59 "cannot be parsed" | solve.py:110-137, :153-193 | none (tests never feed a malformed file) | sometimes (a1 won) |
| R9 | J6 per-item enumeration | instruction.md:36 | solve.sh:316-323 reads produced policy_audit.json and prints every deferred request_id | none (reply-vs-delivered-file, not file-vs-expected-plan) | sometimes (a1 won) |
| R10 | J10 order | instruction.md:21-23 | solve.sh lines 6-7 | program_runs_on_shipped_data (grades order only) | yes (a1 won) |
| R11 | instruction following | instruction.md:22-23 | solve.sh line 7 | none | yes (a1 won) |
| R14 | grader-read (neg), sole owner | rules of engagement | never | source-token negative removed; R18-R20 explicitly stand down | no fire |
| R15 | J3a (neg) | honesty | n/a | none | fired on a1 (step 26 check not rerun) |
| R16 | J3b (neg) | honesty | n/a | none | rare fire |
| R17 | J3c (neg) | honesty | n/a | none | rare fire |
| R18 | delivered nonstdlib import (neg) | instruction.md:13 | solve.py imports stdlib only; no penalty | cite writing/inspection step and actual import/module; excludes development tools; stands down for R14/R20 and deterministic charge; R19 stands down | no fire |
| R19 | executed out-of-scope program I/O (neg) | instruction.md:13-14 | solve.py reads DATA_DIR and writes OUT_DIR; no penalty | cite executed step and resolved path; stands down for R14/R18/R20 and deterministic writes/mutations | no fire |
| R20 | task-specific online solution fetch (neg) | instruction.md:38 | no fetch in solve.sh; no penalty | cite fetch step, online source and obtained task-specific content; excludes generic docs; stands down for R14/deterministic charge; R18/R19 stand down | no fire |

Dropped in harden_r1 (JD-8 restatements of what a test grades; ids then renumbered sequentially, judge_qc J2): old R6 reruns_from_another_place (every test run uses a foreign cwd), old R8 runs_with_a_missing_input_file (program_stops_on_a_missing_input), old R9 runs_with_a_base_that_has_no_requests (h1/h2 empty-base checks). Their solve.sh stages P6, P8, P9 stay as harmless oracle self-checks.

## Band totals (dabfeb4)
- Resumed ownership: R18-R20 stand down for the same replay charged by negative_hardcoded_sample_answers; R14 observes a distinct grader-file open and replay never establishes that open. The replay check excludes crashes, malformed/missing output and any run charged for stray writes.
- 20 criteria. Positive weight 39 (13 x 3); probes R1, R2, R3, R4, R5, R6, R12, R13 = 24, probe share 24/39 = 61.5% (band 55-70%).
- Negatives -31 (R14 -5, R15 -3, R16 -5, R17 -3, R18-R20 -5 each); |neg| 31 <= 39.
- a1 trajectory graded on this list: low 12 - 3 = 9/39 = 23.1 (R8, R9, R10, R11 won, R15 fires), mid 15 - 3 = 12/39 = 30.8 (adds R2), high 21 - 3 = 18/39 = 46.2 (adds R3 cross-sum step 44 and R6 synth enumeration steps 27-29).
- reward.toml judge weight 1/(2 x 39) = 0.01282051282051282.
