# MDUMP error-code reference (revision 3)

A decoder that rejects a file prints exactly one of these objects on stdout and
exits 0. Each object carries exactly the keys shown and no others. All values
are JSON integers except the `error` string. The list is in precedence order:
section 9 of the container format specification says how that order is
applied, and the first condition that holds is the one reported.

| # | error | object | condition |
|---|-------|--------|-----------|
| 1 | `bad_magic` | `{"error": "bad_magic"}` | File shorter than 5 bytes, or bytes 0..4 are not `COREZ`. |
| 2 | `truncated_header` | `{"error": "truncated_header", "length": L}` | Magic is right but the file is shorter than 20 bytes. `L` is the file length in bytes. |
| 3 | `unsupported_version` | `{"error": "unsupported_version", "version": V}` | Byte 15 is not 1, 2 or 3. `V` is the byte found. |
| 4 | `reserved_flag_set` | `{"error": "reserved_flag_set", "flags": F}` | Any of bits 4..7 of byte 10 is set. `F` is the whole flags byte. |
| 5 | `trailer_crc_mismatch` | `{"error": "trailer_crc_mismatch", "stored": S, "computed": C}` | `S` is the u32 LE in the last four bytes; `C` is the CRC-32C the decoder computed over bytes 5..15 and the plaintext body. |
| 6 | `truncated_record` | `{"error": "truncated_record", "record_index": i, "offset": o}` | A field of record `i` (selector, key byte, varint, key bytes, suffix bytes or payload) runs past the end of the body. |
| 7 | `reserved_selector_bits` | `{"error": "reserved_selector_bits", "record_index": i, "selector": B, "offset": o}` | Record `i`'s selector has bit 1, 2, 5 or 7 set, or has bit 4 set on a mode other than raw. `B` is the plaintext selector byte. |
| 8 | `varint_overlong` | `{"error": "varint_overlong", "record_index": i, "offset": o}` | A varint in record `i` still has bit 7 set on its tenth byte. |
| 9 | `noncanonical_varint` | `{"error": "noncanonical_varint", "record_index": i, "offset": o}` | An unsigned key varint in record `i` is not minimal. |
| 10 | `bad_key_prefix` | `{"error": "bad_key_prefix", "record_index": i, "key_prefix": P, "offset": o}` | Front-coded record `i` claims a prefix longer than the previous long key. |
| 11 | `invalid_utf8_key` | `{"error": "invalid_utf8_key", "record_index": i, "offset": o}` | Record `i`'s complete key bytes are not strict UTF-8. |
| 12 | `dict_index_out_of_range` | `{"error": "dict_index_out_of_range", "record_index": i, "dict_index": d, "dict_size": n, "offset": o}` | Dict record `i` has payload index `d` and the dictionary holds `n <= d` entries. `n` never exceeds 40. |
| 13 | `repeat_without_delta` | `{"error": "repeat_without_delta", "record_index": i, "offset": o}` | Repeat record `i` appears before any delta record in the file. |
| 14 | `trailing_bytes` | `{"error": "trailing_bytes", "count": k, "offset": o}` | All `record_count` records parsed and `k > 0` plaintext body bytes remain. `o` is the offset of the first of them. |

Rows 6 to 13 are reported for the first failing record only; records before it
are not reported at all. Within one record the order in which the fields are
read decides which of rows 6 to 13 applies: the selector is checked before the
key is read, the prefix varint is checked against the previous long key before
the suffix length is read, the key is decoded before the payload is read, and
a dict or repeat payload byte is read before its range or delta check is made.

## Offsets

`o` is a position in the plaintext body, counting the first body byte as 0.
For rows 6 to 13 it is the offset of the first byte of the field that was
being read or checked when the problem was found. The fields of a record, in
read order, are: the selector byte; then the short key byte, or the length
varint `L` followed by the key bytes, or the prefix varint `P`, the
suffix-length varint `S` and the suffix bytes; then the payload (the raw
integer, the delta varint, or the dict or repeat byte).

- A field that runs past the end of the body is reported at its first byte,
  even when some of its bytes are present. A missing selector or key byte is
  reported at the body length.
- A varint problem (`varint_overlong`, `noncanonical_varint`, or `P` too long
  for `bad_key_prefix`) is reported at the first byte of that varint.
- The UTF-8 check belongs to the key bytes (the suffix bytes when keys are
  front-coded), so `invalid_utf8_key` is reported where those bytes start,
  even when there are none.
- `dict_index_out_of_range` and `repeat_without_delta` are reported at the
  payload byte.
