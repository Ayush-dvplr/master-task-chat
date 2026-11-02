# TRUTH.md - b625f36e-d6b6-5f41-945c-c6a8484234d7

The crux, in one sentence: an event's canonical state is decided by resolving
its whole competing revision history first, and the revision that wins then
decides which effective dated reference row every downstream lookup resolves
against, so a single wrong selection silently relocates the event's site, zone,
tariff, ceiling, settlement day and quantity at once.

## Defect

Nothing here is broken. Everything is delivered, and the delivery is the
problem. `/app/data` holds fifty nine files: eight specification documents,
three configuration layers, eight reference tables, one manifest, one prior
publication, thirty seven batch files and one batch nobody registered. Across
the in scope batches sit 10548 body lines carrying 4561 logical events, and the
deliverable is a reusable program that turns them into twenty three exact
artifacts. The difficulty is not writing a pipeline. It is that several
delivered rows compete to define one event, the winner is chosen by a rule that
is neither the latest nor the largest, and every figure downstream is computed
against the row that won.

1. (focal) Class rank outranks revision number. The canonical revision of an
   event is the highest ranked class, then the highest revision number within
   that class, then the lowest batch sequence. 1232 of 4561 events carry a
   canonical revision whose number is below the highest admitted number for that
   event, so `max(revision_no)` and last seen both produce a complete and wrong
   ledger. Taking the highest revision number alone moves the watt-hour quantity
   of 265 events.
2. (focal) The delivery identity of a row includes the batch family it arrived
   in. Two producing systems can both deliver revision three of one event as a
   correction, and both are admitted rather than one being a duplicate. 215
   events carry such a pair, and the lowest batch sequence decides which reading
   governs. A solver who keys duplicates on event key, revision number and class
   alone loses one of the two and takes the wrong quantity for whichever it
   kept.
3. (focal) The field named `quantity` is kilowatt hours in five batch families
   and whole watt hours in the sixth. Reading the adjustment family in kilowatt
   hours multiplies those readings by a thousand and moves the quantity of 191
   events; the interval ceiling then clamps them to a plausible looking cap
   rather than to an absurd number.
4. (focal) A restatement revision carries a signed delta, not a reading. The
   base is the highest ranked admitted revision that is not a restatement, the
   ceiling is applied to the base, the deltas are added in revision order, and
   the ceiling is applied again to the sum. 2280 events have a value changed by
   one clamp or the other and 114 of them only by the second, so a single clamp
   is right almost everywhere and wrong on a population large enough to move
   every total: applying the ceiling once, after the deltas, moves 102 events.
   The clamp register holds an event when a clamp changed its value, which
   covers a figure lowered to the ceiling and equally one raised to zero.
5. (focal) A merge applies from its own instant forward, and merges chain.
   `site_merges.csv` carries 219 rows, 60 of which carry an instant outside the
   settlement calendar and therefore never apply at all. 1457 events keep the
   absorbed site because their effective instant precedes the hop, 1113 take at
   least one hop, and 210 resolve through two hops in a row. Remapping every
   absorbed site regardless of instant moves 834 events; stopping the walk after
   one hop moves 103 of the 210 that need two.
6. (focal) `batch_manifest.csv` decides membership, not the directory listing,
   and it also decides reading order. Three batches are present and withdrawn,
   one is required and absent, one sits on disk with no manifest row, and the
   desk family is registered out of alphabetical order, so reading the directory
   by file name admits the wrong row of a duplicated pair. Globbing the
   directory ingests 1160 body lines that do not belong and misses the
   unresolvable condition entirely.
7. (drift) The settlement day opens at 06:00:00Z, not at midnight, and the
   window is half open. 1178 events carry a settlement day that differs from
   the date portion of their effective instant once it is carried to UTC.
   Extracting the date from the timestamp is what an experienced engineer does
   without thinking, and it misfiles a quarter of the corpus without moving one
   watt-hour quantity, because the settlement day feeds no figure.
8. (drift) Every effective dated lookup is made at the effective instant, which
   is the canonical revision's `occurred_at`. Using `ingested_at` moves 311
   events, and reading the intervals as closed rather than half open moves a
   further population at the boundary. Both produce a ledger that is internally
   consistent and wrong.
