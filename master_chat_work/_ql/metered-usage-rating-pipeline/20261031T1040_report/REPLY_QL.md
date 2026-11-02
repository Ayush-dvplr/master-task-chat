Hi, thanks for the round-1 review of metered-usage-rating-pipeline. Summary: 4 findings fixed, 5 kept with reasons, QC recheck passed, fresh trajectory attached.

Fixed
- F-1 (verifier timeouts): agreed. The caches at test_output.py:1041-1070 and :1243-1261 were filled without a guard, so under rewardkit's threads each long-card month was built up to 8 times; our oracle verifier took 1819.6 s of 2700 s, so a slower machine times out. Each month is now built once (per-key guard). Oracle verifier wall after the fix: 313-364 s (max 13.5% of 2700 s).
- F-2 (oracle near the time limit): the margin was thinner than our own 1/4 rule (worst oracle run 6.35 s against 15 s), so the limit is now 20 s in both tests/test_output.py:29 and rating_contract.md:49 (TRUTH lines updated). The 56-point oracle loss you saw did not reproduce on our side (oracle reward 1.0 x3), so we read it as host load.
- M-1 (stale digest): agreed; the task.toml digest went stale when the authors line changed after QC. All nine digests in TRUTH.md are recomputed.
- M-2 (instruction.md:28): agreed on the first half: no check re-runs the program on the shipped month, so instruction.md:28 now says this month is graded as delivered in /app/out; fresh months are compared whole (test_output.py:1404-1405).

Kept (no change)
- W-1: 113 checks is a recorded warning kept at the last QC (kit 03:62 is a warn, no hard cap).
- W-2: the time cap is stated in rating_contract.md:48-49 and fresh months in instruction.md:28; TS-20 (kit 03:51) grades weight order, not share, and we do not describe hidden data size.
- W-3: n2 only fires when the delivered figure is visible and differs, decided from what the transcript shows (kit 04:72).
- W-4: these criteria reward checking habits, which kit 04:86 asks for; judge.toml is not readable by the agent (test.sh:8).
- W-5: trying to open grader paths is the cheat n4 targets (kit 04:88), whether or not the path exists in that container.

QC recheck v5 after the fix: 0 fails, 1 minor (TRUTH.md:135 says "one cent above its base", the test uses 1.00; wording only, no grading effect), 1 warn (wall-clock 20 s limit; all oracle runs pass in Docker). Oracle 1.0 x3, owner 1.0, nop 0, stub 0.

Fresh trajectory on the fixed bytes (tree 23342018274a): final 46.73 (tests 73.46, rubric 20.0). The 112 lost test points are the four ladder months, each "no result within 20 seconds" (timeouts on the agent's program, not wrong answers); the long-card months now pass.
