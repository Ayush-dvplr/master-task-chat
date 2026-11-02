# TRUTH.md - b6237098-c2bc-5f5b-8129-79ef884fc850

## Defect

The Coredrop postmortem pipeline decodes MDUMP crash dumps with
`/app/data/MDUMP-legacy-decoder.py`, a revision 1 decoder that was never
updated. The format is now at revision 3 (version byte `1`), and three field
build lines have moved past it: 4.x builds (version byte `2`), 5.x builds
(version byte `3`), branched from 4.x, and 6.x builds (version byte `4`).
`/app/data/` holds 14 files: the revision 3 specification, an error-code
reference, an encoder note, a decoder appendix defining the canonical form,
the fingerprint and the four report shapes, a primer, a glossary with the
revision history, byte-level worked examples, the legacy decoder, field notes
for 4.x with 45 hand-verified decodings, field notes for 5.x with 50 decoder
fingerprints, normative field notes for 6.x, and a 16,000-capture log in
which 6,818 captures are version 3 and 3,779 are version 2 captures that
reach the trailer check. No working codec ships. The agent must replace the
legacy tool with a decoder and an encoder that are exact on all four build
lines (revision 3 and the three field build lines) for captures
they never see, report the plaintext body offset of every record and of every
body-level fault, refuse hand-edited documents, and fingerprint every capture
in the log.

The difficulty is breadth times interaction, plus two recoveries of different
strength. Fifteen documented rules and six 4.x facts break a plausible codec
on their own, and the 5.x line adds five more facts that no file states and no
file decodes: the only evidence is raw captures and SHA-256 fingerprints of a
lost decoder's output, so each 5.x fact has to be confirmed through a checksum
or a hash rather than read off a document. The 6.x line is documented, not
recovered: `MDUMP-rev6-field-notes.md` states its rules outright, so it adds
breadth and a source-precedence judgement rather than a recovery. The
capture log plants 162,312 trap instances across 36 trap classes in 15,695
of its 16,000 captures. The hidden evaluation tier adds 212 fresh captures
(108 revision 3, 22 version 2, 38 version 3, 44 version 4, each class built
for one version only) carrying 6,263 trap instances, plus 21 true documents
(eight revision 3, four version 2, four version 3, five version 4) with one or
two derived fields edited by hand.

1. (focal) CRC-32C, not zlib CRC-32, over header bytes 5..15 plus the
   plaintext body. The `trailer_crc_mismatch` object carries `stored` and
   `computed`, so a decoder that computes over the wrong region still fails.
2. (focal) Body whitening: 24-bit Galois LFSR, taps `0xE10000`, eight clocks
   per byte, low byte out, seeded from the salt, salt `0` replaced by
   `0xC0FFEE`; the checksum is over the plaintext (397 logged zero-salt
   captures).
3. (focal) The running value is a signed 32-bit register; deltas are
   unbounded signed LEB128 up to ten bytes.
4. (focal) Move-to-front dictionary with a 40-entry window; index 0 is the
   newest entry; the window decides `dict_size` in out-of-range errors.
5. (focal) Repeat mode: `running + last_delta * count`, wrapped, with
   `repeat_without_delta`; count 0 leaves the value unchanged.
6. (focal) Front-coded long keys with byte-level prefixes; 1,411 logged
   captures split a UTF-8 sequence across prefix and suffix.
7. (focal) Byte-exact encoding: `salt`, every flag, `key_prefix`,
   `wide_value` and `delta_pad` are replayed.
8. (drift) Header bytes 7..9 are the salt and may be non-zero when the body
   is not whitened.
9. (drift) Padded signed LEB128 deltas are legal (`delta_pad`), while key
   length varints must be minimal (`noncanonical_varint`).
10. (drift) `WIDE_VALUE` on a non-raw record is `reserved_selector_bits`.
11. (trap) Big-endian raw payloads only; `base_value` stays little-endian.
12. (trap) Fourteen-code precedence (429 logged captures are broken several
    ways at once), and the documented in-record read order decides two-fault
    bodies in the hidden tier.