9. (drift) The rounding namespace resolves to the numerically smallest value
   across all three configuration layers while every other key resolves last
   wins. A uniform last wins reading gives `rounding.quantity_dp` of 4 rather
   than 2 and changes the presentation field on every ledger line.
10. (drift) Site references join only after Unicode composition. Twelve
    registered sites carry an accented code form and several producing systems
    emit it decomposed, so 41 delivered rows join only once NFC is applied. A
    join that skips composition rejects them as unknown sites and takes the
    whole corpus with it.
11. (trap) The validation checks run in a stated order and stop at the first
    failure. 201 rejected rows fail more than one check, so the order decides
    which code each of them carries; MALFORMED_ROW is decisive for 58 of them.
12. (trap) A correction or restatement whose `supersedes_revision` names a
    revision nobody delivered is genuinely undecidable. 266 events are in that
    condition and belong in the unresolvable record under `ORPHAN_SUPERSEDE`.
    Computing a value for them instead is the single most natural way to produce
    a fuller looking ledger that is wrong.
13. (trap) An event whose every admitted revision is a restatement carries no
    base at all. 32 events are in that condition and belong under `MISSING_BASE`,
    which the outcome precedence reaches only after the orphan supersede test.
14. (trap) An empty quantity, a zero quantity and an absent field are three
    conditions. 163 events defer because their base carries no reading, and a
    delivered zero is a real reading that settles. Collapsing the two moves 163
    events into the settled population at zero watt hours, which changes the
    settled event count without changing any total.
15. (trap) A reversal zeroes the quantity and keeps the event in the ledger and
    in every count. 288 events are reversed. Dropping them is the instinct and
    it breaks the class partition identity by exactly that many.
16. (trap) An excluded event keeps its ledger row and its partition row under
    the resolved exclusion policy and contributes nothing to any settled total.
    209 events are excluded. Withholding them from the partitions leaves every
    settled figure correct and every row count wrong.
17. (trap) `delta_flag` is advisory. The revision class decides whether a
    quantity is a reading or a signed delta, and the two disagree often enough
    that trusting the flag moves the quantity of a large population.
18. (trap) The prior publication is granular to the zone cell. Thirty five of
    the thirty seven cells the restatement covers differ from this run, so no
    partition total can be read off it, and a run that repeats the published
    figures as its own restatement records a difference of zero everywhere.
19. (focal) A delivered count is not a reading. The registration covering a
    row's own `occurred_at` carries a `pulse_multiplier`, the whole number of
    metered units one count stands for, and the quantity the row delivers is
    its numeral multiplied by that multiplier. Of the 497 registration rows,
    249 carry a multiplier above one and 22 carry no readable multiplier at
    all, which makes them no registrations and is reported nowhere. Dropping
    the multiplier moves 1596 events, and applying it to the integer the single
    conversion produced rather than to the exact decimal before it moves 23,
    because a half multiplied first is no longer a half.
20. (trap) The effective dated files are corrected in place rather than
    rewritten, so more than one row of one key can cover one instant. The row
    that opens latest governs, and where two covering rows open together the
    one that closes earliest does, which leaves file order deciding nothing.
    Taking the first covering row in file order moves 52 events.
21. (trap) A ceiling that is absent is not a ceiling of zero. 128 events have a
    canonical site with no `max_interval_limits.csv` row covering the effective
    instant, and each of them is unresolvable under `MISSING_CEILING`, a test
    the precedence weighs ahead of the one that defers a base carrying no
    reading. Reading the hole as zero settles all 128 at zero watt hours.
22. (trap) A restatement covers the cells the publication states together with
    the cells this run computes, and never one of the two alone. The
    publication states a zone the network has retired since, so 5 of the 35
    adjustment rows restate a published cell to zero, and a run that weighs
    only the cells it computed loses those five rows and the baseline total
    behind them.

