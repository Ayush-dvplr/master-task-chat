# MDUMP encoder notes

An encoder takes a decoded document (container format specification, section
7) and writes the capture it came from. Every capture the Coredrop writer
produces satisfies `encode(decode(bytes)) == bytes`, and the document holds
every choice the writer made, so an encoder never has to guess.

1. Header: magic, then `record_count` u16 LE, `salt` u24 LE, the flags byte
   rebuilt from the four named flags, `base_value` i32 LE, `version`. Write
   the salt exactly as given, even when the file is not whitened.
2. For each record build the selector from the mode number (bit 0 and bit 3),
   `WIDE_VALUE` (raw records only) and `LONG_KEY`. Reserved bits stay zero.
3. Short keys are one byte. Long keys are UTF-8; without front coding write
   the minimal unsigned varint length and the bytes; with front coding write
   the document's `key_prefix` as `P`, the remaining length as `S`, and the
   bytes after the first `P`. Do not substitute the longest common prefix for
   the stored one.
4. Raw payloads use the width from `wide_value` and the byte order from
   `big_endian_raw`. Delta payloads are signed LEB128 padded by exactly
   `delta_pad` bytes. Dict and repeat payloads are one byte.
5. Compute the CRC-32C over header bytes 5..15 and the plaintext body, then
   whiten the body if the `whitened` flag is set, then append the trailer.
   Whitening happens after the checksum, not before.

## Derived fields

Each record's `value` and `offset` are derived data: they follow from the
other fields, and the encoder does not need them to build the bytes. It must
still check them, because a document whose derived fields are wrong was edited
by hand and no longer describes the capture it claims to.

Walk the records in order, keeping the decoder state of section 6 of the
container format specification and the plaintext body offset of each
record's selector. Within each record compare `offset` first, then `value`.
At the first record whose stored field differs from the recomputed one the
encoder writes no capture file at all, prints exactly one JSON object on
stdout and exits with status 1:

```json
{"error": "inconsistent_document", "record_index": 3, "field": "value"}
```

`record_index` counts records from 0 and `field` is `"offset"` or `"value"`,
whichever was found wrong first. A document the decoder printed always passes
this check. Every other field of the document can be taken as valid.
