# QC_DEFENCE depot-charge-plan (154f570), design stage

Governing rule file for every lever: `environment/data/docs/charging_rules.md` (one rule register, W10). Instruction states job, output paths, exact invocation, whole-document exactness and the rerun promise only.

## L-R1 shared feeder limit per slot
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-27, TS-19, TS-13.
- Live rule (to be written in charging_rules.md "Supply limits"): "In every slot the energy delivered to all buses at all four depots together is at most the feeder limit for that slot: the value in grid.ini, replaced by the derated value for any slot the disruption notice lists."
- Why it passes: IN-15 stated in the governing file (01:45 delegation to a rules file is complete). IN-16 one reading: one number per slot, sum over all depots. IN-17: instruction never says the feeder binds (G-1, IN-17 risk in IDEA). AL-27: fires on every hidden corpus (BRANCH_FIRE 11-20 slots). TS-19: generator asserts every limit inside the stated bounds of grid.ini.
- Fallback: IN-15 row DO (state once as bare property in charging_rules.md, no example); IN-16 row DO (one settling clause "summed over all depots" in the same sentence); IN-17 row: REBUT quoting "Default to keeping the sentence" (01:47); AL-27 row: add hidden reseeded corpus where it fires (already all).

## L-R2 lexicographic objective and exact tie-break
- Rule ids: IN-16, AL-1, AL-27, DS-20, CL-4, TS-26.
- Live rule ("Choosing the plan"): "Of all plans that obey every limit, the day plan is the one with (1) the least sum over buses of class weight times unmet kWh, then (2) the least energy cost, then (3) the least moved energy; if plans are still equal, the plan whose kWh values, listed in order of slot and then bus id with zero for no charge, is greater at the first place the lists differ."
- Why it passes: IN-16 each term a single number; tie-break total order, so the optimum is unique (DS-20: check_exact brute force on small seeds, proto/brute.py 300/300 unique). AL-1: stated, not left to silence. AL-27: tie-break decides on every hidden corpus (bigint_min WRONG on hidden). CL-4: instruction states only an exact whole-document match counts; REBUT quoting FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately" with the one-fact-wrong score from COST_TABLE.
- Fallback: CL-4 row DO (confirm the exactness sentence, rebut with one-fact-wrong score); DS-20 row DO (fix the oracle, never the contract); IN-16 row DO (settling clause "with zero for no charge" already in the sentence).

## L-R3 depot cabinet supply limit per slot
- Rule ids: IN-15, IN-16, AL-27, TS-19.
- Live rule ("Supply limits"): "In every slot the energy delivered to the buses of one depot is at most the cabinets in service at that depot times the cabinet kWh per slot from depots.json; a cabinet the disruption notice lists as out of service is not in service in the listed slots."
- Why it passes: one stated product per depot-slot; fires on hidden 1, 2, 4 and large (1-12 depot-slots); shipped 0.
- Fallback: IN-15 row DO; AL-27 row DO (planted outage block in every hidden corpus via the rare RNG stream).

