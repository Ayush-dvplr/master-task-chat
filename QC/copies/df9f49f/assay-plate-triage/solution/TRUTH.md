# TRUTH.md - assay-plate-triage

Author side golden trajectory. This file never reaches the agent. It records the
twelve mode bits, how the grader scores them, and where a plausible attempt goes
wrong.

## Defect

The bench controller was rebuilt and the triage engine went with it. The agent is
handed the engine's file shapes and stage order, two worked runs at mode zero that
pin the plain chain, and two graded runs whose mode word is `0xfff` and which ship
no output: the unprefixed run it reports its figures over, and a second run under
the prefix `trial_` that holds a different instrument set, operator count and plate
count so the count-dependent bits can be read against two runs. The work is to
recover the twelve mode bits and ship the engine.

1. `(focal)` The twelve mode bits are undocumented and carry the whole weight. Each
   alters exactly one thing: the blank level chains from the previous plate on the
   same instrument; a measure charge lands one read late; the role tolerance comes
   from the previous read's operator; the band edges lift by fifteen times the plate
   tier; normalisation uses the plate's smallest exposure; the panel adjustment
   drops to the plain one on odd replicates; the last sorting instrument that carries
   a plate stores its baseline as a delta from the smallest other baseline; reads
   resolve in ascending exposure then seq; a masked well cancels one strike; the last
   `1 + plate_count % 4` reads by seq are excluded; the written matrix is an alias for
   the one `tier + operator_count` places later in the documented matrix order; and
   quarantine adds the previous plate on the same instrument's strikes.
2. `(focal)` The plain chain's constants are still missing, but they are learnable
   from the two mode zero runs, which ship with all three of their output files.
   That tier is worth 3 of 90.
3. `(drift)` The obvious move is to read the mode word, find nothing about it in the
   notes, and build the plain chain anyway. That is the trap blind solver and it
   scores 0.0333.
4. `(drift)` `declared_reads` equals the line count of `reads.jsonl`, so it looks
   like a consistency field. Under the count bias bit the engine resolves fewer reads
   than that, and nothing announces it except the digests.
5. `(trap)` Four bits are stateful, so they cannot be read off one record. The blank
   chain, the echoed charge, the role lookback and the quarantine span all need the
   run walked in resolution order with per instrument carry.
6. `(trap)` Two bits leave `readings.jsonl` untouched and show up only in
   `plates.json`: the mask absolution and the quarantine span. A solver that checks
   only its readings against the digest will call them free.
7. `(trap)` The exposure order bit changes which read is resolved first, which moves
   the blank chain and the drift chain under it. Bits that look independent interact
   through the carry.

### The mode bits

| Flag | Scope | What the bit does when set | How the engine handles it | Dedicated test |
|---|---|---|---|---|
| `0x001` chain blank | cross-plate | a plate's blank level starts at the current blank level of the plate started before it on the same instrument | carry an ending blank level per instrument while walking the run in resolution order | `mode_bit_chain_blank` |
| `0x002` drift echo | cross-record | a measure read's drift charge is applied when the next read on that plate resolves | hold one charge per plate and release it on the following read | `mode_bit_drift_echo` |
| `0x004` role lookback | record | the drift tolerance is the one belonging to the previous read's operator, the plate's first read using its own | track the previous read's operator per plate | `mode_bit_role_lookback` |
| `0x008` band tier shift | block | the three band edges are each raised by fifteen times the plate's tier | recompute the edges per plate before grading | `mode_bit_band_tier_shift` |
| `0x010` exposure floor | block | normalisation divides by the plate's smallest exposure rather than the read's own | pre-scan each plate for its minimum exposure | `mode_bit_exposure_floor` |
| `0x020` panel parity | metadata | a panel with an odd `replicates` uses the plain adjustment whatever its family | read `replicates` before choosing the adjustment | `mode_bit_panel_parity` |
| `0x040` baseline delta | metadata | the last sorting instrument that carries a plate stores its baseline as a delta from the smallest other baseline | add the smallest other baseline back for that one instrument | `mode_bit_baseline_delta` |
| `0x080` exposure order | ordering | reads resolve in ascending exposure, then ascending seq | sort on the pair before walking | `mode_bit_exposure_order` |
| `0x100` mask absolves | stateful | a masked well removes one strike from its plate, floored at zero | apply on mask reads after the reading is emitted | `mode_bit_mask_absolves` |
| `0x200` count bias | cursor | the last `1 + plate_count % 4` reads by seq are excluded from the run | drop that tail before resolving | `mode_bit_count_bias` |
| `0x400` matrix alias | cross-file | the written matrix is an alias for the one `tier + operator_count` places later in the documented matrix order | resolve the alias against the operator table before adjusting | `mode_bit_matrix_alias` |
| `0x800` quarantine span | corpus | quarantine weighs a plate's strikes plus those of the plate started before it on the same instrument | track the previous plate per instrument to the rollup | `mode_bit_quarantine_span` |

