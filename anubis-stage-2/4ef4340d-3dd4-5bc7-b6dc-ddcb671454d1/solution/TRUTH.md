# TRUTH.md - 4ef4340d-3dd4-5bc7-b6dc-ddcb671454d1

## Defect

No source of a working codec ships anywhere in this instance. `/app/data/` holds
six flat written reference files describing `POLYP`, a binary record container produced
by the Quadrature evaluation grid, plus `POLYP-capture-log.jsonl`, 20,000 field captures
as hex with no decodings. There is no reference decoder and no worked answer key beyond
the examples embedded in the prose. The agent must derive the entire grammar from that
written material and deliver
both halves of the codec: a decoder at `/app/decode.py` that turns a capture into one
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
   appended is the record's resolved `value` (spec §6), not its pre-resolution payload
   (`raw_value`, `delta_raw`, or `dict_index`). Confusing the two produces a decoder that
   is correct until a dictionary index lands on an entry left by a delta or dictionary
   record, and wrong from there on.
3. (focal) The encoder must be byte-exact, not merely semantically equivalent. The
   header field order, the flag bit, the selector bits, and the varint widths all have to
   come back exactly, which is why the decoded document carries pre-resolution payload
   fields at all. The document carries flag bit 0 only, so the encoder writes the
   reserved header bytes and the spare selector bits as zero and every varint at its
   minimal width; every well-formed capture (the capture log and the hidden corpora alike)
   satisfies `encode(decode(b)) == b`. Containers the decoder accepts under the open
   situations U2, U3, U5 and U7 below decode but cannot be rebuilt byte for byte, because
   the document has no field for the bytes those situations carry.
4. (drift) The selector byte does not have the layout an experienced reader expects - the
   mode number, the wide-value flag, and the long-key flag sit at instance-specific bit
   positions, spelled out under *Selector layout* in the Root cause section below. An
   agent that assumes "mode lives in the low two bits" mis-reads the worked examples and
   the captures alike. The specification states the mapping; the instinct contradicts it.
5. (trap) Raw payloads are **signed** `i16` and `i32`. The eval corpus deliberately
   includes magnitudes near `INT16_MAX` and `INT32_MAX` and negative payloads, so an
   implementation that unpacks the payload as unsigned passes the small-value fixtures and
   fails `decodes_raw_and_key_forms` (its raw i16, raw i32 and large-magnitude sub-checks)
   along with the other checks whose fixtures hold negative raw payloads.
6. (trap) The trailer CRC covers the header fields after the magic bytes, followed by the
   body (spec §8; the empty container in spec §9 confirms it). A decoder that runs the
   CRC over the whole file prefix including the magic, or over the body alone, reports
   `trailer_crc_mismatch` for every valid capture, and an encoder making the same mistake
   writes a trailer no correct decoder accepts.

