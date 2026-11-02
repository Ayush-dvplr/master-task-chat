# TRUTH.md - stall-graph-postmortem

## Defect

Nothing in this bundle is broken. What is missing is knowledge. A service fleet
stalled on locks for one incident window, and what survives of that window is a
stall reporter export written in a documented wire shape whose nine numeric
constants the reporter never printed, a thread probe export, a park log export,
five reference tables and six rule documents that state every rule in isolation
and never state the order in which the rules bite. The agent must recover the
nine constants, decode the export under the twelve wire transforms its flag
words declare, resolve every worker through an append only registry, settle a
mutually recursive blame assignment over the lock class budget ladders, and
write ten deliverables that agree with each other and with the shipped
invariants.

1. **(focal)** The nine wire constants are absent from every shipped file. Only
   their candidate lists ship, sixty values across nine lists, together with
   eleven control figures published for a held out calibration population.
   Exactly one assignment reproduces all eleven. A solver that guesses, or that
   fits against the labelled sample, decodes the incident window into silently
   wrong numbers and fails every corpus test. Defeats
   `shipped_window_summary_matches_the_reference` and every
   `generalises_*`.
2. **(focal)** Twelve wire transforms are declared per segment by a flag word.
   Each has a stated forward transform and a one sentence inverse, and each
   inverse is bound to a dedicated weight five test. Three of them force
   strictly sequential decoding inside a segment, one forces it across
   segments, three survive the shipped check totals unchanged. Defeats the
   twelve `trap_*_inverse` tests one for one.
3. **(focal)** The blame settlement is a fixpoint over two mutually dependent
   readings, contention of lock classes and implication of workers, tied
   together by a rung that only ever tightens. The shipped window settles after
   four passes. A single forward sweep is self consistent and wrong. Defeats
   `shipped_policy_audit_matches_the_reference` and every
   `generalises_*`.
4. **(drift)** Every instinct says the newest registry row wins. The registry is
   append only and the rule is the opposite: among the rows live at an event's
   epoch, the row at the **lowest** revision governs. Six of the twenty four
   shipped workers carry overlapping rows. Reading the newest row instead
   changes all nine artifacts, raises the counted set from 161 to 177 and drops
   the retired worker tally from 17 to 0. Defeats
   `shipped_window_summary_matches_the_reference` and
   `generalises_when_registry_presentation_order_inverts`.
5. **(trap)** The declared body line count of a segment is raised above the true
   event count when the count bias flag is set, and the extra lines are ordinary
   well formed body lines that carry no event and are covered by the segment
   check total like any other line. A solver that trusts the declared count
   silently ingests padding as events. Defeats
   `trap_biased_declared_count_inverse`.
6. **(trap)** The slot column is a placeholder when the shadow slot flag is set,
   and the authoritative slot lives in the symbol column suffix. The probe and
   park exports are keyed on the authoritative slot, so a solver reading the
   visible column loses the join and sets the event aside under the wrong
   reason. Defeats `trap_shadow_slot_inverse`.
7. **(trap)** Two registry rules never fire on the shipped window: the alias
   cycle rule and the six row hop limit. Both fire on held out corpora. The
   `cycle` corpus carries an alias pair that closes on itself and leaves 32
   events unresolved against 22 in the unmutated held out window. The
   `nonapplying_rule` corpus lands on the hop limit from both sides, carrying
   one alias chain that resolves on its sixth row and one that would need a
   seventh, and leaves 27 events unresolved; reading the limit as five or as
   seven scores 0.964. Defeats
   `generalises_when_the_registry_carries_a_cycle` and
   `generalises_when_a_dormant_rule_fires`.
8. **(structural, harden round 1)** The partition set is closed: four cell
   reports and two segment reports are always written, and a partition no
   counted event reaches reports zero (`invariants-and-closure.md:53`). A later
   capture brings its own copies of the side tables, and twelve of the
   twenty five held out windows carry a host table that leaves out one or more
   cells, a tenant table that leaves out a segment, or both. A program that
   derives the partition set from the values the side tables carry writes too
   few files and loses each of those twelve windows whole: 60 of 142 points.
