WHAT IS LEFT (4 Nov 2026, handed over from the cloud planning session)

1. Install STAGE A on the Mac (Ayush, with the session's help): upgrade_plan/delivery/README.md. Clone ROOT from delivery/mc2.bundle, copy DATA once, then upgrade one tag at a time (backup, preflight, printed git commands, recheck). Checks only the Mac can do: cold recovery test of the master (MASTER_RECOVERY part B), DCP layering (G1), opencode project config and global plugins (Q78), precheck on a known bundle (set upgrade.known_bundle in settings), real harness tests.
2. At mc2-v2.5: ask Ayush whether to save the new kit snapshot (kit 487b4697, kit_watch.py save --by "<his words>").
3. Two small open decisions: a glossary of old lever labels (W2, G8a, J2b) used in templates, or rename them; a prompt without its "Template:" line: warn (today) or refuse.
4. STAGE B blockers (PLAN_FINAL.md section F): paid run wrap and task name guard in harness queue/master_queue.py (needs Ayush's proceed, R35); Q78; Q19 Mac measurement (tmp/W1-031/MEASURE.md); a short design of steps 6 to 10; then Ayush types PROCEED for STAGE B.
5. Not blocking: Q140 (classify 6 old intake tasks); the 40 unstudied teammate tasks (batches B11 to B24 paused for credits); the paused DEFECT family review (CONFLICT_REVIEW.md PAUSE NOTE, never restart without Ayush); 4 cleanup notes in tmp/W1-041/MAP.md; DCP off for task sessions measured for one week.
6. The mc2 worktree: recreate it locally from the bundle (SETUP_STEPS.md step 5) before changing the new system.
