# TRUTH.md - fd7a2544-0f33-5f62-bde4-a35b23b8b163

## Defect

The board's levy engine is retired and neither its source nor its rule book
survives. The agent receives the current export in `/app/data/current` and an
archive of five past exports in `/app/data/archive/export-01` to
`/app/data/archive/export-05`, each with the nine reports the retired engine
printed for it in a `ledger` folder. Every rule has to be recovered from those
ledgers and then applied to hidden exports that combine all of the rules at a
much larger scale. No rule is written down anywhere in the environment; each
one is visible only through its effect on at least one ledger, and each rule
below changes at least one ledger byte when it is implemented the other way.

- (focal) Overlap claims. Standing parcels (winning, not voided, not
  quarantined) claim land latest book first, then by identifier within a
  book. A parcel's claimed region is its grid polygon minus the union of the
  polygons of every parcel earlier in that order. The claimed area, the
  claimed centroid and the base (claimed area times use weight) are what the
  ledgers print; a parcel whose claim is empty is eclipsed, lands in no
  district and is listed in `data_quality.json`. Shared edges and touching
  corners take nothing. Four of the five archive exports hold nested, identical,
  partial, split and union-covered clusters, so pairwise subtraction, the
  wrong claim order and the full polygon centroid each break several reports.
- (focal) Market scale on a turned datum. Hidden exports carry a market
  square of 1640 stalls (800 rows and 800 lanes that cross the whole square
  and 40 small booths) spread over every book. Each stall is an upright
  integer rectangle as surveyed, filed on a market datum (MKS, BZR or SQR)
  that turns the plot by a Pythagorean rotation and scales it by 0.86 to
  0.90, so on the grid every stall is a turned rectangle with rational
  corners and the rows and lanes cross in roughly n squared points. Any
  settlement done in grid coordinates (per parcel subtraction or one band
  sweep per cluster) runs for many minutes. The 60 second budget needs the
  observation that an affine map keeps unions, differences and area ratios:
  settle a cluster that shares one datum in its surveyed frame, multiply each
  claimed area by the transform determinant and map each claimed centroid
  through the transform. The archive markets are small turned markets, so the
  datum shape is visible there.
- (focal) Revisions across books. The winner for an identifier is the record
  with the highest revision; on an equal revision the later book wins. A VOID
  winner voids the parcel, and a later PARCEL with a higher revision revives
  it.
- (focal) FORMAT 2 books store the first vertex absolutely and every `D` line
  relative to the previous vertex.
- (focal) Datum revisions apply from their `from_book` inclusive, and a
  PARCEL `DATUM` override replaces the book datum.
- (drift) The ruleset in force is the one with the greatest `from_book` that
  does not exceed the highest book number in the export; future rulesets
  never apply.
- (drift) A centroid on a diagonal through the origin goes clockwise: north
  east to East, south east to South, south west to West, north west to North;
  the origin itself goes to `origin_region`.
- (trap) Book grammar. Tokens are separated by spaces or tabs, `#` starts a
  comment anywhere on a line, one file may hold several books each opened by
  its own banner, and numbers may be written with leading zeros, trailing
  zeros or as unreduced fractions. A vertex number spelled any other way (a
  leading `+`, an exponent, an underscore, `.5`, `5.`) quarantines the record
  as MALFORMED_NUMBER even though Python's `Fraction` accepts it; ring and
  geometric checks are then skipped while UNKNOWN_DATUM and UNKNOWN_USE are
  still tried. The current and archive exports expose these forms and traps in
  different combinations.
- (trap) Consecutive duplicate vertices are collapsed and counted as repairs,
  never quarantined, and the reported quarantine code is the first applicable
  one in the export's own `quality.json` precedence.
- (trap) Ties: seat awards break ties by larger base, then by the district
  order of `regions.json`; leftover district cents go by larger remainder,
  then district order; leftover parcel cents by larger remainder, then the
  smaller identifier; districts with zero base take no seats; a Huntington
  Hill priority with no seat held prints as `inf`. Most of these show only
  in `export-04`; the `inf` priority shows only in `export-03`.

## Load-bearing work

- Reading the ledgers closely enough to recover each rule, then confirming
  every guess by rerunning the engine on all five archive exports.
- A parser that follows the full book grammar rather than only what the
  current export shows.
- Exact rational geometry: grid transform, orientation repair, area, centroid
  and the claim settlement as polygon minus union, all in `Fraction`.
- A claim settlement that handles the 1640 stall turned market in seconds:
  one sweep per cluster of touching boxes, settled in the surveyed frame when
  the whole cluster shares one datum and every ring is an upright rectangle
  there.
- Divisor method seats, Hamilton cents and the tie rules, written once and fed
  to every report.

## Verification

