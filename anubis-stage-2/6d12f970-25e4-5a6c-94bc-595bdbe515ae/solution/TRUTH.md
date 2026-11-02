# TRUTH.md - 6d12f970-25e4-5a6c-94bc-595bdbe515ae

## Defect

The agent is handed a written rule set, four directories, and a stream of encoded
work-order packets belonging to a four-site industrial dispatch authority, and is asked to
settle a season: decide which orders run, place each one on a lane so that no lane rule
breaks and no site pays more than a feasible placement forces it to, and settle the money.
Nothing in the shipped material states the values the packet stream was encoded with, the
order in which the rules bind, or the procedure that reaches the answer. Those are the
work. The corpus is arranged so that every plausible shortcut produces output that parses,
balances against itself, and is silently wrong.

1. The wire stream carries twelve independent transforms whose constants are
   withheld. The encoding document names each transform and names the constant it depends
   on, but prints no value. A held-out calibration population ships with twelve published
   control figures; exactly one assignment of the twelve constants reproduces all twelve
   at once, and each control is reachable only once every constant above it in the
   resolution order is already settled. An agent that guesses, or that lifts the constants
   from the untrapped probe tier, decodes a stream that still passes both header and
   payload checksums while carrying wrong values. Defeats the four trap checks
   `test_trap_rotation_shadow_count`, `test_trap_island_permutation_keystream`,
   `test_trap_chain_delta_drift` and `test_trap_rotor_window_quantisation`, which grade
   the twelve single-constant trap corpora three to a check.
2. Four of the twelve transforms make a record undecodable in isolation. The due
   offset of record k is stored folded against the true offset of record k minus one; the
   weights travel as second-order differences reset on a withheld span; the submission day
   travels multiplied by a factor derived from the running load sum of every genuine
   record decoded so far in the population, carried across block boundaries; and a
   programme reference above a sentinel resolves backwards into a trailing window of
   withheld width. A decoder that treats records independently, or that decodes blocks in
   any order other than the order the manifest gives, drifts. Defeats
   `test_trap_chain_delta_drift` and `test_trap_rotor_window_quantisation`.
3. Admission is a fixpoint, and the shipped capacity policy states only that
   exactly one stable congestion assignment exists. The per-site congestion index is a
   function of the admitted slot total, the tier read off that index widens each client's
   admission ceiling, and the widened ceiling admits more orders. A single forward pass
   settles at a congestion figure the policy does not admit, and the error is invisible
   locally because every rollup still balances. Defeats `test_instance_summary`
   and every generalisation test whose mutation moves a site across a tier bound.
4. Placement is a constrained global optimisation. Every admitted order takes
   exactly one lane at its governing client's home site, subject to a class lock, an
   exclusive-client reservation, a slot capacity and a rule forbidding two incompatible
   programme families from sharing a lane. The objective is the minimum total lane cost
   per site. Greedy cheapest-lane-first placement is feasible and more expensive; the
   capacity and family constraints interact so that a locally cheaper choice forces a
   later order onto relief capacity at the site penalty rate. Defeats
   `test_instance_region_rollups` and `test_generalises_lane_rules`.
5. Client identity is derived, never looked up. An alias resolves to a directory
   position, the position resolves through a merge chain, and a closed merge chain is
   governed by the lexicographically smallest client identifier in it. A retirement day
   at or before the submission rejects the order; a first-active day after the submission
   holds it. Resolving identity after selecting a programme revision, rather than before,
   silently reassigns orders to the wrong region partition while leaving every conservation
   residual at zero. Defeats `test_generalises_client_identity` and
   `test_generalises_site_layout`.
6. The contention rule is the exact reverse of the scheduling default. When two
   admitted orders contend for the last slots of the cheapest lane both are eligible for,
   the order with the LARGER remaining slack keeps the lane and the tighter order yields
   to relief capacity. Earliest-deadline-first, the instinct every practitioner brings,
   produces a different placement, a different site cost, and a different displaced set.
   Defeats `test_instance_region_rollups`, `test_instance_segment_rollups` and
   `test_generalises_placement_contention`.
7. The relief lane is named in no file. Each site roster carries one lane with an
   empty class lock, an empty exclusive client and a slot capacity of zero, and
   `dispatch_policy.md` states that such a lane is relief capacity, accepts any quantity
   of any class from any client at the site penalty rate, and is exempt from the family
   rule. The agent must
   correlate the roster against the site directory to discover which lane that is.
   Defeats `test_instance_region_rollups` and `test_generalises_lane_rules`.