## Cascade C-coupling (feeder load per slot carried into every region, segment and summary file)
- Rule ids: CL-4, TS-13, TS-26, AL-28.
- Contract sentence (charging_rules.md and instruction.md): "Every bus charge, depot total and fleet total is taken from the single day plan that is optimal under the stated order for all four depots together, including the shared feeder limit."
- Why it passes: TS-26 cascades per view per extract PASS (QC_RULINGS); each check reads one output family of one corpus (TS-13 one property: that family's document). AL-28 is negatives only; negatives here are cheating acts only.
- Fallback: TS-26 row DO (name the observable of each check; mask shared columns outside the owner, G1a); TS-13 row DO (split a check that opens two families).

## Negatives (G4) and judge (J3a/b/c, J4)
- Rule ids: AL-28, JD-7, JD-15, TS-16.
- Negatives: tests/ path read (-5, grader-read anchored sentence), J3a -3, J3b -5, J3c -3; one act per layer, each act <= -5.
- Why: no negative grades a lever or depends on exit code alone; every probe criterion shown by solve.sh `check <id> ok` (JD-7, QL 26 Oct Q1).
- Fallback: AL-28 row DO (stand down overlapping negative); JD-7 row DO (fix the oracle to meet the criterion); JD-15 row DO (re-label constraint criteria as instruction following with the quoted sentence).

## Plain rules (need, rejection reasons, unmet reason, changed flag, formats)
- Rule ids: IN-15, DS-25, AL-27, TS-19.
- Every reason string and output key written in charging_rules.md (DS-25); every rejection branch planted on every hidden corpus by the rare RNG stream (AL-27); RULE_COVERAGE row per rule (G11).
- Fallback: DS-25: add the literal to the governing file; AL-27: add a hidden fixture.

## L-M meter convention per depot (added P12 fix v1, board efdb667, 04:18 IST 1 Nov)
- Rule ids: DS-21, AL-F0e, CL-10, IN-15, IN-16, IN-17, AL-27, TS-19.
- Live rule (charging_rules.md rule 12): each depot's meter reads the tariff with its clock shifted by a whole number of slots (0 to 95, wrapping past midnight); the settlements fit exactly one shift per depot.
- Why it passes: QC v1 DS-21 ruled the unnamed family unreachable; the family is now stated once in the governing file (IN-15 row DO), the shipped data carries a non-zero shift for at least one depot that its own settlements pin uniquely (DS-21 Fix line), hidden corpora keep their own distinct shifts (AL-27 fires on every corpus).
- Fallback: none for unreachability (DS-21 REAL). If the kill row `careful shift search` keeps more than 60% of lever points, the lever is reported gone and the master decides (P12 direction).

## Trap baseline (P12, current tests before any fix, COST_TABLE.md mutant rows)
| lever | single wrong-reading variant | points lost / 191 |
|---|---|---|
| M meter | L_meter_identity | 166 |
| F feeder + cabinets | L_feeder_ignored / L_cabinets_ignored | 166 / 166 |
| T tie-break | L_tiebreak_first_found | 166 |
| C coupling | no separate mutant; graded through the same 166 fresh+mutation points (LEVERS.md) | 166 |

## P12 fix v2 (board 0d6348c, 1 Nov): new and changed checks
Common rule ids for every row below: IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, JD-5, JD-8, AL-2, AL-27, CL-2, CL-3. DS-21 is untouched (rule 12 meter family sentence kept as efdb667 left it). TS-23: 49 checks, above 35, recorded as warn, nothing merged to reach a count (playbook option A).

| check or criterion | change | why it passes | safe fallback |
|---|---|---|---|
| shipped_policy_audit_exact, shipped_summary_exact, shipped_segment_public_exact, shipped_region_east_exact (w3 each) | CL-3: shipped derating limit lowered to 90 kWh per slot (gen_core render shipped branch, same RNG calls); the correct plan now differs from published_plan.csv at all four depots (oracle: 28 buses changed, North 1, South 1, West 2, East 24) | CL-3: a program that copies the published plan writes changed false for every bus and fails all four; IN-15: rule 11 states the derated limit; IN-17: instruction says nothing about the notice binding; TS-19: limit read from the notice, no stated bound; CL-2: forgery still needs the derived documents | if the shipped notice is ruled an announcement, raise the limit until only one depot changes (master note 2 asks at least one) |
| shipped_data_quality_exact, fresh_h1/h3_data_quality_exact (w3), fresh_h*_summary_exact (records_rejected) | AL-27: every corpus (shipped and hidden) now carries an unknown id with a bad window, a retired id with a bad window and a duplicate row with a bad window; each must be rejected with the earlier reason of rule 4 | AL-27: the stated order is exercised on shipped and hidden data; IN-16: rule 4 says "the first of these that applies"; one reason per row, so one reading | if a two-condition row in shipped data is ruled a hint, keep the hidden rows only (playbook NEVER column) |
| (rule 13 sentence) | DS-20: rule 13 now says a published row whose bus_id is not a bus on the plan is ignored and is not rejected; the test reference skips such rows like the oracle; hidden corpora carry one such row (retired bus) | DS-20: contract, oracle and reference agree; the hidden row grades it; IN-15 stated | none needed |
| relocated_fresh_summary_exact (w3, was relocated_copy_summary_exact) | TS-26: the relocated run uses its own fresh set (seed 47713) graded by no other check, still placed several folders deep and run from another working directory | TS-26: it no longer re-reads the h3 summary that fresh_h3_summary_exact pays for; weight unchanged (3), same lever family | fold into the fresh tier at weight 3 if ruled still duplicate |
| default_paths_run_summary_exact (w3) | AL-2 (1): a further fresh set (seed 55109) placed at /app/data, program started with no flags, summary.json read from /app/out; /app/data and /app/out restored byte for byte afterwards | AL-2: the defaults sentence (instruction L9) is now graded by what the program writes; TS-13 one observable (summary.json of that run); TS-26 its seed is graded nowhere else | drop to w1 if ruled overweight |
| negative_run_writes_outside_output_folder (-1) | AL-2 (3), TS-25, TS-16, TS-12: holds when the flagless run creates a file owned by the run user anywhere under /app, /tmp, /var/tmp, /dev/shm outside /app/out | AL-2: instruction L9 "writes only into the output folder" graded by an observable scan of the program's own run; an absence check, so it is a negative (TS-25); the oracle writes only into --out, so an honest program never trips it (TS-16); the test starts the run itself, so no command history is read (TS-12) | nop and stub: no program, so the flagless run raises and the negative stays silent |
| R17 (w3, task completion, final_answer) | AL-2 (2): the reply reports the eight summary.json totals of the /app/data run each with its value | AL-2: instruction L23 promise graded; J6 per-item enumeration, not J1 (no figure named); R13 still penalises a wrong figure (AL-28: R17 rewards presence, R13 punishes mismatch, different acts) | merge into R10 at w5+3 if ruled split |
| R9 (w3, code quality) + malformed_tariff_stops_naming_file (w3, kit W2 allows 1, 3, 5 only) | JD-5/JD-8: R9 keeps only the exception-handler reading (JD-18 keeps the code-quality criterion); the input behaviour half is graded by tests: missing settlements.csv (existing, w3) and tariff.xml cut off halfway (new, rule 22 "cannot be read") | JD-5 one act per criterion; JD-8 no criterion restates a test; oracle solve.py guarded() names tariff.xml on ET.ParseError | drop the new test if ruled duplicate of the missing-file test |
| R16 (w-1, unchanged) | JD-16 kept as warn: the verifier runs in a separate environment and the validator (section 1.12) requires task.toml artifacts to equal the domain-calculation manifest, so the agent's /app/data never reaches the checks; an end-state test would be dead (TS-16). R16 keeps the whole sentence of instruction L19 | JD-16 recorded warn with reason; AL-28 one layer only (judge); JD-15 instruction following label | add a /app/data artifact if the archetype manifest ever allows it |

## P12 fix v3 (board b7fd1ce, 1 Nov): reply sentence, R10, R17
Rule ids for every row below: IN-16, JD-14, JD-15, AL-1, AL-6, QL-5, AL-28, IN-17. Weights, types and annotations unchanged; tests, data and solution code byte-identical (solution/TRUTH.md regenerated by WORK/tools/truth.py for the new judge sha and R17 name).

| sentence or criterion | change | why it passes | safe fallback |
|---|---|---|---|
| instruction.md:23 reply sentence | IN-16/JD-15/AL-1/AL-6/QL-5: "the totals from `/app/out/summary.json`" became "every figure in `/app/out/summary.json` except `plan_date` and `feeder_kwh_by_slot`"; docs/charging_rules.md:43 rule 20 lists the ten fields, so the excluded two leave exactly the eight R17 names | IN-16 one reading: the set is fixed by the document the program writes; JD-15 R17 now grades a stated promise, not a hidden list; IN-17 plain sentence, no method word, no trap wording, no size bound | name the eight fields in the sentence if "every figure" is ruled loose |
| R10 (w5, task completion, final_answer) | JD-14: grades completeness only: "lists the same number of rejected records of the /app/data run as /app/out/data_quality.json holds, each with a file, a line number and a reason" (one positive clause, kit J10/J11 and JD-5 clean); matching is left to R13 | JD-14/AL-28: R10 pays for presence and count, R13 (-5) alone punishes a record that differs, so no act is paid twice; reward and penalty sum per act stays within 5 | merge R10 count into R13 wording if still ruled double |
| R17 (w3, task completion, final_answer; renamed r17_names_summary_figures) | JD-14/JD-15: "names each of the eight /app/out/summary.json figures of the /app/data run that the instruction asks for, namely ..., each with a value" (presence only, one positive clause); matching is left to R13 | JD-14: accuracy only in R13; JD-15: every listed field is promised by instruction L23 plus rule 20; one act (presence of eight named values) | merge into R10 at w5+3 if ruled split |

## Harden r3 (board c5b188a, 1 Nov): lever U raised feeder limit, judge probes R5/R8/R18/R19
Rule ids for every row below: IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, JD-5, JD-8, JD-14, JD-16, AL-2, AL-27, AL-28, CL-2, CL-3. Instruction, docs/, shipped data and the notice heading are byte-identical (no doc sentence added, IN-17).

### Full answer: "derating reads as lowering" (DS-21 / IN-16)
Rule 11, docs/charging_rules.md:23, word for word:
"11. In every slot the energy delivered to all buses at all four depots together is at most the feeder limit for that slot: `feeder_kwh_per_slot` in `grid.ini` section `[feeder]`, replaced by the derated limit for any slot the disruption notice lists under feeder derating."
Rule 2, docs/charging_rules.md:8, word for word:
"2. A time span written "from X to Y" covers every slot that starts at or after X and before Y. This holds for tariff bands, cabinet outages and feeder derating."
The rule names one value per slot: the grid.ini value, "replaced by" the listed limit for a listed slot. It never says the listed limit is lower, never says "the lower of", and no other sentence bounds it. Grep run in the bundle root (full output, WORK/h3_a1/grep_derate.txt):

```
$ grep -rniE "derat|feeder|below|lower|reduc|at most|exceed|above|cap" instruction.md environment/data/docs environment/data/grid.ini environment/data/disruption_notice.md
instruction.md:3:A city bus operator charges its electric buses overnight at its North, South, West and East depots, which all draw from one shared grid feeder. Each evening it needs one charging plan for the coming day. The data folder `/app/data` holds the fleet register, the duty roster, the next day's trips, the bus types, the depots, the grid settings, the service classes and contracts, the tariff, the settled meter history, the published plan and the disruption notice. The operator's rules for the day plan and for every report are written in `/app/data/docs/charging_rules.md`.
instruction.md:9:with `--data` defaulting to `/app/data` and `--out` defaulting to `/app/out`. It reads only the data folder it is given and writes only into the output folder, where it creates the documents below; for the run on `/app/data` they are:
instruction.md:17:Use the Python 3 standard library only, with no network access. One run of the program may take at most 120 seconds.
instruction.md:21:Each output document is graded whole, and only an exact match of the document counts. Your program will also be run again, with the command above, on fresh data folders in the same layout, and its output there is graded the same way.
instruction.md:23:When you finish, reply with a short account of the run on `/app/data`: every figure in `/app/out/summary.json` except `plan_date` and `feeder_kwh_by_slot`, and every record the run rejected, each with its file, line and reason.
environment/data/docs/charging_rules.md:8:2. A time span written "from X to Y" covers every slot that starts at or after X and before Y. This holds for tariff bands, cabinet outages and feeder derating.
environment/data/docs/charging_rules.md:16:7. A bus's need is the sum of `kwh` of its trips in `trips.jsonl` whose `service_date` is the day after the plan date, plus the kWh of every extra trip the disruption notice lists for that bus on that date, plus the `reserve_kwh` of its type, minus its `soc_arrival_kwh`. A need below zero is zero.
environment/data/docs/charging_rules.md:21:9. A bus receives a whole number of kWh in each slot of its window, from 0 to its `max_kwh_per_slot`, and nothing outside its window. The energy delivered to a bus over the day is at most its need.
environment/data/docs/charging_rules.md:22:10. In every slot the energy delivered to the buses of one depot is at most the cabinets in service at that depot times `cabinet_kwh_per_slot` from `depots.json`. A depot's cabinets in service are its `cabinets` in `depots.json`, less any cabinets the disruption notice lists as out of service at that depot for that slot.
environment/data/docs/charging_rules.md:23:11. In every slot the energy delivered to all buses at all four depots together is at most the feeder limit for that slot: `feeder_kwh_per_slot` in `grid.ini` section `[feeder]`, replaced by the derated limit for any slot the disruption notice lists under feeder derating.
environment/data/docs/charging_rules.md:34:16. Every bus charge, depot total and fleet total is taken from the single day plan that is optimal under the stated order for all four depots together, including the shared feeder limit.
environment/data/docs/charging_rules.md:41:18. `region_<depot>.json`, one per depot (`North`, `South`, `West`, `East`): `depot`, `buses` (number of buses on the plan at the depot), `energy_kwh`, `cost_cents`, `unmet_kwh` (depot totals), and `slots`, one entry per slot `{"slot", "kwh", "feeder_kwh"}` where `kwh` is the depot's energy in the slot and `feeder_kwh` is the energy of all four depots together in the slot.
environment/data/docs/charging_rules.md:43:20. `summary.json`: `plan_date`, `weighted_unmet_kwh`, `energy_cost_cents`, `moved_kwh`, `feeder_peak_kwh` (the largest all-depot energy in any slot), `feeder_kwh_by_slot` (one `{"slot", "kwh"}` per slot, all depots together), `buses_planned`, `buses_short` (buses with unmet above 0), `buses_changed` and `records_rejected`.
environment/data/grid.ini:7:[feeder]
environment/data/grid.ini:8:feeder_kwh_per_slot = 1300
environment/data/disruption_notice.md:8:## Feeder derating
environment/data/disruption_notice.md:10:- from 2026-03-14T20:00 to 2026-03-14T22:00: feeder limit 90 kWh per slot
```
No hit bounds a listed limit by the base: the hits are the shared feeder (instruction.md:3), the 120 s limit (:17), whole-document grading (:21), rules 2, 7, 9, 10, 11, 16, 18, 20, the grid.ini value and the notice heading and line. "Derating" is the heading the notice files the line under (rule 11 says "lists under feeder derating"), and the number on the line is the limit. The raised line uses the shipped notice line format byte for byte (`- from <ts> to <ts>: feeder limit <N> kWh per slot`, disruption_notice.md:10), under the unchanged heading `## Feeder derating`, ordered by start time among the folder's other derating lines. Competing reading min(base, listed) is an unstated convention (DS-21 lesson: the graded reading is the stated one, the competing one is not).

| sentence or criterion | change | why it passes | safe fallback |
|---|---|---|---|
| fresh_u1..u9 x 8 plan docs (72 checks, w5) | new held-out folders: a hidden instance (plain render of the same seed, byte-identical except added lines) plus one raised feeder block (limit base x U(1.4,1.9), rounded down to 10, at most the summed cabinet room of the block, at least base + base//5) and cluster buses that can charge only in that block, so the raised limit binds | IN-15/IN-16 stated rule 11 one reading (above); IN-17 no sentence added; DS-21 no unstated convention; TS-19 generator asserts base < limit <= room (no unreachable limit) and every non-added line equals the plain hidden render (300/300 seeds byte-checked); AL-27 rule 11 replacement above base now fires on 9 held-out folders (shipped 90 < 1300 fires the below case); TS-26 each check grades one document of its own folder, no other check reads that folder, data_quality.json not graded on u-folders; CL-2/CL-3 a forgery of shipped answers earns nothing on u-folders (fresh data) | fold to 4 folders (32 checks) if the count is ruled heavy; never merge checks (TS-23) |
| TS-23 count | 120 checks (48 -> 120), recorded as the existing warn | TS-23 >35 is a warn; never merged to reach a count; negatives sum 9 <= 557 | none needed |
| judge R5 r5_roster_depot_run (w3, replaces meter uniqueness witness) | P-a edge-input run: folder where a bus's roster depot differs from its fleet home_depot; show the depot in policy_audit.json | rule 5 charging_rules.md:14 "A bus's depot is the `depot` on its roster row."; no test plants it (roster depot = home depot in every generator branch), so no re-charge (JD-8); one act (JD-5); oracle selfcheck `check roster_depot ok` | drop to 9 probes (band 27/41 = 65.9%) |
| judge R8 r8_tariff_version_change_run (w3, replaces missing input run) | P-a: tariff version in force on the plan date ends on the plan date, next version starts the next day; show energy_cost_cents | rule 12 charging_rules.md:27 "under the version in force on the plan date"; no test plants a version boundary inside the horizon; the removed R8 repeated the missing_settlements test act (JD-8 gone); oracle `check tariff_version_change ok` | drop |
| judge R18 r18_overlapping_outage_run (w3) | P-a: two outage lines cover the same slot at one depot; show that depot's kwh for the slot in its region file | rule 10 charging_rules.md:22 "less any cabinets the disruption notice lists"; no test plants overlap; oracle `check overlapping_outage ok` | drop |
| judge R19 r19_offgrid_arrival_run (w3) | P-a: a roster arrive time between two slot starts; show the bus's charges | rule 5 charging_rules.md:14 window "slots that start at or after arrive"; no test plants an off-grid arrive; oracle `check offgrid_arrival ok` | drop |
| judge band | positive 44 (was 38), probes 10 x 3 = 30 = 68.2% (band 55-70%); R9, R10, R11, R17 and negatives R12-R16 byte-identical | JD-14 no broad criterion beside the probes; JD-16 R16 warn kept (KEPT.md); R10/R17 unchanged so the v2 fails cannot return; AL-28 negatives one act each | none |
