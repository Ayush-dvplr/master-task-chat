# TRUTH.md - modulus-sieve-replay

Author-side golden trajectory. This file is never shipped to the agent. It
records what the task actually is, what the grader pays for, and the derivation
that answers `instruction.md`.

## Defect

The group's workstation was reimaged, the residue mill went with it, and so did
the per sample residue ledger for the last recorded pass. The bundle ships the
mill's shape and, apart from three figures, none of its numbers. `environment/data/engine.md` names the
five input files, the eight pieces of carried lane state, the fourteen stages in
order and the status ladder. `environment/data/reports.md` names the key set, the
row order and the exact byte form of the four reports. Between them they bound
the search and give away only the three figures no rollup carries. The recorded
pass in `samples.jsonl` and the two surviving rollups beside it are the only evidence
there is.

1. `(focal)` Fifty five mill decisions shape the chain. Three of them leave no
   trace in either surviving rollup and still move a graded report, so the notes
   state them: the credit ceiling is 80, a lane is held when its drift after its
   last sample is above 51, and the `top_tag` tie break goes to the lowest `seq`.
   Of the fifty two left missing, fifty are pinned to a single reading by the
   shipped rollups and graded by both channels. The other two are inert, meaning
   the rival readings grade identically everywhere, so either one is accepted:
   the visiting grade tolerance, which the rollups narrow to zero or one because
   the smallest drift a sieve can add is two and no sample can rest on the figure
   that would separate them, and the `forms.csv` tie break, which never fires
   because no two forms share a `weight_total` on the recorded pass or on any
   generated one. The missing list runs the block factor, which size column
   governs, the terms offset, the fallback count, the gain, the modulus offset,
   the reduction rule, six sector adjustments, three kind adjustments, two window
   adjustments, two family adjustments, whether the charged kind is inherited,
   the family a faulted lane is charged at, the credit release, three band edges,
   the bookkeeping pair, the abandoning action, the action arming the doubled
   relief, four grade tolerances, the trailing record size, the divisor rule
   behind the drift amount, the depth that doubles it, the depth that adds to it,
   the small modulus the greatest common divisor is reduced against, the back to
   back extra, the small modulus the discarded remainder is reduced against, the
   drift ceiling, the floor replacing action, the drift banking action, the
   sealing fault count, the counted status set, the form ordering rule and the
   `forms.csv` and `top_lane` tie breaks.
2. `(focal)` The evidence is aggregated and confounded. No per sample reference
   ships, so a wrong constant surfaces as a wrong total or count in one of the two
   rollups and never points at the sample or the stage that produced it. And no lane
   sits on more than one plain keyed value at once, so no lane isolates one
   adjustment. The three keyed axes have to be fitted together against seven form
   rows and one sieve object rather than read off one lane at a time.
3. `(focal)` The lane state is carried and eight things move at once. Floor,
   drift, credit, fault count, sieve marker, one shot doubled relief, the last
   count and a bounded trailing record all cross from sample to sample on one
   lane. A stateless per sample calculation reproduces nothing past the first
   sample of each lane.
4. `(drift)` `samples.jsonl` ships in an arbitrary line order while the mill
   resolves in ascending `seq` across the whole sieve. Reading the file in the
   order it sits in gives a different carried state and a different ledger.
5. `(drift)` The reduction keeps the least absolute representative of the
   residue class, not the ordinary remainder. Python's own `%` is the obvious
   reading and it is wrong for every figure whose remainder lands in the upper
   half of the range, which is about half of them.
6. `(drift)` The `kind` column of a form that names a parent is the label on the
   card. The charge is taken on the parent's kind, so four of the eight shipped
   forms are misread by anyone who takes the column at face value.
7. `(trap)` A sieve hands the remainder its own normalisation discarded into the
   lane drift, reduced against a small modulus. Nothing about a single sample
   reveals it; only the drift a later sample carries does.
8. `(trap)` An abandoned sample arms a one shot doubling of the next sample's
   drift relief on that lane.
9. `(trap)` A lane whose fault count reaches the sealing figure is charged at a
   fixed modulus family from that point on whatever its own `family` column says.
10. `(trap)` A sample whose two size columns are both empty resolves against the
    count the lane is holding from its own previous sample. A solver that divides
    by zero or by one here drifts every later figure on that lane.
11. `(trap)` The trailing tag record is bounded. A tag returning inside the
    window reuses the weight the earlier sample settled on and a tag returning
    one sample further back takes a fresh one.
12. `(trap)` The drift amount per sieve is built from the number of divisors of
    the count and the greatest common divisor of the count and the modulus, not
    from the count itself. A solver that reads it as a quotient matches on the
    counts whose divisor count happens to agree and diverges everywhere else.
