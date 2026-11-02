# TRIP flood-repair-portfolio harden r3 (c510591)

Bundle tree sha before any work: 931f8f817d76 (no BUNDLE edits made in this round).
Paid attempt 3 program: `a3_score/a3_out/derive_report.py` (697 lines, sha 69670ef2...).
Raw log: `.kiro-run-flood-repair-portfolio-20261101T145306/.../agent/openhands_sdk.txt` (9509 lines).

## Reused by reference
- `20261101_flood-repair-portfolio/a3_score/A3_SCORE.md`: a3 program 108/108 on the current tests
  (verifier 96.56 s); N1-N3 kill driver EXACT at 5.2-8.3 s against the 20 s book limit; judge
  prediction low/mid/high 13.33/30/40, predicted final 65; actual attempt 3 AgentTimeoutError at 7200 s.
- `20261101_flood-repair-portfolio/a3_score/TIMELINE.md`: 72 actions, correctness work 14:54-15:22,
  about 92 min of speed work on synthetic cap-size books, about 68 min waiting on long runs.

## R3 items (trajectory first)
| item | evidence (openhands_sdk.txt line) |
|---|---|
| contract.md opened whole once | L469-L485 (`view /app/data/contract.md`) |
| files opened whole: manifest.json, benefits.ini | L678 (`cat manifest.json && cat benefits.ini`) |
| files only seen by head, then parsed in code: proposals.csv, segment_codes.tsv, sites.jsonl, region_codes.csv, crews.tsv, permits.csv, audit_queries.txt, exclusions.json (600 bytes) | L678-L680 (`head -5 proposals.csv`, `head -c 600 exclusions.json`) |
| files never opened at all | none of the nine; instruction.md read in the prompt (L390) |
| shipped-fitted literals | none: no round, proposal, site or book id literal in the program (grep of R/P/S/B ids returned nothing) |
| tuning literals (speed only, no output effect) | `sys.setrecursionlimit(20000)` L7556-L7594; `DP_DEADLINE = 14.0` L7797-L7835 (with DP_RATE 500000, DP_FLOOR 300000) |
| last correctness check | TIMELINE step 43 (L5689-L6072): hand check of the 19 rejected rounds, exclusion resolution, withdrawn permits, households as whole numbers |
| where checking stopped | L6117 (`/tmp/gen_book.py` created, step 44); everything after is speed work on synthetic books (L6374 onward), last edit L8631, last command L9505 |
| final reply | none written (timeout); the 19 rejected ids are printed only inside the trajectory (L5611) |

## Code read (a3 program against solution/solve.py and contract.md)
Every documented branch matches the reference: manifest and MISSING_FILE order; data-row and
row-number rules; all check orders of contract.md:37-40; NONPOSITIVE_BENEFIT first row (:42);
benefit formula (:48); crew, permit (withdrawn ignored), exclusion (either order, site expansion)
conflicts (:54-58); maximum total with the sorted-id tie rule (:62, same 2^n weight encoding as
the reference); every document shape (:70-78). The MWIS solver (reductions, min-degree
elimination DP with a time budget, branch and bound fallback) is exact in every path; the time
budget changes only which exact path runs.
Differences found only on behaviours no shipped document states (not plantable under the
no-unstated-rule bar): duplicate keys in sites.jsonl, region_codes.csv, crews.tsv and
segment_codes.tsv (a3 first wins, reference last wins); whitespace-only lines (a3 skips, reference
crashes); a data row with fewer fields (a3 pads, reference crashes); UTF-8 BOM; `:` as INI
delimiter; non-ASCII ids (a3 writes raw UTF-8, reference escapes; parsed JSON equal).

## Fuzz table (Docker fixscore-flood:latest, --memory 4g --cpus 2, reference = solution/solve.py run as a program)
Harness `WORK/h3_a3/fuzz3.py`; logs `_runs/20261101/flood-repair-portfolio/harden3-20261101T1755/`.

| branch / case | seeds | MATCH | DIFF | first DIFF field | doc cite |
|---|---|---|---|---|---|
| gen-random (0-3 large, 0-19 faults, 20-60 small, 0-12 ties, both orders, blank rows) | 300 | 300 | 0 | none | contract.md:19-78 |
| gen-faults (19 faults per book, every FAULT_KINDS kind incl. two-file and nonpositive-and-file) | 300 | 300 | 0 | none | contract.md:35-42 |
| gen-ties (12 tie rounds: twin and path gadgets) | 300 | 300 | 0 | none | contract.md:62 |
| gen-large (2-3 lattice rounds n 20-60) | 300 | 300 | 0 | none | contract.md:60-62 |
| gen-fixed (declared order as shipped, no blank rows) | 300 | 300 | 0 | none | contract.md:35 |
| households "01","060","0","61"," 5","5.0","+5", Arabic-Indic 3, "60","1" | 3 each | 30 | 0 | none | contract.md:37 |
| risk_override "a","E","AB"," A","D" | 3 each | 15 | 0 | none | contract.md:23,37 |
| every round rejected (duplicate row in each round) | 3 | 3 | 0 | none | contract.md:37,70,74 |
| exclusions.json `[]`; empty audit_queries.txt | 3 each | 6 | 0 | none | contract.md:29,31,72 |
| PAIR X X; PAIR in both orders; VALUE/PAIR of a rejected round | 3 each | 9 | 0 | none | contract.md:72 |
| segment name capitalised | 3 | 3 | 0 | none | contract.md:30,38 |
| rows of round-scoped files for a round not in proposals.csv | 9 | 9 | 0 | none | contract.md:23 |
| one permit id in two rounds | 3 | 3 | 0 | none | contract.md:28 |
| exclusion site + own proposal; site with itself; proposal of another round | 9 | 9 | 0 | none | contract.md:29,40 |
| single-proposal round; one exclusive crew clique with equal benefits | 6 | 6 | 0 | none | contract.md:56,62 |
| variable-width proposal ids (P9 vs P10) and round ids (R7 vs R10) | 6 | 6 | 0 | none | contract.md:21,62,68 |
| benefit exactly 1 | 3 | 3 | 0 | none | contract.md:42 |
| missing file: proposals.csv, benefits.ini, audit_queries.txt, two missing, reordered manifest with two missing | 15 | 15 both exit 1, same stderr, no docs | 0 | none | contract.md:19 |
| exclusions.json declared first; trailing blank lines; shared crew for a whole round; withdrawn-only permit; duplicate permit row; every site in one region; duplicate and reversed exclusion; faults in two files of one round | 24 | 24 | 0 | none | contract.md:21,27,28,35,58,76 |

Targeted totals: 47 cases x 3 base books = 141 runs: 126 MATCH + 15 missing-file runs with
identical failure; 0 DIFF, 0 crash on either side. Planted-effect check (`fuzz_targeted2.log`):
115 runs changed the reference output against the unmutated book; the 26 that did not are
invariance cases whose documented outcome is "no change" (rows of unknown rounds, cross-round
permit ids, trailing blank lines, a permit or exclusion row joining nothing new).

Result: no documented behaviour where the a3 program differs from the reference. none found.
