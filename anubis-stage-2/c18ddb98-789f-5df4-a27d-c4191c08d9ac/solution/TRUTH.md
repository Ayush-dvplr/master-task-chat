# TRUTH.md - c18ddb98-789f-5df4-a27d-c4191c08d9ac

Author facing record for the settled ingest window task. Never shipped to the
agent and never mounted into the task environment.

## Defect

There is no broken artifact to repair here. The defect is an absence: the
platform that produced this working set never wrote down how it settles a
window, and the working set alone does not tell you in what order its rules
bear on a record. The deliverable is the settled window, and the work is
recovering the platform from what it published.

- The order in which the four rate adjustments compose is nowhere in the
  reference set (focal). Twenty four orders are legal; one reproduces the
  published control figures.
- The spacing of the settlement grid, the convention for a value between two
  grid points, and the backpressure coefficient the surcharge is a share of are
  nowhere in the reference set (focal). Nine spacings, five conventions and six
  hundred and one coefficients are legal. The adjustment rulebook states how the
  coefficient is scaled by the overage, so the arithmetic is readable; only the
  coefficient itself is withheld.
- The quarantine state of the feeds is defined by rules that speak about each
  other, so a single forward pass produces a quarantine set that is silently too
  small rather than an error (drift). The shipped window needs two rounds: FD-11
  crosses its allowance on the first, and the taint FD-11 leaves behind is what
  pushes FD-12 over on the second.
- The tombstone rule is the reverse of the ordinary change data capture
  convention (trap). It is stated in terms in `rulebook_retention.md`, so it is
  a maintenance failure rather than a comprehension failure, but a solver that
  carries its prior about delete semantics into this window withdraws only the
  records that follow a tombstone and keeps eighty records it should have let
  go.
- The number of partition reports is a consequence of the settlement rather
  than a fact about the estate (trap). NORTHFIELD has four feeds, carries
  traffic, is not provisional, and still settles nothing, because one of its
  feeds is designated, two are quarantined by the fixpoint, and the cascade from
  those two takes every record on the fourth. A solver that stops before the
  fixpoint emits a fourth domain report that must not exist.
- The reserve slot designation is a constraint system rather than a preference
  (drift). One hundred and twenty assignments satisfy the per channel
  conditions, fifteen for CASCADE against eight for TIDEWATER; the band in the
  policy register admits exactly one of them, and the choice that looks natural
  for one channel leaves no valid choice for the other.

## Load-bearing work

Every input file is necessary. Deleting any register makes the window
unsettleable, and deleting `calibration_controls.json` makes the five withheld
properties unrecoverable.

The serial chain is fifteen stages deep with two convergence points:

1. Parse the registers.
2. Resolve every producer reference to a canonical identity as at the emission
   instant of the record that carries it, following renames and merges in force
   transitively and detecting cycles.
3. Apply the window boundary, the suspension flag and the provisional domain
   rule.
4. Apply the tombstone rule in its retroactive reading over the whole window.
5. Select the governing rate card for every surviving record.
6. Compute the base unit rate from the card rate and the form multiplier, placed
   on the settlement grid.
7. Compose the four adjustments in the recovered order, placing after each.
8. Apply upheld exceptions as outright replacements of the unit rate.
9. Solve the reserve slot designation. First convergence point: it consumes the
   feed register, the domain register, the channel register, the incident
   register and the policy band at once.
10. Withdraw the records of every designated feed.
11. Drive the quarantine state to its fixpoint. Second convergence point: it
    consumes the tombstone outcome, the designation, and the per domain identity
    resolution at once, and it feeds back into itself.
12. Curtail every domain to its curated cap under the feed coverage obligation.
13. Derive which domains and channels are in scope.
14. Emit the ledger, the partition reports and the window artifacts.
15. Reconcile and summarise.

Stage k consumes the exact output of stage k minus one. A wrong decision at
stage 4 changes the pool the fixpoint at stage 11 measures, which changes the
partition set at stage 13, which changes which files exist at stage 14.

## Egress layer

