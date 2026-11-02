# VARC Container Format, v1.0

Complete specification of the VARC binary container as produced by
PIPE-8 staging service. This document fully defines the header, every record mode,
the cumulator and dictionary state, the error paths, and the trailer checksum -
everything a decoder and a byte-exact encoder need. All multi-byte integers are
little-endian. Offsets are byte offsets from the start of the file unless noted
otherwise.

## §1. File layout

A VARC container is exactly:

```
+-----------+-------------+---------+
|  header   |    body     | trailer |
| (16 bytes)| (variable)  |(4 bytes)|
+-----------+-------------+---------+
```

The body holds `record_count` records back-to-back. The trailer binds the
header and body together.

## §2. Header table

| offset  | width   | field         | notes |
|---------|---------|---------------|-------|
| 0..4    | 5 bytes | magic         | ASCII bytes `50 49 50 45 31`. Any other value is `bad_magic` (§7). |
| 5..6    | u16 LE  | record_count  | Number of records that follow in the body. |
| 7..9    | 3 bytes | reserved      | Must be `0x00 0x00 0x00`. The trailer (§8) binds these bytes when the bundle uses full-prefix CRC coverage. |
| 10      | u8      | version       | Must be `5`. Any other value is `unsupported_version` (§7). |
| 11      | u8      | flags         | Reserved flag byte. Bit 0 has meaning; bits 1..7 must be `0`. See §6. |
| 12..15  | i32 LE  | base_value    | Signed initial value used by some record modes. See §4. |

## §3. Records - raw mode

Every record starts with a **1-byte selector** followed by a key and a payload.
The selector packs three fields:

- bits `2` and `3` carry the payload **mode** number (`1` = raw, `2` = delta, `0` = dictionary). The lower listed bit contributes value 1 and the higher listed bit contributes value 2.
- bit `1` carries the `WIDE_VALUE` flag (raw mode only): `1` = 32-bit payload, `0` = 16-bit.
- bit `7` carries the `LONG_KEY` flag: `1` = varint-length UTF-8 key, `0` = 1-byte key.
- bits `0, 4, 5, 6` must be `0`.

For **raw mode** (`mode == 1`) the record layout is:

| width                        | field       | notes |
|------------------------------|-------------|-------|
| u8                           | selector    | bits: `mode=1`, `WIDE_VALUE`, `LONG_KEY`. |
| 1 byte OR uvarint+UTF-8      | key         | one u8 when `LONG_KEY=0`; a uvarint length followed by that many UTF-8 bytes when `LONG_KEY=1`. |
| i32 LE (`WIDE_VALUE=1`) OR i16 LE (`WIDE_VALUE=0`) | value | signed. |

The decoded JSON object for a raw record is:

```json
{"key": <int or str>, "mode": "raw", "wide_value": true, "long_key": false,
 "raw_value": <int>, "value": <int>}
```

In raw mode `value` equals `raw_value`: the record carries its value literally
and installs it as the new running value (§6). Raw records exercise the header,
the selector byte layout, key encoding, and payload width on their own; §4-§6
define the two modes that build on the running value and the dictionary.

## §4. Delta mode

A record whose selector mode number is `2` is a **delta** record. Its payload is one signed integer delta.

The signed delta is written as signed LEB128: 7 data bits per byte, least-significant group first, high bit set on every byte except the last, and the payload is sign-extended from the final byte. For example a delta of `-3` is the single byte `7d`.

The delta updates the running value described in §6 (`running = running + delta`); the new running value is the record's resolved `value`. The raw delta, before it is applied, is reported as `delta_raw`.

## §5. Dictionary mode

A record whose selector mode number is `0` is a **dictionary** record. Its payload is one unsigned byte, the *payload index*.

The dictionary grows as records are resolved: the resolved value of every preceding record is appended to it (see §6). When a dictionary record is read, the actual entry is `(dictionary_length - 1) - payload_index`, i.e. counted from the back of the dictionary built so far. The entry found there becomes both the record's resolved `value` and the new running value; a payload index outside the current dictionary is a `truncated_record` error. The payload index exactly as written is reported as `dict_index`.

## §6. State semantics

Records are resolved left to right against a single running value and a dictionary that grows by one entry per record. The running value starts at the header `base_value`.

- **raw** replaces the running value with the record's signed payload;
- **delta** adds its signed delta to the running value (§4);
- **dictionary** replaces the running value with the selected dictionary entry (§5).

Immediately after each record is resolved, the record's resolved value is appended to the dictionary, so the Nth record (counting from zero) is read against a dictionary holding exactly N entries. The running value left behind by a record is that record's resolved `value`.

## §7. Error paths

A decoder that rejects a file MUST print exactly one of these JSON objects to
stdout and exit `0`:

1. `{"error": "bad_magic"}` - the first five bytes are not exactly `50 49 50 45 31`.
2. `{"error": "unsupported_version", "version": N}` - magic is correct but the
   version byte is not `5`.
3. `{"error": "trailer_crc_mismatch"}` - magic and version are correct but the
   trailer check (§8) fails.

If more than one condition holds, report the first that matches in the order
above. Do not add any other keys or invent new error strings. A file whose
header and trailer are valid but whose body cannot be parsed - a truncated
field, an unknown mode selector, or a dictionary index out of range - is
reported as `{"error": "truncated_record"}`.

## §8. Trailer

The trailer is a single u32 LE holding `zlib.crc32` over the header fields after the magic bytes, followed by the body.

## §9. Worked examples

### Worked delta record

With a running value of `10`, delta -3 is signed-LEB128 byte `7d`; the resolved value becomes `7`. 
Its selector mode number is `2` and a short key `2a` follows selector byte `08`.

### Worked dictionary record

Given the prior resolved values `[11, 22, 33]`, payload index byte `02` selects `11` using backward indexing.
The resolved value and the next running value both become `11`. Its selector mode number is `0`.

### Reference bytes for an empty container

An empty container has `record_count = 0`, `base_value = 0`, `flags = 0x00`,
and no records. Its complete bytes, including the trailer, are:

```
50 49 50 45 31 00 00 00 00 00 05 00 00 00 00 00 5f 20 4a 3b
```
