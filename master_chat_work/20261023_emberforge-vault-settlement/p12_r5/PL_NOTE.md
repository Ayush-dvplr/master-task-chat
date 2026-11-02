# PL note: emberforge-vault-settlement, P12 r5 (board 51efd20)

False positives: none. All four QC v7 findings (DS-27, TS-25, JD-16, JD-18 / CL-2) rechecked as REAL against the live kit (HEAD 71a653b2) and fixed.

UNSURE questions: none.

## Lessons for the master
- The kit's H6 static check reads the element after `sys.executable` as the executed program, so a grader-written launcher placed there needs its own explicit `chmod` even when the agent program behind it is already staged.
- stacking_check counts the two weight-1 structure checks as isolated rule checks, so its G3 hint reads 31.5 percent (32.7 before this round) while the rule checks themselves are 15 of 54 (27.8 percent).
