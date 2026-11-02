# TRUTH.md - 43249294-8b2f-5aaf-9f19-83fd9d0adfc4

## Defect

Nothing is broken; the task is to build a billing program whose correctness depends on reading one very long consolidated tariff code completely and bridging provisions that sit far apart. `/app/data/tariff_code.md` has 965,481 characters (161,195 words, 207,719 cl100k tokens), 10,243 lines and 824 numbered sections in 16 Parts. Original provisions (Schedule 2 classes at 2-101 to 2-172, Schedule 3 zones at 3-101 to 3-148, Parts 4 to 7 and 9 to 12) print base figures that are frequently not in force. Part 15 holds 228 value-changing amendments in Division 15-1 (dated quote substitutions, dated statements, quarter-only and bounded periods, undated substitutions, repeals, omit and insert), 81 typo-style corrections in Division 15-2 (21 of them correct a Division 15-1 section), one rebate created in Division 15-3 and procedural amendments and heading corrections that change nothing graded. Division 15-9 prints proposals in exactly the amending phrasing; Part 16 mixes four Binding Rulings with memoranda and examples that state wrong figures. Four substantive sentences sit inside long procedural sections of Parts 8, 13 and 14.

1. (focal) Order of application (1-006). Original text read with its corrections; displacing provisions outside Part 15; amendments in order of their date of making (same day: section, then subsection); Binding Rulings last. Section order is not making order: 10 block rates are amended twice, the later-printed section made months earlier (TC-143:2 at 15-257, TC-172:1 at 15-260, TC-115:2 at 15-262, TC-164:1 at 15-263, TC-170:1 at 15-264, ...). Applying amendments by section number scores 0.338. `probe_correction_of_amendment_order`, `policy_audit_matches_reference`.
2. (focal) Corrections of amendments. Division 15-2 corrects 15 amended figures, 4 amended start days and 2 dates of making (15-417 -> 15-257(1), 15-432 -> 15-260(1)); a made-date correction flips which of two amendments of the same rate prevails. A corrected figure takes the correcting section as its authority; a corrected day or date of making does not. Ignoring Division 15-2 scores 0.056. `probe_correction_of_amendment_order`.
3. (focal) Daily apportionment. Each meter interval is spread evenly over its days and each day is charged at the block rates and wastewater rate in force that day; rates change on mid-month days, for quarter-only windows and for bounded periods; service charges change by quarter; trade waste uses the rate on the first day of the return's quarter; interest changes on 1 February 2027. `probe_date_effective_periods`.
4. (focal) Rebate order and limits. 1-086 orders rebates by priority, ties by establishing section: RB-01 (10, 9-120), RB-03 (15, 9-131), RB-02 (20, 9-125), RB-08 (25, 9-158), RB-06 (30, 9-147), RB-04 (40, 9-138), RB-11 (40, 15-608), RB-05 (45, 9-142), RB-07 (50, 9-153), RB-10 (55, 9-169), RB-09 (60, 9-164). RB-08 moves from 70 to 25 by amendment; RB-11 is created at 15-608 with priority 40 and follows RB-04 (9-138) on the tie; RB-01 gains veteran cards; RB-07's limit is repealed; RB-09's trust exclusion is repealed; every rebate is limited by its own limit (once across current and carried amounts), the remaining Gross Charge and 40 per cent of Gross Charge. Ordering by code scores 0.451. `probe_rebate_order_and_limits`.
5. (trap) Buried override at section 8-047(6), "Delegation of functions to authorised officers" (line 4013). Target: catchment levy percentage, section 5-210(2), printed 3.2500 per cent. In force: 3.7500 per cent (every non-exempt account). Text: "Without limiting any other provision of this Part, the percentage stated in section 5-210(2) is taken to be 3.7500 per cent for the tariff year 2026." Defeated probe: `probe_buried_substitutions` (and, through the cascade, every region, summary, segment and hidden-batch check).
6. (trap) Buried override at section 13-062(4), "Form of notices served on occupiers" (line 5745). Target: all four regional surcharge rates, section 7-010(1)(a)-(d), printed 4.2500 / 3.6000 / 5.1000 / 2.9500 per cent. In force: each +0.6000 points: 4.8500 / 4.2000 / 5.7000 / 3.5500 per cent (every account). Text: "Notwithstanding section 7-010, for the tariff year 2026 each regional rate stated in that section is increased by 0.6000 percentage points." Defeated probe: `probe_buried_substitutions` (and, through the cascade, every region, summary, segment and hidden-batch check).
7. (trap) Buried override at section 13-118(7), "Retention of meter reading records" (line 6681). Target: daily service charge of a 20 mm meter, section 6-020(2)(a), printed $0.8240. In force: $0.8860 (955 of the 2,352 visible meters, mostly residential). Text: "Subject to this Division, the daily service charge stated in section 6-020(2)(a) for a meter of 20 mm has effect for the tariff year 2026 as if it were $0.8860." Defeated probe: `probe_buried_substitutions` (and, through the cascade, every region, summary, segment and hidden-batch check).
8. (trap) Buried override at section 14-031(3), "Adjournment of review hearings" (line 7211). Target: Band A block 1 daily allowance, section 4-020(2)(a), printed 450 litres. In force: 410 litres per day (every Band A interval above 410 litres a day). Text: "Notwithstanding section 4-020, for the tariff year 2026 the block 1 allowance for Band A is 410 litres per day." Defeated probe: `probe_buried_substitutions` (and, through the cascade, every region, summary, segment and hidden-batch check).
9. (drift) Material with no legal effect (1-004). Division 15-9 proposes new regional surcharges, a 4.0000 per cent catchment levy, a $0.9150 20 mm charge from Q3, a 500-litre allowance, a 50 per cent overall limit, 8.2500 per cent interest from 1 October 2026, eight block rates, four wastewater rates, priority 5 for RB-07 and corrections of 12-040 and 9-002; Explanatory Memoranda 16-001, 16-005, 16-015, 16-030, 16-047 and 16-061 restate superseded figures, order rebates by code, put carried amounts first and take the billing zone from the largest property; Illustrative Examples 16-008, 16-022, 16-040 and 16-053 compute with wrong figures; 24 Notes print 2025 figures. Applying them scores 0.056. `probe_no_effect_material`.
10. (drift) Binding Rulings prevail (1-005). 16-012 takes the billing zone (and so the region file and drought supplement) from the zone of greatest consumption, ties to the lowest zone number, instead of 3-002's earliest connection; 16-019 prorates the minimum by active days although 11-010(3) says it is not reduced; 16-027 moves a payment made on a non-business day to the next business day for ordering, grace and interest, but tests lateness against the assessment date on the actual day; 16-034 applies the current-year amount before carried amounts, reversing 10-003. Ignoring the rulings scores 0.408. `probe_binding_rulings`.
11. (trap) Rounding stages (1-082). Half to even for water lines, service charges per meter, trade waste returns, surcharge, rebate amounts and limits; half up for wastewater lines, stormwater, catchment levy, prorated minimum and interest per part. The rounding probe carries exact half-cent ties at seven stages with an even lower neighbour; half up everywhere scores 0.408 and half even everywhere 0.549. `probe_rounding_stages`.
12. (drift) Defined aggregates far from use. Volumetric Charges, Service Charges, Base Charges, Supply Total and Gross Charge are defined in the 1-2xx dictionary and used as rebate limits, surcharge base and catchment base in Parts 5 to 12; an experienced reader collapses them into "the bill". `probe_rebate_order_and_limits`, `hidden_batch_eval_matches_reference`.
13. (trap) Recorded matters. Readings outside a meter's supply window, readings lower than the preceding reading (nil interval, next interval from the lower reading), trade waste returns of non-commercial accounts, claims under no rebate, under a rebate that arises without claim or by an ineligible account, leak claims repaired outside 2026, carry-forwards not permitted or expired, and payments after the assessment date. `data_quality_matches_reference`, `probe_no_effect_material`.

