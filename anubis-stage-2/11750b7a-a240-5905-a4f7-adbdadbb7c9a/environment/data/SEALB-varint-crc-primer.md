# SEALB varint and CRC primer

The generated grammar may use either zigzag-uvarint or signed LEB128 for delta
payloads; use the main specification to identify which one applies here.

- Unsigned varints store seven payload bits per byte. The high bit means another
  byte follows.
- Zigzag maps signed deltas to unsigned varints so small negative and positive
  deltas both remain compact: `0 -> 0`, `-1 -> 1`, `1 -> 2`, `-2 -> 3`.
- Signed LEB128 also stores seven bits per byte, but the final byte's sign bit
  extends the value.
- The trailer is a little-endian unsigned CRC32. Compute it over exactly the
  generated coverage region; include or exclude the magic only as specified for
  this bundle.

This primer is generic reference text, not an answer corpus.
