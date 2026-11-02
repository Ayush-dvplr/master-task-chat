# TRUTH.md - ae640566-6067-508e-b982-0158d72da2d4

## Defect

There is no broken program to repair. `/app/data` holds a flat archive of a distributed
gravimeter observatory (sixteen files: raw observations, effective-dated deployment and
custody history, effective-dated calibration certificates, a traceability standards
ladder, lifecycle amendments, reporting thresholds, a network policy, a declarative
`contract.md`, and a worked calibration control in `calibration_slice.json` plus
`calibration_example.json`). The deliverable is a reusable standard-library derivation
script that turns any archive obeying the same contract into ten exact artifacts. The
difficulty is rule COMPOSITION: the contract defines each rule but publishes neither the
precedence order, the rounding convention, nor the report encoding. Those are recovered
from the worked calibration evidence, and the main archive then needs a least fixed point
over reporting standing. Several traps interlock, so fixing one symptom does not repair
the figures another trap moves.

1. (focal) Quarantine precedence is not paragraph order. A repeated `sample_id` is held
   as `duplicate_sample` before anything else. After lifecycle (void samples voided,
   suspects held as `unresolved_suspect`), an observed sample is held for the FIRST
   applicable of `malformed_sample`, `unknown_channel`, `no_deployment`, `no_custody`,
   `no_certificate`, `unknown_unit`, `broken_ladder`, then `unreported_array`. The
   dual-failure records `C-01`..`C-05` and `C-16` in `calibration_slice.json` pin every
   adjacent pair, and `C-06` is a single-condition `broken_ladder` record (the contract
   states the duplicate and malformed positions outright).
2. (focal) Rounding is half away from zero. `C-07`, `C-08` and `C-14` (raw +1, -1, +1 at
   `gain_micro` 500000) give HLS-0006 a published total of 1, and `C-15` (-50 nGal at
   factor 1/100) gives -1. Banker's rounding, truncation and floor each miss one of them.
3. (focal) Reporting standing is a least monotone closure, earned not counted. Only
   `standing_basis=true` observations that survive every non-standing rule qualify. The
   shipped custody chain needs four rounds: HLS-0004 (1), HLS-0031 (2), HLS-0056 (3),
   HLS-0023 (4). A count-everything pass also admits HLS-0011, HLS-0017 and HLS-0042.
4. (focal) Certificate effectiveness composes revocation, restoration and expiry.
   Availability is the state after the whole ledger; a certificate covers `valid_from`
   through `valid_to` inclusive. CERT-0042-B is revoked, so HLS-0042 falls back to the
   tied pair CERT-0042-A / CERT-0042-C; CERT-0042-C wins the tie (higher id) only until
   it expires at `2031-5-31 23:59:59`, after which S-0023 falls to CERT-0042-A, which is
   what `standing_exclusions_by_certificate` shows. CERT-0004-B is revoked (its earlier
   restore at sequence 8 precedes the revoke and is ignored) and CERT-0004-A expires at
   `2031-03-31T23:59:59`, so S-0035 (written `2031-3-31 23:59:59`) is still covered while
   S-0005 has no certificate at all. S-0011 is revised onto 2031-06-02, after CERT-0017-C
   expires, and falls back to CERT-0017-B. CERT-0056-A expires before S-0034.
5. (focal) Malformed sample values are isolated, not fatal. `raw_count` must be an
   optional sign and ASCII digits and `epoch` a readable instant, judged after amendment
   effects. `1_200` (S-0043), Arabic-Indic digits (S-0044), a date without a time
   (S-0045) and `12.0` (S-0046, ahead of its unknown label) are malformed; ` +640 `
   (S-0047) is whole. Python's `int()` accepts the first two, so a lenient reader admits
   a qualifying count and moves standing. Revisions write what they carry: AM-32 writes
   the string `"6600"` and AM-33 an epoch without a time, damaging S-0016 and S-0026
   (each loses a qualifying count, yet both channels keep standing via custody); AM-31
   repairs S-0048 from `3.5` to 35. A loader that calls `int()` on every row crashes.
