# MDUMP worked examples (revision 3)

Every capture below was produced by the current Coredrop writer and decodes exactly as shown. Byte strings are hexadecimal, one byte per pair. Record rows always show the plaintext record bytes, after de-whitening where the header asks for it.

## A. Primitive check values

- CRC-32C (Castagnoli, reflected polynomial `0x82F63B78`, initial register `0xFFFFFFFF`, final XOR `0xFFFFFFFF`) of the nine ASCII bytes `123456789` is `0xE3069283`. `zlib.crc32` of the same bytes is `0xCBF43926`; that is a different function and is never correct for MDUMP.
- CRC-32C of the empty string is `0x00000000`; of the single byte `00` it is `0x527D5351`.
- Keystream for salt `0x000001`, first eight bytes: `00 c2 01 04 50 09 a7 be`.
- Keystream for salt `0x123456`, first eight bytes: `34 3e 00 df 2e fe 5a 4e`.
- Keystream for salt `0x000000` (the register starts at `0xC0FFEE` instead), first eight bytes: `ff 9c 1d 86 0e 98 79 3a`.
- Signed LEB128: `-3` is `7d`; `-3` with delta_pad 2 is `fd ff 7f`; `300` is `ac 02`; `300` with delta_pad 1 is `ac 82 00`; `64` is `c0 00`; `-65` is `bf 7f`.
- Signed LEB128 of `4294967301` (2^32 + 5) is `85 80 80 80 10`; applied to a running value of `10` it resolves to `15`.
- Unsigned LEB128 key lengths: `5` is `05`, `200` is `c8 01`. `85 00` also spells 5 but is not minimal and is rejected (`noncanonical_varint`).
- 32-bit wrap: running value `2147483000` plus delta `1000` resolves to `-2147483296`.

## B. Plain capture

No flags, salt zero. The dictionary before record 2 is `[-3, 300]` (oldest first); payload index 1 counted from the back selects `-3`, which then moves to the back: `[300, -3]`, and the record's own payload `1` is appended: `[300, -3, 1]`.

Complete capture:

```
43 4f 52 45 5a 04 00 00 00 00 00 0a 00 00 00 01 01 2a fd ff 08 2b ac 02 00 2c 01 48 08 66 72 61 6d 65 2e 70 63 05 34 81 cf dd
```

| bytes | meaning |
|---|---|
| `43 4f 52 45 5a` | magic `COREZ` |
| `04 00` | record_count = 4 |
| `00 00 00` | salt = 0 (0x000000) |
| `00` | flags = 0x00 |
| `0a 00 00 00` | base_value = 10 |
| `01` | version = 1 |
| `01 2a fd ff` | record 0 (plaintext, offset 0): raw, key 42, raw_value -3 (i16), value -3 |
| `08 2b ac 02` | record 1 (plaintext, offset 4): delta, key 43, delta_raw 300, delta_pad 0, value 297 |
| `00 2c 01` | record 2 (plaintext, offset 8): dict, key 44, dict_index 1, value -3 |
| `48 08 66 72 61 6d 65 2e 70 63 05` | record 3 (plaintext, offset 11): delta, key 'frame.pc', delta_raw 5, delta_pad 0, value 2 |
| `34 81 cf dd` | trailer: CRC-32C 0xddcf8134 over header bytes 5..15 and the plaintext body |

Decoded document:

```json
{
 "version": 1,
 "flags": {
  "reserved_bit_0": false,
  "front_coded_keys": false,
  "big_endian_raw": false,
  "whitened": false
 },
 "salt": 0,
 "record_count": 4,
 "base_value": 10,
 "records": [
  {
   "key": 42,
   "long_key": false,
   "mode": "raw",
   "wide_value": false,
   "raw_value": -3,
   "value": -3,
   "offset": 0
  },
  {
   "key": 43,
   "long_key": false,
   "mode": "delta",
   "delta_raw": 300,
   "delta_pad": 0,
   "value": 297,
   "offset": 4
  },
  {
   "key": 44,
   "long_key": false,
   "mode": "dict",
   "dict_index": 1,
   "value": -3,
   "offset": 8
  },
  {
   "key": "frame.pc",
   "long_key": true,
   "mode": "delta",
   "delta_raw": 5,
   "delta_pad": 0,
   "value": 2,
   "offset": 11
  }
 ]
}
```

