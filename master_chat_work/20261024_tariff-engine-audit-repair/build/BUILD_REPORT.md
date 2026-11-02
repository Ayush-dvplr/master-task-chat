# BUILD_REPORT: tariff-engine-audit-repair (a5f8657, step P2)

Status: DONE. Bundle `master_chat_work/bundles/tariff-engine-audit-repair/` (29 files, tree sha d09c7bd1fda2 = first 12 hex of sha256 over sorted `path\0sha256(file)\n`). Work files: `master_chat_work/bundles/_work/tariff-engine-audit-repair/`. Archetype repo-patch, category software-engineering, seed 583917.
Session rename: `name_session.py a5f8657` printed "codex: no match / opencode: ['ses_e91db2f81ffe7tSGcxZWRtYaEZ']"; not retried.

## Tree
- environment/Dockerfile; environment/ci: api_contract.md (183 lines, the one contract), meter_reads.jsonl 10815, accounts.csv 3407, billing_periods.csv 2001, rate_card.json 109, regression_cases.jsonl 2000, failing_tests.log 14105, lint_report.json 2665, package_manifest.json, build_config.json
- environment/repo: README.md, pyproject.toml, src/tariff/{__init__,__main__,core,parser,report}.py (planted defects P1-P9), tests/test_visible.py (13 tests, asserts A and B contradict the contract)
- instruction.md (1680 chars), task.toml, solution/{solve.py 653 lines, solve.sh, TRUTH.md}, tests/{Dockerfile, test.sh, test_output.py, judge.toml, reward.toml}
- Data volume 35179 lines (A5: every csv/jsonl/log >= 2001). Formats: md, jsonl, csv, json, log, py, toml (7). Chains: read -> type check -> classify -> tier -> prorate -> round -> settle -> render.

## Levers (rule lives in environment/ci/api_contract.md)
| lever (contract lines) | wrong reading | tests alone | lost | all-but-one overall |
|---|---|---|---|---|
| LV-TR-4 quantity JSON integer (L56, L77-79) beside trim rule (L28-29) | quoted int coerced | 31/121 | 74.4% | 57.8 |
| LV-TR-3 month = billing period (L43-44, L108-110) | calendar / 30 days | 46/121, 30/121 | 62.0%, 75.2% | 64.0, 57.4 |
| LV-TR-2 exact decimal half-even per line (L42, L117-119) | half-up / floats | 46/121, 46/121 | 62.0% | 64.0 |
| LV-TR-2 partial: credit rounded separately (L121-125) | accepted partial | 96/121 | 20.7% | 84.7 |
| LV-TR-1 contract over visible tests (L3-5, L132-134) | amplifier | 115/121 | 5.0% | 92.5 |
COUPLING sentence verbatim at L121-123. Reflex program (TR-4+TR-3+TR-2 together) 26/121. One fact wrong (one line +0.01 on one hidden account): fresh account 91/121, api account 106/121 (energy, standing and one quoted read each measured).

## Tests and judge
- Tests 31: 29 positive (121 points), negatives negative_hardcoded_sample_answers -5, negative_visible_test_removed -3. Shares: whole_doc 20.7%, mutation 54.5%, shipped_only 12.4%, isolated 12.4%; hidden or mutated 75.2%.
- Judge 11 criteria (R1-R8 positive w3 = 24; R9 honesty -5, R10 runs on edited contract copy -3, R11 grader paths -5), batched. solve.sh self-check prints `check R1 ok` .. `check R8 ok`. JUDGE_MAP.md written.
- R10 retargeted per master change 4: in the built image uid 1000 got `Permission denied` appending to /app/ci/api_contract.md.
- Deviation from master change 6: 29 positive checks / 121 points instead of 25 / 111; the api corpus trio was added so rounding and calendar misreads each lose >50% (G10).

## Results
- QC kit: structure 17/0/0, instruction 5/0/0, tests 36/0/0 (O1 overlap 8%), judge 19/0/0; validate_bundle --archetype repo-patch 41 passed 0 failed, GATE PASS.
- Oracle (harbor 0.24.0, QL procedure, tests channel): 1.0, 1.0, 1.0; nop 0.0. Local run_checks oracle 121/121.
- TS-16: both negatives unfired for oracle, 8 lever variants, 4 one-fact variants, 51 rule mutants; negative_hardcoded_sample_answers fires on the hard-code cheat (C_hardcode_shipped).
- RULE_COVERAGE.md: 51 rules, 0 uncovered. Stacking: OUT/STACKING_CHECK.md, STACKING PASS.
- PRECHECK CLEAN. No bytecode in bundle.

## Expected loss
Most likely loss for a careful solver: LV-TR-3 (calendar month, shipped periods are calendar months), then LV-TR-4 (trim rule blesses quoted integers), then LV-TR-2 (no shipped ties). Shipped data cannot separate calendar month, half-up, floats or credit rounding (check_exact.py probes), by design (W5); only the quoted-integer rows and /30 separate on shipped data.

## Open conflicts
None. TRUTH.md provenance kept scaffold keys; validator 15.5 and DS-27 agree on forbidden keys, so no Q18 entry.

## Not run
playground.py (removed upstream; A5 volume checked by datagen.py). Judge channel not executed (needs OPENAI key); private probe run pending.

## Lessons for the master
active meter with only rejected reads was absent from corpora so the "every meter billed" rule was uncovered until mutant M29 | no change: caught by RULE_COVERAGE loop
validate_bundle repo-patch requires the negative name negative_hardcoded_sample_answers | template_change: prompts/templates/_COMMON_RULES_v3.md: name the required negative for repo-patch
credit computed on rounded line sums is insensitive to line rounding, so a rounding lever needs its own whole-line checks on several corpora | no change: recorded in COST_TABLE.md
