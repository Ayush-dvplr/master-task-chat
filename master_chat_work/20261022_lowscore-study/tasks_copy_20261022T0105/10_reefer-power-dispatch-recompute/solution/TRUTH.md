# TRUTH.md - reefer-power-dispatch-recompute

## Defect

Nothing in this bundle is broken source. What is withheld is the derivation:
one operating day of the Ashgrove Point reefer yard was published, the
publication was withdrawn, and the agent holds only the 59 working
papers the day was settled from. The agent has to recompute the day through
the fourteen stages the papers specify and hand back 31 documents plus
the program that produces them. The difficulty is the breadth and the
interaction of the rules those papers state, never a rule they omit.

1. (focal) The provisional allocation of stage P05 is settled against the
   nominal capacity of each feeder and is locally optimal there. Stage P06
   then withholds the standing reserve and unpicks part of it, and stage P07
   takes the confirmed crane duty off the same capacity. A solver that settles
   the allocation once against the final capacity produces a different set of
   spill decisions and forfeits the allocation block and every block after it.

2. (focal) The load reconciliation of stage P09 is a damped iterate whose
   target moves with the standing share, truncated by a pass budget that lives
   only in the portable document. A solver that runs it to convergence trips
   `negative_reconciliation_run_to_convergence`.

3. (focal) The reconciliation rounds the share to a whole watt hour at the
   close of every pass and the next pass opens from that rounded figure. A
   solver that carries exact shares through and rounds once at the end trips
   `negative_reconciliation_rounds_once`.

4. (focal) The control values are split across a spreadsheet package, a
   portable document and a word processing package. The spreadsheet carries
   six sheets and only the one whose key cell matches this day reference
   governs. A solver that reads a sheet by position, by name or by sorted rank
   picks the wrong damping fraction and fails the reconciliation block
   and every block after it.

5. (drift) A confirmed crane duty reduces the capacity available to reefers.
   Adding it to the load instead gives the same comparison and a different
   published adjusted capacity, so the instinct that the two are equivalent
   trips `negative_crane_demand_added_as_load`.

6. (drift) A load equal to the capacity is lawful and a state of charge equal
   to the reserve is lawful. Treating either equality as a violation moves the
   spill ledger and the battery schedule.

7. (trap) A disconnection minute landing exactly on an interval boundary
   closes the interval before it. The corpus carries reefers on both boundary
   forms, and the wrong convention trips
   `negative_disconnect_boundary_opens_interval`.

8. (trap) An ambient multiplier the table carries no row for falls back to the
   class default, and an energy return carrying the absent marker declared
   nothing. Reading either as zero trips
   `negative_absent_ambient_read_as_zero` and
   `negative_absent_declaration_read_as_zero`.

9. (trap) The battery may be drawn only down to its reserve. The shipped day
   reaches the reserve on 17 intervals, so drawing through it trips
   `negative_battery_discharges_at_reserve`.

Seven of the eight outcomes `corpus_sentinel_note.txt` names as unreached by
the shipped day are reached by a graded day, and each is reached in a value
that day publishes, so any other reading of its rule changes bytes a scoring
block compares. The strained day closes an interval below the battery reserve,
exhausts the day pool of a feeder while a member still needs energy, and
carries a reefer row whose record state neither list of
`revision_precedence.toml` names at the highest sequence of its key. The wide
day charges an interval into no room, settles a correction sweep, and lands a
substation peak exactly on the floor of its demand charge band. The sparse day
ties two intervals on the yard peak. Breaking each rule in isolation leaves the test channel at
0.839, 0.839, 0.758, 0.839, 0.919, 0.919 and 0.919 of its maximum respectively.

`tests/test_output.py` records the mapping in `SENTINEL_COVERAGE`, and
`assert_branch_coverage()`, an author-side check that grading never calls,
fails if a profile is retuned so that
one of them stops being reached. The probes read the recomputed publication
rather than the papers, because a day can carry a condition in its input while
every reading of the rule publishes the same bytes, and such a rule is graded
by nothing.

