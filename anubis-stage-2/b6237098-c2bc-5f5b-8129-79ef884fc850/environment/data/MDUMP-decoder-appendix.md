# MDUMP decoder appendix

Operational notes for the postmortem pipeline: the capture log, the canonical
form used to fingerprint decoder output, and the shape of the four report
files. The container format specification remains the authority on the
format itself.

## Capture log

`MDUMP-capture-log.jsonl` holds field captures pulled from the crash
collector, one JSON object per line with exactly two keys: `capture_id` (a
string such as `cap-00001`) and `hex` (the capture's bytes as lowercase hex).
Lines are in collection order and every `capture_id` is unique. Some captures
were damaged in transit or written by a faulty agent; they must be rejected
with the right error object, not repaired.

## Canonical form and fingerprints

The canonical form of a decoder output (a document or an error object) is its
JSON serialisation with object keys sorted, no whitespace at all, and every
non-ASCII character escaped as `\uXXXX` with lowercase hex (characters above
U+FFFF as a surrogate pair). In Python that is exactly
`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`.
The fingerprint of an output is the lowercase hex SHA-256 of its canonical
form encoded as ASCII.

## Report files

The four files under `/app/out` are each written deterministically, so two
runs produce identical bytes. Each `.json` file holds one JSON object; key
order and whitespace inside it are free.

### decoded_examples.jsonl

Illustrative captures you build yourself, one JSON object per line, at least
four lines, with exactly the keys `name`, `hex` and `decoded`. `hex` is the
capture as lowercase hex and `decoded` is the document your decoder prints for
it; every line must be a capture that decodes to a document. No `name` starts
with `sample_`, `field_`, `eval_` or `cap-`, and no line may reuse a capture
that ships in this directory: none of the complete captures printed in
`MDUMP-worked-examples.md`, none of the captures in `MDUMP-rev4-verified.jsonl`
or `MDUMP-rev5-fingerprints.jsonl`, and none of the captures in the capture
log. Taken together the lines must use all four record modes, and among them
there must be at least one whitened capture, one big-endian capture, one
front-coded capture that contains a long key, one whitened capture with
version byte 2 and one whitened capture with version byte 3.

### format_report.json

| key | value |
|-----|-------|
| `format_tag` | `"MDUMP"` |
| `magic_hex` | `"434f52455a"` |
| `version` | `1` |
| `header_size` | `16` |
| `trailer_size` | `4` |
| `header_order`, `selector`, `flag_bits`, `delta_encoding`, `dict_source`, `dict_direction`, `dict_capacity`, `dict_move_to_front`, `crc_algorithm`, `crc_coverage` | exactly as in the grammar summary, section 10 of the container format specification |
| `visible_example_count` | number of lines in `decoded_examples.jsonl` |
| `visible_record_counts` | each line's `record_count`, in line order |
| `visible_mode_counts` | `{"raw": n, "delta": n, "dict": n, "repeat": n}` summed over every example line |
| `capture_count` | number of lines in the capture log |
| `capture_ok_count` | captures that decode to a document |
| `capture_mode_counts` | the same four-mode tally summed over those documents |
| `capture_flag_counts` | `{"reserved_bit_0": n, "front_coded_keys": n, "big_endian_raw": n, "whitened": n}`: how many of those documents have each flag set |
| `capture_status` | object mapping every `capture_id` in the log to `"ok"` or to the `error` string of its error object |
| `capture_sha256` | object mapping every `capture_id` in the log to the fingerprint of your decoder's output for it |

No other keys.

### roundtrip_report.json

`all_roundtrips_equal` (boolean) and `examples`: one entry per
`decoded_examples.jsonl` line, in the same order, each with `name`,
`input_sha256` (SHA-256 of the line's capture bytes), `rebuilt_sha256`
(SHA-256 of the bytes your encoder writes for the line's `decoded`),
`byte_length` and `roundtrip_equal`. Both digests are lowercase hex. No other
keys, at the top level or inside an entry.

### error_analysis.json

- `precedence`: the fourteen error strings in the order of
  `MDUMP-error-codes.md`.
- `cases`: your decoder's output for the first example line's bytes damaged
  six ways: `bad_magic` (byte 0 XOR `0xFF`), `unsupported_version` (byte 15
  set to 9), `reserved_flag_set` (byte 10 OR `0x80`), `trailer_crc_mismatch`
  (last byte XOR `0xFF`), `all_three_broken` (the `bad_magic`,
  `unsupported_version` and `trailer_crc_mismatch` damage applied together)
  and `trailing_bytes` (one plaintext byte `00` added at the end of the body,
  whitened like the rest of the body when the capture is whitened, with the
  trailer recomputed over the longer plaintext body).
- `capture_errors`: for the capture-log entries that decode to an error
  object, a map from the `error` string to how many entries produced it.

`cases` holds exactly those six keys. No other keys.