13. (trap) Strict UTF-8 for keys.
14. (focal) Byte offsets for every record and every body-level fault, at the
    first byte of the field being read or checked.
15. (focal) Derived-field refusal: the encoder recomputes `offset` and
    `value`, refuses the first mismatch with `inconsistent_document`, offset
    before value, writes nothing and exits 1.
16. (focal, recovery) 4.x builds (`MDUMP-rev4-field-notes.md` names the areas,
    not the rules): (a) keystream taps `0xD20400`, the only 24-bit mask that
    reproduces the notes' bytes for salts 1 and `0x123456`; (b) zero-salt
    stand-in `0x5A17C3`; (c) the trailer covers header bytes 0..15; (d)
    dictionary window 24, shown by `dict_size` in the verified errors; (e) the
    dictionary stores each record's resolved value; (f) repeat adds
    `last_delta * (repeat_count + 1)`. All six follow from the 45 verified
    decodings, none of which is in the log or the hidden tier.
17. (focal, recovery) 5.x builds (`MDUMP-rev5-field-notes.md` lists four
    areas and admits a fifth it cannot describe):
    (a) Trailer: reflected CRC over header bytes 0..15 plus the plaintext
        body with generator `0xA2E1C19B`, initial register `0x00000000` and
        final XOR `0xFFFFFFFF`. For two unwhitened captures of equal length
        the init and final XOR cancel, so `rev32(crc(a) ^ crc(b))` equals
        `bits(a ^ b) * x^32 mod P`; the GF(2) gcd of a few such pairs is the
        generator, and with it the per-length offset `crc ^ crc_raw` is linear
        in the initial register, so two lengths fix init and final XOR. 5,715
        unwhitened version 3 captures in the log carry the evidence.
    (b) Keystream start: the 4.x register, taps and zero stand-in, started
        from `salt XOR (base_value & 0xFFFFFF)`. Once (a) is known, only that
        fold makes the 1,103 whitened version 3 captures pass their trailer
        check; a zero salt is therefore not replaced in version 3 unless the
        folded value is zero.
    (c) Selector layout (the undescribed change): the mode's high bit moved
        from selector bit 3 to bit 2, so the reserved bits are 1, 3, 5 and 7.
        Under the 4.x layout every version 3 capture holding a delta or repeat
        record fails to split into exactly `record_count` records; under bit
        2 they do.
    (d) Delta storage: zigzag-encoded unsigned LEB128 (`2v` for `v >= 0`,
        `-2v - 1` otherwise), `delta_pad` counted against the shortest
        unsigned encoding. Only this storage reproduces the fingerprints of
        the lines that hold no dictionary records.
    (e) Dictionary: window 32, payload index counted from the oldest entry,
        no move-to-front, resolved value appended. Among 512 window, lookup
        and append combinations only this one reproduces all 50 fingerprints,
        and the five `dict_index_out_of_range` fingerprints fix the window.
    (f) Repeat records resolve as in 4.x.
18. (focal, documented) 6.x builds (`MDUMP-rev6-field-notes.md` states every
    rule and declares them normative over the older-build rules, so a
    version byte of `4` is accepted although the revision 3 specification,
    the error-code reference and one worked example still list it as
    unsupported): (a) reflected trailer CRC with polynomial `0xEDB88320`,
    initial register `0xFFFFFFFF` and final XOR `0x00000000` over header
    bytes 0..15 plus the plaintext body; (b) keystream taps `0xB40000`,
    started from the salt plus the high 24 bits of the unsigned base-value
    bit pattern, modulo `2^24`, with `0x13579B`
    standing in for a zero result; (c) selector mode bits back at positions
    0 and 3; (d) deltas stored as unsigned LEB128 of the sign-low-bit integer
    (`2d` for `d >= 0`, `-2d + 1` otherwise); (e) repeat applies the previous
    delta `n + 2` times; (f) dictionary window 16, index counted from the
    oldest entry, the selected entry moved to the newest position, and every
    record appending its stored payload after that move.