rulebook_egress.md sections E1 to E7 run after the window has settled and read
the curated ledger it produced. They revise nothing above them: every charge,
count, cap, designation, quarantine state and partition report keeps the value
the settlement gave it. The egress layer is where the deliverable's headline
figures now live, and it deliberately refuses the conventions of the rulebooks
it sits on top of. Four of its rules invert a habit the reference set teaches:

- E1 prices a curated record per octet of payload with a TRUNCATING division,
  `record_charge_micros // (payload_units * 8)`. Every other division in the
  reference set places its result on the settlement grid by the convention
  rulebook costing describes. Carrying that convention into E1 is wrong on 84
  of the 97 curated records of the shipped window, so it is the single most
  expensive habit here rather than a rare edge case. The octet factor is what
  makes the rule bite: dividing the charge by the payload units alone diverges
  from E1 on all 97, because that quotient is just the settled unit rate again.
- E2 holds back a burst record when its rate exceeds `med + sigma * mad` over
  its own domain and feed group, with the median absolute deviation used
  UNSCALED and sigma read from `egress_policy.csv`. The shipped window groups
  into 6 cohorts of 8 to 23 records and holds back 9. A cohort of fewer than
  four records rejects nothing.
- E3 takes the LOWER of the two middle values of an even sample, never their
  mean and never placed on the grid. 3 of the 6 shipped cohorts have an even
  sample, so the even branch is the branch that runs.
- E4 emits the retained records by ASCENDING egress rate, which is never the
  canonical ledger order rulebook ledger fixes by sequence.

E5 sums the retained rates into `egress_pool_micros`, E6 apportions the
window's curated payload units across the cohorts by largest remainder over
their summed rates, and E7 reduces the positional sum of the E4 order by the
published modulus. The shipped window settles to `egress_pool_micros` 19191 and
`egress_digest` 71779 over 88 retained records, with the 6 cohort shares
summing to the 485 curated payload units exactly.

## Verification

`tests/test_output.py` carries seventy nine rewardkit checks: seventy six
positive for a positive weight total of 308, and three negative for an absolute
total of 11, so the test channel's share never falls below -0.5.
`tests/reward.toml` gives this channel half the final reward at `0.5 / 308` and
the judged channel the other half at `0.5 / 118`. Every check returns a bool and
never raises, so bad, missing or hostile output lands as a zero rather than as a
verifier error.

The reference settlement of the shipped window and of thirty five mutated
windows is embedded in `test_output.py` as a zlib stream of one JSON object,
written out in hexadecimal so that no marker a reviewer greps the bundle for can
turn up inside it. The module docstring carries the one line of Python that
prints it back, and the object holds nothing but the calibration block, the shipped
window's artifacts and, per corpus, the registers to materialise, the egress
policy that corpus publishes and the artifacts the reference engine settled it
to. It is data rather than code, and the same bytes as a plain literal would add
eight megabytes to one source line.

Weights follow one rule: 5 is a core outcome the task exists to produce, 3 an
important sub-goal or edge case, 1 a minor detail, an existence check or a
formatting rule. `instruction.md` states that the settled account and the egress
layer are two outcomes of equal standing, so a core outcome on either side
carries 5 and neither tier is flattened against the other. It also states that
the program will be run against other windows and may carry no value true of
this window alone, which makes settling an unseen window the deliverable's
primary behaviour rather than a bonus, so each corpus check carries 5 as well.

The three tiers are forty eight checks at weight 5, twenty at weight 3 and eight
at weight 1, which is the positive total: 5 times 48 plus 3 times 20 plus 1
times 8 is 308.

Core outcomes at weight 5, forty eight of them. Five from the settlement of the
shipped window: `summary_matches_reference`, `unit_charges_match_reference`,
`dispositions_match_reference`, `adjustment_precedence_recovered` (the recovery
of the five withheld properties) and `conservation_residuals_zero` (the proof
nothing was lost or invented). Eight from the egress layer of the shipped
window, each reading one hidden decision: `egress_rate_truncates_not_places`
(E1), `egress_burst_threshold_uses_mad` (E2), `egress_median_takes_lower_middle`
(E3), `egress_order_is_ascending_rate` (E4),
`egress_apportionment_matches_largest_remainder` (E6),
`egress_rates_cover_every_curated_record` (coverage of the curated ledger),
`egress_apportionment_sums_to_curated_units` (the E6 closure) and
`egress_ladder_rendering_matches_groups` (the rendering). And thirty five
`corpus_*` checks, one per mutated window.

