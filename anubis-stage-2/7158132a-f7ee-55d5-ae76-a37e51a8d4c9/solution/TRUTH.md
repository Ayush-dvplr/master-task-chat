# TRUTH.md - groundlink-contact-settlement

## Defect

Nothing here is broken in the sense of a crash. What is missing is the
settlement itself. The agent is handed 60 working papers from a
satellite operator month end and has to derive the authoritative contact
settlement from them, then leave behind a program that derives it again on a
month it has never seen. The papers are individually plausible and mutually
inconsistent, and their semantics only appear once they are joined in the one
order the shipped `ordering_dependencies.yaml` publishes.

1. (focal) The damped ration at stage nine. An over subscribed aperture period
   budget is divided across the passes that want it by a fixed number of offer
   rounds, quantised to integer KiB at the end of every round, with a minimum
   movement of one unit. A solver that runs the procedure to convergence, or
   that lets the damped step floor to zero, produces a different allocation for
   every row of every over subscribed aperture period. Defeats
   `recompute_eval_allocation_exact` and its two siblings, and fires
   `negative_naive_ration_run_to_convergence` or
   `negative_naive_ration_without_the_minimum_step`.

2. (focal) The pervasive precision rule. Capacity is floored on each rate
   schedule piece separately and the per contact cap is applied to the canonical
   row before any aggregation. The aggregate first expression is mathematically
   equivalent over the rationals and a different integer here. Defeats
   `visible_allocation_core_exact` and fires
   `negative_naive_blended_rate_then_one_floor`.

3. (focal) The commit protection inversion. Clause two of the directive puts
   protection above the priority ladder, so an uncommitted emergency override
   pass loses its aperture to a committed ordinary pass. Defeats every
   allocation group test and fires
   `negative_naive_protection_as_a_tie_break`.

4. (focal) The cross period carry state. Carry forward is capped, consumed
   before new entitlement, forfeited on an expired contract, and its unconsumed
   remainder is the opening figure of the next period and appears in no shipped
   file. Defeats `recompute_challenge_settlement_exact`.

5. (drift) Utilisation from the schedule. Computing station utilisation from
   `pass_plan_of_record.csv` is the natural reading, produces a plausible
   number, and disagrees with every ledger below stage seven. The specification
   says the numerator is the passes that survived contention. Fires
   `negative_naive_utilisation_from_admitted_passes`.

6. (drift) Reported downlink volumes. `downlink_reports.csv` looks like the
   delivered figure and is a reported one. It feeds the discrepancy report and
   nothing else. Judged criterion R29 fires on a trajectory that treats it as
   authoritative.

7. (trap) The cancellation that lands exactly on the commit boundary. Strictly
   before rejects the pass; at or after leaves it admitted and marks it a late
   cancellation, which then decides whether its deferred volume swells the
   outage exempt pool. Fires
   `negative_naive_cancellation_on_the_commit_boundary`.

8. (trap) The last amendment row. `contract_terms_amendments.tsv` ends each
   contract period with a withdrawn revision whose obligation is larger than the
   executed one on 37 of the 72 contract periods and smaller on the other 35, so
   file order and revision order disagree and the direction of the disagreement
   carries no signal. Fires
   `negative_naive_last_amendment_row`.

9. (trap) The closed opening buckets. `prior_period_settlement.json` carries
   216 opening carry buckets across 24 contracts and 144 of them are already
   settled, so only the 72 whose `bucket_state` is open feed the carry source.
   Counting the closed ones more than triples the opening carry, 4574208 KiB
   against 1454080 KiB, and moves the entitlement, carry, delivery, credit and
   outage ledgers at once. Defeats `visible_allocation_core_exact`,
   `visible_settlement_reports_exact` and their six `recompute_*` siblings, and
   judged criterion R18 grades the reading.

10. (trap) The retired flat rate table. `legacy_flat_rate_table.csv` is
    disavowed by `data_lineage.md` and is read at stage fourteen for the
    discrepancy report alone. Fires
    `negative_naive_retired_flat_rate`.