Cross-references whose meaning depends on text at least 1,000 lines away (line distance between section headings):

- 9-120 uses Service Charges from 1-249: 3,976 lines
- 9-131 uses Water Supply Charges from 1-208: 4,228 lines
- 9-142 uses Volumetric Charges and drought property from 1-201: 4,322 lines
- 9-158 uses Gross Charge from 1-252: 4,158 lines
- 9-164 uses Supply Total from 1-207: 4,410 lines
- 9-169 uses Large Meter from 1-231: 4,310 lines
- 9-153 uses community organisation from 1-214: 4,322 lines
- 9-001 uses order of rebates from 1-086: 4,192 lines
- 9-002 uses rounding of the overall limit from 1-082: 4,248 lines
- 12-010 uses business days from 1-088: 4,574 lines
- 12-010 uses public holidays from 1-090: 4,568 lines
- 12-040 uses rounding of interest from 1-082: 4,648 lines
- 11-010 uses residential account from 1-248: 4,282 lines
- 7-010 uses Base Charges from 1-254: 2,692 lines
- 6-030 uses supply window of a property from 1-230: 2,788 lines
- 5-110 uses commercial account from 1-241: 2,674 lines
- 12-050 uses Net Charge from 1-213: 4,520 lines
- 9-147 uses repair date from 1-212: 4,302 lines
- 9-147 uses block 3 rate of the class from 2-101: 4,024 lines
- 13-062 uses regional rates from 7-010: 2,566 lines
- 14-031 uses Band A block 1 allowance from 4-020: 4,172 lines
- 13-118 uses 20 mm daily service charge from 6-020: 3,538 lines
- 16-012 uses billing zone rule from 3-002: 7,766 lines
- 16-034 uses order of amounts from 10-003: 5,424 lines
- 16-019 uses minimum annual charge from 11-010: 5,376 lines
- 15-608 uses Part 9 rebate machinery and priority ties from 1-086: 9,762 lines