Important sub-goals and edge cases at weight 3, twenty of them: seventeen
settlement properties (`canonical_identity_resolution`,
`identity_resolution_register_complete`, `ledger_carries_register_facts`,
`quarantine_state_is_a_fixpoint`, `curated_cap_binds_in_every_domain`,
`ledger_order_and_running_total`, `feed_coverage_obligation`,
`governing_rate_card_selection`, `partition_membership_derived`,
`reserve_slot_designation`, `tombstone_retroaction`, `upheld_exception_override`,
`window_admission_and_quality`, `record_counts_close`,
`withdrawal_reasons_complete`, `domain_reports_match_reference` and
`channel_reports_match_reference`) and three egress checks
(`egress_pool_excludes_bursts` for E5, `egress_digest_matches_order` for E7 and
`egress_counts_match_burst_decision` for the two counts the burst decision
produces).

Minor details, existence and formatting at weight 1, eight of them:
`program_delivered`, `fixed_artifacts_present`, `program_takes_two_directories`,
`canonical_ordering_of_collections`, `serialization_form`,
`egress_summary_echoes_octets` and `egress_artifacts_name_their_window` (two
figures liftable verbatim from the registers, so weighted as the transcriptions
they are) and `egress_artifacts_are_integers` (key presence and the absence of
any floating point value, which is a formatting rule rather than a settled
figure).

Negative checks and weights:

- `negative_hardcoded_window_answers` at weight -5
- `negative_burst_record_in_egress_order` at weight -3
- `negative_program_rewrites_its_registers` at weight -3

The three negatives name different agent actions, so no single mistake fires two
of them: carrying figures true of the shipped window alone into the delivered
program, carrying a held-back record into the E4 order, and writing into the
register directory the program was pointed at. The maximum any one action costs
is 5.

Each check owns one observable and no field is decided twice, in any pairing.
Within the egress tier each rulebook rule is read once and the weaker
projections of those rules were removed rather than registered alongside them:
the E1 quotient and the fields carried forward onto the same rows are two
different observables of `egress_rates.json`, the E2 threshold and the E3 median
are two different observables of `egress_bursts.json`, and the pool, the digest,
the two burst counts, the octet echo and the window identifier are five
different observables of `egress_summary.json`, so one wrong figure costs one
check instead of taking its whole artifact down.
`egress_apportionment_sums_to_curated_units` reads the E6 closure property, that
the shares add up to the unit total the artifact echoes, and anchors that echo to
the settled curated payload units; nothing else compares this artifact's
`curated_payload_units` against the reference, so without the anchor a hand
written file whose shares happened to add up to whatever total it declared would
earn the weight. Both of its demands are a different observable from the
reference-share equality `egress_apportionment_matches_largest_remainder` owns.
On the ledger the row fields are split seven ways and no two checks read the
same one: `canonical_identity_resolution` owns `canonical_producer_id`,
`governing_rate_card_selection` owns `governing_card_id`,
`dispositions_match_reference` owns `disposition` and `reason`,
`unit_charges_match_reference` owns the two charge fields,
`ledger_order_and_running_total` owns `sequence`, the ordering key and the
running total, `ledger_carries_register_facts` owns the three fields carried
forward from `landing_records.csv`, and `identity_resolution_register_complete`
owns the `identity_resolutions` array, which is a different observable from the
per record identity because a reference that resolved two ways in one window
makes the two disagree.

Each corpus is one window, and a corpus check reads that window's whole
account: the same artifact names and no others, every settlement figure, every
ledger row in every field, the six egress artifacts and the exact text of the
rendering. That is deliberate rather than a cliff. A figure wrong in one window
costs that window's check alone and leaves the other thirty four corpora and the
forty one per aspect checks on the shipped window untouched, so an answer with
one fact wrong still scores as an answer with one fact wrong; what costs the
whole tier is a rule read wrongly, which is wrong in every window by
construction and should cost accordingly.

