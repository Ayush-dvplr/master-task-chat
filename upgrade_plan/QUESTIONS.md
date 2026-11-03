QUESTIONS FOR AYUSH

Answer in chat with the id (for example "Q9: 64 GB"). Claude records answers in ANSWERS.md and changes the status here.

LIVE NOW: none. Layer F running (W1-025); P1 drafts in progress.
FROM RECORDS, WAITING FOR AYUSH TO CONFIRM (Q65a to Q65e): Q1, Q7, Q10, Q11, Q12, Q16, Q17, Q18, Q22, Q30 to Q33, and which episode for Q35. Answers in tmp/W1-003/ANSWERS_FROM_RECORDS.md.
PARKED until their problem is planned (Q4 is taken up before the UNVERIFIED_RULES review): Q2, Q4, Q8, Q9, Q13, Q19, Q21, Q23 to Q29.
LATER (Ayush): Q37.

PROCESS
Q0. You wrote "Do not edit when you are 100% sure". I read it as "do not edit UNTIL we are both 100% sure". Is that right? [ANSWERED: yes]
Q1. Is this repo a full copy of your Mac folders master_chat_tasks and master_chat_work, or a snapshot that may be older than the Mac? [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q2. After PROCEED, where do changes go: committed in this repo on the branch for you to copy to the Mac, or written as files for you to place by hand? [PARKED until its problem is planned]
Q3. Which of the six problems hurts most right now, so the plan starts there? [ANSWERED: compaction first, plus new problems P7 to P10; order confirmed in Q34]
Q4. Should the UNVERIFIED_RULES.md batches come one batch at a time in chat, or will you read the file and answer by rule id? [PARKED until its problem is planned]

P1 COMPACTION
Q5. Does the master chat run in the opencode TUI (auto.py mentions "oc master")? Which model and provider? [ANSWERED: opencode TUI session "Master Task Chat", Opus 5.5 (Q40, Q50, Q56)]
Q6. Is opencode auto compaction on? Do you also compact by hand? About how many compactions per day? (RQ4 may answer this.) [ANSWERED: native auto compaction OFF; DCP compresses on its own (Q41, Q44, Q49)]
Q7. After a compaction, what exactly did the master get wrong? Old lever rules, your feedback (links, tables), running sessions, something else? One or two real examples. [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q8. May superseded files (LEVER_RULES v1 and v2, snapshots, old template versions) move to a history folder the master never reads? [PARKED until its problem is planned]
Q9. Would you accept the master reading one small generated state card (under about 4 KB) after compaction, instead of the 7 step read order? [PARKED until its problem is planned]

P2 QC FIXES
Q10. Are the careful program and the blind programs saved for every task in a fixed place? Where? [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q11. When a fix lost a lever, how did you find out: next blind read, paid run, or reading the diff? [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q12. The new errors after fixes: mostly new QC findings at recheck, or broken oracle or nop runs, or both? [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q13. Is the QC kit owned by someone else (you can only change your bundle), or can its rules change? [PARKED until its problem is planned]

P3 DOCKER
Q14. How much RAM does your M1 Max have, 32 GB or 64 GB? (RQ3 may answer this.) [ANSWERED by RQ3: 32 GiB, 10 cores]
Q15. Docker Desktop, OrbStack or Colima? Memory and CPUs given to its VM now? [ANSWERED by RQ3: Docker Desktop 29.8.2, VM about 15.6 GiB, 8 CPUs]
Q16. When sessions wait, what do they print: dockfree START=no, the harness queue, or the auto.py busy worker limit? [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q17. Which Docker rule is in force: one at a time, max 2 heavy, or dockfree only? (CONTRADICTIONS C1, C6) [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q18. The 27 Oct Mac hang: do you know the cause (memory, disk, too many containers)? [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q19. How many Docker jobs at the same time do you believe the Mac can run, and of what kind (kill tests, oracle or nop, paid harness runs)? [PARKED until its problem is planned]

P4 HARDENING
Q20. "Hardening as per the proven": do you mean (a) a repeatable recipe applying the R0 lever kinds to a task, (b) a library of proven levers with implementation patterns, or (c) something else? [ANSWERED: no method yet; that is the problem itself. Hardening must hide levers, not leak tests or rubric, pass QC, keep the hard parts, keep oracle 1 and nop 0, and more. FOLLOW UP Q61. Note: until 3 Nov 02:15 this line wrongly carried the Q38 answer; fixed after W1-001]
Q21. Which tasks should be hardened first? [PARKED until its problem is planned]
Q22. What goes wrong today when you harden: the lever does not bite, QC flags it, or too many rounds? [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]

P5 TOKENS
Q23. Which plans do you pay for (Claude Max, Anthropic API, ChatGPT Pro or Plus, OpenAI API, others)? Is the pain usage limits or money? [PARKED until its problem is planned]
Q24. Which step feels most expensive: build, QC, fix, blind reads, or the master chat itself? [PARKED until its problem is planned]
Q25. Are cheaper models fine for mechanical steps (tallies, diffs, intake), or must every session use the strongest model? [PARKED until its problem is planned]

P6 TOOLS
Q26. Every tool and model you use now, including the others (Gemini CLI, Kiro, Cursor, anything). [PARKED until its problem is planned]
Q27. Which tool for which step, and why (cost, quality, limits)? [PARKED until its problem is planned]
Q28. Should auto mode start and watch Codex and the others by itself, or is it enough that they report back in one shared format when you start them by hand? [PARKED until its problem is planned]
Q29. Known limits per tool in practice (for example Codex cannot reach Docker, GPT skips parts of long prompts)? [PARKED until its problem is planned]

RECORD CONTRADICTIONS (see CONTRADICTIONS.md)
Q30. Count cap: is there any cap on tests and judge criteria, a warn above 35, or no cap at all? (C2) [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q31. Which P12 fix template is active, v4 or v5? (C3) [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q32. Is the gate tests under 85, rubric under 85, final under 40, and the older 100, 100, 70 dead? (C4) [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]
Q33. Push needs 1 harness run, or 8 runs on final approval? (C5) [FROM RECORDS (tmp/W1-003/ANSWERS_FROM_RECORDS.md), waiting for Ayush to confirm via Q65a to Q65d]

NEW PROBLEMS P7 TO P10 (from the Q3 answer, 3 Nov)
Q34. Is your Q3 list in priority order, so compaction (P1) comes first, then the others in the order you wrote them? [ANSWERED: yes]
Q35. P7: when you "upgrade the master chat session", what kind of upgrade do you mean (new template versions, new rules, new tools, a new plan like v3.7 or v3.8)? What became worse afterwards? One real example. [ANSWERED: an upgrade led to 2 days of tasks scoring tests 100; details are in the records, read later]
Q36. P8: do your teammates use the same QC kit and the same generator as you? Do they build by hand, with their own chat, or with a system like yours? [ANSWERED: same QC; generator differs, it only gives structure and a plan, Ayush sometimes finds it useless; some friends use direct prompts with everything in them]
Q37. P8: can you share one or two teammate tasks that passed QC and scored well, with their scores? I saw master_chat_work/20261102_test_design_study (10 teammate tasks). Are those the right examples, or are there better ones? [LATER, Ayush will answer]
Q38. P9: "very bad at creating new tasks with respect to the fixing tasks". Which do you mean: (a) new tasks built from scratch come out worse than tasks that get fixed, (b) the system is good at fixing but bad at designing new tasks, or (c) something else? [ANSWERED: (b)]
Q39. P10: which templates were still old after an upgrade? Name one case (which upgrade, which template, which session used the old one). I already found one: state.json and README line 31 still say P12 v4 while INDEX says v5 is active (CONTRADICTIONS C3). [ANSWERED FROM RECORDS: 5 cases in tmp/W1-003/ANSWERS_FROM_RECORDS.md]

FROM THE RQ3 AND RQ4 OUTPUT (3 Nov)
Q40. Which opencode agent does the master chat use: the plain opencode agent, or Sisyphus from the oh-my-openagent plugin (the settings report was written by "Sisyphus, Ultraworker")? Which model does the master use, and is it the same for workers? [ANSWERED: Sisyphus; master always Opus 5.5; workers sometimes Codex, opencode Opus 5.5, or GPT 6.1 Sol. FLAG Q48, Q50]
Q41. The DCP plugin (Dynamic Context Pruning) is on with default settings. It removes or shortens older tool outputs from the context by itself, even with auto compaction off. Did you install it on purpose, and when? Did the "loses all its learning" problem start around the same time? [ANSWERED: Ayush guesses DCP is the problem, and also says the master needs to compress wisely]
Q42. Why is oh-my-openagent installed? Do workers run under Sisyphus too? It adds its own large system prompt and pushes subagents and background tasks, which may clash with your "no subagents" rule and raise token use. [ANSWERED: it works better non stop; workers use it too, without human interaction (Ayush: "i guess so"). FLAG Q48]
Q43. The report came from "GPT 6.1 Sol", which is not in the config file. Which provider gives you GPT in opencode (ChatGPT login, OpenAI API, something else)? [ANSWERED: ChatGPT login in opencode]
Q44. How do you compact by hand: the /compact command, or starting a new session? How often per day for the master chat? [ANSWERED: the plan was by hand, but now it mostly compacts at around 30 to 40% and drops to 7 to 10%, losing important context. FLAG Q49]
Q45. When the Mac hung on 27 Oct, how many opencode sessions and Docker containers were running? Do you have any memory numbers (Activity Monitor) from a busy time? [ANSWERED: no exact numbers, about 3 times the limit set in the files]
Q46. Would you allow, later and only as a measured test, raising the Docker Desktop memory above 15.6 GiB? The Mac has 32 GiB, but opencode sessions and the browser also need RAM, so the right number has to be measured, not guessed. [ANSWERED: 15.6 GiB is probably enough, since not every task uses the memory its task.toml asks for. FLAG Q51]
Q47. Your pasted config lost some square brackets (the "plugin" list). Is that only from copying, and is the real file valid? [ANSWERED: file is valid; brackets were lost only in copying]

FLAGS AND CROSS QUESTIONS ON THE 3 NOV ANSWERS (rule R_FLAG)
Q48. Q40 and Q42 do not fit together fully. Codex workers do not run under Sisyphus, so "workers use the same" is true only for opencode workers. Also Sisyphus pushes subagents, while your 31 Oct rule says GPT prompts must "strictly do not run subagents". Which wins for workers: Sisyphus non stop with subagents, or no subagents? [ANSWERED: master = one saved opencode session, Opus 5.5. Worker prompts go by hand into opencode GPT Sol 6.1, opencode Opus 5.5, or Codex. FOLLOW UP Q56]
Q49. Q44 versus the config: native auto compaction is OFF, yet you see compaction at 30 to 40%. So something else is shrinking the context: most likely DCP, or a feature of the Sisyphus plugin. Next time it happens, can you copy the exact message or screen text you see? [ANSWERED with screen text: "DCP | -8168.3K removed, +311.2K summary" and "Compression #258 -17.8K removed, +957 summary, 16 messages and 13 tools". See FINDINGS F1.8]
Q50. The config default model is claude-opus-5, but you say the master always uses Opus 5.5. Do you pick Opus 5.5 by hand in each session (or with a flag)? [ANSWERED: the model is set once per session and stays when the session is resumed]
Q51. Q46 fits what I found: if 15.6 GiB is enough in practice, the waiting comes mostly from dockfree counting task.toml LIMITS (and 4 GiB for any container without a limit), not real use. But Q45 says you once ran about 3 times the limit and the Mac hung. So "enough" holds for real use, but not if everything starts at once. Do you agree with this reading? [ANSWERED: Ayush wants dynamic values, a background script with no AI tokens that the AI can see and start or stop]

RECOVERY PROMPT (part 2)
Q52. When will you use the recovery prompt: after I compact in this same session, in a brand new session, or both? [ANSWERED: paste it in this same session after compaction]
Q53. Should I update RESUME.md and push after every exchange (always current, one small commit each time), or only at milestones? [ANSWERED: update after every exchange where something changes, skip pure chat]
Q54. May I verify the recovery prompt with a cold test: start one fresh helper agent that gets only the prompt, then check that it reports the state correctly? It costs some tokens. [ANSWERED: yes; worker W1-001]
Q55. Should the recovery also reload part of the master_chat_tasks records, or only this upgrade_plan folder for now? [ANSWERED: yes; a "known from records" section of about 1 KB max, each fact with its source file; details in FINDINGS.md]

Q56. You said you "saved and renamed it in Open Code Sisyphus". Sisyphus is also the name of the main agent of the oh my openagent plugin, and the settings report (a fresh session) ran as "Sisyphus, Ultraworker". So: (1) is "Sisyphus" a name you gave the master session, or the plugin agent, or both? (2) When you paste a worker prompt into a new opencode session, does that session also run as the Sisyphus agent by default? [ANSWERED: the master session is named "Master Task Chat"; Sisyphus is the default agent shown at the bottom of every opencode reply. FOLLOW UP Q57]

Q57. Following Q56: Sisyphus is the default agent, so every opencode session runs as Sisyphus, including worker sessions you paste prompts into. The second half of Q48 is still open: Sisyphus pushes subagents and background tasks, while your 31 Oct rule says GPT prompts must "strictly do not run subagents". For opencode workers, which should win? [ANSWERED: subagents are fine in principle; the rule is for cost and because subagents default to Claude and fail in a GPT session once the Claude limit is used up]
Q58. Worker sessions (WORKERS.md): are you fine with Claude using both W1 helpers inside this session and W2 separate cloud sessions? Any limit you want, for example at most 2 workers at a time? [ANSWERED: both fine, no limit on number or tokens; Ayush wants the end result. FLAG Q62]
Q59. Should workers only return their report (Claude stores it), as WORKERS.md proposes, or may they write their report file into upgrade_plan/reports/ and push it themselves? [ANSWERED: report only; full findings may go in a separate tmp folder, each file mapped by a sha like id]
Q60. For W3 prompts (things only the Mac can see), which tool should you paste them into by default: opencode Opus 5.5, opencode GPT Sol 6.1, or Codex? [ANSWERED: opencode GPT Sol 6.1 for now]

Q61. P4 hardening: you said there are "plenty of things" to follow (hide levers, no leak of tests or rubric, pass QC, oracle 1 and nop 0, and more). Proposal: a helper collects every hardening constraint from your records (route 1 notes, LEVER_RULES, QC playbook, lessons, feedback) into one numbered list, with the source of each. Then you go through it and mark each KEEP, CHANGE or DROP, like UNVERIFIED_RULES. That list becomes the base of a hardening method. Is that the right first step, and may that helper read the records now (this would lift R_RECORDS for this one job)? [ANSWERED: yes; also read the master chat records, and list what is missing from the repo (for example the QC folder) so Ayush can push it]
Q62. FLAG on Q58 versus P5 and Q57: you said subagents cost a lot of tokens, and P5 is "token use is very high", yet for my helpers there is no token limit. Do my helpers in this Claude session draw on the same Claude account and usage limit as your opencode Opus 5.5 task sessions? If yes, heavy helper use here can exhaust the limit your task work needs. Is that acceptable, or should helpers run at quiet times only? (W1-001 used about 79k tokens.) [ANSWERED: no limit during this build; the finished system must be light on tokens in daily use (DR1)]

AFTER HELPERS W1-002 AND W1-003 (3 Nov)
Q63. Secrets: all 24 tracked wrapper.log files under master_chat_work (gate_run and traj folders) contain an OPENAI_API_KEY value. Is this repo private? Is that value a real OpenAI key or a local bridge token? Do you want it rotated, and masked in the repo after PROCEED? [DROPPED: Ayush said ignore]
Q64. May I give you the push list from tmp/W1-003/MISSING.md (MUST items: QC/reports, the live QC kit Input_Bundle_QC, harness master_queue.py and .master-queue/state.json, blind program folders under _runs, opencode config without keys, the newest records and the 3 sessions running at copy time)? Never push: ~/.codex/auth.json, ~/.tb-master-key, ~/.ssh, oc-bridge secrets, ~/.local/share/opencode. [ANSWERED: items 1 to 7 pushed to main 3 Nov; item 8 not needed; item 6 missing, Q76]
Q65. Please confirm or correct the answers the records gave (short list in chat 3 Nov). In particular Q35: episode A (24 to 25 Oct, plan v1 plus habit levers, contract sentences stated the whole graded procedure) or episode B (31 Oct to 2 Nov, min plan v2 and route 1, misread rule levers lost to careful Opus)? [SPLIT into Q65a to Q65e]

GOAL AND NEW RULES (ENTRY 11, 3 Nov)
Q66. FLAG: you wrote tests and rubric must not be above 80. The records (gate v3.7, state.json line 126) say tests under 85, rubric under 85, final under 40. Which is current: 80 or 85? [ANSWERED: 85 now (v3.7), but make the gate dynamic (DR2)]
Q67. FLAG: "my goal is not to make 100% genuine task". Your own records say difficulty must come from computation on hidden data, never from withheld rules (GOALS G11), and every graded fact needs a determinate source (route 1 R2). Which of those still hold? Concretely, what do you want to allow that a "genuine" task would not have? Claude's boundary is in README GOAL item 7. [ANSWERED: many tasks needed; PL and QL say passing QC is fine; every task must be solvable (DR3). FOLLOW UP Q72]
Q68. FLAG: GOALS G9 says uniqueness is checked only against your own registry ("No check against Anubis/Finalized needed"). Now a task must also differ from teammates' tasks. Where can the system see teammates' tasks to compare (Anubis_Tasks_Samples, Finalized_Tasks_RFP, something else)? Who flags a copy, and what counts as "the same task"? [ANSWERED: against his own tasks; each build new; never a close copy of one teammate task]
Q69. QC kit upstream: which repo does the PL push the kit to? The newest snapshot here is knowledge/fingerprints/qc.json, made 25 Oct at kit head 5574d77e, with 6 older archives. Has the kit changed since 25 Oct? How do you tell a major from a minor change today? [ANSWERED: PL repo "terminal bench 2.0"; minor and major defined in README 8b; agents decide; Ayush can paste the kit]
Q70. QL queue: is QL_QUESTIONS.md the right place, and do you forward the questions to the QL by hand? Any format the QL prefers? [ANSWERED: yes, Ayush forwards by hand]
Q71. AYUSH_SUGGESTIONS.md now holds S1 to S5 from this chat. Are there older suggestions in the records (for example in feedback.jsonl) that should be added too? [ANSWERED: no, only suggestions from this upgrade]

Q65a. Q7 (what goes wrong after compaction): the records say the master forgets HOW to work (links, tables, session status, caps), not the task facts. True? [ANSWERED: yes]
Q65b. Q18 (27 Oct hang): the records say the cause was 3 Python solver programs left running on the Mac itself, outside Docker, using about 185 GB. True? [ANSWERED: yes; also other apps, wrong Docker settings and VMware were running (happened once)]
Q65c. Q11 and Q12 (QC fixes): the records say a lost lever was usually noticed only at the next paid run, and the "new errors" were new QC findings, not broken oracle or nop. True? [ANSWERED: yes]
Q65d. Q30 to Q33: no limit on the number of tests (over 35 only gives a warning that is accepted; QL1 asks the QL), fix template P12 v5 is the active one, and one harness run on frozen bytes is enough to push. True? [ANSWERED: yes, but count caps exist: soft 70, hard 100, tests and rubric, minimum per QC. FOLLOW UP Q75]
Q65e. Q35 (2 days of tests 100 after an upgrade): episode A, 24 to 25 Oct, or episode B, 31 Oct to 2 Nov? [ANSWERED: B, 31 Oct and 1 Nov]
Q72. Q67 follow up: "solvable" in your words is "with enough time and everything shipped, an agent can solve it". Does that also mean every graded value has one correct answer that the shipped instruction and data decide (no value that only the hidden tests decide)? [ANSWERED: defined by the solvability prompt in README (ENTRY 13)]
Q73. You asked to change the README goal heading. It is now "GOAL OF THE TASK SYSTEM". Is that what you wanted, or a different wording? [ANSWERED: keep "GOAL OF THE TASK SYSTEM"]

Q74. Please confirm or change Claude's boundary (README GOAL item 7). Your words in ENTRY 11 ("bypassing the QC", "not possible to follow the legit process") and ENTRY 12 ("if it is passing the QC, it is fine", "task must be solvable") are recorded. Claude's reading: every lever must keep the task solvable from what it ships and must pass QC as the kit is written; Claude will not design something whose purpose is to hide an unsolvable or underspecified grading from QC, the PL or the QL. Do you agree with this as the working rule? [ANSWERED: solvability is a QC check (DS-21, F0e, CL-10); extra solvability prompt only if the QL asks; Ayush did not object to the boundary, so it stands as the working rule unless he reopens it]
Q64 note (saved explanation): the "push list" is the list of folders Ayush copies INTO THIS repo so Claude can read them (tmp/W1-003/MISSING.md, MUST items). It does not contradict R_REPOS: Claude never pushes anywhere except this repo; Ayush adds material here himself. It matches RQ1 and RQ2 in REQUESTS.md and Ayush's Q69 offer to paste the QC kit.

Q75. Count caps (Q65d): you set a personal soft cap of 70 and a hard cap of 100 for the number of tests and of rubric criteria, plus the QC minimum. Earlier feedback (24 Oct 12:52) said "there is not cap". (1) Is the hard cap of 100 your own rule, or from the PL, QL or harness? (2) Is a count between 70 and 100 fine whenever it helps the score? These will be settings like the gate (DR2). [ANSWERED: hard cap 100 is Ayush\'s own rule]

Q76. Item 6 of the push list is not in main: the newest master_chat_tasks records (the copy still stops at 3 Nov 00:45) and the outputs of the 3 sessions running then (hangar fix_qcv4, flood fix_qcv4, sensor QC v3). Did you mean to push them, or are they not needed? [ANSWERED: not needed]
Q77. QC kit check: compared with your 25 Oct snapshot (knowledge/fingerprints/qc.json), 2 of the 12 kit files changed: 05_Alignment_Integrity_QC.md and Final_checklist.md. The other 10 are the same. May a helper read the change and classify it MINOR or MAJOR by your definition (README 8b)? That is also a first real test of the R_QC_UPSTREAM idea. [ANSWERED: yes; helper W1-005]

Q78. S6: which folder is the "root" on the Mac: "/Users/mac/Desktop/Terminal Bench"? Should every session (master and task sessions, Claude and GPT) start from that root, or only the master? Note: opencode reads the global config AND the project config and merges them, so "only the root config" may need an extra step (to be checked with a W3 prompt before we rely on it). [ANSWERED: root "Terminal Bench" for all sessions today; a new root folder is planned (Q84)]
Q79. S7: "act on it, first let me know only": on a kit change, should the system ONLY report it to you and wait for your word, or report and also prepare (not apply) the update plan for MINOR changes? And which git link should it watch: the PL repo "terminal bench 2.0" remote, or your local clone? [ANSWERED: only report; Ayush decides later in a session]
Q80. S8, FLAG: your GOALS.md G8 already asks for dynamic ChatGPT idea prompts rewritten after every batch with the lever bank, and templates P1 (ChatGPT ideas, v1 to v3) and P15 (research angle) plus knowledge/ANGLES.md exist. Why did that not work in practice: were the prompts not updated, too long, lost after compaction, or something else? [ANSWERED: teammate tasks are the main knowledge source; research must center on them (Q85)]
Q81. S8: where do the ChatGPT and Gemini results go today, and how do they get back into the knowledge base (pasted into a session, saved as files, not saved)? [ANSWERED: the master writes a prompt and an empty md file; Ayush pastes the response there]
Q82. Still open from before: shall the conflict review (5 most serious hardening conflicts) start now, or after the W1-005 kit result? [ANSWERED: yes, review started in CONFLICT_REVIEW.md]

Q83. Kit change (W1-005): verdict MAJOR because of one change only (C6, one finding gets one check id). Do you agree with MAJOR, or do you count it MINOR because no bundle needs rework? [ANSWERED: MINOR; a name for lenient changes wanted (Q86)]

Q84. New root folder: what should it hold (master_chat_tasks, master_chat_work, bundles, QC, _runs, the harness clone, the generator)? Should THIS git repo become that root? Where would the large folders (_runs has about 62 thousand files) live? [ANSWERED: one git root holding master_chat_tasks, master_chat_work, QC and anything else needed]
Q85. Teammate tasks: where are they (Anubis_Tasks_Samples, Finalized_Tasks_RFP, a shared drive, the PL repo)? Can a helper read them (they are your teammates' work; are you allowed to study them)? This decides how S8 research prompts are built. [ANSWERED: teammate tasks pushed to main as anubis-stage-2/ (ENTRY 19)]

Q86. Kit change classes: proposal LENIENT (a change that only makes QC easier for us; act on it freely), MINOR (a stricter or reworded rule that does not touch fix mapping or hiding), MAJOR (touches fix mapping, hiding or traps). Under this, W1-005's 8 changes are LENIENT and C6 is MAJOR or MINOR as you decide (you said MINOR). Is that what you meant by "better name it"? [ANSWERED: LENIENT, MINOR, MAJOR agreed]

Q87. Priority (ENTRY 19): the core goal is fixing, rebuilding and hardening tasks and making new hard ones. Earlier (Q34) the order was compaction first. Should the plan now put first what directly improves task making (teammate study, hardening method P4, new task design P9, QC fixes P2), with the system fixes (P1 compaction, P3 Docker, P5 tokens, P6 tools) after or in parallel? [ANSWERED: task making first, system fixes in parallel]
Q88. STAGE2_STUDY_PLAN.md: approve the phases? Phase 0 is a script only (no AI tokens) and can run first; Phase 2 is the expensive part. [ANSWERED: approved; Phase 0 done]
Q89. Do you know which one or two teammate tasks failed QC, so they are kept out of the patterns? If not, the study marks QC risk per task instead. [ANSWERED: QC is an AI reviewer, every run finds something; these tasks have the fewest findings; open to discuss (P12, Q92)]

Q90. FLAG on the count cap (Q75, your own hard cap 100): teammate tasks have a median of about 186 test checks (54 to 1798), estimated from the test weights in reward.toml. If that estimate is right, your cap of 100 is far below what passing teammate tasks use. Keep 100, or treat it as a setting to revisit after the cards? [ANSWERED: Ayush asked for the author table (tmp/S2-INDEX/AUTHORS.md); decision on the cap later]
Q91. Phase 1 pick: 26 under gate tasks not yet carded plus 5 high scoring contrast tasks (31 cards, about 2 to 3 million tokens). Approve, or change the list (for example only the lowest 15)? [ANSWERED: study all tasks smartly, skip Ayush's own; plan v2 (Q93)]
Q92. P12 (QC is noisy): shall we set a working definition now, for example "QC passed = no fail findings in 2 runs in a row, minors allowed if they repeat no evidence", or discuss it after the cards show what teammate tasks still carry? [ANSWERED: both; working definition now, refined after cards; CL findings are major (Q95)]

Q93. Approve STAGE2_STUDY_PLAN.md plan v2 (layers A to G, starting with the free script layers A and B and a 3 card pilot)? [ANSWERED: Layer A and B approved]
Q94. Gate categories: tasks fill quotas in easy, medium and hard, and the gate falls over time (70, 50, then 35). Does each category have its own gate today, and which category are your new tasks meant for? The system needs this to know which gate a task must meet. [ANSWERED: no separate gate per category]
Q95. Working QC definition (draft): "QC passed = no fail finding in 2 QC runs in a row; any CL fail blocks; a minor is accepted if it does not come back with the same evidence in the second run". Agree, or change? [ANSWERED: agreed, plus a false positive review step after each QC result]

Q96. Layer C pilot: 3 light cards (one low, one middle, one high Opus tests score, chosen by Claude from FEATURES.csv), about 100k tokens, run as background helpers; Ayush reviews the cards before scaling. Go? [ANSWERED: yes (ENTRY 25); pilot done]

Q97. P1: in opencode, what context size does the master's model show (the percent meter: percent of what total)? This tells how early 100k is. [ANSWERED: yes, percent of 1 million tokens]
Q98. P1 Step 1: which DCP option for the master chat: A tune, B manual (compress only when you say), or C off? Claude recommends B for the master and A for task sessions. [ANSWERED: B for the master; A or C for task sessions]

Q99. Task sessions: DCP off (C), or a light A (compress only near the end of the 1 million window, your messages protected)? Claude suggests C, since one session does one job; we can switch to A if a task session ever runs out of room. [ANSWERED: C, DCP off for task sessions]

Q100. Scaling the cards: light cards (about 40k tokens, no reproduction, first field DEFECT or DESIGN) for all tasks, deep cards only where the loss looks like DESIGN? Or a different depth? [ANSWERED: yes]

GOAL DISCUSSION (ENTRY 29)
G1. Draft goal in one line: "Make more and more accepted tasks the way teammates make them: each passes QC, scores under the gate, is solvable from what it ships, and is new (not a copy). Traps and levers are one tool for that, next to volume, speed, design shapes and test structure." Agree, or change the words? [ANSWERED: yes]
G2. The cards so far mark some teammate tasks DEFECT, for example a rule that only the hidden data carries and that TRUTH.md itself calls undocumented, or a reference that contradicts the docs. These were accepted, and you want to make tasks like teammates. Your own hard requirement DR3 says a task must be solvable from what it ships. When "like teammates" and DR3 conflict, which wins, or do we decide each case together? [ANSWERED: case by case]
G3. Besides traps, what else from teammates should the system learn and copy in approach: design shapes (for example the seeded generator plus full core gate), test structure, rubric style, task size, pace? [ANSWERED: all of them]

Q101. B08, B09 and B10 were already running when you paused. Stop them now (cards written so far are kept), or let them finish? [ANSWERED: keep them running]
Q102. Tighter plan for the rest (B10 to B24, about 56 tasks): which option? (a) stop the cards here and go to patterns with the 34 to 46 cards we have plus the 10 from 2 Nov; (b) a free script pass first that flags likely DEFECT tasks (graded key names or ids not found in the docs), then cards only for the rest; (c) a much smaller card (about 15k tokens, verdict and kind only) for the rest; (d) a sample, for example 10 more tasks chosen to cover categories not yet seen. [ANSWERED: b then d; b result in tmp/S2-TRIAGE/RESULT.md]

Q103. Start sample S1 (10 tasks in STAGE2_STUDY_PLAN.md, about 450k tokens), now or when your credits are back? [ANSWERED: run now, plus a few more chosen by Claude; S01 to S04]

Q104. Amended field type (cards 058cbab3, 88ee425d, af780bef): the data says a field is a whole number, then an amendment rewrites it as text, for example "1200" in quotes. The docs never say whether that amended value still counts as a number or is now invalid. The teammate reference treats it as invalid; Opus treated it as a number, and lost many points. For your own tasks: allowed only if one sentence in the docs decides it, or never use it? [ANSWERED: only with one doc sentence that decides it]
Q105. Rubric asking for unrequested things (pilot 7e0d8feb, af780bef): some rubric criteria give points only if the agent shows one named example or prints a trace, but the instruction never asks for that. Opus lost many rubric points this way. For your own tasks: copy this style, or keep every rubric criterion tied to something the instruction asks for? [FOLLOW UP: Claude suggestion in Q106]

Q106. Claude suggestion for Q105: every rubric criterion traces to a sentence in the instruction (or to the general honesty criterion). Where a worked example or a trace is wanted, add ONE plain sentence to the instruction asking the final reply to include it; the criterion is then fair, passes the QC alignment checks, and still costs Opus points when it skips it. Agree? [ANSWERED: agree]

Q107. Next step for the study: (a) Layer F, one helper reads only the 68 cards and writes the patterns and the confirm list (about 250k tokens); (b) first go through SUMMARY.md together and decide the DEFECT and D7 families case by case, then Layer F; (c) stop the study here and move to the plan with SUMMARY.md. Claude suggests (b). [ANSWERED: (b); paused, see chat 3 Nov]

Note: these ids replace the unnumbered list Claude gave in chat on 2 Nov. Same questions, new numbers.