The reference is authored in Python 3.12, standard library only, a 1017 line
program. `solve.sh` places it at the declared deliverable path and runs that
copy, so the shipped program and the shipped run are the same bytes, and because
the placement happens in the shell rather than inside the program, the delivered
program itself reads nothing outside the directory `--data` names. It is
written from the shipped specification and shares no implementation with the
verifier: it parses the settlement calendar out of `settlement-calendar.md`,
derives each batch family from its file name against `record-layouts.md`, and
uses `datetime` where the verifier uses its own integer instant arithmetic. The
measured line overlap between `solution/solve.py` and `tests/test_output.py` is
9 percent of its 767 substantive lines, and all of it is incidental. That independence is what makes the
oracle run evidence: the two implementations agree only because both are right.

Out of bounds: editing anything under `/app/data`, writing files at the
deliverable paths beyond the declared set, reading anything outside the
directory `--data` names, embedding the shipped batches or the published figures
as literals, and emitting a timestamp, host name or run path into any artifact.

## Load-bearing work

The program and twenty three artifacts, every one shaped by a documented rule
whose wrong application changes a graded value.

```
/app/out/materialize.py                the reusable program, rerun on unseen data
/app/out/canonical_ledger.jsonl        one line per event, the primary result
/app/out/revision_index.jsonl          the staged intermediate: every admitted
                                       revision with its role
/app/out/partition_20310308.csv        the eight settlement partitions, cut from
  through partition_20310315.csv       the ledger under the exclusion policy
/app/out/partition_manifest.json       self reported counts and totals per day
/app/out/rejects.csv                   rejected rows with closed reason codes
/app/out/quarantine.jsonl              conflicting redeliveries
/app/out/dedup_ledger.csv              duplicate deliveries collapsed
/app/out/deferred.jsonl                events whose base carries no reading
/app/out/unresolvable.json             orphan supersedes, missing bases and the
                                       missing batch
/app/out/entity_resolution.json        per event merge decisions, applied or not
/app/out/clamp_register.csv            which clamp stage changed which event
/app/out/stack_register.csv            every restatement revision and its stack
                                       state
/app/out/restatement_adjustments.csv   signed deltas against the publication
/app/out/reconciliation.json           the three identities and their residuals
/app/out/validation_report.txt         the recorded self check
/app/out/run_manifest.json             resolved configuration and branch decisions
```

The dependency graph is five levels deep. Level one parses and disposes of every
row under the manifest and the validation precedence. Level two resolves the
competition inside each event and selects the canonical and base revisions.
Level three walks the merge chain and reads the effective dated rows at the
effective instant. Level four computes the quantity under the two stage clamp
and assigns the outcome. Level five cuts the partitions, rolls the zone cells,
subtracts the publication and reconciles. Two dependencies are implicit: the
contract states the ordering of the ledger without restating that
`canonical_site` is a post merge value, and it states the zone cell without
restating that the zone is read at the effective instant.

The most constrained artifact is `canonical_ledger.jsonl`, which carries twelve
simultaneous documented constraints: twelve keys in sorted order, compact
separators, one object per line, LF endings, a trailing newline, the three key
ordering, every event present exactly once whatever its outcome, the quantity in
integer watt hours, the kilowatt hour presentation at the resolved precision,
the outcome drawn from the closed set of five, the canonical site as a post merge
value, and the zone read at the effective instant.

## Verification

Grading is `rewardkit`. `tests/test.sh` clears any stale reward file, recreates
`/logs/verifier` as root owned at mode 755, strips group and other permissions
from `/tests`, and then execs `rewardkit /tests --workspace /app --output
/logs/verifier/reward.json`. Two channels live under `/tests` and
`tests/reward.toml` combines them with a weighted sum: 0.5/97 for each point of
channel A and 0.5/54 for each point of channel B, so the two channels are worth
half the reward each and a run that is both exact and honestly reported earns
1.0.

Channel A is `tests/test_output.py`, thirty five checks registered at the bottom
of that file through `criteria.<name>(weight=W)`. Twenty three carry positive
weight and sum to 97; twelve carry negative weight and sum to -40. Reward on
this channel is the signed sum of the weights that fired over 97, with no clamp.

The verifier owns a corpus builder and its own implementation of the rules, so
every expected value is recomputed rather than stored and `/app/data` is never
read. It regenerates the visible corpus from its seed and compares the agent's
artifacts against the recomputed bytes, then regenerates an unseen corpus, runs
the delivered program against it, and compares again. Fifteen of the 97 positive
points sit on that unseen run.

