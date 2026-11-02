# PL note - metered-usage-rating-pipeline (1f91f8f), QL round 1

Fixed (4):
- F-1: every cached month, expected document set and program run in the tests is now built once, under its own lock (test_output.py:1027-1036). Before, rewardkit's 8 threads built the same long month up to 8 times. Measured verifier wall is in TRUTH.md.
- F-2: run limit raised from 15 to 20 seconds in the tests, the seven check descriptions, rating_contract.md:49 and TRUTH.md (worst oracle run 6.35 s x 3 = 19.05 s). No lever lost a point; the a4 program still times out on every long and ladder month.
- M-1: all nine TRUTH.md digests recomputed by script after the last edit.
- M-2: instruction.md:28 now says this month's documents are graded as they stand in /app/out and the program is run again on fresh extracts of other months. No rule or hint added.

False positives / kept (no change, carry-over from v4):
- W-1: 113 checks is a recorded warn (kit 03:62, KEPT G03-2), no hard cap.
- W-2: weights grade order, not share (kit 03:51); limit stated in rating_contract.md:48-49.
- W-3: n2 fires only when the delivered figure is visible in the transcript and differs (kit 04:72).
- W-4: criteria reward checking habits, which kit 04:86 asks for; the agent cannot read judge.toml (test.sh:8).
- W-5: trying to open grader paths is the cheat n4 targets (kit 04:88), whether or not the path exists.

Unsure: none.