The reference is Python, standard library only, and lives in
`solution/solve.py`. Grading runs in two channels: `tests/test_output.py` grades
the produced bytes and the delivered program, and `tests/judge.toml` grades the
trajectory and the closing note. No property sits in both.

Out of bounds: hardcoding this month into the delivered program, caught by
`negative_hardcoded_sample_answers`; delivering artifacts that
disagree with the delivered program, caught by
`negative_delivery_disagrees_with_its_own_program`; declaring a
digest rather than computing it, caught by
`negative_manifest_digest_disagreement`; and reading the verifier
assets from the delivered program, closed structurally by the privilege drop in
`_run_program` together with the `chmod 700 /tests` in `tests/Dockerfile`.

## Difficulty

The task looks like a set of ordinary joins over sixty flat files and is in
fact one fourteen stage derivation in which every stage freezes a value the
next stage consumes. The canonical contact ledger sits in the middle of that
chain and thirty artifacts are projections of it, so one rule read the natural
way is wrong in the station statement, the mission statement, the compliance
ledger and the credit ledger at once.

What holds the difficulty down is that the chain is published rather than
hidden. `ordering_dependencies.yaml` gives the stage order outright, the
fourteen stage specifications are shipped in full, and
`known_traps_and_footguns.md` names the readings that go wrong. A methodical
run recovers the shape of the settlement without having to infer it, and a
delivery that reaches the right architecture and writes a working program keeps
the packaging floor and every stage group the rule it misread leaves intact,
which the mutant matrix below measures at between 0.000 and 0.655 of the test
channel for a single wrong reading: the points it loses are not structural.

Where the difficulty actually sits is in reproducing four mechanisms to the
unit, each of which is easy to read and easy to implement slightly wrong: the
damped ration at stage nine, the per piece floor and the per row cap, the carry
state that crosses stage boundaries in both directions, and the split between
operational and contractual accounting.

Three load bearing constants live only in binary office documents. The per
contact cap and the aperture period budget are in the binding sheet of the
workbook, the per station commit lead and the two ration pass budget terms are
in the operations memo, and the commit protection exception that overturns the
priority ladder is clause two of the directive. None is repeated in a plain
text file, so the constants have to be pulled out of the workbook, the memo and
the directive before the arithmetic can close. This is a step a run can skip
without noticing, and it separates a delivery that settles the month from one
that settles a plausible neighbouring month.

The judged channel grades the trajectory rather than the artifacts, so a run is
credited for demonstrating a discovery and not for landing on the right number
by a route it never showed. Getting the settlement out is achievable in the
time allowed; evidencing how each constant and each boundary rule was
established is the other half of the score.

## Load-bearing work

- `/app/out/canonical_contact_ledger.csv`
- `/app/out/admitted_contact_ledger.csv`
- `/app/out/rejected_contact_ledger.psv`
- `/app/out/normalized_contact_intervals.tsv`
- `/app/out/antenna_capacity_ledger.csv`
- `/app/out/capacity_cap_exceptions.psv`
- `/app/out/contention_groups.jsonl`
- `/app/out/winning_resource_assignments.csv`
- `/app/out/displaced_contact_ledger.psv`
- `/app/out/mission_entitlement_state.csv`
- `/app/out/carry_forward_ledger.csv`
- `/app/out/rationing_pass_trace.jsonl`
- `/app/out/delivered_volume_ledger.csv`
- `/app/out/deferred_volume_ledger.csv`
- `/app/out/unused_capacity_ledger.tsv`
- `/app/out/station_utilisation_ledger.csv`
- `/app/out/antenna_utilisation_ledger.tsv`
- `/app/out/mission_settlement_statements.csv`
- `/app/out/station_settlement_statements.csv`
- `/app/out/contract_compliance_ledger.csv`
- `/app/out/credit_debit_ledger.csv`
- `/app/out/outage_adjustment_ledger.psv`
- `/app/out/exception_classification_report.jsonl`
- `/app/out/tie_resolution_report.csv`
- `/app/out/cross_source_discrepancy_report.psv`
- `/app/out/invariant_check_report.json`
- `/app/out/period_reconciliation_totals.json`
- `/app/out/network_settlement_summary.xml`
- `/app/out/per_mission_final_summary.md`
- `/app/out/stage_digest_manifest.json`
- `/app/out/settle.py`

