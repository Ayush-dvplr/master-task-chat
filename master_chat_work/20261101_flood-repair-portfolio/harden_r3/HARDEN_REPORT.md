# HARDEN REPORT flood-repair-portfolio r3 (c510591): NO CORE

## Diagnosis
Paid attempt 3 read contract.md whole (openhands_sdk.txt L469), built an exact solver and finished
correctness checks by step 43 (L6072), then spent about 92 min on speed work and timed out at
7200 s with no final reply (A3_SCORE.md, TIMELINE.md). Its program scores 108/108 on the current
tests. The route-1 search for a WRONG lever on that program found nothing: 1,500 generator books in
five branch profiles and 141 targeted documented-case runs, all MATCH against solution/solve.py
(TRIP.md fuzz table). The only differences are on behaviours no shipped document states.

## Arithmetic
a3 tests stay 100.00 without a WRONG check, so final >= (100 + 0) / 2 = 50 > 40 for any judge.
The timeout lever cannot grow (master note 1: no lower limit, no larger books; a3 5.2-8.3 s busy
against 20 s). Lever share for a3: 0/108. Details in DESIGN.md.

## What was and was not done
- Done: TRIP.md (R3 items with log lines, code read, fuzz table), DESIGN.md (NO CORE), harness
  `WORK/h3_a3/fuzz3.py`, Docker logs under `_runs/20261101/flood-repair-portfolio/harden3-20261101T1755/`.
- Not done (prompt orders a stop at NO CORE): new checks, judge rebuild, time-budget sentence,
  hidden-book prototypes, new kill table, cost table, stacking check, precheck, QC scripts, gate
  lanes, Tasks_INPUT sync. No BUNDLE edit, so STACKING_CHECK.md was not produced and the Tasks_INPUT
  copy needs no sync. Docs changed: no. Bundle tree sha 931f8f817d76 unchanged.
- Rule slip: the first targeted fuzz container started in the same tool batch as a dockfree call
  that printed START=no (FREE_MB=610, three containers of another session running). It finished
  cleanly in under a minute; every later container waited for START=yes.

## Options for the master (one line each)
- Retire or re-route flood: route 1 has no lever left against an a3-class program.
- If kept, only a route that adds a documented rule (docs change, fresh blinds) could create a new
  separating case; that is outside route 1.

## Lessons for the master
- A spec-complete contract plus an exact paid program leaves route 1 nothing; a short fuzz of the paid program vs the reference before issuing route 1 would have settled it | no change: route1 notes R4 (20261101_route1_notes.md:19) already makes NO CORE the stop, the fuzz just has to come first
- The a3 timeout came from speed work after correctness was done, not from a wrong answer; a time-budget sentence alone cannot move tests | no change: arithmetic shows tests 100 regardless
