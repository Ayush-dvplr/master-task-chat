# BUILD_REPORT: hangar-check-replan (af5dddf, route 1 build of redesign 2)

Author Ayush Sah <ayush.sah@ethara.ai>. Shape D. Archetype domain-calculation, category optimization, seed 268417.
Scores below are TESTS-ONLY unless marked judge.

## Tree

BUNDLE = /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/hangar-check-replan/ (25 files; tree sha 3df66c1d1ab2)

| path | files | note |
|---|---|---|
| environment/Dockerfile | 1 | scaffold, `COPY data /app/data`, ENV HOME early |
| environment/data/ | 8 | shipped corpus (seed 2, n=5 per base) |
| environment/data/docs/ | 6 | README.md (register), data_conventions.md, planning_policy.md, overtime_policy.md, deferral_policy.md, output_schema.md |
| instruction.md | 1 | 2219 bytes |
| solution/ | 3 | solve.py (473 lines), solve.sh (oracle + 9 judge probe stages in a heredoc), TRUTH.md |
| tests/ | 5 | Dockerfile, test.sh, test_output.py (embedded generator + shipped blobs), judge.toml, reward.toml |
| task.toml | 1 | scaffold values |

## Data: formats, lines, chains

Formats 6: csv, jsonl, json, toml, docx (WordprocessingML), md. Files 14 under environment/data.
Lines: check_requests.csv 5455, published_plan.csv 5453, fleet_register.csv 2622, base_calendar.jsonl 7304, check_types.json 14, fleet_limits.toml 3, docs 220; total 21071 (A5: >= 20,000 total, each csv/jsonl >= 2,000). The two docx hold the notice and limit tables.
Chains: (1) check_requests -> fleet_register (class, status) -> planning_limits.docx class rates; (2) check_requests -> published_plan (moved term); (3) base_calendar + disruption_notice.docx closures -> legal start days; (4) disruption_notice.docx revised availability -> available day; (5) plan -> planning_limits.docx allowance table -> settlement per check, base, segment, fleet.

## Levers (where written)

| id | lever | governing text | hidden fire |
|---|---|---|---|
| L1 (S1/S2/S3) | settlement after the plan: fleet allowance paid in class / due_date / request_id order; used vs granted; settled = cost minus credit | overtime_policy.md:12-27 | h1 at cap, h2 one over, h3-h6 binding with equal-due pairs on h3 h4 h6; shipped never binds |
| R1 | one fleet overtime pool | overtime_policy.md:9-10 | every hidden corpus binds; shipped used = pool with no trade |
| R2 | moved third term + start/finish vector tie | planning_policy.md:30-38 | ties and late published starts on hidden |
| R3 | deferral reasons no_slot / plan_trade | deferral_policy.md:3-9 | plan_trade only on hidden; no_slot planted |
| U | fixed base/segment universe | output_schema.md:5-8 | empty base + empty segment on h1, h2 |
| X1 | duplicate rule counts read rows only | data_conventions.md:31-36 | h3, h5 (fitted spot of blind e8e9c82) |

## Weights and shares (tests)

35 checks, positive 129, negatives -10 (two). Hidden 113 (87.6%), mutation 6 (4.7%), shipped-only 10 (7.8%); G3 hidden+mutation 92.2%. L1 settlement 93/129 = 72%; plan levers 21 (16%); lever share 92%.
Judge: 17 criteria, positive 39, 9 probes w3 = 27 (69%), negatives R14 -5, R15 -3, R16 -5, R17 -3. Band lower 23%, mid 44%, upper 100%.

## Script and validator results