6. (trap) Ledger ties order by code point. AM-100 sorts before AM-99 and AM-30 before
   am-30, so S-0013 ends void and S-0010 ends at 7300. A natural or case-folded sort
   reverses both; the calibration pair CAL-T10/CAL-T9 and CAL-FIX/cal-fix shows the same.
7. (drift) Parameter sources: ordinary channels take certificate, station, network;
   provisional channels swap the first two. Deployment and custody ties take the later
   start then the LOWER id; certificate ties take the later start then the HIGHER id.
8. (trap) Effective-date resolution precedes standing, which is why the generalisation
   checks mutate custody, thresholds, effective dates, population and area membership.
9. (trap) Counts are unbounded integers. The ratio probe widens every well formed count
   to 29-44 digits, with exact `nGal` halves on both signs. A float path loses units at
   once; Python `Decimal` in its default 28 digit context rounds the quotient before
   `ROUND_HALF_UP` sees it. Only integer arithmetic (`(2n + d) // 2d` with sign handling)
   reproduces unit conversion, gain and ladder rounding.
10. (trap) Ladders may loop. The revocation probe points the fallback certificate of the
   revoked one at `STD-Y -> STD-U <-> STD-V`, plus a self-parented `STD-W`. A walk that
   stops at a revisit and keeps its running total admits those samples; the contract
   makes them `broken_ladder`, and a walk with no visited set never terminates.
11. (edge) An archive with no observation still yields every report: zero lifecycle
   counts, zero shares, `largest_sample` `{reported_nano: 0, sample_id: null}` and a zero
   quarantine ratio rather than a division by zero.
12. (trap) The ledger revises traceability standards. `revise_standard` overwrites a
   standard's parent, ratio or both, and ladders are walked over the standards left after
   the whole ledger. In the shipped archive AM-34 and AM-38 tie at sequence 87, so AM-38
   (code point after AM-34) leaves `STD-C` under `STD-D`, which file order would reverse.
   AM-35 sets `STD-E` to 80, AM-36 carries a quoted ratio and is ignored, and AM-37 names
   an absent standard and is unmatched. The revocation probe archive also files a reparent pair that
   closes an `STD-R <-> STD-T` loop only when replayed by sequence, tied revisions, a
   standard turned primary, malformed and empty revisions, an unknown standard, a replayed
   entry identifier and a repair of the self-parented `STD-W`, so ignoring the operation,
   applying it in file order, reading ties naturally or walking loops leniently all fail.

The reference is `solution/solve.py` (Python 3.12, standard library only, 974 lines),
exposing `derive(data_dir)` and a `reconcile(out_dir, expected)` self-check. `solve.sh`
copies it to `/app/out/derive_report.py` and runs it on `/app/data` and `/app/out`.

Out of bounds: writing artifact values as literals (`negative_hardcoded_sample_answers`);
naming `/tests`, `/solution`, `/logs/verifier` or a reward file in the program or its
reports (`negative_reads_tests_or_reward_files`); importing a third-party package or
reaching the network (`negative_external_dependency_or_network`); output whose bytes vary
between runs (`negative_nondeterministic_output`); changing, renaming or deleting anything
under `/app/data` (judged R9).

## Load-bearing work

10 artifacts are collected under `/app/out`, and every one of them is graded:

- `/app/out/derive_report.py` - the stdlib-only program, run as
  `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`. The tests re-run it against the
  shipped archive (over stale earlier output), the calibration control, mutated copies of
  the shipped archive and generated archives.
- `/app/out/summary.json` - `report_id`, lifecycle counts, the four network totals,
  per-area and per-class maps, `station_totals`, `channel_totals`, `largest_sample`,
  `budget_nano`, both allocation maps and the network `alerts`.
- `/app/out/policy_audit.json` - applied, revoked and unused certificates, ladder values,
  parameter-source counts, provisional channels, thresholds, reporting and unreported
  channels, rounds, qualifying counts, area reporting counts, standing exclusions.
