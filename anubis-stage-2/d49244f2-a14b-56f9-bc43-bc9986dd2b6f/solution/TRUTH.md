# TRUTH.md - d49244f2-a14b-56f9-bc43-bc9986dd2b6f

## Defect

Nothing is broken; the task is to build an assessment program whose correctness depends on reading one very long statute completely and bridging provisions that sit far apart. `/app/data/levy_code.md` is a single consolidated Code of 890,744 characters (142,971 words, roughly 200,000 tokens) with 704 numbered sections. Original provisions (Parts 1 to 6 and 8 to 12) print figures that are frequently not the figures in force: the modifying provisions are printed apart from them, and every substantive one of Part 7 sits between 44% and 57% of the document, inside long runs of procedural amendments, typo corrections and transitional text that change nothing graded. A small number of further modifiers are buried late (Part 13 at about 85% and 90%, a Binding Ruling at about 95%). The program must also bridge rules stated near the start (dictionary, rounding, proration, sequence, holidays at 1-080 to 1-092 and the 1-2xx dictionary) to computations stated near the end (credits, carry-forward, minimum levy, instalments, interest).

1. (focal) Composition order. Section 1-004 applies original provisions first and modifying provisions afterwards in ascending section order. A naive "highest section number wins" reading puts 12-020 (7.00 per cent) above the 7-1xx amendment for 2027, and puts every Part 9 original above Part 7. Corrections of Division 7-2 act in place on the provision they correct, so the 7-2xx correction of the 12-020 base rate changes 2026 days only: in force are [{"from": "2026-01-01", "to": "2026-12-31", "rate_ppm": 75000, "authority": "7-253"}, {"from": "2027-01-01", "to": null, "rate_ppm": 82500, "authority": "7-185"}]. `policy_audit_matches_reference`, `probe_instalments_and_interest`.
2. (focal) Quarter and date series. Activity rates change by quarter (amendments with effect from 1 April, 1 July, 1 October 2026), district rates change on arbitrary days, and the same class can carry a corrected original for Q1 and Q2 and an amendment for Q3 and Q4. Corrections that target an amending section rather than the original (7-202 correcting 7-124, 7-205 correcting 7-132) re-fix the amended figure and become its authority. `probe_quarter_rates_and_corrections`, `probe_district_rate_periods`, `policy_audit_matches_reference`.
3. (focal) Unnamed targets. Section 7-194 raises by 500 ppm, from Q4, every class numbered 2-141 to 2-150 whose band as finally in force is III (AC-141, AC-143, AC-144, AC-147, AC-149, AC-150), including a class moved into Band III by a band amendment; section 7-183 reduces by 15 cents per square metre, from 1 September 2026, every South-region Enterprise Development Zone district (D-07, D-27, D-33). Neither names a class or a district, so searching the Code for a class code or a section number misses them. `probe_quarter_rates_and_corrections`, `probe_district_rate_periods`.
4. (focal) Modifiers outside Part 7. 13-065 sets the coastal supplement to 1.5000 per cent (6-020 prints 1.2000); 13-083 sets the K-06 limit to $5,500 (9-125 prints $4,000); Binding Ruling 14-022 doubles the mutual-class payroll exemption; Binding Rulings also change the principal-district test (aggregate floor area by district, lowest code on ties), prorate the minimum levy, and disapply the 10-006 eligibility condition for carried-forward amounts. `probe_principal_district_and_region`, `probe_credit_sequence_and_limits`, `probe_payroll_and_energy`, `probe_minimum_levy_proration`, `probe_carryforward_rules`.
5. (focal) Credit sequence. 1-086 orders credits by the section number of the provision that creates them, so the order is K-11 (4-060), K-03 (5-040), K-12 (7-143), K-05 (9-104), K-07 (9-109), K-09 (9-112), K-02 (9-118), K-06 (9-125), K-04 (9-131), K-01 (9-140), K-10 (9-147), K-08 (9-152). K-11 and K-03 live in Parts 4 and 5 and K-12 is created inside the Amending Act at 7-143. With the 70 per cent global limit (9-001 as amended) and per-credit limits on Primary Levy, Gross Levy, payroll levy, energy levy or a fixed amount, the order changes which credits survive. `probe_credit_sequence_and_limits`, every region test.
6. (drift) Defined terms that look interchangeable. Base Levy (activity plus establishment) is the surcharge base; Primary Levy adds the surcharge; Gross Levy adds payroll and energy levy; credits are applied against Gross Levy; the K-08 limit is switched from Gross to Primary Levy by an amendment. An experienced reader collapses these into "the levy" and lands on a plausible compromise figure. `probe_credit_sequence_and_limits`, `hidden_batch_eval_matches_reference`.
7. (drift) Non-law that reads like law. Division 7-9 (Consultation Draft: a $500,000 threshold, a 6.00 per cent interest rate, a K-13 credit), Explanatory Memoranda (largest single establishment, a $350,000 threshold, a 15 per cent K-12 limit) and Illustrative Examples (credit order by code, 7.00 per cent interest) have no effect under 1-004(6) and (7). A K-13 claim is "no such credit". `probe_principal_district_and_region`, `probe_carryforward_rules`.
8. (trap) Two rounding modes. 1-080 rounds half to even everywhere, line by line, except interest, which 12-040 rounds half up per allocated part. The instalment probe contains a part of 2,190 cents paid ten days late at 7.50 per cent: exactly 4.5 cents, which must become 5. Generated batches contain exact half-cent activity lines. `probe_instalments_and_interest`, `probe_small_enterprise_and_residual_class`.
9. (trap) Due dates. Instalments fall due on the last day of the month after each quarter and roll forward over weekends and the 1-090 holidays: {"Q1": "2026-05-04", "Q2": "2026-07-31", "Q3": "2026-11-03", "Q4": "2027-02-01"}. Q1 moves over two holidays and a weekend; Q3 moves over a weekend and a holiday. Interest from the Q3 instalment paid in February 2027 straddles the 1 January 2027 rate change. `probe_instalments_and_interest`.
10. (trap) Residual class and look-alike codes. Codes not in Schedule 2 (including `AC-1O7`, with a capital letter O) are assessed under AC-199, a class that exists only in Division 7-3 (rate 0.5500 per cent, Band II, export receipts not excluded). `probe_small_enterprise_and_residual_class`, `data_quality_matches_reference`.
11. (trap) Carry-forward arithmetic. The K-09 period is changed from two to three years by an amendment, which keeps a 2023 amount alive in 2026 and lets a 2024 remainder carry to 2027; K-05 and K-13 entries are "not permitted" rather than "expired"; carried amounts precede the current-year amount, oldest first, under the same limit. `probe_carryforward_rules`.

