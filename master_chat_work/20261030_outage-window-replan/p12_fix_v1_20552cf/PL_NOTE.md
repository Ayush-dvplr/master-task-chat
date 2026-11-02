# PL_NOTE outage-window-replan (P12 fix v1, board 20552cf)

Fixed all QC v1 FAIL and minor findings and two warns. Tests now kill the agent program's process group and any leftover `nobody` processes after every run, grade the 60-second limit the instruction states (was 90), and give every graded input folder the same `docs/` contract files that `/app/data` has. Each fresh hidden season now contains one record that is both an unknown asset and out of season, so the stated order of the intake checks is graded from its first pair. The judge no longer re-grades the missing-input message (R9), R14 no longer stacks with R12 on one invented run, and two new criteria grade the objective pair in the reply (R17, +1) and writes outside `/app/out` (R18, -1). Keywords and tags name the domain; TRUTH wording no longer reads as a work log.

Kept: TS-11 (time-out as the difficulty source, approved by Ayush 30 Oct 04:40; stated 60 s limit, reference at most 2.66 s (h2 2.36 s, h3 2.66 s; WORK/qc1_kill.out) per graded corpus) and oracle x3 (owner rule).

Score shape after the fix: test channel 92 points (unchanged), judge +36 / -18 (was +35 / -17). Blind programs 9aaa86f, 25a31cb and 59480e5 score 18/92 before and after (lever 68 lost, all by time-out at 60.0-60.1 s on h2 and h3 instead of 90.1 s); the reference needs at most 2.66 s.