Channel A rebuilds the current export, a hidden evaluation export, nineteen
named fixtures and six generated allocation fixtures from seeds, runs the
submission on each under a dropped uid, and compares its reports with an
independent reference implementation inside the verifier. The hidden exports
use every rule above together with
the book grammar, other datums, uses, district order and precedence, and
the 1640 stall turned market (the current export and the archive exports
hold small turned markets of 24 rows and lanes). Each run gets 60 seconds.

Channel A has 30 positive checks with a total weight of 86: ten checks of
weight 5 cover the focal claim, allocation and evaluation behavior; eight
checks of weight 3 cover the base methods and other material report behavior;
and twelve checks of weight 1 cover artifact consistency, individual levers
and narrow report properties. The large turned-market checks carry enough
weight that a correct but inefficient claim settlement cannot earn a strong
score. The negative checks are:

- `negative_hardcoded_sample_answers` (weight -5): reference answers of the
  current export appear in the engine source.
- `negative_filename_dependent_behaviour` (weight -5): renamed book files
  change the output.
- `negative_nondeterministic_output` (weight -3): different hash seeds
  change the output bytes.
- `negative_engine_imports_non_stdlib` (weight -3): the engine imports a
  module outside the standard library.
- `negative_writes_outside_out_dir` (weight -3): a run leaves files outside
  its out_dir.

Channel B is an 8 criterion rubric on the trajectory, the engine source and
the final note (positive total 10, negative total 10). It asks for a program
comparison of the final engine with every archive ledger, a separate union
area cross-check of the claims, the required current ruleset and district
seat note, and maintainable code. Its negative criteria cover shipped-data
mutation, package installation, agent-created scratch under `/app`, and
online lookup of task-specific answer material. The oracle
scores 86 of 86 on Channel A with every negative check false.

## Root cause

The rules are not stated, so the work is inference: every reported value is
the output of a rule that the agent has to name, test against the archive
and keep consistent across reports. Several rules only show in one archive
export, and the hidden exports both combine them and add a market far larger
than anything archived, so a solution tuned to the current export or to the
small archive markets fails almost every check.

## Solution shape

`solve.py` is installed as `/app/out/derive_report.py`. `read_books` splits
each file into `SurveyBook` objects, strips comments and validates every
number with `read_number`. `Policy` loads the tables, picks datum revisions
inclusively and the ruleset by the highest book. `Record` ranks by revision
then book. `Ring` collapses duplicates and finds defects. `Parcel` maps the
ring to the grid, repairs orientation and computes area and centroid.
`Footprint`, `StallSweep` and `Patchwork` settle claims: footprints whose
boxes touch form a cluster; a cluster whose members share one datum and are
upright rectangles as surveyed is swept once in that frame with a heap of
open claims and mapped back by the determinant and the transform; a cluster
of upright grid rectangles is swept the same way on the grid; any other cluster is cut into horizontal bands at
every vertex and crossing level, and each stretch is credited to the earliest
footprint covering it. `Apportioner` awards seats, `hamilton` splits cents,
and `LevyEngine` writes the nine reports with `json.dumps(indent=2,
sort_keys=True)`.

## Ordered plan

1. List the archive and read every ledger beside its export.
2. Write the parser and reconciliation; compare `data_quality.json` and the
   record counts of `summary.json` on all five exports.
3. Add datums, rings, quarantine codes and the precedence order.
4. Add area, centroid, claims and districts; compare region files.
5. Add rulesets, seats and cents; compare `policy_audit.json` and the segment
   files, using `export-04` for the tie rules.
6. Settle each cluster in the frame its stalls were surveyed in and time
   it on a self-built turned market of at least 1640 crossing stalls in
   twelve or more books.
7. Rerun all five archive comparisons, a renamed copy and the current export.

## Pitfalls

- Using `Fraction(token)` directly accepts spellings that the retired engine
  quarantined.
- Reading only the first book of a file, or treating `#` as a comment only at
  the start of a line.
- Equal revisions resolved to the earlier book; `D` lines relative to the
  first vertex; datum revisions applied only after their `from_book`.
- Claims settled by pairwise subtraction, by earliest book first, or placed
  by the full polygon centroid; eclipsed parcels left in a district.
- Settling claims one parcel at a time against every earlier claim, or
  sweeping the turned market on the grid, both far too slow for sixteen
  hundred crossing stalls.
- Floats anywhere on the path to a printed number.

## Provenance

```yaml
uuid: fd7a2544-0f33-5f62-bde4-a35b23b8b163
instance_id: fd7a2544-0f33-5f62-bde4-a35b23b8b163
task_name: terminal-bench/fd7a2544-0f33-5f62-bde4-a35b23b8b163
language: python
solve_py_sha256: 0e8b030e26106527154fec3b32cd953d20076bba03045fd02847469a1405cb0d
```
