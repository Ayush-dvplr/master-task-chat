# VARC1 container format contract

This is the normative description of the VARC1 container written by the retired
Sluicegate batch loader. It is the authority for the format: where any other file
under `/app/data` disagrees with it, this file is right. Everything a decoder and
an encoder need is stated here or in the files this document points to:

- `capture_catalog.jsonl`: the archive of captured segment files, one JSON object
  per line with `capture_id`, `stream_id`, `seq_no`, `revision`, `value_sum` and
  `hex` (the container bytes as lowercase hex). `value_sum` is the loader's control
  total for the capture: the sum of the resolved values of its records, worked out
  when the capture was written. Some captures were damaged in transit.
- `field_layouts.csv`: the canonical field table, columns `canonical_id,name,unit,width`.
  `width` is the raw width the loader picked when it first registered a field. It
  is informational: the wide bit of each raw frame decides how that value is stored.
- `symbol_table.tsv`: per stream field aliases, columns `stream_id`, `canonical_id`, `alias`.
- `revision_map.ini` and `revision_notes.md`: the short key remap for each revision.
- `schema_registry.json`: the defined extension types and the opaque rule.
- `crc_profiles.json`: the trailer checksum algorithm and coverage.
- `capture_alpha.varc`, `capture_beta.varc`, `capture_gamma.varc`: three segment
  files of stream 3, in the order the loader wrote them, and
  `stream3_manifest.json`, the operators' manifest for them.
- `escape_rules.md`: body escaping, the fchk byte and the salvage path.
- `decoder_appendix.md`: the entry points, how several segment files are decoded
  together, what the encoder reads, and every output shape.
- `loader_notes.md`: the operators' notes on how the retired loader behaved.

## Segment file

A `.varc` file is one segment of one stream. Every integer in the header is
little endian. Byte offsets are counted from the start of the file, starting at
zero. The 16 byte header is:

| offset | size | field | meaning |
|--------|------|-------|---------|
| 0 | 5 | magic | the ASCII bytes `VARC1` (hex `56 41 52 43 31`) |
| 5 | 1 | version | the supported version is `2` |
| 6 | 1 | flags | bit 0 is `stream_continues`; bits 1 to 7 are zero |
| 7 | 2 | stream_id | the stream this segment belongs to |
| 9 | 2 | seq_no | the position of this segment inside its run of the stream, counting from zero |
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

A short key is one byte, a field id in the range 0 to 255. A long key is an
unsigned LEB128 length followed by that many UTF-8 bytes, which spell a field
name directly.

The body is escaped (see `escape_rules.md`) and `body_len` counts the escaped
bytes. Unescape exactly `body_len` bytes, then read the value by mode and then the
extensions.

## Value by mode

Values resolve against stream state, which holds the cumulators and the resolved
list described under Terms. In fresh state the resolved list is empty and every
cumulator reads zero.

- raw: the value bytes are a signed little endian integer, 4 bytes when wide is
  set and 2 bytes when it is clear. The resolved value is that integer.
- delta: the value bytes are a signed LEB128 delta. The resolved value is the
  cumulator plus the delta.
- dict: the value byte is one unsigned byte, a backward index into the resolved
  list. Index 0 is the most recent resolved value, index 1 the one before it, and
  so on. The resolved value is the entry at position `len(resolved) - 1 - index`.
- reset: there are no value bytes and there is no resolved value. A reset frame
  empties the resolved list and sets every cumulator to zero.

After a raw, delta or dict frame, append its resolved value to the resolved list.
Raw and delta frames also set the cumulator to their resolved value. No other
frame moves a cumulator, except reset.

## Stream state across segment files

State belongs to a run of segments of one stream, not to a file. Decoding one
segment file on its own starts from fresh state. When several segment files are
decoded together, each segment either continues the state left by an earlier
segment of its stream or starts from fresh state; which of the two applies is set
out for `--stream` in `decoder_appendix.md`. A dict index or a delta in a
continuing segment may refer to a value resolved in an earlier segment.

