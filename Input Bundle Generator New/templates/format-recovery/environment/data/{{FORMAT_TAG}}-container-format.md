# {{FORMAT_TAG}} Container Format, v1.0

Complete specification of the {{FORMAT_TAG}} binary container as produced by
{{PRODUCER_SYSTEM}}. This document fully defines the header, every record mode,
the cumulator and dictionary state, the error paths, and the trailer checksum -
everything a decoder and a byte-exact encoder need. All multi-byte integers are
little-endian. Offsets are byte offsets from the start of the file unless noted
otherwise.

## §1. File layout

A {{FORMAT_TAG}} container is exactly:

```
+-----------+-------------+---------+
|  header   |    body     | trailer |
| (16 bytes)| (variable)  |(4 bytes)|
+-----------+-------------+---------+
```

The body holds `record_count` records back-to-back. The trailer binds the
header and body together.

## §2. Header table

{{GRAMMAR_HEADER_TABLE}}

## §3. Records - raw mode

Every record starts with a **1-byte selector** followed by a key and a payload.
The selector packs three fields:

{{GRAMMAR_SELECTOR_DOC}}

For **raw mode** (`mode == {{GRAMMAR_RAW_MODE_ID}}`) the record layout is:

| width                        | field       | notes |
|------------------------------|-------------|-------|
| u8                           | selector    | bits: `mode={{GRAMMAR_RAW_MODE_ID}}`, `WIDE_VALUE`, `LONG_KEY`. |
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

{{GRAMMAR_DELTA_DOC}}

## §5. Dictionary mode

{{GRAMMAR_DICT_DOC}}

## §6. State semantics

{{GRAMMAR_STATE_DOC}}

## §7. Error paths

A decoder that rejects a file MUST print exactly one of these JSON objects to
stdout and exit `0`:

1. `{"error": "bad_magic"}` - the first five bytes are not exactly `{{MAGIC_HEX}}`.
2. `{"error": "unsupported_version", "version": N}` - magic is correct but the
   version byte is not `{{VERSION_NUM}}`.
3. `{"error": "trailer_crc_mismatch"}` - magic and version are correct but the
   trailer check (§8) fails.

If more than one condition holds, report the first that matches in the order
above. Do not add any other keys or invent new error strings. A file whose
header and trailer are valid but whose body cannot be parsed - a truncated
field, an unknown mode selector, or a dictionary index out of range - is
reported as `{"error": "truncated_record"}`.

## §8. Trailer

The trailer is a single u32 LE holding `zlib.crc32` over {{GRAMMAR_CRC_DOC}}.

## §9. Worked examples

{{GRAMMAR_WORKED_EXAMPLES}}

### Reference bytes for an empty container

An empty container has `record_count = 0`, `base_value = 0`, `flags = 0x00`,
and no records. Its complete bytes, including the trailer, are:

```
{{GRAMMAR_EMPTY_HEX}}
```
