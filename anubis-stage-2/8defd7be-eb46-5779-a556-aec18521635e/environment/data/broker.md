# The catalogue probe accounting engine

This directory holds one recorded run of a federated catalogue search broker
together with the two rollups the probe accounting engine produced for it. The
engine itself went with the broker controller when the controller was retired.
Its shape is written down here. Its numbers are not: every constant each stage
applies lived in the controller firmware and was never recorded anywhere. They
have to be recovered from the run and the two rollups.

## What ships here

Five files describe the run.

| File | One row per | Columns |
|---|---|---|
| `pools.csv` | execution pool | `pool`, `mode`, `lag` |
| `indexes.csv` | index | `index`, `layout`, `parent`, `warmup` |
| `analysts.csv` | analyst | `analyst`, `clearance` |
| `partitions.csv` | catalogue partition | `partition`, `pool`, `index`, `plan`, `replica` |
| `lookups.jsonl` | metered lookup | `seq`, `partition`, `query`, `analyst`, `verb`, `phase`, `cursor`, `reach`, `pages`, `rounds` |

`lookups.jsonl` is stored in an arbitrary line order. The engine resolves lookups
in ascending `seq`, which is a single broker wide ordering across every
partition.

`mode` is one of `paired`, `turbo`, `cold`. `layout` is one of `btree`, `sparse`,
`bitmap`, `column`. `clearance` is one of `principal`, `staff`, `rotational`,
`vendor`. `plan` is one of `seek`, `scan`, `merge`, `fanout`, `stream`, `nested`,
`hybrid`. `replica` is 1, 2 or 3. `verb` is one of `fetch`, `refresh`,
`snapshot`, `purge`. `phase` is one of `quiet`, `shoulder`, `peak`.

An index whose `parent` column is filled in is a derived view of that parent. The
engine charges such a partition against the layout of the parent index, and the
layout written on the derived row is the label the catalogue printed on the view
rather than the layout the charge is taken on. An index whose `parent` column is
empty is charged on its own layout.

Two more files hold what the engine produced for this run, in the exact form
`reports.md` describes:

| File | Content |
|---|---|
| `ref_partitions.json` | the per partition rollup for this run |
| `ref_catalog.json` | the catalogue wide rollup for this run |

The per lookup probe ledger the engine wrote that run was not kept. These two
rollups are the whole of the surviving outcome, so a candidate reading of the
constants can only be checked by resolving the run and comparing the rollups it
produces against these two files. Neither rollup carries an index's debt or
credit, so the debt subsystem shows only through what it does to costs,
statuses and dispositions.

One thing about the partition table is worth saying plainly. Of `plan`, the
charged `layout` and the pool's `mode`, exactly one value on each of those three
columns leaves the figure alone, and **no partition in this run sits on more than
one of those three plain values at once**. No single partition therefore shows
one adjustment on its own, and the adjustments have to be fitted together rather
than read off one at a time.

## Carried state

Carried state belongs to the **index** a partition names, not to the partition.
Two partitions naming one index share every figure below, and the lookups of one
move the state the other is resolved against. Each index carries ten things while
the lookups reaching it are resolved.

- `baseline`: starts at the `warmup` figure of that index.
- `debt`: starts at zero.
- `credit`: starts at zero.
- miss count: starts at zero.
- four markers: whether the index has resolved a lookup yet, whether the index's
  previous lookup was a `fetch`, whether the index is holding an unspent waiver,
  and whether the index is holding an unspent doubled relief.
- a lock flag, raised for good once the miss count reaches a fixed figure.
- a trailing record of the last few lookups resolved against the index, each
  remembered as its `query` and the cost that lookup settled on. The record holds
  a fixed number of entries and the oldest is dropped once it is full.

## The stage order

Every lookup passes through these fourteen stages in this order.

1. **Offset.** The index's current baseline is taken off the lookup's `cursor`.
   This result is held at zero when it would fall below zero.
2. **Round normalisation.** The figure is rescaled with one fixed gain against a
   governing count derived from the lookup, and the division truncates towards
   zero. The governing count is built from two of the lookup's three size
   columns: one column decides whether it or one of the other two supplies the
   base figure, the base figure is scaled by a fixed factor when that column
   supplies it, and the remaining column multiplies the result after a fixed
   offset is applied to it. This result is held at zero when it would fall below
   zero.
