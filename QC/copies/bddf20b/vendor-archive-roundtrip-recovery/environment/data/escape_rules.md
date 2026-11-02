# VARC1 escaping and salvage

## Escaping inside a frame body

The frame body is escaped so that the sync byte never appears by accident inside
it. The escape byte is `0x1B`. Inside a body, the two byte values `0xAA` (the sync
byte) and `0x1B` (the escape byte) are each written as `0x1B` followed by the byte
exclusive or `0x20`. No other byte is changed. The extensions are part of the body
and are escaped with it.

The `body_len` field counts the escaped bytes. Unescaping is bounded: read exactly
`body_len` bytes and unescape only within that window. An escape byte that is the
last byte of the window has no partner inside it; the frame is damaged. To
unescape: walk the window, and whenever you see
`0x1B` take the next byte in the window, exclusive or it with `0x20`, and emit
that; otherwise emit the byte as is.

## The fchk byte

The one byte `fchk` before `body_len` is the low 8 bits of the sum of the
unescaped body bytes. After unescaping a body, the sum of those raw bytes and `0xFF`
must equal `fchk`. A frame whose fchk does not match is a damaged frame.

## When a frame parses

The frames of a segment lie between the end of the header (offset 16) and the
start of the trailer (the last 4 bytes of the file). A frame parses at an offset
when all of these hold:

- the byte at that offset is `0xAA`;
- the selector has bits 5 to 7 clear, and its wide bit is clear unless the mode is
  raw;
- the key, the fchk byte and `body_len` are complete, and a long key's bytes are
  valid UTF-8;
- the escaped body window ends at or before the start of the trailer, and no
  escape byte in it is left without a partner;
- the fchk byte matches the unescaped body;
- the unescaped body holds exactly the value bytes of its mode (2 or 4 bytes for
  raw by the wide bit, one complete signed LEB128 for delta, one byte for dict,
  none for reset), followed by one or more complete extensions that fill the rest
  of it when has_ext is set, and by nothing when has_ext is clear;
- for a dict frame, the index points inside the resolved list as it stands.

Every frame of an undamaged segment parses.

## Salvage after damage

A segment may carry damaged frames: frames whose bytes were corrupted in transit,
so they no longer parse. The salvage entry point (see `decoder_appendix.md`)
recovers what it can:

- Start at offset 16 with fresh stream state and walk frame by frame up to the
  start of the trailer. `rec_count` is not used to stop the walk.
- When no frame parses at the current offset, that offset is the `from_offset` of
  a damage entry. Scan forward byte by byte from the next offset; the first offset
  where a frame parses is the `resync_offset`, and decoding resumes there.
- If no frame parses before the trailer, the entry's `resync_offset` is the offset
  where the trailer begins and salvage stops.
- Each damaged span is reported once, by one damage entry. The frames inside it
  are lost: they add nothing to the resolved list and move no cumulator.
  Decoding resumes with the stream state exactly as it was just before the
  damaged span.

Salvage does not reject a segment for a bad header. If the header is bad, salvage
still walks the frames and records the header fault separately (the
`header_defect` field in its output), while the ordinary single file decode path
rejects such a segment outright under the rules in `format_contract.md`.
