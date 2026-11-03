WHERE TOKENS GO TODAY (W1-033, 3 Nov 2026). Estimates from file sizes at 4 characters per token, from board.json counts, and from the S7 session measurements. Read only.

Paths: MCT = master_chat_tasks, S7 = master_chat_work/20261030_upgrade2/S7_cli_workers, KB = 1,000 bytes, k = thousand tokens, M = million tokens.

PART 1. SESSIONS PER TASK (MCT/board.json, 445 rows, classified by step text and prompt name; W1-033 script)
1. All rows: fix 130, QC 88, blind 78, harden 56, research and other 63, build 28.
2. 19 task slugs have at least one build row. Their mean per task: build 1.5, harden 2.3, QC 1.9, fix 3.3, blind 3.3, research and other 1.3. About 13.6 sessions per built task.
3. The busiest tasks run 20 to 36 sessions: schema-migration-plan-repair 36 (10 QC, 11 fix), sentinel-policy-recompute 35 (14 fix), district-heat-flex-procurement 31, metered-usage-rating-pipeline 28, tariff-engine-audit-repair 28.
4. Caveat: the classification is by keywords; 123 rows point at prompt files not in this copy. Counts are within a few rows.

PART 2. WHAT EACH SESSION KIND MUST READ BEFORE IT WORKS (today)
Issued prompt sizes are medians of the issued files the board points to (W1-033 script; S7/FINDINGS.md:29 gives close values). Files told to read come from each template's "Read first, in full" list.
1. Build (P2 v5, template 31.1 KB, issued median 21.0 KB). Reads _COMMON_RULES_v5 19.7, LEVER_RULES_v3 62.7, LEAK_LIBRARY 4.5, QC_RULINGS 21.5, QC_FIX_PLAYBOOK_v3 22.7, KNOWLEDGE 16.3 (P2_build_v5.md:24 to :30). Total 168.4 KB, about 42k tokens. The same list also names checks.json (334 KB, about 83k tokens); whether sessions read it whole is UNVERIFIED, so it is left out of the totals.
2. Harden (P9 v4, template 16.3 KB, issued 13.1 KB). Reads _COMMON_RULES 19.7, round_notes 12.4 (four sections; whole file counted), LEVER_RULES 62.7, LEAK_LIBRARY 4.5, QC_RULINGS 21.5, PLAYBOOK 22.7 (P9_harden_from_results_v4.md:23 to :28). Total 156.6 KB, about 39k tokens, plus the task's WORK files.
3. QC (P11 v3, template 19.3 KB, issued 15.4 KB). Reads the live QC kit in full: Starter 9.5, Final_checklist 76.0, five gate files 151.1 (P11_full_qc_v3.md:37; sizes from the kit copy in upgrade_plan/tmp/W1-032/kit_test/kit_57c22748). Total 253.0 KB, about 63k tokens, plus the bundle. P11 v3 does not cite _COMMON_RULES, so FINDINGS F5.1 "every issued prompt carries _COMMON_RULES" is not exact for QC.
4. Fix (P12 v5, template 16.8 KB, issued 13.3 KB). Reads _COMMON_RULES 19.7, round_notes 12.4, LEVER_RULES 62.7, QC_RULINGS 21.5, PLAYBOOK 22.7 (P12_recheck_fix_v5.md:24). Total 152.3 KB, about 38k tokens, plus the QC report and bundle.
5. Blind (P13 v2, template 5.5 KB, issued 5.0 KB). Reads only the blind copy. About 1.3k tokens plus the task files.
6. Research and other (P14, P15, replays, scorers; issued 7 to 10 KB). About 2k tokens plus sources.

PART 3. FIRST READ TOKENS PER BUILT TASK, BEFORE
kind | sessions per task | first read per session | per task
build | 1.5 | 42k | 63k
harden | 2.3 | 39k | 90k
QC | 1.9 | 63k | 120k
fix | 3.3 | 38k | 126k
blind | 3.3 | 1.3k | 4k
research and other | 1.3 | 2k | 3k
total | 13.6 | | about 406k tokens

Why this matters more than it looks: text read early stays in the context and is read again from the prompt cache on every later model call. S7 measured per session medians of 27.4M cache read tokens for build, 18.7M harden, 11.0M QC, 10.1M fix, 1.3M blind (S7/FINDINGS.md:19 to :25). With the board counts that is about 142M cache read tokens and about 1.07M output tokens per built task, and about 106 USD of opencode recorded cost per task (W1-033 arithmetic; recorded cost is not a charge). How cache reads count against a Claude Max limit is UNVERIFIED.

