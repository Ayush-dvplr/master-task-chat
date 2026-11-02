# DESIGN g37_a4 (board 1e969db): NO CORE

Bundle tree bbc865f36130, unchanged. No BUNDLE edits were made.

## Measured facts (Docker, 8g, 2 cpus; logs in WORK/g37_a4/)

- a4 gets every graded document right. It loses only by time.
  - hidden world: EXACT in 0.38 s.
  - long-1..3 and ladder-1..4: all 7 are TIMEOUT. a4 was still running at the 60 s cap;
    the reference takes 3.1-4.7 s (meas_a4.log, meas_ref.log).
- Flattened-parent probe: ladder-1/2 with each parent pointed at its root, so the billing
  groups and expected documents are unchanged. a4 is EXACT in 32.1 s and 50.6 s
  (meas_a4_flat.log).
  - So a4 has a second slow spot on the 50000-tier card, besides the O(N x depth)
    parent walk (transform.py:131-141).
  - Both slow spots are TIMEOUT. Neither is WRONG.
- Differential fuzz: 11 seeds x 11 perturbations = 121 runs, all EXACT (fuzz_a4.log).
  - Each perturbation is a rewrite the documents allow: reordered plan changes and
    accounts, non-canonical ids, padded cells, shuffled tiers and products, shuffled ini
    sections, west token order, north key order, xml pool order, and all of them at once.
- Full read of a4 against rating_contract.md:1-230 and ref_compute: every stated rule
  is implemented as the reference implements it (TRIP.md lists the cites).

## Arithmetic (why note 5 cannot be met)

Let P = positive test points and T = points a4 loses. Every one of those losses is a
TIMEOUT.
- a4 tests = 1 - T/P.
- Note 5 / LEVER_RULES v3.5 (3): crash/timeout share T/P <= 0.30, so a4 tests >= 70.0.
- Note 5 needs a4 <= 60 (aim 50), which needs T/P >= 0.40. This contradicts the cap unless
  some documented behaviour exists that a4 gets WRONG.
- Today: T/P = 160/422 = 37.9%, already above the cap. a4 = 62.09.
- Lowering shipped checks from w3 to w1 (84 to 28 points) gives a4 = 206/366 = 56.3%.
  The timeout share then becomes 43.7%, which breaks the cap further.
- Adding more held-out worlds from the existing generators only adds TIMEOUT points
  (same bound) or points a4 passes (raises a4).

## Try 1: held-out families on behaviours a4 misreads

- Searched three ways: code read, 121-run fuzz, and 2 shallow-tree scale worlds.
- Found 0 documented behaviours that a4 gets WRONG.
- Three candidate holes are undefined in the docs, and the reference would disagree with
  a fair program, so they are rejected (LEVER_RULES 8, no new stated rule):
  - CRLF accounts.csv;
  - pool amount with more than 2 dp;
  - credit base 0 with minimum > 0.
- Result: no family.

## Try 2: compliant timeout design plus judge cut

- Bring T/P down to exactly 30% by adding points a4 passes, or by cutting lever weight.
  Then a4 tests = 70.0.
- Judge changes:
  - Zero-weight the cheap criteria R1, R5, R9 and R23, which a4 earned at steps 34, 24,
    21 and 37.
  - Keep R6 (J4 code quality) and the R11 negative (J3). Keep the probe band R2-R4, R8 and
    R16-R22.
  - Predicted a4 judge mid: R6 3 + R7 3 - R11 3, about 3-8.
- Predicted final = (70 + 3..8)/2 = 36.5-39.
- Against note 5:
  - (a) needs final <= 35: fails.
  - a4 <= 60: fails (70).
  - Blind and first-write programs were not measured, because the bar already fails on a4.
- Result: fails note 5.

## Kill table (a4 first; no new checks built)

| program | world | seconds | verdict | lever pts kept |
|---|---|---|---|---|
| a4 | hidden | 0.38 | EXACT | n/a |
| a4 | long-1/2/3 | >60 / >60 / >60 | TIMEOUT | 0/48 |
| a4 | ladder-1/2/3/4 | >60 x4 | TIMEOUT | 0/112 |
| a4 (flat probe) | flat-1/2 | 32.1 / 50.6 | EXACT but > 15 s limit | n/a |
| reference solve.py | long / ladder | 3.12-3.71 / 4.24-4.65 | EXACT | 160/160 |

Reference/limit = 4.65/15 = 0.31, already above the 1/4 target before this round.

## What would unblock (master decision)

The floor is set by the rule, not by effort. A careful program like a4 reads every stated
rule correctly, so the only lever is scale, and scale is capped at 30% of points. Options:
- Accept a4 at about 70 tests with the judge cut, for a predicted final of about 37-39.
  This misses the bar of 35 but is under the gate's final < 40.
- Add a new documented behaviour: docs change, so 3 fresh blinds are needed.
- Retire the task.

NO CORE: this file.
