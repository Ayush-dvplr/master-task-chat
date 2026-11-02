# TRUTH.md - 8defd7be-eb46-5779-a556-aec18521635e

Author-side golden trajectory. This file is never shipped to the agent. It
records what the task actually is, what the grader pays for, and the derivation
that answers `instruction.md`.

## Defect

The broker controller was retired. The probe accounting engine went with it, and
so did the per lookup probe ledger for the last recorded run. The bundle ships
the engine's shape and none of its numbers. `environment/data/broker.md` names
the five input files, the ten pieces of carried index state, the fourteen stages
in order and the status ladder. It also says that six plan values, three layouts,
two phases and two modes carry an adjustment, whose forms and figures are both
missing, and that neither rollup carries an index's debt or credit.
`environment/data/reports.md` gives the key set and byte form of the three
reports. The recorded run (330 lookups, 79 partitions, 80 indexes) and its two
rollups are the only evidence.

1. `(focal)` About fifty firmware decisions are missing and graded:
   - the gain (1440), and the count rule: `pages * 4` when `pages > 0`, else
     `reach`, times `rounds + 1`;
   - the six plan forms: scan `-7`, merge `*2//3`, fanout `+11`, stream
     `n - n % 9`, nested `*13//11`, hybrid `//3`;
   - the three layout forms: sparse `*8//9`, bitmap `+17`, column `*3//2`;
   - the two phase forms: shoulder `n - n // 6`, peak `+9`;
   - the two mode forms: turbo `*19//17`, cold `min(n, 540) - 13`;
   - floor rounding in all of the keyed divisions;
   - release 36, credit ceiling 90, doubled relief x2, waiver `//2`;
   - lock at 2 misses with ratio 3/2, trailing record of 4 with the newest
     entry winning;
   - bands 320 / 160 / 30;
   - `refresh` + `snapshot` as the bookkeeping verbs and `purge` as the sealing
     verb;
   - tolerances: principal 48, staff 30, rotational 14, vendor 0;
   - debt `reach // 40`, replica 3 doubles it, replica 2 adds 7, a back-to-back
     fetch adds 5, debt ceiling 120;
   - fetch raises the baseline by 4;
   - stalled at 3 misses, held when the debt is above 39;
   - counted statuses {ok, flagged};
   - rows sorted by (`-cost_total`, `partition`);
   - `top_query` takes the later `seq` on a tie, `top_partition` the larger
     identifier.
2. `(focal)` The evidence is aggregated, confounded and now debt-blind. A wrong
   constant moves a total, a count or a disposition and never points at its
   lookup or stage. No partition sits on more than one plain keyed value, and
   the debt that relief subtracts is never shown, so the cost chain and the debt
   subsystem have to be fitted jointly.
3. `(focal)` The non-affine entries hide from a near fit. Taking the plain
   reading of all six of stream, cold, shoulder, nested, turbo and the floor
   rounding reproduces most rows and scores 0.2651 on the test channel. Each
   of them is pinned by at least four lookups in the shipped run.
4. `(drift)` `lookups.jsonl` is shuffled; the engine resolves in ascending `seq`.
5. `(drift)` `snapshot` and `refresh` are resolved against the old state and
   only then move it.
6. `(drift)` A derived view is charged on its parent's layout. Its own row
   carries a decoy layout, and a partition that names the parent itself keeps
   separate state.
7. `(trap)` The `rounds` column is stored one low.
8. `(trap)` A fetch drifts the baseline by 4 after the line is emitted.
9. `(trap)` A purge arms a doubled relief and a snapshot arms a waiver. Both are
   one shot and both occur.
10. `(trap)` Two misses raise a permanent lock (x3/2) and three stall the
    partition; partitions end on 0 to 4 misses.
11. `(trap)` The record holds four entries: queries return at distances 2, 4 and
    5. Two partitions snapshot between returns, so the record holds one query at
    two costs.
12. `(trap)` The row order and both tie breaks run against habit, and each is
    decided by the shipped rollups.

## Load-bearing work

The two rollups are the only oracle, so a candidate is checked by resolving the
whole run and comparing both files. The cheap parts come first: report shape,
bands as counts, misses, baseline drift through `baseline_end`. The cost chain
has to be fitted jointly. Its forms are open-ended, so local search over affine
parameters converges to a basin that is wrong on a scattering of lookups. Fixing
that means attributing the leftover residuals to the right stage: stream
quantisation, cold saturation (cold partitions' peak costs pile up at 527 plus
release), shoulder ceiling, floor rounding on negatives, and the debt terms. The
debt terms are visible only through relief, `flagged` counts and `held`.

## Verification

`tests/test_output.py` rebuilds every graded corpus from a seed inside the test
container, so the verifier never reads `/app/data`. It declares 42 criteria: 39
positive summing to 83 and three negative summing to -11.

