# MDUMP varint, CRC-32C and keystream primer

Background for the three primitives the container format specification relies
on. The specification itself (sections 4, 5.4 and 8) is the rule; this file
explains the mechanics.

## Unsigned LEB128

Seven payload bits per byte, least significant group first; bit 7 means
another byte follows. `5` is `05`, `127` is `7f`, `128` is `80 01`, `300` is
`ac 02`. The same number can be spelled with redundant trailing groups (`85
00` is also 5); MDUMP key varints must use the shortest spelling.

## Signed LEB128 and padding

Signed LEB128 uses the same byte layout but the final value is sign-extended
from bit 6 of the last byte. `-1` is `7f`, `-3` is `7d`, `63` is `3f`, `64` is
`c0 00`, `-64` is `40`, `-65` is `bf 7f`.

Padding appends redundant groups that repeat the sign: set bit 7 on the last
byte of the shortest encoding, add `pad - 1` bytes of `ff` (negative values)
or `80` (non-negative values), and finish with one `7f` (negative) or `00`
(non-negative). `-3` padded by 2 is `fd ff 7f`; `300` padded by 1 is
`ac 82 00`. Decoding a padded varint gives the same value; the pad count is
the number of bytes beyond the shortest encoding. Decoders must not limit
values to 32 or 64 bits: a ten-byte varint holds a 70-bit two's-complement
number.

## CRC-32C

CRC-32C (Castagnoli) is a 32-bit CRC with reflected polynomial `0x82F63B78`.
A common table-driven form:

```
table[i] = i, then 8 times: x = (x >> 1) ^ 0x82F63B78 if x & 1 else x >> 1
crc = 0xFFFFFFFF
for each byte b: crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
result = crc ^ 0xFFFFFFFF
```

Check value: CRC-32C of ASCII `123456789` is `0xE3069283`. Python's
`zlib.crc32` and `binascii.crc32` compute CRC-32 (polynomial `0xEDB88320`,
check value `0xCBF43926`), which is a different checksum. The standard
library has no CRC-32C, so a decoder has to carry its own.

## Galois LFSR keystream

A Galois LFSR shifts its register one place per clock and, when the bit
shifted out is 1, XORs a constant (the tap mask) into the register. MDUMP uses
a 24-bit register, tap mask `0xE10000`, eight clocks per keystream byte, and
the low eight bits of the register after those clocks as the byte. The
register never becomes zero once started from a non-zero value, which is why
a zero salt is replaced by `0xC0FFEE` before the first clock.