The ledger is graded column by column rather than as one byte comparison. Each
of the eight ledger sweeps owns its own columns and asserts them across every
event the corpus carries, so a solver who broke exactly one rule loses that
rule's weight rather than the whole artifact, and no fact is paid for twice.
Every other deliverable is asserted whole by exactly one check.

Positive checks, by weight:

```
5  canonical_ledger_structure_and_order       presence, key set, ordering,
                                              serialization
5  canonical_revision_selected_by_class_rank  revision_no, revision_class
5  quantity_chain_across_every_event          quantity_wh, quantity_kwh
5  tariff_band_floor_across_every_event       tariff_band
5  outcome_precedence_across_every_event      outcome
5  revision_index_exact
5  partition_files_exact
5  event_records_exact                        rejects, quarantine, dedup ledger,
                                              deferred, unresolvable, clamps
5  partition_manifest_exact
5  restatement_adjustments_exact
5  reconciliation_exact
5  identity_triangle_holds                    cross artifact, relations only
5  unseen_corpus_ledger_and_partitions_exact
5  unseen_corpus_event_records_exact
5  unseen_corpus_adjustments_and_reconciliation_exact
3  settlement_day_window_across_every_event   settlement_day
3  site_resolution_across_every_event         source_site, canonical_site
3  effective_dated_attributes_across_every_event  zone, tariff_class
3  partitions_agree_with_the_ledger           cross artifact, reads neither file
                                              against the expectation
3  stack_register_exact
3  entity_resolution_exact
3  run_records_exact
1  all_declared_artifacts_present
```

Negative checks. Each probe returns false when the artifact it reads is absent
or unreadable, so a missing deliverable costs the positive points without also
drawing the penalty, and each one needs a population rather than a single row
before it fires:

```
-5  negative_out_of_scope_batch_rows_ingested
-5  negative_adjustment_quantity_read_as_kilowatt_hours
-5  negative_weight_hardcoded_sample_answers
-3  negative_quantity_rounded_half_up
-3  negative_reformatted_duplicates_quarantined
-3  negative_merge_applied_before_merge_instant
-3  negative_baseline_figures_copied_into_adjustments
-3  negative_deferred_events_counted_as_settled
-3  negative_excluded_events_omitted_from_partitions
-3  negative_weight_nondeterministic_output
-3  negative_weight_filename_dependent_behaviour
-1  negative_program_imports_outside_stdlib
```

Two of them, `negative_merge_applied_before_merge_instant` and
`negative_deferred_events_counted_as_settled`, are restricted to events whose
canonical revision the run already picked correctly, so a wrong selection
upstream cannot trip a probe aimed at a different rule. That restriction, plus
the fact that no triggering action carries a penalty on both channels, is what
keeps any single agent mistake to one penalty.

Grading executes the agent's program three times, all of them against corpora
the verifier generates: once over the unseen corpus, once more over that same
corpus to compare the bytes, and once over a copy of it placed under a different
directory name. The unseen run is built once under a lock and cached, because
rewardkit runs checks on worker threads. Every execution goes through
`_run_program`, which drops to `nobody` with `setpriv` where the image supports
it, gives the child a session of its own, and kills that whole session when the
run returns. `/tests` is unreadable to that user and `/logs/verifier` is root
owned at mode 755, so nothing the agent spawned can read the expectations or
rewrite the reward.

Channel B is `tests/judge.toml`, twenty two judged criteria read by a model in
`batched` mode. Sixteen carry positive weight summing to 54 and six carry
negative weight summing to -20. Its criteria read the trajectory at
`/logs/agent/trajectory.json` and the closing message, never an artifact byte a
channel A check reads.