9. **(rule, harden round 1)** Padding lines are ordinary body lines: they follow
   their segment's events in logical order in the order they are written
   (`journal-and-wire.md:64-66`) and, like every body line, read and write the
   owner window (`journal-and-wire.md:83`). A program that drops padding before
   the owner window sees it resolves later ring references to the wrong
   owner. The calibration slice keeps ring references and padding in
   different segments, so every control figure reconciles under both
   readings. Measured alone: shipped policy audit plus all thirteen
   `generalises_*` windows, 68 of 142 points.
10. **(rule, harden round 1)** Owner tags follow alias rows at the epoch of the
   event that carries them, and a walk that cannot finish leaves the tag as
   written (`identity-and-registry.md:57-66`). Shipped, calibration and sample
   owners all name themselves, so no shipped figure depends on it; twelve held
   out windows spell some owners by an alias. A program that keeps owner tags
   literal misattributes held counts, implication and every settled figure in
   those windows: 60 of 142 points.

The reference implementation is Python 3 using only the standard library. Two
grading channels score the run. Channel A is `tests/test_output.py`, the
deterministic rewardkit criteria driven by `tests/test.sh`, which grades
artifact and state correctness. Channel B is `tests/judge.toml`, graded by a
judge that sees `instruction.md`, the ATIF trajectory at
`/logs/agent/trajectory.json` and the collected artifacts, and which grades
process and response quality only.

`Out of bounds:` baking the shipped window's totals or the corpus seeds into the
delivered program as literals, caught by
`negative_hardcoded_sample_answers`; keying behaviour on the name of the input
directory, caught by `negative_filename_dependent_behaviour`; reading the
labelled sample answer files at run time, caught by
`negative_reads_supplied_answer_data_at_runtime`; emitting a different post
mortem set on two identical runs, caught by `negative_nondeterministic_output`;
editing anything under `/app/data`, caught by judged criterion R11; claiming a
check, test or re-run passed with no later run showing it, caught by judged
criterion R10.

The nine recovered constants are a different matter and are not out of bounds.
They are constants of the reporter rather than of this capture, the shipped
material says so, and a later capture carries no control slice to re-derive them
from, so the delivered program is expected to hold them and
`negative_hardcoded_sample_answers` deliberately does not look for them.

## Load-bearing work

The graded artifact list is the ten paths `task.toml` declares.

```
/app/out/derive_report.py
/app/out/summary.json
/app/out/policy_audit.json
/app/out/data_quality.json
/app/out/region_North.json
/app/out/region_South.json
/app/out/region_West.json
/app/out/region_East.json
/app/out/segment_commercial.json
/app/out/segment_public.json
```

`derive_report.py` is a reusable standard library program taking an input
directory and an output directory, falling back to `/app/data` and `/app/out`.
It must reach the same answers on windows it has never seen, so no shipped
identifier, count or total may appear in it as a literal. It carries the nine
constants it settled against the calibration slice, because a later capture
ships without that slice, and it runs correctly on an input directory holding
only a journal, a probe export, a park export and the five side tables.

`summary.json` carries the window level roll up: the counted and set aside
counts, the byte totals emitted and logged, the wait, hold and depth totals, the
wait for token total, the within budget count, and the breakdowns by service
cell, by lock class, by tenant segment, by settled rung and by symbol.

`policy_audit.json` carries the settlement itself: one row per lock class with
its entering rung, its settled rung, its budget, whether it is contended,
whether it is quarantined, its owners, its first and last tick and its totals;
and one row per worker with its pool, its waited and held counts, whether it is
implicated, and its totals.

`region_*.json` and `segment_*.json` are the six partition reports. Each names
its own partition and the axis that partition sits on, cross tabulates logged
bytes over both axes and over lock class, and carries the same totals. A
partition no counted event reaches still reports, and reports zero.

`data_quality.json` is the reconciliation and derivation record. It carries the
counted count, the event count, the five reason tallies, the byte conservation
block, the settlement block with the pass count and the quarantined classes, the
candidate search with one entry per constant, and the calibration comparison
with one row per published control figure.

