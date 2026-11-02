# DESIGN: flood-repair-portfolio harden r2 (cb8dada)

## Arithmetic (paid run a1 today)
- Tests 108/108 = 100, judge mid 13.33 (4/30), final 56.66.
- Bar: (tests + 13.33) / 2 <= 35 needs tests <= 56.67, i.e. a1 must lose >= 47 of 108 points; lever share >= 45%.

## Core: Lever 1 (TIMEOUT kind), bigger hidden books, same generator, same stated limit
- Stated limit stays 20 s per book (environment/data/contract.md:15, tests BOOK_SECONDS). Caps stay (contract.md:11-12: 200 rounds, 160 rows, 900 records). instruction.md: "The program will also be run on other books written in the same format." No doc changes.
- Hidden H1, H2, H3: the large-round list of each is repeated 30 times (H1 [(156,13),(160,14)]x30, H2 [(148,12),(160,13)]x30, H3 [(152,14),(144,12)]x30), so each book has 60 large lattice rounds + 40 small = 100 rounds (half the stated cap). Registers scale: crews 700+60k, permits 600+80k, sites 500+60k (k = 60). New seeds 815301, 822402, 833503 (own RNG per book, bookgen.make_book, the same code that wrote the shipped book). Faults, ties, blank_row, audits, order unchanged.
- M, MS, MR, SHIPPED unchanged (shipped book and visible checks stay fast for a1: 2.2-3.3 s, trajectory steps 55/61/70).
- Each hidden book stays its own delivered() call; reruns_identical runs H1 twice more (two more 20 s calls).
- Only edits: WORK/hidden_meta.json seeds/specs -> assemble_tests.py -> tests/test_output.py (_BOOKS seeds, specs, sha256 pins). Every check body, name and weight byte-identical.

## Lever 2 (WRONG kind): none found
- Self-pairs (exclusion of a site vs its own proposal, duplicate permit rows): a1 add() skips a == b (a1_program/derive_report.py:270-272), permit members deduped (294-295).
- Ids fixed width (generator _codes), so string and numeric order agree; households parsing matches contract.
- 150/150 fuzz books MATCH (h1_a1/fuzz.py). No quiet documented branch that a1 gets wrong was found.

## Kill table (Docker python:3.12-slim, --memory 4g --cpus 2, second core busy; rep30 = kill2.log, rep20 = kill1.log)
Verdict at the stated 20 s limit; lever pts = 75 hidden per-book + 3 reruns_identical = 78.

| program | N1 s | N2 s | N3 s | peak MB | verdict @20 s | lever pts kept |
|---|---|---|---|---|---|---|
| a1 paid run (h1_a1/a1_program) | >60 | >60 | >60 | 71 | TIMEOUT x3 | 0/78 |
| first-write (a1 step 11) | >40 (rep20) | >40 (rep20) | >40 (rep20) | 472 | TIMEOUT x3 | 0/78 |
| all-but-one (ref, plain BFS start) | 42.86 | 54.89 | 42.46 | 605 | TIMEOUT x3 | 0/78 |
| dae9563 (memo branch and reduce) | >40 (rep20) | >40 (rep20) | >40 (rep20) | 63 | TIMEOUT x3 | 0/78 |
| strong.py linear sweep | per round >60 (bench4) | | | | TIMEOUT | 0/78 |
| elim_program (verifier min-fill VE) | 7.93 | 7.55 | 6.51 | 117 | EXACT | 78/78 |
| vebest_program (careful enumerator) | 6.86 | 6.51 | 5.93 | 95 | EXACT | 78/78 |
| ref solve.py busy | 1.12 | 1.11 | 0.95 | 49 | EXACT | n/a |
| ref solve.py unbusy | 1.20 | 1.11 | 0.97 | 51 | EXACT | n/a |

- rep20 (80 rounds) check: a1 T@40, T@40, 39.95 s; rep30 chosen so a1 is >= 3x the limit on every book (host noise 20-25%).
- Careful enumerators (VE over a good elimination order) keep the lever: recorded, not a blocker (route1 R5(d)).
- No WRONG and no CRASH anywhere; every finished run matched ref.

## Timing gates
- Ref worst 1.12 s busy = 1/18 of 20 s (<= 1/4 met); limit >= 3x ref (17.9x).
- Per hidden book in the verifier: program <= 20 s + expected() VE ~8 s + generation. Program calls: H1, H2, H3, M, MS, MR, relocated M, 3 missing-input, 2 reruns = 12 x 20 s = 240 s worst, + ~30 s expected = ~280 s worst case; verifier timeout 2700 (90% = 2430). To be measured on oracle in P3.
- Memory: ref <= 51 MB, verifier VE ~117 MB, inside 4 GiB.

## Predicted paid-run score (a1)
- Tests: 108 - 78 = 30 kept -> 27.78. Judge mid 13.33 unchanged -> final (27.78 + 13.33) / 2 = 20.56 (<= 35 met).
- Lever share = 78 / 108 = 72% (>= 45% met); timeout share of a1's loss = 78/78 = 100%.
- Tests mid 27.78 <= 56 met.

## Judge
- judge.toml unchanged (J3a stays). The judge's existing "times only the shipped book" item now has a real cost behind it.

## Docs changed
- No. instruction.md, contract.md, data files unchanged. solution/TRUTH.md gets the new hidden sizes and timings (sha256 by script last).

## Risks
- A faster grader host could bring a1 under 20 s only if it is > 3x faster than this Docker host.
- Verifier hidden-book generation and VE time to be measured in P3; if worst > 2430, drop to rep20 (a1 still >= 2x limit).
