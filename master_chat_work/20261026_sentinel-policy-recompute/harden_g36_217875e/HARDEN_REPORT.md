# HARDEN_REPORT: sentinel-policy-recompute, gate v3.6 (board 217875e)

Status DONE. The test lever is unchanged (P-1 ledger_repair hidden-scale TIMEOUT, 28/146 = 19.18%). This round rebuilt the judge band and merged the held QC v7 fixes F1, F2, F3, F5 and F6. F4 was not applied (option A).
Session rename: `name_session.py 217875e` printed "codex: no match / opencode: ['ses_e81a923efffe6XWw3cIfaiXsE9']". 217875e was not in the list, so I did not retry.

## Arithmetic before / after
| | tests | rubric | final |
|---|---|---|---|
| before: a7 run 07363dd (tree f8c5f625cf1d), measured | 117/145 = 80.69 | 8/41 = 19.51 | 50.10 |
| after: a7 program rescored on the final tests (Docker), a7 trajectory re-graded by hand on the new judge | 118/146 = 80.82 (measured) | 3/37 = 8.11 | 44.47 |
| after, R12 counted as passed (master ask) | 118/146 = 80.82 | 4/37 = 10.81 | **45.82** |
| after, R12 and R13 passed | 118/146 = 80.82 | 7/37 = 18.92 | 49.87 |

Target: tests < 85, rubric < 85, final < 50. The master's ask was rubric <= 12 and final <= 46.5. Both are met at the a7 prediction (10.81 / 45.82).

## New sentences
- instruction.md:7 (F5, IN-L2): "It must also record whether every delivered artifact is present and whether the configuration matches the resolved policy."
- TRUTH.md:52 (F6): the cite is now `override_precedence.conf:8`. TRUTH counts are 40 checks / P 146 / neg -14, judge 16 criteria 37 / -11. Sha refreshed by truth_sha.py.
- judge.toml R12 description: "The agent leaves a maintainable /app/tool/cli.py in which a reference file that is unreadable or unparsable stops the run with an error message naming that file."

## Checks and criteria changed (file:line)
- tests/test_output.py:1677 `test_shipped_config_carries_policy_values` w3, and :1683 `test_shipped_profiles_carry_policy_deltas` w3 (F3 split of the old w5 check; the rebuild bytes assert was deleted). Criteria are at :1972/:1977 and registrations at :2056-2057. Every other body is byte-unchanged. The lever checks are :1563, :1592, :1597, :1602, :1607 (w5 each) and :1612 (w3).
- tests/judge.toml (16 criteria, +37 / -11):

| criterion | line | weight | change |
|---|---|---|---|
| R1 r1_runs_shipped_tool_before_first_edit | :11 | 1 | unchanged |
| R2-R5 | :24-:63 | 3 each | unchanged |
| R6-R8 recomputes timeout / threshold / prod value separately | :76, :89, :102 | 3 important | F2 (back to w3) |
| R9 names defect before first edit | :115 | 3 | unchanged |
| R10 r10_rerun_with_changed_version_map | :128 | 3 | new probe (old R10 dropped, F1) |
| R11 r11_rerun_with_changed_unit_cutover | :141 | 3 | new probe |
| R12 r12_cli_names_unreadable_reference_file | :154 | 1 important, state_change | new code-quality criterion (JD-18). CL-2: FALSE on the shipped cli.py, which raises a raw TOMLDecodeError/JSONDecodeError that does not name the file (Docker) |
| R13 r13_response_lists_every_artifact_path | :167 | 3 | unchanged |
| R14 J3a / R15 J3b / R16 J3c | :180, :193, :206 | -3 / -5 / -3 | unchanged |

- tests/reward.toml weights = { test_output = 1/146, judge = 1/37 }.
- solution/solve.py self_check_probes: version-map rerun :1179 (v100 -> v099), unit-cutover rerun :1187 (2250 -> 2857), unreadable input :1218 (kept). Prints are plain (DS-17).
- Deviation: R12 type is `agent behavior`, not the code-quality label the master asked for. judge_qc.py:122-125 CATEGORIES has no code-quality label, and putting it under task completion was a vendor v5:35 minor. This is recorded in WORK/QC_DEFENCE.md.