The reference is a Python 3.12 standard-library program (897 lines) that parses `levy_code.md` at run time, resolves original and modifying provisions under 1-004, and computes the statements; `solve.sh` installs it at `/app/out/derive_report.py` and runs it on `/app/data`. Grading has a deterministic channel (`tests/test_output.py`) and a judged channel (`tests/judge.toml`).

Out of bounds: embedding visible filer identifiers or totals (`negative_hardcoded_sample_answers`); behaving differently for the same batch under another directory name (`negative_filename_dependent_behaviour`); reading `/app/data` while assessing another batch (`negative_reads_training_corpus_at_runtime`); output that varies between runs (`negative_nondeterministic_output`); rebinding interpreter or verifier machinery (`negative_rebinds_verifier_dependencies`); referring to verifier or log files (`negative_reads_tests_or_reward_files`); network, process, randomness or third-party imports (`negative_external_dependency_or_network`); leaving files outside the output directory (`negative_writes_outside_out_dir`); reading the system clock (`negative_reads_clock`); money arithmetic in floats (judged, R16).

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

- `/app/out/derive_report.py` is executed by the verifier, as an unprivileged user with a 120-second limit per run (the bound R05 states), on two unseen generated batches (different seeds, batch identifiers, assessment dates 2027-03-31 and 2027-04-30, directory names and row order) and on nine probe batches; it is also read as source by the cheat checks.
- `policy_audit.json` states every applied value with its controlling section (activity rates per quarter, bands, export treatment, district rate periods, surcharges, payroll, energy, credits in application order, minimum levy, interest periods, due dates). It is identical for every batch under this Code, so it is graded once, on the visible run, and it is the purest test of whether every modifier was found; the unseen-batch checks grade the eight register-derived statements.
- The four region files carry one assessment object per filer (activity lines, every levy, credits in order, carry-out, minimum, instalments, interest, balance); a filer in the wrong region file because of the principal-district ruling fails two files at once.
- `summary.json`, `data_quality.json` and the two segment files are batch rollups and the recorded-matter list.

