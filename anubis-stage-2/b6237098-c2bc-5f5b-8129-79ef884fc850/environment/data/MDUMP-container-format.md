# MDUMP Container Format, revision 3

This is the authoritative specification of the MDUMP crash-dump container
written by the Coredrop capture agent. It defines the header, the header
flags, body whitening, every record mode, the decoder state, the decoded
document, the trailer checksum and the rejection rules. Where any other file
in this directory disagrees with this document, this document wins. In
particular the legacy decoder (`MDUMP-legacy-decoder.py`) implements revision
1 and is known to be wrong about revision 3 captures in several places.

Conventions: offsets are byte offsets from the start of the file. "u8", "u16
LE", "i32 LE" and so on are unsigned or two's-complement signed integers of the
stated width and byte order. Bit `n` of a byte is the bit with value `1 << n`.
Worked byte-level examples for many of these rules live in `MDUMP-worked-examples.md`.

## 1. File layout

```
+--------------------+----------------------+--------------------+
| header (16 bytes)  | body (variable)      | trailer (4 bytes)  |
+--------------------+----------------------+--------------------+
```

The body is every byte between offset 16 and the last four bytes of the file.
Its length is not stored anywhere; it is `file_length - 20`.

## 2. Header

| offset | width   | field          | notes |
|--------|---------|----------------|-------|
| 0..4   | 5 bytes | magic          | ASCII `COREZ`, bytes `43 4f 52 45 5a`. |
| 5..6   | u16 LE  | record_count   | Number of records in the body. |
| 7..9   | u24 LE  | salt           | Whitening seed (section 4). Any value is legal, including non-zero values in files that are not whitened. Revision 1 called these three bytes "reserved, must be zero"; that rule is withdrawn. |
| 10     | u8      | flags          | Section 3. |
| 11..14 | i32 LE  | base_value     | Initial running value (section 6). Always little-endian, whatever the flags say. |
| 15     | u8      | version        | `1` for captures written to this specification. `2` marks a 4.x field build; see `MDUMP-rev4-field-notes.md`. `3` marks a 5.x field build; see `MDUMP-rev5-field-notes.md`. Any other value is rejected. |

## 3. Header flags

| bit | name               | meaning when set |
|-----|--------------------|------------------|
| 0   | `reserved_bit_0`   | No effect on decoding. It is reported and must be reproduced. |
| 1   | `front_coded_keys` | Long keys are front-coded against the previous long key (section 5.2). |
| 2   | `big_endian_raw`   | Raw-mode payloads are big-endian instead of little-endian (section 5.3). |
| 3   | `whitened`         | The body is XORed with a keystream derived from the salt (section 4). |
| 4..7 | (reserved)        | Must be zero. Any of them set is `reserved_flag_set`. |

## 4. Body whitening

When `whitened` is set, the body bytes on the wire are the plaintext body XORed
byte by byte with a keystream. A decoder recovers the plaintext body by XORing
the wire body with the same keystream; every rule in sections 5 and 6, and the
trailer checksum in section 8, operate on the plaintext body. When `whitened`
is clear the wire body is the plaintext body and the salt has no effect.

The keystream is produced by a 24-bit Galois linear-feedback shift register.

1. The register starts at `salt`. If `salt` is zero the register starts at
   `0xC0FFEE` instead.
2. One clock is: if bit 0 of the register is 1, shift the register right by
   one and XOR it with `0xE10000`; otherwise just shift it right by one.
3. For each body byte, in order starting with the first byte of the body,
   clock the register eight times and then take its low eight bits as the
   keystream byte for that body byte.

The register is never reset inside a file. Section A of the worked examples
lists the first keystream bytes for three salts.

## 5. Records

The plaintext body holds `record_count` records back to back. Each record is a
selector byte, then a key, then a payload whose shape depends on the mode.

### 5.1 Selector byte

| bit(s)    | meaning |
|-----------|---------|
| 0 and 3   | Mode number. Bit 0 contributes 1 and bit 3 contributes 2: `0` = dict, `1` = raw, `2` = delta, `3` = repeat. |
| 4         | `WIDE_VALUE`. Meaningful only for raw records: 1 = 32-bit payload, 0 = 16-bit payload. On any other mode it must be 0. |
| 6         | `LONG_KEY`. 1 = UTF-8 key (section 5.2), 0 = one-byte integer key. |
| 1, 2, 5, 7 | Reserved, must be 0. |

