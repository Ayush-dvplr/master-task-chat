# ceadc676 — Aryan Mehta; Poonam Chourey (Medium)
Stage-2 accepted; final 42.02%, tests lost 65.0/71.0 positive weight (91.549%), test/judge final contributions 4.225/37.791 points (`inventory.csv`, reproduced by `scripts/inventory.py`).
## A. Lost checks and observed failure
- heldout_reseed_exact: weight 5.0, earned 0.0; Rerun on a reseeded batch with other sessions, revisions, jams and rulings, every report is exact (`tests/test_output.py:3883`; `reward-details.json`, criterion `heldout_reseed_exact`).
- heldout_spring_exact: weight 5.0, earned 0.0; Rerun on a spring batch across a skipped clock hour with a pause typed inside it and the 1900 date system, every report is exact (`tests/test_output.py:3888`; `reward-details.json`, criterion `heldout_spring_exact`).
- heldout_zone_exact: weight 5.0, earned 0.0; Rerun on a batch under another site clock with a negative base offset, every report is exact (`tests/test_output.py:3893`; `reward-details.json`, criterion `heldout_zone_exact`).
- heldout_memo_exact: weight 5.0, earned 0.0; Rerun on a batch whose memo changes the reference sets, limits, thresholds, windows and tolerances, every report is exact (`tests/test_output.py:3898`; `reward-details.json`, criterion `heldout_memo_exact`).
- heldout_profile_exact: weight 5.0, earned 0.0; Rerun on a batch whose profile changes the certified sheet, drift material, element order and fit settings, every report is exact (`tests/test_output.py:3903`; `reward-details.json`, criterion `heldout_profile_exact`).
- First verifier output: `reward: 0.4202` (`verifier/test-stdout.txt:1`). It contains no assertion difference; WRONG/TIMEOUT/CRASH is not separable from this log.
- Trajectory indexed steps: document reads 4:cat /app/data/method_handbook.md; 5:cat /app/data/feed_layouts.md; 6:cat /app/data/output_contract.md; 7:cat /app/data/rerun_pack.md; echo ==========; cat /app/data/analysis_profile.yml; ech; program/run 27:mkdir -p /app/out && cat > /app/out/run_irms.py <<'PYEOF'
#!/usr/bin/env python3
"""R; 31:cat >> /app/out/run_irms.py <<'PYEOF'


# -------------------------------------------; 33:cat >> /app/out/run_irms.py <<'PYEOF'


# -------------------------------------------. Cause requires source-level review; no misread is established by the score alone.
## B. Test construction and measurement
- Construction anchors: `tests/test_output.py:3387` def _Ggenerate(data, seed: int, over: dict \| None = None) -> dict:; `tests/test_output.py:3480` def _corpus(name: str) -> tuple:; `tests/test_output.py:3693` def _all_exact(out, corpus: str, names) -> bool:.
- Comparison anchors: `tests/test_output.py:1022` # ============================================================================ reference derivation; `tests/test_output.py:3693` def _all_exact(out, corpus: str, names) -> bool:.
- Criterion-name hidden lower bound 41.0/71.0 positive weight; this is a lower bound only (names miss generated cases). Timeout literals in test code: 120 s. Test count 34; judge count 35.
## C. Wording and QC
- Instruction generalisation: `instruction.md:1` “The stable isotope facility published batch HSI-2611, d15N versus AIR and d13C versus VPDB from two EA-IRMS lines, from the saved rerun pack '/app/data/rerun_pack.md'. The publishe”
- Agent-visible document sample: `environment/data/feed_layouts.md:3` “Every shard is a peak export. The catalog names the layout of each file in its REGISTER events; file names carry no meaning.”. This sampled line is not assumed to cause the failure.
- Check wording: `tests/test_output.py:3747` “@criterion(description="The program run_irms.py, all twenty-one contract reports and manifest.json exist under /app/out")”.
- Judge wording: `tests/judge.toml:14` “description = "The agent rebuilds each table row of governance_memo.pdf from the text objects of one page that share a y coordinate."”.
- QC mapping: IN-16/TS-19/DS-21 require a unique, learnable rule; IN-17 permits discovery from shipped data; AL-27 requires a firing witness; TS-11 applies to timing/seed stability; TS-26/JD-8/CL-4 require distinct observables and localised loss. Stage-2 presence is not evidence of a pass under our QC kit. Check TRUTH.md and shipped evidence before copying.
## D–F. Assessment
- Pattern P2: Generated fresh packs vary seeds and carrier settings (generator anchor above); only form/manifest checks pass in the recorded run. The exact core reports fail, so the record does not prove the carrier variation alone defeated a correct solver. ADAPT one legal carrier variant at a time with a value-preservation proof; avoid hidden forms absent from the contract.
- Positive checks passed: deliverables_present, program_writes_contract_files, delimited_headers_exact, json_report_keys, manifest_consistent, text_serialization.
- QL/PL: no task-local QL or PL note file found in this repo tree; acceptance means inclusion in stage-2 only.
- Measured property: the named weighted checks above; whether shipped data triggers them needs the cited generator and input files. Hidden failure mechanism and first differing field remain UNRESOLVED where stdout is reward-only.
- Transfer: ADAPT only after proving the rule from agent-visible data, a branch-fire witness, oracle correctness, and per-check isolation. Avoid adopting unexplained oracle-only expectations.