## Kill table (final tests, Docker 4g/2cpu, measured)
| program | tests | lever kept |
|---|---|---|
| a7 agent program | 0.8082 | 0/28 TIMEOUT x6 |
| blind b1f1 | 0.6644 | 0/28 |
| blind 7230 | 0.7877 | 0/28 |
| blind d6d5 | 0.8082 | 0/28 TIMEOUT x6 |
| harden_t3 generic solvers (greedy, naive, tables, halves) | 0.8082 (arithmetic; lever byte-unchanged) | 0/28 |

The reference takes at most 0.26 s per corpus against the 60 s limit.

## Counts and weight shares
40 checks (TS-23 cap 35 is a warn under option A), P 146, neg -14. Shares: hidden_rows 118 (80.8%), shipped_only 16 (11.0%), mutation 9 (6.2%), isolated 3 (2.1%); G3 87.0%; lever 19.18%. Judge 16 criteria, +37 / -11. See STACKING_CHECK.md (STACKING PASS; the AL-28 UNMATCHED row was split by hand into 7 acts, each <= 5).

## Measured cost table
- run program (all but one: a7, d6d5): 0.8082 measured. Blind range 0.6644-0.8082.
- cost_first_write_tests 0.6489 and cost_all_but_one 0.9008 are harden_t3 measured values on P131. They were not re-measured this round because the lever, corpora and checks are unchanged.
- CL-4 one fact wrong (arithmetic): `requires` misread 130/146 = 0.890; one wrong shipped timeout 137/146 or 140/146.
- F3 isolation (Docker): config.json max_records +1 scored 0.9384. It fails the config check, the report digest check (pre-existing TS-13 read) and the transcript negative; the profiles check passes. profile_dev.json +1 scored 0.9795 and fails only the profiles check.

## Judge band, predicted run score
| band | rubric | final with tests 80.82 |
|---|---|---|
| a7 trajectory, strict | 8.11 | 44.47 |
| a7 + R12 (prediction used) | 10.81 | 45.82 |
| a7 + R12 + R13 | 18.92 | 49.87 |
| generic probe-rate mid (25% of probes, R12 + R13 passed) | 33.1 | 56.96 (over 50) |

The a7-trajectory prediction meets the gate. The generic mid would not. The margin depends on Opus skipping the R10/R11 probes as a7 did.

## Gates
- PRECHECK last line: `PRECHECK CLEAN`.
- QC: structure_qc 17/1 warn (X1 binary) /0 fail; instruction_qc 5/0/0 PASS; tests_qc 36/1 warn (A3 40>35) /0 fail; judge_qc 19/0/0 PASS. qc_fail 0. Outputs are in qc/.
- validator: 38 passed, 10 failed. The same 10 FAILs appear on the pre-round Tasks_INPUT copy (qc/validator_base.txt), so none were introduced here.
- xref_check: 94 entries, 0 findings.
- Docker chain (manual equivalent from exe_copy copies; Harbor CLI not used), ALL_DONE 23:12:51: oracle 1.0 / 1.0 / 1.0, owner 1.0, nop 0.0, stub 0.0, forgery 0.1164.
  - The forgery rose from t3's 0.0153 because the forge keeps the oracle's shipped artifacts and so passes the 8 shipped/cli checks (22 points). That comes from the shipped check weights set in QC v4-v7, not from this round. It fails all hidden and mutation points, and the hardcode negative fires.
- Rescore ALL_DONE 23:24:29. Log: /tmp/opencode-logs/sentinel-policy-recompute-g36-217875e/.

## Tasks_INPUT
6 files differed before the sync: instruction.md, solution/TRUTH.md, solution/solve.py, tests/judge.toml, tests/reward.toml, tests/test_output.py. After `cp -Rp`, `diff -rq` is empty. Tree sha is f5e0d873e6c6 (67 paths, t3 method).

## Not run
- Harbor CLI / harness run (manual Docker chain instead).
- No new kill test or first-write cost measurement (lever unchanged, master note 4).
- No real Opus judge run; the rubric figures are hand predictions.
- The CL-4 one-fact-wrong figures are arithmetic.

## Lessons for the master
- A code-quality criterion on the declared artifact adds +1 to the rubric numerator for a careful agent. Keep it at w1.
- judge_qc has no code-quality category label; the J7 list needs one, or the "agent behavior" ruling should be standing.
- Shipped-artifact checks raise the forgery floor (0.1164); watch it against the forgery cap if more shipped checks are added.
- The rubric margin rests on probe criteria; a probe-heavy agent lands near the generic mid of 33 and a final of about 57.
- The F3 split makes the config and profile failures isolable (verified 0.9384 / 0.9795).
