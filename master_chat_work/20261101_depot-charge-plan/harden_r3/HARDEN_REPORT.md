# depot-charge-plan harden r3 (board c5b188a)

Bundle `master_chat_work/bundles/depot-charge-plan`, tree 088691cb6539 -> 07c7f6bfb71c. Tasks_INPUT copy synced, tree 07c7f6bfb71c, `diff -rq` empty.
Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. Design: DESIGN.md; trajectory read: TRIP.md; stacking: STACKING_CHECK.md.

## Diagnosis
- a1 final 72.37 = tests 100.0 (197/197) + judge 44.74. Correction to master note 1: R12 (-3, unrun-check claim) did fire, so judge = 20 - 3 = 17/38.
- a1 program (923 lines) reads every value from the files; no shipped-fitted literals (its /tmp/validate.py, step 48, is full of them).
- Fuzz a1 vs reference, 300 seeds per branch (shipped, hidden, hidden_reorder, large): 1200/1200 MATCH. The generator never plants the one documented case a1 gets wrong.
- That case: rule 11 (charging_rules.md:23) says the feeder limit is "replaced by the derated limit"; a1 takes `min(base, derate)` (derive_report.py:519-523). The hidden generator only ever lowers the limit.
- Other documented branches a1 never exercised (roster depot != home depot, tariff version ending on the plan date, overlapping cabinet outages, arrival between slot starts): a1 handles them correctly by reading the code. They became judge probes, not test levers.

## Lever U (tests): held-out uplift folders u1..u9
- Generator `uplift(seed, out)` (WORK/gen_core.py:369-456; embedded in tests/test_output.py:421). It renders the plain hidden instance, then adds one feeder line inside `## Feeder derating`. The line uses the shipped format byte for byte, and its limit sits above `feeder_kwh_per_slot`. It also adds a cluster of buses that can only charge in that block, so the joint plan reaches the raised limit.
- Per-seed asserts: base < lim <= summed cabinet room of the block. Every non-added line is byte-identical to the plain hidden render of the same seed: 300/300 bytes true, 105 seeds walk h to the next qualifying seed (max +7), and test seeds use the walked h.
- 300-seed fuzz: 300/300 DIFF for a1 on all 8 plan docs, data_quality the same 300/300, above-base slots 4-8. Reference max 3.29 s, a1 max 1.25 s.
- Checks: `fresh_u<i>_<doc>_exact` for 9 folders x 8 plan docs (policy_audit, region x4, segment x2, summary), weight 5 each, 72 checks = 360 points. Each folder has its own memoised run, and data_quality is not graded on u folders.
- Code locations: `_UPLIFT` tests/test_output.py:45, `_uplifted` :3517, `_check_uplift` :3773, defs :4087-4442, registrations :4526-4597.
- Old checks are byte-identical: diff of tests/test_output.py before/after is additions only (WORK/h3_a1/g7_test_output.diff), and `render` is untouched.
- Isolation: a program raising on u5 only scores 517/557, losing exactly u5's 40 points.
- DS-21/IN-16 defence (WORK/QC_DEFENCE.md, Harden r3 section): quotes rule 11 (:23) and rule 2 (:8) word for word. The full grep output (WORK/h3_a1/grep_derate.txt) shows no doc bounds a derated limit below the base, and the raised line format is shipped byte for byte. No doc sentence was added, and the notice heading is unchanged.

## Arithmetic
- Tests: 120 (48 + 72; TS-23 warn recorded, never merged), positive 557, negatives -9. reward.toml weights 0.5/557 and 0.5/44.
- Lever share 360/557 = 64.6%. Held-out tier 529/557 = 95.0%.
- a1 program on new tests: 197/557 = 35.37 (measured, full verifier).
- Judge (19 criteria, positive 44, probes 10 x 3 = 30 = 68.2%). a1 regrade: low 25.0 (11/44, R12 fires), mid 31.8 (14/44), high 38.6 (17/44, lenient R2 from step 57 v3 copy).
- Predicted a1 final: (35.37 + 31.8)/2 = 33.6 (range 30.2-37.0). This meets the gate bars (tests < 85, rubric < 85, final < 40) and the master target <= 35.