## C. Whitened capture with repeat records and 32-bit wrap

Whitened with salt 1. Record 0 overflows the running value and wraps. Record 1 repeats the last delta twice. Record 3 repeats it zero times, which leaves the running value unchanged. Record 4 adds -2^32, which wraps back to the same value.

Complete capture:

```
43 4f 52 45 5a 05 00 01 00 00 08 78 fd ff 7f 01 08 c3 e9 03 59 0b a5 af 02 20 0d 41 62 43 31 be df db a1 34 85 d1 78 34 e1 82 ab
```

| bytes | meaning |
|---|---|
| `43 4f 52 45 5a` | magic `COREZ` |
| `05 00` | record_count = 5 |
| `01 00 00` | salt = 1 (0x000001) |
| `08` | flags = 0x08 |
| `78 fd ff 7f` | base_value = 2147483000 |
| `01` | version = 1 |
| `08 01 e8 07` | record 0 (plaintext, offset 0): delta, key 1, delta_raw 1000, delta_pad 0, value -2147483296 |
| `09 02 02` | record 1 (plaintext, offset 4): repeat, key 2, repeat_count 2, value -2147481296 |
| `11 03 00 00 00 80` | record 2 (plaintext, offset 7): raw, key 3, raw_value -2147483648 (i32), value -2147483648 |
| `09 04 00` | record 3 (plaintext, offset 13): repeat, key 4, repeat_count 0, value -2147483648 |
| `08 05 80 80 80 80 70` | record 4 (plaintext, offset 16): delta, key 5, delta_raw -4294967296, delta_pad 0, value -2147483648 |
| `34 e1 82 ab` | trailer: CRC-32C 0xab82e134 over header bytes 5..15 and the plaintext body |

The body is whitened. Wire body bytes `08 c3 e9 03 59 0b a5 af 02 20 0d 41 62 43 31 be df db a1 34 85 d1 78`; keystream for salt 0x000001 `00 c2 01 04 50 09 a7 be 01 20 0d 41 e2 4a 35 be d7 de 21 b4 05 51 08`; plaintext body `08 01 e8 07 09 02 02 11 03 00 00 00 80 09 04 00 08 05 80 80 80 80 70`. The record rows above show the plaintext.

Decoded document:

```json
{
 "version": 1,
 "flags": {
  "reserved_bit_0": false,
  "front_coded_keys": false,
  "big_endian_raw": false,
  "whitened": true
 },
 "salt": 1,
 "record_count": 5,
 "base_value": 2147483000,
 "records": [
  {
   "key": 1,
   "long_key": false,
   "mode": "delta",
   "delta_raw": 1000,
   "delta_pad": 0,
   "value": -2147483296,
   "offset": 0
  },
  {
   "key": 2,
   "long_key": false,
   "mode": "repeat",
   "repeat_count": 2,
   "value": -2147481296,
   "offset": 4
  },
  {
   "key": 3,
   "long_key": false,
   "mode": "raw",
   "wide_value": true,
   "raw_value": -2147483648,
   "value": -2147483648,
   "offset": 7
  },
  {
   "key": 4,
   "long_key": false,
   "mode": "repeat",
   "repeat_count": 0,
   "value": -2147483648,
   "offset": 13
  },
  {
   "key": 5,
   "long_key": false,
   "mode": "delta",
   "delta_raw": -4294967296,
   "delta_pad": 0,
   "value": -2147483648,
   "offset": 16
  }
 ]
}
```

## D. Front-coded keys, big-endian raw payloads, a padded delta and a salt without whitening

Flags `front_coded_keys` and `big_endian_raw`; the salt is non-zero but the body is not whitened. Record 1 shares 7 bytes with the previous long key `café.é` (`63 61 66 c3 a9 2e c3`), so its suffix starts with the continuation byte `a8`, which is not valid UTF-8 on its own; the key is decoded only after the prefix and suffix are joined. Record 3 shares only 4 bytes even though more are available: the writer chose 4, and the document records that choice. Record 2 is a short-key record, so it does not change the previous long key.

