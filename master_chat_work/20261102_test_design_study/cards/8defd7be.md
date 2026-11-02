# 8defd7be — Sanvi Gupta; Sugam Agrawal (Expert)
Stage-2 accepted; final 9.06%, tests lost 81.0/83.0 positive weight (97.59%), test/judge final contributions 1.205/7.857 points (`inventory.csv`, reproduced by `scripts/inventory.py`).
## A. Lost checks and observed failure
- full_ledger_on_unseen_run_alpha: weight 5.0, earned 0.0; POSITIVE: the three reports match the reference ledger on an unseen catalogue run. (`tests/test_output.py:1562`; `reward-details.json`, criterion `full_ledger_on_unseen_run_alpha`).
- full_ledger_on_unseen_run_bravo: weight 5.0, earned 0.0; POSITIVE: the three reports match the reference ledger on a second unseen catalogue run. (`tests/test_output.py:1567`; `reward-details.json`, criterion `full_ledger_on_unseen_run_bravo`).
- full_ledger_on_unseen_run_charlie: weight 5.0, earned 0.0; POSITIVE: the three reports match the reference ledger on a third unseen catalogue run. (`tests/test_output.py:1572`; `reward-details.json`, criterion `full_ledger_on_unseen_run_charlie`).
- full_ledger_on_unseen_run_delta: weight 5.0, earned 0.0; POSITIVE: the three reports match the reference ledger on a fourth unseen catalogue run. (`tests/test_output.py:1577`; `reward-details.json`, criterion `full_ledger_on_unseen_run_delta`).
- full_ledger_on_unseen_run_echo: weight 5.0, earned 0.0; POSITIVE: the three reports match the reference ledger on a fifth unseen catalogue run. (`tests/test_output.py:1582`; `reward-details.json`, criterion `full_ledger_on_unseen_run_echo`).
- First verifier output: `reward: 0.0906` (`verifier/test-stdout.txt:1`). It contains no assertion difference; WRONG/TIMEOUT/CRASH is not separable from this log.
- Trajectory indexed steps: document reads 4:cat /app/data/broker.md; 5:cat /app/data/reports.md; echo ====; cat /app/data/pools.csv; echo ====; cat /app/dat; 6:head -3 /app/data/lookups.jsonl; echo ====; cat /app/data/ref_catalog.json; echo ====; program/run 9:rm /app/out/x; mkdir -p /tmp/work && cd /tmp/work && python3 -c "
import json,csv,col; 41:cd /tmp && rm -rf o1 o2 && python3 /app/out/broker.py /app/data /tmp/o1 && python3 /a. Cause requires source-level review; no misread is established by the score alone.
## B. Test construction and measurement
- Construction anchors: `tests/test_output.py:1330` def _case_for(label, seed):.
- Comparison anchors: `tests/test_output.py:1386` assert _artifact(out, name) == expected[name], "%s disagrees with the reference" % name; `tests/test_output.py:1393` assert _artifact(out, report) == expected[report], "%s disagrees with the reference" % report.
- Criterion-name hidden lower bound 56.0/83.0 positive weight; this is a lower bound only (names miss generated cases). Timeout literals in test code: none extracted s. Test count 42; judge count 32.
## C. Wording and QC
- Instruction generalisation: `instruction.md:3` “The written notes in '/app/data/broker.md' and '/app/data/reports.md' describe the shape of the engine and the shape of its three reports. They give the input columns, the ten piec”
- Agent-visible document sample: `environment/data/broker.md:5` “engine itself went with the broker controller when the controller was retired.”. This sampled line is not assumed to cause the failure.
- Check wording: `tests/test_output.py:1705` “@criterion(description="POSITIVE: driven with an input and an output directory the program writes the three documented reports.")”.
- Judge wording: `tests/judge.toml:14` “description = "The agent writes /app/out/broker.py to disk before the last command in which it tests a candidate constant against the shipped rollups."”.
- QC mapping: IN-16/TS-19/DS-21 require a unique, learnable rule; IN-17 permits discovery from shipped data; AL-27 requires a firing witness; TS-11 applies to timing/seed stability; TS-26/JD-8/CL-4 require distinct observables and localised loss. Stage-2 presence is not evidence of a pass under our QC kit. Check TRUTH.md and shipped evidence before copying.
## D–F. Assessment
- Pattern P3: TRUTH.md:3-20 withholds roughly fifty constants and functional forms; TRUTH.md:121-127 gives only a local sweep. The hypothesis space is not bounded in agent-visible files. AVOID under DS-21/IN-16, despite stage-2 acceptance.
- Positive checks passed: program_writes_the_three_reports_from_two_directory_arguments, report_serialization_carries_the_documented_byte_form.
- QL/PL: no task-local QL or PL note file found in this repo tree; acceptance means inclusion in stage-2 only.
- Measured property: the named weighted checks above; whether shipped data triggers them needs the cited generator and input files. Hidden failure mechanism and first differing field remain UNRESOLVED where stdout is reward-only.
- Transfer: ADAPT only after proving the rule from agent-visible data, a branch-fire witness, oracle correctness, and per-check isolation. Avoid adopting unexplained oracle-only expectations.