SHARE_STEP_DOWNWARD is the eighth and no fixture can construct it. The
downward half of RULE P09.i is vacuous under the algorithm the stage
specifications define: a share opens at zero and is held in the range zero to
its limit at the close of every pass, RULE P09.e sets the target to the
standing share plus a non negative portion of the unallocated pool, RULE
P09.f only cuts a target down to the limit the share never exceeds, and RULE
P09.g only adds. The target therefore never stands below the standing share,
the damped move is never downward, and the step is never negative. It is
listed in `SENTINEL_INERT` and that same author-side check fails if it ever becomes
reachable. The over_capacity reading of RULE P06.f is out of reach in the load
ledger of its own stage, where the removals of P06.d leave nothing standing
above the reserved capacity; RULE P14.h takes the same three readings against
the adjusted capacity plus the battery support in
`final_schedule_by_feeder.psv`, where all three are published.

RULE P01.b settles what an unrecognised record state means, so the reefer row
the strained day plants is a trap with a stated answer rather than a guess: a
row governs only while its record state is one of the words the applicable
list carries, and a word neither list carries is set aside like any other.

The reference implementation is Python, standard library only, exact rational
arithmetic throughout. Grading runs in two channels: `tests/test_output.py`
holds every deterministic fact and `tests/judge.toml` holds every judged one.
No property is graded in both, and no single wrong reading carries a
penalty in both channels: the eleven named wrong readings are charged by
their negative tests and nowhere else, and the four negative criteria sit
on wrong paths no detector reaches.

Out of bounds: baking the shipped answers into the delivered program is caught
by `negative_hardcoded_sample_answers`; reading this operating day
out of the program source rather than out of its input directory is caught by
`negative_reads_training_corpus_at_runtime`; a program that
ignores its input is caught by
`negative_program_ignores_its_input`; non deterministic output is
caught by `negative_nondeterministic_output`; behaviour that
follows the directory name is caught by
`negative_filename_dependent_behaviour`; writing anything beyond
the declared documents, or touching the input directory, is caught by
`negative_program_dirties_its_directories`; and a manifest written
from something other than the delivery is caught by
`negative_manifest_digest_mismatch`.

## Load-bearing work

The graded artifacts are:

- `/app/out/normalised_reefers.jsonl`
- `/app/out/availability_lattice.csv`
- `/app/out/energy_floor_ledger.csv`
- `/app/out/dispatch_priority_queue.csv`
- `/app/out/provisional_allocation.psv`
- `/app/out/feeder_violation_ledger.csv`
- `/app/out/crane_adjusted_capacity.csv`
- `/app/out/battery_schedule.csv`
- `/app/out/reconciliation_iterations.csv`
- `/app/out/tariff_charge_ledger.csv`
- `/app/out/deadline_correction.csv`
- `/app/out/cycle_break_report.json`
- `/app/out/objective_vector.json`
- `/app/out/final_schedule.csv`
- `/app/out/publication_manifest.json`
- `/app/out/interval_demand.csv`
- `/app/out/feeder_load_ledger.csv`
- `/app/out/spill_decisions.tsv`
- `/app/out/soc_ledger.psv`
- `/app/out/constraint_certificate.json`
- `/app/out/peak_demand_certificate.json`
- `/app/out/unmet_requirement_report.tsv`
- `/app/out/reefer_service_certificate.csv`
- `/app/out/audit_trace.jsonl`
- `/app/out/dispatch_control_totals.conf`
- `/app/out/final_schedule_by_feeder.psv`
- `/app/out/final_schedule_by_vessel.xml`
- `/app/out/substation_report_sb_alder.json`
- `/app/out/substation_report_sb_bourne.json`
- `/app/out/substation_report_sb_calloway.json`
- `/app/out/daily_dispatch_summary.md`
- `/app/out/reeferdispatch.py`

