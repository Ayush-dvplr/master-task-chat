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
