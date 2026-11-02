# The residue mill

This directory holds one recorded sieve pass at a number theory group together
with the two rollups of it that survived, and the input of a second pass for
which nothing survived. The mill itself was lost when the group's workstation was
reimaged. Its shape is written down here. Its numbers are not: every constant
each stage applies lived in the mill's configuration and was never recorded
anywhere. They have to be recovered from the recorded pass and its two rollups.

## What ships here

Five files describe the pass.

| File | One row per | Columns |
|---|---|---|
| `moduli.csv` | modulus | `modulus`, `family`, `base`, `offset` |
| `forms.csv` | quadratic form | `form`, `kind`, `parent` |
| `analysts.csv` | analyst | `analyst`, `grade` |
| `lanes.csv` | sieve lane | `lane`, `modulus`, `form`, `sector`, `depth` |
| `samples.jsonl` | metered sample | `seq`, `lane`, `tag`, `analyst`, `action`, `window`, `value`, `span`, `blocks`, `terms` |

`samples.jsonl` is stored in an arbitrary line order. The mill resolves samples
in ascending `seq`, which is a single sieve wide ordering across every lane.

`family` is one of `composite`, `prime`, `power`. `kind` is one of `mixed`,
`quadratic`, `cubic`, `linear`. `grade` is one of `principal`, `senior`,
`junior`, `visiting`. `sector` is one of `plain`, `upper`, `lower`, `split`,
`folded`, `shifted`, `wrapped`. `depth` is 1, 2 or 3. `action` is one of
`sieve`, `probe`, `seed`, `close`, `void`. `window` is one of `dawn`, `dusk`,
`night`.

The `base` column of `moduli.csv` is the lane's opening floor. The `offset`
column stands for the modulus the lane reduces against, with one fixed whole
number offset applied to it.

The `parent` column of `forms.csv` is either empty or the identifier of another
form in the same table. A form named as a parent has an empty `parent` of its
own, so the chain is at most one step long. The `kind` written on a form that
names a parent is the label the group printed on the card, and the kind the mill
charges against is the parent's.

Two more files hold what the mill produced for this pass, in the exact form
`reports.md` describes:

| File | Content |
|---|---|
| `ref_forms.csv` | the per form rollup for this pass |
| `ref_sieve.json` | the sieve wide rollup for this pass |

Neither the per sample residue ledger nor the per lane rollup the mill wrote for
that pass was kept. These two rollups are the whole of the surviving outcome, so
a candidate reading of the constants can only be checked by resolving the pass
and comparing the rollups it produces against these two files. Both are coarse:
`ref_forms.csv` carries one row per form and `ref_sieve.json` one object for the
whole pass, so a wrong constant moves a figure without saying where it came from.

Five further files, `carry_moduli.csv`, `carry_forms.csv`, `carry_analysts.csv`,
`carry_lanes.csv` and `carry_samples.jsonl`, are the input of a second pass in
the same schema, the carry pass. It is longer than the recorded pass, it rests on
its own lanes, moduli, forms and analysts, and no rollup of any kind survives for
it.

One thing about the lane table is worth saying plainly. Of `sector`, the charged
`kind` and the modulus `family`, exactly one value on each of those three
columns leaves the figure alone, and **no lane in this pass sits on more than one
of those three plain values at once**. No single lane therefore shows one
adjustment on its own, and the adjustments have to be fitted together rather
than read off one at a time.

## Carried lane state

Each lane carries eight things while its samples are resolved. Samples on one
lane never touch the state of another lane.

- `floor`: starts at the `base` figure of the lane's modulus.
- `drift`: starts at zero.
- `credit`: starts at zero.
- fault count: starts at zero.
- whether the lane's previous sample was a `sieve`.
- a one shot doubled relief that one of the five actions arms.
- the count of the lane's most recent sample, held for a sample that carries no
  count of its own.
- a bounded trailing record of the lane's most recent resolved samples, holding
  the `tag` each carried and the weight each was given. How many samples that
  record keeps is a missing constant.

## The stage order

Every sample passes through these fourteen stages in this order. No stage in the
chain reports a figure below zero: each one clamps its result at zero before the
next stage runs, except where a stage is said to take an absolute value.

1. **Count.** The sample carries two size columns, `span` and `blocks`. One of
   them governs and the other is left alone, and which one governs depends on
   the value `blocks` carries. When `blocks` is the one that governs it is first
   multiplied by one fixed factor. The result is then multiplied by the sample's
   `terms`, which the column stores with one fixed whole number offset applied
   to it.
2. **Inheritance.** A sample whose two size columns leave stage 1 with nothing
   to divide by takes the count the lane is holding from its own previous
   sample instead. A lane with no previous sample falls back to a fixed figure.
   Whatever the sample ends up resolving against is what the lane then holds.
3. **Offset.** The lane's current floor is taken off the sample's `value`.
4. **Normalisation.** The figure is rescaled against the count with one fixed
   gain, and the division truncates towards zero. The remainder that division
   discards is not thrown away; stage 14 says where it goes.