The fifteen documents of the stage spine carry one published observable per
stage plus the manifest. `normalised_reefers.jsonl` carries the governing row
of every reefer with its converted nameplate and its declared energy.
`availability_lattice.csv` carries the first interval, the last interval and
the slot count of every reefer. `energy_floor_ledger.csv` carries the
mandatory floor, the requested energy and the discretionary energy.
`dispatch_priority_queue.csv` carries the rank of every queued reefer and the
rung code of every refused one. `provisional_allocation.psv` carries one row
per reefer and interval of its lattice. `feeder_violation_ledger.csv` carries
one row per feeder and interval a removal happened in.
`crane_adjusted_capacity.csv` carries the reserved capacity, the crane draw
and the adjusted capacity of every feeder and interval.
`battery_schedule.csv` carries the action, the deficit, the discharge, the
charge and the limit reason of every interval.
`reconciliation_iterations.csv` carries one row per pass, feeder and member.
`tariff_charge_ledger.csv` carries the price, the load, the stored energy and
the charge of every interval. `deadline_correction.csv` carries every
displacement the correction attempted. `cycle_break_report.json` carries the
sweeps, the cycles and the frozen reefers. `objective_vector.json` carries the
seven components in comparison order. `final_schedule.csv` carries the base
draw, the allowance and the energy of every reefer and interval.
`publication_manifest.json` carries the core digest over the six core
documents and the publication digest over the rest.

The load family carries the interval demand, the feeder load ledger, the spill
decisions, the state of charge ledger and the constraint certificate. The
tariff family carries the peak demand certificate, the unmet requirement
report, the reefer service certificate, the audit trace and the control
totals. The publication family carries the schedule by feeder, the schedule by
vessel, the three substation reports and the daily summary.

`reeferdispatch.py` is the delivered program. It accepts a `--data` option and
an `--out` option in either order, creates the output directory when absent, writes
the 31 documents there, exits zero, writes nothing else and leaves its
input directory as it found it.

Out of bounds by design: the delivered program holds no identifier, control
value, threshold, boundary or rung code of this operating day. Every one of
them is read from the directory the program is pointed at, which is what lets
it reproduce three operating days it has never seen. The substations are part
of that rule and are read from two papers rather than assumed: the order
`peak_demand_certificate.json` follows comes from `substation_topology.xml`,
and the reports the publication carries, together with the order the manifest
lists them in, come from `reporting_feeder_roster.conf` under RULE P14.e. The
roster print order differs from the topology order on the wide and the sparse
day, so a program that takes either from a literal forfeits those days.

## Verification