Complete capture:

```
43 4f 52 45 5a 04 00 cd ab 00 06 ff ff ff ff 01 41 00 08 63 61 66 c3 a9 2e c3 a9 ff fe 48 07 01 a8 fd ff 7f 11 09 12 34 56 78 40 04 06 a9 2e c3 a8 2e 33 02 01 d2 08 75
```

| bytes | meaning |
|---|---|
| `43 4f 52 45 5a` | magic `COREZ` |
| `04 00` | record_count = 4 |
| `cd ab 00` | salt = 43981 (0x00abcd) |
| `06` | flags = 0x06 |
| `ff ff ff ff` | base_value = -1 |
| `01` | version = 1 |
| `41 00 08 63 61 66 c3 a9 2e c3 a9 ff fe` | record 0 (plaintext, offset 0): raw, key 'café.é', key_prefix 0, raw_value -2 (i16), value -2 |
| `48 07 01 a8 fd ff 7f` | record 1 (plaintext, offset 13): delta, key 'café.è', key_prefix 7, delta_raw -3, delta_pad 2, value -5 |
| `11 09 12 34 56 78` | record 2 (plaintext, offset 20): raw, key 9, raw_value 305419896 (i32), value 305419896 |
| `40 04 06 a9 2e c3 a8 2e 33 02` | record 3 (plaintext, offset 26): dict, key 'café.è.3', key_prefix 4, dict_index 2, value -2 |
| `01 d2 08 75` | trailer: CRC-32C 0x7508d201 over header bytes 5..15 and the plaintext body |

Decoded document:

```json
{
 "version": 1,
 "flags": {
  "reserved_bit_0": false,
  "front_coded_keys": true,
  "big_endian_raw": true,
  "whitened": false
 },
 "salt": 43981,
 "record_count": 4,
 "base_value": -1,
 "records": [
  {
   "key_prefix": 0,
   "key": "café.é",
   "long_key": true,
   "mode": "raw",
   "wide_value": false,
   "raw_value": -2,
   "value": -2,
   "offset": 0
  },
  {
   "key_prefix": 7,
   "key": "café.è",
   "long_key": true,
   "mode": "delta",
   "delta_raw": -3,
   "delta_pad": 2,
   "value": -5,
   "offset": 13
  },
  {
   "key": 9,
   "long_key": false,
   "mode": "raw",
   "wide_value": true,
   "raw_value": 305419896,
   "value": 305419896,
   "offset": 20
  },
  {
   "key_prefix": 4,
   "key": "café.è.3",
   "long_key": true,
   "mode": "dict",
   "dict_index": 2,
   "value": -2,
   "offset": 26
  }
 ]
}
```

## E. Move-to-front dictionary

Four raw records, then three dictionary records. Without move-to-front, record 5 would select `101`; with it, it selects `102`.

Complete capture:

```
43 4f 52 45 5a 07 00 00 00 00 00 00 00 00 00 01 01 00 64 00 01 01 65 00 01 02 66 00 01 03 67 00 00 0a 02 00 0b 03 00 0c 00 fc f0 11 2b
```

| bytes | meaning |
|---|---|
| `43 4f 52 45 5a` | magic `COREZ` |
| `07 00` | record_count = 7 |
| `00 00 00` | salt = 0 (0x000000) |
| `00` | flags = 0x00 |
| `00 00 00 00` | base_value = 0 |
| `01` | version = 1 |
| `01 00 64 00` | record 0 (plaintext, offset 0): raw, key 0, raw_value 100 (i16), value 100 |
| `01 01 65 00` | record 1 (plaintext, offset 4): raw, key 1, raw_value 101 (i16), value 101 |
| `01 02 66 00` | record 2 (plaintext, offset 8): raw, key 2, raw_value 102 (i16), value 102 |
| `01 03 67 00` | record 3 (plaintext, offset 12): raw, key 3, raw_value 103 (i16), value 103 |
| `00 0a 02` | record 4 (plaintext, offset 16): dict, key 10, dict_index 2, value 101 |
| `00 0b 03` | record 5 (plaintext, offset 19): dict, key 11, dict_index 3, value 102 |
| `00 0c 00` | record 6 (plaintext, offset 22): dict, key 12, dict_index 0, value 3 |
| `fc f0 11 2b` | trailer: CRC-32C 0x2b11f0fc over header bytes 5..15 and the plaintext body |