`Out of bounds by design:` the delivered program never reads `/app/data` when
it is pointed elsewhere, never writes outside the output directory it is given,
and never installs a dependency.

## Verification

`tests/test.sh` clears any stale reward file under `/logs/verifier`, locks that
directory to root, restricts `/tests` against unprivileged readers, and then
hands over to the pinned `harbor-rewardkit==0.2.1` with
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. It
writes no reward bytes itself. rewardkit scores each criterion-bearing file at
the top of `tests/` as one input, `test_output` and `judge`, and writes
`reward.json` and `reward-details.json`. `tests/reward.toml` combines the two
into the single `reward`, each channel weighted `0.5` divided by its own
positive total, so a full pass reads 1.0, doing nothing reads 0.0 and the floor
is -1.0. No clamp exists anywhere and none is needed, because neither channel's
negatives outweigh its positives.

Channel A declares 36 checks: 32 positive summing to **142** and four negative
summing to **-18**. Over the test channel alone, an empty container reads 0.000
and the reference reaches 1.000.

Positive checks:

```
post_mortem_set_is_complete                                  1
post_mortem_program_carries_its_promised_fallback_locations  1
shipped_window_summary_matches_the_reference                 3
shipped_policy_audit_matches_the_reference                   3
shipped_cell_reports_match_the_reference                     3
shipped_tenant_segment_reports_match_the_reference           3
shipped_reconciliation_record_matches_the_reference          3
trap_zigzag_wait_inverse                                     5
trap_chained_hold_mask_inverse                               5
trap_stride_interleave_inverse                               5
trap_biased_declared_count_inverse                           5
trap_reversed_origin_pairs_inverse                           5
trap_chained_segment_origin_inverse                          5
trap_sentinel_escape_inverse                                 5
trap_ring_owner_reference_inverse                            5
trap_coarse_spin_escape_inverse                              5
trap_rotated_token_inverse                                   5
trap_registry_alias_worker_inverse                           5
trap_shadow_slot_inverse                                     5
generalises_to_a_fresh_stall_window                          5
generalises_when_budget_ties_move                            5
generalises_when_waits_sit_on_the_budget                     5
generalises_when_registry_presentation_order_inverts         5
generalises_when_a_service_cell_empties                      5
generalises_when_the_registry_carries_a_cycle                5
generalises_when_the_pool_boundary_shifts                    5
generalises_when_a_new_worker_enters                         5
generalises_when_a_dormant_rule_fires                        5
generalises_when_the_partition_count_changes                 5
generalises_when_the_window_scales                           5
generalises_when_the_window_contradicts_the_control_slice    5
generalises_when_every_tag_has_one_live_row                  5
```

Negative checks:

```
negative_hardcoded_sample_answers                           -5
negative_filename_dependent_behaviour                       -5
negative_reads_supplied_answer_data_at_runtime              -5
negative_nondeterministic_output                            -3
```

Channel B is `tests/judge.toml`: eleven criteria, nine positive summing to 27
and two negative summing to -8. R1 through R6 are conduct criteria, one per
output family: each asks whether the agent recomputed a delivered figure
outside its program and compared it with the program's output (cell logged
bytes, settled rungs, cell counted events and waits, segment depths, set aside
tallies, control figures). R7 asks whether the agent reran its program on a
copy of the data whose contents it altered and checked that dependent figures
moved. R8 asks the final response to list the quarantined lock classes by id.
R9 judges the maintainability of the delivered `derive_report.py`. R10 (-5)
prices a claimed pass with no later run showing it; R11 (-3) prices edits under
`/app/data`. `solution/solve.sh` ends with a self-check stage that performs
every conduct act and prints `check R1 ok` through `check R6 ok` and
`check R7 ok`; `WORK/JUDGE_MAP.md` maps each criterion to that line.

