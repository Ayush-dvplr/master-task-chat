# V2 rate resolution

Inputs: the canonical attempt from V1, and `rate_code_register.csv`.

## R05 the editorial rate

The editorial rate of an asset is the exact rational `rate_num / rate_den`
read from `rate_code_register.csv` against the canonical attempt's
`rate_code`. The `nominal_fps` column in the ingest register is a rounded
label kept for the traffic system's own display. It is never the rate. A
rate of `30000/1001` is not `29.97` and the difference matters at every
conversion.

The `nominal_fps` label is also occasionally inconsistent with the
attempt's own rate code. That is a recording defect in the source system and
is another reason the label is never read as a rate.

## R06 the drop frame flag

Drop frame labelling applies to an attempt when both of these hold:

  the attempt's `tc_mode` is `DF`
  the rate register's `df_allowed` for that rate code is `yes`

An attempt that claims `DF` on a rate code whose `df_allowed` is `no` is
read as non drop. Drop frame is a property of the rate, not of the row that
claims it.

## R40 the separator is not evidence

The registers are keyed at several desks. Some labels of drop frame material
carry a colon before the frame number, and some labels of non drop material
carry a semicolon there. The separator a label was keyed with says nothing
about drop frame: every label of an asset, its `som_tc`, its `eom_tc` and the
`part_som_tc` and `part_eom_tc` of each of its parts, is counted under the
drop frame flag R06 settles for the asset's canonical attempt, and every
`sched_start_tc` is counted under the channel's own drop frame behaviour.
A label is published, where a published column carries it, exactly as the
register records it.

## The timecode base

The `tc_base` column of the rate register is the whole number of frame
numbers a second of timecode carries at that rate code. Timecode fields
count in `tc_base`; durations convert at `rate_num / rate_den`. The two are
not the same number for any rate code whose denominator is `1001`.

## Drop frame arithmetic

At timecode base `b`, drop frame skips `b * 2 / 30` frame numbers at the
start of every minute whose minute number within the day is not a multiple
of ten. For a timecode `hh:mm:ss` with frame `ff` and `m = hh * 60 + mm`,
the whole frame count is

    ((hh * 60 + mm) * 60 + ss) * b + ff - (b * 2 / 30) * (m - m / 10)

with both divisions taken as whole number division.