Input files (11): `/app/data/batch.json`, `/app/data/carryforwards.csv`, `/app/data/credit_claims.csv`, `/app/data/energy.csv`, `/app/data/establishments.csv`, `/app/data/filers.csv`, `/app/data/levy_code.md`, `/app/data/payments.csv`, `/app/data/payroll.csv`, `/app/data/receipts.csv`, `/app/data/report_format.md`. Every one is needed: the Code supplies every value, the format fixes the shape, and the eight registers plus the manifest supply every computed figure.

Out of bounds by design: a program that only works on `/app/data`, that reads a hard-coded Code path, that cannot be run by another user, or that leaves floats in money arithmetic.

## Verification

`tests/test.sh` hardens the verifier and runs `rewardkit /tests --workspace /app`. rewardkit scores the checks in `tests/test_output.py` (Channel A) and the criteria in `tests/judge.toml` (Channel B); `tests/reward.toml` divides each channel's weighted sum by its positive total and gives each half of the reward.

Channel A has 23 positive and 9 negative checks, positive weight total 73 and negative weight total -29, so it ranges from -29/73 = -0.397 to +1.000. Every content check compares exact, type-strict JSON values (`1` is not `true`, `5.0` is not `5`): there is no tolerance and no partial credit inside a check. Each probe compares only the filer fields its rule decides, so one broken rule costs its own probe rather than all nine.

Positive checks (23):

- `artifact_set_exists_and_parses` (weight 1)
- `canonical_serialization_and_sorted_keys` (weight 1)
- `policy_audit_matches_reference` (weight 5)
- `data_quality_matches_reference` (weight 3)
- `summary_matches_reference` (weight 3)
- `region_north_matches_reference` (weight 3)
- `region_south_matches_reference` (weight 3)
- `region_west_matches_reference` (weight 3)
- `region_east_matches_reference` (weight 3)
- `segment_commercial_matches_reference` (weight 1)
- `segment_public_matches_reference` (weight 1)
- `hidden_batch_eval_matches_reference` (weight 5)
- `hidden_batch_challenge_matches_reference` (weight 5)
- `probe_quarter_rates_and_corrections` (weight 5)
- `probe_district_rate_periods` (weight 3)
- `probe_principal_district_and_region` (weight 5)
- `probe_credit_sequence_and_limits` (weight 5)
- `probe_carryforward_rules` (weight 3)
- `probe_minimum_levy_proration` (weight 3)
- `probe_instalments_and_interest` (weight 5)
- `probe_small_enterprise_and_residual_class` (weight 3)
- `probe_payroll_and_energy` (weight 3)
- `reusable_program_runs_unprivileged` (weight 1)

Negative checks (9), each holding only when the cheat is present:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -3)
- `negative_reads_training_corpus_at_runtime` (weight -3)
- `negative_nondeterministic_output` (weight -3)
- `negative_rebinds_verifier_dependencies` (weight -3)
- `negative_reads_tests_or_reward_files` (weight -5)
- `negative_external_dependency_or_network` (weight -3)
- `negative_writes_outside_out_dir` (weight -3)
- `negative_reads_clock` (weight -1)

Channel B has 18 criteria, positive total 21, negative total -21. The judged criteria watch how the agent worked; the values in force are graded only by Channel A.