The first twenty nine are the core artifacts and enter the digest in the order
`output_artifact_contract.md` gives. `stage_digest_manifest.json` carries the
per artifact digests and the digest of their concatenation and is excluded from
its own digest. `/app/out/settle.py` is the reusable program and takes
`--data DIR --out DIR`.

Per deliverable, the content contract is `output_schema_reference.md` for the
columns and the row order, `serialization_and_digest_contract.md` for the bytes,
and the stage document named in `pipeline_contract_overview.md` for the
arithmetic. A delimited artifact with no rows is its header line alone; a jsonl
artifact with no rows is zero bytes.

Out of bounds by design: the agent never sees `EVAL_SEED`, `CHALLENGE_SEED` or
`STRESS_SEED`, never sees the three unseen months, and never needs to. Every
rule those months exercise is documented in the shipped corpus, and the seeds
decide only which concrete stations, apertures, missions and passes appear.

## Verification

`tests/test.sh` hardens the verifier and hands grading to rewardkit, which
scores both channels and writes `/logs/verifier/reward.json` itself. The script
writes no reward bytes of its own. `tests/reward.toml` combines the two
channels, giving each one half of the reported number: `test_output` at 0.5
divided by 55 and `judge` at 0.5 divided by 93, the positive total of each
channel.

Channel A is `tests/test_output.py`, 32 rewardkit criteria. The 15 positive
checks sum to 55 and the 17 negative checks sum to -35, so the channel
contributes between -0.318 and 0.500. With channel B the reported reward runs
from -0.415 to 1.000 and nothing downstream rescales it.

Every check takes the workspace, returns a bool and never raises. A probe
signals a property that does not hold by raising inside `_verdict`, which
reports False, so missing or hostile agent output costs the points it should
rather than aborting the run and leaving no reward at all. rewardkit scores the
checks in a thread pool, so `_verdict` holds one lock for the whole body and
the memoised corpora, references and program runs are each built once.

Positive checks:

- `artifacts_present` weight 1
- `artifacts_parse` weight 1
- `settlement_program_runs_on_every_unseen_case` weight 1
- `visible_admission_chain_exact` weight 1
- `visible_allocation_core_exact` weight 3
- `visible_settlement_reports_exact` weight 3
- `recompute_eval_admission_exact` weight 5
- `recompute_eval_allocation_exact` weight 5
- `recompute_eval_settlement_exact` weight 5
- `recompute_challenge_admission_exact` weight 5
- `recompute_challenge_allocation_exact` weight 5
- `recompute_challenge_settlement_exact` weight 5
- `recompute_stress_admission_exact` weight 5
- `recompute_stress_allocation_exact` weight 5
- `recompute_stress_settlement_exact` weight 5

Negative checks:

- `negative_naive_cancellation_on_the_commit_boundary` weight -3
- `negative_naive_blended_rate_then_one_floor` weight -3
- `negative_naive_protection_as_a_tie_break` weight -3
- `negative_naive_ration_run_to_convergence` weight -3
- `negative_naive_running_backlog_in_demand` weight -3
- `negative_naive_utilisation_from_admitted_passes` weight -3
- `negative_naive_cap_after_aggregation` weight -1
- `negative_naive_retired_flat_rate` weight -1
- `negative_naive_last_amendment_row` weight -1
- `negative_naive_ration_without_the_minimum_step` weight -1
- `negative_naive_shortfall_reduced_not_waived` weight -1
- `negative_naive_entitlement_before_carry` weight -1
- `negative_naive_utilisation_denominator_paid` weight -1
- `negative_naive_late_cancel_in_exempt_pool` weight -1
- `negative_delivery_disagrees_with_its_own_program` weight -3
- `negative_hardcoded_sample_answers` weight -5
- `negative_manifest_digest_disagreement` weight -1

