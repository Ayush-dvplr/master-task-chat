# Timecode, clocks and broadcast days

## Ticks and frames

All instants and durations below are exact integers in ticks, where one tick is 1/30000 of a second. A channel with `frame_rate = 30000/1001` has a nominal rate of 30 and a frame lasts 1001 ticks. A channel with `frame_rate = 25` has a nominal rate of 25 and a frame lasts 1200 ticks.

## Labels

A label is `HH:MM:SS<sep>FF` with two digits in each field. Drop frame channels (`timecode = drop`) write `;` as the separator and non drop channels (`timecode = nondrop`) write `:`. A label is valid only with its channel's separator, `HH` at most 23, `MM` and `SS` at most 59 and `FF` below the nominal rate.

The frame count of a label is the number of frames from the label `00:00:00` of the same local date.

On a non drop channel the count is `((HH * 60 + MM) * 60 + SS) * R + FF`, with `R` the nominal rate.

On a drop frame channel the count is `((HH * 60 + MM) * 60 + SS) * 30 + FF - 2 * (T - floor(T / 10))`, where `T = 60 * HH + MM`. Drop frame counting skips the labels with `SS = 00` and `FF` equal to `00` or `01` at the start of every minute whose `MM` is not a multiple of ten, so such a label never names a frame.

The same formula, with hours allowed past 23, converts every `HH:MM` or `HH:MM:SS` bound in the corpus (broadcast day start, daypart bounds) to a frame count with `SS` and `FF` taken as zero where absent. The length of a local date in frames, written `DAY`, is the count of `24:00:00` on that channel.

## Local and UTC instants

The local instant of a label on local date `D` is `D * 86400 * 30000 + count * frame_ticks`, where `D` is the number of days since 1970-01-01. Its UTC instant is the local instant minus `offset * 60 * 30000`, where `offset` is the offset of the channel's zone in force at that UTC instant. Every label in the corpus has exactly one such offset. UTC stamps in the switcher and probe logs convert to ticks as milliseconds since 1970-01-01T00:00:00Z times 30.

The absolute index of a label is `D * DAY + count`. Moving a label by `k` frames moves its absolute index by `k`, crossing local dates where it has to.

## Broadcast days

A broadcast day opens at the label `broadcast_day_start` of `channels.ini`. A label whose absolute index falls on local date `D` with a count below the count of that start label belongs to broadcast date `D - 1`, and its broadcast clock count is `count + DAY`. Every other label belongs to broadcast date `D` with broadcast clock count equal to its count. Daypart bounds and break opening times are compared on this broadcast clock. Recurring commitments, flights, amendments, blackout dates and weekdays all refer to broadcast dates, and the weekday of a broadcast date is the weekday of that calendar date.

## Chain clocks

Chain A is locked to the house reference. Chain B runs a free clock: every label in a chain B as-run line is ahead of the house reference by the chain B offset, in frames, that the probe log reports.

The probe that governs a chain B line is the latest `chain=B` probe whose instant is at or before the line's uncorrected UTC instant. A probe with `lock=OK` sets the offset to its `offset_frames`. A probe with `lock=RELOCK` sets the offset to zero, whatever `offset_frames` it prints, because that figure is the reading taken before the relock. A probe with `lock=STALE` is a repeated old reading and governs nothing. Before the first governing probe the offset is zero. `chain=A` probes are reference self checks and carry nothing.

A chain B line governed by offset `k` has the corrected absolute index `uncorrected index - k` and the corrected UTC instant `uncorrected UTC instant - k * frame_ticks`. Every rule that uses an instant, an absolute index, a broadcast date or a broadcast clock count of a chain B line uses the corrected values.