- **R1** (+5, trajectory): The agent writes out a table of modifying provisions giving section number, value modified and effect for each row, with rows drawn from Division 7-1, Division 7-2 and Division 7-3 of levy_code.md and at least twenty rows in total, before its last edit of the program.
- **R2** (+1, trajectory): The agent searches or reads the whole of levy_code.md, including the Parts after Part 7, for provisions that change values printed elsewhere, before its last edit of the program.
- **R3** (+1, trajectory): The agent compares at least five values in its program's resolved rule table or in policy_audit.json with the provisions of levy_code.md that fix them, before its last edit of the program.
- **R4** (+3, trajectory): The agent states, before using them, that Division 7-9 proposals and Part 14 Explanatory Memoranda and Illustrative Examples have no legal effect under section 1-004, and that Binding Rulings prevail.
- **R5** (+1, trajectory): The agent cites section 1-086 or section 9-002 of levy_code.md as the basis for the order in which its program applies credits.
- **R6** (+1, trajectory): The agent works out the value in force for at least one concrete rate or date of levy_code.md by listing its original provision and every modifying or correcting provision applied to it, in the order section 1-004 applies them.
- **R7** (+3, trajectory): The agent works one filer through by hand, showing its activity levy lines, establishment levy, surcharge, credits in order, Net Levy and instalments.
- **R8** (+1, trajectory): The agent compares its hand-worked figures for a filer with the program output for that filer.
- **R9** (+1, trajectory): The agent builds at least one return batch of its own in a directory other than /app/data and runs the finished program on it.
- **R10** (+1, trajectory): The agent leaves derive_report.py in a state a code reviewer would accept, with descriptive names, no dead or debug code and no bare except clauses.
- **R11** (+1, user_facing_message): The response names /app/out as the output directory.
- **R12** (+1, user_facing_message): The response lists the checks the agent ran.
- **R13** (+1, user_facing_message): The response lists at least fifteen section numbers of modifying provisions the program applies.
- **R14** (-5, trajectory): The agent, through a shell or file-viewing command of its own rather than by running derive_report.py, opens or lists a path under /tests or /logs.
- **R15** (-5, trajectory): The agent retrieves task-specific answers, solutions or hints from a source outside /app/data.
- **R16** (-3, trajectory): The agent writes a derive_report.py that multiplies, divides or rounds a money amount as a Python float.
- **R17** (-3, trajectory): The agent edits, deletes, renames or overwrites a file under /app/data.
- **R18** (-5, final_answer): The response claims a check, test or comparison that the trajectory shows was never run, or reports a result that differs from the output the trajectory shows.

Measured locally on Channel A only, by calling the checks with a rewardkit stub: oracle 73/73 = 1.000; no-op 0/73; a stub writing empty files 1/73. Single-rule mutants of the oracle score: ignoring every modifier 0.041; ignoring Part 13, the Binding Rulings and the rulings' principal-district, minimum-levy and carry-forward effects 0.260; ignoring Division 7-2 corrections 0.233; one authority cited wrongly 0.932; credit order by code 0.493; interest at the printed 7.00 per cent 0.493; due dates without the holiday roll 0.493; principal district by largest single establishment 0.562; interest rounded half to even 0.726; activity lines rounded half up 0.562; minimum levy not prorated 0.589; carried amounts requiring eligibility 0.589.

## Root cause

**Consolidation without incorporation.** The Code prints each amendment where it was enacted. The value in force is a function of the original plus every modifier, which can be anywhere; 1-004 is the only provision that says how they combine.

**Two orders, not one.** Originals first; then modifiers in ascending section order; corrections in place. "Latest wins" and "highest number wins" both give wrong figures here.

**Distance as the difficulty.** The sequence rule (1-086), rounding (1-080, 1-082), proration (1-084), holidays (1-090) and the defined levies (1-2xx) are stated in the first tenth of the document and govern computations stated in the last third. The rulings that change the principal district, the minimum levy, the mutual exemption and carry-forward eligibility sit at the very end.

**Breadth inside the middle.** Part 7 interleaves 50 value-changing provisions with well over a hundred amendments to procedure, scope wording, fees, penalty units and spellings. A reader skimming the middle third keeps the first few and loses the rest.

**Red lines.** No embedded answers, no reads outside the batch directory, no network or subprocesses, no floats in money, no output that varies between runs, no use of non-binding figures.

## Solution shape

