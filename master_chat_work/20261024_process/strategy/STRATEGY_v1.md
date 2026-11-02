# STRATEGY v1 (master, 24 Oct 11:46 IST)

Written by the master instead of continuing session e66cd5f (Ayush, 24 Oct 11:26, item 5). Inputs: this folder's SCENARIOS.md, CRITIQUE.md, ALTERNATIVES.md; qc_reverse/A and B; MASTER_UPGRADE_PLAN_v1.md (approved).

## Goal
A task is done when the live kit gives zero findings (fails, minors, warns; dec 101) and 2 real Opus runs both score tests < 100, rubric < 100, overall < 70. Nothing else counts as progress.

## What decides hardness
- Real Opus runs, read with loss.py. Local reflex or per-lever solvers are not evidence (0.11 local vs 100 real).
- Points are lost to computation the shipped data settles (dispatch hidden_h1..h4, emberforge multi-unit charge, peer gm-arena). Withheld rules of engagement, unstated literals and vague wording lose QC rounds, not Opus points.
- The judge is the cheapest lever: criteria built from what the probe shows Opus skipped (A5), only where the oracle path does it.

## Pipeline (per task)
idea with a named computation trap -> build (P2 v3) -> precheck.sh CLEAN -> private probe on our harness (dec Q-A a, never submitted) -> loss.py -> kill if tests >= 95 -> judge criteria from the probe -> 1 QC -> at most 2 fix rounds -> stop at first PASS -> 2 gate runs -> PL.
issue.py refuses anything outside this; only Ayush's verbatim override lifts a refusal.

## Portfolio now
| task | state | next |
|---|---|---|
| dispatch | fix 77e8554 | 1 QC, then 2 gate runs (needs rubric <= 66.67 at tests 67.33) |
| emberforge | fix 5336aa7 | private probe, loss.py, 1 QC |
| caldermoor, season, numeric | read a1ab2d0 | FIX or DROP per read (season and caldermoor are judge-only gaps; numeric tests 98.81 is a kill unless a new trap) |
| match-replay | fix | fragment grammar into calibration.md, then probe (Q54) |
| vendor | killed | real run 100/100/100 |
| schema, sentinel, sensor, district, cohort-retention | parked | new design only |
| peer study | 6c287ec | adopt or avoid list for templates |

## Capacity and order
One Docker run at a time, median 26 min, about 12-15 runs a day. Queue order: gate runs for tasks that passed QC (max 4 a day), then probes capped at 60 min. Time box 8 v3 sessions per task, then drop.

## Measures (checked by the master each day)
- QC rounds per PASS (target 1-2; was 4-7).
- Share of new findings that are fix-induced or harden-induced (was 60%).
- Tasks at gate on 2 runs (was 0).

## Open items for Ayush
Q56 PL note about the kit R6 template; Q52 litellm security (rotate keys); stale question list (one batch close).
