# MDUMP field notes: version byte 3 captures

Notes from the capture team. Agent builds from the 5.x line write captures
with version byte `3`. The 5.x line was branched from 4.x, so a version 3
capture follows `MDUMP-rev4-field-notes.md` (and through it the container
format specification) except where this file says otherwise. Where this file
and either of the others disagree about a version 3 capture, this file wins.

These notes are thinner than the 4.x ones. The 5.x reference decoder was lost
before anyone wrote its rules down, and nobody decoded a 5.x capture by hand.
What survives is the list below, the version 3 captures in the capture log,
and `MDUMP-rev5-fingerprints.jsonl`.

## What stayed the same

As far as anyone knows: the header layout, the flags, keys and front coding,
raw payloads, the varint rules for key lengths, the 32-bit running value,
repeat records (they resolve as in 4.x), the decoded document shape (with
`"version": 3`), offsets, the fourteen error codes and their precedence, and
the encoder rules, applied with every 5.x change below, including the one
nobody pinned down. A version 3 document encodes back to a version 3 capture.

## What the team is sure changed

- **Trailer.** Same span as 4.x, all sixteen header bytes followed by the
  plaintext body, and still a reflected 32-bit CRC stored as a u32 LE. The
  generator polynomial is new, and it is none of the published CRC-32
  polynomials the team tried. Nobody checked whether the initial register
  and the final XOR stayed as in CRC-32C.
- **Keystream.** Same register, taps, clocking, read-out and zero stand-in as
  4.x, but the register no longer starts from the salt alone: the writer
  folds one other header field into the salt first.
- **Delta payloads.** Same framing as before (seven bits per byte, low group
  first, at most ten bytes, padding allowed), but the value is no longer
  stored as sign-extended two's complement. `delta_pad` still counts the bytes
  beyond the shortest encoding of what is stored.
- **Dictionary.** Changed again. The window is different, and so is the way a
  payload index selects an entry; what is appended after each record is the
  same as in 4.x. `dict_size` in `dict_index_out_of_range` reports the 5.x
  window.

## What the team suspects

Even with the changes above, the logged version 3 captures still come apart
at the record level. There is at least one more change to how a record's
bytes are laid out that nobody pinned down.

## Fingerprints

`MDUMP-rev5-fingerprints.jsonl` holds version 3 captures that the 5.x
reference decoder processed before it was lost, one JSON object per line with
exactly two keys: `hex` (the capture as lowercase hex) and `sha256` (the
fingerprint of that decoder's output for it, as defined in
`MDUMP-decoder-appendix.md`). Some are damaged and some are not. None of them
comes from the capture log.