A selector with a reserved bit set, or with `WIDE_VALUE` set on a record whose
mode is not raw, is `reserved_selector_bits`.

### 5.2 Keys

When `LONG_KEY` is 0 the key is the next byte, an integer 0..255.

When `LONG_KEY` is 1 the key is UTF-8 text. Its bytes are stored one of two
ways, chosen for the whole file by the `front_coded_keys` flag.

- Flag clear: an unsigned varint `L` (section 5.4), then exactly `L` key bytes.
- Flag set: an unsigned varint `P`, then an unsigned varint `S`, then exactly
  `S` suffix bytes. The key bytes are the first `P` bytes of the previous long
  key's bytes followed by the `S` suffix bytes. The previous long key is the
  key of the most recent earlier record in this file whose `LONG_KEY` was 1,
  whatever its mode; short-key records do not change it. Before the first long
  key of a file the previous long key is empty. `P` greater than the length of
  the previous long key is `bad_key_prefix`, and it is detected as soon as `P`
  has been read, before `S` is read.

Prefixes are counted in bytes, not characters, so a prefix may end in the
middle of a multi-byte UTF-8 sequence and the suffix may start with
continuation bytes. Only the complete key bytes are decoded, as strict UTF-8
(no surrogates, no overlong forms, nothing above U+10FFFF); if they are not
valid the record is `invalid_utf8_key`. The writer does not always share the
longest possible prefix, so `P` is part of the decoded document.

### 5.3 Payloads

| mode   | payload | pre-resolution field(s) |
|--------|---------|-------------------------|
| raw    | i16 (`WIDE_VALUE` 0) or i32 (`WIDE_VALUE` 1), two's complement, little-endian unless `big_endian_raw` is set | `wide_value`, `raw_value` |
| delta  | one signed LEB128 varint (section 5.4) | `delta_raw`, `delta_pad` |
| dict   | one u8, the payload index | `dict_index` |
| repeat | one u8, the repeat count | `repeat_count` |

How each payload changes the running value is section 6.

### 5.4 Varints

All varints are little-endian base-128: seven data bits per byte, least
significant group first, bit 7 set on every byte except the last. A varint is
at most 10 bytes long; if ten bytes have been read and the tenth still has bit
7 set, the record is `varint_overlong`. A varint that runs past the end of the
body is `truncated_record`.

- Unsigned varints (key lengths `L`, prefix lengths `P`, suffix lengths `S`)
  must be minimal: a varint of two or more bytes whose last byte is `00` is
  `noncanonical_varint`.
- Signed varints (delta payloads) are signed LEB128: after the last byte the
  value is sign-extended from bit 6 of that byte. The writer sometimes pads a
  delta with redundant sign-extension bytes. Padding is legal. `delta_pad` is
  the number of bytes the varint used beyond the shortest signed LEB128
  encoding of the same value, so it is 0 for a minimal varint. A delta may be
  any value a 10-byte varint can hold; it is not limited to 32 bits.

## 6. Decoder state

Decoding keeps five pieces of state per file, all reset at the start of every
file:

- the running value, a signed 32-bit register, starting at `base_value`;
- the last delta, starting empty;
- the dictionary, a list starting empty, holding at most 40 entries;
- the previous long key (section 5.2), starting empty;
- the record index, counting records from 0.

Every value written into the running value is first reduced to signed 32 bits:
take it modulo 2^32 and map the result into -2^31..2^31-1. Records are
processed strictly in file order:

- **raw**: the running value becomes `raw_value`.
- **delta**: the running value becomes `running + delta_raw`, reduced; the
  last delta becomes `delta_raw` (unreduced).
- **dict**: let `n` be the dictionary length. A payload index `>= n` is
  `dict_index_out_of_range`. Otherwise the selected entry is the one at
  position `n - 1 - dict_index` counting from the oldest entry at position 0,
  so index 0 is the newest entry. The running value becomes the selected
  entry, reduced. The selected entry is then removed from its position and
  appended at the newest end (move-to-front).