**Observable partition.** Channel A asserts: the presence of the ten
deliverables; the two fallback path strings inside the delivered program's
executable text; the byte exact content of `summary.json`, `policy_audit.json`,
the four cell reports and the two segment reports; and within
`data_quality.json` the counted count, the event count, the five reason
tallies, the byte conservation block and the quarantined class list. Channel B
asserts verification acts in the trajectory, one enumeration in the final
response, and code quality. No criterion restates a figure or a method a test
grades.

The rule that combines the two channels into a single reported figure lives in
`tests/reward.toml`, which gives each channel half of the final score by
dividing it by that channel's own positive total.

## Root cause

**Withheld constants, not withheld information.** Every rule the graded corpora
exercise is written out in `environment/data/`. What is withheld is nine
numbers, and the calibration slice pins each of them to exactly one value by
inference. A visible only solve reaches every graded answer.

**Ordering is derived, never stated.** The six rule documents are read in name
order and applied in very nearly the reverse. Which constant can be settled
before which follows only from the data dependencies: the count bias window
before events split from padding, the interleave stride before the wait
differences unwind, the chain mask width after the waits, the hold scale before
any tick, the epoch span after the ticks.

**Append only registries are read backwards by habit.** The revision rule is
the one deliberate inversion of a domain default in this task. It is stated
once, in plain words, in `identity-and-registry.md`, and it is consequential:
all nine artifacts move under the conventional reading.

**Fixpoints are not single passes.** Contention depends on rungs, implication
depends on contention, and rungs depend on implication. The specification
asserts that the loosest assignment meeting the condition is unique and says
nothing about how to reach it.

**Conservation is a measurement, not an assumption.** The window emits twenty
four bytes per spin sample and the park log records what actually landed. The
residual is the difference and it is not zero.

**Red lines.** No `cheat/` directory may exist. The delivered program may not
read the shipped answer files, may not key on the input directory name, may not
carry a shipped total as a literal, and may not write outside the output
directory it is given. Nothing under `/app/data` may be edited.

## Solution shape

1. Read the six rule documents and the five reference tables, and separate the
   three populations under `/app/data` by their name prefixes.
2. Parse the labelled sample journal, which carries no flags, to fix the base
   line shape of the header and the body line and the two check totals.
3. Stage the constant search against the calibration journal and the eleven
   published figures, one constant at a time, in the order the data
   dependencies allow: count bias window, interleave stride, chain mask width,
   depth complement width, owner ring width, coarse spin unit, token rotation
   offset, hold scale, epoch span. Sixty evaluations, one survivor at each
   stage.
4. Decode the incident journal with all twelve inverses live, undoing the count
   bias first, then the stride placement, then the per line transforms, then
   the sequential chains in logical order across the whole file.
5. Advance the intra segment tick cursor from each segment origin by the
   running hold total converted through the hold scale.
6. Resolve each event's worker at that event's own epoch: pick the lowest
   revision live row, follow canonical tags for at most six rows, and set the
   event aside when the chain cycles, overruns or finds no live row.
7. Apply the pool window convention, then join the thread probe and the park
   export on the canonical tag and the authoritative slot, tallying each reason
   that applies.
8. Order the counted events by segment identifier, then authoritative slot,
   and read each worker's reported pool off the first counted event in that
   order.
9. Settle the blame assignment to its loosest stable state, counting the
   passes, and read the quarantined classes and the within budget flags off the
   settled rungs.
10. Build the ten deliverables, reconcile the byte conservation, and write them
    in the style the one shipped example report fixes.

## Ordered plan

1. Inventory `/app/data` and read every document before writing code. Earns
   nothing on its own and is the precondition for every later step.
2. Implement the base line shape against the labelled sample until the sample
   answers reproduce exactly. It is where the check totals prove themselves.
3. Enumerate all sixty candidate values over the calibration journal, evaluate
   each against its bound control figure, and record a verdict and a falsifier
   for every one before selecting.
4. Settle the nine constants before computing any incident figure, and compare
   the reproduced figures against all eleven published ones by a second route.
   Earns R6.
5. Decode the incident window with all twelve inverses and carry the tick
   cursor, carrying padding through the owner window. Earns the twelve trap
   tests and the padding share of every `generalises_*` window.