The thirty five corpora are chosen so that no two of them exercise the same
decision. Eleven stress the settlement rules the shipped window already
exercises from another angle: ties, caps, designation bands, an emptied
partition, an identity cycle, a moved boundary, a longer fixpoint, a moved
tombstone, a record emitted exactly at the close, a calibration block admitting
a different combination of the withheld properties, and a cap that leaves the
coverage obligation binding. The remaining twenty four stress what the shipped
window leaves untested: registers arriving in the reverse row order, quarantine
floors above every settled domain, curated records carrying no payload at all,
two days no card governs, every exception upheld, a rename chain three deep, a
fully suspended domain, caps far below demand, every feed quarantined and no
feed quarantined, a narrowed and a widened boundary, floor rates above the card
rates and absent altogether, rewritten tier and form classes, doubled and
awkward payloads, producers retiring inside the boundary, one card and every
card live, no exception and no tombstone at all, a rename cycle three producers
long, and every record on one feed. Twenty one of them publish an egress
policy of their own, with a sigma from 1 to 6, a modulus from 97 to 1000039 and
octets per payload unit from 2 to 32, so a program that carries the shipped
sigma, modulus or octet size as a constant settles those corpora wrongly even
when every settlement rule above the egress layer is right.

No positive check grades an absence. Whether a held-back record was wrongly
carried into the E4 order, and whether the program wrote into the register
directory it was handed, are both detected on the negative side, where an empty
or missing artifact earns nothing instead of passing.

The work dependency holds over the egress layer. Every egress check that reads
only the shipped window can be satisfied by a canned table keyed on the shipped
record identifiers, so the corpus checks grade the egress artifacts the program
produces for windows whose curated ledgers differ from the shipped one, with
expectations taken from each corpus's own reference settlement and never from
the program's own output, so a self-consistent forgery cannot satisfy them
either. Measured on the test channel alone: a hand written artifact per declared
path, `{}` for each JSON path and an empty rendering, scores 1 of 308, which is
`program_delivered` alone; doing nothing at all scores 0 of 308 and fires no
negative.

Rule E2's STRICTLY GREATER threshold is load-bearing. No curated record of the
shipped window sits exactly on its group threshold, which is why reading the
rule as `>=` costs nothing there. The `tie_configuration_changed` corpus does
carry such a record, in a group large enough for the rule to apply, so the two
readings diverge on it, and that corpus is graded by
`corpus_tie_configuration_changed`, so the strict reading decides graded output.

`serialization_form` owns the byte form of the shipped window alone: it compares
each delivered file against a re-serialization of that file's own parsed
content, so a wrong value cannot fail it and a wrong byte form cannot fail
anything else on the shipped window.

`feed_coverage_obligation` owns `rulebook_retention.md` R3. The shipped window
never forces the choice, so the check also runs the `coverage_obligation_binds`
corpus, where OAKLINE carries a curated cap of 24 against 186 eligible units and
the charge maximising retention would silence FD-13 entirely.

The judged channel is `tests/judge.toml` and carries thirty five criteria:
thirty two positive for a positive total of 118, and three negative for an
absolute total of 11. No judged criterion restates a value a deterministic check
asserts: the judged channel grades the reporting obligation and the derivation
behind each number, while the deterministic channel grades whether the number is
right. Every criterion that demands a figure in the final message traces to a
sentence in the instruction's closing paragraphs, the egress reporting criteria
included. The two observables around the recovered properties are kept apart so
one sentence cannot earn both: `r14_states_adjustment_composition_order` grades
only that the response names the four adjustments in the order they compose, and
`r27_names_the_evidence_for_the_properties` alone grades naming the calibration
slice as the evidence that settled them. No rulebook attribution is asked for
either way, because `rulebook_adjustment.md` declines to state that order and
`invariants.md` V11 records that it is deliberately unwritten, so demanding one
would have required a false claim.