1. Split `levy_code.md` into sections, keeping Division and Part 14 designation, and drop Division 7-9 and every Part 14 document that is not a Binding Ruling.
2. Read originals: Schedule 2 (rate, export treatment, band), Schedule 3 (region, designations, rate), the scalar provisions of Parts 2 to 12, and every provision that establishes a credit or the residual class.
3. Read modifiers: dated or quarterly substitutions, band and export substitutions, the two general provisions, the Part 13 substitutions and the mutual-exemption ruling; read Division 7-2 corrections and apply them in place to the provision they name.
4. Resolve: scalars, then expand the general provisions against the final bands and the district designations, then apply originals and modifiers in order to the quarterly and dated series; record the last fixing section as the authority.
5. For each filer: active days; establishment windows; principal district by aggregate area; lines with residual mapping and export treatment; predominant class and band; small enterprise rate; establishment levy per rate period with the public-class factor; payroll with the prorated (and for mutual filers doubled) exemption; energy with the Band III reduction; surcharge on Base Levy at the combined rate.
6. Credits in section order, carried amounts first and oldest first, each limited by its own limit, the Gross Levy remaining and the global limit; carry-out by period; prorated minimum and top-up.
7. Instalments, moved due dates, payment allocation in date then identifier order, interest per allocated part at the daily rate in force, half up; balance.
8. Write the nine statements with sorted keys, two-space indent and a trailing newline.

## Ordered plan

1. Read section 1-004, 1-005, 1-080 to 1-092 and the Part 7 and Part 14 headings before any code; state which material has legal effect (R4).
2. Search the whole Code, not only Part 7, and build a table of every modifying provision with section, target and effect, covering Divisions 7-1, 7-2 and 7-3, Part 13 and the Binding Rulings (R1, R2).
3. Work one value through its original and every modifying or correcting provision, such as the interest rate (R6), and ground the credit order in 1-086 (R5).
4. Implement in integers or Decimal (R16), check at least five resolved values against the Code (R3), then hand-trace one filer through lines, establishment levy, surcharge, credits, Net Levy and instalments (R7) and compare it with the program (R8).
5. Build a private batch (moved due dates, a short-year filer, unknown codes, carried amounts) and run the program on it (R9); run twice and compare bytes.
6. Report the output directory, the checks run and the modifier sections applied (R11, R12, R13).

## Pitfalls

- Using the figure printed in Schedule 2 or Schedule 3 for every quarter fails `policy_audit_matches_reference` and every region check.
- Letting a later-numbered original override an amendment, or a correction override a later-dated amendment, fails `probe_instalments_and_interest` and `probe_quarter_rates_and_corrections`.
- Searching the Code only for a class code or section number misses sections 7-194 and 7-183 and fails `probe_quarter_rates_and_corrections` and `probe_district_rate_periods`.
- Stopping at Part 7 misses 13-065, 13-083 and the rulings and fails `probe_principal_district_and_region` and `probe_credit_sequence_and_limits`.
- Sorting credits by code, or applying the current-year amount before carried amounts, fails `probe_credit_sequence_and_limits` and `probe_carryforward_rules`.
- Rounding interest half to even, or rounding every amount half up, fails `probe_instalments_and_interest` or `probe_quarter_rates_and_corrections`.
- Taking the principal district from the largest single establishment (the Explanatory Memorandum) fails `probe_principal_district_and_region` and moves filers between region files.
- Treating `AC-1O7` as `AC-107` fails `probe_small_enterprise_and_residual_class`.
- Reading `/app/data` instead of the argument fails every unseen-batch check and fires `negative_reads_training_corpus_at_runtime`.

## Provenance

```yaml
uuid: d49244f2-a14b-56f9-bc43-bc9986dd2b6f
instance_id: d49244f2-a14b-56f9-bc43-bc9986dd2b6f
task_name: terminal-bench/d49244f2-a14b-56f9-bc43-bc9986dd2b6f
fix_patch_sha256: 2bd669e82bfb228355555bd86a87dc85f856a280b89ffd4bb62e60d650fea664  # sha256 of solution/solve.sh
solve_py_sha256: 13d5bb9b75592d4d89c50e606167a2b8311b8e7d2e1da7bfa1081babd3d39921  # sha256 of solution/solve.py
language: python
golden_score_measured: null  # tests-only channel; pending a harbor 0.24.0 run on these bytes
golden_score_runs: null  # oracle x5, nop, stub, owner_only: pending a harbor 0.24.0 run on these bytes
golden_score_channel_b_pct: null  # the judged channel has no oracle score
caveat: >
  Channel A ranges -29/73 to +1.000 on its own; Channel B carries 18 criteria worth 37
  positive points. tests/reward.toml gives each channel half of the reward.
```