13. `(trap)` `forms.csv` is ordered by descending `weight_total` with ties broken
    by ascending identifier, which no identifier gives away.
14. `(trap)` The `top_lane` tie break runs against the common habit: it goes to
    the smaller identifier among lanes sharing the largest `weight_total`. The
    `top_tag` tie break, the lowest `seq`, leaves no mark on either rollup and is
    stated in `reports.md`.

The reference implementation lives in `solution/solve.py`. It carries the whole
mill as one source string. Before it writes anything it sets twelve lanes aside,
resolves the other eighty, then puts the held back block back and checks that no
kept lane moved and that both surviving rollups over the whole pass still match
`ref_forms.csv` and `ref_sieve.json`. It then builds a three sample input of its
own on which the two rival `top_tag` readings disagree, runs both readings over
it and over the recorded pass, and reads eight keyed differences off pairs of
lanes that share two keyed columns and differ on the third. Only then does it
work `total_drift` out through a separate walk over the samples, write
`/app/out/sieve.py`, run it over `/app/data`, compare both produced rollups
against the shipped reference files byte for byte, stage the carry pass under its
plain names, run the same program over it, and print the twenty closing report
figures.

Out of bounds: nothing asks the agent to change the mill's shape, to add or drop
report keys, to alter the serialization, or to touch anything under `/app/data`.
The shape is given and only the constants are open.

## Load-bearing work

One graded artifact is declared in `task.toml`:

- `/app/out/sieve.py`

The contract that artifact has to meet:

- It is a Python program that runs on the standard library alone.
- It takes the input directory as its first command line argument and the output
  directory as its second.
- It writes `residues.jsonl`, `lanes.json`, `forms.csv` and `sieve.json` into the
  output directory in the byte form `environment/data/reports.md` documents, down
  to the row order of `forms.csv`.
- Every value it reports is worked out from the input files at run time, so the
  same program produces the right answer on sieve passes it has never seen, with
  lanes, moduli, forms and analysts that appear nowhere in `/app/data`, and on a
  pass holding no lane and no sample at all.
- Two runs over one input directory write byte identical files.

The per sample ledger has no shipped reference, but it is graded: the check
`residue_ledger_on_unseen_passes` compares `residues.jsonl` on ten unseen passes
against a reference the verifier derives itself, and every probe reads one field
of it.

The closing report in the final message is the second deliverable. Three of its
figures are measured over the recorded pass: `setup_weight` 8907, `voided_weight`
4555 and `folded_weight` 8211.

The other seventeen are measured over the carry pass, the second pass whose input
ships as the five `carry_` files and for which no rollup of any kind survives:
`carry_total_weight` 311196, `carry_kept_weight` 199151, `carry_flagged_weight`
70955, `carry_refused_weight` 994, `carry_peak_band_weight` 249624,
`carry_high_band_weight` 40030, `carry_base_band_weight` 20394,
`carry_sieve_weight` 123032, `carry_senior_weight` 73934, `carry_night_weight`
73296, `carry_cubic_weight` 162086, `carry_quadratic_weight` 60777,
`carry_prime_weight` 119113, `carry_cleared_weight` 211340, `carry_held_weight`
41298, `carry_sealed_weight` 17468 and `carry_total_drift` 27143.