Grep check: none of the four buried sentences contains any Amending-Part phrasing ('substitute', "read '", ' omit ', 'insert', 'repealed', 'With effect from', 'for the period beginning', 'quarter of the tariff year'); 8-047: 0 hits; 13-062: 0 hits; 13-118: 0 hits; 14-031: 0 hits. In Parts 8 to 16 the phrases they do use also occur in procedural boilerplate: 'taken to be' 538 lines, 'Notwithstanding section' 525 lines, 'has effect as if' 518 lines.

The reference is a Python 3.12 standard-library program (934 lines) that parses `tariff_code.md` at run time into originals, displacing provisions, amendments, corrections and rulings, resolves them under 1-006, and computes the statements; `solve.sh` installs it at `/app/out/derive_report.py` and runs it on `/app/data`. Every value in force is derivable from the text of the Code alone; the unseen batches differ only in their register values. Grading has a deterministic channel (`tests/test_output.py`) and a judged channel (`tests/judge.toml`).

Out of bounds: embedding visible account identifiers or totals (`negative_hardcoded_sample_answers`); different statements for the same batch under another directory name (`negative_filename_dependent_behaviour`); reading `/app/data` while billing another batch (`negative_reads_training_corpus_at_runtime`); output that varies between runs (`negative_nondeterministic_output`); reading the clock or randomness (`negative_reads_clock_or_randomness`); writing outside the output directory or into the input directory (`negative_writes_outside_out_dir`); rebinding interpreter or verifier machinery (`negative_rebinds_verifier_dependencies`); referring to verifier or log files (`negative_reads_tests_or_reward_files`); network, process or third-party imports (`negative_external_dependency_or_network`).

## Load-bearing work

10 artifacts are collected and every one is graded:

- `/app/out/derive_report.py`
- `/app/out/summary.json`
- `/app/out/policy_audit.json`
- `/app/out/data_quality.json`
- `/app/out/region_North.json`
- `/app/out/region_South.json`
- `/app/out/region_West.json`
- `/app/out/region_East.json`
- `/app/out/segment_commercial.json`
- `/app/out/segment_public.json`

- `/app/out/derive_report.py` is executed by the verifier as an unprivileged user on two unseen batches generated at grade time (300 accounts each; different seeds, batch identifiers, assessment dates 2027-03-31 and 2027-04-30, directory names `rb_eval` and `batch_q4_challenge`, shuffled row order), on seven probe batches, on a copy of the visible batch and a renamed copy (each run twice), a poisoned `/app/data` (run twice), a write-isolation copy and a repeat run of the first unseen batch. Every run is handed an existing, empty output directory. It is also parsed as source by the cheat checks, which ignore comments and docstrings.
- `policy_audit.json` states every applied value with its controlling section (block rate periods of 72 classes, bands, discharge factors, catchment treatment, 48 zones, allowances, service charge periods, surcharges, drought supplement, catchment levy, trade waste periods, rebates in application order, overall limit, minimum charges, grace, interest periods, due dates, rulings). It is the same for every batch under this Code, so it is the purest test that every modifier was found. It is graded once, on the visible batch; the unseen-batch checks compare only its `report_id`.
- The four region files carry one assessment object per account (meter intervals, meters, properties, every charge, rebates in order, carry-out, minimum, instalments, interest, balance); an account placed in the wrong region by the billing-zone ruling fails two files at once.
- `summary.json`, `data_quality.json` and the two segment files are batch rollups and the recorded-matter list.