Every bit also carries weight through the six all but one runs and the nine full
mode runs, which is where the mass sits: a bit read wrong costs 5 points on each of
those it appears in, and only 1 on its own dedicated test.

The reference engine lives in `solution/solve.py` as a source string, is written out
to `/app/out/triage.py` and is the same text the verifier grades against. The corpus
generator and the reference engine both live inside `tests/test_output.py`, so the
grader rebuilds every run from a seed and never reads `/app/data`.

Out of bounds: nothing asks the agent to change the report shapes, to add fields, to
touch `/app/data`, or to reach past the Python standard library. Report files written
by hand earn nothing, because only the program is collected.

## Load-bearing work

One artifact is collected:

- `/app/out/triage.py`

Its content contract: a standard library only Python program taking an input
directory and an output directory as its first two arguments. It reads
`manifest.json`, `instruments.csv`, `panels.csv`, `operators.csv`, `plates.csv` and
`reads.jsonl` from the input directory, honours the `mode` word it finds there, and
writes `readings.jsonl`, `plates.json` and `bench.json` into the output directory in
the documented byte forms. Repeated runs over one input write identical bytes.

The final message also carries ten named figures measured over the shipped run.
Those figures appear in no shipped file and are graded by the judged channel alone.

## Verification

Grading runs in a separate verifier container built from `tests/`. `tests/test.sh`
hardens the verifier (clears any stale reward file, locks `/logs/verifier` to root,
restricts `/tests`) and then hands over to `rewardkit`, which writes
`/logs/verifier/reward.json`; `test.sh` writes no reward itself. `tests/reward.toml`
combines the two channels into the single `reward`, each at half weight: the test
channel at `0.5 / 90` and the judged channel at `0.5 / 39`.

Channel A is `tests/test_output.py`: 33 rewardkit criteria, 30 positive and 3
negative, positive total 90 and negative total -11, so a perfect run reads 1.000. The
weights live on the `criteria.<name>(weight=W)` registrations and nowhere else.

Positive criteria, 15 at weight 1 and 15 at weight 5:

- `reusable_program_is_delivered` weight 1
- `untrapped_run_alpha_resolves` weight 1
- `untrapped_run_beta_resolves` weight 1
- `mode_bit_chain_blank` through `mode_bit_quarantine_span` weight 1 (twelve, one per mode bit)
- `every_bit_except_chain_blank`, `every_bit_except_role_lookback`, `every_bit_except_exposure_floor`, `every_bit_except_baseline_delta`, `every_bit_except_mask_absolves`, `every_bit_except_matrix_alias` weight 5
- `full_mode_run_alpha` through `full_mode_run_theta` weight 5 (eight full-mode runs)
- `full_mode_run_with_a_grown_operator_table` weight 5

Negative criteria:

- `negative_hardcoded_sample_answers` weight -5
- `negative_third_party_dependency` weight -3
- `negative_nondeterministic_output` weight -3

Only the three base-tier criteria pass without any bit implemented, so the trap
blind ceiling is 3 of 90, which is 0.0333.
Every graded corpus is rebuilt inside `tests/` from its own seed, and all three
reports are compared byte for byte. Each check is guarded so bad or missing agent
output returns False rather than raising.

Channel B is `tests/judge.toml`: 15 binary criteria, positive total 39 and negative
total -8. Ten positives (`R2` through `R11`) each read one closing figure out of the
final message and compare it with the value the reference engine produces for the
shipped run: `trace_rejects` 14, `technician_reviews` 17, `off_role_reviews` 5,
`hold_plates` 23, `saturated_reads` 4, `thin_matrix_total` 2036, `rich_matrix_total`
3104, `assay_family_total` 4969, `high_reads` 75 and `blank_end_total` 4120. `R1`
asks that the closing report names all ten figures as whole numbers, and `R12` reads
the trajectory for the agent recomputing the manifest digests from its own
resolution, so a trial that dies before writing its report still scores on this
channel. `R15` is a conduct criterion worth 3 that reads the trajectory for the
quality of the delivered `triage.py`, since the deterministic tests grade its output
bytes and never judge how the source reads. The two negatives fire when the agent
edits a file under `/app/data` (`R13`, -5) or opens the grader under `/tests` or
`/logs/verifier` (`R14`, -3). No Channel A criterion observes any of these, and no
closing figure is graded by any Channel A criterion, so the two channels never grade
the same fact.


## Root cause

**The mode word was never documented.** `engine.md` states that the word exists, that
each of its twelve bits alters one step, and that the firmware holding the meanings
is gone. Naming the candidate readings would turn the task into a search the model
clears in a few steps, so the notes bound the search without listing options.

**The worked runs teach the base tier and nothing else.** Both ship at mode zero, so
no shipped output exercises a single bit. That is what keeps the example from acting
as a self verification oracle for the traps.