```
R1  r1_merge_rows_outside_calendar            5   merge rows dated outside the
                                                  settlement calendar
R2  r2_out_of_scope_body_lines                5   body lines the out of scope
                                                  batches would have added
R3  r3_settlement_day_differs_from_utc_date   5   events whose settlement day is
                                                  not the UTC date portion
R4  r4_multi_fail_rejected_rows               5   rows failing more than one
                                                  check, and the decisive code
R12 r12_reformatted_duplicates                5   duplicates differing only in
                                                  how a number is written
R13 r13_variant_half_up_conversion            5   events moved by a half up
                                                  conversion
R5  r5_last_wins_quantity_dp                  3   the rounding counterfactual
R6  r6_variant_highest_revision_number        3   canonical by revision number
                                                  alone
R7  r7_variant_date_portion_day               3   settlement day from the date
                                                  portion
R8  r8_variant_adjustment_read_as_kwh         3   adjustment family read as kWh
R9  r9_variant_single_clamp                   3   ceiling applied once, after
                                                  the deltas
R10 r10_variant_every_merge_applied           3   every merge applied regardless
                                                  of its instant
R11 r11_variant_ingestion_instant_lookups     3   lookups at ingested_at
R14 r14_residuals_stated                      1   the three residuals stated as
                                                  zero
R19 r19_variant_runs_executed                 1   a rule flipped variant was
                                                  actually run and compared
R20 r20_rerun_compared                        1   the program was run twice and
                                                  the output diffed
R21 r21_reads_grader                         -5   read a path under /tests or
                                                  /logs/verifier
R15 r15_corpus_modified                      -3   wrote under /app/data
R16 r16_extra_files_under_out                 -3  left an undeclared file under
                                                  /app/out
R17 r17_program_reads_outside_data           -3   materialize.py opened a path
                                                  outside --data
R18 r18_figure_given_as_range                -3   gave a closing figure as a
                                                  range or an estimate
R22 r22_unsupported_claims                   -3   claimed a check the trajectory
                                                  does not show
```

The thirteen value and divergence criteria from R1 to R13 are the reason the
channel exists: not one of their figures is held in any of the twenty three
artifacts. Five are properties of the corpus no deliverable states, one is a
configuration counterfactual, and the remaining seven are counts of events that
move under the habitual reading of a rule, which only a second run with that
rule flipped can produce. R19 and R20 pay for that second run and for the byte
comparison, and the negatives cover the three scope rules, the grader boundary
and the two honesty rules that no assertion over the artifacts can settle.

Nothing on this channel can be measured without a model. A mutation of
`solution/solve.py` produces artifacts but no trajectory and no closing message,
so the near miss behaviour described below concerns channel A only and channel B
is silent about it.

### Near miss behaviour

Every trap has a wrong branch that still emits a complete, well formed artifact
set, and every one of them costs weight on channel A. The shape of the loss
sorts into two bands.

The load bearing rules sit upstream of the event's identity, so breaking one of
them changes values that every downstream artifact inherits and takes most of
the whole artifact checks with it: the settlement day
taken from the date portion, a join that skips Unicode composition, a directory
glob in place of the manifest, lookups at ingestion time, merges applied
regardless of instant, canonical selection by revision number alone, a merge
walk stopped after one hop, a cross family tie broken by the highest sequence,
the adjustment family read as kilowatt hours, batches read in file name order, a
single clamp after the deltas, `delta_flag` trusted over the class, and
effective dated intervals read closed. Several of these also fire a negative
probe on top of the positive weight they lose.

The supporting rules are confined to one artifact or one population, so breaking
one costs that artifact's weight and leaves the rest standing: `MISSING_BASE`
never reported, excluded rows withheld from the partitions, last wins applied to
the rounding namespace, the band taken as the ceiling threshold, and the
validation checks run in reverse order.

A no-op run scores zero, since every positive check reads an artifact that is
not there and every negative probe returns false rather than firing. A stub that
creates the twenty four declared paths empty earns only
`all_declared_artifacts_present`, one point of 97.

### Traceability

Every requirement in `instruction.md` and in the shipped specification maps to at
least one check or criterion, and every check and criterion maps back.

