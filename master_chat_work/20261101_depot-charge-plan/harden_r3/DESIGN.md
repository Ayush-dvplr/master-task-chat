# depot-charge-plan harden r3 (board c5b188a): DESIGN

Base: BUNDLE tree 088691cb6539 (= Tasks_INPUT = attempt-1 bytes), kit 5574d77e. Diagnosis: OUT/TRIP.md.
Runs: `_runs/20261101/depot-charge-plan/harden3-20261101T1746/` (fuzz h3fz_*.log, kill h3kill.log, old tests oldkill/, selfcheck_proto.log; each ends ALL_DONE).

## 1. Diagnosis in one paragraph
a1 = tests 197/197 + judge 17/38 (R12 -3 did fire: 20 - 3; master note said none fired). The a1 program reads every
value from the files and matched the reference on 1200 fuzz folders (shipped, hidden, hidden_reorder, large, 300 seeds
each, all MATCH). The one documented behaviour it gets wrong: a feeder derating line whose limit is ABOVE
`feeder_kwh_per_slot`. a1 `derive_report.py:519-523` takes `min(base, derate)`; the rules say the base is "replaced by"
the derated limit. No current generator branch plants it (every hidden derate is below base; shipped 90 < 1300).

## 2. Lever (WRONG kind, tests): held-out "uplift" folders (route-1 R4 L2)
Fact: for a slot listed under feeder derating, the feeder limit is the listed number, also when it is above the
`[feeder]` value.
- Cite: `environment/data/docs/charging_rules.md:23` rule 11 "at most the feeder limit for that slot:
  `feeder_kwh_per_slot` in `grid.ini` section `[feeder]`, replaced by the derated limit for any slot the disruption
  notice lists under feeder derating." Also `:8` rule 2 (span "from X to Y" applies to feeder derating) and `:34`
  rule 16 (one optimal plan including the shared feeder limit). `instruction.md:21` promises fresh folders in the same
  layout. Reference `solution/solve.py:602-605` `feeder_by_slot[s] = limit`.
- Competing reading: "a derating can only lower the limit", i.e. min(base, listed). It is a convention the docs never
  state; the stated verb is "replaced". No doc bounds a derated limit below the base (grep of instruction.md,
  charging_rules.md, grid.ini, notice for derat/lower/reduc/above: only lines 8 and 23). Shipped derate 90 < 1300
  coincides under both readings, so shipped data never contradicts the hidden fact (LEVER_RULES W5, hidden only).
- Generator (WORK `h3_a1/proto/gen_core_up.py`, to be merged into `gen_core.py` and the embedded copy in
  tests/test_output.py): kind "uplift" = the hidden instance of that seed, plus own RNG `Random(seed*7919+3)`: a block
  of 4-8 slots outside the low derate block where the feeder is at base; limit = base x U(1.4, 1.9) capped by the
  block's summed cabinet room (cabinets scaled up when room < 1.5 x base); a cluster of buses whose windows are exactly
  that block, need = rate x length, so unmet minimisation forces delivery above base in every block slot. Rendered as a
  normal notice line `- from X to Y: feeder limit N kWh per slot` under `## Feeder derating`. Conv RNG key 3.
  Assert per seed: limit > base and the reference total in the block > base.
- Fuzz (uplift, seeds 1-300): 300/300 DIFF vs a1, every seed all 8 plan docs differ, data_quality equal; reference slots
  above base 4-8 per seed; 0 generator failures; reference max 3.25 s, a1 max 0.97 s.
- New checks: 9 folders u1..u9, seeds 11113, 22229, 33343, 44449, 55547, 66653, 77761, 88867, 99971, each in its own
  memoised run (one folder failing costs only its own 8 checks), graded on the 8 plan docs (policy_audit, region x4,
  segment x2, summary) at w5 like the existing fresh_h1..h4 docs (TS-20: core outcome = 5; same kind of check, no
  inversion). data_quality not graded there (equal by construction, would pay for a non-lever fact twice; TS-26).
- Names: `fresh_u<i>_<doc>_exact`. 72 new checks, +360 weight. Old 48 checks byte-identical.

