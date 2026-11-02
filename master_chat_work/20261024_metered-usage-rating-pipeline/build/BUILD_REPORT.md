# BUILD_REPORT: metered-usage-rating-pipeline (board b5f7557, step P2)

Status: DONE. Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/metered-usage-rating-pipeline/`
(tree sha 212f389aeb8d). Work files: `master_chat_work/bundles/_work/metered-usage-rating-pipeline/`.

Session rename: `name_session.py b5f7557` ran at 16:12:53 IST and printed `codex: no match` /
`opencode: ['ses_e927ed24cffe3mOOnAOsDv0HIU']`; the list did not show b5f7557 by name. Not retried.

## Tree (23 files)

- `instruction.md`, `task.toml`
- `environment/Dockerfile`, `environment/data/` (12 files, below)
- `solution/TRUTH.md`, `solution/solve.py` (343 lines), `solution/solve.sh` (copies solve.py to
  /app/out/transform.py, runs it, then a heredoc self-check stage printing `check R1 ok` .. `check R7 ok`, `check R10 ok`)
- `tests/Dockerfile`, `tests/test.sh`, `tests/test_output.py` (1349 lines; embedded shipped data,
  reference engine and seeded generator, hidden seed only here), `tests/judge.toml`, `tests/reward.toml`

## Data (environment/data, 12 files, 9 formats, 21,054 lines)

| file | format | lines |
|---|---|---|
| rating_contract.md | markdown, the one contract (W10) | 196 |
| collector_central.csv | csv | 3,233 |
| collector_east.tsv | tsv, epoch seconds | 3,233 |
| collector_north.jsonl | jsonl | 3,232 |
| collector_south.txt | fixed width, Latin-1 | 3,232 |
| collector_west.log | key=value log, ISO offsets | 3,232 |
| accounts.csv | csv | 2,406 |
| plan_changes.log | log | 2,208 |
| rate_card.json | json | 33 |
| commitments.xml | xml | 8 |
| products.ini | ini | 31 |
| collector_controls.json | json (honest record-count control) | 10 |

Chains (length >= 4): C1 products.ini name -> collector row -> rate_card tier by cumulative account units
across all collectors -> charge -> region credit base -> every committed line's credit -> region,
segment, product, summary reports. C2 plan_changes.log id (canonical form) -> plan/segment in force
at line timestamp -> segment rate -> charge -> credit base -> credit. C3 collector_controls month ->
west UTC conversion -> timestamp_outside_month -> data_quality + accepted set -> tier counters.
C4 commitments pool -> credit base glossary -> per-line credit -> net -> all reports.

## Levers (from WORK/LEVERS.md)

| lever | habit | rule written in | weight carried (of 199) |
|---|---|---|---|
| LV-MU-1 north `units` is a JSON integer, beside the global trim rule | H1/L5 | rating_contract.md, Collector files: north block + text-units sentence | 189 (95.0%) |
| LV-MU-2 exact decimal, half-even per line at 0.01 (charge and credit) | H2/L8 | rating_contract.md, Rating charge sentence and Credit sentence | 110 (55.3%) |
| LV-MU-3 credit base = committed lines at the line timestamp | H3/L9 | rating_contract.md, Glossary, credit base | 133 (66.8%) |
| LV-MU-4 account ids upper-case + hyphens removed, matters only in plan_changes.log | H4/L10 | rating_contract.md, Identifiers | 115 (57.8%) |

COUPLING quantity: the region credit base, which decides the credit of every line of the region.
Hidden months set pool = k/8 of the true base so a 0.01 slip in the base flips several half-cent credits.
Shipped data: north separating rows ship (L5 only); no charge or credit tie ships; plan_changes.log
writes only canonical ids. DESIGN.md section 4 records why no shipped self-test separates LV-MU-2/3/4.

## Tests and judge

- 52 checks: 23 row-owned or document families, each visible w3 (delivered /app/out) and `_hard` w5
  (fresh month from seed 58213, run as nobody from a renamed input folder and a foreign cwd);
  mutation_tier_scale w5, missing_collector w3, control_mismatch w3, determinism w3, transform_exists w1;
  one negative `negative_hardcoded_sample_answers` w-5. Positive 199.
- Shares of positive test weight: hidden or mutated 129 (64.8%); whole-document 96 (48.2%); row-owned
  line checks 88 (44.2%); shipped-only 70 (35.2%).
- Judge: 14 criteria, mode batched, positive 28: R1-R6 independent recomputation per output family w3,
  R7 J9 altered-copy rerun w3, R8 J4 code quality w3, R9 J6 lists every output file w1, R10 foreign-cwd
  run w3; negatives R11 honesty -3, R12 unsupported figure -3, R13 grader paths -5, R14 writes under
  /app/data -3. WORK/JUDGE_MAP.md covers all 14.
- reward.toml: test_output 0.5/199, judge 0.5/28.
- solve.py shares 12.7% of its substantive lines with test_output.py (O1 warn at 20%).

## Cost table (G10, WORK/COST_TABLE.md, rubric 90)

| lever | alone lost | all but this right overall | one fact wrong lost |
|---|---|---|---|
| LV-MU-1 | 95.0% | 47.5 | 73.9% |
| LV-MU-2 | 55.3% | 67.4 | 17.6% |
| LV-MU-3 | 66.8% | 61.6 | 34.7% |
| LV-MU-4 | 57.8% | 66.1 | 25.1% |

All four wrong (PREMORTEM reflex program): 10/199. Rule coverage (G11): 51 rows, 0 uncovered.

## Gates

- structure_qc exit 0, 0 FAIL (WARN X1: collector_south.txt skipped as binary, it is Latin-1 by design).
- instruction_qc exit 0, 0 FAIL, 0 WARN. tests_qc exit 0, 0 FAIL (WARN A3: 52 checks, kept, TS-23). judge_qc exit 0, 0 FAIL.
- validate_bundle.py --archetype data-pipeline: 39 passed, 0 failed, 0 warnings, GATE PASS.
- playground.py: not run, the file no longer exists in GEN (KNOWLEDGE.md:84, removed in a72c20a4). A5 volume
  checked by datagen.py instead: 21,054 lines, every csv/tsv/jsonl/txt/log >= 2,206 lines.
- Oracle through real `uvx --from harbor-rewardkit==0.2.1 rewardkit`, tests channel, local scratch copy:
  1.0, 1.0, 1.0. Nop (empty /app/out): 0.0. Tests also run under Python 3.12 (stub harness): 199/199.
- check_exact.py (independent recomputation + invariants + override-removal probes): CHECK_EXACT OK.
- STACKING: PASS (OUT/STACKING_CHECK.md). precheck.sh last line: `PRECHECK CLEAN`.
- GEN and QC fingerprints re-hashed at the end: 0 differences.

## Expected loss per lever (DESIGN.md section 9)

- LV-MU-1: every visible and `_hard` family plus mutation_tier_scale (north rows `"123"`, `" 45"`).
- LV-MU-2: rating_<r>_hard, credit_<r>_hard, region_<r>_hard, segment_<s>_hard, product_summary_hard,
  summary_hard, mutation_tier_scale (planted even-hundredth ties, k/8 pools).
- LV-MU-3: credit_<r>, region_<r>, segment_<s>, product_summary, summary, visible and `_hard`, plus mutation_tier_scale.
- LV-MU-4: rating/credit/region/segment/product_summary/summary/data_quality `_hard` plus mutation_tier_scale
  (mixed-case, hyphenated ids in the hidden plan_changes.log).

## Open conflicts and not run

- No OPEN CONFLICT Q18: validator 15.5 and DS-27 agree (KNOWLEDGE.md line 37); scaffold provenance kept.
- Not run: Docker build and container oracle (so the setpriv drop to nobody was not exercised locally;
  `_grant_read` is in place for QC H6/TS-30); playground.py (removed upstream); oracle x5 (x3 per Ayush).
- Deviation from IDEA: collector_controls.json carries record counts only, no unit sums (a unit sum
  would confirm the LV-MU-1 strict reading on shipped data).

## Lessons for the master

- Row-owned tests plus one COUPLING quantity kept every lever above 50% alone without whole-document cascades | no change: recorded in DESIGN.md section 6
- The rating-order tie rule needed a hidden fixture (same timestamp, ids against file order) before it covered any test | template_change: LEVER_RULES_v1.md G11 add "tie-break rules need a planted tie"
- stacking_check.py mislabels visible vs `_hard` pairs as TS-26 duplicates and under-counts hidden share for row-owned checks | template_change: tools/stacking_check.py classify by tier argument
- playground.py is gone from GEN but the build prompt still asks for it | template_change: build prompt Phase 8 step 1