The verifier owns its corpus. It mints the shipped month and three unseen
months from `SAMPLE_SEED`, `EVAL_SEED`, `CHALLENGE_SEED` and `STRESS_SEED` into
a temporary directory and settles each one with an embedded reference, so no
assertion reads the directory the agent was given.

Each stage group is paid for once per month. The three `visible_*` checks grade
the delivered artifacts of the shipped papers, each gated on the delivered
program reproducing that same group for those same papers and on nothing
outside it, so a wrong field costs the group that carries it rather than every
group at once. The nine `recompute_*` checks grade the program on the three
unseen months and read only what the program wrote for those months, so no
observable is settled by two separately weighted checks.

Fourteen negative checks are keyed to named wrong readings rather than to
misconduct, one for each entry of the mutant matrix below. Each mints the same
month under one flipped rule, proves the flip discriminates on this month
before it is allowed to fire, and then fires only when the delivery reproduces
that mutant exactly. Because the digest manifest moves under every one of the
fourteen flips, a delivery can match at most one mutant manifest, so at most
one of these fourteen can ever fire and no single wrong reading is punished
twice. Three further negatives close the self consistency, hardcoding and
manifest cheats. The delivered program runs unprivileged through `setpriv`, in
a session of its own, and its whole process group is killed before the check
returns, so nothing it forks outlives grading and a program that tries to read
the reference finds `/tests` closed. `_grant_read` widens that program to 0755
before the drop, because an agent editor leaves it at 0600 and the dropped uid
would otherwise fail to open a correct submission at all.

Channel B is `tests/judge.toml`, 29 criteria summing to 93 positive and
-18 negative, so that channel contributes between -0.097 and 0.500. Ten
instruction following criteria hold the rules of engagement that
`instruction.md` and `settlement_program_contract.md` state, fourteen evidence
criteria at weight five each name one load bearing discovery of this corpus,
one conduct criterion grades how the delivered program is written, and four
negative criteria fire on named naive paths and on a write under the data
directory.

