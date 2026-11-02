# VARC1 escaping and salvage

## Escaping inside a frame body

The frame body is escaped so that the sync byte never appears by accident inside
it. The escape byte is `0x1B`. Inside a body, the two byte values `0xAA` (the sync
byte) and `0x1B` (the escape byte) are each written as `0x1B` followed by the byte
exclusive or `0x20`. No other byte is changed.

The `body_len` field counts the escaped bytes. Unescaping is bounded: read exactly
`body_len` bytes and unescape only within that window. An escape byte as the last
thing in the window pairs with the byte before the window ends, never with a byte
outside it. A body that ends on an escaped `0xAA` sitting right before the next
frame's sync byte must not swallow that sync byte: the window stops at
`body_len`, so the following frame starts cleanly at its own sync. To unescape:
walk the window, and whenever you see `0x1B` take the next byte in the window,
exclusive or it with `0x20`, and emit that; otherwise emit the byte as is.

## The fchk byte

The one byte `fchk` before `body_len` is the low 8 bits of the sum of the
unescaped body bytes. After unescaping a body, the sum of those raw bytes and `0xFF`
must equal `fchk`. A frame whose fchk does not match is a damaged frame.

## Salvage after damage

A segment may carry in band damage: one or more frames whose bytes were corrupted
in transit, so they fail to parse or their fchk does not match. The salvage entry
point (see `decoder_appendix.md`) recovers what it can:

- Walk frames from the first frame onward.
- When a frame fails to parse, or its fchk does not match, record one damage entry
  and resume. The damage entry has `from_offset` (the offset where the bad frame
  began), `resync_offset` (where decoding resumed) and `reason` (a short text).
- Resume only at a sync byte that begins a frame which parses cleanly. Scanning
  forward byte by byte, a `0xAA` is accepted as the resume point only when the
  frame starting there parses and its fchk matches; a `0xAA` that merely appears
  inside damaged bytes is not a resume point.
- Each damaged span is reported once. The frames inside a damaged span are neither
  decoded nor silently skipped: they are accounted for by the single damage entry
  for that span.
- If no later sync begins a clean frame, the last damage entry's `resync_offset`
  is the offset where the trailer begins and salvage stops.

Salvage does not reject a segment for a bad header. If the header is bad, salvage
still walks the frames and records the header fault separately (the
`header_defect` field in its output), while the ordinary single file decode path
rejects such a segment outright under the rules in `format_contract.md`.