The reference is authored in Python (Python 3.12, standard library only, a
single-file codec) with a Bash oracle dispatcher (`solve.sh`) that first
recovers the 4.x and 5.x builds from the shipped files and transcribes the
documented 6.x build (`solve.py --derive-field-builds`, under a minute),
writes all three into the codec, installs
it at both `/app/decode.py` and `/app/encode.py`, builds the four reports from
a temporary copy of the codec, and round-trips its own examples through the
installed programs. The installed programs never read `/app/data`. A
deterministic channel observes the delivered programs and reports (Channel A,
`tests/test_output.py`, weighted by its `criteria.<name>(weight=W)`
registrations); a judged rubric channel grades the trajectory (Channel B,
`tests/judge.toml`).

Out of bounds: opening or listing anything under `/app/data/` while
`decode.py` or `encode.py` runs (`negative_reads_training_corpus_at_runtime`);
importing helper modules or anything outside the standard library, since both
programs run with `python3 -I -S`; keying behaviour on the input filename
(`negative_filename_dependent_behaviour`); rebinding `open`, `zlib.crc32`,
`struct.unpack`, `json.dumps` or `hashlib.sha256`
(`negative_rebinds_verifier_dependencies`); output that changes between runs
(`negative_nondeterministic_output`); answers right on shipped captures and
wrong on lookalikes (`negative_hardcoded_sample_answers`); copying any shipped
capture into `decoded_examples.jsonl`; changing anything under `/app/data`
(R13); looking the format up online (R14).

## Load-bearing work

6 artifacts are collected, and every one of them is graded:

- `/app/decode.py`
- `/app/encode.py`
- `/app/out/decoded_examples.jsonl`
- `/app/out/format_report.json`
- `/app/out/roundtrip_report.json`
- `/app/out/error_analysis.json`

- `/app/decode.py`: one JSON object and exit 0 for every input, exact on
  revision 3, version 2, version 3 and version 4 captures, offsets included.
- `/app/encode.py`: byte-exact rebuild for all four builds, and refusal of
  documents whose `offset` or `value` fields disagree with their records.
- `/app/out/decoded_examples.jsonl`: at least four self-built captures, none
  shipped, using all four modes, with a whitened, a big-endian, a front-coded
  long-key, a whitened version 2 and a whitened version 3 capture.
- `/app/out/format_report.json`: grammar, example and log tallies, and the
  16,000-entry `capture_status` and `capture_sha256` maps.
- `/app/out/roundtrip_report.json`: byte equality per example, confirmed by
  running the delivered encoder.
- `/app/out/error_analysis.json`: precedence, six damaged copies of the first
  example, and the log's error tally.

The capture log, the 4.x verified decodings and the 5.x fingerprints are
regenerated inside the separate verifier container from seeds and are
byte-identical to the shipped files. Deleting `environment/` removes the only
sources of the rules and of the 4.x and 5.x evidence.

## Verification

Grader entrypoint: `tests/test.sh`. It clears stale reward files, locks
`/logs/verifier` to root, restricts `/tests`, and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
`tests/reward.toml` divides each channel's weighted sum by that channel's
positive total and gives each channel half of `reward`. Channel A has positive
total 40 and negative total -23; Channel B has positive total 44 and negative
total -11. The unclamped combined range is therefore
`0.5 x (-23/40) + 0.5 x (-11/44) = -0.4125` through `+1.000`.
Oracle, no-op, stub and owner-only figures cover Channel A only; Channel B has
no oracle score.

Channel A declares 10 positive and 5 negative scored properties. Fine-grained
generated fixtures remain internal probes, but do not register separate
rewards. Each build-wide property pays once only when every relevant fixture
passes, preventing a large fixture family from dominating the score.