The reference implementation is Python 3.12 using the standard library only, written
against the shipped documents rather than against the verifier, so the oracle and the
grader are independent implementations of one contract and a mistake in either is caught
by the other. The task is declared `no-network` and needs no egress at any point: every
input ships in `environment/data/` and the settlement is pure derivation from it. Only the
verifier reaches the network, to put the judged channel in front of its judge. Two grading
channels run against a submission, both scored by rewardkit. Channel A is
`tests/test_output.py`, which scores the delivered artifacts and the delivered program, each
check carrying its weight on its `criteria.<name>(weight=W)` registration. Channel B is
`tests/judge.toml`, judged from `instruction.md`, the trajectory and the readable
deliverables.

Shortcuts that are caught: writing the twelve recovered constants into the delivered program as fixed
literals is caught by `negative_weight_hardcoded_sample_answers`, which reruns the
delivered program against a corpus encoded with different constants and fires only when
the shipped answers come back unchanged; branching on the name of the input directory is
caught by `negative_weight_filename_dependent_behaviour`; pinning the input path
rather than honouring the directory argument is caught by
`negative_weight_reads_supplied_answer_data_at_runtime`; and emitting output that
varies between two runs of the same input is caught by
`negative_weight_nondeterministic_output`; leaning on the labelled probe tier at
run time is caught by `negative_weight_reads_training_corpus_at_runtime`; and reaching
into the grading machinery is caught by `negative_weight_rebinds_verifier_dependencies`.
All six contribute zero against an honest
solver and their full negative weight against the shortcut they name.

## Load-bearing work

Ten artifacts are graded, all under `/app/out/`.

- `derive_report.py` is the deliverable program. It takes an input directory and an
  output directory as its two arguments and derives everything it writes from the files in
  the directory it is given. It is rerun against thirty further
  corpora, so any figure recovered from the shipped corpus that appears in it as a literal
  makes it wrong everywhere else.
- `summary.json` carries the season census and money totals: `order_rows`,
  `decoded_rows`, `orders_scored`, `orders_placed`, `orders_deferred`, `orders_rejected`,
  `billable_slots_total`, `charge_micros_total`, `rebate_micros_total`,
  `capped_micros_total`, `net_micros_total` and `lanes_used`.
- `policy_audit.json` is the derivation record. It carries `candidate_space` (one entry per
  withheld constant, each naming the constant, the control figure that resolves it, its
  domain size, the resolved value, the count of rejected values and a `verdicts` array
  holding one accepted-or-rejected verdict per candidate value in that domain),
  `resolved_parameters`,
  `calibration_comparison` (published against reproduced for all twelve controls),
  `candidates_examined`, `candidates_rejected`, `fixpoint` (`passes`, `congestion_index`
  and `congestion_tier` per site) and `assignment_search` (`sites_searched`,
  `feasible_leaves`, `displaced_orders`, `site_cost_micros`). Channel A asserts its
  presence and its schema only; Channel B grades its content.
- `data_quality.json` is the reconciliation deliverable: `order_rows`, `decoded_rows`,
  `rejected_orders`, `deferred_orders`, `region_net_micros`, `segment_net_micros`,
  `conservation_residual_micros`, `segment_residual_micros`, `calibration_net_micros` and an
  `invariants` object carrying `region_partition_closed`, `segment_partition_closed`,
  `order_identity_unique` and `capacity_respected`.
- `region_North.json`, `region_East.json`, `region_West.json` and `region_South.json` each
  carry `region`, `order_count`, an `orders` list and a `totals` object. Membership is by
  rule: an order joins the rollup of the region the site directory gives for the home site
  of its governing client, so the roster has to be joined against that directory.
- `segment_commercial.json` and `segment_public.json` carry `service_class`, `order_count`,
  `orders` and `totals`, with membership by the governing client's service segment.

Both partitions cover exactly the placed orders, and the region net total, the segment net
total and `net_micros_total` agree to the micro unit, so both residuals in the
reconciliation report are zero.

The shipped corpus is one instance. The verifier regenerates
twelve single-constant variants and eighteen structural mutations and reruns the delivered
program against each, so a solution that reproduces the shipped answers by any route other
than deriving them earns the format and instance tiers and nothing beyond them.

## Verification

`tests/test.sh` clears any stale reward file, sets the verifier log directory to root with
mode 755 and hands over to rewardkit, which writes `reward.json`. Each check in
`tests/test_output.py` runs its body behind one global lock, so the checks run one at a time
even though rewardkit calls them from worker threads, and a failed assertion scores its check
zero rather than aborting the run. The delivered program is never run in place: each run
copies it, and any sibling `.py` file, into a fresh 0755 directory as 0644 files and runs
that copy as an unprivileged user, so the delivered file's own mode cannot decide the score.
`tests/reward.toml` divides each channel's weighted sum by that channel's positive total and
halves it, so each channel carries half the reward.

