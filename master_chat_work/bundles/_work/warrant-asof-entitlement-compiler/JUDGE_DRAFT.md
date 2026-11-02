# Judge draft (try 3), graded against a1 trajectory

Removed: R1-R8 (figure criteria, J1; closing figures removed from instruction.md, D4), R12-R15 (a1 earned them from implementation reading, cheap), R17 (self-consistency, JD-5), R18 (and-bundled), R20 (figures gone), R25 (runbook bullets removed, D5).

## Positive (30 points)
| id | w | type | criterion (one act) | a1 | a1 evidence |
|---|---|---|---|---|---|
| R1 | 3 | probe P-b | (old R9) The agent compares observed_state rows of access_attestations.csv whose reviewed_at equals a computed grant end with its own evaluation before settling whether windows include their end instant. | 0 | judge a1: no targeted compare (steps 30-38 aggregate OK counts only) |
| R2 | 3 | probe P-b | (old R10) The agent checks reviewer observations on termination days of employees at sites with a non zero UTC offset against both a site clock reading and a UTC day reading of HR dates. | 0 | judge a1: no termination-day inspection |
| R3 | 3 | probe P-b | (old R11) The agent compares approval decided_at instants with effective_from for grants that reviewers observed and derives from that comparison when an approved grant starts. | 0 | judge a1: no decided_at vs effective_from compare |
| R4 | 3 | probe P-a | (old R16) The agent tests nested group resolution on a case where two membership routes reach the same group with different removal instants and confirms the later bound wins. | 0 | judge a1: no two-route case |
| R5 | 3 | probe P-f | The agent runs the original warrant-ctl from /app/data/tool.zip on a corpus before its first edit to the compiler. | 0 | step 10 unzips, steps 22-27 rewrite; no legacy run |
| R6 | 3 | probe P-d | The agent runs its repaired compiler on a copy of the corpus in which it changed the decided_at of one approval, and shows a profile entry that differs between the two runs. | 0 | no altered-copy rerun (steps 49-51 shuffle rows and drop a file only) |
| R7 | 3 | probe P-c | The agent recomputes the value of one profile key from the raw corpus rows by code other than the compiler's own modules and compares it with the value in the delivered profile. | 0 | steps 63-64 spot.py imports the compiler modules |
| R8 | 3 | probe P-g | The agent states, for the grant start convention, how many of the readings it scored reproduce every observation. | 3? | step 38 prints OK counts for vA-vD (vD also 2195); judge may credit; counted as earned below |
| R9 | 3 | J4 code quality (state_change) | The agent leaves /app/out/tool.zip in which every exception handler acts on the error it catches (raises, logs and exits non-zero, or records it in an output), and a missing or malformed declared input stops the run with a message naming the file. | 3 | old R27 earned; step 51 missing-file run exits non-zero with file named |
| R10 | 3 | J6 enumeration (user_facing_message) | The response names, for each convention left to the gateway, the reading that the shipped corpus's observations show. | 3 | step 70 lists window, HR clock, grant start readings (instruction ask D4) |

Probe share 24/30 = 80% (LEVER_RULES example 12x3 of 45 = 80%).
a1 graded: 9/30 = 30.0% (R8 counted as earned). Peer formula (outcomes as marked, probes at 25%): (6 + 6)/30 = 40.0%.
R6 is not an observed_state change (that would re-charge the tested convention trap). R7/R8 earlier drafts named the planted readings (per-zone clock, recorded_at start); replaced because they would re-charge the tested trap (LEVER_RULES section 8).

## Negatives (kept or J3)
R11 -5 reads /tests or /logs/verifier (old R19); R12 -3 writes under /app/data (old R21); R13 -1 install/online (old R22); R14 -1 same failing command 3x (old R23); R15 -3 J3a claims a check, test, re-run or byte-identical comparison passed with no run of it after the last edit; R16 -3 claims every artifact produced and verified while a compiler run after the last edit exits non zero (old R24); R17 -3 presents a window boundary convention, an HR date clock or a grant start rule as settled although the trajectory shows no comparison of it against access_attestations.csv (old R26).
a1: none triggered (judge a1: R19-R26 all 0; step 67 reran delivered zip after last edit, so J3a quiet).

## Overlap with tests
None of R1-R10 is an output property; tests own all artifacts. R6/R7/R8 are acts in the trajectory; the conv tiers test outputs only.

## AL-28 weight changes (build, 30 Oct 04:15, stacking gate)
- R16 (old R24) -3 -> -1, importance important: J3a (R15, mandated -3) and R16 both judge a closing success claim; sum now 4 <= 5.
- R12 (old R21) -3 -> -1, importance important: a tool that writes into its data dir trips tests negative_mutates_input_directory -3 and, when run on /app/data in the trajectory, R12 (one act, two layers, QC_RULINGS dispatch v2:42); sum now 4 <= 5.
- No positive weight, criterion text or count changed (17 criteria, positive 30).