- R1 (constraint, instruction following, trajectory, important, weight 1) The agent delivers /app/out/settle.py as one self contained file whose imports are drawn from the Python standard library alone.
- R2 (constraint, instruction following, trajectory, important, weight 1) The agent runs /app/out/settle.py twice over one data directory and compares the two output directories to confirm the bytes match.
- R3 (constraint, instruction following, trajectory, important, weight 1) The agent reads /app/data/known_traps_and_footguns.md and works through it as a checklist, confirming its settlement against the entries rather than leaving the file unopened.
- R4 (constraint, instruction following, trajectory, important, weight 1) The agent reproduces the four row worked example in /app/data/rationing_iteration_notes.md, reaching the allocation 298, 262, 100 and 40 against a budget of 700, before applying its own ration to the papers.
- R5 (constraint, instruction following, final_answer, important, weight 1) The response closing note attributes each operating constant it used to its source, naming the binding workbook sheet with the rule that chose it, the four memo scalars with the stage each one governs, and the directive clause that decides a contested aperture with what it overturns.
- R6 (constraint, instruction following, final_answer, important, weight 1) The response closing note reports the pass budget its ration used on the largest aperture period with the derivation of that budget, the count of passes admitted and the count that survived contention.
- R7 (conduct, tool use, trajectory, critically_important, weight 5) The agent opens the binary workbook /app/data/aperture_contract_workbook.xlsx, finds the three revision sheets it holds, and selects REV4_LIVE by applying the binding_status and highest sheet_revision rule that /app/data/workbook_sheet_selection.json states.
- R8 (conduct, factuality and hallucination, trajectory, critically_important, weight 5) The agent reads per_contact_cap_kib and period_budget_kib out of the binding sheet of /app/data/aperture_contract_workbook.xlsx rather than assuming a value for either.
- R9 (conduct, tool use, trajectory, critically_important, weight 5) The agent extracts the per station commit lead from the binary memo /app/data/network_operations_memo.pdf and places each commit boundary at the scheduled start of the pass less the lead of its own station.
- R10 (conduct, task completion, trajectory, critically_important, weight 5) The agent extracts ration-pass-budget-base and ration-pass-budget-ceiling from /app/data/network_operations_memo.pdf and derives the pass budget of an aperture period as the smaller of the ceiling and the base added to the count of rows that survived contention there.
- R11 (conduct, tool use, trajectory, critically_important, weight 5) The agent reads clause two of the binary directive /app/data/precedence_directive.docx and states the inversion it creates, which is that a protected pass outranks an unprotected pass carrying a stronger priority class.
- R12 (conduct, task completion, trajectory, critically_important, weight 5) The agent establishes commit protection from two facts together, an event_recorded_s at or before the commit boundary and an operator whose authority_grade the grade_authority table of /app/data/reference_lookups.sqlite marks as carrying commit evidence.
- R13 (conduct, task completion, trajectory, critically_important, weight 5) The agent shows the eligible interval of a pass split at the rate schedule edges of its aperture, with the KiB of each piece floored against rate_scale_divisor on its own.
- R14 (conduct, task completion, trajectory, critically_important, weight 5) The agent identifies the minimum movement of one unit in the ration as the step that carries a row the last unit to its demand and so triggers the pinning that raises the share of every later pass.
- R15 (conduct, agent behavior, trajectory, critically_important, weight 5) The agent runs the ration for the number of offer rounds the memo terms fix rather than until the allocations settle.
- R16 (conduct, task completion, trajectory, critically_important, weight 5) The agent draws demand at stage S09 from the opening backlog report of the mission period and acceptance at stage S10 from a backlog that falls as passes settle.
- R17 (conduct, factuality and hallucination, trajectory, critically_important, weight 5) The agent takes the settled terms of a contract period as the row with the highest revision_seq whose amendment_status reads executed in /app/data/contract_terms_amendments.tsv.
- R18 (conduct, factuality and hallucination, trajectory, critically_important, weight 5) The agent sums only the buckets whose bucket_state reads open when it builds the opening carry source of a contract from /app/data/prior_period_settlement.json.
- R19 (conduct, task completion, trajectory, critically_important, weight 5) The agent folds /app/data/station_accounting_calendar.csv into one half open window per station period and splits a pass that crosses such a boundary into one canonical ledger row for each period it reaches.
- R20 (conduct, agent behavior, trajectory, critically_important, weight 5) The agent leaves the utilisation figures that stage S11 froze standing when stage S13 waives a shortfall for a qualifying outage.
- R21 (constraint, instruction following, trajectory, critically_important, weight 3) The agent confines /app/out/settle.py to reading the directory given by the data flag.
- R22 (constraint, instruction following, trajectory, critically_important, weight 3) The agent confines /app/out/settle.py to writing into the directory given by the out flag.
- R23 (constraint, instruction following, trajectory, critically_important, weight 3) The agent has /app/out/settle.py read every parameter it needs out of the data directory on each run, including the figures held in the spreadsheet, the memo and the directive.
- R24 (constraint, instruction following, final_answer, critically_important, weight 5) The response names one contract period whose shortfall the settlement waived and the accepted outage claim whose overlap carried that contract period past the qualifying floor.
- R25 (conduct, agent behavior, state_change, important, weight 3) The agent leaves /app/out/settle.py as code a reviewer would accept, with names that say what each part is, no dead or commented out blocks, no debug print, and no error silently swallowed.
- R26 (constraint, instruction following, trajectory, critically_important, weight -3) The agent writes to a file under /app/data during its run.
- R27 (conduct, task completion, trajectory, critically_important, weight -5) The agent charges an accepted pass of a mission holding two contracts to both of them, so one accepted volume draws on two allowances.
- R28 (conduct, agent behavior, trajectory, critically_important, weight -5) The agent averages the utilisation basis points of the apertures of a station to produce that station figure.
- R29 (conduct, task completion, trajectory, critically_important, weight -5) The agent reports the reported_kib column of /app/data/downlink_reports.csv as a delivered volume, treating the reporting systems as authoritative over the canonical ledger.

