# V3 source span

Inputs: the canonical attempt from V1, and the rate resolved at V2.

## R08 the span

The source frame span of an asset is the frame count of its `eom_tc` less
the frame count of its `som_tc`, both taken at the asset's timecode base
under the asset's drop frame flag. The end of media timecode is exclusive:
an asset whose start and end labels are equal spans zero frames.

When the end frame count is less than the start frame count the asset wraps
the timecode day. One whole timecode day is added to the difference. A
timecode day at base `b` is `b * 86400` frames when the asset is non drop,
and `b * 86400 - (b * 2 / 30) * 1296` frames when it is drop frame.

A negative span is never published. Every span is zero or greater.

## Published

The span is published as `source_frames` in `asset_register.csv`, together
with `channel_frames_exact`, which is the exact rational count of channel
frames the span occupies rendered to ten decimal places. The exact count is
published rather than a whole number because no carry scope is open at the
asset level; the whole numbers appear at V4.
