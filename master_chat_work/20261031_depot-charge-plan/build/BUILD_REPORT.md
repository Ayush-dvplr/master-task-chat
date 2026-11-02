# BUILD REPORT: depot-charge-plan (board 154f570)

Status: DONE. Shape D. Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/depot-charge-plan/`.
Work: `master_chat_work/bundles/_work/depot-charge-plan/`. Session rename: `name_session.py 154f570` printed `codex: no match`, `opencode: ['ses_e6c82bbdfffebyu6deVAtfxNU5']`.

## Tree (24 files, tree sha da868c0505bf)
- instruction.md 25 lines (2151 chars), task.toml 47 (author Ayush Sah <ayush.sah@ethara.ai>, agent 7200 s, verifier 2700 s)
- environment/Dockerfile 26; environment/data: 13 files
- solution/: TRUTH.md 238, solve.py 624, solve.sh 276 (self-check stage embedded, 9 `check <id> ok` lines)
- tests/: Dockerfile 9, test.sh 10, test_output.py 3855, judge.toml 217, reward.toml 7

## Data (7 formats: csv, jsonl, json, ini, xml, md; 21857 lines, A5 PASS)
fleet_register.csv 4001, roster.csv 4958, trips.jsonl 5189, published_plan.csv 5241, settlements.csv 2244, tariff.xml 23 (3 versions), grid.ini 8, depots.json 21, bus_types.json 14, contracts.json 89, service_classes.ini 5, disruption_notice.md 16, docs/charging_rules.md 48 (rules 1-22).
Chains: roster -> fleet_register -> bus_types -> need (trips + notice extras + reserve - soc); roster contract -> contracts.json -> service_classes.ini weight -> objective term 1; settlements -> tariff version on settled date -> meter shift per depot -> depot price on plan date -> cost; depots.json cabinets -> notice outages -> per-slot depot limit; grid.ini feeder -> notice derates -> shared per-slot limit.

## Levers (Shape D, 3 sharp rules; hard branch fires 0 times on shipped)
| lever | rule written in | alone lost | shipped fires | hidden fires |
|---|---|---|---|---|
| M meter convention (unique shift fitted from settlements) | docs/charging_rules.md:27 (rule 12) | 86.9% | 0 (all shifts 0) | 4/4 corpora, every depot |
| F shared feeder + depot cabinet limits (derates, outages) | charging_rules.md:22-23 (rules 10-11) | 86.9% | 0 | 4/4 |
| T lexicographic order + tie-break (slot, bus id; greater list) | charging_rules.md:33 (rule 15), coupling :34 | 86.9% | 0 (tie never decides) | 4/4 |
Coupling sentence rule 16 (:34): every report from the one optimal plan for all four depots together.

## Checks and weights
- Tests: 45 checks (43 positive, 2 negatives -3 / -5). Positive 191: hidden generated 172 (90.1%), held-out w5 tier 160 (83.8%), shipped-only 18 (9.4%), whole-doc exact 187 (97.9%), mutation reruns 9. WARN A3 (45 > 35) recorded, not merged.
- Judge: 16 criteria, positive 35, 8 probes (P-a, P-b, P-c x2, P-d, P-e, P-g, P-h) = 68.6%; J4, J6 (w5), J10 order w3; negatives J3a -3, J3b -5, J3c -1, grader-read -5, scope -1. Estimate lower 23% / mid 44% / upper 66%.
- reward.toml: test_output 0.5/191, judge 0.5/35.

## Results
- QC: structure_qc 17/0 fail; instruction_qc 5/0; tests_qc 35 pass, 1 WARN A3, 0 fail; judge_qc 19/0. validate_bundle.py --archetype domain-calculation: 40 passed, 0 failed, GATE PASS. No WARN C6. (playground.py removed from GEN; A5 by own line count.)
- Oracle (Docker, dcp-verifier:1 = python:3.12-slim + rewardkit 0.2.1 + litellm 1.105.0): o1, o2, o3, o4 = 1.0; nop n1, n2 = 0.0.
- STACKING: PASS (OUT/STACKING_CHECK.md). PRECHECK last line: `PRECHECK CLEAN`.
- Fingerprints re-checked: GEN 160/160, QC 12/12 identical.
- check_exact: independent recompute exact on shipped + 4 hidden; brute force 300 tiny instances, every optimum unique, 0 mismatches; override-removal probes move 8 reports on hidden (outages, derates, extras, meter) and 0 on shipped for outages/derates/meter (degenerate by design).

## Kill test and design blinds (WORK/KILL_TEST.md)
- v1 (exact optimum only): blind fd98e12 EXACT 9/9 everywhere -> NO CORE; G-8 redesign added the meter lever.
- Redesign: literal multiplier, careful enumerator, tariff-as-stated, shipped convention: EXACT shipped, WRONG 0/8 on all hidden. Greedy/EDF/class/swap/per-depot trims/split-exact/plain flow: WRONG 0/8 on hidden. Design blind d9d6ab5: EXACT shipped, WRONG on all 7 hidden families except data_quality (100% lever points lost by WRONG, 0 TIMEOUT).
- Residual risk: a reader that searches all slot shifts against settlements plus implements the exact tie pass is EXACT (reference method).

## Expected loss per lever
- M: every fresh_h1..h4 family check except data_quality (32 x w5) plus reordered/relocated reruns; first-write (identity meter) tests 25/191 = 13.1%.
- F, T: same 34 checks each when wrong alone. All-but-one predicted final (13.1 + 44)/2 = 28.6.
- Probes expected Opus: P-b, P-g FAIL; P-c, P-d, P-e, P-h 20-30%; P-a 20%.

## Open conflicts
- None. TRUTH provenance kept as scaffold shape (fix_patch_sha256 = solve.sh); no Q18 conflict observed (validator and QC both pass).

## Not run
- No harness or paid run; no fresh P13 blinds beyond the two design blinds (master queues them).

## Lessons for the master
- exact optimum alone was solved by the design blind in 7 min | no change: matches LIBRARY L09
- a per-corpus convention fitted from history, with shipped value identity, was missed by blind d9d6ab5 | no change: record in LEVER_RULES 1C as promising
- precheck skips RULE_COVERAGE rows whose first cell starts with "rule" | template_change: tools/precheck.sh RULE_COVERAGE row regex