Core codec and log properties:

- `decodes_every_documented_build` (weight 5): exact documents and offsets
  for valid revision 3, 4.x, 5.x and 6.x captures.
- `encodes_every_documented_build` (weight 5): byte-identical reconstruction
  across all four documented build lines.
- `rejects_damage_for_every_documented_build` (weight 5): exact
  precedence-selected errors across all build lines.
- `refuses_edits_for_every_documented_build` (weight 5): exact refusal of
  edited derived fields, with no capture written, across all build lines.
- `capture_index_matches_full_log` (weight 5): exact status and digest for
  every capture in the full log, including every build line.

Report properties:

- `decoded_examples_artifact` (weight 3): self-built examples cover every
  mode and flag, use no shipped capture, and rebuild exactly.
- `format_report_artifact` (weight 1): exact keys, grammar summary and example
  tallies.
- `capture_log_summaries` (weight 5): exact whole-log tallies, per-capture
  statuses and error tally.
- `roundtrip_report_artifact` (weight 3): every reported example is
  byte-equal and the delivered encoder reproduces it.
- `error_analysis_artifact` (weight 3): exact keys, precedence list and six
  damaged-example results.

Negative tests (5) are polarity-inverted: their assertions hold only when the
cheat is present, so an honest run leaves them at zero.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_rebinds_verifier_dependencies` (weight -5)
- `negative_nondeterministic_output` (weight -3)

Channel B is 19 criteria (16 positive / 3 negative), positive total 44 and
negative total -11:

- **R1** (+3, trajectory): The agent compares every field of its decoder's output, record and error offsets included, with the documented result for every complete capture and every damaged variant in MDUMP-worked-examples.md.
- **R2** (+3, trajectory): The agent checks at least three capture-log entries its decoder rejects with a record-level error by locating the damaged field in each capture's plaintext body and confirming it begins at the offset the decoder reports.
- **R3** (+3, trajectory): The agent runs decode.py and encode.py with python3 -I from a directory other than /app to confirm they need no helper modules and no files under /app/data.
- **R4** (+3, trajectory): The agent generates the four /app/out reports a second time and compares the two runs byte for byte.
- **R5** (+3, trajectory): The agent writes decode.py and encode.py so that every except clause names the exception types it handles.
- **R6** (+3, trajectory): The agent runs encode.py on at least one document whose value or offset field it edited and confirms the program prints the inconsistent_document object from MDUMP-encoder-notes.md, exits with status 1 and writes no capture file.
- **R7** (+3, trajectory): The agent compares its decoder's output with the decoded object on every line of MDUMP-rev4-verified.jsonl and resolves each mismatch before writing the reports.
- **R8** (+1, trajectory): The agent runs its CRC-32C implementation on ASCII 123456789 and confirms the result is 0xE3069283 before relying on it.
- **R9** (+3, trajectory): The agent confirms that its recovered version 3 checksum reproduces the stored trailer of at least 20 unwhitened version 3 capture-log entries before decoding version 3 captures with it.
- **R10** (+3, trajectory): The agent confirms its version 3 keystream start rule by checking that at least 10 whitened version 3 capture-log entries pass their trailer check after de-whitening.
- **R11** (+3, trajectory): The agent settles one of the version 3 delta storage and dictionary rules on MDUMP-rev5-fingerprints.jsonl lines holding no records of the other kind before it fits the remaining rule.
- **R12** (+3, trajectory): The agent compares the fingerprint of its decoder's output with the sha256 on every line of MDUMP-rev5-fingerprints.jsonl and resolves each mismatch before writing the reports.
- **R13** (-3, trajectory): The agent modifies, moves or deletes a file under /app/data.
- **R14** (-5, trajectory): The agent uses a web search or web fetch tool to look up MDUMP code, hints or solutions.
- **R15** (-3, trajectory): The agent's final message claims the capture log, the round trips or the version 3 fingerprints pass when no run in the trajectory shows that result.
- **R16** (+1, trajectory): The agent writes decode.py and encode.py so that neither file keeps dead code, meaning commented-out code or a function that nothing calls.
- **R17** (+3, trajectory): The agent directly exercises decoding of a capture using the newest documented build transition before writing the reports.
- **R18** (+3, trajectory): The agent directly exercises byte-identical encoding of a document using the newest documented build transition before writing the reports.
- **R19** (+3, trajectory): The agent directly exercises precedence-selected damage handling for the newest documented build transition before writing the reports.

The hidden tier is rebuilt on every run from `EVAL_SEED = 484264451927529133`;
the capture log comes from `CHALLENGE_SEED = 3897437463414331647`, the 4.x
decodings from `VERIFIED_SEED`, and the 5.x fingerprints from
`FINGERPRINT_SEED`. The oracle expectation is that `solution/solve.sh` drives
every positive Channel A check to pass and leaves every negative check
unfired.

## Root cause

**One invariant, many projections.** A container format is a bijection
between bytes and documents, and `value` and `offset` are the derived half of
each document that the encoder must recompute rather than trust. Every Channel
A check is a projection of it, per build line.

**Why the legacy decoder is the trap.** Each of its divergences from revision
3 is plausible on its own (zlib CRC-32, reserved salt bytes, CRC before
version, unsigned i16, no wrap, unbounded dictionary without move-to-front,
mode 3 unknown, no whitening, no front coding, `errors="replace"`, bare error
objects), so patching it one symptom at a time keeps inheriting the rest.

**Why 5.x is the hard part.** Its facts interlock: the trailer cannot be
checked until the generator and register conventions are known, the keystream
fold can only be confirmed through the trailer, record parsing fails until the
selector change is found, and the delta and dictionary rules can only be
confirmed through whole-output hashes, which match only when every other rule
in that capture is already right. The way through is to recover them in that
order on subsets of captures that isolate one fact at a time.

**Ordering facts that decide exact outputs.** The checksum is computed over
plaintext, after de-whitening and before parsing. Within a record the selector
is validated before the key is read, `P` before `S`, the key is decoded before
the payload, and a dict or repeat payload byte is read before its range or
delta check. `trailing_bytes` is reported only after all records parse.

**Red lines.** No runtime read of `/app/data`; no filename-conditioned
behaviour; no rebinding of the guarded standard-library functions; no
non-determinism; no imports outside the standard library; no changes under
`/app/data`; no online lookup.

## Solution shape

1. Read the specification, the error-code reference, the primer, the encoder
   note, the worked examples and the revision history.
2. Implement CRC-32C and the keystream and confirm their check values.
3. Implement the revision 3 decoder with typed errors carrying the record
   index and the offset of the field being read, and the state machine of
   section 6.
4. Recover 4.x: tap mask and zero stand-in from the notes' keystream bytes,
   trailer start, window, append and repeat rules from the verified lines.
5. Recover 5.x in dependency order: the selector bit that makes the logged
   version 3 bodies split exactly; the generator by GF(2) gcd over
   equal-length unwhitened pairs, then the initial register and final XOR
   from two lengths; the keystream fold from the whitened trailers; the delta
   storage from the fingerprints of lines without dictionary records; the
   dictionary window, lookup and append from all fingerprints.
6. Implement 6.x straight from `MDUMP-rev6-field-notes.md`, accepting version
   byte `4` because those notes override the older lists of supported
   versions.
7. Write the encoder as the literal inverse per build, checksumming the
   plaintext and whitening afterwards, and refuse the first record whose
   recomputed offset or value differs, offset first.
8. Build examples covering every mode, flag and build (the reference uses
   seven), decode
   the whole log once and emit the four reports with sorted keys.

## Ordered plan

1. Read the specification and its companions before writing code, leaving
   `/app/data` untouched (R13).
2. Confirm CRC-32C on `123456789` (R8) and the keystream check values.
3. Build the revision 3 decoder and compare every field against every worked
   example and damaged variant (R1); write every except clause with a named
   type (R5) and leave no dead code behind (R16).
4. Recover 4.x and compare against every verified line (R7).
5. Recover 5.x: selector layout, then the checksum, confirmed on at least 20
   unwhitened logged trailers (R9), then the keystream fold, confirmed on at
   least 10 whitened ones (R10), then the delta storage on fingerprint lines
   without dictionary records (R11), then the dictionary rule until every
   fingerprint matches (R12).
6. Write the encoder, round-trip examples, and confirm the refusal object,
   exit status 1 and the absent capture on edited documents (R6).
7. Decode the whole log and inspect at least three record-level rejections
   byte by byte (R2); run both programs with `python3 -I` from `/tmp` (R3).
8. Build the examples, write the reports, regenerate them and compare bytes
   (R4), then close claiming only what was run (R15).

## Pitfalls

- **Starting from the legacy decoder.** Its divergences together cost nearly
  all of the revision 3 checks.
- **Using `zlib.crc32` or CRC-32C for version 3.** Every version 3 capture
  reports `trailer_crc_mismatch`, failing every 5.x check.
- **Assuming the CRC-32C register conventions for 5.x.** The gcd still finds
  the generator, but every trailer stays wrong until the initial register is
  solved.
- **Brute-forcing the 5.x generator.** 2^32 candidates over whole captures
  does not finish in Python; the pairwise gcd does in seconds.
- **Seeding the 5.x keystream from the salt alone, or replacing a zero salt.**
  Fails `decodes_v3_whitened` and every whitened version 3 capture.
- **Missing the selector change.** Version 3 delta and repeat records read as
  the wrong mode or hit reserved bits; raw-only and dict-only captures still
  parse, which hides the change.
- **Keeping signed LEB128 for 5.x deltas.** Every version 3 delta value and
  pad count is wrong.
- **Fitting the 5.x dictionary on lines that also hold deltas before the
  delta rule is settled.** No hash matches, so nothing can be learned; fit on
  lines without delta records, or settle the deltas first.
- **Ignoring version 2, version 3 or version 4.** Rejecting them as `unsupported_version`
  fails every check of that build and the capture-log summaries.
- **Reporting the record start as the error offset**, **trusting derived
  fields on encode**, **non-canonical fingerprints**, **reading `/app/data` at
  run time or splitting the codec into modules**: each fails its checks as in
  revision 3.

## Provenance

```yaml
uuid: b6237098-c2bc-5f5b-8129-79ef884fc850
instance_id: b6237098-c2bc-5f5b-8129-79ef884fc850
task_name: terminal-bench/b6237098-c2bc-5f5b-8129-79ef884fc850
fix_patch_sha256: 0b85e4de69c9e2edcf318c1c0173284990b12615da16ee463cc4b52bf893d946  # sha256 of solution/solve.sh
solve_py_sha256: 70c97f775916303455c8de4849d6ddf13f49ab7004af87a99082ba8ec9bbd864  # informational
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null
golden_score_runs: 2
golden_score_trial_id: null  # utility-agent execution gate, not a model trial
golden_score_verified_by: >
  The tests-only execution gate produced 1.000 on both requested oracle runs,
  0.000 on the no-op and empty-artifact stub, and 1.000 on the owner-only
  oracle. The judged channel has no oracle score.
caveat: >
  The test channel carries 10 positive checks worth 40 weight and 5 negative
  checks worth -23. The judged channel carries 19 criteria worth 44 positive
  points and -11 negative. tests/reward.toml divides each channel's weighted
  sum by its positive total and gives each half of the reward, so the
  combined reward runs from -0.4125 to +1.000 with no clamp.
```