- `/app/out/data_quality.json` - `input_file_count`, lifecycle counts,
  `conservation_ok`, the `quarantine_reasons` census, amendment anomalies, orphan
  aliases, unrostered-area counts and `quarantine_ratio_ppm` with its alert.
- `/app/out/region_{North,South,West,East}.json` and
  `/app/out/segment_{commercial,public}.json` - one per roster entry, empty ones included.

Shipped-archive figures from the reference: observed 50, accepted 22, voided 4,
quarantined 24 (duplicate 2, unresolved_suspect 1, malformed 6, unknown_channel 1,
no_deployment 1, no_certificate 5, unknown_unit 1, broken_ladder 1, unreported_array 6),
ignored amendments 8, unmatched 9, `canonical_nano` -304719443, `traced_nano` -305124596,
`reported_nano` 80671.
Calibration control: observed 20, accepted 8, quarantined 11, voided 1,
`canonical_nano` and `reported_nano` 69.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier` and `/tests`, then runs
`rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit scores
two channels and `tests/reward.toml` gives each half of the final reward:

- `test_output` - 35 deterministic checks in `tests/test_output.py`: 31 positive (total
  135) and 4 negative (total -20). They compare the agent's reports with an independent
  reference implementation held in the test file, on the shipped archive and on archives
  the verifier builds. Each trap probe derives the expected reports and the reports every
  shortcut reading would produce, then grades only the report keys the shortcut moves.
  Those keys take in the figure totals whenever the shortcut shifts them, so a convention
  that touches every figure is priced by most probes: measured on the test channel, a sign
  flip on `drift_nano` alone scores 0.637 (11 checks lost) and a `traced_nano` that skips
  the gain step scores 0.600 (12 lost), while a narrow slip such as upper-casing the orphan
  alias tokens scores 0.919 (3 lost). The five standing generalisation probes grade the
  standing facts (reporting channels, rounds, qualifying counts, area reporting counts,
  standing exclusions, accepted and quarantined counts, the reason census and
  unrostered-area counts). Every archive the verifier builds is
  sealed read-only before the program runs, the program runs under a fresh unprivileged
  uid, and every process left under that uid is killed once it returns. The empty-archive
  check runs the program into an absent nested output location, so the program has to
  create it. Targeted fixtures exercise the drift position tie on a shared epoch, the
  largest sample tie, an alert gap equal to the gate, a zero numerator unit ratio, an
  empty `entry_id` and a primary standard carrying a nonzero ratio, each in exactly one
  check. The two calibration checks (precedence census and rounding) also run a perturbed
  control (new identifiers, report id and budget, one row dropped, one count moved), so
  copying `calibration_example.json` earns nothing. `negative_hardcoded_sample_answers`
  keys on shipped numeric answer figures only.
- `judge` - 12 judged criteria in `tests/judge.toml`: 8 positive (total 22), 4 negative
  (total -10). R1, R2, R4, R5, R6 and R7 watch the trajectory (calibration outcomes
  compared with the worked example, one half-nanounit case rounded by hand, raw ledger
  lines read with the damaged ones, one reporting round traced by hand, one ladder
  correction summed by hand, the program run on an altered archive copy); R3 is the
  instruction's self-reconciliation constraint; R8 grades the delivered code for review.
  R9 penalises changing the archive, R10 a success claim the agent's own last comparison
  contradicts, R11 a claimed check absent from the session and R12 identical failing
  reruns. Judge criteria never restate a test-graded fact, and no judged penalty repeats a
  test negative.

`tests/reward.toml` weights: `test_output = 0.5/135`, `judge = 0.5/22`, so the combined
reward ranges from -0.301 to 1.000.

Measured with the test channel: `solve.sh` passes every positive check and fires no
negative one (1.000); an empty run scores 0.000; a mutant that gives standing-excluded
samples drift positions scores 0.785. No judged-channel oracle score exists, because the
oracle leaves no trajectory.

