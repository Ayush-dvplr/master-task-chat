# TRUTH.md - 11750b7a-a240-5905-a4f7-adbdadbb7c9a

## Defect

No source of a working codec ships anywhere in this instance. `/app/data/` holds
7 flat files describing `SEALB`, a binary record container produced by the KMS-9
envelope daemon: six written reference documents and one capture log of 20,000 hex
captures with no decoded answers. There is no reference decoder and no worked answer
key beyond the examples embedded in the prose. The agent must derive the entire
grammar from that written material and deliver both halves of the codec: a decoder at `/app/decode.py` that turns a capture into one
JSON document, and an encoder at `/app/encode.py` that turns that same document back
into the original bytes. The grammar is specific to this task instance, so
every published property below is instance-specific and cannot be recalled from
training.

1. (focal) Three payload modes must all work. Raw is the easy one; **delta** (spec §4)
   and **dictionary** (spec §5) carry the weight. A solver that implements raw only
   answers fewer than half of the positive tests, because the hidden corpus mixes modes
   inside a single capture and the running value threads through all three.
2. (focal) The resolution state machine (spec §6) is stateful and order-sensitive.
   Records resolve left to right against one running value seeded from the header
   `base_value`, and the dictionary grows by exactly one entry per record. The entry
   appended is the record's resolved `value` (spec §5 and §6), not its pre-resolution
   payload (`raw_value`, `delta_raw`, or `dict_index`). Confusing the two produces a
   decoder that is correct until the first dictionary record that reads back a delta or
   dictionary entry, and wrong from there on.
3. (focal) The encoder must be byte-exact, not merely semantically equivalent. The
   header field order and the payload widths have to come back unchanged, which is why
   the decoded document carries pre-resolution payload fields at all. The document has
   no field for the reserved header bytes or for flag bits 1..7, so the encoder writes
   them as zero, which is what every clean capture carries; `encode(decode(b))` equals
   `b` for every clean capture, including the hidden ones. Containers the decoder
   accepts under U2, U3, U5 or U7 (defect 7) cannot be rebuilt byte for byte, and no
   round-trip test uses one.
4. (drift) The selector byte does not have the layout an experienced reader expects -
   the mode number is split across bits 3 and 7, the wide-value flag sits at bit 0 and
   the long-key flag at bit 5, as spelled out under *Selector layout* in the Root cause
   section below. An agent that assumes "mode lives in the low two bits" mis-reads the
   captures. The specification states the mapping; the instinct contradicts it.
5. (trap) Raw payloads are **signed** `i16` and `i32`. The eval corpus deliberately
   includes magnitudes near `INT16_MAX` and `INT32_MAX`, so an implementation that
   unpacks the payload as unsigned passes the small-value tests and fails
   `decodes_raw_and_key_forms` and `decodes_delta_dict_and_mixed`, and the round-trip
   and report checks with them.
6. (trap) The trailer CRC covers the header fields after the magic bytes, followed by
   the body (spec §8) - not the whole file and not the magic. A decoder that checks the
   wrong region rejects every clean capture as `trailer_crc_mismatch`, and an encoder
   that seals the wrong region fails every round-trip test while looking perfectly
   reasonable in a diff of the decoded JSON.
7. (free parameters) The instruction says eight situations a container can present are
   settled by neither the specification nor its companion notes, and leaves the
   treatment to the agent. None of them occurs in the shipped capture log. The
   reference treatments, each graded by its own test (listed under Verification), are:
   - U1 flag bits 1..7 set -> `truncated_record`
   - U2 nonzero reserved header bytes 11..13 -> ignored, decoded normally
   - U3 reserved selector bits 1, 2, 4, 6 set -> ignored, decoded by the mode bits
   - U4 `WIDE_VALUE` set on a delta or dictionary record -> `truncated_record`
   - U5 spare bytes between the last record and the trailer -> ignored, decoded normally
   - U6 varint (key length or delta) with a redundant trailing byte -> `truncated_record`
   - U7 long key that is not valid UTF-8 -> decoded with U+FFFD replacement characters
   - U8 file shorter than header plus trailer (14, 16 or 19 bytes) -> `trailer_crc_mismatch`
   No file under `/app/data` states these treatments outright. U1, U4, U6 and U8 follow
   most naturally from the byte-exact contract and the §7 precedence; U2, U3, U5 and U7
   are choices the agent has to make and justify.