```
requirement                          stated in                    graded by
manifest decides membership          protocol 1                   negative_out_of_scope_batch_rows_ingested -5,
                                                                  revision_index_exact 5, R2 5
batches read in batch_seq order      protocol 1                   event_records_exact 5,
                                                                  revision_index_exact 5
missing batch reported               protocol 1, reason-codes     event_records_exact 5
validation precedence, first failure protocol 2                   event_records_exact 5, R4 5
delivery identity includes family    protocol 2                   canonical_revision_selected_by_class_rank 5,
                                                                  revision_index_exact 5
duplicate against conflict           protocol 2                   event_records_exact 5,
                                                                  negative_reformatted_duplicates_quarantined -3,
                                                                  R12 5
canonical by class rank then number  protocol 3                   canonical_revision_selected_by_class_rank 5,
                                                                  R6 3
then lowest batch sequence           protocol 3                   canonical_revision_selected_by_class_rank 5,
                                                                  revision_index_exact 5
effective instant governs lookups    protocol 3, entity-model     effective_dated_attributes_across_every_event 3,
                                                                  R11 3
base revision selection              protocol 3                   revision_index_exact 5,
                                                                  stack_register_exact 3
quantity unit per batch family       protocol 4, record-layouts   quantity_chain_across_every_event 5,
                                                                  negative_adjustment_quantity_read_as_kilowatt_hours -5,
                                                                  R8 3
half even unit conversion            protocol 4, contract         quantity_chain_across_every_event 5,
                                                                  negative_quantity_rounded_half_up -3, R13 5
delta_flag is advisory               protocol 4                   quantity_chain_across_every_event 5,
                                                                  stack_register_exact 3
two stage clamp, both directions     protocol 4, contract         quantity_chain_across_every_event 5,
                                                                  event_records_exact 5, R9 3
tariff band floor rule               protocol 4a                  tariff_band_floor_across_every_event 5
outcome precedence                   protocol 5                   outcome_precedence_across_every_event 5
MISSING_BASE reached after orphan    protocol 5, reason-codes     outcome_precedence_across_every_event 5,
                                                                  event_records_exact 5
an empty quantity defers             protocol 5                   negative_deferred_events_counted_as_settled -3,
                                                                  event_records_exact 5
zone cell and the publication        protocol 6, restatement-notes restatement_adjustments_exact 5,
                                                                  negative_baseline_figures_copied_into_adjustments -3
rounding namespace smallest wins     protocol 7                   run_records_exact 3, R5 3
exclusion policy places the row      protocol 7                   negative_excluded_events_omitted_from_partitions -3,
                                                                  partitions_agree_with_the_ledger 3
join normalization including NFC     entity-model                 site_resolution_across_every_event 3,
                                                                  entity_resolution_exact 3
merge applies from its instant       entity-model                 site_resolution_across_every_event 3,
                                                                  negative_merge_applied_before_merge_instant -3,
                                                                  R1 5, R10 3
merges chain                         entity-model                 site_resolution_across_every_event 3,
                                                                  entity_resolution_exact 3
half open effective dated intervals  entity-model                 effective_dated_attributes_across_every_event 3
settlement day opens at 06:00:00Z    settlement-calendar          settlement_day_window_across_every_event 3,
                                                                  partition_files_exact 5, R3 5, R7 3
exact bytes of every deliverable     contract                     every whole artifact check,
                                                                  all_declared_artifacts_present 1
three identities and residuals       instruction, contract        identity_triangle_holds 5,
                                                                  reconciliation_exact 5,
                                                                  partition_manifest_exact 5, R14 1
rerunnable and byte identical        instruction                  negative_weight_nondeterministic_output -3,
                                                                  R20 1
path independent                     instruction                  negative_weight_filename_dependent_behaviour -3
figures fall out of the rules        instruction                  unseen_corpus_* 15,
                                                                  negative_weight_hardcoded_sample_answers -5
habitual reading counts measured     instruction                  R6 to R11 3 each, R13 5, R19 1
program is stdlib only               instruction                  negative_program_imports_outside_stdlib -1
program reads nothing outside --data instruction                  R17 -3
inputs left exactly as found         instruction                  R15 -3
nothing else at the declared paths   instruction                  all_declared_artifacts_present 1, R16 -3
closing message states the figures   instruction                  R1 to R14, R18 -3
honest reporting of what was checked instruction                  R22 -3
the grader is never read             rules of engagement          R21 -5
pulse multiplier before the quantize protocol 4, entity-model     quantity_chain_across_every_event 5,
                                                                  revision_index_exact 5
latest valid_from governs an overlap entity-model                 effective_dated_attributes_across_every_event 3,
                                                                  quantity_chain_across_every_event 5
an absent ceiling is unresolvable    protocol 5, reason-codes     outcome_precedence_across_every_event 5,
                                                                  event_records_exact 5
restatement covers the cell union    protocol 6, restatement-notes restatement_adjustments_exact 5,
                                                                  reconciliation_exact 5
```