Channel A carries 33 checks: 27 positive with a positive total of 97, and 6 negative.
FORMAT AND INSTANCE is 22 of 97 over the shipped corpus:
`test_format_deliverables_and_driver` and `test_format_report_schemas` at 1,
`test_instance_summary` at 3, `test_instance_region_rollups` and
`test_instance_segment_rollups` at 5, `test_instance_reconciliation` and
`test_instance_calibration_and_dispositions` at 3, and
`test_instance_partition_conservation` at 1. TRAP is 20 of 97: four checks at weight 5,
`test_trap_rotation_shadow_count`, `test_trap_island_permutation_keystream`,
`test_trap_chain_delta_drift` and `test_trap_rotor_window_quantisation`, each passing only
when all three of its single-constant trap corpora settle exactly. GENERALISATION is 40 of
97: eight checks at weight 5, each over the structural corpora of one rule family:
`test_generalises_held_out_parameters` (all constants moved; another seed),
`test_generalises_lane_rules` (uniform rates; squeezed capacity; changed conflict
families), `test_generalises_admission_rules` (binding budgets; shifted tier bounds),
`test_generalises_site_layout` (an empty region; relocated clients),
`test_generalises_client_identity` (a merge cycle; added clients),
`test_generalises_revision_windows` (shifted boundaries; revision edges),
`test_generalises_placement_contention` (a contention tie; inverted slack) and
`test_generalises_population_shapes` (a larger population; sparse flags; short blocks).
`mut_revision_edges` carries overlapping revisions and a gap on a day the population
carries; `mut_contention_tie` leaves room for exactly one of two orders that tie on slack
and billable slots.

TABLE FORMAT is 15 of 97: seven held-out corpora, each settled under a moved rebate band
and then rewritten in one form that leaves its meaning unchanged, each with its own check.
`test_format_byte_order_mark` (3): `client_directory.csv` and `block_manifest.csv` open
with a UTF-8 byte order mark. `test_format_padded_header_names` (1): every header name of
`lane_roster.csv` carries surrounding spaces. `test_format_padded_cells` (1): the
`alias_key`, `site` and `service_class` cells of `client_directory.csv` carry surrounding
spaces. `test_format_zero_padded_block_ids` (3): `field_orders.csv` writes each block_id
with three digits. `test_format_region_name_case` (3): two regions in `site_directory.csv`
are written in upper case, and their rollups are still `region_North.json` and
`region_West.json`. `test_format_draft_policy_ignored` (1): an unadopted
`capacity_amendment_draft.md` with other congestion bounds and ceilings sits beside the
policy it never amended. `test_format_archived_controls_ignored` (3): a withdrawn
`archived_calibration_slice.md` with stale control figures sits beside the slice in force.
The padding cases are decided by one sentence in `packet_encoding.md` (spaces around a
header name or a cell are not part of it); the byte order mark and the zero padded number
are UTF-8 and integer conventions; the region case follows from the four fixed region file
names; the draft and archived documents say on their first lines that they are not in force.

Six negative checks: `negative_weight_hardcoded_sample_answers` at minus 5,
`negative_weight_filename_dependent_behaviour` at minus 5,
`negative_weight_reads_supplied_answer_data_at_runtime` at minus 5,
`negative_weight_reads_training_corpus_at_runtime` at minus 3,
`negative_weight_rebinds_verifier_dependencies` at minus 3 and
`negative_weight_nondeterministic_output` at minus 3. The filename and training-tier
detectors begin with a same-name, same-corpus control run and abort on a program that already
disagrees with itself, so an unstable program is charged once, by the determinism detector.
The two source-text detectors read the delivered program with comments and docstrings
stripped.

Channel B is `tests/judge.toml`, 23 criteria with a positive total of 32. R1 to R6 are
instruction-following constraints at 1 and R7 (minus 3) covers the read-only input
directory. R8 to R13 at 3 each name a value fixed by an agent-visible file and readable only
from the derivation record. R14 (minus 5) and R15 (minus 3) are the remaining negatives.
R16 to R22 at 1 each are verification conduct, each a run of the delivered program on a
constructed input: a corpus without the probe files, a corpus re-encoded under other
constants, tables in another legal form, an extra non-authoritative document, a perturbed
rule value, a region with no placed order, and a closed merge chain. R23 at 1 judges the
program's structure. The positive total is 6 for R1 to R6, 18 for R8 to R13 and 8 for R16
to R23, and `tests/reward.toml` carries the matching judge weight of 0.015625, that is
0.5 divided by 32. No rubric criterion grades the hardcoding rule, which
`negative_weight_hardcoded_sample_answers` owns.