PART 4. THE MASTER'S OWN READ, BEFORE AND AFTER THE P1 CARD
1. Before: the README read order after each compaction loads about 100 KB, about 25k to 30k tokens (upgrade_plan/FINDINGS.md:7). DCP on defaults compressed the master at least 258 times (upgrade_plan/ANSWERS.md:55, :58), and each compression is followed by part or all of that read order.
2. After: STATE_CARD 6.3 KB on a normal day, hard limit 8 KB (upgrade_plan/ANSWERS.md:336 to :346; drafts/P1/sample_STATE_CARD.md 7.5 KB), with the rules in force inside it. About 1.6k to 2k tokens, then only what the next step needs (drafts/P1/MASTER_RECOVERY.md part A).
3. Saving: about 23k to 28k tokens per recovery, and the same amount less on every later master call while that text would have stayed in context. With DCP manual, recoveries happen only when Ayush compresses. Recoveries per day: UNKNOWN.

PART 5. TOP SAVINGS THE NEW DESIGN ALREADY GIVES
1. BUILD_RULES instead of stacked rules. Build, harden and fix read BUILD_RULES 4.5 KB (the draft is 4.5 KB, not 3.8 KB) plus PATTERNS 12.8 KB where a design is needed, instead of LEVER_RULES 62.7 plus _COMMON_RULES 19.7 plus PLAYBOOK 22.7 plus KNOWLEDGE 16.3 (QC_RULINGS kept only as rows). After: build about 43 KB (11k tokens), harden about 37 KB (9k), fix about 24 KB (6k).
2. Fix map rows instead of the whole playbook. FIX_MAP has 71 rows, mean 0.46 KB (upgrade_plan/tmp/W1-030/FIX_MAP.md); a fix with 8 findings reads about 3.7 KB instead of PLAYBOOK 22.7 KB plus the whole 36.8 KB map.
3. Per task first reads after: build 1.5 x 11k = 16k, harden 2.3 x 9k = 21k, QC unchanged 120k, fix 3.3 x 6k = 20k, blind 4k, research 3k. Total about 184k, down from 406k: about 222k tokens saved per task (55 percent). Carried through later calls, at 50 to 150 model calls per session after the read (UNVERIFIED; S7 counted 21 to 563 tool parts per session, S7/FINDINGS.md:29), that is about 11M to 33M fewer cache read tokens per task, against about 142M today.
4. State card: about 23k to 28k tokens per master recovery (Part 4).
5. DCP off for task sessions. This is a correctness change, not a sure token cut. Pro: the measured cache writes are large (median 0.81M per QC session and 2.1M per build session, from S7/worker_measurements.csv), which fits DCP rewriting history and breaking the cache prefix; with DCP off the prefix stays stable (INFERRED). Con: nothing prunes old tool output, so the context grows. Net effect UNVERIFIED; measure with S7's measure_workers.py after one week.
6. Scripts that use no tokens. Regression check SCRIPT steps (byte diff, lever program rerun, vacuity probe; upgrade_plan/tmp/W1-030/REGRESSION_CHECK.md) replace the fix session doing them by hand, and stop bad fixes before a QC round: 60 percent of new QC findings came from our own edits (upgrade_plan/tmp/W1-003/ANSWERS_FROM_RECORDS.md:83). One QC plus one fix round avoided per task saves about 100k first read tokens and about 21M cache read tokens (INFERRED). kit_watch.py replaces a model reading the 238 KB kit (about 59k tokens) to find what changed; only changed lines go to a classifying prompt. template_check.py replaces reading about 126 KB of templates (about 31k tokens) per template audit. Both are per change, not per task.

PART 6. FURTHER SAVINGS, WITH RISK
1. Event wait instead of poll loops (dockslot, upgrade_plan/tmp/W1-031). 382 "sleep; docker ps" loops in 26 to 30 Oct (S7/FINDINGS.md:27); every poll is a model call that rereads the whole context. 50 polls in a 150k context session is about 7.5M cache read tokens (INFERRED). Risk: a wrong slot count delays or collides with a paid run.
2. Compact tool output. Scripts return short JSON plus the path to the full log, instead of whole gate logs; sampled sessions held 0.15 to 4.40 MB of tool JSON (S7/FINDINGS.md:29, :35). Risk: a summary hides a failure; keep raw logs and spot checks.
3. QC kit by section on rechecks. QC reads 238 KB of kit every round. A recheck could read only the gate files and checklist sections that the changed lines touch (P11 v3 already uses CHANGED_LINES). Saves up to about 40k tokens per recheck. Risk: high. R33 says prompts read the live files, and the kit says read in full; a missed check passes a defect. Needs Ayush.
4. Lower variant or a cheaper model for mechanical steps: intake summaries, blind scoring, replays, screening (Codex at reasoning low used 7,146 tokens for a file count, REQUEST.md:72). Workers run variant high today (MCT/auto/auto.py:64); build reasoning is 153k tokens per session. Risk: missed detail; only after a paired test on a frozen input (S7/FINDINGS.md:37). Depends on Q25.
5. Shorter issued prompts. A dispatch header with sha, paths and rule file hashes instead of restated rules; S7 estimates 3.2 KB less per QC prompt and 4.5 KB per build prompt (S7/FINDINGS.md:33). Risk: an omitted rule; check rule coverage.