Every one of the twenty is a sum over a per sample residue ledger or a per lane
rollup, and neither ships for either pass. None is reachable by aggregating a
column of `ref_forms.csv` or `ref_sieve.json`. The seventeen carry figures cannot
be fitted at all: the carry pass has no surviving outcome to fit against, so they
are answerable only by a mill whose constants are already right.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier` and `/tests`,
and hands over to rewardkit 0.2.1, which writes the only reward. `tests/reward.toml`
weights the test channel at 0.5 over its positive total of 96 and the judged
channel at 0.5 over its positive total of 72.

Channel A is `tests/test_output.py`: 35 checks, 32 positive summing to 96 and
three negative summing to minus 11. Every pass the delivered program is driven
over is generated inside the verifier from a seed, and the expected reports are
derived from that corpus by the reference mill in the same file before the
program is launched. The program runs as `nobody` under `setpriv` with a scratch
`HOME` and a 300 second budget.

- Three format checks at weight 1: the four reports with their documented keys,
  the documented byte form, and the empty pass.
- Twenty six probe checks at weight 3. Each builds a small pass aimed at one
  decision and compares only the field that decision moves, so a wrong local
  constant costs its own probe and nothing else among them: the sample `weight`
  for the gain, the count columns, the reduction, each of the six sector
  adjustments, the cubic kind, the quadratic and linear kinds, the parent kind,
  the dusk and night windows, both families, the promoted family, the repeated
  tag, the doubled relief, the inherited and fallback count and the credit
  drawdown; `drift_before` for the greatest common divisor term and for the depth
  rules; `band` for the band edges; `status` for the grade tolerances; the row
  order of `forms.csv` for the form ordering rule; and `verdict`, `weight_total`,
  `peak_weight` and `top_tag` of `lanes.json` for the verdict ladder, the counted
  status set and the `top_tag` tie break.
- Three unseen-pass checks at weight 5 over the same ten generated passes, each
  reading a different report: `residues.jsonl`, `lanes.json`, and the two rollups
  `forms.csv` and `sieve.json`, all byte for byte.
- `negative_hardcoded_recorded_lane_answers` at minus 5 fires when five or more of
  the recorded pass's lane identifiers appear as string literals in the program;
  `negative_third_party_dependency` at minus 3 fires when an import or a dynamic
  import names a module outside `sys.stdlib_module_names`; and
  `negative_nondeterministic_output` at minus 3 fires when four reruns over one
  input directory exit nonzero or write bytes that differ from the first run.

Every check returns a bool and turns any exception on agent output into False.

Channel B is `tests/judge.toml`: twenty nine criteria with a positive total of
72 and a negative total of minus 5. Twenty `final_answer` outcome criteria each
read one closing figure, with the figure written into the criterion text, and
carry `task completion` or `factuality and hallucination`. Seventeen read the
carry pass, which has no surviving rollup of any kind, so they are answerable
only by a mill whose constants are right; the eight at weight 5 are the whole
pass sums the most decisions move. The other three read the recorded pass at
weight 1. Six `trajectory` constraint criteria at weight 1 each quote one
sentence of `instruction.md`: setting a block aside and replaying it, building
an input that separates two rival readings, working one figure out a second
way, comparing both rollups against the shipped references byte for byte,
narrowing a keyed adjustment from a pair of lanes, and running the program over
the staged carry pass. One `state_change` constraint
at minus 5 fires on creating, editing, moving or deleting a file inside
`/app/data`. Two conduct criteria at weight 1 judge the delivered program: the
stages split across named functions, and the recovered constants declared once
as named module level values. No test reads the final message and no criterion
reads a report file, so the two channels grade disjoint surfaces.

Test channel ladder, measured on the test channel alone with every check run
against programs placed at `/app/out/sieve.py`: oracle 1.0000, no-op 0.0000; a
single wrong local decision (one sector, kind, window or family adjustment, a
band edge, a tolerance, the record size, a depth rule, the sealing count, the
counted set, the form order or a tie break) between 0.6875 and 0.9479; a wrong
core decision that every figure passes through (the gain, the terms offset, the
modulus offset or the reduction rule) between 0.0312 and 0.2812. No judged
channel score is claimed for the oracle, since the oracle leaves no trajectory.

## Root cause

**One chain, one carried state, and arithmetic that is genuinely modular.** The
fourteen stages run in a fixed order over a lane whose floor, drift, credit,
fault count, sieve marker, doubled relief, last count and trailing record all
move between samples. The reduction stage keeps the least absolute
representative, so the sign of the ordinary remainder is wrong half the time, and
the drift arithmetic is a divisor count plus a greatest common divisor rather
than a quotient. Neither reading falls out of inspection; both have to be
proposed and tested.

**Aggregation destroys locality.** The surviving evidence is two rollups, one
row per form and one object for the whole pass. Every figure in them is a sum, a
count or a set over the pass as a whole, so a wrong constant anywhere inside the
chain reaches the reader only as a wrong total with nothing to localise it, and
three decisions leave no mark on either file at all, which is why the notes
state them.

**Confounding destroys isolation.** The three keyed columns were laid out so that
no lane carries more than one plain value, so there is no lane whose total is a
function of one adjustment alone. The pairs that share two keyed columns and
differ on the third are the only local evidence there is, and they narrow a
difference rather than pin a value.

**State that reaches sideways and backwards.** A returning tag inside the
trailing record discards the whole chain result, a sieve folds its own discarded
remainder into the drift, an abandoned sample changes what the next sample
subtracts, and enough faults change which family a lane is charged at. Each is
invisible on a lane that never does the thing.

## Solution shape

1. Read `engine.md` and `reports.md` end to end and write down the stage order,
   the carried state and the four report contracts before touching the data.
2. Load the five input files, sort the samples by `seq`, and build the lane,
   modulus, form and analyst lookups with the parent alias resolved.
3. Write the chain as a single pass over the sorted samples, keeping one state
   record per lane with all eight carried pieces.
4. Fit the constants by proposing a full mill, resolving the pass, and comparing
   the two rollups it produces against the shipped references. Use the pairs of
   lanes that share two keyed columns to narrow one adjustment at a time.
5. Emit `residues.jsonl` in ascending `seq` with the ten documented keys, then
   roll the pass up per lane with the thirteen documented keys, per form with the
   five documented columns in the documented order, then the sieve with the eight
   documented keys.
6. Serialize each file exactly as `reports.md` states and write all four into the
   output directory the second command line argument names.

## Ordered plan

1. Read both notes. Grounds the whole conduct tier and stops the agent from
   inventing report keys.
2. Load and sort. Establishes the single sieve wide ordering that drift item 4
   punishes.
3. Build the base chain with placeholder constants and reproduce the shape of
   `ref_forms.csv` first, column set and row count before any value.
4. Fit the keyed axes from pairs of lanes that share two keyed columns and differ
   on the third. This is judged criterion R5.
5. Fit the reduction rule, then the drift subsystem from the lanes whose samples
   are all sieves, then the credit from the lanes that close, then the doubled
   relief from the sample after an abandoned one.
6. Fit the ladder from the counts both rollups carry: the flagged counts pin the
   grade tolerances and the sealed list pins the sealing fault count. Take the
   credit ceiling, the holding figure and the `top_tag` tie break from the notes.
7. Hold a block of lanes back while fitting and replay it once the reading
   settles. This is judged criterion R1.
8. Where two readings survive, build a small input on which they disagree and run
   both. This is judged criterion R2.
9. Write `/app/out/sieve.py`, run it over `/app/data`, and compare both rollups
   against the shipped references byte for byte. This is judged criterion R4.
10. Work one figure out a second time through a separate calculation. This is
    judged criterion R3.
11. Stage the five `carry_` files under their plain names, run the same program
    over that directory, and read the seventeen carry figures off the result.
    This is judged criterion R6.
12. State the twenty figures in the closing message. These are judged criteria
    R7 to R26.

## Pitfalls

- Resolving samples in file order rather than by `seq` gives a different carried
  state on every lane and fails the probes and all three unseen-pass checks.
- Taking the ordinary remainder rather than the least absolute representative
  fails `least_absolute_residue`, most probes and the unseen-pass checks.
- Reading the kind off the lane's own form rather than through the parent fails
  `charged_kind_follows_the_parent_form`.
- Dividing by `span` on every sample ignores the governing count rule and fails
  `governing_count_columns`.
- Multiplying by `terms` as stored rather than by the offset value misprices
  every sample and fails nearly every check.
- Reading the drift step as a quotient of the count rather than as a divisor
  count fails `drift_step_carries_the_common_divisor` and `drift_step_by_depth`.
- Dropping the discarded remainder or the greatest common divisor term fails the
  drift probes and the unseen-pass checks.
- Charging a faulted lane at its own family fails
  `faulted_lane_is_charged_at_the_promoted_family`.
- Taking the drift rather than twice the drift off the sample after an abandoned
  one fails `abandoned_sample_arms_a_doubled_drift_relief`.
- Dividing by zero or by one on a sample with two empty size columns fails
  `absent_count_columns_inherit_the_previous_count`.
- Sorting `forms.csv` by identifier fails `form_rows_carry_the_documented_order`.
- Ignoring the stated holding figure, credit ceiling or `top_tag` tie break fails
  `lane_verdicts_and_counted_totals` or `lane_rollup_on_unseen_passes`.
- Baking the shipped rollups into the program and copying them out scores only
  the format checks, because every other check builds a pass the program has
  never seen.
- Carrying the recorded pass's lane identifiers as string literals fires
  `negative_hardcoded_recorded_lane_answers` at minus 5.
- Reaching for a package outside the standard library fires
  `negative_third_party_dependency` at minus 3.
- Writing anything that varies between two runs over one input fires
  `negative_nondeterministic_output` at minus 3.

## Provenance

```yaml
uuid: 6b2f91ad-3c48-4e7a-8d15-9f3c04e7b621
instance_id: modulus-sieve-replay
task_name: terminal-bench/modulus-sieve-replay
fix_patch_sha256: 5f8fbe5714df66ab1b8fb7eaab48e4ad1a57a97f8f53a4f563c20077de7c95c5
solve_py_sha256: ba35bbec6b5ce5134f0b67a64642fbbf82e95ea957ea49f360ee8e8de1a0da0e
language: python
status: ready
```