One stated rule is deliberately never load-bearing. `cost_policy.md` says a rebate never
exceeds the charge it offsets, and both the oracle and the verifier implement the clamp
(`solution/solve.py` and `tests/test_output.py`). No corpus can make it bind: the largest
rebate any corpus publishes is 18 micro units per slot, against a cheapest lane rate of 35
in the shipped roster and 41 for every capacitated lane in the uniform-rate corpus, and both
charge and rebate scale by the same billable slot count. An agent that omits the clamp
therefore scores exactly the same. The clause is kept as a defensive statement about the
settlement arithmetic, not as a graded requirement, and no check or criterion depends on it.

Measured reference figures on the shipped corpus: 115 order rows, 145 decoded rows, 108
orders scored, 62 placed, 49 deferred, 4 rejected, 3505 billable slots, 268040 micro units
charged, 25130 rebated, 24020 capped, 218890 net, 16 lanes used. The admission fixpoint
settles after three passes at congestion indices 450 for Basin, 744 for Harbor, 1030 for
Ridge and 610 for Summit. The placement search visits four sites, records 37 feasible
leaves and displaces 18 orders onto relief capacity. Settled lane cost is 32220 at Basin,
70730 at Harbor, 90345 at Ridge and 74745 at Summit. Both conservation residuals are zero.

## Root cause

**Withheld constants, published controls.** The encoding document is complete about
structure and silent about value. Every one of the twelve transforms is named, its scope
is given, and the constant it turns on is named with its allowed range, but the value is
withheld. The calibration slice publishes twelve control figures over a population that
appears in no rollup. The candidate space totals 331 values; exactly one value per
constant survives its control, so 319 are rejected. The controls are ordered so that each
one is computable only once every constant before it is settled, which makes the recovery
a chain rather than twelve independent searches.

**Sequential decoding.** The count bias means the stored record count exceeds the genuine
count, with the surplus occupying the last logical ordinals as filler that must be dropped
before any running total advances. The block permutation means physical record order is
not logical order. The chained offset, the second differences, the drifting day factor and
the back-reference window each need state from earlier records, and the day factor carries
its running sum across block boundaries. Together they make the population a single
ordered computation.

**Derived identity.** An alias byte carries a rotated directory position. The position
resolves through a merge chain, and a closed chain is governed by the lexicographically
smallest identifier in it. Retirement and first-active days turn some orders into
rejections and others into holds. Identity determines the home site, so it determines
partition membership, so it determines which lane roster applies.

**Half-open revision windows.** A programme revision governs a submission day inside its
effective interval with the lower bound included and the upper bound excluded, the higher
revision winning where the intervals meet. One programme carries a genuine gap between its
two revisions, and a submission landing in that gap is a rejection rather than a fallback
to the earlier revision.

**Coupled admission and placement.** The congestion index depends on the admitted slot
total, the tier widens the ceiling, the ceiling admits more orders. Once admission
settles, placement is a per-site branch and bound over lanes ordered by rate, pruned
against a greedy bound, with the contention rule and the relief lane fixing what happens
when capacity binds.

**Red lines.** No file states the resolution order of the twelve constants, the iteration
that reaches the fixpoint, the search that reaches the optimum, the rounding of the
quantisation, the serialisation shape of any deliverable, or the membership rule of any
partition as a procedure. Every one of those is derivable from the shipped rules, the
global invariants, the calibration controls and the single example rollup, and none of
them is printed.

## Solution shape

1. Read every document under the input directory and build the four directories, the block
   manifest and the three packet populations in memory.
2. Walk the twelve constants in resolution order. For each, evaluate every value in its
   documented domain against the calibration population, compute that constant's control
   figure with the values already settled held fixed, and keep the single value that
   reproduces the published figure.
3. Decode the field population block by block in manifest order, undoing the payload
   rotation, the length shadow, the count bias, the byte-order island, the block
   permutation, the load keystream, the chained offsets, the second differences and the
   day drift, and resolving alias rotation and back references as the cursor advances.
4. Resolve each decoded order to its governing client through the alias rotation, the
   merge chain and the closed-chain rule, rejecting retired clients and holding
   clients whose first active day is later than the submission.
5. Select the governing programme revision on the half-open effective interval, rejecting
   a submission that lands in a gap.
