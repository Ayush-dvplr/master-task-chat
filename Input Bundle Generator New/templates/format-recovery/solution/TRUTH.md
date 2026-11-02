# TRUTH.md - {{BUNDLE_NAME}}

## Defect

No source of a working codec ships anywhere in this instance. `/app/data/` holds
{{TRUTH_DATA_FILE_COUNT}} flat written reference files describing `{{FORMAT_TAG}}`, a
seeded binary record container produced by {{PRODUCER_SYSTEM}}, and nothing else - no
capture, no reference decoder, no worked answer key beyond the examples embedded in the
prose. The agent must derive the entire grammar from that written material and deliver
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
6. (trap) The trailer CRC covers {{GRAMMAR_CRC_DOC}}. That region includes the flag byte
   and the reserved bytes verbatim. A "helpful" encoder that normalises reserved bytes
   to zero, or that recomputes flags from the decoded document instead of replaying the
   observed byte, produces a file that differs from the original in the CRC and fails
   every round-trip test while looking perfectly reasonable in a diff of the decoded
   JSON.

The reference is authored in Python (Python 3.12, standard library only,
{{TRUTH_SOLVE_PY_LINES}}-line single-file codec) with a Bash oracle dispatcher
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
same input across two runs (`negative_nondeterministic_output`); embedding
the visible sample answers as literals (`negative_hardcoded_sample_answers`);
installing third-party packages; and looking the format up online - `{{FORMAT_TAG}}` is
invented for this instance and nothing about it exists outside this bundle.

## Load-bearing work

{{TRUTH_ARTIFACT_COUNT}} artifacts are collected, and every one of them is graded:

{{TRUTH_ARTIFACT_LIST}}

- `/app/decode.py` (new) - invoked as `python3 /app/decode.py <input.{{FORMAT_EXT}}>`.
  Prints exactly one JSON object on stdout, nothing else, and exits 0 even when the
  capture is rejected. On rejection it prints a single-key error object using the error
  name the specification defines, honouring the documented precedence.
- `/app/encode.py` (new) - invoked as
  `python3 /app/encode.py <document.json> <output.{{FORMAT_EXT}}>`. Consumes the decoder's
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

`/app/data/{{FORMAT_TAG}}-capture-log.jsonl` ships 20,000 field captures as hex, about
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

Channel A declares {{TRUTH_CHANNEL_A_SUMMARY}}, positive weight total
{{TRUTH_POSITIVE_TOTAL}} and negative weight total {{TRUTH_NEGATIVE_TOTAL}}, so the
theoretical reward range is {{TRUTH_REWARD_RANGE}}.

Positive tests ({{TRUTH_POSITIVE_COUNT}}):

{{TRUTH_POSITIVE_TEST_LIST}}

Negative tests ({{TRUTH_NEGATIVE_COUNT}}) are polarity-inverted: their assertions hold
only when the cheat is present, so an honest run leaves them "failing" and contributes
zero weight. They subtract only from a solver that actually cheats.

{{TRUTH_NEGATIVE_TEST_LIST}}

Channel B is {{TRUTH_RUBRIC_SUMMARY}}:

{{TRUTH_RUBRIC_LIST}}

The hidden corpus is reseeded on every run from `EVAL_SEED = {{EVAL_SEED}}`, distinct
from the visible `SAMPLE_SEED = {{SAMPLE_SEED}}` and the labelled
`CHALLENGE_SEED = {{CHALLENGE_SEED}}`. The verifier rebuilds it into a seed-specific
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

**The state machine.** {{GRAMMAR_STATE_DOC}}

**Delta encoding.** {{GRAMMAR_DELTA_DOC}}

**Dictionary resolution.** {{GRAMMAR_DICT_DOC}}

**Why the grammar is seeded.** The header field order, selector bit assignment, mode
identifiers, delta encoding, dictionary direction, and CRC coverage are all specific to this task
instance. This is the whole point of the task: it forecloses recall. No amount
of prior exposure to binary container formats supplies the answer, and there is no public
`{{FORMAT_TAG}}` to look up. The only path to a passing solution runs through reading the
shipped specification. For this instance the recovered grammar is:

`{{GRAMMAR_SUMMARY}}`

**Header layout for this instance.**

{{GRAMMAR_HEADER_TABLE}}

**Selector layout for this instance.**

{{GRAMMAR_SELECTOR_DOC}}

**Red lines.** No runtime read of `/app/data`; no filename-conditioned behaviour; no
rebinding of `open` / `zlib.crc32` / `struct.unpack`; no non-determinism across runs; no
hidden-corpus answers baked into the `/app/out/*` artifacts; no third-party packages; no
online lookup.

## Solution shape

1. Read `/app/data/{{FORMAT_TAG}}-container-format.md` end to end before writing a line,
   then the supporting files - the decoder appendix, the encoder notes, the error-code
   reference, the varint/CRC primer, and the glossary. Deciding which file answers which
   question is part of the task.
2. Transcribe the header into a single parse function: magic `{{MAGIC_ASCII}}`
   (`{{MAGIC_HEX}}`), version `{{VERSION_NUM}}`, then the five post-magic fields in the
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

{{TRUTH_PROVENANCE_BLOCK}}
