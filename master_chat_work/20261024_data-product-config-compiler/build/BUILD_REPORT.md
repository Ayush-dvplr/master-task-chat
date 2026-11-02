# BUILD_REPORT: data-product-config-compiler (board 13a9939)

Status: DONE. Bundle `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/data-product-config-compiler/`, tree_sha `b8acb6bb8bd7`.

Session rename: `name_session.py 13a9939` printed `codex: no match` and `opencode: ['ses_e91d07e10ffeL1KsK0NZMTDQp0']` (opencode session renamed; no retry).

## Tree
25 files, no bytecode. environment/ (Dockerfile + 15 data files), instruction.md (20 lines, 1856 chars), task.toml, solution/ (solve.sh, solve.py 384 lines, TRUTH.md 208 lines), tests/ (Dockerfile, test.sh, test_output.py 1325 lines, judge.toml 165 lines, reward.toml).

## Data (environment/data, 15 files, 10 formats, A5 own count 20,995 text lines)
| file | format | lines |
|---|---|---|
| config_contract.md | md | 172 |
| release_manifest.json | json | 606 |
| schema_registry.json | json | 53 |
| base_layer.yaml | yaml | 11 |
| products.ini | ini | 3,856 |
| owners.csv | csv | 3,666 |
| deprecation.log | log | 3,360 |
| selectors.rules | rules DSL | 39 |
| team_overrides.json | json | 122 |
| product_overrides.jsonl | jsonl | 9,075 |
| env_dev.toml / env_prod.toml | toml | 14 / 16 |
| cluster_quota.json | json | 5 |
| tool.zip | zip (cli.py, loaders.py, resolve.py, quota.py, emit.py, README.md) | binary |

Chains: C1 log id -> canonical form -> catalog -> status -> quota denominator -> every quota; C2 owners.csv + `RETIRE owner=` -> active owner -> team -> selectors/team overrides -> settings -> profiles; C3 override JSON value -> schema type -> accept/reject -> weight -> quota -> summary; C4 manifest compile_date -> --date -> owner activity -> status.

## Levers (rules all in /app/data/config_contract.md)
| lever | habit | rule at | hidden case | shipped separates? |
|---|---|---|---|---|
| LV-CC-1 owner active on D, log retires owners | H3 | L38-40 (glossary), L63-65 (log kinds) | 10+3 log-retired owners in weight-selector teams, 3 retired after D for date_shift | no (no `RETIRE owner=` shipped) |
| LV-CC-2 JSON value keeps its type | H1/L5 | L92-93 + L104-106 (stated twice) | quoted ints/bools incl. weight, bool-for-int, 30.0, 1e2 | yes (separating rows ship) |
| LV-CC-4 canonical ids in rarely joined log | H4/L10 | L28 | ~60% retire-product ids mixed-case/hyphenated | no (shipped log ids canonical) |
| COUPLING quota share | G1 | L131-135 | planted largest-remainder ties at the cut per doc | n/a |
LV-CC-3 (absent/null/empty list, L126-127) is graded work, not a lever (master accepted deviation). Planted defects P1-P6, L1, L2, L4 each break one quoted contract sentence (TRUTH.md Defect section).

## Grading
Tests 34 (33 positive, P = 125; 1 negative `negative_hardcoded_sample_answers` -5). 11 families visible w3 + `_hard` w5, mutations date_shift/quota_rescale/shuffled_relocated w5, robustness w3 (missing_input, invalid_date, catalog_mismatch, determinism, readonly_inputs, document_format, report_run), tool_zip_layout w1. Judge 12 criteria (positive 28; R11 honesty -3, R12 grader-read -5), batched header kept. reward.toml test_output 0.004, judge 0.0178571.
Shares: hidden/mutated reruns 70.4%, row-owned (isolated) 57.6%, whole-document 15.2%, shipped-only 29.6%. solve.py/test_output.py shared lines 7.8%.

## Cost table (measured, rubric 90)
| lever | alone lost | all-but-this overall | one-fact-wrong tests score |
|---|---|---|---|
| LV-CC-1 | 54.4% | 67.8 | 45.6% |
| LV-CC-2 | 68.0% | 61.0 | 74.4% |
| LV-CC-4 | 58.4% | 65.8 | 41.6% |
Master point 3 trigger (>=68) not fired; LV-CC-1 is the thinnest at 67.8. All wrong 20% tests (55.0 overall). RULE_COVERAGE 47 rows, 0 uncovered.

Expected loss: LV-CC-1 -> the 10 `_hard` families other than rejected_overrides_hard, date_shift, quota_rescale, shuffled_relocated, readonly_inputs; LV-CC-2 -> settings/quota/deploy/rejected/summary families visible and hard, quota_rescale, shuffled_relocated, readonly_inputs; LV-CC-4 -> all 11 `_hard` families, date_shift, quota_rescale, shuffled_relocated, readonly_inputs.

## Gates
- structure_qc, instruction_qc, tests_qc, judge_qc: exit 0, 0 FAIL (only WARN X1: tool.zip binary skipped).
- validate_bundle.py --archetype cli-config: 41 passed, 0 failed, 0 warnings, GATE PASS.
- Oracle (QL Docker procedure, harbor 0.24.0, tests channel): 1.0, 1.0, 1.0; nop 0.0. readonly_inputs passed as nobody from a foreign cwd with a read-only renamed data dir in all three trials (master point 4).
- STACKING PASS (OUT/STACKING_CHECK.md). precheck last line: `PRECHECK CLEAN`.
- GEN and QC fingerprints re-checked after the build: 160 + 12 files, 0 mismatches, heads unchanged. `scripts/__pycache__/master_queue.cpython-312.pyc` (20:00) in the harness clone is not from this build (gitignored, outside GEN/QC).

## Open conflicts
None. TRUTH Provenance keeps the scaffold-written block; validator 15.5 and QC DS-27 agree, so Q18 not needed.

## Not run
Live agent probe (master queues it); judge channel (no OPENAI_API_KEY locally).

## Lessons for the master
- stacking_check.py G3 counts only whole_doc/mutation/format names (12%) and misses `_hard` reruns (70.4%) | template_change: tools/stacking_check.py:264 count `_hard` names as hidden reruns
- validate_bundle 7.4 requires a negative named exactly `negative_hardcoded_sample_answers` | no change: worth one line in the build prompt Phase 4
- harbor run needs `-y` when task.toml carries verifier.env with an API key | template_change: knowledge/intake/ql_oracle_nop_procedure.md add `-y`
- LV-CC-1 alone sits at 67.8 even with 13 hidden log-retired owners; owner-scope levers need extra COUPLING weight early | no change: met the 68 line