The reference is authored in Python (Python 3.12, standard library only,
298-line single-file codec) with a Bash oracle dispatcher
(`solve.sh`) that installs the same module at both `/app/decode.py` and
`/app/encode.py` and then emits the four report artifacts. A deterministic channel
observes the delivered programs (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric channel grades the derivation trajectory
(Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the prose
above - read them from those files, or from the lists below which mirror them.

Out of bounds: reading anything under `/app/data/` while `decode.py` or `encode.py` runs
(`negative_reads_training_corpus_at_runtime`); importing helper modules the
agent writes alongside the two entry points, which will not be collected; keying
behaviour on the input filename (`negative_filename_dependent_behaviour`);
rebinding `open`, `zlib.crc32`, or `struct.unpack`
(`negative_rebinds_verifier_dependencies`); emitting different bytes for the
same input across two runs (`negative_nondeterministic_output`); a decoder
that reproduces the verifier's 24-capture raw-only sample tier while getting none of the
fresh eval captures right, the signature of answers keyed to a fixed set rather than
decoded (`negative_hardcoded_sample_answers`; no sample answers ship to the agent);
installing third-party packages; and looking the format up online - `POLYP` is
invented for this instance and nothing about it exists outside this bundle.

## Load-bearing work

6 artifacts are collected, and every one of them is graded:

- `/app/decode.py`
- `/app/encode.py`
- `/app/out/decoded_examples.jsonl`
- `/app/out/format_report.json`
- `/app/out/roundtrip_report.json`
- `/app/out/error_analysis.json`

- `/app/decode.py` (new) - invoked as `python3 /app/decode.py <input.vcm>`.
  Prints exactly one JSON object on stdout, nothing else, and exits 0 even when the
  capture is rejected. On rejection it prints the error object the specification defines
  (`{"error": ...}`, plus `version` for `unsupported_version`), honouring the documented
  precedence.
- `/app/encode.py` (new) - invoked as
  `python3 /app/encode.py <document.json> <output.vcm>`. Consumes the decoder's
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

`/app/data/POLYP-capture-log.jsonl` ships 20,000 field captures as hex, about
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
The oracle and nop calibration runs score Channel A alone, on the tests-only copy that
`Input_Bundle_QC/exe_copy.py` builds; Channel B has no oracle score.

Channel A declares 16 positive and 5 negative tests, positive weight total
48 and negative weight total -23, so the
theoretical reward range is -23/48 = -0.479 to +1.000.

Positive tests (each grouped test passes only when every listed check holds):

- `decoder_and_single_json_output` (weight 1): decode.py/encode.py exist, one JSON object per run
- `decodes_raw_and_key_forms` (weight 1): raw i32/i16, large magnitude, short and long keys
- `decodes_delta_dict_and_mixed` (weight 1): delta, dict, mixed modes from the eval corpus
- `classifies_header_damage_in_order` (weight 1): bad_magic, unsupported_version, bad crc, precedence
- `encoder_round_trips` (weight 1): labelled samples and eval corpus byte-exact
- `record_order_and_payload_fields` (weight 1): record count/file order, pre-resolution payload fields
- `report_artifacts_match_reference` (weight 1): the four /app/out artifacts
- `reproduces_labelled_sample_answers` (weight 1): the verifier's 24 raw-only, short-key sample captures (built from `SAMPLE_SEED`; none ships to the agent) decode to the expected documents
- `unknown_flag_bits_reject_container` (weight 5): U1, flag bits 1..7 set -> truncated_record
- `nonzero_reserved_header_bytes_are_ignored` (weight 5): U2, reserved header bytes 13..15 nonzero -> decoded normally
- `reserved_selector_bits_are_ignored` (weight 5): U3, selector bits outside the mode, WIDE and LONG_KEY bits set -> decoded by mode bits
- `wide_bit_on_delta_or_dict_rejects_container` (weight 5): U4, WIDE on delta/dict -> truncated_record
- `bytes_after_last_record_are_ignored` (weight 5): U5, slack bytes before trailer -> decoded normally
- `overlong_varint_rejects_container` (weight 5): U6, redundant trailing varint byte -> truncated_record
- `invalid_utf8_long_key_uses_replacement_character` (weight 5): U7, invalid UTF-8 long key decoded with U+FFFD
- `container_shorter_than_header_and_trailer_fails_crc` (weight 5): U8, file shorter than header+trailer (fixtures cut to 14/16/19 bytes) -> trailer_crc_mismatch; the reference applies the same answer to any file with a correct magic that is cut before its version byte

Negative tests (5) are polarity-inverted: their assertions hold
only when the cheat is present, so an honest run leaves them "failing" and contributes
zero weight. They subtract only from a solver that actually cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_rebinds_verifier_dependencies` (weight -5)
- `negative_nondeterministic_output` (weight -3)

Channel B is 13 criteria (11 positive / 2 negative), positive total 31:

- **R1** (+1): reads the complete POLYP-container-format.md before implementing.
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

The verifier regenerates every corpus it grades against on each run from constants in
`tests/test_output.py`: the eval corpus from `EVAL_SEED = 4612699244913462795`, the
labelled sample tier from `SAMPLE_SEED = 5529642094207996685` (the shipped capture log is
rebuilt from `SAMPLE_SEED ^ 0x5EED5EED`), and the field tier from
`CHALLENGE_SEED = 763925621974729790`. Apart from the capture log's hex, none of these
captures or their decodings ships to the agent. The verifier writes them into
seed-specific temporary directories so it works under harbor's `separate` verifier mode,
where `/app/data/` is not propagated. The oracle expectation is that running
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
`record_order_and_payload_fields` checks for them on every record.

**The state machine.** Records are resolved left to right against a single running value and a dictionary that grows by one entry per record. The running value starts at the header `base_value`.

- **raw** replaces the running value with the record's signed payload;
- **delta** adds its signed delta to the running value (§4);
- **dictionary** replaces the running value with the selected dictionary entry (§5).

Immediately after each record is resolved, the record's resolved value is appended to the dictionary, so the Nth record (counting from zero) is read against a dictionary holding exactly N entries. The running value left behind by a record is that record's resolved `value`.

**Delta encoding.** A record whose selector mode number is `1` is a **delta** record. Its payload is one signed integer delta.

The signed delta is zig-zag mapped (`n >= 0` becomes `2n`, `n < 0` becomes `2|n| - 1`) and then written as an unsigned LEB128 varint: 7 data bits per byte, least-significant group first, high bit set on every byte except the last. For example a delta of `-3` maps to zig-zag `5`, a single byte `05`.

The delta updates the running value described in §6 (`running = running + delta`); the new running value is the record's resolved `value`. The raw delta, before it is applied, is reported as `delta_raw`.

**Dictionary resolution.** A record whose selector mode number is `2` is a **dictionary** record. Its payload is one unsigned byte, the *payload index*.

The dictionary grows as records are resolved: the resolved value of every preceding record is appended to it (see §6). When a dictionary record is read, the actual entry is `(dictionary_length - 1) - payload_index`, i.e. counted from the back of the dictionary built so far. The entry found there becomes both the record's resolved `value` and the new running value; a payload index outside the current dictionary is a `truncated_record` error. The payload index exactly as written is reported as `dict_index`.

**Why the grammar is instance-specific.** The header field order, selector bit assignment, mode
identifiers, delta encoding, dictionary direction, and CRC coverage are all specific to this task
instance. This is the whole point of the task: it forecloses recall. No amount
of prior exposure to binary container formats supplies the answer, and there is no public
`POLYP` to look up. The only path to a passing solution runs through reading the
shipped specification. For this instance the recovered grammar is:

`{"crc_coverage": "header_records", "delta_encoding": "zigzag_uvarint", "dictionary": {"direction": "backward", "source": "resolved_values"}, "header_order": ["base_value", "record_count", "flags", "version", "reserved"], "selector": {"long_key_bit": 7, "mode_bits": [2, 5], "mode_ids": {"delta": 1, "dict": 2, "raw": 0}, "wide_bit": 0}}`

**Header layout for this instance.**

| offset  | width   | field         | notes |
|---------|---------|---------------|-------|
| 0..4    | 5 bytes | magic         | ASCII bytes `4e 55 4d 50 4b`. Any other value is `bad_magic` (§7). |
| 5..8    | i32 LE  | base_value    | Signed initial value used by some record modes. See §4. |
| 9..10   | u16 LE  | record_count  | Number of records that follow in the body. |
| 11      | u8      | flags         | Reserved flag byte. Bit 0 has meaning; bits 1..7 must be `0`. See §6. |
| 12      | u8      | version       | Must be `1`. Any other value is `unsupported_version` (§7). |
| 13..15  | 3 bytes | reserved      | Must be `0x00 0x00 0x00`. The trailer (§8) binds these bytes when the bundle uses full-prefix CRC coverage. |

**Selector layout for this instance.**

- bits `2` and `5` carry the payload **mode** number (`0` = raw, `1` = delta, `2` = dictionary). The lower listed bit contributes value 1 and the higher listed bit contributes value 2.
- bit `0` carries the `WIDE_VALUE` flag (raw mode only): `1` = 32-bit payload, `0` = 16-bit.
- bit `7` carries the `LONG_KEY` flag: `1` = varint-length UTF-8 key, `0` = 1-byte key.
- bits `1, 3, 4, 6` must be `0`.

**Red lines.** No runtime read of `/app/data`; no filename-conditioned behaviour; no
rebinding of `open` / `zlib.crc32` / `struct.unpack`; no non-determinism across runs; no
hidden-corpus answers baked into the `/app/out/*` artifacts; no third-party packages; no
online lookup.

## Solution shape

1. Read `/app/data/POLYP-container-format.md` end to end before writing a line,
   then the supporting files - the decoder appendix, the encoder notes, the error-code
   reference, the varint/CRC primer, and the glossary. Deciding which file answers which
   question is part of the task.
2. Transcribe the header into a single parse function: magic `b"NUMPK"`
   (`4e 55 4d 50 4b`), version `1`, then the five post-magic fields in the
   order the specification gives, which is not the order the field names suggest.
3. Implement the selector decode as a bit-mask table derived from the spec's own
   assignment, not from a guessed layout. Settle the bits the specification says must be
   zero the way the reference does: flag bits 1..7 set reject the container as
   `truncated_record` (U1), while spare selector bits and nonzero reserved header bytes
   are ignored (U3, U2).
4. Implement the three payload readers - raw (signed, width from the wide flag), delta
   (varint, then the documented signed mapping), dictionary (index, then the documented
   direction) - each returning both its pre-resolution payload and the resolved value.
5. Implement the resolution loop: one running value seeded from `base_value`, one
   dictionary appended to once per record with the record's resolved value, and
   left-to-right ordering that never looks ahead.
6. Implement the trailer check with `zlib.crc32` over the documented coverage region, and
   the rejection precedence `bad_magic` → `unsupported_version` →
   `trailer_crc_mismatch` → `truncated_record`, exiting 0 on every one of them.
7. Write the encoder as the literal inverse of each reader: flag bit 0 from
   `reserved_bit_0`, reserved header bytes and spare selector bits as zero, and every
   varint at its minimal width. Verify `encode(decode(b)) == b` on every decodable capture
   in the log and on every example the agent builds.
8. Emit the four `/app/out/*` reports from the agent's own illustrative examples with
   `sort_keys=True` and a trailing newline, so two runs produce identical bytes.

## Ordered plan

1. Read the specification first and take notes on the five decisions that vary - header
   order, selector bits, mode identifiers, delta mapping, dictionary direction. Rubric R1
   and R2 credit exactly this: reading the whole contract and naming the record modes,
   key encodings, state semantics, and error paths *before* implementing.
2. Hand-decode a container byte by byte, CRC included, before trusting the code, and
   compare it with the decoder's output (rubric R11). Check the decoder against the
   worked examples in specification §9 (rubric R4). If the hand-decode disagrees with
   the prose, the prose wins - re-read it.
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
   capture that violates two rules at once; the earlier rule must win.
7. List the situations the specification and its companion notes leave open, pick a
   treatment for each with the reason for it over the alternative (rubrics R8, R9), then
   build CRC-resealed containers that exercise each one and run the decoder on them
   (rubrics R10, R12, R13). The reference treatments are listed under *Open situations*
   below.
8. Install both programs at `/app/decode.py` and `/app/encode.py` and verify they import
   and run in a clean Python 3.12 with nothing on `sys.path` beyond the standard library
   (rubric R5). Confirm neither file mentions `/app/data` and neither reads it; the capture
   log path is passed in on the command line when the reports are built.
9. Emit the four report artifacts deterministically, run everything twice, and diff the
   outputs byte for byte before finishing. Close with a summary naming where each
   artifact was written.

## Pitfalls

- **Assuming a conventional selector layout.** The single most expensive wrong instinct.
  The mode number is split across non-adjacent bits for this instance, and the flag bits
  are not where a hand-rolled format would put them. Read the assignment; do not infer
  it.
- **Publishing only the resolved value.** A decoder that emits `value` and drops
  `raw_value` / `delta_raw` / `dict_index` fails the decode tests, which compare every
  key, and leaves the encoder no way to choose between byte encodings that resolve
  identically.
- **Appending the pre-resolution payload to the dictionary.** The dictionary grows by
  each record's resolved `value` (spec §6). Getting this backwards yields a decoder that
  stays correct until a dictionary index lands on an entry left by a delta or dictionary
  record, and is wrong from there on.
- **Treating raw payloads as unsigned.** Passes on small values, fails precisely on the
  `INT16_MAX` / `INT32_MAX` captures the eval corpus plants for this purpose.
- **Running the CRC over the wrong region.** The trailer covers the header fields after
  the magic plus the body. Including the magic, or covering the body alone, turns every
  valid capture into `trailer_crc_mismatch`.
- **Accepting an overlong varint.** A key length or delta written with a redundant
  trailing byte is open situation U6; the reference rejects the container as
  `truncated_record`.
- **Exiting non-zero on a rejected capture.** The decoder must print its error object
  and exit 0. A non-zero exit fails the rejection tests even when the error name is
  right.
- **Getting the rejection precedence wrong.** A file can be bad in several ways at once.
  The specification fixes the order; a decoder that checks the CRC before the magic
  reports the wrong name on a capture that is bad in both.
- **Keying answers to a fixed capture set.** No decoded answers ship, so there is
  nothing to hardcode; a decoder that reproduces the verifier's sample tier while failing
  every fresh eval capture trips `negative_hardcoded_sample_answers`.
- **Reading `/app/data` at run time.** The verifier runs in `separate` mode where that
  directory does not exist. A codec that depends on it scores zero at grading time even
  though it works perfectly during development.
- **Naming the data directory inside the programs.** `negative_reads_training_corpus_at_runtime`
  fires on any string constant in `decode.py` or `encode.py` that contains the data
  directory path, docstrings and default arguments included. Pass the capture-log path on
  the command line instead.
- **Splitting the codec across helper modules.** Only the named artifact paths are
  collected. An import of a sibling file the agent wrote will not resolve at grading time.
- **Non-deterministic decoder output.** Anything that varies between runs (unsorted
  set iteration, timestamps, randomness) trips `negative_nondeterministic_output`, which
  decodes one capture four times and compares the results. The `/app/out/*` reports are
  collected once, so keep them deterministic for the instruction's sake rather than for
  a check.

## Provenance

```yaml
uuid: 4ef4340d-3dd4-5bc7-b6dc-ddcb671454d1
instance_id: 4ef4340d-3dd4-5bc7-b6dc-ddcb671454d1
task_name: terminal-bench/4ef4340d-3dd4-5bc7-b6dc-ddcb671454d1
fix_patch_sha256: e7370121d657f4f5928add51ff3d1e5d3302962f4177031e05d555aba7e9d261  # sha256 of solution/solve.sh
solve_py_sha256: f6370c3c72fde3424b804a05e9f21175c3f8c859599987599c4fdb03668ac5c9  # informational; solve.py is 298 lines
language: python
golden_score_measured: 1.0  # test channel only, on the tests-only copy exe_copy.py builds
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null  # the judged channel has no oracle score
golden_score_runs: 2
golden_score_trial_id: null  # local QC calibration, 2026-10-26
golden_score_verified_by: >
  Two oracle runs read exactly 1.000 each, the no-op run 0.000 and the
  owner-only oracle run 1.000, on the test channel in tests/test_output.py
  only; the judged channel has no oracle score. The full calibration
  standard is five oracle runs at exactly 1.000.
caveat: >
  The test channel carries 16 positive checks worth 48 weight and 5 negative
  checks worth -23 weight, so on its own it ranges -23/48 = -0.479 to
  +1.000. The judged channel carries 13 criteria worth 31 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```

## Open situations

The instruction says eight situations are settled by neither the specification nor its
companion notes; it gives the count only. Each is a weight-5 test, and R12/R13 grade the
exercised treatment of U2/U3 and U7 in the trajectory. The reference treatments:

| id | situation | reference treatment |
|----|-----------|---------------------|
| U1 | flag bits 1..7 set | reject as `truncated_record` |
| U2 | reserved header bytes 13..15 nonzero | ignore, decode normally |
| U3 | selector bits 1, 3, 4, 6 set | ignore, decode by the mode bits |
| U4 | WIDE bit set on a delta or dictionary record | reject as `truncated_record` |
| U5 | spare bytes between the last record and the trailer | ignore, decode normally |
| U6 | overlong varint (redundant trailing byte) in a key length or delta | reject as `truncated_record` |
| U7 | long key that is not valid UTF-8 | decode with U+FFFD replacement characters |
| U8 | file with a correct magic shorter than header plus trailer | `trailer_crc_mismatch` |

U8 follows from specification §7 (magic and version are correct, or the version byte is
missing, and the trailer check cannot pass). U1, U4 and U6 match a decoder that rejects
every "must be 0" violation and every encoding its encoder could not reproduce. U2, U3,
U5 and U7 go the other way: the specification says the reserved bytes and spare selector
bits must be zero, and no shipped file states that they, trailing slack or an undecodable
key are tolerated. A decoder that rejects those four containers instead scores 28/48 on
the test channel.
