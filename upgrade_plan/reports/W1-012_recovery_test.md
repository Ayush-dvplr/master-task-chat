W1-012 REPORT: THIRD COLD TEST (3 Nov 2026)
Recovered correctly: planning state, goal and top priority, agreed line, running card batches, compaction decisions.
Gaps found and fixed (09:39): read order missing the queue and brief; no method to tell finished batches after a compaction; helper id clash with batch numbers; counts 109, 95, 98 unexplained; stale live lines (CR1a, Q84, Q86, Q93, Q96, Q85, Q99, Q75, P1 to P10, "cold tested twice"); card 8.4 KB with a run on NEXT STEPS; card time behind the last commit; one card over 3 KB.
Fix: RESUME.md rewritten (RUNNING NOW block, short decisions), tmp/S2-CARDS/CARD_RUN.md procedure, statuses corrected, recovery prompt version 3.