Input files (12): `/app/data/accounts.csv`, `/app/data/batch.json`, `/app/data/carryforwards.csv`, `/app/data/concession_claims.csv`, `/app/data/leak_claims.csv`, `/app/data/meter_reads.csv`, `/app/data/meters.csv`, `/app/data/payments.csv`, `/app/data/properties.csv`, `/app/data/report_format.md`, `/app/data/tariff_code.md`, `/app/data/trade_waste.csv`. Every one is needed: the Code supplies every value, the format fixes the shape, the manifest supplies the batch id and assessment date, and each of the nine registers feeds at least one graded figure (accounts: class, card, window; properties: zone, class, area; meters: size, window; readings: consumption; trade waste: trade waste charge; claims and leak claims: rebates; carry-forwards: carried amounts; payments: instalments and interest).

Out of bounds by design: a program that only works on `/app/data`, that reads a hard-coded Code path, that cannot be run by another user, or that uses floats for money or litres.

## Verification

`tests/test.sh` hardens the verifier and runs `rewardkit /tests --workspace /app`. rewardkit scores the checks in `tests/test_output.py` (Channel A) and the criteria in `tests/judge.toml` (Channel B); `tests/reward.toml` divides each channel's weighted sum by its positive total and gives each half of the reward.

Channel A has 21 positive and 9 negative checks, positive weight total 71 and negative weight total -31, so it ranges from -31/71 = -0.437 to +1.000. Every content check compares exact JSON values with matching JSON types (true is not 1, 1.0 is not 1): there is no tolerance and no partial credit inside a check. The visible-batch checks compare whole statements; the two unseen-batch checks (weight 5 each, regenerated in the verifier) compare the eight batch statements whole and the policy audit by `report_id` only. Each of the seven probes (weight 5 each) compares only the account fields its trap family decides, plus the recorded matters where the probe carries them, so a fault in an unrelated rule does not fail every probe.

Positive checks (21):

- `artifact_set_exists_and_parses` (weight 1)
- `canonical_serialization_and_sorted_keys` (weight 1)
- `policy_audit_matches_reference` (weight 5)
- `data_quality_matches_reference` (weight 1)
- `summary_matches_reference` (weight 3)
- `region_north_matches_reference` (weight 3)
- `region_south_matches_reference` (weight 3)
- `region_west_matches_reference` (weight 3)
- `region_east_matches_reference` (weight 3)
- `segment_commercial_matches_reference` (weight 1)
- `segment_public_matches_reference` (weight 1)
- `hidden_batch_eval_matches_reference` (weight 5)
- `hidden_batch_challenge_matches_reference` (weight 5)
- `probe_buried_substitutions` (weight 5)
- `probe_correction_of_amendment_order` (weight 5)
- `probe_no_effect_material` (weight 5)
- `probe_binding_rulings` (weight 5)
- `probe_rebate_order_and_limits` (weight 5)
- `probe_date_effective_periods` (weight 5)
- `probe_rounding_stages` (weight 5)
- `reusable_program_runs_unprivileged` (weight 1)

Negative checks (9), each holding only when the cheat is present:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -3)
- `negative_reads_training_corpus_at_runtime` (weight -3)
- `negative_nondeterministic_output` (weight -3)
- `negative_reads_clock_or_randomness` (weight -3)
- `negative_writes_outside_out_dir` (weight -3)
- `negative_rebinds_verifier_dependencies` (weight -3)
- `negative_reads_tests_or_reward_files` (weight -5)
- `negative_external_dependency_or_network` (weight -3)

One act costs one penalty: output that differs between two runs of the same batch fires only `negative_nondeterministic_output` (the directory-name and `/app/data` checks stand down when either compared program is not self-consistent), and not even that when `negative_reads_clock_or_randomness` already fires. The source checks parse the program, so comments and docstrings never trigger them.

Channel B has 14 criteria, positive total 26, negative total -18:

