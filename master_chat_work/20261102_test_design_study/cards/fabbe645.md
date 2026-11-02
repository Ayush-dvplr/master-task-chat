# fabbe645 — Aditya Joshi; Dinshi Jain (Medium)
Stage-2 accepted; final 45.84%, tests lost 107.0/113.0 positive weight (94.69%), test/judge final contributions 2.655/43.182 points (`inventory.csv`, reproduced by `scripts/inventory.py`).
## A. Lost checks and observed failure
- kolhapur_sizes: weight 5.0, earned 0.0; Kolhapur replica sizes are the exact byte counts of the binary index, never the catalogue sector counts (`tests/test_output.py:2356`; `reward-details.json`, criterion `kolhapur_sizes`).
- ratnagiri_hex_sizes: weight 5.0, earned 0.0; Ratnagiri rows from the shards that carry a hexadecimal size field have exact byte sizes (`tests/test_output.py:2374`; `reward-details.json`, criterion `ratnagiri_hex_sizes`).
- margao_base32_digests: weight 5.0, earned 0.0; Margao rows from the shard with Base32 digests carry the right SHA-256 digest (`tests/test_output.py:2379`; `reward-details.json`, criterion `margao_base32_digests`).
- kolhapur_renditions: weight 5.0, earned 0.0; Kolhapur rows carry the rendition named by the rendition letter in force (`tests/test_output.py:2384`; `reward-details.json`, criterion `kolhapur_renditions`).
- legacy_collections: weight 5.0, earned 0.0; Margao rows filed under legacy collection ids resolve to the current id by catalogued date (`tests/test_output.py:2388`; `reward-details.json`, criterion `legacy_collections`).
- First verifier output: `_check_decommissioned_node: fewer than half of the Nashik rows are listed
_check_required_replicas: too few single collection objects can be graded
_check_kolhapur_sizes: fewer than half of the Kolhapur rows are listed
_check_ratnagiri_hex_sizes: few` (`verifier/test-stdout.txt:1`). Inspect subsequent stdout for per-check evidence.
- Trajectory indexed steps: document reads none located by command search; program/run 26:cd /app && time python3 /app/out/optimize.py --data /app/data --out /tmp/t1 && ls -la; 28:cd /app && time python3 /app/out/optimize.py --data /app/data --out /tmp/t1 && ls -la; 31:cd /tmp && rm -rf t2 d2 t3 && cp -r /app/data /tmp/d2 && python3 /app/out/optimize.py. Cause requires source-level review; no misread is established by the score alone.
## B. Test construction and measurement
- Construction anchors: no named generator located.
- Comparison anchors: `tests/test_output.py:2059` found[entry.name] = entry.read_bytes(); `tests/test_output.py:2290` return mine == ref.
- Criterion-name hidden lower bound 4.0/113.0 positive weight; this is a lower bound only (names miss generated cases). Timeout literals in test code: 10;20 s. Test count 32; judge count 12.
## C. Wording and QC
- Instruction generalisation: `instruction.md:1` “Hello, this is the archive desk at Konkan Coast Broadcast Archive. Our four tape vaults hold more copies of the digitised masters than the retention charter asks for, and the next ”
- Agent-visible document sample: `environment/data/archive_desk_brief.md:9` “vaults than the retention charter asks for, while some files never reached enough vaults. Each”. This sampled line is not assumed to cause the failure.
- Check wording: `tests/test_output.py:3016` “@criterion(description="Kolhapur replica sizes are the exact byte counts of the binary index, never the catalogue sector counts")”.
- Judge wording: `tests/judge.toml:14` “description = "The agent compares the byte size and SHA256 digest of each shipped input file with its entry in /app/data/estate_census.toml during the session, before it reports th”.
- QC mapping: IN-16/TS-19/DS-21 require a unique, learnable rule; IN-17 permits discovery from shipped data; AL-27 requires a firing witness; TS-11 applies to timing/seed stability; TS-26/JD-8/CL-4 require distinct observables and localised loss. Stage-2 presence is not evidence of a pass under our QC kit. Check TRUTH.md and shipped evidence before copying.
## D–F. Assessment
- Pattern P5: The instruction promises full-size completion under 60 seconds (instruction.md:19). Stdout says “the full size run did not finish cleanly”; that combines timeout, crash and missing output, so TIMEOUT is suspected but not proven. TS-11 requires a generous measured oracle margin.
- Positive checks passed: census_hold, visible_outputs.
- QL/PL: no task-local QL or PL note file found in this repo tree; acceptance means inclusion in stage-2 only.
- Measured property: the named weighted checks above; whether shipped data triggers them needs the cited generator and input files. Hidden failure mechanism and first differing field remain UNRESOLVED where stdout is reward-only.
- Transfer: ADAPT only after proving the rule from agent-visible data, a branch-fire witness, oracle correctness, and per-check isolation. Avoid adopting unexplained oracle-only expectations.
