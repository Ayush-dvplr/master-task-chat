# MDUMP field notes: version byte 4 captures

Agent builds from the 6.x line write version byte `4`. They retain the
revision-3 header, flags, key encodings, raw integers, 32-bit wrapping,
document shape, offsets, errors, precedence and encoder/refusal contract.
The changes below are normative and replace the corresponding older-build
rules.

- The reflected trailer CRC covers the entire 16-byte header followed by the
  plaintext body. Its reflected polynomial is `0xedb88320`, its initial
  register is `0xffffffff`, and its final XOR is `0x00000000`. The stored
  trailer remains little-endian.
- Whitening uses a 24-bit right-shift Galois register with taps `0xb40000`.
  Before clocking, add the high 24 bits of the header's unsigned base-value
  bit pattern to the salt modulo `2^24`. If that folded result is zero, use
  `0x13579b`. Clocking and byte read-out otherwise remain unchanged.
- Selector mode bits return to positions 0 and 3.
- Delta payloads are unsigned LEB128 holding a sign-low-bit integer: a
  non-negative delta `d` stores `2*d`; a negative delta stores `-2*d+1`.
  Padding and `delta_pad` use the existing unsigned framing rules.
- A repeat payload `n` applies the previous delta `n+2` times.
- The dictionary window has 16 entries. An index counts forward from the
  oldest entry; the selected entry moves to the newest position. Every record
  appends its stored payload (not its resulting value), after that move.

A version 4 document must encode to a version 4 capture and is subject to the
same derived-field consistency checks as all earlier versions.