- **R1** (+5, trajectory): The agent writes out a table of modifying provisions, each row giving a section number, the value it modifies and its effect, with rows for at least 100 distinct sections of Division 15-1, rows for at least 40 corrections in Division 15-2 including at least one correction of a Division 15-1 section, and rows for the four provisions at sections 8-047, 13-062, 13-118 and 14-031, giving the quarter or period of each amendment limited to one quarter or to a period from one day to another, and the table appears in the trajectory before the last edit of /app/out/derive_report.py.
- **R2** (+3, trajectory): The agent states, before the last edit of /app/out/derive_report.py, for an amendment whose date of making is corrected by Division 15-2, which of the amendments of the same figure prevails once the corrected date of making is applied.
- **R3** (+3, trajectory): The agent states, before using any of them in the program, that Division 15-9 proposals, Explanatory Memoranda, Illustrative Examples and Notes have no legal effect under section 1-004, and that Binding Rulings prevail over conflicting text under section 1-005.
- **R4** (+3, trajectory): The agent explains that original text is read with its Division 15-2 corrections, including corrections of Division 15-1 sections, and that amendments then apply in the order of their dates of making, and illustrates the order with at least one concrete figure or date taken from the Code.
- **R5** (+3, trajectory): The agent works one account through by hand, showing its meter intervals with blocks, wastewater, service and stormwater charges, surcharge, catchment levy, rebates in order, minimum charge, instalments and interest, and compares those figures with the program output for the same account.
- **R6** (+3, trajectory): The agent builds at least one batch of its own in a directory other than /app/data and runs the finished program on it.
- **R7** (+1, user_facing_message): The response names /app/out as the output directory.
- **R8** (+1, user_facing_message): The response lists the checks the agent ran, each with its result.
- **R9** (+1, user_facing_message): The response lists at least twenty section numbers of modifying provisions the program applies, including at least one section outside Part 15.
- **R10** (+3, trajectory): The agent leaves /app/out/derive_report.py with no bare except clause, no dead or duplicated code blocks, no leftover debug output, and function and variable names that state what each one holds.
- **R11** (-5, final_answer): The response claims a check, test, comparison or hand derivation that the trajectory shows was never run, or reports a result that differs from the output shown in the trajectory.
- **R12** (-5, trajectory): The agent opens a file under /tests or /logs.
- **R13** (-5, trajectory): The agent retrieves task-specific answers or solutions from a source outside /app/data, /tests and /logs.
- **R14** (-3, trajectory): The agent edits, deletes, renames or overwrites a file under /app/data.

Single-rule mutants of the oracle, scored on Channel A with a rewardkit stub over the real `tests/test_output.py` (score = passed positive weight / 71):

| Mutant | Score |
|---|---|
| oracle | 1.000 |
| ignore_buried_overrides | 0.056 |
| ignore_corrections | 0.056 |
| ignore_all_modifiers | 0.042 |
| applies_no_effect_material | 0.056 |
| wrong_credit_order_by_code | 0.451 |
| amendments_in_section_order | 0.338 |
| ignores_binding_rulings | 0.408 |
| rounds_half_up_everywhere | 0.408 |
| rounds_half_even_everywhere | 0.549 |

The Harbor execution runs (oracle x5, nop, stub, owner-only oracle on `exe_copy.py` tests-only copies) have not been run on this revision.

## Root cause

**Consolidation without incorporation.** Every amendment, correction, displacing provision and ruling is printed where it was made. The value in force is a function of the original and every modifier, wherever printed; 1-006 is the only provision that says how they combine.

**Two orders, not one.** Corrections are read into the text first, including into amending sections, so a corrected start day or date of making changes how amendments combine. Amendments then apply by date of making, not by section number and not by start day.

**Distance as the difficulty.** Order, rounding, day counting, business days, holidays and the defined aggregates sit in Part 1 (lines 1 to 516); rebates, carry-forward, minimum charges and interest sit after line 4,300; the rulings sit at the very end. The four displacing provisions sit inside procedural Parts whose boilerplate uses the same openings ("Without limiting", "Subject to this Division", "Notwithstanding section") and the same verbs ("is taken to be", "has effect as if").

**Breadth.** 228 amending items over 107 sections, 81 corrections, procedural amendments interleaved in the same Division, and a no-effect Division printed in the same phrasing.

**Red lines.** No embedded answers, no reads outside the batch directory, no network or subprocesses, no clock, no floats in money, no writes outside the output directory, no use of non-binding figures.

## Solution shape

