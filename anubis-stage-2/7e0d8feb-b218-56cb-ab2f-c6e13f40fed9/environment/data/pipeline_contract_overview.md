# Pipeline contract overview

One transmission day of the channel `ch_regional_one` is conformed in
fourteen stages. Each stage freezes a value that the next stage consumes.
The stages are numbered V1 to V14 and each has its own specification file in
this directory.

| stage | file | what it freezes |
|---|---|---|
| V1 | spec_stage_v1_asset_canonicalisation.md | the canonical ingest attempt per asset |
| V2 | spec_stage_v2_rate_resolution.md | the editorial rate and the drop frame flag |
| V3 | spec_stage_v3_source_span.md | the source frame span of an asset |
| V4 | spec_stage_v4_channel_conversion.md | the channel frame count of a part |
| V5 | spec_stage_v5_segment_assembly.md | the material duration of a slot |
| V6 | spec_stage_v6_splice_conditioning.md | the conditioned position of a break |
| V7 | spec_stage_v7_schedule_placement.md | the placed start of a slot |
| V8 | spec_stage_v8_drift_correction.md | the trims and the fills |
| V9 | spec_stage_v9_avail_derivation.md | the admitted spots and the deferrals |
| V10 | spec_stage_v10_market_substitution.md | the per market break set |
| V11 | spec_stage_v11_settlement.md | the money in minor units |
| V12 | spec_stage_v12_make_good.md | the make good obligations |
| V13 | spec_stage_v13_minutage_compliance.md | the advertising frames per clock hour and the frames left unbilled |
| V14 | spec_stage_v14_reconciliation.md | the deltas and the digest |

The numbers name the stages, not the order they run in. V10 runs before V9,
because V9 admits spots against the per market break set V10 freezes. V13
runs before V11, because V11 bills only the frames V13 leaves inside the
regulatory cap of each clock hour (R41), and V12 then values both the
deferrals and the grains V11 could not bill.

## The channel

The channel transmits at the exact rational rate `30000/1001` frames per
second and publishes drop frame timecode on a timecode base of thirty. The
broadcast day opens at the timecode `06:00:00;00` and runs for one whole day
of channel timecode frames, which is `2589408` frames. A timecode label
earlier than the day start belongs to the following calendar day and
therefore to the end of this broadcast day.

Every published frame count in every artifact is a whole number of channel
frames unless the column name says otherwise.

## The pervasive rule

Every conversion of a frame count or a duration into channel frames is
carried out in exact rational arithmetic, floored to a whole frame, and the
fraction that the floor discarded is held in a named carry scope and added
to the next conversion made inside that same scope. A scope releases a whole
frame as soon as the held fraction reaches one. Nothing is ever rounded to
nearest, and no intermediate value is rounded at all. The scopes are named
in spec_stage_v4_channel_conversion.md and their residuals are published.

## The correction this job is

`prior_conform_register.csv` holds the previous automated computation of
this same transmission day. It is wrong. Stage V14 reports the recomputation
against it. The prior register is never an input to any other stage.
