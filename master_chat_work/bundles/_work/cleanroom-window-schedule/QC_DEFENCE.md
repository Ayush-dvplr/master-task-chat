# QC_DEFENCE 3040f47 cleanroom-window-schedule

Anticipated QC findings and the planned answer (QC_FIX_PLAYBOOK_v2 row; no lever softened).

| check / ruling | risk | planned answer |
| CL-4 exactness too strict | whole-doc exact per book | REBUT: instruction states only an exact match counts (FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately"); one-fact-wrong score shown in COST_TABLE; fallback partition = feasibility / optimality / rollups already separate tests |
| CL-2, IN-2 hidden rule | carry across nights, crew lead time | every rule in the contract file in plain words (G-1); no emphasis sentence (G-8); RULE_COVERAGE row per rule |
| IN-15/16/17 instruction | rule text or banned words in instruction.md | W10 one contract file; instruction holds job, paths, exactness, seconds, lookup sentence; scan for test/grader/verifier/judge/reward words |
| DS-4 ids | ids encode order or answer | random neutral night and job ids; date order lives only in audit.toml |
| DS-27 TRUTH provenance | scaffold provenance vs VB 15.5 | keep what the scaffold writes; if VB 15.5 and DS-27 disagree, record OPEN CONFLICT Q18 |
| AL-27 rule without triggering rows | rejection codes untested | every code planted in shipped book and in every hidden book; generator asserts presence |
| AL-1/AL-2/AL-28 | solution and tests agree by shared code | tests reference is a different formulation; check_exact.py brute force third opinion; TS-S13 overlap measured |
| TS-13, TS-20, TS-23 | flaky timing, warn on runtime | per-book timeout 10 s x nights, oracle measured in Docker <= 1/3 of it; TS-23 warn kept and recorded |
| TS-16/TS-19/TS-25/TS-26 | tests weak or order dependent | each test independent, fresh tmp dir, first differing record in message; TS-26 fixed manually as KNOWLEDGE notes |
| TS-24/28/29 hardening | executing agent code | run as uid 1000, python -I, foreign cwd, timeouts, checks never raise outside assert; H6 _grant_read for dropped uid |
| A5 volume | playground removed | >= 2k lines in every csv/tsv/jsonl, >= 20k total, verified by script in P2 |
| A3 > 35 tests | warn | about 30 tests; record only |
| QC_RULINGS hidden generator bounds | hidden data outside stated limits | generator asserts every contract limit over 300 seeds |
| QC_RULINGS absence-shaped positive | "no extra keys" style positives | none; only negative is the /tests/ read act (-5) |
| JD-7/JD-8/JD-15/JD-18 judge | label and weight issues | conduct criteria labelled per J-rules; constraint criteria labelled instruction following; weights in {±1,±3,±5}; header only mode,type,evaluation_target,importance |
| JD-12 >= 8 criteria | too few | 8-10 planned |
| R3 weights | non-exact float weights | integers 5/3/1 and -5; reward.toml 0.5/P per channel |
| H6/TS-30 | dropped uid cannot read data | _grant_read; test.sh chmod 755 /logs/verifier |
| W11 / G-7 | answers in environment/ | no plan, net or rollup shipped; precheck grep for computed totals |

## Lessons for the master
- QC defence table is mostly reusable across optimization tasks | no change: keep per task, rows differ by lever