- Two weight-1 criteria check the report shape and byte form on an unseen run.
- Twenty-six weight-1 criteria each target one rule on a purpose-built probe,
  among them stream, nested, hybrid, cold (on figures above the ceiling),
  rounding of figures below zero, debt accrual per replica up to the ceiling,
  and both tie breaks with the row order (that probe compares all three files).
  The keyed-adjustment probes run figures off multiples of 2, 3, 6 and 9, and
  the lock probe runs odd costs into the 3/2 ratio, so every form is separated
  from its floor, ceiling and round-half rivals on at least two lookups.
- Eleven weight-5 criteria drive the program over a distinct unseen run and
  compare all three reports byte for byte. Each unseen run is built by the same
  `_populate` routine as the shipped run, with its own seed, names and pool lags,
  so it carries every stressor: values off multiples of 9, cold figures above
  540, negative intermediates under credit, ties both ways, records holding a
  query at distance 4 and 5, derived views on every layout, and shared indexes
  of two and three partitions.

Measured locally, test channel only, normalised by 83 (stub `rewardkit`, not
root):

- oracle: 1.0000; no-op: 0.0000; empty reports: 0.0000;
- seventeen single-rule mutants: 0.2410 to 0.3373. They are stream plain, cold
  uncapped, shoulder floor 5/6, truncating divisions, nested 6/5, turbo 9/8,
  record 3, release 35, credit cap 89, vendor tolerance 1, held 40, `top_query`
  by larger query, per-partition state, per-partition phase exemption, oldest
  record entry, debt divisor 41 and back-to-back +6. Every one fails all eleven
  weight-5 runs. Fourteen also fail at least one probe; vendor tolerance 1,
  held 40 and the per-partition phase exemption have no probe of their own and
  score 0.3373;
- the plain reading of all six awkward entries at once (stream unquantised, cold
  uncapped, shoulder floor 5/6, nested 6/5, turbo 9/8, truncating divisions):
  0.2651.

Identifiability sweep: 171 variants were tried on the shipped rollups. They cover
one step either side of every numeric constant, nearby fractions and the ceiling
of every ratio, rival forms for every keyed entry, floor against truncate, every
verb role assignment, every counted set, both tie breaks in each alternative
reading, row orders, and the per-partition, file-order, no-alias and no-exemption
readings. 168 of them change at least one byte of `ref_partitions.json` or
`ref_catalog.json`. The three inert ones are the offset clamp, the normalisation
clamp and the relief clamp, which `broker.md` states outright. Two added variants
are also inert on the rollups. The first is a clamp at zero after the cold mode
adjustment. Unseen run juliet grades it, and `broker.md` settles it in text,
because only stages 1, 2 and 8 are held at zero and the missing-constants list
asks how the keyed divisions round once a figure has gone below zero. The second
is a snapshot that replaces the credit with the debt it clears rather than adding
that debt to the credit. Unseen runs charlie, echo and golf grade it, and
`broker.md` settles it in text, because stage 14 says the snapshot moves the debt
it is clearing into the credit, up to a ceiling the credit never passes.
The thinnest pinned decisions are each decided by two independent partitions:
band edges, tolerances, record size, held threshold, `top_query` tie, stall
count and oldest-vs-newest record entry. The per-partition phase exemption,
also stated in `broker.md`, rests on one lookup.

The oracle and the verifier implement one engine, so their agreement is not
independence evidence. Solvability rests on the sweep above. The parameterised
sweep engine was also checked byte-equal to the verifier's on the shipped run
and three unseen runs.

## Root cause

The engine lived in controller firmware that was not archived, and the ledger it
wrote was treated as a working file. What survives is the last run's input and
its two rollups.

## Solution shape

One file, `/app/out/broker.py`, standard library only, two positional arguments.
It resolves lookups in ascending `seq` with ten pieces of state per named index
and writes the three documents in the exact serialization `reports.md` gives.
`solution/solve.py` embeds the program as a string, writes it before checking the
fit, then:

1. holds back 11 partitions and replays them;
2. builds a counterfactual where the later lookup carries the smaller query;
3. reads eight keyed differences off pairs that share two keyed columns;
4. narrows the scan offset from 21 candidates to one using a seek and scan pair
   on unshared indexes;
5. walks `total_debt` longhand;
6. byte-compares both rollups and reruns the program for determinism;
7. prints the twenty figures.

## Ordered plan

1. Read `broker.md` and `reports.md`.
2. Write a first `/app/out/broker.py` with neutral constants and keep it on disk
   (R1).
3. Fit the gain and the count from the low-debt partitions. Fit the keyed
   adjustments jointly and keep the residuals per partition.
4. Fit the debt subsystem through relief, `flagged` counts and `held`
   dispositions, since no debt field ships.
5. Attribute the remaining residuals stage by stage until every row matches:
   stream quantisation, cold ceiling, shoulder rounding, floor on negatives.
6. Hold back a block and replay it (R2). Build a disagreeing input for one rival
   pair (R3). Narrow one keyed adjustment from a pair (R4). Recompute one figure
   independently (R5).
7. Run the program over `/app/data`, byte-compare both rollups (R21, R6), rerun
   it for determinism (R7), and report the twenty figures (R9 to R19, R22 to
   R31).

