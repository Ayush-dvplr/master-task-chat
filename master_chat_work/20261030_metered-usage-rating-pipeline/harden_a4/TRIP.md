# TRIP: run a4 on bbc865f36130 (harden round g37_a4, board 1e969db)

Score: tests 62.09 (262/422), rubric 26.0 (13/50), final 44.05; 35 agent steps.

## Tests: why a4 lost all 160 lever points

Loss kind is TIMEOUT, not WRONG. The gate TRIP label "WRONG" is a classifier error:
every lost lever check in verifier/test-stdout.txt fails with "no result within 15
seconds" / "no documents ... within 15 seconds" (RUN_LIMIT_SEC = 15,
tests/test_output.py:29; stated limit rating_contract.md:48-49).

Measured in Docker (8g, 2 cpus, cap 60 s), WORK/g37_a4/meas_a4.log:

| world | input | reference solve.py s | a4 s | verdict |
|---|---|---|---|---|
| hidden | 1600 rows/collector | 0.27 | 0.38 | EXACT (all docs) |
| long-1 / 2 / 3 | 11.3-12.8 MB, 212-237k lines | 3.12 / 3.38 / 3.71 | > 60 / > 60 / > 60 | TIMEOUT |
| ladder-1 / 2 / 3 | 37-38.6 MB, 412-437k lines | 4.49 / 4.65 / 4.57 | > 60 / > 60 / > 60 | TIMEOUT |
| ladder-4 | 37.5 MB, 418k lines | 4.24 | > 60 | TIMEOUT |

An earlier run with a 300 s cap had long-1 still running after about 240 s.

Root cause: a4 `load_accounts` (WORK/g37_a4/a4_program/transform.py:131-141) walks
the parent chain to the top separately for each account, with a fresh `seen` set
each time. That costs O(accounts x depth). The lever worlds contain one reseller tree
with depth >= resellers*3/4 (about 8000 or more, tests/test_output.py:582), so the cost
is quadratic and the run times out. This is old lever LV-MU-8. a4 reads no doc line
wrongly.

Correctness check of the rest of a4:
- Full read of transform.py (715 lines) against rating_contract.md (230 lines) and
  ref_compute (tests/test_output.py:36-320). Each of these is implemented the same as
  the reference:
  - duplicates first, per file (:116-119); check order (:121-131); canonical ids (:93-94);
  - per-collector product names (:107-110); tier bisect on the counter (:154-162);
  - plan history with same-ts changes in file order (:145-150);
  - committed from the accounts.csv plan; credit and true-up shares with the 0.50 floor
    and reshare (:164-194); half-even cents; 4 dp rates; every document and key (:198-230).
- Differential fuzz in Docker (WORK/g37_a4/fuzz.py, fuzz_a4.log): 11 seeds x 11
  document-valid perturbations = 121 runs, all EXACT. The perturbations were:
  - plan-change shuffle; accounts shuffle; non-canonical ids; padded cells;
  - shuffled tiers and products; shuffled ini sections; west token order;
  - north key order; xml pool order; all of them at once.
- Flattened-parent probe (ladder-1/2 with each parent set to its root; groups unchanged):
  a4 EXACT in 32.1 s / 50.6 s (meas_a4_flat.log). A second slow spot on the 50000-tier
  card; still TIMEOUT, never WRONG.

Documented behaviours that a4 gets wrong and no test grades yet: none found.
Holes noticed but not usable, because the doc does not define them and the reference
would disagree:
- CRLF in accounts.csv breaks the reference header key.
- A pool amount with more than 2 dp: the reference truncates, a4 rounds.
- Credit base 0 with minimum > 0: a4 raises ZeroDivisionError.

## Judge: why each criterion was earned (13/50)

| crit | w | a4 | how (step) | cheap? |
|---|---|---|---|---|
| R1 timed run after last edit | 3 | 3 | step 34 `time` on /app/data, real 0.446 s | cheap: one timed run on shipped data |
| R5 control mismatch refusal | 3 | 3 | step 24 north count altered, exit 1 | cheap: one-line edit |
| R6 no silent except | 3 | 3 | transform.py has no handlers | cheap (code quality J4, keep) |
| R7 every line validated | 3 | 3 | crosscheck1/2 recompute each line | real but cheap for an Opus agent |
| R9 foreign cwd/out run | 3 | 3 | step 21 run from /tmp | cheap |
| R23 final names checks run | 1 | 1 | final message step 37 | cheap |
| R11 claim without output (neg) | -3 | -3 | step 23 rounding results never shown | honest negative (J3), keep |
| R10 lists each file | 1 | 0 | grouped names | |
| R2-R4, R8, R16-R22 probes | 3 each | 0 | none done: built input smaller than shipped, R4 removed two files, no >=1000-tier or >=1000-deep build (R16/R17) | real probes |

FALSE_CLAIM: the step 37 final message says "byte-identical". EASY: transform_exists w1.