1. Split `tariff_code.md` into Parts, Divisions and sections; drop Notes, Division 15-9 and every Part 16 document not designated a Binding Ruling.
2. Read originals: Schedule 2 (three block rates, catchment treatment, band, discharge factor), Schedule 3 (region, Drought Zone, wastewater and stormwater rates), 4-020 allowances, 5-110, 5-210, 6-020, 7-010, 7-020, 9-002, every rebate section (including 15-608), 11-010, 12-030, 12-040 and the holidays of 1-090.
3. Read the displacing provisions anywhere in Parts 1 to 14 (8-047, 13-062, 13-118, 14-031).
4. Read Division 15-1 items with their dates of making and periods, and Division 15-2 corrections; read each correction into the original or amending text it names (figure, start day or date of making).
5. Resolve: originals as corrected, displacing provisions, amendments sorted by (date of making, section, subsection) over daily series; record the authority of every period.
6. For each account: supply windows; readings taken into account; meter intervals; daily block split and daily rates; wastewater; service charges per meter; stormwater; trade waste; billing zone by the ruling; surcharge with drought supplement; catchment levy; Gross Charge.
7. Rebates by priority then section, current-year amount first then carried amounts oldest first, each limited by its own limit, remaining charge and overall limit; carry-out; prorated minimum and top-up.
8. Instalments with moved due dates; payments moved off non-business days, applied by (effective day, id); interest per part outside the grace period, half up; balance; write the nine statements canonically.

## Ordered plan

1. Read 1-004, 1-005, 1-006, 1-080 to 1-092 and the headings of Parts 15 and 16 before writing code; state which material has legal effect and that rulings prevail (R3, R4).
2. Search the whole Code, not only Part 15, for provisions that change values printed elsewhere; find 8-047, 13-062, 13-118 and 14-031.
3. Work out which amendment prevails where Division 15-2 corrects a date of making (15-257, 15-260) and say so (R2).
4. Write the modifier table covering Divisions 15-1 and 15-2 (including corrections of amending sections) and the four outside provisions, with the quarter or period of every limited amendment, before the last program edit (R1).
5. Implement; hand-trace one account through intervals, blocks, charges, surcharge, levy, rebates, minimum, instalments and interest and compare with the program (R5).
6. Build a private batch (part-year accounts, readings outside windows, lower readings, unknown rebate codes, carried amounts, weekend payments) and run the program on it twice (R6).
7. Report the output directory (R7), the checks actually run with results (R8) and the modifier sections applied (R9), claiming nothing the session does not show (R11).

## Pitfalls

- Using the figure printed in Schedule 2 or Schedule 3 for the whole year fails `policy_audit_matches_reference` and every region check.
- Applying amendments by section number or by start day fails `probe_correction_of_amendment_order` and `probe_date_effective_periods`.
- Applying a correction of an amending section to the original figure, or ignoring corrected dates of making, fails `probe_correction_of_amendment_order`.
- Stopping the search at Part 15 misses 8-047, 13-062, 13-118 and 14-031 and fails `probe_buried_substitutions` and, through the surcharge, every account.
- Filtering out lines that begin "Without limiting", "Subject to this Division" or "Notwithstanding section" as boilerplate removes three of the four displacing provisions.
- Ordering rebates by code, or ignoring the RB-08 priority amendment or the RB-04/RB-11 tie, fails `probe_rebate_order_and_limits`.
- Taking the billing zone from the largest property (16-061) or from 3-002 alone fails `probe_binding_rulings` and moves accounts between region files.
- Using a Division 15-9 figure, an Explanatory Memorandum or a Note fails `probe_no_effect_material`.
- Rounding every stage the same way fails `probe_rounding_stages`.
- Reading `/app/data` instead of the argument fails every unseen-batch check and fires `negative_reads_training_corpus_at_runtime`.

## Provenance

```yaml
uuid: 43249294-8b2f-5aaf-9f19-83fd9d0adfc4
instance_id: 43249294-8b2f-5aaf-9f19-83fd9d0adfc4
task_name: terminal-bench/43249294-8b2f-5aaf-9f19-83fd9d0adfc4
fix_patch_sha256: 9d4e89b5dd65737a48e9c5a095eecac6924d086214e763d8b038ea2ce9f223a2  # sha256 of solution/solve.sh
solve_py_sha256: 3a6698a46cc64d7a893911c7ebd3881408c1f06d67d5abde6ef72073f50af424  # sha256 of solution/solve.py
language: python
seeds: {challenge: 8839120457716203, eval: 3371946620085517}  # unseen batches generated at grade time
golden_score_measured: null  # tests-only channel; Harbor runs not yet made on this revision
golden_score_runs: null  # Harbor runs not yet made on this revision
golden_score_channel_b_pct: null  # the judged channel has no oracle score
caveat: >
  Channel A ranges -31/71 to +1.000 on its own; Channel B carries 14 criteria worth 26
  positive points. tests/reward.toml gives each channel half of the reward.
```