| gate | result |
|---|---|
| structure_qc.py | 17 pass, 1 WARN X1 (two .docx skipped as binary; they are real Word packages), 0 fail |
| tests_qc.py | 36 pass, 0 warn, 0 fail (35 checks) |
| judge_qc.py | 19 pass, 0 fail (17 criteria) |
| instruction_qc.py | 5 pass (2219 chars) |
| validate_bundle.py --archetype domain-calculation | 40 passed, 0 failed, GATE PASS |
| own A5 count | 21071 lines (data 20860 in 8 files, docs 220); every csv/jsonl >= 2,000 |
| O1 solve.py vs test_output overlap | 1% |
| oracle x3 (harbor, tests-only copy, judge removed) | 1.0, 1.0, 1.0 (ql2-20261101T1407; verifier 294-315 s of 2700) |
| owner-only oracle (exe_copy --owner-only) | 1.0 (owner2-20261101T1407; verifier 303 s) |
| nop | 0.0 (ql-20261101T1249 nop job, tests before the thread-lock fix; the fix only serialises case builds, a missing program still fails every check) |
| first oracle round (before fix) | 1.0, 1.0, 0.744; owner-only 0.783: rewardkit 0.2.1 runs criteria in threads, so hidden folders were built and run concurrently and raced the 60 s limit; fixed with one lock in test_output.py |
| G12 generator survey | 300 of 300 seeds pass bounds and planted-branch asserts (287 first draw, 11 second, 2 third; 8 allowed) |
| wrong implementations (Docker, 17 programs) | oracle 129/129; every mutant loses by WRONG; negatives silent on oracle and on every mutant (COST_TABLE.md) |
| stacking_check.py | PASS (OUT/STACKING_CHECK.md; AL-28 by hand) |
| check_exact.py (all start days, no dominance) | OK on shipped vs solve.py |
| precheck.sh | PRECHECK CLEAN (WARN X1 binary docx, WARN JD-5 R14 is the mandated grader-read anchor sentence) |
| Tasks_INPUT copy | /Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Tasks_INPUT/hangar-check-replan/ via cp -Rp; diff -rq empty; tree sha BUNDLE 3df66c1d1ab2 = copy 3df66c1d1ab2 (25 files each) |

## Expected loss per lever (measured mutants, tests of 129; COST_TABLE.md)

| slip | tests | lost | predicted final (tests + judge mid 44)/2 |
|---|---|---|---|
| settlement: cap not subtracted | 30 | 76.7% | 33.7 |
| settlement: per-base cap | 36 | 72.1% | 36.0 |
| settlement: unordered | 51 | 60.5% | 41.8 |
| settlement: whole checks only | 51 | 60.5% | 41.8 |
| settlement: granted not used | 58 | 55.0% | 44.5 |
| settlement: start day key | 79 | 38.8% | 52.6 |
| R1 pool per base | 4 | 96.9% | 23.6 |
| N revised availability ignored | 14 | 89.1% | 27.5 |
| R3 no_slot-only deferral | 36 | 72.1% | 36.0 |
| R2 first-found tie | 75 | 41.9% | 51.1 |
| R2 earliest start only | 76 | 41.1% | 51.5 |
| U axes from records | 88 | 31.8% | 56.1 |
| X1 ids from ignored rows | 103 | 20.2% | 61.9 |
| Q line numbers from 1 | 123 | 4.7% | 69.7 |
| design blind e8e9c82 (literal reader) | 103 | 20.2% | 61.9 |
| oracle | 129 | 0 | 72.0 |

All losses WRONG (exit 0, wrong fields); no TIMEOUT, no CRASH. Route 1 note: the literal reader e8e9c82 keeps 80% and is recorded, not a blocker; the paid run decides the harden.

## Open conflicts

None new. TRUTH provenance keeps the scaffold keys; validator 15.5 passed, so no Q18 conflict arose.

## Not run

Fresh design blinds (master: none for this build). Nop on the final test file (Docker busy; nop 0.0 is from the test file before the lock, which only serialises case builds). The clip of an early available day to day 1 has no observable effect (mutant c_no_clip 129/129); RULE_COVERAGE.md lists it as not covered, outside the 14 graded rules. Judge not run (no paid model run); judge numbers are estimates.

## Lessons for the master

rewardkit 0.2.1 runs criteria in threads; a test file that builds shared hidden folders lazily must hold one lock or runs race the per-run limit (oracle 0.74 then 1.0) | template_change: scaffold tests/test_output.py helper block: add a module lock around case builds
A fixed hidden folder can miss a planted branch for some seeds; redraw up to 8 times with an assert, then survey 300 seeds (7 of 102 missed before, 0 of 300 after) | template_change: LEVER_RULES_v3 G12: add redraw-with-assert pattern
The literal design blind keeps 80% here; its only loss is a fitted duplicate-id reading turned into a held-out case (X1) | no change: route 1 note R3 item 2 already asks for this
Docker is shared with other agents; dockfree said START=no for the last 15 min, so nop was not rerun on the final test file | no change: recorded in Not run
