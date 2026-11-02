# Idea card: vendor-archive-roundtrip-recovery (master-gated, 21 Oct 2026 12:45 IST)
Source: ChatGPT batch 20261021_data-processing, idea 2 "Byte-Exact Vendor Archive Recovery" (accepted as finalist 1). This card is the master's gated version and replaces the ChatGPT text where they differ.

## Premise
A data engineering team migrates long-lived telemetry archives after the vendor software is gone. The agent writes `decode.py` and `encode.py` for a documented, compact, stateful container format, decodes the supplied captures to normalised records, and proves byte-exact round trips. A decoder that gets every known field right can still fail the central contract: reproduce every valid captured frame byte for byte, and encode new or modified records canonically.

## Inputs (about 12 files, stdlib-readable, at least 6 formats)
`format_contract.md` (normative byte layout, versions, error catalogue with precedence and offset convention, canonical rules, report schemas); `schema_registry.json`; `field_layouts.csv`; `symbol_table.tsv` (dictionary seeds and scopes); `revision_map.ini` (field-id remaps between revisions); `escape_rules.xml`; `crc_profiles.json` (checksum variants and byte coverage); `frame_index.jsonl` (offsets, lengths, stream ids, sequence numbers); `capture_alpha.bin`, `capture_beta.bin` (frames from several streams, valid and damaged); `transport_errors.log` (damage annotations, not permission to skip bytes); `sample_order.txt` (prescribed stream and file processing order).
No decoded answers, no reference decoder output, no expected round-trip report.

## Spine (lever B)
metadata -> frame location -> physical validation (header, length, escape, checksum) -> per-stream context (dictionary, sequence, delta, reset) -> value decode -> revision remap to normalised schema -> encode (preserved or canonical) -> byte compare -> reports. Tests also grade later stages on supplied correct intermediates through documented entry points.

## Levers (ids for the registry)
- STANDARD A: hidden captures combine 3 or more of the rules below in one frame (escaped extension bytes + a dictionary reference set in an earlier file of the same stream + a revision remap + a non-shortest integer).
- STANDARD B: the chain above.
- STANDARD F (LV-VA-5): validation precedence and offsets on frames with several defects at once (for example a plausible length, an unsupported revision and a bad checksum). Exact error string and offset convention.
- STANDARD E: stacked constraints on encoder output: byte-exact for unmodified captured frames, canonical for new records, positional preservation for modified ones (LV-VA-2, LV-VA-4).
- NEW LV-VA-1 stream-local state: dictionary and sequence state belong to a stream, continue across capture files in the prescribed order, and are cleared only by that stream's reset frame.
- NEW LV-VA-2 opaque extensions in position: unknown extension fields are kept as raw bytes in their original position relative to known fields. When a known field of a captured record is modified, the encoder re-emits the frame with extensions in their original slots, recomputes length and checksum, and keeps preserved representations of the untouched fields.
- NEW LV-VA-3 framing-aware escaping: unescaping applies only inside the payload range given by the decoded length; a payload that ends on an escape-like byte next to a following header must not merge frames.
- NEW LV-VA-4 representation memory: a captured integer in a longer-than-shortest permitted form must be reproduced in that form when re-encoding the unmodified frame, but written in shortest form for new records and for the modified field itself.
- NEW LV-VA-6 resynchronisation: after a damaged range the decoder resumes only at the documented sync marker, and frames inside the damaged range are reported once each under the documented rule (not skipped silently, not decoded).

## Master's changes to the ChatGPT idea
- Dropped lever C (the archetype ships no partial decoder). Added LV-VA-4 and LV-VA-6.
- Strengthened the extension lever: plain "keep bytes in order" leaks, because a careful agent round-trips visible captures and passes. The hard part is modified records, which visible data cannot self-test.
- Replaced the reviewer list (all "the log identifies X") with concrete-fact criteria (see the build prompt).
