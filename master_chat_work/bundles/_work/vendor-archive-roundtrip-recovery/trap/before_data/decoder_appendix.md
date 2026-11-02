# VARC1 decoder appendix: entry points and output shapes

This file states the entry points your programs must support, how several segment
files are decoded together, what the encoder reads, and the shape of every JSON
output. Key order and whitespace inside JSON are free; the key names, value types
and the stated numbers are not.

## Entry points

- `python3 /app/decode.py <file.varc>` decodes one segment file from fresh stream
  state and prints one JSON object (the decode document below) to standard out,
  nothing else, and exits 0. A rejected segment prints one error object instead
  and still exits 0.
- `python3 /app/decode.py --stream <manifest.json>` decodes the segment files a
  manifest lists, in the listed order, and prints
  `{"segments": [<decode document per listed entry, in order>]}`. The manifest and
  the way its segments share stream state are set out under Manifest and Runs
  below. Every segment in a manifest has a good header and undamaged frames.
- `python3 /app/decode.py --salvage <file.varc>` decodes one segment file whose
  frames may be damaged, from fresh state, and prints the salvage document below.
- `python3 /app/encode.py <document.json> <out.varc>` reads one decode document,
  writes the segment bytes to `<out.varc>` and exits 0.

## Decode document

```
{
  "magic_ok": true,
  "version": 2,
  "stream_id": 7,
  "seq_no": 0,
  "revision": 3,
  "flags": {"stream_continues": false},
  "record_count": 2,
  "records": [ <record>, ... ]
}
```

Each record carries exactly these keys, plus the one pre-resolution key for its
mode:

- `raw_key`: the short key byte, or null for a long key.
- `long_key`: true or false.
- `key_str`: present only when `long_key` is true, the UTF-8 key text.
- `mode`: one of `raw`, `delta`, `dict`, `reset`.
- `field`: the resolved field name, or null for a reset frame.
- `unit`: the field unit, or null for a reset frame.
- `canonical_id`: the canonical field id, or null for a reset frame.
- `wide`: true or false for a raw record, null for the other modes.
- `value`: the fully resolved integer, or null for a reset frame.
- `ext_present`: true or false.
- `extensions`: a list of `{"type": int, "hex": string}` in original order; the
  hex is lowercase. Empty when `ext_present` is false.
- pre-resolution key: raw records carry `raw_value` (int); delta records carry
  `delta_raw` (int) and `delta_raw_len` (the captured LEB128 byte length); dict
  records carry `dict_index` (int). A reset record carries none of these.

## What the encoder reads

`encode.py` builds the header from `stream_id`, `seq_no`, `revision` and
`flags.stream_continues`, and always writes the magic, version 2 and zero reserved
bytes. It writes one frame per entry of `records`, in order, and sets `rec_count`
to the number of entries. For each record it reads `mode`, `long_key`, `raw_key`
(short key) or `key_str` (long key), `wide`, `ext_present`, `extensions` and the
pre-resolution key of its mode, and it works out `fchk`, `body_len`, the escaping
and the trailer itself. It does not read `magic_ok`, `version`, `record_count`,
`field`, `unit`, `canonical_id` or `value`.

The value bytes of a raw record are `raw_value` written as its low 16 bits when
`wide` is false and its low 32 bits when `wide` is true, little endian.

When `delta_raw_len` is a JSON integer, the delta is written in exactly that many
bytes. Otherwise (null, or any other value) the delta is written in the shortest
form. A decode document always carries the captured length. Whoever changes
`delta_raw`, or adds a delta record, sets that record's `delta_raw_len` to null. A
record added to a document carries the same keys a decoded record of its mode
carries.

Documents handed to the encoder may have been edited by hand. An extension `hex`
is read without regard to letter case, after trimming surrounding whitespace.

## Manifest

A manifest is one JSON object `{"segments": [<entry>, ...]}`. Each entry is an
object with `path`, the absolute path of a segment file, and it may also carry
`stream_continues` and `note`. Operators kept manifests by hand: every text value
in a manifest is trimmed of surrounding whitespace before it is used, and `note`
is free text that changes nothing. The same file may be listed more than once.

## Runs

Within one manifest each `stream_id` has at most one current run. A run holds a
stream state and the `seq_no` of the last segment taken into it. The entries are
handled in order:

- A segment whose stream has no current run starts a new run from fresh stream
  state and is taken into it.
