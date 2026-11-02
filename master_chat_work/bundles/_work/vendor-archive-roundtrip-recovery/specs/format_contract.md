# VARC1 container format contract

This is the complete and normative description of the VARC1 container written by
the retired Sluicegate batch loader. Everything a decoder and an encoder need is
stated here or in the files this document points to. The reference material
lives in these files under `/app/data`:

- `capture_catalog.jsonl`: the archive of captured segment files, one JSON object
  per line with `capture_id`, `stream_id`, `seq_no`, `revision` and `hex` (the
  container bytes as lowercase hex). Some captures were damaged in transit.
- `field_layouts.csv`: the canonical field table, columns `canonical_id,name,unit,width`.
- `symbol_table.tsv`: per stream field aliases, columns `stream_id`, `canonical_id`, `alias`.
- `revision_map.ini`: the short key remap for each revision.
- `schema_registry.json`: the defined extension types and the opaque rule.
- `crc_profiles.json`: the trailer checksum algorithm and coverage.
- `capture_alpha.varc`, `capture_beta.varc`: the two segment files of one example stream.
- `escape_rules.md`, `revision_notes.md`, `decoder_appendix.md`: the escaping and
  resync rules, the revision remap narrative, and the output report shapes.

The format has fifteen rules the decoder and encoder must apply. They are all
written down in this file and the files above. Read them carefully.

## Segment file

A `.varc` file is one segment of one stream. Every integer in the header is
little endian. Byte offsets are counted from the start of the file, starting at
zero. The 16 byte header is:

| offset | size | field | meaning |
|--------|------|-------|---------|
| 0 | 5 | magic | the ASCII bytes `VARC1` (hex `56 41 52 43 31`) |
| 5 | 1 | version | the supported version is `2` |
| 6 | 1 | flags | bit 0 set means more segments follow in this stream; bits 1 to 7 are zero |
| 7 | 2 | stream_id | the stream this segment belongs to |
| 9 | 2 | seq_no | the position of this segment inside the stream, counting from zero |
| 11 | 2 | rec_count | the number of frames in this segment |
| 13 | 1 | revision | the field id revision in force for this segment |
| 14 | 2 | reserved | both bytes are zero |

After the header come `rec_count` frames. After the last frame come the 4 trailer
bytes.

## Trailer checksum

The trailer is 4 bytes, a crc32 value, little endian. It covers header offsets 5
through 15 inclusive, which is the 11 header bytes after the magic. Frame bytes
are not covered by the trailer. The exact algorithm and coverage are repeated in
`crc_profiles.json`.

## Frame

Each frame is laid out as:

| part | encoding |
|------|----------|
| sync | one byte, always `0xAA` |
| selector | one byte, described below |
| key | a short key or a long key, described below |
| fchk | one byte, the low 8 bits of the sum of the unescaped body bytes |
| body_len | an unsigned LEB128 count of the escaped body bytes that follow |
| body | `body_len` escaped bytes; after unescaping it is the value bytes then the extensions |

The selector byte holds:

- bits 0 and 1: the mode. `0` raw, `1` delta, `2` dict, `3` reset.
- bit 2: wide. For raw mode, set means a 4 byte value, clear means a 2 byte value. Zero for other modes.
- bit 3: long_key. Set means the key is a long key, clear means a short key.
- bit 4: has_ext. Set means the body carries one or more extensions after the value.
- bits 5 to 7: zero.

A short key is one byte, an unsigned field id in the range 0 to 255. A long key is
an unsigned LEB128 length followed by that many UTF-8 bytes, which spell a
canonical field name directly.

The body is escaped (see `escape_rules.md`) and `body_len` counts the escaped
bytes. Unescape exactly `body_len` bytes, then read the value by mode and then the
extensions.

## Value by mode

Values resolve against per stream state: a running cumulator (an integer starting
at zero) and a resolved list (the resolved values of earlier frames of the
stream, in order).

