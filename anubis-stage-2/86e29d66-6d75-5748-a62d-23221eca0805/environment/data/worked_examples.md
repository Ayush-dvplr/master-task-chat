# Worked examples

The examples below use a small invented run so that each rule can be followed by hand.
They do not describe the archive that ships with them. Every number here is produced by
the rules in the policy notes and by nothing else.

## The miniature run

One shard `sh-99` at pass index 1, owner `w7`, manifest example count 486, six hold out
rows and no duplicate rows, so the effective size is 480. Ten micro records at
sequences 11 through 20, each with 48 examples, loss scale 1024 and overflow 0. One
phase opening marker for `p1` at sequence 1 carrying width 4 and rate scale 100. One
restart `rs-09` at sequence 17 resuming checkpoint `ck-90`, which was written at
sequence 14 and claims a micro cursor of 4. The restart exception for `rs-09` offers no
width, a rate scale of 100 and `carry_partial` set to false. The accumulation policy
default width is 4 with a minimum of 2 and a maximum of 8. The schedule base is peak
3200, floor 400, warmup 6, decay span 18 and restart period 15.

## Roll back and the cursor

The resume checkpoint was written at sequence 14 and the restart is at sequence 17, so
the records at sequences 15 and 16 are strictly inside that window and are rolled back.
The records at 14 and at 17 are both outside it and survive. Accepted records are those
at sequences 11, 12, 13, 14, 18, 19 and 20, which is seven records and 336 examples.

Rebuilding the cursor for `ck-90` counts accepted records with a sequence of 14 or
below, which is four. The claim is also four, so no drift is raised. Had the claim read
six, one `cursor_drift` event would be counted and nothing else would change.

Coverage is one pair of shard and pass index at effective size 480, so planned examples
is 480 and the coverage gap is 480 minus 336, which is 144.

## The same restart under two widths

With the resolved width 4 the walk goes 11, 12, 13, 14 and closes optimizer step 1 with
four records and 192 examples. The pending window is empty. The next record is at
sequence 18, and before it is counted the restart at sequence 17 fires. Carry resolves
to false, but the pending count is zero, so nothing is discarded. Records 18, 19 and 20
leave a trailing partial of three records and 144 examples. The run has one optimizer
step.

With a profile width override of 3 the walk goes 11, 12, 13 and closes step 1. Record 14
leaves a pending count of 1. The restart then fires before record 18, carry resolves to
false, and that single pending record is discarded: `discarded_partial_records` is 1 and
`discarded_partial_examples` is 48. Records 18, 19 and 20 close step 2 and the trailing
partial is empty. The run has two optimizer steps.

The same archive and the same restart therefore produce a clean boundary at one width
and a split window at another. A ledger that counts windows by dividing the accepted
record count by the width agrees with both answers by accident at width 4 and disagrees
at width 3.

## Rates

Under width 4 the run has one step. Step 1 is inside the warmup because 1 is at most 6,
so the base rate is `ratio(3200 * 1, 6)` which is 533. The phase scale is 100 and no
profile or exception scale applies, so the rate stays 533. The rate list is
`[[1,533]]`.

Under width 3 the run has two steps. Step 2 is still inside the warmup, so its base rate
is `ratio(6400, 6)`. The quotient is 1066 with remainder 4, and twice 4 exceeds 6, so the
rate is 1067. The rate list is `[[1,533],[2,1067]]` and its digest is the first 16
hexadecimal characters of the SHA-256 digest of the canonical text of that list.

## A shared sequence

Suppose a second record also claims sequence 12, identical except that it carries 96
examples. The two canonical forms begin

    {"examples":48,"loss_scale":1024,
    {"examples":96,"loss_scale":1024,

and the first is the smaller text, so the 48 example record stays in the stream and the
96 example record is charged to `duplicate_sequence` with 96 rejected examples. The
total record count is 11 even though only 10 records reach classification.

## An ownership move

Add one move row sending `sh-99` from `w7` to `w8` with effective sequence 16. Records at
sequences 11 through 15 resolve to owner `w7` and are accepted. Records at 16 and above
resolve to `w8`, so a record at sequence 18 that still names `w7` is charged to
`owner_mismatch`. If the run actually handed the shard over, records from 16 onward name
`w8` and nothing is charged. Reading only the manifest owner reverses the picture and
manufactures mismatches that never happened.

## Cadence, selection and averaging

Take the width 3 variant, which ends at optimizer step 2, and a cadence of
`eval_every_steps` 1 with an `eval_cadence_scale` of 2, so probes are expected at steps
2 and nowhere else below 3. A probe at step 2 is matched. A probe at step 5 is an
`orphan_probe` because step 5 is beyond the final step. An expected step with no probe
is a `missing_probe`.

Now take a longer run with four matched probes carrying metrics 52400, 49100, 49100 and 49600 in step
order, a patience of 3 and an average window of 3. The first probe sets the standing
best. The second improves on it and resets the strike counter. The third equals the
standing best, which is not an improvement, so strikes becomes 1. The fourth is worse,
so strikes becomes 2. Two is below the patience of 3, so the walk ends at the last
matched probe and that probe step is the stop step.

Selection takes the matched probe with the lowest metric; the lowest here is 49100 and
two probes hold it, so the smaller step wins, and if the steps were also equal the
smaller probe identifier would win. If that probe names checkpoint `ck-90` and the
checkpoint index shows `ck-90` superseded by `ck-91` and `ck-91` superseded by nothing,
the reported best checkpoint is `ck-91`. If instead `ck-91` were superseded by `ck-90`,
the chain would return to a checkpoint it had already visited, one `supersession_cycle`
event would be counted and the chain would stop there.

Averaging takes the metrics of matched probes up to the stop step whose own checkpoint
is superseded by nothing, keeps the last three in step order, and takes the mean under
the arithmetic policy. With metrics 49100, 49100 and 49600 the sum is 147800 and
`ratio(147800, 3)` has quotient 49266 and remainder 2, and twice 2 exceeds 3, so the
averaged metric is 49267.
