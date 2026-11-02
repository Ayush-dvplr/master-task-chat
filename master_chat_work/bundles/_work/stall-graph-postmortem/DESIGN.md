# DESIGN stall-graph-postmortem (reconstructed 26 Oct 2026, harden r1 Phase 1)

Origin: built by Aakarsh Kumar outside the pipeline. This file is reconstructed from
`solution/TRUTH.md`, `environment/data/*`, `tests/test_output.py` and `tests/judge.toml`
as they stand at harden r1 start (only the master's `_grant_read` fix differs from the run copy).

## Task
A lock-stall post mortem. The agent delivers `/app/out/derive_report.py`
(`python3 /app/out/derive_report.py <DATA_DIR> <OUT_DIR>`, no-arg fallback `/app/data` `/app/out`,
stdlib only) that decodes a flag-word wire journal (`stall_journal.psv`), joins a thread probe and
park export, resolves worker identity through a revisioned alias registry, settles lock-class blame
on rung ladders to a fixpoint, and writes nine documents: `summary.json`, `policy_audit.json`,
`region_{East,North,South,West}.json`, `segment_{commercial,public}.json`, `data_quality.json`.

## Hidden structure
- Nine withheld wire constants (60 candidates, `calibration-and-controls.md:10-20`), settled from the
  calibration population against 11 control figures (`control-slice-figures.json`), staged one
  constant per control (reference `recover`, `tests/test_output.py:652-680`).
- Twelve flag-word transforms (`journal-and-wire.md:42-95`), each with a weight-5 `trap_*` check on a
  hidden corpus that forces only that flag (`_trap_probe`, `tests/test_output.py:1340`).
- Thirteen hidden window variations (`generalises_*`, `tests/test_output.py:1550-1658`), each a
  reseeded challenge corpus with one generator mutation (`build_plan` 907-1010, side-table
  generators 783-905).
- Shipped window: five whole-document checks at weight 3 (`tests/test_output.py:1372-1418`).

## Grading (as built)
- Channel A tests: 36 checks, 32 positive = 142, 4 negatives = -18; reward.toml
  `test_output = 0.5/142`. Whole-document exact text match of the 8 post mortem reports plus
  `data_quality` keys accepted_count, event_count, rejections, reconciliation and
  settlement.quarantined_classes (`GRADED_QUALITY_KEYS`, `tests/test_output.py:1315`).
- Channel B judge: 14 criteria, 11 positive = 37, 3 negative = -9; `judge = 0.5/37`; batched,
  gpt-5.6-sol, ATIF trajectory.

## Harden round 1
Baseline (master rescore on the fixed grader): tests 132/142 = 93, judge 100, overall ~96.
Phase 1 diagnosis: `OUT/DIAGNOSIS.md` (harden_r1). Master GO 14:42 IST for LV-1, LV-2, LV-3,
the judge rebuild and defects D1-D10.

Phase 2 built:
- LV-1 closed partition set planted in 12 of 25 hidden corpora (8 drop cells, 8 drop a segment,
  4 both); bound restated in `instruction.md:3` and `calibration-and-controls.md:53-55`.
- LV-2 reference follows `journal-and-wire.md`: padding lines follow the events and write the
  owner window; calibration split keeps every control reconciling under both readings; no control
  figure and no sample answer moved; `stall_journal.psv` and `calibration_stall_journal.psv`
  regenerated.
- LV-3 owner tags follow alias rows (`identity-and-registry.md:57-66`), hidden only in 12 corpora.
- Judge: 11 criteria, positives 27 (R1-R6 conduct, R7, R8, R9), negatives R10 -5, R11 -3;
  `judge = 0.5/27`. The self-check stage in `solution/solve.sh` prints each oracle act.
- D3, D4 one reading each; D6 announcements removed; G5 sentence added; D7 TRUTH fixed.
- Measured: each lever alone 42 / 48 / 42 percent of test points; reflex on all three 14/142.
