# GROUP_SUMMARY e30c85c (sensor-a2): sensor-network-lsq-correlated-adjustment, attempt 2

Session rename: `name_session.py e30c85c` matched opencode `ses_e96c77f75ffeOCooQH0LvmPEYP` (codex: no match). repo_head n/a; bundle fingerprint `8abc4b9aed1afc3cea4d83bd3a524bca84c29eef`.
Detail: `A_sensor-network-lsq-correlated-adjustment.md`, `B_sensor-network-lsq-correlated-adjustment.md`.

## 1. Table
| task | verdict A | overall / tests / rubric | genuine tests points lost | genuine judge points lost |
|---|---|---|---|---|
| sensor-network-lsq-correlated-adjustment | GENUINE | 90.0 / 100 (62/62) / 80 (12/15) | 0 | 3 (R5 code-structure criterion; genuine against the code, but the criterion is RISKY under JD-15/JD-18) |

History: attempt 1 (bundle v0) 71.16 / 100 / 42.31 (number only). The harden raised the judge score (42 -> 80) and left tests at 100.

## 2. Why the harden failed
- H1-CENTRING: schema.md:66-69 names the file, column, scope (lengths, non-zero partials, tripod) and the exception ("A pillar mount adds nothing"); step 20 printed mounts, step 26 coded it right (derive_report.py:313-318), steps 33-34 confirmed it exactly against the "faulty" `naive_weight` manifest.
- H2-ANGLE-REDUCE: schema.md:99-101 gives the exact range and the reason; shipped OB00213 (north.csv:221, 0.000455 vs 399.999545 gon) shows the error at once; coded at step 26 (L300-304); step 42 checked max |l| angle 0.01381.
- H3-REVISION: schema.md:44-46 pre-empts both reflexes (true id, higher revision); step 17 found the 6 duplicates after un-transposing before any code; coded at step 26 (L321-337); steps 44-45 checked the duplicates agree across conventions.
- H4-CHAIN: the chain is written as numbered sections in execution order with no branch to choose; step 27 (first run) printed vTPv and sigma0^2 equal to TRUTH.md:60-62; step 48 re-ran on a hand-patched extract with different u.

## 3. Natural traps
NO NATURAL TRAP.

Evidence: one program write (step 26, minute 7), never edited (steps 27-53 are runs and probes only); the first run equalled TRUTH; no lever was coded wrong and then fixed. The trajectory stores no reasoning text, so hesitation can only be read from commands, and the commands show none on graded logic. Two near-candidates checked and rejected:
- Steps 33-34 (45 weights differ from `naive_weight`): the only output/data disagreement in the run. Resolved in one step to the correct reading (missing unit conversion + tripod term). It is a confirmation, not a hesitation; it argues for removing the manifest, not for a lever.
- Step 47 genericity copy changed only workbook/policy control values, station/frame names and dropped rows; never mounts, revisions, duplicate order or boundary angles. This is an unchecked area, but the code there is a direct transcription of the sentence and was correct on all three hidden extracts (test-stdout L1-6, 62/62). An untested branch that is coded right from a full sentence is not a trap.

Per the prompt, Phase C stops here. Judge observations (R1-R4 figure copies under J1/JD-8, R5 tri-split narrower than JD-18 ordinary practice, R6+R7 both -5 on the final-reply act under AL-28) are recorded in B sections 7-8 for the master.

## Lessons for the master
- Tests 100 is genuine: whole-document compares on three regenerated extracts, run as nobody; nothing was skipped or trivially true.
- Mutant scores (8/62) measure the cost of a wrong reading under the 54-point cascade, not the chance the agent reads it wrongly; all six mutants are "ignore the sentence" and the agent read every sentence at minute 0.
- Each H-lever was one sentence that named its exception, with shipped rows that separate the readings, and the "faulty" naive_weight manifest decoded H1: three LEAK_LIBRARY causes at once.
- Judge: R1-R4 copy four printed figures (J1); R5's read/compute/write tri-split cost 3 points on readable code and is RISKY under JD-15/JD-18.
- No natural trap in this trajectory; further same-kind hardening of sensor should wait for a blind-solve gate (district a5 lesson).
