MASTER EDITS IN ROOT (found 5 Nov 2026 08:16 IST after Ayush asked why the ROOT master changes system files; WAITING for Ayush)

WHAT GIT SHOWS IN ROOT (/Users/mac/Desktop/mc2_root, HEAD 8ad18ec5 = mc2-v2.5.3; git status --porcelain)
1. master_chat_tasks/RULES_IN_FORCE.md, changed 5 Nov 02:28 (Ayush 02:20 in the master): ORDER no longer has a QL QC before the paid run; push = the RFP bundle sent to the QL; QL loop after the push; QC PASS now ends "Then the paid run (ORDER)" instead of "Then the QL runs a full QC".
2. Changed 5 Nov 08:13 after Ayush 08:11 in the master ("Apply all, save snapshot (Recommended); Exemption holds"; decisions.jsonl): knowledge/BUILD_RULES.md (KIT line and T18 conduct clause), knowledge/FIX_MAP.md (THE LINE, CLIENT PRECEDENCE, rows remapped to kit 48726eb7, new IN-17 row), prompts/templates/_COMMON_RULES_v5.md, P2_build_v5.md, P9_harden_from_results_v4.md, P12_recheck_fix_v5.md, CHANGELOG.md.
3. Not tracked by git but also new: kit snapshot knowledge/fingerprints/qc_48726eb7 (old qc.json moved to archive_5574d77e), which is data and is fine.
4. Untracked .omo/ at ROOT top level (only master_chat_tasks/.omo/ is excluded).

WHY IT HAPPENED
1. Nothing in the master's own rules says system files change only through a release. RULES_IN_FORCE ROLE (R1) says the master "plans, writes and tunes prompts", the old system's way (template edits plus a CHANGELOG line). The rule "the new master only does task work" was said by the upgrade session in chat and in RESUME, never put into the master's rules or tools. Lesson 9 in LESSONS.md.
2. The master asked Ayush each time and wrote decisions.jsonl lines, so it followed its rules as written.

WHAT IT BREAKS
1. The next round (mc2-v2.5.4) prints "git status --porcelain must print nothing ... stop": it stops until these edits are dealt with.
2. The worktree (mc2-v2) does not have these edits; a release built only from the worktree would not carry them, and checking out a release over a changed file can refuse or lose work.
3. Two writers of the same files: what is in use in ROOT is no longer exactly a tagged version.

FLAGS (R_FLAG)
1. The ORDER change (no QL QC before the paid run) contradicts what the upgrade files say for data-product item 3 ("QL QC owed before the paid run", RESUME RUNNING NOW item 4, DATA_PRODUCT_TRIAGE.md). Ayush's 02:20 words are not in ANSWERS.md.
2. The master classified the kit change as MAJOR under Q86 (KIT_CLASSES.md d11f933); the upgrade session's note said the 4 Nov part has no MAJOR change (reports/KIT_CHANGE_487b4697.md). The master's reading covers 29 Oct plus 4 Nov.

QUESTION A: who may change system files (rules, knowledge, templates, tools) from now on?
1. (Recommended) The master proposes, the upgrade session releases: on Ayush's word the master writes the change as a proposal file in master_chat_work/<date>_system_change/ and never edits tracked files; this session puts it into the worktree, tests it, tags it, and Ayush runs the round. Cost: a change reaches use after a round (minutes), and one rule line plus a tool check go into mc2-v2.5.4.
2. The master edits directly on Ayush's word (as now); before each release this session copies ROOT's edits into the worktree. Cost: two writers, every round starts by syncing, and an edit can be lost or overwritten.
3. Only the upgrade session changes system files; the master does not even propose. Cost: slower, and Ayush must bring each change here himself.

QUESTION B: the 8 edits already made in ROOT.
1. (Recommended) Keep them: this session copies them into the worktree as they are (diff checked line by line against ROOT), runs the self tests and template_check, and releases them in mc2-v2.5.4 with 9718df83 and the master gaps; Ayush then restores the 8 files in ROOT to mc2-v2.5.3 (git checkout of those paths, after a backup) and runs the normal round, which brings the same text back as a tagged version. Cost: one longer round.
2. Review each change with Ayush first, then option 1 for the ones he keeps. Cost: more of his time.
3. Undo them in ROOT and redo through a release later. Cost: the master works on the old rules until then.