## Judge changes (tests/judge.toml)
- Removed R5 meter uniqueness witness (a1 did it, step 13) and R8 missing input run (a1 did it; it duplicates the missing_settlements test act).
- Added four P-a edge-input probes (w3, tool use/trajectory/important):
  - R5 `r5_roster_depot_run` (judge.toml:64, rule 5 :14)
  - R8 `r8_tariff_version_change_run` (:103, rule 12 :27)
  - R18 `r18_overlapping_outage_run` (:233, rule 10 :22)
  - R19 `r19_offgrid_arrival_run` (:246, rule 5 :14)
- Oracle self-check prints `check roster_depot|tariff_version_change|overlapping_outage|offgrid_arrival ok` plus a witness (solve.sh:270, 295, 321, 347; seen in gate oracle1 agent log). JUDGE_MAP rows were updated.
- All other criteria are byte-identical. R10/R17/R13 were not touched, so the v2 R17/R10 fails cannot return.
- No new probe is earned by an a1 act. Near misses:
  - step 57 v3 has two North outages at disjoint times (not R18)
  - v1 plan date 03-10 sits inside a version that does not end on the plan date (not R8)
  - a1 never edits roster.csv in a copy (R5/R19)

## Kill table (final tests, full verifier, points /557; U kept /360)
| program | points | % | U kept | U E/W/C | s |
|---|---|---|---|---|---|
| a1 | 197 | 35.4 | 0 | 0/72/0 | 52 |
| dblind_fd98e12 | 4 | 0.7 | 0 | 0/72/0 | 60 |
| dblind_d9d6ab5 | 10 | 1.8 | 0 | 0/72/0 | 74 |
| blind1 | 10 | 1.8 | 0 | 0/72/0 | 155 |
| blind2 / blind3 | 6 / 6 | 1.1 | 0 | 0/0/72 | 56 |
| firstwrite | 13 | 2.3 | 0 | 0/72/0 | 61 |
| allbutone (no tie pass) | 16 | 2.9 | 0 | 0/72/0 | 80 |
| oracle_min (all-but-one U) | 197 | 35.4 | 0 | 0/72/0 | 76 |
| careful shift search | 480 | 86.2 | 315 | 63/9/0 | 77 |
| careful + rule 13 | 557 | 100 | 360 | 72/0/0 | 71 |
| oracle | 557 | 100 | 360 | 72/0/0 | 89 |

The careful enumerator keeps its points; this is recorded, not a blocker (R5 d). Its replace-derates reading is the stated one.

## Cost
- Reference max 17.9 s (large, 3-container contention) against a 30 s bar (120 s limit). u folders 3.29 s, shipped 2.42 s.
- Full tests-only verifier (test.sh): oracle 89 s, a1 52 s.
- Harbor verifier: oracle 115.8 / 109.4 / 123.3 s, owner 124.6 s (bar 2430 of 2700). Details in WORK/COST_TABLE.md.

## Gates
- stacking_check: TS-26 18 groups pass by hand (distinct folder x file), AL-28 hint pre-existing (max 5 per act), data_quality not graded on u folders.
- PRECHECK last line: `PRECHECK CLEAN`. Only WARN [A3] 120 checks (TS-23), 0 IN17/G5 warns; 4 QC scripts exit 0; validator 40 passed 0 failed (PRECHECK.txt, VALIDATOR.txt).
- xref_check 0 findings. TRUTH.md regenerated by script last.
- Harbor gate runs (`_runs/20261101/depot-charge-plan/hardengate-20261101T2019`, exe_copy.py plain/--owner-only/--stub): oracle 1.000 x3, owner 1.000, nop 0.000, stub 0.0018, forgery 0.0287 (16/557).
- Tasks_INPUT: copied solution/{TRUTH.md,solve.sh} and tests/{judge.toml,reward.toml,test_output.py}; `diff -rq` empty.

## Docs changed
No. instruction.md, docs/ and all shipped data are byte-identical. Changes are in tests/ (test_output.py, judge.toml, reward.toml) and solution/ (solve.sh, TRUTH.md).

## Not run
- No paid or judge run of attempt 2; judge scores are predicted from the a1 trajectory regrade.
- Design-blind programs were scored on tests only.

## Lessons for the master
- A clean 300-seed fuzz of every branch with zero DIFF means the lever must come from a documented case the generator never plants; listing never-planted branches should be a standard step 2 output | template_change: add "never-planted documented branches" column to TRIP fuzz table.
- Adding to a rendered instance by inserting lines after render keeps old checks byte-identical and gives a cheap byte-check proof | template_change: prefer post-render insertion for new hidden branches.
- Master note 1 said no negative fired, but R12 had fired; read judge_output per criterion before arithmetic | template_change: none.