Twelve of the judged criteria watch the trajectory and the delivered source
rather than the final message. Ten of those carry positive weight, and
`solution/solve.sh` exhibits every one of them: it reads the whole reference set
before writing anything, settles the
window, settles the same registers a second time into a directory of its own and
compares the two accounts file by file, settles a third time from a register
directory outside `/app/data` to show the program carries nothing of this
window, reads the residuals back, and recomputes one curated record's settled
charge by hand, with its own grid placement written out rather than borrowed
from the engine, before reporting. The report it prints then satisfies every
final message criterion in turn, with the arithmetic shown rather than asserted:
the per adjustment trace, the surcharge as the coefficient against the feed's
excess, both readings of the tombstone rule with the record count each would
withdraw, both sides of the three conservation identities, the identity and the
governing card of one named record at that record's own instant, the defect rate
of every feed that survived the quarantine fixpoint beside its allowance, the
count of admissible slot assignments and how many of them land inside the
published band, the units against the cap in each domain, the reason each
uncreated partition report settled out of scope, and the per octet division of
one retained and one held-back record.

## Root cause

The task is hard for one reason: fourteen independently verifiable constraints
have to hold at once over a computation that is serially dependent fifteen
stages deep, and the procedure that satisfies them is not written down anywhere.

Rules are complete. Procedure is absent. The reference set states each rule
precisely and in isolation, states the invariants the result must satisfy, and
publishes a calibration slice whose figures exactly one reading of the platform
reproduces. It never states an order of application, a rounding convention, a
grid spacing, the byte form an artifact takes, or how many partitions exist. The
schema names the fields but leaves their derivation and their serialized form to
the rulebooks and the one shipped example.

## Solution shape

`solution/solve.py` is the reference engine, 1267 lines of standard library
Python. It takes a register directory and an output directory as positional
arguments and contains no value true only of this window.

`recover_parameters` settles the calibration slice once per tombstone reading,
filters on the three record count controls, which are independent of every other
property, then searches the twenty four orders, five conventions and nine
spacings against the control records whose feeds are inside their nominal
throughput, then the six hundred and one coefficients against the control
records whose feeds are over it, then re-settles and checks every remaining
published figure. The staged filter is what makes the recovery tractable: the
product of the twenty four orders, five conventions, nine spacings, six hundred
and one coefficients and two tombstone readings is 1298160 points, and the
record count controls prune all but a small fraction of them before any charge
is settled. Exactly one point survives every published figure.

`settle` runs the fifteen stages. `curtail` is an exact dynamic program over
used units and a feed coverage mask, maximising settled charge, then record
count, then reconstructing so that ties take the lexicographically smallest
identifier list. `designate_reserve_slots` enumerates the per channel options
and takes the product across channels, refusing to settle unless exactly one
assignment falls inside the policy band.

## Ordered plan

1. Read every rulebook, the invariant statement and the calibration material.
2. Settle the calibration slice under candidate readings until one reproduces
   every published figure.
3. Resolve identity as at each record.
4. Apply admission, then the retroactive tombstone rule over the whole window.
5. Select governing cards and compute base rates on the grid.
6. Compose the adjustments in the recovered order.
7. Solve the designation constraint system.
8. Drive the quarantine state to its fixpoint.
9. Curtail each domain under the coverage obligation.
10. Derive the partition set, emit the artifacts, reconcile.

## Pitfalls

- Reading the tombstone rule the ordinary way. Eighty records hang on it, and so
  does the quarantine pool that decides two feeds and one whole domain.
- Breaking a tie on the greater number rather than on the greater text. Two
  incidents share the highest severity on FD-13 and two rename events share an
  instant on PR-20, and in both pairs the identifier that is greatest as text is
  the numerically smaller one.
- Stopping the quarantine loop after one round. FD-12 is only reachable on the
  second round, and NORTHFIELD only disappears because of it.
- Emitting a report for every non provisional domain. NORTHFIELD settles
  nothing and must have no report.
- Treating the designation as a per channel choice. It is one assignment for the
  window.
- Resolving identity against the final state of the event register rather than
  as at each record. PR-06 renames twice, and the two records either side of the
  second rename resolve differently.
- Applying the feed floor before the adjustments rather than as the last word.
- Reading the window interval as closed at both ends. A record emitted exactly
  at the window close belongs to the next window, and the corpus that carries
  one is the only graded input that says so.