## 3. Arithmetic
Positive test weight 197 -> 557. a1 program: 197 + 0 = 197/557 = **35.37%**. Lever share 360/557 = **64.6%** (>= 40%).
Judge (section 5): a1 low 25.0 / mid 31.8 / high 38.6. Pred final = (35.37 + 31.8)/2 = **33.6** (low 30.2, high 37.0;
gate final < 40 met at high too; target <= 35 met at mid and low).
Counts above the prompt's flags: **tests 120 (> 48)**, **criteria 19 (> 17)**. TS-23 (> 35 checks) stays a recorded
warn, nothing merged (QC ruling, district-heat precedent).

## 4. Kill table (Docker, python:3.12-slim / dcp-verifier:1, 4g, 2 cpus; new = 72 checks on u1..u9)
| program | new EXACT/WRONG/CRASH | lever pts kept /360 | old tests /197 | total /557 | % | max s (new) |
|---|---|---|---|---|---|---|
| a1 (paid program) | 0/72/0 | 0 | 197 (graded run) | 197 | 35.4 | 0.75 |
| design blind fd98e12 | 0/72/0 | 0 | 4 (measured now) | 4 | 0.7 | 0.75 |
| design blind d9d6ab5 | 0/72/0 | 0 | 10 (measured now) | 10 | 1.8 | 1.72 |
| blind1 | 0/72/0 | 0 | 10 | 10 | 1.8 | 5.49 |
| blind2 | 0/0/72 | 0 | 6 | 6 | 1.1 | 0.38 |
| blind3 | 0/0/72 | 0 | 6 | 6 | 1.1 | 0.39 |
| first-write | 0/72/0 | 0 | 13 | 13 | 2.3 | 1.90 |
| all-but-one (no tie pass) | 0/72/0 | 0 | 16 | 16 | 2.9 | 1.64 |
| all-but-one (oracle with min feeder) | 0/72/0 | 0 | 197 (measured now, reward 1.0) | 197 | 35.4 | 1.81 |
| careful shift search | 63/9/0 | 315 | 165 | 480 | 86.2 | 2.12 |
| careful shift search + rule 13 | 72/0/0 | 360 | 197 | 557 | 100 | 1.65 |
| oracle | 72/0/0 | 360 | 197 | 557 | 100 | 1.51 |
Reference seconds on uplift folders: max 1.87 s (kill run), 3.25 s (fuzz, 2 workers per container); large hidden
folders max 18 s under contention (<= 30 s = 1/4 of the 120 s limit). Old-test scores for blind1-3, first-write,
all-but-one, careful from the fix v2 kill run (same test_output.py). The careful programs read "replaced" literally and
keep the lever: recorded, not a blocker (route-1 R5 d). Their 9 careful WRONG = one folder hit by its rule 13 gap.
No TIMEOUT anywhere; the lever is WRONG-kind only.
First kill attempt (h3kill_nodocs.log) was a harness slip: the folders lacked `docs/`, which the tests copy in
(`_fresh_tree`); fixed, rerun above.

## 5. Judge changes (tests/judge.toml; proto WORK/h3_a1/proto/judge.toml, parses: 19 criteria)
Removed (acts a1 performs, so they are not probes of skipped acts, and both restate test-graded behaviour):
- R5 r5_meter_uniqueness_witness (a1 step 13 tried all 96 shifts; the meter fit is graded by every fresh folder).
- R8 r8_missing_input_run (a1 step 57 v4 copy; duplicates missing_settlements/malformed_tariff tests, JD-5/JD-8).
Kept unchanged: R1-R4, R6, R7 (probes a1 skipped), R9 code quality (J4), R10 per-item list (J6, w5), R11 final run,
R12 -3 (J3a), R13 -5 (J3b), R14 -1, R15 -5, R16 -1, R17 (passed v3; no figure values graded, no overlap with R13).
Added (P-a edge-input runs for documented branches a1 never exercised and no test plants; each w3, type tool use,
evaluation_target trajectory, importance important):
- R5 r5_roster_depot_run: folder in which a bus's roster row names a depot other than its home_depot in
  fleet_register.csv; shows the depot that bus has in policy_audit.json (rule 5, charging_rules.md:14).
