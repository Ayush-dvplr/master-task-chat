# MDUMP field notes: version byte 2 captures

Notes from the capture team. Agent builds from the 4.x line write captures
with version byte `2`. Nobody has written these changes into the container
format specification yet, so this file and `MDUMP-rev4-verified.jsonl` are
what we have. Where this file and the specification disagree about a version
2 capture, this file wins; for version 1 captures nothing here applies. The
5.x line was branched from these builds, so version 3 captures start from
these rules too; see `MDUMP-rev5-field-notes.md`.

## What stayed the same

Everything in the specification holds for version 2 captures except the
points listed under "What changed": the header layout, flags, selector byte,
keys, front coding, payload encodings, varint rules, the 32-bit running value,
the decoded document shape (with `"version": 2`), offsets, the fourteen error
codes and their precedence, and the encoder rules. A version 2 document
encodes back to a version 2 capture with the same changes applied.

## What changed

- **Keystream.** It is the same kind of register, clocked the same way and
  read out the same way, but the tap mask is different and so is the value
  that stands in for a zero salt. First eight keystream bytes, as measured
  on a 4.x agent:
  - salt `0x000001`: `08 e4 01 12 bd e1 c0 d5`
  - salt `0x123456`: `84 a8 a2 61 2e b2 b5 19`
  - salt `0x000000`: `0f c8 a5 07 3f 65 b1 18`
- **Trailer.** Still CRC-32C over header bytes followed by the plaintext
  body, but it no longer starts at the same header byte.
- **Dictionary.** It holds fewer entries than before, and the value appended
  after each record is no longer the record's pre-resolution payload.
  `dict_size` in `dict_index_out_of_range` reports the new window.
- **Repeat records.** They resolve differently; a repeat count of 0 no
  longer leaves the running value unchanged.

## Verified decodings

`MDUMP-rev4-verified.jsonl` holds version 2 captures that triage decoded by
hand and confirmed against the matching crash reports, one JSON object per
line with exactly two keys: `hex` (the capture as lowercase hex) and
`decoded` (the decoder output for it, a document or an error object). None of
them comes from the capture log.