**The digest is what makes it fair rather than a guess.** Both digests are taken over
the resolved reports, so a candidate reading can be tested against the shipped file
plate by plate. Dropping any one bit moves at least one plate digest on the shipped
run and on four verifier corpora, both on its own and on top of the other eleven,
and the three count-dependent bits are each distinguished from their constant
reading by the `trial_` run.

**Carried state couples the bits.** Blank level, drift and strikes run forward per
plate and, under two of the bits, per instrument across plates. Resolution order is
itself one of the bits, so getting it wrong moves every carried value under it.

## Solution shape

1. Read `engine.md` and `reports.md` and write down the stage order and the digest
   definitions.
2. Reproduce both mode zero runs from their inputs and check against the shipped
   outputs until the plain chain agrees line for line.
3. Implement the two digests and confirm them against the example manifests.
4. Take the graded run, set a candidate reading of one bit, resolve, and compare
   plate digests against `manifest.json`.
5. Work bit by bit, keeping the readings that raise the count of matching plate
   digests, and check `plates.json` as well as `readings.jsonl`, since two bits move
   only the rollup.
6. Once every plate digest and the run digest match, write the engine to
   `/app/out/triage.py`, driven by the mode word it reads from its input directory.
7. Measure the ten closing figures over the shipped run and state them.

## Ordered plan

1. Fit the plain chain on `example_a_` and confirm it on `example_b_`, so a
   disagreement later is a mode bit rather than a constant.
2. Build the digest routine and validate it against both example manifests before
   trusting it on the graded run.
3. Resolve the graded run at mode zero and count matching plate digests to get a
   baseline for the search.
4. Attack the bits that move a single plate first, since they give the cleanest
   signal, then the stateful ones.
5. Treat resolution order as a bit in its own right, since it moves every carried
   value under it.
6. Watch for bits that leave `readings.jsonl` untouched and show only in the plate
   rollup.
7. Deliver the program early, then keep refining bits with the time left.
8. Report the ten closing figures, which the rubric grades one by one.

## Pitfalls

- Building the plain chain, finding nothing about the mode word, and shipping.
  That is the trap blind solver at 0.0333.
- Digesting only `readings.jsonl` and calling the mask absolution and quarantine span
  bits free. Caught by `mode_bit_mask_absolves` and
  `mode_bit_quarantine_span` and by every weight 5 test.
- Iterating `reads.jsonl` in file order rather than resolving it. Every carried value
  diverges and all fifteen weight 5 tests fail.
- Trusting `declared_reads` as the number of reads to resolve. Caught by
  `mode_bit_count_bias`.
- Reading the matrix column literally under the alias bit. Caught by
  `mode_bit_matrix_alias` and by
  `full_mode_run_with_a_grown_operator_table`, which changes the operator count
  the alias reads.
- Applying a recal or a blank before the read that carries it is emitted. Caught by
  the base tier tests.
- Writing the three report files by hand. Only the program is collected, so the hand
  written files are never read.
- Embedding the shipped run's plate identifiers as literals. Fires
  `negative_hardcoded_sample_answers` for -5.
- Reaching for a package outside the standard library. Fires
  `negative_third_party_dependency` for -3.
- Emitting anything order dependent or time dependent. Fires
  `negative_nondeterministic_output` for -3.

## Provenance

```yaml
instance_id: assay-plate-triage
task_name: terminal-bench/assay-plate-triage
solve_sh_sha256: 506c48d5e58f92d657e48e96f92d49b1457aaa09d503b7fed85a0451de86a7c7
solve_py_sha256: 020bc7657189884b430ca6d700f8f7063b79962537465b687222fab4a3a2b59b
solve_py_lines: 492
language: python
mode_bits: 12
data_files: 32
shipped_run:
  mode: 4095
  read_lines: 143
  resolved_reads: 141
  plates: 37
  quarantined: [PLT-17, PLT-20, PLT-32]
  value_total: 47546
trial_run:
  prefix: trial_
  mode: 4095
  read_lines: 153
  resolved_reads: 152
  plates: 40
  operators: 6
  instruments: 4
  note: >
    A second graded run shipping digests only and no worked output. Its operator
    count, plate count and instrument baselines all differ from the shipped run, so
    the matrix-alias, count-bias and baseline-delta bits are each decidable against
    its digests where the shipped run alone left them tied to a constant reading.
channel_a:
  criteria: 33
  positive_total: 90
  negative_total: -11
  trap_blind_ceiling: 0.0333
channel_b:
  criteria: 15
  positive_total: 39
  negative_total: -8
golden_score_tests_only:
  oracle: 1.000
  nop: 0.000
  oracle_runs: 5
  note: >
    Tests-only values from the Step 10 execution gate, run under harbor 0.24.0 and
    harbor-rewardkit 0.2.1 on a copy with judge.toml deleted and reward.toml set to
    1/90. The deterministic channel scored 90/90 for the reference engine (reward
    1.000 on five runs) and 0/90 for an empty submission (0.000), with no negative
    criterion firing on either. The judged channel is validated against the rewardkit
    schema but never executed, so no judged-channel oracle score exists.
```

