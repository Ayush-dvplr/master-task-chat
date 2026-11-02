# POLYP decoder appendix

This appendix restates the decoder-facing invariants from the container format
specification without adding any corpus answers.

- Decode the 16-byte header before reading records. The magic is
  `4e 55 4d 50 4b`; the supported version is `1`.
- The generated header field order is part of this bundle's grammar and must be
  followed exactly as listed in the main format specification.
- Record selectors carry both mode bits and flags. The generated selector layout
  is summarized by `{"crc_coverage": "header_records", "delta_encoding": "zigzag_uvarint", "dictionary": {"direction": "backward", "source": "resolved_values"}, "header_order": ["base_value", "record_count", "flags", "version", "reserved"], "selector": {"long_key_bit": 7, "mode_bits": [2, 5], "mode_ids": {"delta": 1, "dict": 2, "raw": 0}, "wide_bit": 0}}`.
- `value` is the resolved signed integer after applying raw, delta, or
  dictionary semantics. Retain the pre-resolution payload (`raw_value`,
  `delta_raw`, or `dict_index`) so encoding can be byte-exact.
- Rejection precedence is fixed: bad magic first, then unsupported version, then
  trailer CRC mismatch, then malformed/truncated record data.

## Capture log

`POLYP-capture-log.jsonl` holds field captures from the producer, one JSON
object per line with `capture_id` and `hex` (the container's bytes as lowercase hex).
Some captures were damaged in transit. Decode every one with your decoder; two reports
below summarise the log.

## Report artifacts

The four files under `/app/out` describe containers you build yourself. Each `.json`
file is one JSON object; key order and whitespace are free.

- `decoded_examples.jsonl`: one JSON object per line with exactly the keys `name`,
  `hex` and `decoded`, at least three lines, and the lines together use all three
  record modes. `hex` is the container's bytes as lowercase hex, `decoded` is the
  document your decoder prints for those bytes, and no `name` starts with `sample_`,
  `field_` or `eval_`.
- `format_report.json`: `format_tag`, `magic_hex` (lowercase hex), `version`,
  `header_size`, `trailer_size`, `header_order`, `selector`, `delta_encoding`,
  `dict_source`, `dict_direction` and `crc_coverage`, valued exactly as in the grammar
  summary above (the summary's dictionary `source` and `direction` become `dict_source`
  and `dict_direction`), plus `visible_example_count` (the number of lines in
  `decoded_examples.jsonl`), `visible_record_counts` (each line's record count, in line
  order) and `visible_mode_counts` (`{"raw": n, "delta": n, "dict": n}` summed over
  every line), plus `capture_count` (lines in the capture log), `capture_ok_count`
  (captures that decode to a document rather than an error object) and
  `capture_mode_counts` (the same three-mode tally summed over those documents).
- `roundtrip_report.json`: `all_roundtrips_equal` and `examples`, one entry per
  `decoded_examples.jsonl` line in the same order, each with `name`, `input_sha256`
  (sha256 of the line's bytes), `rebuilt_sha256` (sha256 of the bytes your encoder
  writes for `decoded`), `byte_length` and `roundtrip_equal`.
- `error_analysis.json`: `precedence`, the list
  `["bad_magic", "unsupported_version", "trailer_crc_mismatch"]`, and `cases`, your
  decoder's output for the first example's bytes damaged four ways: `bad_magic` (first
  byte XOR `0xFF`), `unsupported_version` (version byte set to `9`),
  `trailer_crc_mismatch` (last byte XOR `0xFF`) and `all_three_broken` (all three at
  once), plus `capture_errors`: for the captures in the capture log that decode to an
  error object, a map from that object's `error` value to how many captures produced it.

This file is reference material only. It does not contain sample, field, or eval
capture answers.