- A segment whose stream has a current run is taken into that run when its
  `seq_no` is larger than the run's last `seq_no`. Otherwise it is a resend: its
  document is decoded from the run's stream state as it stands, and the run, its
  stream state and its last `seq_no` are left exactly as they were.
- A segment taken into a run is decoded from the run's stream state, which it
  updates, and its `seq_no` becomes the run's last `seq_no`. If the segment
  continues the stream, the run stays current; if not, the run ends.

A segment continues the stream when its header has `stream_continues` set. When
its manifest entry carries `stream_continues` as a JSON boolean (`true` or
`false`), that value decides in place of the header bit. Each printed document
still reports the segment's own header, its `flags` included.

## Salvage document

```
{
  "records": [ <record>, ... ],
  "damaged": [ {"from_offset": int, "resync_offset": int, "reason": string}, ... ],
  "header_defect": null
}
```

`records` are the frames that decoded cleanly, in order. `damaged` has one entry
per damaged span, in order; `reason` is a short free text. `header_defect` is
null for a good header, or the error string of the first failing header check (for
example `reserved_not_zero`) when the header is bad; the frames are walked either
way.

## Output report files under /app/out

### decoded_examples.jsonl

At least four lines, one JSON object per line, each with exactly `name`, `hex`
and `decoded`. `hex` is the segment bytes as lowercase hex, `decoded` is the
decode document `decode.py <file>` prints for those bytes. Across the lines the
records must use all four modes, and at least one line must carry an opaque
extension and at least one a long key. These are examples you build yourself. No
`name` starts with `cap`, `rej`, `eval`, `sample` or `field`.

### format_report.json

One object with these keys, all computed over `capture_catalog.jsonl`:

- `format_tag` = "VARC", `magic_hex` = "5641524331", `version` = 2,
  `header_size` = 16, `trailer_size` = 4, `sync_byte` = "aa", `esc_byte` = "1b",
  `crc_coverage` = "header", `crc_covers_offsets` = [5, 15],
  `mode_ids` = {"raw": 0, "delta": 1, "dict": 2, "reset": 3}.
- `catalog_count`: the number of capture lines.
- `catalog_ok_count`: the lines that decode to a document.
- `catalog_error_count`: the lines that decode to an error object.
- `catalog_mode_counts`: {"raw": n, "delta": n, "dict": n, "reset": n} summed over
  every record of every ok capture.
- `stream_count`: the number of distinct `stream_id` values among ok captures.
- `catalog_frame_count`: the total number of records over all ok captures.
- `catalog_errors`: a map from each error string to how many captures produced it.
- `distinct_field_count`: the number of distinct non null `field` names over ok
  captures.
- `field_name_sha256`: the sha256, as lowercase hex, of the UTF-8 text made by
  joining the sorted distinct non null `field` names with a single newline `\n`
  between them (no trailing newline).
- `field_unit_sha256`: the sha256, as lowercase hex, of the UTF-8 text made by
  joining, with a single newline, the sorted distinct strings `base_name` + a tab
  + `unit`, one for each distinct non null `canonical_id` seen in ok captures,
  where `base_name` is that id's `name` in `field_layouts.csv` and `unit` is its
  `unit`.

Each catalog line is decoded on its own, from fresh state.

### roundtrip_report.json

```
{"all_roundtrips_equal": true,
 "examples": [{"name": ..., "input_sha256": ..., "rebuilt_sha256": ...,
               "byte_length": ..., "roundtrip_equal": true}, ...]}
```

One entry per `decoded_examples.jsonl` line in the same order. `input_sha256` is
the sha256 of the line's bytes, `rebuilt_sha256` is the sha256 of the bytes your
encoder writes for its `decoded`, `byte_length` is the input length, and
`roundtrip_equal` is whether the two digests match. `all_roundtrips_equal` is true
only when every entry is equal.

### error_analysis.json

```
{"cases": {"bad_magic": {...}, "unsupported_version": {...},
           "reserved_not_zero": {...}, "record_count_overflow": {...},
           "trailer_crc_mismatch": {...}, "all_defects": {...}}}
```

Each case is your decoder's error object for the bytes of your first
`decoded_examples.jsonl` line damaged one way: `bad_magic` sets the first byte to
its value exclusive or `0xFF`; `unsupported_version` sets the version byte to 9;
`reserved_not_zero` sets the byte at offset 14 to 1; `record_count_overflow` sets
`rec_count` to 65535; `trailer_crc_mismatch` sets the last byte to its value
exclusive or `0xFF`; `all_defects` applies all five at once.