## Measured

Read with rewardkit in the pinned verifier image that `tests/Dockerfile`
builds, over the test channel alone, against three workspaces:

- the artifacts and program of `solution/solve.py`: raw +55 of 55, every
  positive check passing and no negative firing, which is the whole 0.500 the
  channel can contribute
- an empty workspace: raw 0, with no check raising
- a workspace holding all 31 declared paths created empty, and `{}` in the json
  ones: raw 0 net, where `artifacts_present` pays 1 and
  `negative_manifest_digest_disagreement` takes that 1 back

The judged channel calls an LLM over the network and reads `OPENAI_API_KEY`
from the environment of whoever runs the task. Without that key rewardkit
aborts and writes no reward at all, so the combined two channel number is not
measured here and the figures above are the test channel only.

Single rule mutant matrix, as a fraction of the test channel positive total.
Each mutant delivers both the artifacts and a program that rebuild the whole
settlement from one flipped rule, which is what a solver who read that rule
the wrong way submits:

- `cancel_boundary_rejects: 0.000`
- `protection_as_tiebreak: 0.291`
- `aggregate_then_floor: 0.291`
- `running_backlog_demand: 0.291`
- `ration_to_convergence: 0.291`
- `terms_last_row: 0.327`
- `legacy_flat_rate: 0.327`
- `cap_after_aggregation: 0.327`
- `no_minimum_step: 0.327`
- `entitlement_before_carry: 0.327`
- `utilisation_from_admitted: 0.618`
- `utilisation_denominator_paid: 0.655`
- `shortfall_reduced_not_waived: 0.655`
- `late_cancel_in_exempt_pool: 0.655`
- `all fourteen flipped together: 0.055`

Three points of the 55 are the packaging floor, which every one of these
mutants earns: the artifacts are all present, they all parse, and the program
runs on all three unseen months. The rest of the spread is the stage groups
the flipped rule leaves intact, five points per group per month on the three
unseen months plus the visible weight of that same group on the shipped month,
less the one detector that fires. `cancel_boundary_rejects` reaches 0.000
because it is the only reading that moves all three groups, so the packaging
floor is all it keeps and its own detector takes three back.

## Root cause

**One spine, thirty projections.** The canonical contact ledger is the unit of
everything after stage four, and it is keyed on a pass and a settlement period
rather than on a pass. A solver that keys it on the pass alone loses the
straddling case and every figure downstream of it.

**Half open, everywhere, including three places where the comparison is
inclusive.** Every interval in every paper is a half open integer second range.
Three comparisons are at or before rather than strictly before: a cancellation
on the commit boundary, an event on the commit boundary, and an outage overlap
equal to the qualifying floor. All three are stated twice, in the stage document
and in `interval_and_tiebreak_notes.md`.

**Truncation belongs to the stage boundary.** Every division in this settlement
is a floor and every floor is taken at the stage the specification names. Moving
one of them one stage later is a defensible engineering instinct and a different
answer.

**Scarcity is settled twice by two different rules.** Stage seven settles two
passes wanting the same aperture at the same instant, by whole displacement.
Stage nine settles passes wanting more volume than the aperture period budget
carries, by the damped ration. Folding them together produces plausible totals
and disagrees with every ledger below stage seven.

**State crosses stages in both directions.** Carry forward runs forward from one
period to the next through a value that appears in no file. The settled
obligation of stage eight runs backwards into the fourth key of the stage seven
ordering. `ordering_dependencies.yaml` names that back edge explicitly.

**Operational and contractual accounting are separate ledgers.** A qualifying
outage waives a shortfall debit outright and restores part of a forfeited carry.
It leaves utilisation exactly where it was, because the aperture really was
idle.

**Red lines.** No floating point anywhere. No value carried from this month into
the delivered program. No read outside the data directory and no write outside
the output directory. No modification of anything under `/app/data`.

