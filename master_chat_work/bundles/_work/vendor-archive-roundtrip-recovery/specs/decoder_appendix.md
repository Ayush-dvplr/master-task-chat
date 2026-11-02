# VARC1 decoder appendix: entry points and output shapes

This file states the exact entry points your programs must support and the exact
shape of every JSON output. Key order and whitespace inside JSON are free; the
key names, value types and the stated numbers are not.

## Entry points

- `python3 /app/decode.py <file.varc>` decodes one segment file with fresh stream
  state and prints one JSON object (the decode document below) to standard out,
  nothing else, and exits 0. A rejected segment prints one error object instead
  and still exits 0.
- `python3 /app/decode.py --stream <manifest.json>` decodes an ordered list of
  segment files that belong to interleaved streams, carrying each stream's state
  across its files. The manifest is `{"segments": [{"path": "..."}, ...]}` in the
  order the segments must be processed. State is kept per `stream_id` across the
  list. It prints `{"segments": [<decode document per input segment, in order>]}`.
- `python3 /app/decode.py --salvage <file.varc>` decodes a segment that may carry
  in band frame damage and prints the salvage document below.
- `python3 /app/encode.py <document.json> <out.varc>` reads one decode document
  and writes the segment bytes it came from, exits 0.

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

Each record carries exactly these keys, plus the one pre resolution key for its
mode:

- `raw_key`: the short key byte, or null for a long key.
- `long_key`: true or false.
- `key_str`: present only when `long_key` is true, the UTF-8 key text.
- `mode`: one of `raw`, `delta`, `dict`, `reset`.
- `field`: the resolved field name, or null for a reset frame.
- `unit`: the field unit from `field_layouts.csv`, or null for a reset frame.
- `canonical_id`: the canonical field id, or null for a reset frame.
- `wide`: true or false for a raw record, null for the other modes.
- `value`: the fully resolved signed integer, or null for a reset frame.
- `ext_present`: true or false.
- `extensions`: a list of `{"type": int, "hex": string}` in original order; the
  hex is lowercase. Empty when `ext_present` is false.
- pre resolution key: raw records carry `raw_value` (int); delta records carry
  `delta_raw` (int) and `delta_raw_len` (the captured LEB128 byte length); dict
  records carry `dict_index` (int). A reset record carries none of these.

## Salvage document

```
{
  "records": [ <record>, ... ],
  "damaged": [ {"from_offset": int, "resync_offset": int, "reason": string}, ... ],
  "header_defect": null
}
```

`records` are the frames that decoded cleanly, in order. `damaged` has one entry
per damaged span. `header_defect` is null for a good header, or the error string
(for example `reserved_not_zero`) when the header is bad.

## Output report files under /app/out

### decoded_examples.jsonl

At least four lines, one JSON object per line, each with exactly `name`, `hex`
and `decoded`. `hex` is the segment bytes as lowercase hex, `decoded` is the
decode document your decoder prints for those bytes. Across the lines the records
must use all four modes, and at least one line must carry an opaque extension and
at least one a long key. These are examples you build yourself. No `name` starts
with `cap`, `rej`, `eval`, `sample` or `field`.

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
  + `unit`, one for each distinct `canonical_id` seen in ok captures, where
  `base_name` is that id's `name` in `field_layouts.csv` and `unit` is its `unit`.

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
{"precedence": ["bad_magic", "unsupported_version", "reserved_not_zero",
                "record_count_overflow", "trailer_crc_mismatch"],
 "cases": {"bad_magic": {...}, "unsupported_version": {...},
           "reserved_not_zero": {...}, "record_count_overflow": {...},
           "trailer_crc_mismatch": {...}, "all_defects": {...}},
 "catalog_errors": {...}}
```

Each case is your decoder's error object for the bytes of your first
`decoded_examples.jsonl` line damaged one way: `bad_magic` sets the first byte to
its value exclusive or `0xFF`; `unsupported_version` sets the version byte to 9;
`reserved_not_zero` sets the byte at offset 14 to 1; `record_count_overflow` sets
`rec_count` to 65535; `trailer_crc_mismatch` sets the last byte to its value
exclusive or `0xFF`; `all_defects` applies all five at once and must report the
highest precedence error. `catalog_errors` is the same map as in
`format_report.json`.