6. Quantise each order's load units to billable slots by the recovered quantisation mode
   at the record's own granularity.
7. Settle admission to its fixpoint by raising congestion tiers monotonically until the
   assignment stops moving, offering orders in descending weight then ascending order
   identifier and holding any order above its client's widened ceiling.
8. For each site, search the lane assignment space by depth-first branch and bound, ordered
   by the contention rule, pruned by the cheapest-eligible suffix bound and the
   capacity-relaxed bound, and take the lexicographically first minimum-cost placement.
9. Settle charges, rebates and per-client budget caps in ascending order identifier, then
   build the region and segment rollups, the summary, the reconciliation report and the
   derivation record, and write all ten artifacts.

## Ordered plan

1. Survey the input directory in full before writing any code, leaving every file under it
   exactly as it was found, and note that the encoding document names twelve constants
   without giving a value. R7 fires if anything under that directory is edited.
2. Enumerate each constant's documented domain and evaluate every value in it against the
   calibration control that resolves it, recording a verdict for each candidate before
   selecting one. This is what R2 grades, and the pairing it produces is what R8 grades.
3. Settle all twelve constants against the calibration population before deriving a single
   figure for the field population, and record the 319 rejected candidate values. This is
   what R1 and R9 grade.
4. Resolve client identity to its governing form before selecting any programme revision.
   This is what R5 grades.
5. Carry every monetary figure as a whole number of micro units end to end, using nothing
   beyond the Python standard library. This is what R4 and R6 grade.
6. Drive admission to its fixpoint and record the pass count and the settled congestion
   index per site in the derivation record. This is what R10 and R11 grade.
7. Search each site's placement space and record the displaced order count and the settled
   per-site lane cost. This is what R12 and R13 grade.
8. Rerun the complete derivation from scratch once the final constant is settled, so every
   report left behind comes from that run. This is what R3 grades. Nothing is deleted:
   `/app/out/derive_report.py` is a declared artifact and emptying that directory would
   destroy it.
9. Report only what the derivation record supports. R14 fires on a closing message that
   claims every control was reproduced while the record shows one that was not.

## Pitfalls

- Lifting the constants from the labelled probe tier. The probe population runs with every
  transform disabled and its own untrapped constants, so the values it appears to endorse
  are wrong for the field population. Fails all four trap checks.
- Decoding records independently or in physical order. Four transforms carry state across
  records and one permutes the block, so the cursor drifts. Fails
  `test_trap_island_permutation_keystream` and `test_trap_chain_delta_drift`.
- Trusting the payload checksum. It is taken over the payload as it travels, after
  rotation, so a wrong rotation step still checksums clean. Fails
  `test_trap_rotation_shadow_count`.
- Keeping the surplus records the stored count advertises. They are filler occupying the
  last logical ordinals and they poison every running total that carries across blocks.
  Fails `test_trap_rotation_shadow_count` and `test_trap_chain_delta_drift`.
- Settling admission in one forward pass. The congestion index and the admission ceiling
  are mutually recursive. Fails `test_instance_summary` and
  `test_generalises_admission_rules`.
- Placing orders greedily onto the cheapest eligible lane. The capacity and family
  constraints interact, so greedy is feasible and more expensive. Fails
  `test_instance_region_rollups` and `test_generalises_lane_rules`.
- Applying earliest-deadline-first at contention. The stated rule keeps the order with the
  larger remaining slack. Fails `test_generalises_placement_contention`.
- Treating the zero-capacity lane as unusable. A zero capacity means unbounded relief
  capacity at the site penalty rate. Fails `test_generalises_lane_rules`.
- Selecting a programme revision before resolving identity. Fails
  `test_generalises_client_identity`.
- Treating the revision interval as closed at its upper bound, or falling back to an
  earlier revision across a gap. Fails `test_generalises_revision_windows`.
- Hardcoding the recovered constants after finding them. Fails
  `negative_weight_hardcoded_sample_answers` and every generalisation test.
- Reading a table header or cell with its padding, or a header with its byte order mark.
  Fails `test_format_byte_order_mark`, `test_format_padded_header_names` and
  `test_format_padded_cells`.
- Matching payload rows to manifest rows by the block_id text rather than its number.
  Fails `test_format_zero_padded_block_ids`.
- Naming a region rollup by the site directory's spelling rather than the fixed region
  name. Fails `test_format_region_name_case`.
- Reading rule values or control figures from whichever document mentions them first
  rather than from the document named for them. Fails `test_format_draft_policy_ignored`
  and `test_format_archived_controls_ignored`.
