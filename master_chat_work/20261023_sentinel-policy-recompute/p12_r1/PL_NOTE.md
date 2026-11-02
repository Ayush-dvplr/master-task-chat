# PL_NOTE sentinel-policy-recompute (P12 r1, aa5e389)

Status PAUSED. Final tree e478f82d9b72 (start e0ef9c52a757). Full table in RECHECK_FIX.md.

## False positives

None. All 14 findings were rechecked against the live kit (71a653b2) and are real.

## Kept items

- G04-3 JD-16 (warn): R4 "The agent writes a file under /app/out other than the seven declared artifacts." stays as is. Ayush approved it; it is not edited.

## Paused items (need a master ruling)

- G03-1 TS-20 and G03-3 TS-13 (the shipped-artifact split). The master weights (3,2,2,1,1,1) use weight 2, which tests_qc.py:154 does not allow. Two legal tries both failed trap survival:
  - weights 3,1,1,1,1,1 (P 38): reflex 0.2895, and six levers fell below the 0.90 ratio.
  - all weights 1 (P 36): reflex 0.2500, and the controls, allowance and inclusive-window levers fell below 0.90.
  - The reflex bound limits total shipped weight to 3.75, and G3 shipped-only <= 5% allows only one w1 shipped check.
  - The merged w1 check is restored. The options are in RECHECK_FIX.md under "Deviations from master directions" item 1.

## Deviation to confirm

- G04-4 R8: the master wording would fire on the oracle, because solve.py writes summary.json and validation_report.json with json.dumps. It would also stack with the transcript negative to -8. The replacement is "The agent passes the set command a value for /app/out/config.json that differs from the value its repaired resolve printed for that key in the same run." (-5, agent behavior, trajectory).

## UNSURE questions

- None on labels. Question for the master: which of the options in RECHECK_FIX.md "Deviations from master directions" item 1 (a, b or c) applies to the shipped split? Alternatively, does TS-20 accept the merged w1 check, given that the core config is graded at 5 on hidden data?

## Docker (tests-only, live kit exe_copy copies)

oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0 (TS 20261023T190325-5aaf). The first chain (20261023T190241-d48f) aborted at the harbor env prompt before any trial ran, so it was relaunched with `-y --env docker`.

## Lessons for the master

- Check split weights against the reflex bound and ALLOWED_WEIGHTS before issuing them.
- Negatives about hand-written artifacts must exclude the files that the oracle itself writes.
- Make rerun checks reference-first; that one change closes TS-19, CL-5 and CL-2.
