# BUILD_REPORT 57a2dd7 cold-chain-backbone-quote

Status: DONE (BUILD READY, no probe run, per master go item 11).
Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/` (30 files, tree_sha 9b9b10478339)
Work: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote/`
Session rename: `name_session.py 57a2dd7` printed `codex: no match` and `opencode: ['ses_e8d348d88ffeIQOmrg62B56iIe']`.

## Tree

```
environment/Dockerfile
environment/ci/{api_contract.md, sites.csv, layout.tsv, links.jsonl, access_rules.toml, activation.ini,
               regression_cases.jsonl, failing_tests.log, lint_report.json, package_manifest.json, build_config.json}
environment/repo/{README.md, pyproject.toml, src/task/{__init__,__main__,core,parser,report}.py, tests/test_visible.py}
instruction.md  task.toml
solution/{solve.py, solve.sh, TRUTH.md}
tests/{Dockerfile, test.sh, test_output.py, judge.toml, reward.toml}
```

## Data (environment/ci, 11 files, 8 formats: md csv tsv jsonl toml ini json log)

| file | lines |
|---|---|
| sites.csv | 3450 |
| layout.tsv | 3352 |
| links.jsonl | 5873 |
| regression_cases.jsonl | 2400 |
| failing_tests.log | 8155 |
| lint_report.json | 4485 |
| activation.ini | 1926 |
| access_rules.toml | 228 |
| api_contract.md | 164 |
| build_config.json | 20 |
| package_manifest.json | 15 |
| total | 30068 (A5: >= 20,000 total, every csv/tsv/jsonl/log >= 2,000) |

Shipped book: 96 projects (90 accepted, 6 rejected covering all 4 codes), 18 to 52 sites, up to 94 links, 4 to 10 cold rooms,
every accepted project with a single optimum. No quote, network or expected value anywhere in environment/ (W11, G-7).

Chains (length >= 4):
1. sites.csv class -> activation.ini class charge or `<project>/<site>` override -> site activation -> quote -> share_bp -> summary.
2. links.jsonl band, km -> access_rules.toml tariff and [closed] -> open link cost -> minimum network -> quote -> every report total.
3. layout.tsv corridor, slot -> access_rules.toml corridor order -> corridor position -> E_BAD_SPAN and link booking -> site/corridor totals.
4. failing_tests.log FAIL/ERROR lines + regression_cases.jsonl -> package outcomes -> test_fixes.json.

## Levers

| lever | written in | measured loss alone (of 84) | overall |
|---|---|---|---|
| LV-CC-1 exact minimum-cost network (wrong: KMB / greedy attach) | api_contract.md:80-92, shipped core.py KMB | 63 (75.0%) | 57.5 |
| LV-CC-2 runtime at 16-17 cold rooms (wrong: tuned Dreyfus-Wagner) | api_contract.md:94-96 Limits sentence | 54 (64.3%) | 62.9 |
| LV-CC-3 activation once per activated site, carried into totals | api_contract.md:84-85, 100-108; shipped core.site_lines | 69 helper (82.1%), 43 report-only (51.2%, secondary) | 53.9 / 69.4 |

Docker timings (python:3.12-slim, 2 cpus, seconds per project, 47-52 sites): reference 0.010-0.16 at every count;
tuned DW 0.5 (12), 1.4-1.7 (13), 4.8 (14), 13.1-15.4 (15), 41.4 (16), 128.2 (17); prototype DW 237.8 at 17.
Per-book limit 4 s x projects + 10 s; oracle Docker 0.23-0.38 s per book.

## Tests and judge

tests 26 (24 positive, 84 points; negatives negative_hardcoded_sample_answers -5, negative_visible_tests_removed -3);
judge 10 criteria (positive 20, R9 -5, R10 -3), batched. reward.toml test_output 0.005952380952380952, judge 0.025.
Shares of positive test weight: hidden or mutated 78.6%, whole-document 85.7%, shipped-only 19.0%, isolated 2.4%, tie 3.6%.
G12: 300 seeds of the hidden generator, no crash, bounds asserted, every branch planted, worst reference 0.025 s.
RULE_COVERAGE 42 rows, 0 uncovered; EVIDENCE_MAP 24 rows; LEVERS.md covers all 26 checks.

## Script results

- structure_qc, instruction_qc, tests_qc, judge_qc: VERDICT PASS each, 0 warns.
- validate_bundle.py --archetype repo-patch: 41 passed, 0 failed, 0 warnings, GATE PASS.
- check_exact.py: 2400 regression cases by enumeration, 90 book projects vs Dreyfus-Wagner, tie book picks by enumeration: CHECK_EXACT PASS.
- Oracle x3 (harbor run, judge removed, QL procedure): 1.0, 1.0, 1.0. Nop: 0.0. (WORK/runs/harbor/)
- N1 silent for oracle, kmb, greedy, tuned DW, perlink, report_only; fires only for the copier (WORK/runs/variants.log).
- Stacking: STACKING PASS (OUT/STACKING_CHECK.md).
- Fingerprints re-checked at end: generator 160 files diff 0, QC 12 files diff 0.
- precheck.sh last line: `PRECHECK CLEAN`

## Expected loss

Per lever as measured with one-lever-wrong programs: LV-CC-1 63/84, LV-CC-2 54/84, LV-CC-3 69/84 (43/84 report-only).
A first program that keeps the shipped KMB core and fixes the parser scores about 21/84; a correct node-weighted DW
scores about 30/84 (exact on the shipped book, over the time limit on fresh books).

## Open conflicts

None. VB 15.5 and DS-27 did not disagree (TRUTH carries no forbidden keys or narration; validator PASS).

## Not run

Probe run, P13 blind reads and loss.py (master issues them). Judge channel not run (rubric taken as 90 in the cost table).

## Lessons for the master
lesson: validate_bundle requires the hardcoded negative to be named negative_hardcoded_sample_answers | template_change: add the name to LEVER_RULES_v2 G4
lesson: harbor run prompts on [verifier.env] OPENAI_API_KEY and aborts under nohup; pass -y | template_change: ql_oracle_nop_procedure.md harbor run line
lesson: a CPython DW with big-int sentinels runs slower than a float one; benchmark the tuned DW with small ints before calling LV-CC-2 safe | no change: build-specific
lesson: a judge negative on hardcoding stacks with the test negative on the same act (AL-28); pick a different act for the judge | no change: stacking_check catches it
