# P12 recheck + fix: district-heat-flex-procurement (QL round 2, board 19f8e1f)

Kit HEAD `5574d77eb9f22c207ba05fd8f9ac31d42ba45271` (fingerprints qc.json 12/12, pl_generator.json 160/160, no upstream change). Tree before fixes `2b289f9f9561` (backup `WORK/pushed_2b289f9f9561/`, tree re-read 2b289f9f9561). Tree after fixes `9d1e071a5792`. "TO" = `tests/test_output.py` before edits, "TN" = after; "S" = `environment/data/schema.md`; "T" = `solution/TRUTH.md` after. Report `_ql/.../20261029T1217_report/QL_REPORT.md` (Q:), triage `ql2_triage_48eb59a/TRIAGE.md`. Session rename: `name_session.py 19f8e1f` printed `codex: no match`, `opencode: ['ses_e78b09a67ffeVCZ8FPnVqGiYNV']`; the list did not show 19f8e1f by name (noted, not retried).

Noise check (Always 13): `diff -rq BUNDLE QC/copies/a8e4f16/district-heat-flex-procurement` printed nothing, so every cited line is byte-identical to the round QC v10 passed. Each finding below names a live kit line; the noise column says whether v10's PASS reason covered it.

## Phase 1 rows

Levers (LEVERS.md): REENTRY (M1), CHAIN1 (M2), RELIEF (M3), WIDE (P-3 exact optimum, timeout), greedy, AL-27 rows (UNIT10, CODESHIP, ADDmiss, GAPdrop, LEDwithin, ALWge, CLAIMlt). Effect column order: REENTRY / CHAIN1 / RELIEF / WIDE / greedy / AL-27 rows.