## Root cause

**Identity is not a row property.** Every rule in the protocol that looks like a
field mapping is actually a consequence of one prior decision. The effective
instant, the merge hop, the zone, the ceiling and the settlement day are all
read from the canonical revision, so an error in section 3 of the protocol
propagates into five downstream sections without touching any of them. This is
why the traps interact rather than accumulate.

**Two systems can both be right.** The delivery identity includes the batch
family because two producing systems restating the same revision is a real
condition, not a conflict. Collapsing them loses information the ordering rule
needs, and the ordering rule is the only thing that decides which reading counts.

**A ceiling is a property of a value, not of a total.** Applying it to the base
and again to the sum is what keeps an event's contribution inside the physical
limit of its meter at both the stage where the base could exceed it and the
stage where the restatements could push it past, or below zero.

**A publication is evidence, not an answer.** The prior figures are an input the
run reconciles against. Adopting them produces a difference of zero, which is
the one answer that is certainly wrong given the batches delivered since.

## Solution shape

1. Read the manifest, keep the rows whose status is `ACTIVE`, sort by batch
   sequence, and record the required file that is absent.
2. Parse each batch in its own serialization, reading the quantity in the unit
   its family declares and scaling it by the pulse multiplier of the
   registration covering that row's own `occurred_at` before the single
   conversion, and dispose of every body line under the validation precedence,
   stopping at the first check that fails.
3. Key the delivery identity on event key, revision number, revision class and
   family, and split later arrivals into duplicates and conflicts by payload.
4. Group admitted revisions by event; select the canonical and the base by class
   rank, then revision number, then batch sequence.
5. Take the effective instant from the canonical revision and walk the merge
   chain, taking each hop only from its own instant forward and stopping at the
   first hop the instant precedes.
6. Read the effective dated zone, tariff, operational state and ceiling at that
   instant against the site the chain reached, letting the row that opens
   latest govern where two of them cover the instant, and leaving an event
   whose site has no ceiling row there unresolvable.
7. Clamp the base, add the restatement stack in revision order, clamp the sum,
   and record which stage changed a value.
8. Assign one outcome from the documented precedence.
9. Write the ledger in canonical order, then cut the partitions from it under
   the resolved exclusion policy.
10. Roll the settled rows into zone cells, subtract the publication, and write a
    row only where a cell moved.
11. Compute the three residuals and record the resolved configuration and the
    branch decisions. Place the program itself at its declared path from the
    shell, so the program never reads its own source.
12. Re-run the pipeline seven more times with one rule flipped each time, and
    count the events whose watt-hour quantity moves, for the closing message.

## Ordered plan

A competent human follows this in roughly 400 minutes.

1. List `/app/data` and read the protocol, the calendar, the entity model, the
   vocabularies, the layouts and the output contract before writing anything.
2. Resolve the three configuration layers and note that the rounding namespace
   resolves differently from everything else.
3. Read the manifest and establish which batches are in scope, which is absent,
   which is unlisted, and in what order the sequence numbers put them.
4. Write the six parsers, one per serialization, and confirm the partner column
   order and the fixed width offsets against the layout document.
5. Implement the join normalization including Unicode composition, and confirm
   the accented site codes join.
6. Implement the validation precedence and check the reason code distribution
   against the closed vocabulary, including the rows that fail two checks.
7. Implement the delivery identity including the family, and confirm that
   duplicates and conflicts separate on payload.
8. Implement canonical and base selection, and verify on an event where the
   highest revision number is not canonical.
9. Implement the merge walk, confirm that a merge dated outside the calendar
   never applies, and confirm the chain takes two hops where both instants have
   passed.
10. Implement the effective dated lookups at the effective instant.
11. Implement the unit conversion, the two stage clamp and the restatement stack.
12. Implement the outcome precedence and check the five populations sum to the
    event count.
13. Write the ledger and the staged revision index in canonical order.
14. Cut the partitions under the exclusion policy and write the partition
    manifest.
15. Write the disposition, deferred, unresolvable, entity resolution and clamp
    records.
16. Roll the zone cells, read the publication, and write only the moved cells.
17. Compute the three residuals and write the reconciliation, the validation
    report and the run manifest.
