# TRUTH.md - counter-page-crash-recovery

## Defect

The archive `/app/data/project.zip` holds `pagerecover`, a package that recovers counter pages after a crash. Each
crash image of a book has pages of signed integer slots on disk, a write-ahead journal of updates, CLRs, commits,
aborts, ENDs and fuzzy checkpoints, and a master checkpoint record. The contract (`/app/data/recovery_contract.md`)
states the recovery protocol (analysis from the master checkpoint, redo from the smallest recLSN with a per-record
page decision, appended ENDs and CLRs in a stated order) and four recovery documents computed from the recovered
page image.

- (focal) `src/pagerecover/recovery.py` replays only the changes of committed transactions and then reverses every
  update of each loser in its own reverse order, ignoring CLRs already in the log. Loser writes flushed to disk stay
  in the image, updates already compensated by an earlier rollback or an interrupted restart are undone twice, no
  END is appended and CLRs do not move pageLSN, so `module_core.json` and every figure taken from it are wrong.
- (focal) The appended record sequence must follow the stated audit order: ENDs for winners in ascending id, ENDs
  for losers with no undo point in ascending id, then one global undo loop that always takes the loser whose undo
  point has the largest LSN, appending its END at once. Each appended record consumes the next LSN, and CLRs set
  pageLSN, so the order decides the recovered pageLSNs, the image digest and the appended list.
- (drift) `src/pagerecover/pages.py` keeps only the low 32 bits of pageLSN (LSNs exceed 2^32), reads slots as
  unsigned and skips the crc; `loader.py` lowercases page ids through configparser, imports `tomli`, reads the
  journal in file order (lines are shuffled) and returns empty text for a missing file; `reports.py` hashes
  non-canonical JSON and sums signed compensation; `cli.py` exits 0 on a missing input; `pyproject.toml` has
  version 2.3.0, Python 3.8, a `tomli` dependency and package dir `lib`.
- (trap) The shipped book carries no record that changes the same page twice and no earlier restart stopped right
  after a CLR whose undo_next names another CLR. A redo that updates pageLSN after each change, or an undo walk that
  treats such a CLR as an undo point, is exact on the shipped book and wrong on every hidden book image.
- (trap) The shipped unit tests in `tests/test_smoke.py` pass for both the shipped method and the contract method.

## Load-bearing work

1. Decode the book exactly: case-sensitive page ids, u64 pageLSN, signed i64 slots with crc32 per frame, journal
   sorted by lsn per image, master LSN from `checkpoint.toml`, rejections in the stated order.
2. Analysis from the checkpoint_end whose begin_lsn is the master LSN, scanning from the master LSN, END removing
   a transaction, the dirty page table keeping the first recLSN.
3. Redo from the smallest recLSN; for each record decide its redone pages against the pageLSNs before any of its
   changes, then apply every change on those pages and set their pageLSN to the record lsn.
4. Appended records in the stated order, the undo point walk following undo_next of CLRs (including CLRs written
   by earlier interrupted restarts) so each update is undone once, CLR undo_next = undone update's prev.
5. Build the four documents from the recovered image; package the repaired project as stated and run it from the
   archive.

## Verification

The tests extract `/app/out/package.zip` and run `python -I -B` with the archive's `src` first on the path and
`runpy` on `pagerecover` (`recover --data DIR --out DIR`) as user `nobody` (setpriv) from a foreign working
directory. Every hidden book is generated at grade time by the seeded builder embedded in `tests/test_output.py`;
nothing from those books ships in the image. Hidden images are rejection-sampled until each carries every one of
these cases: a redone record with two changes on the same page, a record whose lsn equals the pageLSN of a page
it changes, a CLR whose undo_next names a CLR, a loser with no undo point among losers with work left, winners
whose ids disagree with table order, a recLSN below the master LSN, a loser write flushed after a committed write
to the same page, checkpoint tables that disagree with the log tail, and two or more earlier restarts that each
wrote CLRs before being interrupted.

| book | images | records per image | limit (s) | oracle (s) in Docker |
|---|---|---|---|---|
| max (H3) | 12 | up to 1149, 24 pages | 60 | 0.54, 0.29, 0.33 |

