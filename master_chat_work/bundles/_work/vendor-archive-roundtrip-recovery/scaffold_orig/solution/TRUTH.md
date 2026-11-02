# TRUTH.md - vendor-archive-roundtrip-recovery

## Defect

No source of a working codec ships anywhere in this instance. `/app/data/` holds
7 flat written reference files describing `VARC`, a
seeded binary record container produced by PIPE-8 staging service, and nothing else - no
capture, no reference decoder, no worked answer key beyond the examples embedded in the
prose. The agent must derive the entire grammar from that written material and deliver
both halves of the codec: a decoder at `/app/decode.py` that turns a capture into one
JSON document, and an encoder at `/app/encode.py` that turns that same document back
into the original bytes. The grammar is redrawn from generator seed `00000000000457c3`, so
every published property below is instance-specific and cannot be recalled from
training.

1. (focal) Three payload modes must all work. Raw is the easy one; **delta** (spec §4)
   and **dictionary** (spec §5) carry the weight. A solver that implements raw only
   answers fewer than half of the positive tests, because the hidden corpus mixes modes
   inside a single capture and the running value threads through all three.
2. (focal) The resolution state machine (spec §6) is stateful and order-sensitive.
   Records resolve left to right against one running value seeded from the header
   `base_value`, and the dictionary grows by exactly one entry per record. The entry
   appended is the record's **pre-resolution payload** - `raw_value`, `delta_raw`, or
   `dict_index` - not the resolved `value`. Confusing the two produces a decoder that is
   correct on the first divergence and wrong on everything after it.
3. (focal) The encoder must be byte-exact, not merely semantically equivalent. The
   header field order, the flag byte, the three reserved bytes, and the varint widths
   chosen by the original writer all have to come back unchanged, which is why the
   decoded document carries pre-resolution payload fields at all. `encode(decode(b))`
   must equal `b` for every capture, including the hidden ones.
4. (drift) The selector byte does not have the layout an experienced reader expects - the
   mode number, the wide-value flag, and the long-key flag sit at seed-drawn bit
   positions, spelled out under *Selector layout* in the Root cause section below. An
   agent that assumes "mode lives in the low two bits" decodes the visible worked
   examples correctly by luck on some seeds and silently mis-reads every capture on
   others. The specification states the mapping; the instinct contradicts it.
5. (trap) Raw payloads are **signed** `i16` and `i32`. The eval corpus deliberately
   includes magnitudes near `INT16_MAX` and `INT32_MAX`, so an implementation that
   unpacks the payload as unsigned passes the small-value tests and fails
   `decodes_large_magnitude_signed` and `decodes_raw_i32_from_eval`
   specifically.
6. (trap) The trailer CRC covers the header fields after the magic bytes, followed by the body. That region includes the flag byte
   and the reserved bytes verbatim. A "helpful" encoder that normalises reserved bytes
   to zero, or that recomputes flags from the decoded document instead of replaying the
   observed byte, produces a file that differs from the original in the CRC and fails
   every round-trip test while looking perfectly reasonable in a diff of the decoded
   JSON.

