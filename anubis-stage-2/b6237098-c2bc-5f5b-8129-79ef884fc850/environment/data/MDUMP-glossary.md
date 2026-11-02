# MDUMP glossary and revision history

## Glossary

- **base value**: signed i32 header field that seeds the running value.
- **running value**: the decoder's signed 32-bit register; every record leaves
  its resolved `value` in it.
- **last delta**: the `delta_raw` of the most recent delta record; repeat
  records multiply it.
- **dictionary**: bounded list (40 entries) of pre-resolution payloads,
  newest at the back, read by dict records with move-to-front.
- **pre-resolution payload**: the field a record actually stores
  (`raw_value`, `delta_raw`, `dict_index`, `repeat_count`), as opposed to its
  resolved `value`.
- **plaintext body**: the body after de-whitening; identical to the wire body
  when the `whitened` flag is clear.
- **offset**: a position in the plaintext body, counting its first byte as 0.
  Decoded records give the offset of their selector byte; body-level error
  objects give the offset of the field that failed.
- **front coding**: storing a long key as a byte prefix shared with the
  previous long key plus a suffix.
- **salt**: header bytes 7..9; the whitening seed.
- **capture**: one MDUMP file, one line of the capture log.

## Revision history

- Revision 1: three record modes (raw, delta, dict), unbounded dictionary
  without move-to-front, header bytes 7..9 reserved as zero, flags byte with
  only bit 0 defined, zlib CRC-32 over the header and body. The legacy decoder
  in this directory was written against revision 1 and was never updated.
- Revision 2: repeat mode; header bytes 7..9 become the salt; body whitening;
  CRC-32C replaces zlib CRC-32; 32-bit running value; padded deltas.
- Revision 3: front-coded keys; big-endian raw payloads; bounded dictionary
  with move-to-front; the full error list with diagnostic fields. All captures
  in the capture log written to this specification are revision 3, and the
  version byte stayed `1` throughout.
- 4.x field builds: write version byte `2` and change the keystream, the
  trailer span, the dictionary and repeat records. Not yet folded into the
  specification; see `MDUMP-rev4-field-notes.md`.
- 5.x field builds: branched from 4.x and write version byte `3`. Their
  rules were never written down; see `MDUMP-rev5-field-notes.md` for what
  the capture team knows.
