# aa314fee — Anjali Kumari; Sugam Agrawal (Expert)
Stage-2 accepted; final 17.64%, tests lost 64.0/66.0 positive weight (96.97%), test/judge final contributions 1.515/16.129 points (`inventory.csv`, reproduced by `scripts/inventory.py`).
## A. Lost checks and observed failure
- region_ledger_backbone_exact: weight 5.0, earned 0.0; The region documents carry the ledger backbone of every request with the governed customer, node, quantity, ceiling and claim exac (`tests/test_output.py:313`; `reward-details.json`, criterion `region_ledger_backbone_exact`).
- cumulative_shortfall_spine_exact: weight 5.0, earned 0.0; The carried shortfall spine is exact on every ledger row, including the carried in, carried out and running totals. (`tests/test_output.py:326`; `reward-details.json`, criterion `cumulative_shortfall_spine_exact`).
- site_cycle_capacity_and_fill_exact: weight 5.0, earned 0.0; Every site cycle reports the governing capacity, the fill level, the honoured minimum total, the grant, the residual and the bindi (`tests/test_output.py:340`; `reward-details.json`, criterion `site_cycle_capacity_and_fill_exact`).
- program_reproduces_unseen_extract_alpha: weight 5.0, earned 0.0; The delivered module rebuilds the ledger, the spine and the site cycle figures of a first unseen extract at another scale. (`tests/test_output.py:353`; `reward-details.json`, criterion `program_reproduces_unseen_extract_alpha`).
- program_reproduces_unseen_extract_beta: weight 5.0, earned 0.0; The delivered module rebuilds the ledger, the spine and the site cycle figures of a second unseen extract whose declarations leave (`tests/test_output.py:368`; `reward-details.json`, criterion `program_reproduces_unseen_extract_beta`).
- First verifier output: `reward: 0.1764` (`verifier/test-stdout.txt:1`). It contains no assertion difference; WRONG/TIMEOUT/CRASH is not separable from this log.
- Trajectory indexed steps: document reads 4:cd /app/data && cat corpus_index.md; program/run 33:cd /app/out && time python3 derive_report.py --data /app/data --out /app/out 2>&1 \| ; 56:cd /app/out && rm -f *.json && python3 derive_report.py --data /app/data --out /app/o; 60:cd /app/out && rm -rf __pycache__ && rm -f *.json && python3 derive_report.py --data . Cause requires source-level review; no misread is established by the score alone.
## B. Test construction and measurement
- Construction anchors: `tests/test_output.py:186` def _matches(out: Path, corpus: str, names) -> bool:; `tests/test_output.py:204` def _unpack(corpus: str, target: Path) -> None:.
- Comparison anchors: `tests/test_output.py:186` def _matches(out: Path, corpus: str, names) -> bool:; `tests/test_output.py:255` result["before"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest().
- Criterion-name hidden lower bound 18.0/66.0 positive weight; this is a lower bound only (names miss generated cases). Timeout literals in test code: 30;900 s. Test count 27; judge count 29.
## C. Wording and QC
- Instruction generalisation: `instruction.md:5` “'output_contract.md' fixes every key, every ordering and every spelling, and 'reason_codes.json' fixes the closed vocabularies; both bind to the letter. Each region document carrie”
- Agent-visible document sample: `environment/data/allocation_policy.md:5` “Each site cycle has a capacity in wafer equivalents and a set of claiming”. This sampled line is not assumed to cause the failure.
- Check wording: `tests/test_output.py:312` “@criterion(description="The region documents carry the ledger backbone of every request with the governed customer, node, quantity, ceiling and claim exactly right.")”.
- Judge wording: `tests/judge.toml:14` “description = "The response states that a run which holds every carried amount at zero hands out 2628151 wafer equivalents in total across the four site documents and moves 851 led”.
- QC mapping: IN-16/TS-19/DS-21 require a unique, learnable rule; IN-17 permits discovery from shipped data; AL-27 requires a firing witness; TS-11 applies to timing/seed stability; TS-26/JD-8/CL-4 require distinct observables and localised loss. Stage-2 presence is not evidence of a pass under our QC kit. Check TRUTH.md and shipped evidence before copying.
## D–F. Assessment
- Pattern P3: TRUTH.md:8 says shortfall carries across cycles, so one wrong decision reaches later ledgers. Its exact whole-ledger checks localise poorly; CL-4 requires independently graded partial views. ADAPT the carried-state fixture, not full-ledger stacking.
- Positive checks passed: artifacts_present_and_parse, program_runs_and_exits_clean.
- QL/PL: no task-local QL or PL note file found in this repo tree; acceptance means inclusion in stage-2 only.
- Measured property: the named weighted checks above; whether shipped data triggers them needs the cited generator and input files. Hidden failure mechanism and first differing field remain UNRESOLVED where stdout is reward-only.
- Transfer: ADAPT only after proving the rule from agent-visible data, a branch-fire witness, oracle correctness, and per-check isolation. Avoid adopting unexplained oracle-only expectations.