- Carrying the five recovered properties into the program as constants. They are
  properties of the platform rather than of this window, so the anti hardcoding
  probe does not reach them, and the corpus whose calibration admits a different
  combination is what makes the program recover them rather than assume them.
- Copying the domain report shape into the channel reports. They are different
  artifacts, and the channel membership list is not narrowed by scope.
- Sorting the ledger by record identifier. It is ordered by emission instant.

- Placing the E1 quotient on the settlement grid, the convention every other
  division in the reference set uses, rather than truncating it -> fails
  `egress_rate_truncates_not_places` and `egress_rates_cover_every_curated_record`.
  84 of the 97 curated records differ between the two.
- Dividing the charge by the payload units without the octet factor -> the
  rates are wrong everywhere and the whole egress layer follows them.
- Scaling the median absolute deviation by the usual 1.4826 consistency
  constant, or reaching for a standard deviation -> fails
  `egress_burst_threshold_uses_mad` and moves the retained set, the pool, the
  apportionment and the digest with it.
- Averaging the two middle values of an even cohort -> fails
  `egress_median_takes_lower_middle`.
- Rejecting from a cohort of fewer than four curated records -> the shipped
  window has no such cohort, so this only shows up on an unseen window, which
  is exactly where the delivered program is graded.
- Leaving a burst record in the pool -> fails `egress_pool_excludes_bursts`, and
  carrying one into the E4 order fires
  `negative_burst_record_in_egress_order`.
- Emitting the egress order in canonical ledger order -> fails
  `egress_order_is_ascending_rate` and `egress_digest_matches_order`, because
  the order is what the digest multiplies positions against.
- Rounding each payload share on its own rather than handing the remainder to
  the largest -> fails `egress_apportionment_matches_largest_remainder` and
  usually `egress_apportionment_sums_to_curated_units` too.
- Taking sigma or the modulus from anywhere other than `egress_policy.csv` ->
  fails the threshold and digest checks on the shipped window, and fails every
  one of the twenty one corpora that publish a policy of their own.
- Taking the octets per payload unit as eight rather than from
  `egress_policy.csv` -> costs nothing on the shipped window, where eight is
  what the register says, and every egress figure of the ten corpora that
  publish another size.
- Reading a register in file order, whether by trusting the first row of
  `window_calendar.csv` without looking, by breaking a tie on arrival order, or
  by emitting a list in the order it was read -> the shipped window and the
  `register_rows_reversed` corpus hold the same rows in opposite orders and
  settle identically, so order dependence shows up there and nowhere else.
- Assuming a window curates something. `defect_allowance_tightened` quarantines
  every feed and `records_on_one_feed` leaves one feed carrying every record,
  and both settle to a charge of zero, no partition report at all and an empty
  egress layer whose pool, digest and share table still have to be written.
- Dividing by a payload of zero. `zero_payload_curated_records` curates records
  that carry none, and E1 passes over them rather than pricing them.

## Declared artifacts that a correct solve never writes

`task.toml` declares all eight candidate partition reports, but a correct
settlement of the shipped window puts only LEDGERWORKS, MERIDIAN and OAKLINE in
scope, so `domain_northfield.json`, `domain_penumbra.json` and
`domain_quarryside.json` are never created. The harness copies declared paths
only, so those three come back as `"status": "failed"` in the run manifest while
the run itself succeeds. That is expected rather than a defect, and declaring
them is load bearing: if the three out of scope names were left undeclared, an
agent that wrongly produced one of them would have it silently dropped and would
escape `partition_membership_derived`, the check that enforces leaving an out of
scope report uncreated.

## Provenance

```yaml
uuid: c18ddb98-789f-5df4-a27d-c4191c08d9ac
instance_id: c18ddb98-789f-5df4-a27d-c4191c08d9ac
task_name: terminal-bench/c18ddb98-789f-5df4-a27d-c4191c08d9ac
fix_patch_sha256: 2e0f8bbab3606f4741fae8c40547195c7301689a2377274208c9a63544655063
solve_py_sha256: 67aee5d115cfcafba98df597f10ee50df7167e6b665cbf4255e7f2074e2b115f
language: python
status: complete
```
