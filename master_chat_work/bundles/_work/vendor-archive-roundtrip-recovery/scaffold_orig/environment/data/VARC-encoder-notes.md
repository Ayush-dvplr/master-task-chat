# VARC encoder notes

The encoder should rebuild a capture from the JSON document shape emitted by the
decoder.

1. Emit the magic `50 49 50 45 31` and the generated header fields in their exact
   generated order.
2. Use the document's `record_count`, `base_value`, and reserved-bit flag.
3. For each record, rebuild the selector from the generated mode identifiers and
   flag bit positions. Raw records set `wide_value`; long keys set the long-key
   flag and carry a uvarint byte length before UTF-8 key bytes.
4. Encode raw payloads as little-endian signed i16/i32. Encode delta payloads
   using this bundle's generated delta codec. Encode dictionary payloads as the
   stored u8 `dict_index`.
5. Append the CRC32 trailer over the generated coverage region. Do not normalize
   otherwise-preserved header bytes when round-tripping.

This note describes mechanics; it intentionally ships no decoded corpus answers.