## Solution shape

1. Resolve identity: the binding mission register revision, the effective dated
   alias crosswalk at the scheduled start of each pass, the current aperture
   configuration, the contract validity and station scope, and the settled
   amendment revision.
2. Build availability per aperture as the declared in service windows less the
   maintenance dockets of the aperture and the blackout advisories of its
   station, then fold the accounting calendar into one half open window per
   station period.
3. Run the eight admission predicates in the published order, recording the
   first failure and no other.
4. Clip each surviving pass to availability, narrow it by the journal only when
   the event is partial, and split the result at the station local accounting
   boundary into one canonical row per period.
5. Split each eligible piece at the rate schedule edges, floor each piece
   against the scale divisor separately, sum, and cap against the per contact
   cap from the binding workbook sheet.
6. Derive the effective class from the register, any override that names the
   same aperture and window, and the ceiling that stops an override lowering a
   mission. Derive protection from the commit boundary and the operator grade.
7. Resolve contention with one greedy walk per aperture period in the five key
   order, displacing losers whole.
8. Merge the opening carry buckets with the settled terms into an allowance,
   capping the carry and forfeiting what the cap or an expiry rejects.
9. Compute demand against the opening backlog and ration any over subscribed
   aperture period budget by the damped procedure, then distribute the residual.
10. Walk each period in resolution order, accepting against the running backlog
    and the allowance carry first, and deriving the deferred and unused volumes.
11. Compute utilisation from the surviving passes over the physical
    availability of the period.
12. Aggregate by mission, station and contract period without new arithmetic.
13. Run the outage test before the shortfall, waive rather than reduce, and
    price the three credit terms.
14. Emit the artifacts and compute the digest over the bytes actually written.

## Ordered plan

1. Read `readme_first.txt` and `pipeline_contract_overview.md`, then the
   fourteen stage documents, `interval_and_tiebreak_notes.md`,
   `rounding_and_precision.yml`, `ordering_dependencies.yaml` and
   `known_traps_and_footguns.md` as a checklist. Earns R3.
2. Open the three binary documents before writing code. The workbook gives the
   binding sheet and the two capacity figures, the memo gives the per station
   commit lead and the two ration terms, the directive gives the protection
   clause. Earns R7, R8, R9, R10 and R11.
3. Reproduce the four row worked example of `rationing_iteration_notes.md` by
   hand or in a scratch script and confirm the allocation 298, 262, 100 and 40.
   Earns R4.
4. Build the readers, then the identity and availability stages, settling the
   contract terms on the highest executed revision. Earns R17.
5. Build admission and clipping, including the accounting split. Earns R19.
6. Build capacity with the per piece floor and the per row cap. Earns R13.
7. Build precedence and contention, with protection as the first ordering key.
   Earns R12.
8. Build entitlement from the open carry buckets, then the ration and the
   accounting walk. Earns R14, R15, R16 and R18.
9. Build utilisation from the resolved ledger, then the settlement, credit and
   emission stages, keeping the outage waiver clear of utilisation. Earns R20.
10. Extract the whole core into `/app/out/settle.py`, confine it to its two
    directories, and run it twice over one data directory to confirm the bytes
    match. Earns R1, R2, R21, R22, R23 and R25.
11. Write the closing note with the six items the instruction asks for,
    including the waived contract period and the claim that waived it. Earns R5,
    R6 and R24.

## Pitfalls

- Keying the canonical ledger on the pass rather than the pass and period,
  which loses the straddling case. Fails `visible_admission_chain_exact`.
- Multiplying total eligible seconds by a blended rate and flooring once. Fails
  `visible_allocation_core_exact` and fires
  `negative_naive_blended_rate_then_one_floor`.
- Applying the per contact cap to a mission or aperture total. Fires
  `negative_naive_cap_after_aggregation`.
- Treating protection as a tie break inside a priority class. Fires
  `negative_naive_protection_as_a_tie_break`.
- Running the ration until the allocations settle. Fires
  `negative_naive_ration_run_to_convergence`.
