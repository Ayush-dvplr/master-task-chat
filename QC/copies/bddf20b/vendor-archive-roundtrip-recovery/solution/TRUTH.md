# TRUTH.md - vendor-archive-roundtrip-recovery

## Defect

The task ships no broken code to repair. The defect is a missing codec: the
VARC1 container was written by a vendor loader that no longer exists, and the
archive under `/app/data` cannot be read, round tripped or migrated until a
decoder and a byte exact encoder are rebuilt from the written contract. Every
rule is stated in the shipped files; the difficulty is that the rules chain, and
the grader reads whole documents decoded from hidden segments, manifests and
edited documents.

Items the solver must get right, classified:

- (focal) Count fields read unsigned. `format_contract.md` Field names: a raw
  record whose unit is `count` is read unsigned, in place of the signed reading
  under Value by mode. The catalog's `value_sum` control flags the signed reading
  on the shipped captures; reading every raw value unsigned also satisfies that
  control on the shipped captures but not on hidden segments.
- (focal) One cumulator per field name. `format_contract.md` Terms defines the
  cumulator that a delta adds to as the one kept for the record's field name; the
  resolved list stays one per stream state.
- (focal) Run ledger. `decoder_appendix.md` Runs: each stream has at most one
  current run holding a stream state and the last `seq_no` taken; a segment whose
  `seq_no` is not larger than that is a resend, decoded from the state as it
  stands, and it leaves the run exactly as it was.
- (focal) Strict types beside lenient text. A manifest entry's `stream_continues`
  replaces the header bit only when it is a JSON boolean, although every text
  value in a manifest is trimmed; an encoder document's `delta_raw_len` gives an
  exact length only when it is a JSON integer, although extension hex is read
  case-insensitively after trimming.
- (trap) Revision per segment, remap before alias, unlisted key bytes as their
  own ids; `loader_notes.md` describes an older revision 0 behaviour that the
  contract overrides.
- (trap) Opaque extensions and overlong deltas kept exactly as captured on
  unmodified records; raw values written as their low 16 or 32 bits; bounded
  escaping; salvage resumes only where a frame parses.
- (drift) Header rejection order, offset 15 alone, both reserved bytes set, the
  record count bound and the checksum error fields.

## Load-bearing work

The solver must: implement the header, the frame reader with bounded escaping
and the frame check; resolve the four modes against a cumulator per field name
and a stream wide resolved list, reading count fields unsigned; name fields
through the segment's own revision, the sparse revision map and the stream
alias; carry runs in `--stream` with the resend ledger and the JSON boolean
override, trimming manifest text; implement the rejection order and the salvage
walk; make the encoder read the pre-resolution keys, write raw values by their
low bits and honour `delta_raw_len` only as a JSON integer; and build the four
reports from the catalog and from examples it writes itself.

## Verification

Grading has two channels. The deterministic channel in `tests/test_output.py`
has 27 positive checks with a positive weight total of 107 and 5 negative checks:
`negative_hardcoded_sample_answers` (-5), `negative_nondeterministic_output` (-3,
same path three times), `negative_filename_dependent_behaviour` (-3, same bytes
under three names, each name run twice; it stands down when a name's repeats
differ), `negative_reads_training_corpus_at_runtime` (-5, field names follow a
planted copy of the tables under `/app/data`) and
`negative_rebinds_verifier_dependencies` (-3, a `.pth` file or a module named
after a standard library or grader module in the workspace). The behavioural
negatives stand down unless the program ran cleanly. 13 whole document checks
(weight 65) compare full `--stream`, decode, salvage and encoder outputs on
hidden inputs drawn at grade time; 8 isolated rule checks (weight 24) and 2
mutation checks (weight 6) each read one rule's observable; 4 report checks
(weight 12) read the reports, three of them by running the delivered programs on
the agent's own examples. A failing check prints its reason to the verifier's
standard output.
The judged channel in `tests/judge.toml` has 6 positive criteria with a positive
total of 16 (four self-built test cases, one per focal item, the code quality of
the two programs and a catalog round trip check) and 2 negative criteria.
The reference solution scores 1.0 on the test channel and an agent that does
nothing scores 0.0.

## Root cause

There is no bug to trace. The difficulty comes from chained rules: a wrong
reading of the count unit, the cumulator scope, the run ledger or the override
type changes values in every document that holds such a record, while every
identity the solver can check on the shipped data (round trips, catalog counts,
and the control totals under the all unsigned reading) still holds.

## Solution shape

`solution/solve.py` parses the field table, the alias table and
`revision_map.ini` into a schema, and `solve.sh` bakes that schema into self contained
`/app/decode.py` and `/app/encode.py` programs, then emits the four reports.
The decoder validates the header in the stated order, names each frame's field
first, reads its value (unsigned for a count unit) and applies it to a carry
object holding a total per field name and the resolved list. `--stream` trims
manifest text, keeps one open run per stream id with the last `seq_no` taken,
decodes a resend from a copy of the run's carry, and closes or keeps the run by
the entry's JSON boolean `stream_continues` or else the header bit. `--salvage`
walks from offset 16 to the trailer, records each damaged span and resumes at
the first offset where a frame parses against the state from before the span.
The encoder writes frames from the pre-resolution keys and recomputes counts,
checks, lengths and the trailer.

## Ordered plan

1. Read the contract and build the header, selector and trailer layout.
2. Implement the varints, the bounded escaping and the frame check.
3. Implement the four modes with a cumulator per field name and the count unit.
4. Add revision remap (sparse map, per segment revision) and aliases.
5. Implement the encoder and confirm byte exact round trips on the catalog.
6. Check every catalog `value_sum`.
7. Add `--stream` with the manifest rules and the run ledger, then `--salvage`.
8. Handle `delta_raw_len` types and edited or added records.
9. Emit the four reports from the catalog and self built examples.

## Pitfalls

Reading every raw value unsigned to satisfy the control totals; keeping one
running total per stream; feeding a resend's frames into the run; treating
`"true"`, `"false"`, `1` or `0` as a boolean override; parsing a text
`delta_raw_len`; carrying state into a new run; resolving a revision 0
continuation under the previous revision; looking up the alias before the remap;
re-encoding every delta in shortest form; dropping or reordering opaque
extensions; unescaping past the window; applying a damaged frame's effect; and
reading `/app/data` from inside the delivered programs.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: vendor-archive-roundtrip-recovery
task_name: terminal-bench/vendor-archive-roundtrip-recovery
fix_patch_sha256: 062f6c746aef8ffdeb026e9a5baaffcd61d8d306ec3b75740e683da5919d9097  # sha256 of solution/solve.sh
solve_py_sha256: 3effcfe49a118823ad7f13c1ada61b4afa6ce15b84d13904cafa86e7d04aa3bc  # sha256 of solution/solve.py
language: python
```