- raw: the value bytes are a signed little endian integer, 4 bytes when wide is
  set and 2 bytes when it is clear. The resolved value is that integer.
- delta: the value bytes are a signed LEB128 delta. The resolved value is the
  current cumulator plus the delta, and that becomes the new cumulator.
- dict: the value byte is one unsigned byte, a backward index into the resolved
  list. Index 0 is the most recent resolved value, index 1 the one before it, and
  so on. The resolved value is the entry at position `len(resolved) - 1 - index`.
- reset: there are no value bytes. A reset frame clears the stream resolved list
  and sets the cumulator back to zero. It contributes no resolved value.

After every frame other than reset, append the resolved value to the stream
resolved list. The cumulator is set to the resolved value for raw, delta and dict
frames.

## Stream state across segment files

Stream state belongs to the stream, not to the file. When segments of one stream
are decoded in order, the cumulator and the resolved list carry over from one
segment into the next. State is cleared only by a reset frame, never by a segment
boundary. A dict index or a delta in a later segment may therefore refer to a
value that was resolved in an earlier segment of the same stream. The entry point
for ordered multi segment decoding is described in `decoder_appendix.md`.

## Representation memory for delta values

A delta LEB128 may be written in a longer than shortest form. When an unmodified
frame is re encoded it must reproduce the delta in exactly the byte length it was
captured in. When a record is new, or when its delta value was changed, the delta
is written in shortest form. Record the captured byte length of each delta so the
encoder can reproduce it.

## Extensions

If has_ext is set, the bytes after the value are a sequence of extensions that
fill the rest of the unescaped body. Each extension is an unsigned LEB128 type, an
unsigned LEB128 length, and that many payload bytes. An extension whose type is
not listed in `schema_registry.json` is opaque: keep its bytes unchanged and in
their original position. When a record is re encoded, every extension is emitted
again in its original order and position, even when another field of that record
was modified.

## Field names

The decoded field name for a record is worked out like this:

1. Find the canonical field id. For a long key the id is the `canonical_id` whose
   `name` in `field_layouts.csv` equals the key text. For a short key the id is the
   remap of the key byte under the segment revision (see `revision_notes.md` and
   `revision_map.ini`); under an identity revision the id equals the key byte.
2. The base name is the `name` for that canonical id in `field_layouts.csv`.
3. If `symbol_table.tsv` has a row for this segment's `stream_id` and this
   canonical id, the field name is that row's `alias`. Otherwise it is the base
   name.

The unit for a record is the `unit` of its canonical id in `field_layouts.csv`. A
reset frame has no field name and no unit.

## Rejection

A whole segment is rejected when the header is bad. The decoder reports a single
JSON error object and nothing else. The checks run in this fixed order and the
first one that fails decides the error:

1. magic wrong: `{"error": "bad_magic"}`
2. version not 2: `{"error": "unsupported_version", "version": V}` where V is the version byte
3. a reserved byte is not zero: `{"error": "reserved_not_zero", "offset": O}` where
   O is the offset of the first non zero reserved byte (14 or 15)
4. rec_count cannot fit: `{"error": "record_count_overflow", "record_count": N}`. A
   segment needs at least 5 bytes per frame, so rec_count is impossible when
   `rec_count * 5` is larger than the bytes between the header and the trailer.
5. trailer checksum wrong: `{"error": "trailer_crc_mismatch", "expected": E, "found": F}`
   where E is the crc the header computes to and F is the trailer value.

When several of these faults are present at once, the earliest one in the list
wins. A frame whose bytes are damaged in the body is a different matter and is
handled by the salvage path in `escape_rules.md`, not by rejection.

## Encoding

Encoding is the exact inverse of decoding and must reproduce an unmodified
segment byte for byte: the same header, the same frame bytes, the same escaping,
the same delta byte lengths, the same extensions in place, and a recomputed
trailer checksum. A new record, or a field whose value was changed, is written in
the canonical shortest form for that field.