Docker: python:3.12-slim, uid 1000, network none. The other hidden books (dense 12 images, restart 12, rejection
11, relocated 8, scaled 12) finish in 2 to 4 seconds of grading each, most of it book generation.

Expected documents are recomputed at grade time by the embedded reference and compared whole (parsed JSON); a
mismatch reports the first differing path.

Channel A checks and weights (positive weight total 95):

| check | weight |
|---|---|
| artifacts_present | 1 |
| archive_layout | 3 |
| package_metadata | 3 |
| build_report_values | 1 |
| selftest_truthful | 3 |
| shipped_core, shipped_metrics, shipped_appended, shipped_summary | 3 each |
| dense_core, dense_metrics, dense_appended, dense_summary | 5 each |
| restart_core, restart_metrics, restart_appended, restart_summary | 5 each |
| max_core | 5 |
| max_summary | 3 |
| max_within_limit | 3 |
| rejection_core | 5 |
| relocated_core | 5 |
| scaled_summary | 5 |
| missing_input_rejected | 3 |
| rerun_identical | 3 |
| negative_hardcoded_sample_answers | -5 |
| negative_shipped_tests_dropped | -3 |

`negative_hardcoded_sample_answers` fires when the archived source contains an image id of the shipped book or the dense hidden
book output reuses shipped image ids. `negative_shipped_tests_dropped` fires when the archived `tests/test_smoke.py` drops a
shipped test or marks one skipped.

Measured test points (reference-equal on all books, variants scored on the same hidden books): oracle 95 of 95 with
both negatives silent; shipped method (commit-filter replay, naive undo) 20; textbook ARIES with END placed when a
chain reaches its begin and pageLSN updated after each change 23; eager pageLSN redo only 42; one-hop undo_next 32;
per-transaction undo order 33; redo from the master LSN 33; empty output 0.

## Root cause

The original author treated recovery as replaying committed work over the disk image. Under steal and no-force,
disk pages hold uncommitted writes and miss committed ones, so recovery must repeat history from the dirty page
table and then undo losers with compensation records that are themselves logged, flushed and possibly interrupted.
The decoding defects come from narrow struct formats and library defaults (configparser key folding).

## Solution shape

- `loader.py`: checks the six inputs and raises `MissingInput(name)`; `optionxform = str`; `tomllib`; journal rows
  sorted by lsn per image; bad frames counted (crc mismatch, duplicate page).
- `pages.py`: `>Q` pageLSN, `>%dq` slots, crc32 over the frame bytes.
- `recovery.py`: `validate_image` in contract order; `analyse`; `redo` with the per-record page decision;
  `undo_point`; `undo` producing the appended records; `recover_image`.
- `reports.py`: canonical sha256, absolute compensation, audits.
- `cli.py`: missing input named on stderr, exit 2, no document written.
- `pyproject.toml`: version 2.4.0, Python 3.12, no dependencies, package dir `src`.

## Ordered plan

1. Read the contract, the config files and the project.
2. Fix packaging and decoding; confirm the unit tests.
3. Rewrite analysis, redo and undo from the contract.
4. Cross-check the recovered image against a closed form (disk value plus later log deltas minus every loser
   change) and the appended list against invariants; rerun on an altered copy.
5. Build package.zip from `expected_targets.json` and `compiler_flags.json`, run the archived package, write
   selftest.json and build_report.json.

## Pitfalls

- Updating pageLSN after each change of a record skips its second change on the same page.
- A CLR reached through another CLR's undo_next is not an undo point; follow its undo_next.
- ENDs consume LSNs and losers with no undo point get their END before any CLR, so the order moves every pageLSN.
- Redo starts at the smallest recLSN, which can lie before the master checkpoint.
- The archive is what runs; a fix left only in `/app/project` scores nothing on hidden books.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: counter-page-crash-recovery
task_name: terminal-bench/counter-page-crash-recovery
fix_patch_sha256: f41b00f0c6a7a287cb896bfc996c0d0befede1bd6d7002d757f9ba5c1ac5615d
solve_py_sha256: bc70399411fe5f700eddfb83b00bf12125b69296abfe9862a683ee5460f11395
language: python
```