| ID | label | rule quote (kit file:line) | evidence quote (bundle file:line, before) | noise | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|---|
| QL2-F1 | REAL | IN-16 "No significant ambiguity in anything that is graded ... reachable in exactly one way" 01_Instruction_QC.md:46 | S:309 "All but the last two are totals over every event-region"; S:313 "The global totals equal the sums over the region files"; TO:760 `summary.update(event_count=len(event_list)` (distinct events); Q:7-18 sum reading gives 2000 and 229/237 | v10 did not read S:313 against event_count: stands | FIX: S:309-317 now "`event_count` is the number of events in `events.json`, each counted once" and the sum sentence names the keys `candidate_offer_count` .. `grant_unallocated_cents`, "`event_count` is not such a sum" | IN-16 (DO: settle in the governing file, general case) | none / none / none / none / none / none | none needed | S |
| QL2-F2 | REAL | DS-24 "The oracle is an independent implementation, not a copy of the verifier" 02_Data_Solution_QC.md:69 | TO:455 `bounded` (twin classes TO:466-475, lane order TO:476-477, bound TO:494 `min(caps[t][0], rel[t] + reach[i][t])`, strict cut TO:502) = solve.py:268-353 choose_portfolio; TO:577 `solver = search if lazy & SEARCH_FLAGS else bounded` | v10 measured shared names, not the shared search: stands | FIX: `bounded` deleted; new module `_exact` (TN:490) is a layered state table over sites (relief-ordered, states merged on relief/recovery/segment vectors, ways summed, no twin classes, no branch cut on the oracle's bound); TN:938 `else optimum`. Exact on shipped/H1/H2 live (1.2 s). Wide optima computed once offline by `_exact` (19.7/46.6/41.2/30.6 s), checked equal to the old truth and to the oracle's choice on all 320 event-regions (0 mismatches, `p12q2/gen_wide_truth.log`, `check_repair.py` CHECK OK), stored in `_WIDE_TRUTH` (TN:166) by event-region digest (master 18:00 direction). Wide inputs, 64 wide points, 120 s unchanged | DS-24 (DO: independent exact method, cross-checked on every graded extract) | none / none / none / none / none / none | none needed | TO |
| QL2-F3 | REAL | TS-26 "No intra-test double payment, in ANY pairing ... Two tests reading the same observable" 03_Tests_QC.md:53 | TO:1665 shipped quality_counts projection keeps `unallocated_pool_count`, also read by residual_match on shipped; Q:38-47 +1 fails both (221/237) | v10 paired families by name: stands | FIX: `SHIPPED_ELSEWHERE` (TN:2021) drops `unallocated_pool_count` from the shipped quality_counts projection only; residual_match owns it; both `_hard` checks and all weights unchanged | TS-26 (DO: narrow to different observables, weight stays in family) | none on all | none needed | TO |
| QL2-F4 | REAL | AL-2 "Everything promised is graded ... An ungraded promise invites solutions that skip it" 05_Alignment_Integrity_QC.md:33 | S:272 `bid_cost_cents`, S:278-279 `compliance_counts`; no family projects them (TO:1654 FAMILIES); Q:49-60 zeros pass 237/237 | v10 enumerated region keys by totals only: stands | FIX: families `bid_cost_rows`, `compliance_rows`: shipped w3 (TN:2633, :2643), H1 w5 (TN:2638, :2648), each wide extract w1 (TN:2787 ff.) = 24 points; reward.toml test_output 0.5/261 | AL-2 (DO: grade the observable on hidden inputs) | none / none / none / harder (wide loss 64 -> 72) / harder (183 -> 195) / none | n/a (harder) | TO, reward.toml |
| QL2-F5 | REAL | CL-3 "no asserted value liftable verbatim from a shipped file ... (derivation is fine and expected)" 05_Alignment_Integrity_QC.md:87; Final_checklist.md:490 | export_manifest.tsv:2-3 "gives its records, counted the way data_quality.json counts the rows of that file"; rows :7-20 records = `rows` counts; generator TO:910-941 | v10 read the receipt as integrity data: stands | FIX (master option a): `records` column removed from the shipped receipt and from `_write_receipt` (TN:1271); header now `file`, `field`, `field_sum`; comment "Each line names a file. Where a field is named, field_sum is ..."; S:101-104 and T:57-58 updated; field sums stay true; no false count. solve.py unchanged (it counts receipt rows itself, solve.py:228-230) | CL-3 (DO: remove the copyable value; never a false one) | none on all (receipt trap now needs counting: harder or none) | none needed | export_manifest.tsv, S, TO, T |
| QL2-F6 | REAL | DS-22 "TRUTH.md describes the bundle that actually shipped" 02_Data_Solution_QC.md:78 | T:38 (before) lists `allowance_ticks_mutation` among `draws_from` graders; mut_allowance specs carry no draws_from (TO:1103-1124) | stands | FIX: T:32-38 list ends "`tie_decisions_match_hard` and totals." | DS-22 | none on all | n/a | T |
| QL2-F7 | REAL | DS-22 02_Data_Solution_QC.md:78 | T:95 (before) "twenty families, each a shipped-data check (w3)"; tie_decisions_match runs on `case_root('tie')` (TO:2103-2105) | stands | FIX: T:96-98 "The light check runs on the shipped data, except `tie_decisions_match`, which runs on a generated extract where two portfolios tie" | DS-22 | none on all | n/a | T |
| QL2-F8 | FALSE_POSITIVE | TS-13 "One property per test" 03_Tests_QC.md:44 | `canonical_serialization_and_integer_units` TO:1995-2014 grades one property, the JSON encoding contract | v10 V:153 PASS | REBUT (KEPT row) | NOISE/keep | none | n/a | none |
| QL2-F9 | FALSE_POSITIVE | TS-14 03_Tests_QC.md:45 | negative name TO:2524-2539; v10 V:36 recorded, Ayush accepted | carry-over | REBUT (KEPT row) | NOISE/keep | none | n/a | none |
| QL2-F10 | FALSE_POSITIVE | TS-23 "at most 35 (warn)" 03_Tests_QC.md:62 | 66 (now 78) checks; no count cap (Ayush 24 Oct 12:50, option A 27 Oct); V:39, V:165, KEPT l5 | carry-over | KEEP warn with count | TS-23 | none | n/a | none |
| QL2-F11 | FALSE_POSITIVE | IN-2 01_Instruction_QC.md:32 | instruction.md:7 states what the output must satisfy, names no grading mechanism; V:87 | carry-over | REBUT | NOISE/keep | none | n/a | none |
| QL2-F12 | FALSE_POSITIVE | JD-14 "No double payment inside the file" 04_Judge_QC.md:91 | judge.toml:38-48 R3 credit_cents vs :155-165 R12 cap_binding_count: different observables (report itself says so); V:192 | carry-over | REBUT | NOISE/keep | none | n/a | none |
| QL2-F13 | FALSE_POSITIVE | JD-15 04_Judge_QC.md:92, :139 | judge R1-R4, R8-R10, R12 are conduct criteria that raise the odds of a correct result; the report says they pass; V:193, QC_RULINGS l141-145 | carry-over | REBUT | NOISE/keep | none | n/a | none |
| QL2-F14 | FALSE_POSITIVE | AL-19 05_Alignment_Integrity_QC.md:65 | Popen without `env=` TO:1807; bundle reads and ships no credential, inherited key is the pinned placeholder; V:40, V:235, KEPT l6 | carry-over | REBUT | NOISE/keep | none | n/a | none |
| QL2-F15 | REAL | AL-27 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters" 05_Alignment_Integrity_QC.md:38 | specs `allowance_order`, `allowance_consumption` TO:1086-1106 never planted (PLANTED TO:1159-1162); H1 draws wh_per_tick 25 so `tick_feasibility` (10 Wh) is defused; HIDDEN_GUARDS TO:1288-1295 has no Wh reading | stands | FIX: both unused specs deleted; start-instant ordering stays graded by `allowance_ticks_mutation` (mut_allowance pair, TN:1447 comment: start order differs from id and string order) and the LEDid guard on H1 (G3); `("DH2", "selection")` added to H1 guards (TN:1632), H1 seed re-chosen by the existing guard loop | AL-27 (DO: hidden case constructs the reading) | none / harder-or-same (55 -> 50, 90.9% kept) / none / none / none / UNIT10, CODESHIP, GAPdrop, LEDwithin harder; others none | none needed (>=90% kept) | TO, RULE_COVERAGE.md |
| QL2-F16 | FALSE_POSITIVE | AL-7 05_Alignment_Integrity_QC.md:43 | T:130 is a marked test-channel figure, T:232 the full-run score, T:238 says so | carry-over | REBUT | NOISE/keep | none | n/a | none |
| QL2-F17 | REAL | DS-22 02_Data_Solution_QC.md:78 | T:181 (before) "a lower bound on components 1 and 2" vs solve.py:310-326 five components | stands | FIX: T:191 "stops a branch once the five-part key with components 1 and 2 bounded (relief still reachable, capped at the ceiling, and segment relief still reachable) and components 3 to 5 taken as they stand is already worse" | DS-22 | none | n/a | T |

Counts: REAL 9 (F1-F7, F15, F17), FALSE_POSITIVE 8 (F8-F14, F16), UNSURE 0. Fixed 9, kept 8 (KEPT.md).

## Deviations from master directions

None. F2 follows the master 18:00 ruling: the live `_exact` table is exact on all seven roots but takes 156 s on the host for the four wide extracts (single event-regions up to 12.8 s), so the wide optima are computed once offline and stored; shipped, H1 and H2 stay live.

## What changed (files)

- `tests/test_output.py` (from `WORK/test_output.src.py` by `WORK/embed.py`): F2 `_exact` + `_WIDE_TRUTH` + `optimum` (old `bounded` removed); F3 `SHIPPED_ELSEWHERE`; F4 two families and 12 checks; F5 `_write_receipt` three columns; F15 two specs deleted, DH2 guard. G7 diff `OUT/G7_src_diff.txt`, every hunk mapped in `OUT/G7_NOTE.md` (no unnamed hunk). Dockerfile, test.sh, judge.toml unchanged.
- `tests/reward.toml`: test_output 0.5/237 -> 0.5/261 (0.0019157088122605363); judge unchanged.
- `environment/data/export_manifest.tsv` (F5), `environment/data/schema.md` (F1, F5); `_SHIPPED_DATA` re-embedded.
- `solution/TRUTH.md` (F5, F6, F7, F17, counts 78/261, measured figures /261), sha lines by `WORK/q2_truth.py` last. solve.py, solve.sh, instruction.md, judge.toml, task.toml unchanged.
- WORK: QC_DEFENCE (QL2 section), XREF (retired values), LEVERS (QL2 section), RULE_COVERAGE (/261 figures), DESIGN (QL2 note), README_STALE.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| bid_cost_rows_match (w3), _hard (w5) | added | TS-13 one property (bid_cost_cents of event entries); TS-14 name = property, description TN:2632; TS-20 core selection keeps w5, this a value cross-check; TS-25 earned (zeros fail, shipped copy fails on H1, vacuity.py); TS-26 shipped vs H1 vs wide extracts differ; CL-2/CL-4 reference derives cost from offers.csv, not from a shipped figure | PASS TN:2633, :2638 |
| compliance_rows_match (w3), _hard (w5) | added | same set; five-label object of site rows per event-region | PASS TN:2643, :2648 |
| wide_k_bid_cost_rows_match, wide_k_compliance_rows_match, k=0..3 (w1 each) | added | TS-13, TS-14, TS-25 (each wide projection non-empty, zeros fail), TS-26 each on its own wide extract, TS-20 w1 master-set; verifier time: one program run per extract shared with existing wide checks | PASS TN:2787 ff., registrations TN:2995-3022 |
| quality_counts_match (w3) | narrowed (shipped projection drops unallocated_pool_count), description re-worded | TS-13, TS-14 description matches body, TS-26 now disjoint from residual_match on shipped, TS-25 still earned | PASS TN:2021 |
| all families' truth | `bounded` replaced by `_exact`/`_WIDE_TRUTH` | CL-2 truth independent of solve.py search (DS-24); TS-25 unchanged expectations (check_repair.py: identical expected() on 7 roots) | PASS TN:490, :938 |
| H1 hidden extract | seed re-chosen (DH2 guard) | AL-27, TS-25 every H1 guard family changes; trap survival | PASS TN:1632 |
| reward.toml | test_output weight 0.5/261 | AL-28 negatives -13 <= 261; TS-23 balance | PASS reward.toml |

Judge unchanged: JD rows not touched. touched_rows: 7.

## Vacuity probe

`WORK/p12q2/vacuity.py` (host, test logic): shipped, H1 and wide0..3 projections of bid_cost_rows and compliance_rows are non-empty; all-zero values fail; shipped figures copied onto H1 / wide fail; shipped `unallocated_pool_count`+1 leaves the shipped quality_counts projection unchanged and fails residual_match. Output `VACUITY OK`. Unedited environment (nop run in Docker): reward 0.0. Judge positives unchanged since QC v10 (no positive earnable without work, v10 V:190-193).

## Side effects

| FIX id | ids re-checked | result |
|---|---|---|
| F1 (IN-16) | AL-27 (FIX_SIDE_EFFECTS row): the distinct-vs-sum case is constructed on every extract (500 events over 4 regions on shipped); IN-15 no rule moved next to its use | clean |
| F2 (DS-24) | TS-25 expectations identical on 7 roots; verifier time (oracle verify 34 s); DS-21 solvable unchanged | clean |
| F3 (TS-26) | TS-14 (FIX_SIDE_EFFECTS row): name and description of quality_counts_match match the narrowed body | clean |
| F4 (AL-2) | TS-25 (FIX_SIDE_EFFECTS row): vacuity.py; NEW-CHECK TS-13/TS-14/TS-16/TS-25/TS-26; TS-23 count 78 (warn kept) | clean |
| F5 (CL-3) | DS-21 (FIX_SIDE_EFFECTS row): rows still derivable by counting files; data_quality `rows.export_manifest.tsv` still 14; Never 11 no false count | clean |
| F6/F7/F17 (DS-22) | sha lines by script; precheck DS-22 | clean |
| F15 (AL-27) | TS-13 (FIX_SIDE_EFFECTS row): checks unchanged; G3 grader named for start-instant ordering; RULE_COVERAGE.md no 0 row | clean |

side_effect_findings: 0.

## Noise keeps

- F8-F14, F16: bundle byte-identical to PREV_QC_COPY a8e4f16 (`diff -rq` empty); each finding re-raises a row v10 passed or Ayush accepted (V:153, V:36, V:39/V:165, V:87, V:192, V:193, V:40/V:235, T:130/:232/:238). Rows in `OUT/KEPT.md`.

## Trap survival

Before = `WORK/p12/dout/TRAP_p12new.txt` (/237), after = `WORK/p12/dout/TRAP_q2.txt` (/261), same variants, Docker `--memory 4g --cpus 2`.

| lever | before loss | after loss | kept | verdict |
|---|---|---|---|---|
| REENTRY | 45 | 45 | 100% | PASS |
| CHAIN1 | 55 | 50 | 90.9% | PASS |
| RELIEF | 53 | 53 | 100% | PASS |
| WIDE (exhaustive program, timeout) | 64 | 72 | 113% | PASS |
| greedy | 183 | 195 | 107% | PASS |
| UNIT10 | 90 | 95 | 106% | PASS |
| CODESHIP | 100 | 110 | 110% | PASS |
| ADDmiss | 35 | 35 | 100% | PASS |
| GAPdrop | 15 | 20 | 133% | PASS |
| LEDwithin | 35 | 45 | 129% | PASS |
| ALWge | 40 | 40 | 100% | PASS |
| CLAIMlt | 5 | 5 | 100% | PASS |
| empty_portfolio | 46 | 46 | 100% | PASS |

No separating hidden case removed (the two deleted specs were never planted). CHAIN1 drops 5 because the new H1 seed changes which families its draws_from chain moves; it keeps 90.9%.

## Gate results

| gate | result | evidence |
|---|---|---|
| xref_check | 0 findings | `xref_check: 50 entries, 0 findings` |
| precheck | PRECHECK CLEAN | tests 78, judge 12; WARN [A3] 78 checks (KEEP); note SELF_CHECKS only |
| stacking | STACKING PASS | `OUT/STACKING_CHECK.md` |
| G7 | every hunk named | `OUT/G7_src_diff.txt`, `OUT/G7_NOTE.md` |
| vacuity | PASS | `VACUITY OK` |
| trap survival | PASS | table above |
| oracle x3 | 1.0, 1.0, 1.0 (verify 34/34/35 s) | `/tmp/opencode-logs/dh-19f8e1f/dchain-20261029T182059-eebe/runs.log` |
| owner-only x1 | 1.0 (verify 35 s) | `/tmp/opencode-logs/dh-19f8e1f/dchain-20261029T182059-eebe/runs.log` |
| nop x1 | 0.0 | `/tmp/opencode-logs/dh-19f8e1f/dchain-20261029T182059-eebe/runs.log` |
| score bar (a13 program on fixed tests) | 0.7241 = 189/261 = 72.41% <= 72.9958% (24 wide checks timed out at 120 s, as predicted) | `/tmp/opencode-logs/dh-19f8e1f/dchain-20261029T182059-eebe/runs.log`, a13-1.verifier.log |
| verifier worst case | 495 s (a13 program) | <= 2,430 s |

## QC_RULINGS rows

- IN-16 | event_count in summary.json vs "global totals equal the sums" | QC: ambiguous (fail) | REAL | the sum sentence now names its keys and says event_count is not a sum (S:309-317).
- TS-26 | quality_counts_match and residual_match both read unallocated_pool_count on shipped | QC: double payment | REAL | shipped quality_counts projection drops the key; residual owns it; hard checks unchanged.
- TS-13 | canonical_serialization_and_integer_units | QC: two properties | FALSE_POSITIVE | one property, the JSON encoding contract (V:153, TO:1995-2014).
- JD-15 | conduct criteria R1-R4, R8-R10, R12 | QC: requirements not in instruction | FALSE_POSITIVE | the report says they pass; kit 04_Judge_QC.md:139 allows conduct criteria that raise the odds of a correct result.

## Lessons for the master

- A regex that rewrites a dict literal in a generator must anchor on its own closing line; `\{.*?^\}` deleted 1,000 lines once (caught by the G7 diff and a host expected() comparison before any Docker run).
- An exact truth that is independent of the oracle can be much slower than the oracle's tuned search; storing offline-computed optima for fixed-seed extracts keeps DS-24 and the verifier budget.
- A new hidden-seed guard re-picks the seed and moves other levers' losses; always re-run the full trap sweep after adding one.