The reference is authored in Python (Python 3.12, standard library only,
298-line single-file codec) with a Bash oracle dispatcher
(`solve.sh`) that installs the same module at both `/app/decode.py` and
`/app/encode.py` and then emits the four report artifacts. A deterministic channel
observes the delivered programs (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric channel grades the derivation trajectory
(Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the prose
above - read them from those files, or from the lists below which mirror them.

Out of bounds: reading anything under `/app/data/` while `decode.py` or `encode.py` runs
(`negative_reads_training_corpus_at_runtime`, which fires on any string literal in
either program that contains `/app/data`); importing helper modules the
agent writes alongside the two entry points, which will not be collected; keying
behaviour on the input filename (`negative_filename_dependent_behaviour`);
rebinding `open`, `zlib.crc32`, or `struct.unpack`
(`negative_rebinds_verifier_dependencies`); emitting different bytes for the
same input across two runs (`negative_nondeterministic_output`); embedding
corpus answers as literals (`negative_hardcoded_sample_answers`, which fires when
every regenerated sample capture decodes but no fresh eval capture does);
installing third-party packages; and looking the format up online - `SEALB` is
invented for this instance and nothing about it exists outside this bundle.

## Load-bearing work

6 artifacts are collected, and every one of them is graded:

- `/app/decode.py`
- `/app/encode.py`
- `/app/out/decoded_examples.jsonl`
- `/app/out/format_report.json`
- `/app/out/roundtrip_report.json`
- `/app/out/error_analysis.json`

- `/app/decode.py` (new) - invoked as `python3 /app/decode.py <input.nnc>`.
  Prints exactly one JSON object on stdout, nothing else, and exits 0 even when the
  capture is rejected. On rejection it prints a single-key error object using the error
  name the specification defines, honouring the documented precedence.
- `/app/encode.py` (new) - invoked as
  `python3 /app/encode.py <document.json> <output.nnc>`. Consumes the decoder's
  own document shape and rebuilds the capture byte for byte.
- `/app/out/decoded_examples.jsonl` (new) - one decoded document per line for the
  agent's *own* illustrative examples. Hidden or reseeded corpus answers must not appear
  here.
- `/app/out/format_report.json` (new) - deterministic summary of the recovered grammar:
  header layout, selector mapping, mode identifiers, CRC coverage, plus the capture-log
  tallies (`capture_count`, `capture_ok_count`, `capture_mode_counts`).
- `/app/out/roundtrip_report.json` (new) - deterministic self-check that every
  illustrative example satisfies `encode(decode(bytes)) == bytes`.
- `/app/out/error_analysis.json` (new) - deterministic summary of the documented
  rejection paths and their precedence order, plus `capture_errors`, the error-code
  tally over the damaged captures in the capture log.

`/app/data/SEALB-capture-log.jsonl` ships 20,000 captures as hex, about
9% damaged (bad magic, unsupported version, trailer CRC). The verifier regenerates the
same log with `capture_log()`, so the tallies are checked against
ground truth; decoding all of them is the large-input half of the task, and only a
decoder that follows the specification's precedence gets the error tally right. Deleting
the log makes those two reports impossible to produce.

The exact shape of each report is written down for the agent in the "Report artifacts"
section of the decoder appendix, and the instruction points there; the reference
`solution/solve.py` follows that section with its own examples, and the tests check
the shape and its consistency with whatever examples the agent chose, never a fixed
example set. This section names the deliverables so a reader
knows the shape of the work, not the text to type.

Out of bounds by design: shipping the answers to captures the agent never generated;
splitting the codec across importable helper modules; depending on files under
`/app/data/` at run time; and any behaviour that varies with the input path.

## Verification

Grader entrypoint: `tests/test.sh`. It hardens the verifier (clears stale reward files,
locks `/logs/verifier` to root, restricts `/tests`) and then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit
scores Channel A from the `@criterion` checks in `tests/test_output.py`, each weighted by
its `criteria.<name>(weight=W)` registration, and Channel B from the criteria in
`tests/judge.toml`, which the judge reads against `/logs/agent/trajectory.json`.
`tests/reward.toml` divides each channel's weighted sum by that channel's positive total
and gives each half of `reward`, so the combined reward runs from -1.000 to +1.000.
The oracle and nop calibration runs score Channel A alone, on a tests-only copy of the
bundle with `tests/judge.toml` removed; Channel B has no oracle score.

Channel A declares 16 positive and 5 negative tests, positive weight total
48 and negative weight total -23, so the
theoretical reward range is -23/48 = -0.479 to +1.000.

Positive tests (each group passes only when every listed check holds):

- `decoder_and_single_json_output` (weight 1): decode.py/encode.py exist, one JSON object per run
- `decodes_raw_and_key_forms` (weight 1): raw i32/i16, large magnitude, short and long keys
- `decodes_delta_dict_and_mixed` (weight 1): delta, dict, mixed modes from the eval corpus
- `classifies_header_damage_in_order` (weight 1): bad_magic, unsupported_version, bad crc, precedence
- `encoder_round_trips` (weight 1): regenerated sample and eval captures rebuilt byte-exact
- `record_order_and_payload_fields` (weight 1): record count/file order, pre-resolution payload fields
- `report_artifacts_match_reference` (weight 1): the four /app/out artifacts
- `reproduces_labelled_sample_answers` (weight 1)
- `unknown_flag_bits_reject_container` (weight 5): U1, flag bits 1..7 set -> truncated_record
- `nonzero_reserved_header_bytes_are_ignored` (weight 5): U2, reserved bytes 11..13 nonzero -> decoded normally
- `reserved_selector_bits_are_ignored` (weight 5): U3, selector bits 1,2,4,6 set -> decoded by mode bits
- `wide_bit_on_delta_or_dict_rejects_container` (weight 5): U4, WIDE on delta/dict -> truncated_record
- `bytes_after_last_record_are_ignored` (weight 5): U5, slack bytes before trailer -> decoded normally
- `overlong_varint_rejects_container` (weight 5): U6, redundant trailing varint byte -> truncated_record
- `invalid_utf8_long_key_uses_replacement_character` (weight 5): U7, invalid UTF-8 long key decoded with U+FFFD
- `container_shorter_than_header_and_trailer_fails_crc` (weight 5): U8, file shorter than header+trailer (14/16/19 bytes) -> trailer_crc_mismatch

Negative tests (5) are polarity-inverted: their assertions hold
only when the cheat is present, so an honest run leaves them "failing" and contributes
zero weight. They subtract only from a solver that actually cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_rebinds_verifier_dependencies` (weight -5)
- `negative_nondeterministic_output` (weight -3)

Channel B is 13 criteria (11 positive / 2 negative), positive total 31:

- **R1** (+1): reads the complete SEALB-container-format.md before implementing.
- **R2** (+1): identifies record modes, key encodings, state/dictionary semantics, error paths.
- **R3** (+1): derives decoder and byte-exact encoder from the specification and worked examples.
- **R4** (+1): validates decoder behaviour against the worked examples.
- **R5** (+1): verifies decode.py and encode.py import in a clean Python 3.12 session.
- **R6** (-5): mutates the specification text, verifier assets, or reward files.
- **R7** (-5): retrieves a task-specific implementation from an external source.
- **R8** (+5): lists at least six unsettled container situations with the treatment applied.
- **R9** (+5): weighs two candidate treatments for at least four unsettled situations.
- **R10** (+5): runs the decoder on self-built, CRC-resealed containers covering at least five unsettled situations.
- **R11** (+3): hand-decodes one container byte by byte, including the CRC, and compares.
- **R12** (+5): final decoder, as exercised, decodes containers with nonzero reserved header bytes or reserved selector bits instead of rejecting.
- **R13** (+3): final decoder, as exercised, still returns records when a long key is invalid UTF-8, using replacement characters.

The sample, field and eval corpora and the capture log are regenerated deterministically
by `tests/test_output.py` from constants in that file. The verifier builds them in a
temporary directory so it works under harbor's `separate` verifier mode, where
`/app/data/` is not propagated. The oracle expectation is that running
`solution/solve.sh` inside the container drives every positive Channel A test to pass and
holds every negative test in its failing state.

## Root cause

**What "recovering a format" actually requires.** A container format is a bijection
between a byte string and a document. Reading the bytes is only half of it; the half that
carries the grade is proving the map is invertible. Every property the tests measure is a
projection of that single invariant - decode correctness, encoder round-trip, the
pre-resolution payload fields, and determinism are four views of "the document retains
exactly enough information to rebuild the bytes."

**Why the pre-resolution fields exist.** The resolved `value` of a record is lossy. Two
different byte encodings can resolve to the same value: a raw record holding 7 and a
delta record holding `+7` against a running value of 0 both resolve to 7. If the decoder
publishes only `value`, the encoder cannot know which byte sequence to emit, and the
round-trip tests fail no matter how correct the decode is. `raw_value`, `delta_raw`, and
`dict_index` are the witnesses that make the map invertible, which is why
`record_order_and_payload_fields` checks for them on their own.

**The state machine.** Records are resolved left to right against a single running value and a dictionary that grows by one entry per record. The running value starts at the header `base_value`.

- **raw** replaces the running value with the record's signed payload;
- **delta** adds its signed delta to the running value (§4);
- **dictionary** replaces the running value with the selected dictionary entry (§5).

Immediately after each record is resolved, the record's resolved value is appended to the dictionary, so the Nth record (counting from zero) is read against a dictionary holding exactly N entries. The running value left behind by a record is that record's resolved `value`.

**Delta encoding.** A record whose selector mode number is `1` is a **delta** record. Its payload is one signed integer delta.

The signed delta is written as signed LEB128: 7 data bits per byte, least-significant group first, high bit set on every byte except the last, and the payload is sign-extended from the final byte. For example a delta of `-3` is the single byte `7d`.

The delta updates the running value described in §6 (`running = running + delta`); the new running value is the record's resolved `value`. The raw delta, before it is applied, is reported as `delta_raw`.

**Dictionary resolution.** A record whose selector mode number is `0` is a **dictionary** record. Its payload is one unsigned byte, the *payload index*.

The dictionary grows as records are resolved: the resolved value of every preceding record is appended to it (see §6). When a dictionary record is read, the actual entry is `payload_index` counted from the front of the dictionary built so far. The entry found there becomes both the record's resolved `value` and the new running value; a payload index outside the current dictionary is a `truncated_record` error. The payload index exactly as written is reported as `dict_index`.

**Grammar for this instance.** The header field order, selector bit assignment, mode
identifiers, delta encoding, dictionary direction, and CRC coverage are all stated in the
shipped specification and summarised in the decoder appendix. There is no public `SEALB`
to look up, so the only path to a passing solution runs through reading that
specification. The grammar is:

`{"crc_coverage": "header_records", "delta_encoding": "signed_leb128", "dictionary": {"direction": "forward", "source": "resolved_values"}, "header_order": ["base_value", "flags", "version", "reserved", "record_count"], "selector": {"long_key_bit": 5, "mode_bits": [3, 7], "mode_ids": {"delta": 1, "dict": 0, "raw": 2}, "wide_bit": 0}}`

**Header layout for this instance.**

| offset  | width   | field         | notes |
|---------|---------|---------------|-------|
| 0..4    | 5 bytes | magic         | ASCII bytes `53 45 41 4c 42`. Any other value is `bad_magic` (§7). |
| 5..8    | i32 LE  | base_value    | Signed initial value used by some record modes. See §4. |
| 9       | u8      | flags         | Bit 0 is `reserved_bit_0`; bits 1..7 are written as `0`. A set bit 1..7 is `truncated_record` (U1). |
| 10      | u8      | version       | Must be `3`. Any other value is `unsupported_version` (§7). |
| 11..13  | 3 bytes | reserved      | Written as `0x00 0x00 0x00`, inside the CRC coverage (§8). Nonzero bytes are ignored on decode (U2). |
| 14..15  | u16 LE  | record_count  | Number of records that follow in the body. |

**Selector layout for this instance.**

- bits `3` and `7` carry the payload **mode** number (`2` = raw, `1` = delta, `0` = dictionary). The lower listed bit contributes value 1 and the higher listed bit contributes value 2.
- bit `0` carries the `WIDE_VALUE` flag (raw mode only): `1` = 32-bit payload, `0` = 16-bit.
- bit `5` carries the `LONG_KEY` flag: `1` = varint-length UTF-8 key, `0` = 1-byte key.
- bits `1, 2, 4, 6` are written as `0`; set bits are ignored on decode (U3).

**Red lines.** No runtime read of `/app/data`; no filename-conditioned behaviour; no
rebinding of `open` / `zlib.crc32` / `struct.unpack`; no non-determinism across runs; no
hidden-corpus answers baked into the `/app/out/*` artifacts; no third-party packages; no
online lookup.

## Solution shape

1. Read `/app/data/SEALB-container-format.md` end to end before writing a line,
   then the supporting files - the decoder appendix, the encoder notes, the error-code
   reference, the varint/CRC primer, and the glossary. Deciding which file answers which
   question is part of the task.
2. Transcribe the header into a single parse function: magic `b"SEALB"`
   (`53 45 41 4c 42`), version `3`, then the five post-magic fields in the
   order the specification gives, which is not the order the field names suggest.
3. Implement the selector decode as a bit-mask table derived from the spec's own
   assignment, not from a guessed layout. Reject a container with flag bits 1..7 set
   (U1) or with `WIDE_VALUE` on a delta or dictionary record (U4); decode normally when
   reserved selector bits (U3) or reserved header bytes (U2) are nonzero.
4. Implement the three payload readers - raw (signed, width from the wide flag), delta
   (varint, then the documented signed mapping), dictionary (index, then the documented
   direction) - each returning both its pre-resolution payload and the resolved value.
5. Implement the resolution loop: one running value seeded from `base_value`, one
   dictionary appended to once per record with the record's resolved value, and
   left-to-right ordering that never looks ahead.
6. Implement the trailer check with `zlib.crc32` over the documented coverage region, and
   the rejection precedence `bad_magic` → `unsupported_version` →
   `trailer_crc_mismatch` → `truncated_record`, exiting 0 on every one of them.
7. Write the encoder as the literal inverse of each reader: flag byte from
   `flags.reserved_bit_0`, reserved bytes `00 00 00`, raw payloads at the width
   `wide_value` names, and varints at their minimal width (an overlong varint is
   rejected on decode, U6). Verify `encode(decode(b)) == b` on every example the agent
   builds.
8. Emit the four `/app/out/*` reports from the agent's own illustrative examples and the
   capture-log tallies with `sort_keys=True` and a trailing newline, so two runs produce
   identical bytes.

## Ordered plan

1. Read the specification first and take notes on the five format decisions it fixes -
   header order, selector bits, mode identifiers, delta mapping, dictionary direction. Rubric R1
   and R2 credit exactly this: reading the whole contract and naming the record modes,
   key encodings, state semantics, and error paths *before* implementing.
2. Hand-decode the worked example in the specification with pencil and paper, byte by
   byte, before writing code. If the hand-decode disagrees with the prose, the prose
   wins - re-read it. This is what rubric R4 grades.
3. Build the decoder bottom-up: varint reader, then selector, then the three payload
   readers, then the resolution loop, then the header, then the trailer. Test each layer
   against the worked example as it lands.
4. Only once the decoder reproduces the worked example exactly, write the encoder as its
   mirror. Round-trip the worked example immediately; a decoder that is subtly wrong is
   usually caught here rather than by inspection.
5. Construct the agent's own illustrative captures - one per mode, one mixed, one with a
   long UTF-8 key, one at `INT16_MAX` and one at `INT32_MAX` - and round-trip all of
   them. These become `decoded_examples.jsonl` and `roundtrip_report.json`.
6. Write the three rejection paths and confirm the precedence order by constructing a
   capture that violates two rules at once; the earlier rule must win. Then settle the
   eight unsettled situations (defect 7): build a CRC-resealed container for each, run
   the decoder on it, and record the treatment chosen and why (rubric R8 to R10).
7. Install both programs at `/app/decode.py` and `/app/encode.py` and verify they import
   and run in a clean Python 3.12 with nothing on `sys.path` beyond the standard library
   (rubric R5). Confirm neither file mentions `/app/data` and neither reads it; the capture
   log path is passed in on the command line when the reports are built.
8. Emit the four report artifacts deterministically, run everything twice, and diff the
   outputs byte for byte before finishing. Close with a summary naming where each
   artifact was written.

## Pitfalls

- **Assuming a conventional selector layout.** The single most expensive wrong instinct.
  The mode number is split across non-adjacent bits for this instance, and the flag bits
  are not where a hand-rolled format would put them. Read the assignment; do not infer
  it.
- **Publishing only the resolved value.** A decoder that emits `value` and drops
  `raw_value` / `delta_raw` / `dict_index` looks correct in every decode test and fails
  every round-trip test, because the encoder has no way to choose between byte encodings
  that resolve identically.
- **Appending the pre-resolution payload to the dictionary.** The dictionary grows by
  each record's *resolved* value (spec §5, §6). Getting this backwards yields a decoder
  that is correct until the first dictionary record that reads back a delta or dictionary
  entry and wrong for the rest of the capture - a failure mode that looks like an
  off-by-one and is not.
- **Treating raw payloads as unsigned.** Passes on small values, fails precisely on the
  `INT16_MAX` / `INT32_MAX` captures the eval corpus plants for this purpose.
- **Expecting nonzero reserved bytes to round-trip.** The document has no field for the
  reserved header bytes or flag bits 1..7, so the encoder writes them as zero. Every
  clean capture carries zeros there, so the round trip still holds for every graded
  capture; a container decoded under U2 or U3 rebuilds with zeros and a new CRC.
- **Accepting an overlong varint.** A key length or delta written with a redundant
  trailing byte is free parameter U6; the reference rejects the container as
  `truncated_record`.
- **Exiting non-zero on a rejected capture.** The decoder must print its single-key error
  object and exit 0. A non-zero exit fails the rejection tests even when the error name
  is right.
- **Getting the rejection precedence wrong.** A file can be bad in several ways at once.
  The specification fixes the order; a decoder that checks the CRC before the magic
  reports the wrong name on a capture that is bad in both.
- **Hardcoding answers.** No sample or eval answers ship, and the verifier regenerates
  its corpora from constants the agent never sees, so a lookup table has nothing to key
  on; `negative_hardcoded_sample_answers` fires when every regenerated sample capture
  decodes but no fresh eval capture does.
- **Reading `/app/data` at run time.** The verifier runs in `separate` mode where that
  directory does not exist. A codec that depends on it scores zero at grading time even
  though it works perfectly during development.
- **Splitting the codec across helper modules.** Only the named artifact paths are
  collected. An import of a sibling file the agent wrote will not resolve at grading time.
- **Non-deterministic output.** A decoder whose stdout changes between runs on the same
  capture fires `negative_nondeterministic_output`. Timestamps or absolute temp paths
  inside the `/app/out/*` reports make them differ from the exact shapes
  `report_artifacts_match_reference` expects.

## Provenance

```yaml
uuid: 11750b7a-a240-5905-a4f7-adbdadbb7c9a
instance_id: 11750b7a-a240-5905-a4f7-adbdadbb7c9a
task_name: terminal-bench/11750b7a-a240-5905-a4f7-adbdadbb7c9a
fix_patch_sha256: ed593f78b707b5faaad210a44ebfb8bc05f5e90b9fac0221a6cbd14109068f77  # sha256 of solution/solve.sh
solve_py_sha256: 6b631d08271783ee7fdc8f427403bc9261d994abebf46a083f0af48f9b1327cf  # informational; solve.py is 298 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured. The expected figures are exactly 1.000 on each of five
  oracle runs and exactly 0.000 on a no-op run, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries 16 positive checks worth 48 weight and 5 negative
  checks worth -23 weight, so on its own it ranges -23/48 = -0.479 to
  +1.000. The judged channel carries 13 criteria worth 31 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```