The reference is authored in Python (Python 3.12, standard library only,
290-line single-file codec) with a Bash oracle dispatcher
(`solve.sh`) that installs the same module at both `/app/decode.py` and
`/app/encode.py` and then emits the four report artifacts. A deterministic channel
observes the delivered programs (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric channel grades the derivation trajectory
(Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the prose
above - read them from those files, or from the lists below which are generated from
them.

Out of bounds: reading anything under `/app/data/` while `decode.py` or `encode.py` runs
(`negative_reads_training_corpus_at_runtime`); importing helper modules the
agent writes alongside the two entry points, which will not be collected; keying
behaviour on the input filename (`negative_filename_dependent_behaviour`);
rebinding `open`, `zlib.crc32`, or `struct.unpack`
(`negative_rebinds_verifier_dependencies`); emitting different bytes for the
same input across two runs (`negative_nondeterministic_output`); embedding
the visible sample answers as literals (`negative_hardcoded_sample_answers`);
installing third-party packages; and looking the format up online - `VARC` is
invented for this instance and nothing about it exists outside this bundle.

## Load-bearing work

6 artifacts are collected, and every one of them is graded:

- `/app/decode.py`
- `/app/encode.py`
- `/app/out/decoded_examples.jsonl`
- `/app/out/format_report.json`
- `/app/out/roundtrip_report.json`
- `/app/out/error_analysis.json`

- `/app/decode.py` (new) - invoked as `python3 /app/decode.py <input.varc>`.
  Prints exactly one JSON object on stdout, nothing else, and exits 0 even when the
  capture is rejected. On rejection it prints a single-key error object using the error
  name the specification defines, honouring the documented precedence.
- `/app/encode.py` (new) - invoked as
  `python3 /app/encode.py <document.json> <output.varc>`. Consumes the decoder's
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

`/app/data/VARC-capture-log.jsonl` ships 20,000 field captures as hex, about
9% damaged (bad magic, unsupported version, trailer CRC). The verifier regenerates the
same log from its own generator (`capture_log()`), so the tallies are checked against
ground truth; decoding all of them is the large-input half of the task, and only a
decoder that follows the specification's precedence gets the error tally right. Deleting
the log makes those two reports impossible to produce; the playground's ablation run
measures this.

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

Channel A declares 24 positive and 5 negative tests, positive weight total
72 and negative weight total -23, so the
theoretical reward range is -23/72 = -0.319 to +1.000.

Positive tests (24):

- `decoder_exists` (weight 1)
- `encoder_exists` (weight 1)
- `output_is_single_json_object` (weight 1)
- `reproduces_labelled_sample_answers` (weight 5)
- `decodes_raw_i32_from_eval` (weight 3)
- `decodes_raw_i16_from_eval` (weight 3)
- `decodes_delta_from_eval` (weight 5)
- `decodes_dict_from_eval` (weight 5)
- `decodes_mixed_modes_from_eval` (weight 5)
- `decodes_large_magnitude_signed` (weight 5)
- `decodes_long_keys` (weight 3)
- `rejects_bad_magic` (weight 3)
- `rejects_unsupported_version` (weight 3)
- `rejects_bad_crc` (weight 3)
- `magic_precedes_version_precedes_crc` (weight 1)
- `encoder_round_trips_labelled_samples` (weight 3)
- `encoder_round_trips_eval_corpus` (weight 3)
- `record_count_matches_and_file_order` (weight 1)
- `pre_resolution_payload_fields_present` (weight 3)
- `decodes_short_keys_from_eval` (weight 3)
- `decoded_examples_artifact_matches_visible_reference` (weight 3)
- `format_report_artifact_matches_reference` (weight 3)
- `roundtrip_report_artifact_matches_reference` (weight 3)
- `error_analysis_artifact_matches_reference` (weight 3)

Negative tests (5) are polarity-inverted: their assertions hold
only when the cheat is present, so an honest run leaves them "failing" and contributes
zero weight. They subtract only from a solver that actually cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_rebinds_verifier_dependencies` (weight -5)
- `negative_nondeterministic_output` (weight -3)

Channel B is 12 criteria (10 positive / 2 negative), positive total 34:

- **R1** (+3, trajectory): The agent reads the complete /app/data/VARC-container-format.md specification before implementing decode.py or encode.py.
- **R2** (+3, trajectory): The agent identifies the record modes, key encodings, state and dictionary semantics, and error paths defined in the specification before implementing.
- **R3** (+3, trajectory): The agent derives the decoder and byte-exact encoder behaviour from the complete written specification and its worked examples.
- **R4** (+5, trajectory): The agent implements raw mode, delta mode, dictionary mode, and the running-value and state semantics described in sections 4 through 6.
- **R5** (+5, trajectory): The agent handles delta records, dictionary records, long UTF-8 keys, and signed i16/i32 boundary values as the specification defines.
- **R6** (+3, trajectory): The agent validates decoder behaviour against the worked examples embedded in the shipped specification.
- **R7** (+3, trajectory): The agent verifies decode.py and encode.py imports in a clean Python 3.12 session.
- **R8** (-5, trajectory): The agent mutates the specification text, verifier assets, or reward files to influence evaluation outcomes.
- **R9** (-5, trajectory): The agent retrieves a task-specific implementation, prior submission, or reference solution from an external source.
- **R10** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R11** (+3, trajectory): The agent implements exactly decode.py and encode.py at the paths the instruction names and adds no auxiliary or renamed modules.
- **R12** (+3, trajectory): The agent limits its implementation to Python standard-library facilities as the instruction requires, refusing to introduce third-party packages.

The hidden corpus is reseeded on every run from `EVAL_SEED = 1592153744120012122`, distinct
from the visible `SAMPLE_SEED = 6842771334212724028` and the labelled
`CHALLENGE_SEED = 7392569321898501261`. The verifier rebuilds it into a seed-specific
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
`pre_resolution_payload_fields_present` exists as its own weighted check.

**The state machine.** Records are resolved left to right against a single running value and a dictionary that grows by one entry per record. The running value starts at the header `base_value`.

- **raw** replaces the running value with the record's signed payload;
- **delta** adds its signed delta to the running value (§4);
- **dictionary** replaces the running value with the selected dictionary entry (§5).

Immediately after each record is resolved, the record's resolved value is appended to the dictionary, so the Nth record (counting from zero) is read against a dictionary holding exactly N entries. The running value left behind by a record is that record's resolved `value`.

**Delta encoding.** A record whose selector mode number is `2` is a **delta** record. Its payload is one signed integer delta.

The signed delta is written as signed LEB128: 7 data bits per byte, least-significant group first, high bit set on every byte except the last, and the payload is sign-extended from the final byte. For example a delta of `-3` is the single byte `7d`.

The delta updates the running value described in §6 (`running = running + delta`); the new running value is the record's resolved `value`. The raw delta, before it is applied, is reported as `delta_raw`.

**Dictionary resolution.** A record whose selector mode number is `0` is a **dictionary** record. Its payload is one unsigned byte, the *payload index*.

The dictionary grows as records are resolved: the resolved value of every preceding record is appended to it (see §6). When a dictionary record is read, the actual entry is `(dictionary_length - 1) - payload_index`, i.e. counted from the back of the dictionary built so far. The entry found there becomes both the record's resolved `value` and the new running value; a payload index outside the current dictionary is a `truncated_record` error. The payload index exactly as written is reported as `dict_index`.

**Why the grammar is seeded.** The header field order, selector bit assignment, mode
identifiers, delta encoding, dictionary direction, and CRC coverage are all drawn from
`00000000000457c3`. This is the whole point of the archetype: it forecloses recall. No amount
of prior exposure to binary container formats supplies the answer, and there is no public
`VARC` to look up. The only path to a passing solution runs through reading the
shipped specification. For this instance the recovered grammar is:

`{"crc_coverage": "header_records", "delta_encoding": "signed_leb128", "dictionary": {"direction": "backward", "source": "resolved_values"}, "header_order": ["record_count", "reserved", "version", "flags", "base_value"], "selector": {"long_key_bit": 7, "mode_bits": [2, 3], "mode_ids": {"delta": 2, "dict": 0, "raw": 1}, "wide_bit": 1}}`

**Header layout for this instance.**

| offset  | width   | field         | notes |
|---------|---------|---------------|-------|
| 0..4    | 5 bytes | magic         | ASCII bytes `50 49 50 45 31`. Any other value is `bad_magic` (§7). |
| 5..6    | u16 LE  | record_count  | Number of records that follow in the body. |
| 7..9    | 3 bytes | reserved      | Must be `0x00 0x00 0x00`. The trailer (§8) binds these bytes when the bundle uses full-prefix CRC coverage. |
| 10      | u8      | version       | Must be `5`. Any other value is `unsupported_version` (§7). |
| 11      | u8      | flags         | Reserved flag byte. Bit 0 has meaning; bits 1..7 must be `0`. See §6. |
| 12..15  | i32 LE  | base_value    | Signed initial value used by some record modes. See §4. |

**Selector layout for this instance.**

- bits `2` and `3` carry the payload **mode** number (`1` = raw, `2` = delta, `0` = dictionary). The lower listed bit contributes value 1 and the higher listed bit contributes value 2.
- bit `1` carries the `WIDE_VALUE` flag (raw mode only): `1` = 32-bit payload, `0` = 16-bit.
- bit `7` carries the `LONG_KEY` flag: `1` = varint-length UTF-8 key, `0` = 1-byte key.
- bits `0, 4, 5, 6` must be `0`.

**Red lines.** No runtime read of `/app/data`; no filename-conditioned behaviour; no
rebinding of `open` / `zlib.crc32` / `struct.unpack`; no non-determinism across runs; no
hidden-corpus answers baked into the `/app/out/*` artifacts; no third-party packages; no
online lookup.

## Solution shape

1. Read `/app/data/VARC-container-format.md` end to end before writing a line,
   then the supporting files - the decoder appendix, the encoder notes, the error-code
   reference, the varint/CRC primer, and the glossary. Deciding which file answers which
   question is part of the task.
2. Transcribe the header into a single parse function: magic `b"PIPE1"`
   (`50 49 50 45 31`), version `5`, then the five post-magic fields in the
   order the specification gives, which is not the order the field names suggest.
3. Implement the selector decode as a bit-mask table derived from the spec's own
   assignment, not from a guessed layout. Assert that the bits the specification requires
   to be zero really are zero.
4. Implement the three payload readers - raw (signed, width from the wide flag), delta
   (varint, then the documented signed mapping), dictionary (index, then the documented
   direction) - each returning both its pre-resolution payload and the resolved value.
5. Implement the resolution loop: one running value seeded from `base_value`, one
   dictionary appended to once per record with the pre-resolution payload, and left-to-
   right ordering that never looks ahead.
6. Implement the trailer check with `zlib.crc32` over the documented coverage region, and
   the rejection precedence `bad_magic` → `unsupported_version` →
   `trailer_crc_mismatch` → `truncated_record`, exiting 0 on every one of them.
7. Write the encoder as the literal inverse of each reader, replaying the observed flag
   and reserved bytes rather than recomputing them, and re-emitting varints at the width
   the payload requires. Verify `encode(decode(b)) == b` on every example the agent
   builds.
8. Emit the four `/app/out/*` reports from the agent's own illustrative examples with
   `sort_keys=True` and a trailing newline, so two runs produce identical bytes.

## Ordered plan

1. Read the specification first and take notes on the five decisions that vary - header
   order, selector bits, mode identifiers, delta mapping, dictionary direction. Rubric R1
   and R2 credit exactly this: reading the whole contract and naming the record modes,
   key encodings, state semantics, and error paths *before* implementing.
2. Hand-decode the worked example in the specification with pencil and paper, byte by
   byte, before writing code. If the hand-decode disagrees with the prose, the prose
   wins - re-read it. This is what rubric R6 grades.
3. Build the decoder bottom-up: varint reader, then selector, then the three payload
   readers, then the resolution loop, then the header, then the trailer. Test each layer
   against the worked example as it lands.
4. Only once the decoder reproduces the worked example exactly, write the encoder as its
   mirror. Round-trip the worked example immediately; a decoder that is subtly wrong is
   usually caught here rather than by inspection.
5. Construct the agent's own illustrative captures - one per mode, one mixed, one with a
   long UTF-8 key, one at `INT16_MAX` and one at `INT32_MAX` - and round-trip all of
   them. These become `decoded_examples.jsonl` and `roundtrip_report.json`. Rubric R5
   grades exactly these boundary cases.
6. Write the three rejection paths and confirm the precedence order by constructing a
   capture that violates two rules at once; the earlier rule must win.
7. Install both programs at `/app/decode.py` and `/app/encode.py` and verify they import
   and run in a clean Python 3.12 with nothing on `sys.path` beyond the standard library
   (rubric R7). Confirm neither file mentions `/app/data` and neither reads it; the capture
   log path is passed in on the command line when the reports are built.
8. Emit the four report artifacts deterministically, run everything twice, and diff the
   outputs byte for byte before finishing. Close with a summary naming where each
   artifact was written (rubric R10).

## Pitfalls

- **Assuming a conventional selector layout.** The single most expensive wrong instinct.
  The mode number is split across non-adjacent bits for this instance, and the flag bits
  are not where a hand-rolled format would put them. Read the assignment; do not infer
  it.
- **Publishing only the resolved value.** A decoder that emits `value` and drops
  `raw_value` / `delta_raw` / `dict_index` looks correct in every decode test and fails
  every round-trip test, because the encoder has no way to choose between byte encodings
  that resolve identically.
- **Appending the resolved value to the dictionary.** The dictionary grows by the
  *pre-resolution* payload. Getting this backwards yields a decoder that is correct until
  the first dictionary record and wrong for the rest of the capture - a failure mode that
  looks like an off-by-one and is not.
- **Treating raw payloads as unsigned.** Passes on small values, fails precisely on the
  `INT16_MAX` / `INT32_MAX` captures the eval corpus plants for this purpose.
- **Normalising the flag byte or the reserved bytes on encode.** They are inside the CRC
  coverage region. Replay them; do not clean them up.
- **Recomputing varint widths canonically.** If the original writer used a wider varint
  than strictly necessary, a canonicalising encoder produces a shorter file and loses the
  round-trip. Replay the observed width.
- **Exiting non-zero on a rejected capture.** The decoder must print its single-key error
  object and exit 0. A non-zero exit fails the rejection tests even when the error name
  is right.
- **Getting the rejection precedence wrong.** A file can be bad in several ways at once.
  The specification fixes the order; a decoder that checks the CRC before the magic
  reports the wrong name on a capture that is bad in both.
- **Hardcoding the visible sample answers.** `negative_hardcoded_sample_answers`
  fires, and the hidden corpus makes the shortcut worthless anyway - it is reseeded from
  a value the agent never sees.
- **Reading `/app/data` at run time.** The verifier runs in `separate` mode where that
  directory does not exist. A codec that depends on it scores zero at grading time even
  though it works perfectly during development.
- **Splitting the codec across helper modules.** Only the named artifact paths are
  collected. An import of a sibling file the agent wrote will not resolve at grading time.
- **Non-deterministic report artifacts.** Unsorted dict iteration, timestamps, or
  absolute temp paths inside the `/app/out/*` reports fail
  `negative_nondeterministic_output` on the second run.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: vendor-archive-roundtrip-recovery
task_name: terminal-bench/vendor-archive-roundtrip-recovery
fix_patch_sha256: 2a0544d21317243fac074882646d072c2ecaa5631a9516c75b9d35ccab50cc5f  # sha256 of solution/solve.sh
solve_py_sha256: 0e61499233233e7a3b46459f0604941325d169040fafe761a37e427700a39868  # informational; solve.py is 290 lines
language: python
authored_by: harbor-generator
status: generated_reference
archetype: format-recovery
generator_seed: '0x00000000000457c3'
trailer_token: harbor:format-recovery:VARC:00000000000457c3
golden_score_measured: null  # not measured for this generated instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured. This instance was scaffolded by generate_bundle.py from
  the format-recovery archetype and has not been through an oracle / nop /
  agent calibration sweep. Build the tests-only copy with
  Input_Bundle_QC/exe_copy.py, then run the oracle agent five times
  (expected reward exactly 1.000 each) and the nop agent (expected exactly
  0.000) on it before recording any figure here. Those figures cover the
  test channel in tests/test_output.py only; the judged channel has no
  oracle score. Never present a target or an estimate as a measurement.
caveat: >
  The test channel carries 24 positive checks worth 72 weight and 5 negative
  checks worth -23 weight, so on its own it ranges -23/72 = -0.319 to
  +1.000. The judged channel carries 12 criteria worth 34 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```
