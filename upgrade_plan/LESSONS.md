LESSONS OF THE UPGRADE SESSION (started 5 Nov 2026, ENTRY 111). One entry per mistake: what happened, the mistake, what changed so it does not repeat. Every session reads this after RESUME.md and adds an entry in the same turn a mistake is found (COMPACT_PROMPT.md asks for it too). Newest last.

1. Stale handoff files (5 Nov 01:30, found by Ayush's question, fixed in a0520a44).
   What happened: Ayush asked whether a new session would be the same as this one. The check showed NEXT.md still said "Install STAGE A on the Mac", AGENTS.md said the tags end at mc2-v2.5.2, the RESUME header was dated 4 Nov 20:59 with RUNNING NOW as one very long paragraph, LIVE NOW said "installing ROOT", and the TS-26 and JD-14 triage table existed only in chat.
   Mistake: after each step the session updated only RESUME RUNNING NOW, not the other files a new session reads, and it kept a waiting question's content only in chat. AGENTS.md HOW YOU WORK items 4 and 6 already asked for LIVE NOW and RESUME.
   Changed: AGENTS.md HOW YOU WORK item 6 names every file to refresh after a step (RESUME header and RUNNING NOW, NEXT.md, LIVE NOW, AGENTS.md when a fact in it changes) and says a waiting question with its options is saved in a file; long history moves to INSTALL_LOG.md.

2. Tag made before the release was closed (5 Nov 00:14 to 00:17, ENTRY 105, 106).
   What happened: mc2-v2.5.3 was tagged on c7fd06cd; minutes later Ayush added two more changes for the same release, so the tag had to move to 8ad18ec5, which AGENTS.md forbids; Ayush allowed it once after three checks.
   Mistake: tagging while Ayush could still add to the release.
   Changed: before a tag, ask Ayush "anything more for this release?" and tag only after his answer; untagged commits wait (9718df83 waits for mc2-v2.5.4 this way).

3. Commit message without a blank line after the title (5 Nov 00:14, c7fd06cd).
   Mistake: the message was passed with no empty second line, so git shows the whole message as the title.
   Changed: every commit message is title line, empty line, body; check with git log --oneline -1 after the commit.

4. A test graded what its prompt never asked (4 Nov 23:55 and 5 Nov 00:01, ENTRY 102, 103).
   What happened: two cold recovery tests missed the goal, the gate and the handoff table, the same way twice.
   Mistake: the pass points asked for things the part B prompt did not ask for; the session first offered to judge the master instead of the prompt.
   Changed: part B asks for them (mc2-v2.5.3); a test's pass points must match what its prompt asks.

5. A dropped rule lived in more places than were named (5 Nov 00:06, ENTRY 104, 105).
   What happened: ENTRY 98 named 2 places for the dropped noise rule; a grep found it in 5 more (_COMMON_RULES_v5 Always 13, P12 v5, the playbook, P11 and P16 carry-over).
   Changed: before saying a rule is removed, grep every template, knowledge file and tool for it and list each hit to Ayush.

6. Mac only test bugs reached the release (4 Nov 23:33, ENTRY 101).
   What happened: test_issue_mc2.py failed twice on the Mac (unresolved /var temp path; the real settings old_root exists on the Mac) and blocked two preflights, so two manual rounds were needed.
   Mistake: the tests used real settings paths and unresolved temp paths; they were never run on the Mac before the release.
   Changed: fixed in mc2-v2.5.3 (realpath, a missing old folder); every release runs all self tests in the worktree on the Mac before the tag.

7. A command given without checking it works in Ayush's setup (4 Nov night, G1 check).
   What happened: the session told Ayush to type "/dcp help"; in DCP 3.2.0 on this Mac /dcp is not offered (the DCP TUI panel is not loaded), so the text reached the master as chat.
   Mistake: the session read the plugin code but not whether the command is registered in Ayush's opencode.
   Changed: before giving Ayush a command for a tool, check it in his installed version and config; say "UNVERIFIED" when it cannot be checked.

8. The card showed old events as if they were live (4 Nov 23:55, ENTRY 103).
   What happened: both cold masters proposed work on hangar-check-replan (pushed) and sensor-network-lsq-correlated-adjustment (parked), because the card's NEWS lines showed old board events without the stage now.
   Changed: NEWS lines show "(now <stage>)" (mc2-v2.5.3).

9. A rule told to Ayush was never put where the master reads it (5 Nov 08:16, found by Ayush's question, reports/ROOT_EDITS.md).
   What happened: the session told Ayush that system changes happen only here and the new master only does task work. The ROOT master then edited RULES_IN_FORCE.md (02:28) and 7 knowledge and template files (08:13) on Ayush's word, so ROOT no longer matches mc2-v2.5.3 and the next round's git status step stops.
   Mistake: the rule lived only in chat and in upgrade_plan; the master's RULES_IN_FORCE ROLE (R1) still says it "writes and tunes prompts", and no tool checks it.
   Changed: before telling Ayush how the system behaves, check that the master's own rules or tools say so; if not, say "not enforced yet" and ask. The fix itself waits for Ayush (QUESTION A and B in reports/ROOT_EDITS.md).

10. Commit run in parallel with a file write that failed (5 Nov 08:40, b9c09a25).
   Mistake: the write of reports/HANDOFF_NEW_OLD.md failed (file not read first) while the commit ran beside it, so b9c09a25 says the file was updated when it was not; fixed in 10a70339.
   Changed: commit only after every edit of that step has returned success, never in the same parallel batch.