- R8 r8_tariff_version_change_run: folder in which the version in force on the plan date ends on the plan date and
  another starts the next day; shows energy_cost_cents of summary.json (rule 12, charging_rules.md:27).
- R18 r18_overlapping_outage_run: two outage lines cover one slot at one depot; shows that depot's kwh for that slot in
  its region file (rule 10, charging_rules.md:22).
- R19 r19_offgrid_arrival_run: a roster arrive time between two slot starts; shows that bus's charges in
  policy_audit.json (rule 5, charging_rules.md:14).
None re-charges a test trap (J2b): no new probe touches feeder derating. One act per criterion, no menus.
Band: 10 probes x 3 = 30 of 44 positive = 68.2% (55-70%). Oracle shows every probe: prototype
WORK/h3_a1/proto/selfcheck.py adds check roster_depot / tariff_version_change / overlapping_outage / offgrid_arrival;
oracle passes all 13 (`check <id> ok` + witness, 9 s); the a1 program passes them too (so they are judge-only acts,
not hidden WRONG facts).
a1 on the new judge: wins R9 3 + R10 5 + R11 3 + R17 3 = 14, probes 0.
- low 11/44 = **25.0** (R12 -3 fires again, as graded), mid 14/44 = **31.8**, high 17/44 = **38.6** (one probe, e.g.
  R2 from the v3 derate copy, credited leniently).
JD-14/JD-16 unchanged (no new broad criterion; R16 warn kept per KEPT.md). v2 R17/R10 failures not reintroduced.

## 6. QC defence (rows to write in Phase 2; QC_DEFENCE + EVIDENCE_MAP)
- IN-15: the graded rule is rule 11 text at charging_rules.md:23. IN-16: one reading ("replaced by"); min needs an
  unstated convention. IN-17: no doc or instruction change, nothing announces raised limits.
- DS-21: the fact is stated, not a convention; shipped data does not contradict it. Risk named: a reviewer may read
  "derating" as "always lower" and call the raised line odd data. Answer: no stated bound, rule 11 says "replaced",
  the notice line format is the shipped one, and the same verb governs lowered lines.
- TS-19: uplift folders stay inside every stated bound (`_assert_contract_bounds` applied; slot_minutes 15, 96 slots,
  feeder > 0, etc.). AL-27: the uplift folders are the first graded input separating "replaced" from "min" (rule 11
  exercised). TS-23 warn recorded. TS-26: each new check reads one doc of one new folder; no data_quality duplicate.
- JD-5/JD-8: removed R8 (test duplicate); new probes grade acts, not figures. AL-2: no new promise. CL-2: forgery price
  unchanged in kind (fresh folders unseen); CL-3: hidden answers computed at test time by the embedded reference.

## 7. Cost and bar (route-1 R5)
Verifier now ~40 s (kill lanes: 36-45 s); +9 folders x (render + reference + program) ~3-4 s each -> est. 75-90 s vs
timeout 2700 s (90% = 2430). Shipped and visible checks untouched. Oracle 1.0 / owner 1 / nop 0 to be measured in
Phase 3. Docs changed: **no**. Shipped data changed: **no**. Instruction changed: **no**.

## 8. Phase 2 plan (after go)
1. Digest tests/ and solution/ before. 2. Merge the uplift branch into WORK gen_core.py and the embedded generator in
tests/test_output.py; byte-check shipped/hidden/large renders unchanged (300 seeds each) and assert the uplift shape on
300 seeds. 3. Register u1..u9 (`_FRESH` seeds, 72 checks w5). 4. judge.toml as the proto. 5. solve.sh self-check
heredoc gains the 4 new checks (old checks byte-identical). 6. WORK docs (LEVERS, COST_TABLE, QC_DEFENCE,
EVIDENCE_MAP, JUDGE_MAP), TRUTH.md by script last, xref 0. 7. Phase 3 gates once each.

Risk for attempt 2 (not a bar item): the lever bites only an agent that reads "derating" as min; a1, blind1 and both
design blinds did, the careful programs did not.

DESIGN READY: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_depot-charge-plan/harden_r3/DESIGN.md