## Representation memory for delta values

A delta LEB128 may be written in a longer than shortest form: the shortest form
followed by extra groups that only repeat the sign, with the continuation bit set
on every byte but the last. Re-encoding an unmodified record reproduces its delta
in exactly the byte length it was captured in. A new delta record, or one whose
delta was changed, is written in the shortest form. The decode document records
the captured length, and `decoder_appendix.md` says how the encoder reads it.

## Extensions

If has_ext is set, the bytes after the value are a sequence of extensions that
fill the rest of the unescaped body. Each extension is an unsigned LEB128 type, an
unsigned LEB128 length, and that many payload bytes. An extension whose type is
not listed in `schema_registry.json` is opaque: keep its bytes unchanged and in
their original position. When a record is re-encoded, every extension is emitted
again in its original order and position, even when another field of that record
was modified.

## Field names

The decoded field name for a record is worked out like this:

1. Find the canonical field id. For a long key the id is the `canonical_id` whose
   `name` in `field_layouts.csv` equals the key text. For a short key the id is
   the key byte resolved under the revision byte in the header of the segment
   that holds the frame (see `revision_notes.md` and `revision_map.ini`). Every
   segment uses its own revision byte. Revisions 0 to 3 are identity revisions on
   every segment, continuation segments included: there the id equals the key byte.
2. The base name is the `name` for that canonical id in `field_layouts.csv`.
3. If `symbol_table.tsv` has a row for this segment's `stream_id` and this
   canonical id, the field name is that row's `alias`. Otherwise it is the base
   name.

The unit for a record is the `unit` of its canonical id in `field_layouts.csv`. A
long key whose text matches no `name` in `field_layouts.csv` has no canonical id:
its field name is the key text itself, and its unit and canonical id are null. A
reset frame has no field name, no unit and no canonical id.

A raw record whose unit is `count` is read unsigned, in place of the signed reading
under Value by mode: its value bytes are an unsigned little endian integer, so its
`raw_value` and its resolved value run from 0 to 65535 when wide is clear and from
0 to 4294967295 when wide is set.

## Rejection

A whole segment is rejected when the header is bad. The decoder reports a single
JSON error object and nothing else. The checks run in this fixed order and the
first one that fails decides the error:

1. magic wrong: `{"error": "bad_magic"}`. A file shorter than 20 bytes cannot
   hold a header and a trailer and is rejected this way too.
2. version not 2: `{"error": "unsupported_version", "version": V}` where V is the version byte
3. a reserved byte is not zero: `{"error": "reserved_not_zero", "offset": O}` where
   O is the offset of the first non zero reserved byte (14 or 15)
4. rec_count cannot fit: `{"error": "record_count_overflow", "record_count": N}`. A
   segment needs at least 5 bytes per frame, so rec_count is impossible when
   `rec_count * 5` is larger than the bytes between the header and the trailer.
5. trailer checksum wrong: `{"error": "trailer_crc_mismatch", "expected": E, "found": F}`
   where E is the crc the header computes to and F is the trailer value.

When several of these faults are present at once, the earliest one in the list
wins. A segment whose header passes all five checks is not rejected. If its frame
bytes are damaged, read it through the salvage path in `escape_rules.md`.

## Encoding

Encoding is the exact inverse of decoding and must reproduce an unmodified
segment byte for byte: the same header, the same frame bytes, the same escaping,
the same delta byte lengths, the same extensions in place, and a recomputed
trailer checksum. A new record, or a record whose value was changed, is written in
the shortest form. `decoder_appendix.md` lists the document keys the encoder reads.

## Terms

- cumulator: an integer the stream state keeps for each field name. The cumulator
  of a record is the one kept for the record's field name (its `field`, worked out
  under Field names). A field name whose cumulator has not been set reads zero.
- resolved list: the resolved values of the raw, delta and dict frames held in the
  stream state, in the order they were decoded.
- stream state: the cumulators and the resolved list together. Which segment files
  share one stream state is set out for `--stream` in `decoder_appendix.md`.