- **repeat**: if no delta record has appeared earlier in this file, the record
  is `repeat_without_delta`. Otherwise the running value becomes
  `running + last_delta * repeat_count`, reduced. A repeat count of 0 leaves the
  running value unchanged. Repeat records do not change the last delta.

The record's resolved `value` is the running value after the record. Then the
record's pre-resolution payload is appended at the newest end of the
dictionary: `raw_value` for raw, `delta_raw` for delta, `dict_index` for dict,
`repeat_count` for repeat. If the dictionary now holds 41 entries, the oldest
entry is dropped. Dictionary entries keep their unreduced payload values; only
the running value is reduced.

## 7. Decoded document

A successfully decoded capture is one JSON object with exactly these keys:

```json
{"version": 1,
 "flags": {"reserved_bit_0": false, "front_coded_keys": false, "big_endian_raw": false, "whitened": false},
 "salt": 0, "record_count": 2, "base_value": 0,
 "records": [ ... ]}
```

`records` holds exactly `record_count` objects in file order. Each record
object carries exactly the following keys and no others:

| record | keys |
|--------|------|
| every record | `key`, `long_key`, `mode`, `value`, `offset` |
| long-key record in a file with `front_coded_keys` set | also `key_prefix` (the stored `P`) |
| raw | also `wide_value`, `raw_value` |
| delta | also `delta_raw`, `delta_pad` |
| dict | also `dict_index` |
| repeat | also `repeat_count` |

`key` is an integer for short keys and a string for long keys. `mode` is one
of `"raw"`, `"delta"`, `"dict"`, `"repeat"`. `offset` is the position of the
record's selector byte in the plaintext body, counting the first body byte as
0, so the first record always has offset 0. Every number is a JSON integer.
Key order and whitespace inside the object are free.

The document carries everything needed to rebuild the file byte for byte:
`salt`, every flag, `key_prefix`, `wide_value` and `delta_pad` are replayed by
the encoder, never recomputed or normalised. `value` and `offset` are derived
data: the encoder recomputes them and refuses a document whose stored values
disagree (`MDUMP-encoder-notes.md`).

## 8. Trailer

The trailer is a u32 LE holding the CRC-32C (Castagnoli) checksum of the 11
header bytes at offsets 5..15 (everything after the magic) followed by the
plaintext body. CRC-32C here is the reflected CRC with polynomial
`0x82F63B78`, initial register `0xFFFFFFFF` and final XOR `0xFFFFFFFF`. It is
not the checksum `zlib.crc32` computes. The checksum covers the plaintext
body, so a whitened file must be de-whitened before it can be checked.

## 9. Rejection

A file that cannot be decoded produces exactly one JSON error object instead
of a document. The checks run in the order below and the first that fails
decides the error; `MDUMP-error-codes.md` gives the exact keys of every error
object.

1. Fewer than 5 bytes, or the first five bytes are not the magic: `bad_magic`.
2. Fewer than 20 bytes: `truncated_header`.
3. Version byte not `1`, `2` or `3`: `unsupported_version`.
4. Any of flag bits 4..7 set: `reserved_flag_set`.
5. Trailer does not match the CRC-32C of section 8: `trailer_crc_mismatch`.
6. Records are parsed in order; the first record that fails ends decoding
   with that record's error. Within a record the fields are read in order
   (selector, key, payload) and checked as they are read, so the first
   problem met in that order is the one reported. The error object also
   gives the plaintext body offset of the field that failed.
7. After `record_count` records, any plaintext body bytes left over:
   `trailing_bytes`, with the offset of the first leftover byte.

## 10. Grammar summary

The grammar facts above, in machine-readable form:

```json
{"header_order": ["record_count", "salt", "flags", "base_value", "version"],
 "selector": {"mode_bits": [0, 3], "wide_bit": 4, "long_key_bit": 6, "reserved_bits": [1, 2, 5, 7],
              "mode_ids": {"dict": 0, "raw": 1, "delta": 2, "repeat": 3}},
 "flag_bits": {"reserved_bit_0": 0, "front_coded_keys": 1, "big_endian_raw": 2, "whitened": 3},
 "delta_encoding": "signed_leb128",
 "dict_source": "payload_values",
 "dict_direction": "backward",
 "dict_capacity": 40,
 "dict_move_to_front": true,
 "crc_algorithm": "crc32c",
 "crc_coverage": "header_records"}
```