## Root cause

Composition, not arithmetic. Each rule in `contract.md` is simple; the work is how they
compose, and the contract withholds the order, the rounding mode and the serialisation.
Standing is a fixed point because floors depend on how many channels already report.
Certificate effectiveness needs the whole ledger replayed in code point order before any
interval is chosen. Value validation must happen after replay because revisions both
damage and repair rows. Every figure is integer nanounits, and the budget exceeds 2^53.

## Solution shape

1. Load the CSV tables with a real CSV reader, the JSON files, and the ledger, splitting
   off malformed ledger lines.
2. Replay the ledger by (sequence, entry_id) in code point order, first posting per
   entry_id, keeping raw field text so damaged values never raise. Apply
   `revise_standard` in the same order, then walk every ladder over the final standards.
3. For each first-row observed sample: malformed check, channel (alias then structural),
   deployment, custody, certificate (unrevoked, covering, later start, higher id), unit,
   ladder; hold at the first failure.
4. Count qualifying observations and iterate the standing closure; hold non-basis samples
   of non-reporting channels as `unreported_array`.
5. Resolve gain, offset and drift, assign drift positions per (channel, certificate),
   compute the floored figure with half-away rounding at each step.
6. Aggregate, apportion by largest remainder, raise alerts, write sorted-key two-space
   JSON with a trailing newline, then re-read and reconcile.

## Ordered plan

1. Read `contract.md` beside `calibration_slice.json` and `calibration_example.json` and
   compare each control outcome with the worked example (R1).
2. Settle the rounding convention by hand on one half-nanounit control case (R2).
3. Print the raw ledger lines, damaged ones included, before writing the replay (R4).
4. Write the loader, replay, quarantine chain and standing closure; trace one reporting
   round by hand against the closure output (R5).
5. Sum one certificate's ladder correction by hand and compare it with the program (R6).
6. Write the aggregation and serialisation, with the self-reconciliation step that
   re-reads the reports and exits nonzero on disagreement (R3).
7. Run the program on an altered copy of the archive in a scratch directory, never on
   `/app/data` itself (R7, R9), and keep the code reviewable (R8).

## Pitfalls

- Treating paragraph order as precedence, or validating values before replay.
- Calling `int()` on raw counts: it accepts `1_200` and non-ASCII digits and raises on
  `12.0`, which aborts the whole run.
- Rounding through `float` or default-context `Decimal`; walking a ladder with no
  visited set; dividing by the observed count when the archive is empty.
- Ignoring `valid_to`, or treating it as exclusive.
- Sorting tied ledger entries naturally or case-insensitively.
- Walking ladders over the standards table as shipped, or applying standard revisions in
  file order; coercing a quoted `ratio_ppm` instead of ignoring the revision.
- Counting conditional observations toward standing, or stopping after one round.
- Applying the floor before drift and offset; confusing the two tie-break directions.
- Apportioning through floats; dropping empty buckets; unsorted keys or no newline.
- Opening anything under `/tests` or editing `/app/data`.

## Provenance

```yaml
uuid: ae640566-6067-508e-b982-0158d72da2d4
instance_id: ae640566-6067-508e-b982-0158d72da2d4
task_name: terminal-bench/ae640566-6067-508e-b982-0158d72da2d4
fix_patch_sha256: 96193adb3c1a37361f7f87043cde76145a523c95fe23ea9959b0f43d6d180faa  # sha256 of solution/solve.sh
solve_py_sha256: b3d7938e313f35bb97a0e19f839d01dce3fa12650ca9b9b07f48ad04d49c1dae  # sha256 of solution/solve.py (974 lines)
test_output_sha256_prefix: 44eba44eda1cf753  # tests/test_output.py (3081 lines)
judge_toml_sha256_prefix: 852fd4022f9a2456  # tests/judge.toml
contract_md_sha256_prefix: 6b5da47c1475cd7b  # environment/data/contract.md (231 lines)
language: python
```