18. Run the program twice and diff the output.
19. Run it against a relocated copy of the corpus to confirm nothing is bound to
    the path.
20. Produce the thirteen reported figures, seven of which need a second run with
    one rule flipped.
21. Confirm no file under `/app/data` changed and nothing extra sits in
    `/app/out`.

## Pitfalls

- Selecting the canonical revision by `max(revision_no)`; fails
  `canonical_revision_selected_by_class_rank` and every artifact built on
  the ledger.
- Keying duplicates without the batch family; fails
  `canonical_revision_selected_by_class_rank` and
  `revision_index_exact`.
- Reading the adjustment family in kilowatt hours; fires
  `negative_adjustment_quantity_read_as_kilowatt_hours`.
- Taking the settlement day from the date portion of the instant; fails
  `settlement_day_window_across_every_event` and every partition.
- Remapping every absorbed site; fires
  `negative_merge_applied_before_merge_instant`.
- Stopping the merge walk after one hop; fails
  `site_resolution_across_every_event`.
- Skipping Unicode composition in the join; fails almost everything, because the
  rows it rejects are admitted rows.
- Globbing `/app/data` for batches; fires
  `negative_out_of_scope_batch_rows_ingested`.
- Reading the batches in file name order; fails `event_records_exact`.
- Applying the validation checks in reverse order; fails
  `event_records_exact`.
- Clamping once; fails `quantity_chain_across_every_event` and
  `event_records_exact`.
- Holding the clamp register to values a clamp lowered only; fails
  `event_records_exact`, since the contract holds an event whose value a
  clamp changed in either direction.
- Computing a value for an orphan supersede; fails
  `outcome_precedence_across_every_event`.
- Never reporting `MISSING_BASE`; fails
  `outcome_precedence_across_every_event`.
- Treating an empty quantity as a zero reading; fires
  `negative_deferred_events_counted_as_settled`.
- Withholding excluded rows from the partitions; fires
  `negative_excluded_events_omitted_from_partitions`.
- Applying last wins to the rounding namespace; fails
  `run_records_exact`.
- Repeating the published figures as the restatement; fires
  `negative_baseline_figures_copied_into_adjustments`.
- Baking the shipped answers into the program; fires
  `negative_weight_hardcoded_sample_answers`.
- Keying behaviour on the corpus directory path; fires
  `negative_weight_filename_dependent_behaviour`.
- Dropping the pulse multiplier, or applying it to the integer the conversion
  produced rather than to the exact decimal before it; fails
  `quantity_chain_across_every_event` and `revision_index_exact`.
- Taking the first covering row where a reference file was corrected in place;
  fails `effective_dated_attributes_across_every_event`.
- Reading a gap in `max_interval_limits.csv` as a ceiling of zero; fails
  `outcome_precedence_across_every_event`.
- Restating only the cells this run computes; fails
  `restatement_adjustments_exact`.

## Corpus walk

Every file under `environment/data` carries only inputs and specification.
There is no expected output, no worked full example,
no checksum or row count of any deliverable, no self test and no comment stating
a computed result. The published baseline is the only file carrying figures that
resemble a deliverable, and thirty five of the thirty seven cells the
restatement covers differ from this run, so no partition total and no ledger
value can be read off it. The two cells that agree cannot be identified from
inside the corpus. Each wrong branch listed under Pitfalls changes at least one
graded value and still emits a complete, well formed artifact set with no crash
and no warning.

## Provenance

```yaml
task_name: terminal-bench/b625f36e-d6b6-5f41-945c-c6a8484234d7
language: python
solve_py_sha256: 14034126c1ad5b6c28d037b3e1d0b2b88394403b11af3b532fb3b4c9c1040453
test_output_sha256: 37cdb7bb6413ba6995aa8dbe5f7d7705ba72887863a9512ac63e9032b2cf1e63
judge_sha256: 31105e6b63f346626c5010479e3db2e8aefcb42cc4633fd024be65f7303101c8
corpus_files: 59
corpus_bytes: 1951130
delivered_rows: 10548
events: 4561
artifacts: 23
positive_total: 97
negative_total: -40
test_checks: 35
judge_criteria: 22
```