## Pitfalls

- Fitting percentages or affine forms leaves a few lookups per entry wrong, and
  any one of them zeroes all eleven weight-5 runs.
- Truncating instead of flooring is wrong on the planted negative lookups and on
  `rounding_of_figures_below_zero`.
- Treating `cold` as `-13` without the 540 ceiling misses every saturated cold
  lookup.
- Looking for debt in a rollup field: neither rollup carries debt or credit, so
  the debt subsystem shows only through relief, `flagged` counts and `held`.
- Per-partition state is wrong on `PRT-47..49` and `PRT-58/59`. Sharing state
  between a view and its parent is wrong on `PRT-04/05`.
- A per-partition phase exemption fails, because the later members of each
  shared index open on `peak` or `shoulder`.
- Taking the larger query on a `top_query` tie fails the two partitions where
  the later lookup has the smaller query.
- Sorting rows alphabetically, scanning the record oldest first, or resolving in
  file order fails every weight-5 run.
- Shipped identifiers as literals fire `negative_hardcoded_sample_answers`
  (-5). A non-stdlib import fires `negative_third_party_dependency` (-3).
  Varying output fires `negative_nondeterministic_output` (-3): the program is
  rerun twice over its own reports and twice into empty directories.
- Claiming a byte match that the last comparison in the trajectory contradicts
  fires the judged `negative_byte_match_claimed_against_evidence` (-3).

## Provenance

```yaml
uuid: 8defd7be-eb46-5779-a556-aec18521635e
instance_id: 8defd7be-eb46-5779-a556-aec18521635e
task_name: terminal-bench/8defd7be-eb46-5779-a556-aec18521635e
version: 1.0.0
solve_py_sha256: e6b44ff15101e9241ceff2980648b944c6995d6cd2ee650cae7cdc8e20a8f752
language: python
status: ready
```

---

# Task notes

## Task Metadata

- **Category:** `Reverse Engineering`
- **Tags:** ["python", "csv", "json", "rule-recovery", "stdlib"]
- **Expert time:** 10 hours (600.0 min)
- **Junior time:** 30 hours (1800.0 min)
- **Agent timeout:** 1.5 hours (5400s)
- **Deliverable:** `/app/out/broker.py`

## Difficulty explanation

About fifty firmware decisions have to be induced from one run of 330 lookups
and two rollups that never show a per-lookup cost, an index's debt or an index's
credit. Three properties carry the difficulty:

1. The evidence is aggregated and confounded across four keyed axes and a hidden
   debt subsystem.
2. Six keyed entries are deliberately non-affine or awkward (a multiple-of-9
   floor, a ceiling ratio, a capped subtraction, 13/11, 19/17, floor rounding of
   negatives). A near fit is right on most rows and wrong on a handful, which
   the grader scores as wrong.
3. No partition isolates a constant. Every planted witness shares its partition
   with unrelated lookups, so constants are recovered by joint fitting and
   residual attribution rather than read off.

The sweep pins every graded constant on the shipped rollups except two readings
the stage text in `broker.md` decides: the cold entry's behaviour below zero and
whether a snapshot adds the debt it clears to the credit or replaces the credit
with it.

## Solution explanation

See "Solution shape". The oracle performs every fit check the instruction asks
for and prints the twenty figures.

## Verification explanation

The verifier channel is described under "Verification". `tests/judge.toml` has
32 criteria, 70 positive and -8 negative:

- seven trajectory criteria for the fit checks;
- two negative criteria: writing to `/app/data` (-5), and a closing claim of a
  byte match that the last comparison in the trajectory contradicts (-3);
- twenty closing figures, each checked against its value (R9 to R18 at weights
  5, 3 and 1, R22 to R31 at weight 1), and one all-twenty-named criterion. The
  values are listed under "Additional Notes";
- one code-quality criterion and one criterion for driving the program over the
  shipped run.

`tests/reward.toml` weights `test_output` by 0.5/83 and `judge` by 0.5/70.

## Additional Notes

- The full closing report for the shipped run: `total_cost` 78450, `ok_cost`
  30861, `dropped_cost` 67, `setup_cost` 15143, `locked_cost` 8057,
  `heavy_band_cost` 51359, `warm_band_cost` 17751, `light_band_cost` 9164,
  `fetch_cost` 55250, `peak_phase_cost` 20056, `shoulder_phase_cost` 21897,
  `sparse_cost` 18924, `stream_cost` 2742, `turbo_cost` 55290, `cold_cost`
  11303, `shared_index_cost` 4215, `derived_view_cost` 6647, `replica3_cost`
  25532, `total_debt` 13606, `flagged_debt` 5877.
- No figure is a rollup aggregate. Checked mechanically against every value in
  both rollups plus every per-key and per-disposition sum, only `dropped_cost`
  (67) coincides with a single rollup value. That is a coincidence of a small
  number, not a derivation.
- Agent-visible data is flat and holds nine files under `environment/data`.
