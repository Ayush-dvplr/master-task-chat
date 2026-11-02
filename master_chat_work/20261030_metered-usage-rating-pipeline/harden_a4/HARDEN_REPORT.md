# HARDEN_REPORT g37_a4 (board 1e969db): NO CORE

Session renamed 1e969db in opencode. The codex list reported no match.

## Status

- BUNDLE was not edited. Tree sha bbc865f36130 was the same before and after.
- Tasks_INPUT was not touched.
- Phases 2 and 3 did not run: no build, precheck, stacking check, oracle, nop, stub or
  forgery runs.

## Diagnosis (TRIP.md)

- All 160 lever points a4 lost are TIMEOUT. The gate labelled them WRONG by mistake.
  - Every lost check says "no result within 15 seconds".
  - In Docker, a4 ran past the 60 s cap on all 7 long/ladder worlds; the reference takes
    3.1-4.7 s.
- a4 is EXACT on the hidden world, on 121 fuzz runs that only change things the documents
  allow, and on 2 flattened-parent ladder worlds (32 s and 50 s).
- Causes: an O(N x depth) parent walk (transform.py:131-141, old LV-MU-8) and a second slow
  spot on the 50000-tier card.

## Arithmetic

- Before: a4 tests 62.09, timeout share 37.9% (already above the 30% cap).
- Every point a4 loses is a timeout point, so a4 tests = 1 - timeout share >= 70 under the
  cap. Note 5 needs a4 <= 60.
- Try 1, held-out WRONG families: none exist.
- Try 2, compliant timeout design plus zero-weighting judge R1/R5/R9/R23: predicted
  a4 = 70 tests, judge mid about 3-8, final about 36.5-39, which is above 35.

## Kill table

See DESIGN.md:
- a4 TIMEOUT on 7/7 lever worlds, EXACT elsewhere.
- Reference EXACT, 4.65 s max against the 15 s limit.

Docs changed: n. Judge changed: n.

## Lessons for the master
- The gate TRIP marks a timeout as WRONG; read test-stdout for "within N seconds" before planning | template_change: gate TRIP classifier, timeout message match
- A program that reads every stated rule right can only lose on scale, so the 30% timeout cap sets its floor at 70 tests | no change: rule conflict for the master to settle (cap vs a4 <= 60)
