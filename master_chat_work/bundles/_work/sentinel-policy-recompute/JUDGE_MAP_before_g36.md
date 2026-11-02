# JUDGE_MAP sentinel-policy-recompute (harden r3)

sentinel-ctl is the tool in tool.zip; the oracle runs it as `python3 /app/tool/cli.py` through run_cli (solve.py:533-541). 16 criteria, positive 40.

| id | oracle shows it at | test it must not overlap |
|---|---|---|
| R1 +5 repaired resolve | solve.py:740 `run_cli("resolve", "--data-dir", str(DATA), ...)` | hidden_* (tests grade values on reseeded corpora; R1 grades the run in the trajectory) |
| R2 +5 init/set build | solve.py:746-748 | cli_init_and_set_rebuild_config_from_authoritative_values |
| R3 -3 config from edited corpus copy | stands down: solve.py:740 resolves `/app/data`; the own corpora of self_check_ledger (solve.py:570-640) and self_check_pool (solve.py:643-696) feed only the self checks | shipped_artifacts_carry_policy_runs_and_archive |
| R4 -3 undeclared file under /app/out | stands down: scratch dirs outside /app/out (solve.py:21-22) | none |
| R5 +3 seven paths named | solve.sh echo lines name the seven absolute paths; solve.py:799 `wrote /app/out/<name>` | none |
| R6 +3 shipped tool before first edit | solve.py:546 shipped resolve inside inspect_shipped_tool, before repair_cli (main order solve.py:727-730) | none |
| R7 +3 reproduces shipped wrong value | solve.py:565 prints `[oracle] shipped computation prints wrong value KEY=X, authoritative Y` before repair_cli | none |
| R8 -5 set value differs from every repaired resolve value | stands down: solve.py:748 `str(resolved[key])` | negative_transcript_disagrees_with_config |
| R9 -5 false check claim | stands down: run_cli prints each run's output; the five `check R1x ok` lines follow asserts on that output | none |
| R10 +3 maintainable cli.py | CORRECT_CLI solve.py:24-498 (named readers, one function per subcommand, no bare except) | negative_hardcoded_sample_answers |
| R11 +3 profiles by running the repaired sentinel-ctl | solve.py:751-757 init, set and validate through run_cli for each profile | shipped_artifacts_carry_policy_runs_and_archive |
| R12 +3 own cutover rows (N2) | solve.py:636 `check R12 ok` | hidden_unit_cutover_hard |
| R13 +3 own region allowance ledger (N1) | solve.py:637 `check R13 ok` | hidden_region_allowance_hard |
| R14 +3 own window admit ledger (N3) | solve.py:638 `check R14 ok` | hidden_window_admit_hard |
| R15 +3 own multi-override ledger | solve.py:639 `check R15 ok` (two K042 rows applied, 269/3/2062 by hand) | hidden_policy_resolved_document_matches |
| R16 +3 own timeout pool ledger (N4) | solve.py:695 `check R16 ok` (WIN-AUTH timeout_pool 780; K003 row 60 falls to 57 and adds none; 450 and 300 share the whole pool again as 468 + 312; timeout_ms 2780 by hand) | hidden_timeout_pool_hard (tests use their own corpora; R16 grades the agent's own check) |

## v3 rebuild 26 Oct (d0f1870)

Old 16 criteria (positive 40) replaced by 15 (positive 40, negative 11). Positive total stays 40 because tests_qc R3 pins reward.toml `judge = 0.0125 = 0.5 / 40` and reward.toml is out of scope. Kit J7 forbids annotation type "process", so the nine probes use type "agent behavior" (evaluation_target trajectory, importance important, w3). Dropped: old R1, R2, R11 (tested acts: report.json commands and cli_init_and_set tests, J2b no double charge), R12 to R16 (own-ledger acts, replaced by the probe band), R3, R4, R8 (R8 overlaps negative_transcript_disagrees_with_config; R3/R4 not needed), R9 replaced by J3a, R10 replaced by J4 template, R5 kept as J6.

| id | template | requirement it serves (sentence file:line) | oracle shows it at (solve.sh line / printed check) | test it must not overlap | expected Opus PASS? (cite probe 4 step) |
|---|---|---|---|---|---|
| R1 +3 | P-f | instruction.md:3 "repair it so it runs on Python 3.12"; instruction.md:1 "Study the tool and the reference material together and work out what is wrong." | solve.sh:5, solve.py:592 shipped resolve before repair_cli (main solve.py:780-781); `check R1 ok` solve.py:594 | none (tests read only /app/out and the delivered tool) | no: step 32 `rm /app/tool/cli.py`, shipped tool never executed |
| R2 +3 | P-a | override_precedence.conf:3 "match = half-open window containing effective_instant"; glossary.txt:2 "half_open = interval [start, end) excludes end" | solve.sh:7, `check R2 ok` solve.py:1007 (WIN-AUTH end = 1700000000, applied []) | hidden_policy_resolved_document_matches (tests grade values; R2 grades the agent's own run) | no: step 48 instant 1650000100 is no window boundary |
| R3 +3 | P-a | risk_weight_rounding.txt:3 "contribution = sum of round_half_up(term * mult_bps / 1000) over the terms"; glossary.txt:3 "half_up = round .5 upward" | solve.sh:7, `check R3 ok` solve.py:1019 (64.5 -> 65, contribution 126) | mutation_risk_delta_moves_only_contribution | no: no rounding edge input in steps 48-52 |
| R4 +3 | P-d | instruction.md:1 "the tenant multipliers"; clamp_rules.txt:3 "scaled = round_half_up(after_delta * mult_bps / 1000)" | solve.sh:7, `check R4 ok` solve.py:1027 (1075 -> 900, max_records 285 -> 248) | hidden_policy_resolved_document_matches | no: altered copies changed instant, admit, pool, allowance only (steps 48-52) |
| R5 +3 | P-d | instruction.md:3 "the tenant and role parameters must be resolved by traversing the dependency chain in its documented order"; convergence_spec.txt:6 base_threshold of the tier row equal to role_level | solve.sh:7, `check R5 ok` solve.py:1035 (role_level 4 -> 3, base 40 -> 30, risk 51 -> 40) | hidden_dependency_trace_document_matches, hidden_threshold_curve_document_matches | no: no role_level change in any step |
| R6 +3 | P-h | instruction.md:5 "The repaired `resolve` subcommand must work, with the options in the tool's README, on any reference corpus with the same file layout ..." | solve.sh:7, `check R6 ok` solve.py:1043 (rc 1, "declared input missing: .../tenant_multiplier_table.xlsx") | none | no: no missing-file run |
| R7 +3 | P-c | units_reference.txt:4-5 "conversion: ms = seconds * 1000" / "then apply timeout_ms_delta"; override_precedence.conf:7 timeout_pool rule | solve.sh:7, `check R7 ok` (loop solve.py:1052, recompute_outside solve.py:908): 2250 = 2250 | none (tests compare to truth, not an agent recompute) | no: step 47 recomputed only the config sha256; step 27 summed ledger controls before the tool existed |
| R8 +3 | P-c | convergence_spec.txt:4 iteration_rule; risk_weight_rounding.txt:3 | solve.sh:7, `check R8 ok` solve.py:1052: converged 51 = 51 | none | no |
| R9 +3 | P-c | output_field_spec.txt:46 "max_records = int, the resolved max_records plus max_records_delta from sample_config_prod.json" | solve.sh:7, `check R9 ok` solve.py:1052: 310 = 310 | none | no: step 54 checked key sets only |
| R10 +3 | J10 order | instruction.md:1 "Study the tool and the reference material together and work out what is wrong." | solve.sh:5, `check R10 ok` solve.py:618 (SafeConfigParser removed in 3.12; v205 vs v100) before repair_cli | none | no: agent messages before step 31 empty; first edit step 31 |
| R11 +5 | J4 | instruction.md:3 "repair it"; instruction.md:5 any corpus with the same layout | CORRECT_CLI declared_input solve.py:43-50, resolve_policy wrapper solve.py:235, cmd_report solve.py:490; `check R11 ok` solve.py:1066 (3 handlers each raise; malformed policy_version_map.json rc 1 naming file) | negative_hardcoded_sample_answers | no: probe 4 R10 verdict, read_commands calls Path(value).is_file() on inline JSON -> OSError |
| R12 +5 | J6 | instruction.md:7 "state where each delivered artifact was written" | solve.sh:10-11 echo the seven paths; solve.py:852 `wrote /app/out/<name>` | none | yes: step 57 "Delivered artifacts (exactly seven)" |
| R13 -3 | J3a | factuality | stands down: every `check` line follows the run it reports | none | not fired: outputs FIELD SPECS OK, hashes shown |
| R14 -5 | J3b | factuality, final_answer | stands down: oracle prints no figure that differs | negative_transcript_disagrees_with_config reads report.json, not the reply | not fired: step 57 figures 285/3/2250/51 match config |
| R15 -3 | J3c | factuality, final_answer | stands down | none | not fired: step 57 states counts the trajectory shows (14 rejections step 56) |

Totals: 15 criteria; probes 9 (R1-R9) x 3 = 27 of 40 positive = 67.5 percent; negatives 11.
Judge estimate for Opus (LEVER_RULES section 6): lower = 5/40 = 12.5 (R12 only, probes absent from the log); mid = (R12 5 + 9 probes x 3 x 0.25 = 6.75) / 40 = 29.4; upper = (R12 5 + 27 probes + R10 3) / 40 = 87.5. Predicted final = (100 + 29.4) / 2 = 64.7.
Mid 29.4 is above the 28 target and below the 34 cap. It cannot go lower: positive total is locked to 40, a tenth probe makes the share 75 percent (cap 70), and the remaining 13 points must sit on J4 (w5), J6 (w5) and J10 (w3); J6 is the one enumeration the instruction asks for and Opus passes it.