5. **Reduction.** The figure is reduced against the lane's modulus. The mill
   does not keep the ordinary remainder: it keeps the representative of the
   residue class that is smallest in absolute value, so a remainder in the upper
   half of the range is carried as the negative representative below it. The
   absolute value of that representative is what the rest of the chain works on.
6. **Sector adjustment.** One adjustment keyed on the lane's `sector`. Six of
   the seven sector values carry an adjustment; the seventh leaves the figure
   alone.
7. **Kind adjustment.** One adjustment keyed on the charged `kind`. Three of the
   four kinds carry an adjustment; the fourth leaves the figure alone.
8. **Window adjustment.** One adjustment keyed on the sample's `window`. Two of
   the three windows carry an adjustment; the third leaves the figure alone.
   This stage is skipped altogether on the first sample a lane resolves.
9. **Family adjustment.** One adjustment keyed on the family the lane is charged
   at. Two of the three families carry an adjustment; the third leaves the
   figure alone. A lane whose fault count has reached the figure that seals it
   is charged from that point on at one fixed family whatever its own modulus
   says.
10. **Credit release.** Every sample releases a fixed amount from the lane's
    credit, or the whole credit when less than that amount is left, and the
    amount released is added to the figure. What is released leaves the credit.
11. **Drift relief.** The lane's drift at the moment the sample is resolved is
    taken off the figure. That drift is reported as `drift_before` and the
    result, held at zero when it would fall below zero, is the sample's weight
    so far. When the lane is holding the one shot doubled relief, twice the
    drift comes off instead of the drift, and the marker clears.
12. **Repeat lookup.** When the sample's `tag` also sits in the lane's trailing
    record, the weight of the most recent sample in that record carrying the
    same tag replaces the figure this sample would otherwise be given. A tag
    that has dropped out of the trailing record does nothing. The result is
    reported as `weight`.
13. **Banding and status.** `weight` falls into one of four bands, reported as
    `band`: `peak`, `high`, `base` or `idle`, from the widest figure down. Then
    an ordered ladder decides `status`. The first condition that holds wins and
    the rest are never consulted.
    - a bookkeeping action resolves to `setup`, and two of the five actions are
      bookkeeping actions;
    - an abandoned sample resolves to `voided`, and one action is the
      abandoning one;
    - a bottom band sample resolves to `refused`;
    - a sample whose `drift_before` sits above the tolerance of the analyst's
      `grade` resolves to `flagged`, and each of the four grades has its own
      tolerance;
    - anything left resolves to `kept`.
14. **Carry update.** After the residue line is emitted the lane state moves on,
    after stage 10 has already taken its release out of the credit. One action
    replaces the floor with its own `value`. One action moves the drift it is
    clearing into the credit, up to a ceiling of 80 that the credit never
    passes, and leaves the drift at zero. The abandoning action arms the one shot doubled
    relief. A `sieve` sample adds a drift amount derived from the number of
    divisors its count has; one of the three `depth` values doubles that amount,
    a second `depth` value adds a fixed extra to it, the greatest common divisor
    of the count and the modulus contributes its own residue against a fixed
    small modulus, and a sieve that directly follows another sieve on the same
    lane adds a further fixed extra on top. A `sieve` also adds the remainder
    its own stage 4 division discarded, reduced against a fixed small modulus.
    Drift has a ceiling it never passes. A sample that resolved to `refused`
    adds one fault. The sample's tag and weight then join the trailing record,
    and the oldest entry drops out once the record is full.

## What is missing

The block factor, which size column governs, the terms offset, the fallback
count, the gain, the modulus offset, whether the reduction keeps the least
absolute representative, the six sector adjustments, the three kind adjustments,
the two window adjustments, the two family adjustments, whether the charged kind
is inherited, the family a faulted lane is charged at, the amount each sample
releases from the credit, the three band edges, which two
actions are the bookkeeping pair, which action abandons a sample, which action
arms the doubled relief, the four grade tolerances, the size of the trailing
record, the drift amount per sieve and the divisor rule behind it, the depth
that doubles it, the depth that adds to it, the small modulus the greatest
common divisor is reduced against, the amount a back to back sieve adds, the
small modulus the discarded remainder is reduced against, the drift ceiling,
which action replaces the floor, which action banks the drift, the fault count
that seals a lane, which statuses count into a lane total, the ordering rule of
`forms.csv` and the two tie breaks `reports.md` leaves open are all mill
constants. None of them is written down in this directory. The recorded pass and
its two rollups are the only evidence there is, and some of these constants
leave no mark on either rollup.

Three figures did survive on the group's whiteboard because neither rollup
carries them: the credit ceiling is 80, a lane is `held` when its drift after
its last sample is above 51, and the `top_tag` tie break goes to the lowest
`seq`. `reports.md` repeats the last two where it describes `lanes.json`.
