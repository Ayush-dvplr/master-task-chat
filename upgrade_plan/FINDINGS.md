FINDINGS FROM THE REPO (Claude, 3 Nov 2026)

Source: this repo at commit 10d3e3ff only. Every finding is a reading of the files, not a verified fact about how the system behaves on the Mac. Each one needs Ayush to confirm.

P1. COMPACTION

F1.1 The read order after compaction (master_chat_tasks/README.md lines 5 to 14) loads about 100 KB: README 9 KB, GOALS 7 KB, KNOWLEDGE 16 KB, route 1 notes 8 KB, all of feedback.jsonl 16 KB, lessons, the decisions tail, state.json 16 KB, pipeline_v4 PLAN and MASTER_UPGRADE_PLAN_v1. That is roughly 30k tokens before any work.
F1.2 The rules are layered patches. GOALS.md line 95 says "v3.8 overrides the Law 1 text below". README line 31 says "the WRONG only wording below is superseded". Route 1 notes R0 overrides R4, R5 and LEVER_RULES v3.4, v3.5, v3.7. The model must work out which layer wins every time.
F1.3 The same lesson ("after compaction run the README read order") was logged on 1 Nov 11:27 and again on 2 Nov 16:31 in lessons.jsonl. Writing a lesson down did not make it stick.
F1.4 decisions.jsonl is 278 KB. Too large to reread.
F1.5 state.json says "CONFIG + STANDING RULES ONLY" but still holds superseded values (see CONTRADICTIONS.md C3, C4).

P2. QC FIXES

F2.1 knowledge/QC_FIX_PLAYBOOK_v3.md line 3: a study (3b00450) found 67 of 255 later findings were caused by fixes, at least 22 directed by the fix prompt (mostly pasted QC "Fix:" text).
F2.2 Guard rules G1 to G7 (QC_FIX_PLAYBOOK_v3.md lines 64 to 70) are instructions to the model. Nothing mechanical checks, after a fix, that the lever still makes the careful program lose points.
F2.3 Route 1 notes R0 item 4 already asks for a saved input per lever that makes oracle and careful program differ. That saved input could be rerun automatically, but no tool does it today (UNVERIFIED: tools/precheck.sh not read line by line yet).

P3. DOCKER

F3.1 tools/dockfree.py assumes: 3072 MiB headroom, a container with no memory limit counts as 4096 MiB, CPU cap 12 against 8 vCPUs. Docker VM is 16 GiB per AUTO_POLICY.md ("Docker has 16 GiB now").
F3.2 dockfree counts memory LIMITS, not memory actually used. Two tasks with memory_mb 4096 to 6144 can already give START=no while really using much less.
F3.3 Each worker polls dockfree in its own loop. There is no queue or slot handout, so workers wait and retry independently (this also costs tokens).
F3.4 Three different Docker rules exist in the records (see CONTRADICTIONS.md C1).
F3.5 auto/auto.py lines 65 to 87: MAX_BUSY_WORKERS 5, MAX_BUILDS 2, MAX_HARNESS 2, POLL_S 60, MAX_BUSY_AT_LAUNCH 2 (a paid run starts only with 2 or fewer busy workers), MAX_BUSY_WITH_RUN 3. These limits can hold sessions even when Docker has room.
F3.6 Paid runs go through scripts/master_queue.py in the harness repo. Not seen.

P4. HARDENING

F4.1 Route 1 notes R0 (2 Nov): misread rule levers lose to careful Opus 5 (depot a1 and a2, hangar a1, flood a4 scored tests 100). Primary lever must be (a) carrier or encoding variation, (b) a documented branch fired only by hidden data at scale, or (c) measured scale. At least 40% of positive test weight.
F4.2 The lever rules live in several files at several versions (LEVER_RULES_v3.md 63 KB, route 1 notes, GOALS G11, README line 31).

P5. TOKENS

F5.1 Every issued prompt carries _COMMON_RULES_v5 (20 KB) plus a template: P2 build 31 KB, P11 QC 19 KB, P12 fix 17 KB, P9 harden 16 KB.
F5.2 Sessions are told to read KNOWLEDGE.md 16 KB, LEVER_RULES_v3.md 63 KB, QC_FIX_PLAYBOOK_v3.md 23 KB and more.
F5.3 prompts/issued holds 7.1 MB of issued prompts.
F5.4 Polling (F3.3) and compaction rereads (F1.1) add more.

P6. MULTIPLE TOOLS

F6.1 auto/auto.py drives only opencode: reads opencode.db (line 58), starts "opencode serve" (line 764), sets OPENCODE_PERMISSION (line 456).
F6.2 Codex and other tools are invisible to auto mode. Only the board and result.json tie them together.
F6.3 feedback 31 Oct 16:12: GPT prompts for opencode must say "strictly do not run subagents".
F6.4 auto/plans/20261029_smoketest_kiro.md exists, so Kiro was tried at least once.

OTHER

F7.1 master_chat_tasks/auto/__pycache__/auto.cpython-314.pyc is tracked in git.
