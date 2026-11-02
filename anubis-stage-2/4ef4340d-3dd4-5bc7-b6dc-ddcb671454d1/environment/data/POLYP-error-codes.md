# POLYP error-code reference

Decoders must return one compact JSON object on stdout and exit successfully even
for damaged captures.

| Condition | Required JSON | Notes |
| --- | --- | --- |
| Magic bytes do not match | `{"error":"bad_magic"}` | Highest precedence. |
| Version byte is unsupported | `{"error":"unsupported_version","version":N}` | Report the observed integer version. |
| Trailer CRC check fails | `{"error":"trailer_crc_mismatch"}` | Applies after magic and version are accepted. |

If a record is malformed after a valid header and CRC, the reference verifier may
classify it as a truncated-record failure. The three rows above are the graded
documented error paths.

This file contains no hidden-corpus data.