3. **Plan adjustment.** One adjustment keyed on the partition's `plan`. Six of the
   seven plan values carry an adjustment; the seventh leaves the figure alone.
4. **Layout adjustment.** One adjustment keyed on the charged `layout`. Three of
   the four layouts carry an adjustment; the fourth leaves the figure alone.
5. **Phase adjustment.** One adjustment keyed on the lookup's `phase`. Two of the
   three phases carry an adjustment; the third leaves the figure alone. This
   stage is skipped altogether on the first lookup an index resolves.
6. **Mode adjustment.** One adjustment keyed on the pool's `mode`. Two of the
   three modes carry an adjustment; the third leaves the figure alone.
7. **Credit release.** Every lookup releases a fixed amount from the index's
   credit, or the whole credit when less than that amount is left, and the amount
   released is added to the figure. What is released leaves the credit.
8. **Debt relief.** The index's debt at the moment the lookup is resolved is
   taken off the figure. That debt is reported as `debt_before`. When the index is
   holding an unspent doubled relief the amount taken off is that debt scaled by a
   fixed factor instead, and the doubled relief is spent. The result, held at zero
   when it would fall below zero, becomes the working cost.
9. **Repeat query.** When the lookup's `query` also sits in the index's trailing
   record, the working cost is discarded and the cost remembered against that
   query is taken instead. The most recent entry carrying the query wins.
10. **Waiver.** When the index is holding an unspent waiver the cost is divided by
    a fixed figure, truncating towards zero, and the waiver is spent.
11. **Lock surcharge.** When the index's lock flag is raised the cost is scaled by
    one fixed ratio, truncating towards zero. The result is reported as `cost`.
12. **Banding.** `cost` falls into one of four bands, reported as `band`: `heavy`,
    `warm`, `light` or `idle`, from the widest figure down.
13. **Status.** An ordered ladder decides `status`. The first condition that holds
    wins and the rest are never consulted.
    - a bookkeeping verb resolves to `setup`, and two of the four verbs are
      bookkeeping verbs;
    - a sealing verb resolves to `locked`, and one of the remaining two verbs
      seals;
    - a bottom band lookup resolves to `dropped`;
    - a lookup whose `debt_before` sits above the tolerance of the analyst's
      `clearance` resolves to `flagged`, and each of the four clearances has its
      own tolerance;
    - anything left resolves to `ok`.
14. **Carry update.** After the probe line is emitted the index state moves on,
    after stage 7 has already taken its release out of the credit. A `dropped`
    lookup adds one miss, and the lock flag goes up for good once the miss count
    reaches a fixed figure. A `refresh` lookup replaces the baseline with its own
    `cursor`. A `snapshot` lookup moves the debt it is clearing into the credit, up
    to a ceiling the credit never passes, leaves the debt at zero, and arms a
    waiver for the index's next lookup; that verb is one of the two bookkeeping
    verbs. A `fetch` lookup adds a debt amount derived from its `reach`, and also
    raises the index's baseline by a fixed figure; one of the three `replica`
    values multiplies that debt amount, a second `replica` value adds a fixed extra
    to it, and a fetch that directly follows another fetch on the same index adds a
    further fixed extra on top. Debt has a ceiling it never passes. The sealing
    verb arms a doubled relief for the index's next lookup. Every lookup appends
    its query and its settled cost to the trailing record.

## What is missing

The gain, the governing count column and the factor and the offset that build the
count with it, the six plan adjustments, the three layout adjustments, the two
phase adjustments and the two mode adjustments (the form of each one as well as
its figures, and how the divisions inside them round when a figure has gone
below zero), the amount each lookup releases from
the credit, the credit ceiling, the factor the doubled relief applies, the three
band edges, the divisor the waiver applies, the miss count
that raises the lock flag and the ratio the lock applies, the size of the trailing
record, which two verbs are the bookkeeping pair, which verb seals a partition,
the four clearance tolerances, the debt amount and the replica that multiplies it
and the replica that adds to it, the amount a back to back fetch adds, the debt
ceiling, the figure a fetch adds to the baseline, the miss count that stalls a
partition, the debt figure that holds a partition back, which statuses count into
a partition total, the order the rows of `partitions.json` run in, and both of the
tie breaks in `reports.md` are all firmware constants. None of them is written
down in this directory. The recorded run and the two rollups are the only evidence
there is.