6. Resolve identity under the lowest revision rule, resolve owner tags through
   alias rows, and apply the window convention. Earns the shipped corpus
   tests and the alias owner windows.
7. Settle the blame assignment and record the pass count. Earns the policy
   audit tests.
8. Write the ten deliverables, then run the whole derivation again from the
   start into a second, empty output directory and confirm the two runs agree
   byte for byte. Keeps `negative_nondeterministic_output` clean. Write all
   four cell reports and both segment reports whatever the side tables carry. The second directory is
   a fresh one: emptying `/app/out` would delete the delivered program with it.
9. Carry every figure in Python integers throughout.
10. Recompute each output family outside the program, rerun on an altered copy
    of the data, and list the quarantined classes in the response. Earns R1
    through R6, R7 and R8.

## Pitfalls

- Trusting the declared body line count. Fails
  `trap_biased_declared_count_inverse`.
- Decoding body lines in the order they appear on the wire. Fails
  `trap_stride_interleave_inverse`.
- Decoding a body line in isolation. Fails `trap_zigzag_wait_inverse`,
  `trap_chained_hold_mask_inverse` and `trap_ring_owner_reference_inverse`.
- Resetting the rolling owner window or the origin chain at a segment boundary.
  Fails `trap_ring_owner_reference_inverse` and
  `trap_chained_segment_origin_inverse`.
- Taking the newest live registry row. Fails
  `shipped_window_summary_matches_the_reference`.
- Taking the first live registry row in file order. Passes on the shipped
  window and fails
  `generalises_when_registry_presentation_order_inverts`.
- Resolving a worker once per segment rather than once per event. The
  `boundary_shift` corpus carries one segment whose events span an epoch
  boundary while its worker is re homed across that same boundary. Fails
  `generalises_when_the_pool_boundary_shifts` and nothing else, measured at
  0.964.
- Reading the visible slot column. Fails `trap_shadow_slot_inverse`.
- Trusting a check total to prove a field. The line total is taken over the
  rotated token and the segment total is taken over every body line including
  padding. Fails `trap_rotated_token_inverse` and
  `trap_biased_declared_count_inverse`.
- Settling the blame assignment in one pass. Fails
  `shipped_policy_audit_matches_the_reference` and every
  `generalises_*`.
- Reading budgets at the entering rung rather than the settled rung. Fails
  `generalises_when_budget_ties_move`.
- Assuming the byte residual is zero. Fails
  `shipped_reconciliation_record_matches_the_reference`.
- Fitting the constants against the labelled sample. The sample carries no
  flags and its answers do not move under any candidate value, so it pins
  nothing. Fails every `generalises_*`.
- Generalising from the labelled sample answers and writing no inverse at all.
  Measured at 0.015.
- Deriving the cell and segment sets from the side table values. Passes on the
  shipped window and loses the twelve held out windows whose tables leave a
  partition out (60 points).
- Dropping padding before the owner window sees it. Fails
  `shipped_policy_audit_matches_the_reference` and every `generalises_*`
  (68 points).
- Keeping owner tags literal. Passes on the shipped window and loses the twelve
  alias owner windows (60 points).
- All three readings at once: 14 of 142.

## Provenance

```yaml
uuid: d7bc935c-6cfd-f8e3-0abc-4a5eb9ebcee4
instance_id: stall-graph-postmortem
task_name: terminal-bench/stall-graph-postmortem
solve_py_sha256: cc0fb50e1f45c44758784e70ec4e8ea90ce91427328b01e15a48e4fcff7fa884
fix_patch_sha256: 88466e001ee03bec9081d3d23316a7af6160516e37990441104ef43959deec3d
language: python3
test_channel_oracle_reward: 1.000
test_channel_nop_reward: 0.000
verification_notes: >-
  Both figures are TEST CHANNEL ONLY, measured by running rewardkit over a copy
  of tests/ whose reward.toml weights test_output alone at 1 divided by its
  positive total of 142. The judged channel is validated against the rewardkit
  0.2.1 schema and never executed for these numbers: oracle and nop make no
  model calls and leave no trajectory, so no judged score exists for either.
```