`tests/test.sh` clears any stale reward file, locks the verifier log directory to root, closes `/tests` to every other reader and hands over to `rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. It writes no reward itself. rewardkit scores two channels: `test_output` from the deterministic checks in `tests/test_output.py` and `judge` from the criteria in `tests/judge.toml`. `tests/reward.toml` multiplies each channel sum by 0.5 over its positive total and adds them, so each channel counts for half.

The test channel registers 35 checks. The 16 positive checks sum to 62 and the 19 negative checks sum to minus 59, so the channel share runs from minus 0.476 to 0.5. Every check runs under one lock because rewardkit runs criteria on worker threads and the variant detectors rebind module globals while they recompute. A check returns True when its assertion held and False on any exception.

The positive weight is spent in stage ordered blocks that partition the publication. Every document is graded in exactly one block and no block is gated on another, so a stage read the wrong way costs the blocks that stage feeds and every earlier block stays banked.

Positive checks:

- `all_artifacts_exist` (weight +1)
- `core_documents_parse` (weight +1)
- `shipped_p01_p02_exact` (weight +3)
- `shipped_p03_p04_exact` (weight +3)
- `shipped_p05_p06_exact` (weight +3)
- `shipped_p07_p09_exact` (weight +3)
- `shipped_p10_p14_exact` (weight +3)
- `program_strained_early_exact` (weight +5)
- `program_strained_middle_exact` (weight +5)
- `program_strained_late_exact` (weight +5)
- `program_wide_early_exact` (weight +5)
- `program_wide_middle_exact` (weight +5)
- `program_wide_late_exact` (weight +5)
- `program_sparse_early_exact` (weight +5)
- `program_sparse_middle_exact` (weight +5)
- `program_sparse_late_exact` (weight +5)

Negative checks:

- `negative_alphabetical_ladder_order` (weight -3)
- `negative_free_capacity_before_reserve` (weight -3)
- `negative_crane_demand_added_as_load` (weight -3)
- `negative_reconciliation_run_to_convergence` (weight -3)
- `negative_reconciliation_rounds_once` (weight -3)
- `negative_reads_training_corpus_at_runtime` (weight -3)
- `negative_spill_to_cheapest_interval` (weight -3)
- `negative_absent_ambient_read_as_zero` (weight -3)
- `negative_disconnect_boundary_opens_interval` (weight -3)
- `negative_redistribution_across_the_feeder` (weight -3)
- `negative_battery_discharges_at_reserve` (weight -3)
- `negative_absent_declaration_read_as_zero` (weight -3)
- `negative_hardcoded_sample_answers` (weight -5)
- `negative_program_ignores_its_input` (weight -3)
- `negative_nondeterministic_output` (weight -3)
- `negative_filename_dependent_behaviour` (weight -3)
- `negative_program_dirties_its_directories` (weight -3)
- `negative_rebinds_verifier_dependencies` (weight -3)
- `negative_manifest_digest_mismatch` (weight -3)

The judged channel is `tests/judge.toml`, 35 criteria judged from the trajectory, the final message and the delivered program source. Its positive criteria sum to 79 and its negative ones to minus 14. It grades process, tool use, instruction following, factuality and boundaries. It never grades the bytes of a produced document, which the test channel owns, and no wrong reading a test detector already charges for is charged again here.

- R1 (instruction following, trajectory, +1) The agent opens /app/data/readme_first.txt and /app/data/terminal_contract_overview.md before it opens any register.
- R2 (instruction following, trajectory, +3) The agent works the fourteen stages in the order /app/data/terminal_contract_overview.md lists them.
- R3 (instruction following, state_change, +5) The agent restricts /app/out/reeferdispatch.py to the Python standard library.
- R4 (instruction following, trajectory, +3) The agent reads /app/data/corpus_sentinel_note.txt before it concludes that a documented branch is absent from this operating day.
- R5 (instruction following, user_facing_message, +3) The response gives the live workbook sheet key together with the sheet name that key was taken from.
- R6 (instruction following, user_facing_message, +3) The response gives the number of passes the reconciliation ran to together with one reefer whose share was still moving at the last of them.
- R7 (instruction following, user_facing_message, +3) The response gives the count of reefers set aside under each of the six rung codes printed in /app/data/dispatch_admission_ladder.txt.
- R8 (instruction following, user_facing_message, +1) The response names the reefers whose energy return declared nothing.
- R9 (instruction following, user_facing_message, +1) The response gives the seven components of the objective vector in the order they are compared.
- R10 (agent behavior, trajectory, +1) The agent names a feeder that /app/data/feeder_capacity_register.csv carries a capacity row for and that /app/data/substation_topology.xml omits, and states that the feeder stands out of force.
- R11 (instruction following, user_facing_message, +3) The response names one feeder and one interval where the crane duty took the adjusted capacity of that feeder to zero.
- R12 (instruction following, state_change, +1) The agent leaves /app/out/reeferdispatch.py carrying the fourteen stages as fourteen separately named steps in the stage order /app/data/terminal_contract_overview.md prints, as /app/data/reeferdispatch_program_contract.md requires.
- R13 (instruction following, trajectory, +3) The agent leaves /app/data byte for byte as it found it.
- R14 (tool use, trajectory, +3) The agent opens /app/data/substation_capacity_workbook.xlsx as a zip archive, reads its worksheet and shared string parts, and shows the cell it took the reconciliation damping numerator and denominator from.
- R15 (tool use, trajectory, +3) The agent extracts the text of /app/data/dispatch_operations_memo.pdf and shows the reconciliation pass budget, the minimum step in watt hours and the dependency protection depth it read there.
- R16 (tool use, trajectory, +3) The agent opens /app/data/priority_ordering_directive.docx and shows the four ordering keys in their key positions together with the class rank it read for each temperature class.
- R17 (agent behavior, trajectory, +3) The agent gives the reserved capacity of one named feeder in one named interval as that feeder nominal capacity for the interval less its standing reserve watts, quoting all three figures.
- R18 (agent behavior, trajectory, +3) The agent gives, for one named reefer, its need and its target at the opening of the last reconciliation pass together with the share that pass closed on, and states that the day pool of its feeder still stood unallocated when the budget ran out.
- R19 (agent behavior, trajectory, +3) The agent shows one reconciliation share rounded to a whole watt hour at the close of a pass and shows the pass after it opening from that rounded figure.
- R20 (agent behavior, trajectory, +3) The agent converts a nameplate quoted in megajoules per hour through the numerator of 2500 and the denominator of 9 that /app/data/unit_register_dictionary.toml carries, and gives the quoted value and the whole watt figure it stored for one named reefer.
- R21 (agent behavior, trajectory, +3) The agent names the substation and service group pairing it redistributed a freed share inside for one feeder, and gives the reefer whose share ceiling freed that mass.
- R22 (agent behavior, trajectory, +3) The agent names the reefer that the cluster rung of /app/data/dispatch_admission_ladder.txt caught on the plug four reefers of this operating day share in /app/data/reefer_service_register.csv.
- R23 (agent behavior, trajectory, +3) The agent gives one reefer whose disconnect minute lands on an interval boundary together with the connect minute, the disconnect minute and the last interval of the lattice it gave that reefer.
- R24 (agent behavior, trajectory, +3) The agent gives one interval where the closing state of charge equalled the reserve watt hours of /app/data/battery_operating_policy.toml, with the discharge it published for that interval and the limit reason it gave.
- R25 (agent behavior, trajectory, +3) The agent identifies the vessel in /app/data/vessel_call_register.csv whose highest revision sequence is a withdrawn one, and states which lower revision it took as the applicable call together with the cutoff interval that revision carries.
- R26 (agent behavior, trajectory, +3) The agent identifies a reefer in /app/data/energy_declaration_returns.psv whose superseded return carries a higher declaration sequence than its filed one, and states which of the two rows it took the declared energy from.
- R27 (agent behavior, trajectory, +3) The agent gives one removed placement with the interval it was removed from, the interval it landed in and the reserved capacity of that landing interval.
- R28 (agent behavior, state_change, +1) The agent leaves /app/out/reeferdispatch.py free of dead code, carrying no binding it never reads and no block it never reaches.
- R29 (factuality and hallucination, trajectory, +3) The agent reconciles the sweep budget it worked the deadline correction under against the dependency protection depth of /app/data/dispatch_operations_memo.pdf, giving both figures and the addition between them.
- R30 (factuality and hallucination, trajectory, +1) The agent states that /app/data/reefer_thermal_supplement.csv, /app/data/legacy_tariff_extract.csv and /app/data/night_office_audit.db govern nothing, citing /app/data/data_lineage.md as the paper that says so.
- R31 (agent behavior, trajectory, +1) The agent runs its delivered program a second time over one input directory, compares the two outputs byte for byte, and reports the result of that comparison.
- R32 (factuality and hallucination, trajectory, -3) The agent quotes a damping fraction, a maintenance coefficient or a vessel share ceiling taken from a sheet of /app/data/substation_capacity_workbook.xlsx whose key cell carries a day reference other than the one /app/data/substation_topology.xml gives.
- R33 (factuality and hallucination, user_facing_message, -5) The response states a figure for a published quantity that differs from the figure the document the agent delivered carries for that quantity.
- R34 (agent behavior, trajectory, -3) The agent settles the price of an interval from /app/data/legacy_tariff_extract.csv and carries that price into the tariff charge ledger.
- R35 (agent behavior, trajectory, -3) The agent takes a governing row for this operating day from a register record whose day identifier names one of the earlier operating days the registers carry.

## Root cause

**Stage order is load bearing.** The allocation is settled three times over:
once against the nominal capacity, once against the capacity the standing
reserve leaves, and once against the capacity the crane duty leaves and the
battery lifts. Each settlement is correct where it stands and wrong as a final
answer. The published ledgers record all three, so a solver that collapses
them into one pass disagrees with the reference on the spill decisions, on the
violation ledger and on everything downstream.

**Withholding comes before counting.** The standing reserve of a feeder is
withheld before any free capacity is counted. A solver that counts the free
capacity first and subtracts afterwards admits placements the reserve refuses.

**A capacity change is not a load.** A crane duty lowers the ceiling rather
than raising the floor. The two readings agree on the comparison and disagree
on the published adjusted capacity, and the clamp at zero is where they also
disagree on the decision.

**A budget is not a convergence guard.** The reconciliation pass budget is
spent whether or not the shares have settled, and the target of a pass moves
with the standing share, so the iterate is still moving on the shipped day
when the budget runs out.

**Rounding is placed, not deferred.** Each stage stores the whole number its
own rounding rule yields and every later stage reads the stored number. One
nameplate unit converts through 2500 over 9 and every ambient multiplier is a
thousandth fraction, so nothing lands on a whole number by accident.

**Absence is not zero.** An ambient pairing the table omits falls back to the
class default. An energy return carrying the absent marker declared nothing
and the reefer defaults to its mandatory floor. A vessel whose every revision
is withdrawn has no applicable call and takes the sentinel slack.

**Red lines.** No graded quantity depends on a value outside `instruction.md`
and `environment/data/`. The verifier never reads the agent corpus. The
delivered program runs as an unprivileged user that cannot read the tests.
None of the eleven named wrong readings fires on honest work: each asserts
that the delivered bytes match that reading, so a correct delivery fails the
assertion and escapes the penalty. The source text detector is narrower than
that claim and is scoped deliberately: it matches the day identifier and the
day reference only, both unique to this day, and it reads the program with
comments stripped, so neither a sample row in a comment nor a feeder
identifier that every operating day shares can trip it.

## Solution shape

1. Read the operating day identifier and the day reference from the topology
   paper, and filter every register to that day.
2. Drop the rows whose record state is set aside, then take the highest
   sequence among what survives, per the sequence field the precedence paper
   names for that register.
3. Convert nameplates and declared energies through the unit register, storing
   the whole number each conversion rounds to.
4. Expand each connection window onto the 96 interval grid under the half open
   convention and strike out the intervals a booked maintenance window covers.
5. Derive the interval floor of every reefer from its stored nameplate, the
   ambient multiplier of the interval and the maintenance coefficient of the
   governing workbook sheet, rounding once per interval.
6. Walk the printed admission ladder in its printed order, settle the cluster
   rung among the survivors, and order the rest on the four keys of the
   directive.
7. Allocate against the nominal capacity in rank order, admitting a placement
   when the running load plus its draw stands at or below the capacity.
8. Withhold the standing reserve, remove the highest ranked placement while
   the load stands above the reserved capacity, and spill each removal into
   the next eligible interval.
9. Take the confirmed crane duty off the reserved capacity and clamp the
   result at zero.
10. Work the battery forward one interval at a time, discharging against the
    deficit down to the reserve and charging in the eligible bands.
11. Settle the discretionary allowance over the pass budget with the damping
    fraction of the live sheet, the share ceiling of each vessel and the
    redistribution inside the substation and service group cell, rounding at
    the close of every pass.
12. Place each allowance into the intervals that still carry headroom and
    charge the day at its interval prices.
13. Correct the reefers left short at their vessel cutoff, freeze the reefers
    whose displacements cycle, and reconcile the seven component objective.
14. Write the publication and the manifest last.

## Ordered plan

1. Open the readme and the contract overview before any register. Earns R1.
2. Read the data lineage and set the three papers that govern nothing aside.
   Earns R30.
3. Open the spreadsheet package as a zip and take the damping fraction from
   the sheet whose key cell matches the day reference. Earns R14 and avoids
   R32.
4. Extract the portable document text and take the pass budget, the minimum
   step and the protection depth. Earns R15.
5. Open the word processing package and take the four ordering keys and the
   class ranks. Earns R16.
6. Work the stages in the order the overview prints. Earns R2.
7. Show the reserved capacity arithmetic on one feeder and interval. Earns
   R17.
8. Show the crane clamp at zero. Earns R11.
9. Show the last reconciliation pass still moving. Earns R6 and R18.
10. Show one pass opening from the rounded share the pass before it left.
    Earns R19.
11. Report the rung counts, the reefers that declared nothing and the seven
    objective components, each figure agreeing with the document delivered
    for it. Earns R5, R7, R8 and R9, and avoids R33.
12. Read the sentinel note before concluding a branch is absent, and
    implement the outcomes it names from their specifications. Earns R4,
    and the seven a graded day reaches are checked by the tests.
13. Leave the delivered program free of dead code, with no binding it
    never reads and no block it never reaches. Earns R28.
14. Take every governing row from this operating day and every interval price
    from the tariff schedule of the day. Avoids R34 and R35.

## Pitfalls

- Settling the allocation once against the final capacity. Fails
  `shipped_p05_p06_exact` and every block the allocation feeds.
- Counting free capacity before withholding the standing reserve. Trips
  `negative_free_capacity_before_reserve`.
- Adding the crane duty to the load. Trips
  `negative_crane_demand_added_as_load`.
- Running the reconciliation to convergence. Trips
  `negative_reconciliation_run_to_convergence`.
- Rounding the share once at the end. Trips
  `negative_reconciliation_rounds_once`.
- Spilling into the cheapest interval. Trips
  `negative_spill_to_cheapest_interval`.
- Reading the ladder in alphabetical rung order. Trips
  `negative_alphabetical_ladder_order`.
- Reading an absent ambient pairing as zero. Trips
  `negative_absent_ambient_read_as_zero`.
- Reading the absent marker as a declared zero. Trips
  `negative_absent_declaration_read_as_zero`.
- Opening the interval a disconnection lands on. Trips
  `negative_disconnect_boundary_opens_interval`.
- Redistributing a freed share across the whole feeder. Trips
  `negative_redistribution_across_the_feeder`.
- Drawing the battery through its reserve. Trips
  `negative_battery_discharges_at_reserve`.

## Provenance

- task: terminal-bench/reefer-power-dispatch-recompute
- operating day: AP-2044-D111, day reference DSP-067712
- shipped corpus: 59 working papers, regenerated from SAMPLE_SEED 4193067712
- solution/solve.py sha256: ca66af561e4b7afed954dc7c92ae1ab2b50eb35da52daafaf9fa84631ea4581f
- tests/test_output.py sha256: a4a4b6758540653d9a894f011e24b492bdbb3c31435430cab7f951774cfafc5b
- grading: 35 weighted checks, 16 positive summing 62, 19 negative
  summing minus 59; 35 judged criteria, 4 of them negative