Decoded document:

```json
{
 "version": 1,
 "flags": {
  "reserved_bit_0": false,
  "front_coded_keys": false,
  "big_endian_raw": false,
  "whitened": false
 },
 "salt": 0,
 "record_count": 7,
 "base_value": 0,
 "records": [
  {
   "key": 0,
   "long_key": false,
   "mode": "raw",
   "wide_value": false,
   "raw_value": 100,
   "value": 100,
   "offset": 0
  },
  {
   "key": 1,
   "long_key": false,
   "mode": "raw",
   "wide_value": false,
   "raw_value": 101,
   "value": 101,
   "offset": 4
  },
  {
   "key": 2,
   "long_key": false,
   "mode": "raw",
   "wide_value": false,
   "raw_value": 102,
   "value": 102,
   "offset": 8
  },
  {
   "key": 3,
   "long_key": false,
   "mode": "raw",
   "wide_value": false,
   "raw_value": 103,
   "value": 103,
   "offset": 12
  },
  {
   "key": 10,
   "long_key": false,
   "mode": "dict",
   "dict_index": 2,
   "value": 101,
   "offset": 16
  },
  {
   "key": 11,
   "long_key": false,
   "mode": "dict",
   "dict_index": 3,
   "value": 102,
   "offset": 19
  },
  {
   "key": 12,
   "long_key": false,
   "mode": "dict",
   "dict_index": 0,
   "value": 3,
   "offset": 22
  }
 ]
}
```


Dictionary trace (oldest entry first):

| after record | dictionary | note |
|---|---|---|
| 0 | `[100]` |  |
| 1 | `[100, 101]` |  |
| 2 | `[100, 101, 102]` |  |
| 3 | `[100, 101, 102, 103]` |  |
| 4 | `[100, 102, 103, 101, 2]` | index 2 selects position 1 = 101; moved to the back, then payload 2 appended |
| 5 | `[100, 103, 101, 2, 102, 3]` | index 3 selects position 1 = 102; moved to the back, then payload 3 appended |
| 6 | `[100, 103, 101, 2, 102, 3, 0]` | index 0 selects position 5 = 3; moved to the back, then payload 0 appended |

## F. Rejected captures

Each line takes the capture from section B, applies the stated damage, and shows the one JSON object the decoder prints. Offsets count plaintext body bytes from 0; in section B record 3 starts at offset 11, its key length varint is at offset 12, its key bytes start at offset 13 and its payload byte is at offset 21.

| damage | decoder output |
|---|---|
| first byte XOR `0xff` | `{"error": "bad_magic"}` |
| file cut to 12 bytes | `{"error": "truncated_header", "length": 12}` |
| version byte set to 4 | `{"error": "unsupported_version", "version": 4}` |
| flags byte set to `0x40` | `{"error": "reserved_flag_set", "flags": 64}` |
| last trailer byte XOR `0xff` | `{"error": "trailer_crc_mismatch", "stored": 584024372, "computed": 3721363764}` |
| selector of record 2 OR `0x10` (wide bit on a dictionary record), CRC recomputed | `{"error": "reserved_selector_bits", "record_index": 2, "selector": 16, "offset": 8}` |
| two bytes `00 00` appended to the body, CRC recomputed | `{"error": "trailing_bytes", "count": 2, "offset": 22}` |
| record_count raised to 5, CRC recomputed | `{"error": "truncated_record", "record_index": 4, "offset": 22}` |
| last body byte removed (the payload of record 3), CRC recomputed | `{"error": "truncated_record", "record_index": 3, "offset": 21}` |
| key length of record 3 changed from `08` to `0c`, CRC recomputed | `{"error": "truncated_record", "record_index": 3, "offset": 13}` |
| key length of record 3 spelled `88 00` instead of `08`, CRC recomputed | `{"error": "noncanonical_varint", "record_index": 3, "offset": 12}` |
