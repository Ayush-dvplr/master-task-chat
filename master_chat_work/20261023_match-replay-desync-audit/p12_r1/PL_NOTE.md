# PL note: match-replay-desync-audit (965f34e), P12 r1

## False positives

None. All ten QC v1 items were checked against the live kit (HEAD 71a653b2) and the bundle. Nine are real; one is unsure.

## Kept items

- W-03 (TS-23, warn): the tests now hold 42 checks (41 plus the new listing check from F-04). The kit cap is a warning only (03_Tests_QC.md:62, tests_qc.py:295). Ayush approves more than 35. Every check grades a different staged capture set or a different named observable. Folding them would break TS-13 (one property per test) and would merge lever checks, which the playbook TS-23 row forbids. Kept as is.

## Unsure, question for the master

- W-02 (DS-21 / IN-9, warn): the control figures digest fragments whose exact text (for example `"%d:%d"` per capture for CTRL-A, comma joined hex lines for CTRL-B to CTRL-D) appears in no shipped file. charter-scale.md:30-33 says only that each fragment is preceded by a vertical bar and written in UTF-8; calibration.md names each control's material in prose. QC ruled it solvable but hard: the agent can find the format by trying layouts until the digest matches the published figure.
  Neither LEVERS.md nor DESIGN.md names this format search as a lever or a stated difficulty, so by your direction I did not add a defence and did not add the table.
  Question: do we (a) keep withholding the serialization and record "digest confirmed format search" as a stated difficulty in DESIGN.md and QC_DEFENCE.md, or (b) publish a short fragment format table in calibration.md?
  Note for the choice: after F-03 every fresh capture set draws its own eleven quantities, so recovery through the controls is now required on every held-out set. A program that cannot rebuild the fragments scores about 0.04 (6 of 158). Option (b) makes the task easier at that step; option (a) keeps it hard but leaves the W-02 warning open.

## Lessons for the master

- A promise like "recover the values each run" needs held-out data that actually moves those values; otherwise no test can tell recovery from carrying.
- When a judge criterion has a clause the oracle fails, the JD-7 playbook says fix the oracle; this round dropped the clause under JD-5 instead, so the playbook could use a JD-5 row.
- Drawing fresh values per corpus can quietly move lever cases out of the graded slice; rerun the single-lever variants after any change to data generation.