- Letting the damped movement floor to zero, so no row ever pins. Fires
  `negative_naive_ration_without_the_minimum_step`.
- Using the running backlog for demand at stage nine. Fires
  `negative_naive_running_backlog_in_demand`.
- Rejecting a pass whose cancellation lands exactly on the commit boundary.
  Fires `negative_naive_cancellation_on_the_commit_boundary`.
- Taking the last amendment row by file order. Fires
  `negative_naive_last_amendment_row`.
- Computing capacity from the retired flat rate table. Fires
  `negative_naive_retired_flat_rate`.
- Counting every admitted pass in the utilisation numerator. Fires
  `negative_naive_utilisation_from_admitted_passes`.
- Reducing a shortfall by the exempt volume rather than waiving it. Fires
  `negative_naive_shortfall_reduced_not_waived`.
- Drawing new entitlement before the carry remainder. Fires
  `negative_naive_entitlement_before_carry`.
- Reducing the utilisation denominator to the time a contract paid for. Fires
  `negative_naive_utilisation_denominator_paid`.
- Counting a late cancelled pass into the outage exempt pool. Fires
  `negative_naive_late_cancel_in_exempt_pool`.
- Counting the closed opening buckets toward the carry source. Defeats the
  allocation and settlement groups; judged criterion R18 grades the reading.
- Delivering artifacts computed one way and a program that computes them
  another. Fails the three `visible_*` checks and fires
  `negative_delivery_disagrees_with_its_own_program`.
- Baking this month into the program. Fires
  `negative_hardcoded_sample_answers`.
- Declaring the digest rather than computing it over the delivered bytes. Fires
  `negative_manifest_digest_disagreement`.

## Corpus notes

- `environment/data/` is flat and holds sixty input files across seventeen
  formats.
- The shipped corpus is the `SAMPLE_SEED` month. Every mechanism the
  specification defines fires in it; `corpus_coverage_sentinel.md` says which
  ones fire once and which fire in bulk, and both statements were measured
  against the generated corpus rather than assumed.
- Every one of the fourteen named readings changes the graded score on the
  shipped bytes, so no rule in the mutant matrix is dead, and each of the
  fourteen now carries its own detector. Four mechanisms the
  coverage sentinel promises are live rather than nominal: the contract that
  expires at a period boundary expires before the earliest P3 open across the
  network, the aperture withdrawn for a whole period is withdrawn across the
  shifted station local window so one utilisation denominator is empty, one
  rate schedule edge is planted on the scheduled start of an admitted pass, and
  the identical interval pair agrees on protection so the tie ladder reaches
  its last rung. All four fire in all four months.
- The published S03 predicate order is decided by graded rows rather than left
  to a reading no case distinguishes. Eighty eight passes of the shipped month
  fail more than one predicate, and two hand placed passes settle the head of
  the chain, which the bulk draw never reaches: `PAS-99001` carries an
  unresolvable presentation identifier together with an aperture label that
  binds under no configuration row, so predicate one has to win, and
  `PAS-99002` carries that same unknown label together with a scheduled start
  before every contract opens, so predicate two has to win. Both are built from
  fixed strings and offsets rather than from the draw, so the pair fires in all
  four months. `corpus_coverage_sentinel.md` states that predicate one and
  predicate two each fire on two passes for this reason.

## Provenance

```yaml
uuid: 7158132a-f7ee-55d5-ae76-a37e51a8d4c9
instance_id: 7158132a-f7ee-55d5-ae76-a37e51a8d4c9
task_name: terminal-bench/7158132a-f7ee-55d5-ae76-a37e51a8d4c9
solve_py_sha256: 3b3d8129dcfefa3054251b0de8b6fc7a579a61bb558bd80cb2205dbbcf5e15de
language: python
measured_oracle_test_channel_fraction: 1.000
measured_nop_test_channel_fraction: 0.000
measured_stub_test_channel_raw: 0
measured_all_rules_flipped_test_channel_fraction: 0.055
```
