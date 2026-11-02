# SEALB glossary and changelog

## Glossary

- **base value**: signed i32 header field that initializes the running value.
- **running value**: decoder state updated by raw, delta, and dictionary records.
- **raw record**: record whose payload is a signed i16 or i32 absolute value.
- **delta record**: record whose payload is added to the running value.
- **dictionary record**: record whose payload selects a prior stored source.
- **long key**: UTF-8 key preceded by a uvarint byte length.
- **short key**: one-byte integer key.
- **pre-resolution payload**: the exact raw payload needed for byte-exact
  re-encoding (`raw_value`, `delta_raw`, or `dict_index`).

## Changelog

- Bundle-local revision 1: ships a complete written specification plus flat
  non-answer reference notes. No sample, field, or hidden eval answers are
  included in `/app/data`.
