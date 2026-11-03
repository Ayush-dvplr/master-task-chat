PREFILL FOR Q23 TO Q29 (W1-033, 3 Nov 2026). Read only helper. Ayush confirms later.

Paths: MCT = master_chat_tasks, MCW = master_chat_work, UP = upgrade_plan, S7 = MCW/20261030_upgrade2/S7_cli_workers, REQ = MCW/20261030_upgrade2/REQUEST.md, LH = MCT/auto/runs/20261031T2154_leverhunt/REPORT.md.
Marks: FROM RECORDS = the records say it; PARTLY = some of it is in the records, the rest is UNKNOWN; UNKNOWN = nothing found.
Account names, keys and tokens are left out on purpose. REQ:29 names the Claude account; it is not copied here.

Q23. Plans paid for, and is the pain limits or money?
Mark: PARTLY.
1. Claude: on 30 Oct the Claude Code CLI reported subscriptionType "max" (REQ:29). Ayush: "i change the login among my friends", so the Claude CLI account rotates and its quota is unknown (REQ:67). The paid harness uses a Claude subscription login refreshed from the macOS keychain (MCT/decisions.jsonl:188; route B "Claude-subscription agent", MCT/lessons.jsonl:51). opencode reaches Anthropic through the opencode-anthropic-console plugin (UP/inputs/opencode_settings_20261103.md:9, :124); whether that is a subscription login or an API key is UNKNOWN.
2. OpenAI: Codex CLI is "Logged in using ChatGPT" (REQ:28); GPT inside opencode also uses the ChatGPT login (UP/QUESTIONS.md:72, Q43). Plus or Pro: UNKNOWN. No OpenAI API key use was found.
3. Kiro: a kiro provider (kiro-cli) with 20 models is configured (UP/inputs/opencode_settings_20261103.md:8, :44 to :74). Plan: UNKNOWN.
4. Pain: every record is about usage limits, none about money. Usage limit hits: MCT/decisions.jsonl:186 (harness, night of 25 Oct), :408 (evening auto stopped 28 Oct), :668 (Codex "model at capacity"). Limit rules Ayush set for the lever hunt: Claude limit means wait and resume; an OpenAI or Codex limit moves work to Claude only when no build, QC or fix runs on Claude (MCT/decisions.jsonl:662). Ayush: "save Claude Opus: use Codex or opencode GPT for workers wherever possible" (MCT/feedback.jsonl:31). Subagents fail in a GPT session once the Claude limit is used up (UP/QUESTIONS.md:92, Q57). The dollar figures in opencode's database are recorded list costs, not charges (S7/FINDINGS.md:17).
Prefill: Claude Max (rotating among friends) plus a ChatGPT plan used by Codex and opencode GPT; the pain is usage limits. To confirm: the ChatGPT tier, whether opencode Claude uses the same Max login, the Kiro plan, and whether money matters at all.

Q24. Which step feels most expensive?
Mark: PARTLY (measured cost FROM RECORDS; Ayush's feeling UNKNOWN).
1. Per session, measured on 190 sessions issued 22 to 30 Oct (S7/FINDINGS.md:19 to :25, medians): P2 build 218k output, 153k reasoning, 27.4M cache read, 24.21 USD recorded; P9 harden 18.7M cache read, 12.39 USD; P11 QC 11.0M, 8.97 USD; P12 fix 10.1M, 6.23 USD; P13 blind 1.3M, 1.25 USD.
2. In total over that window (W1-033 sum over S7/worker_measurements.csv): QC 811M cache read, 739 USD recorded (40 percent of the 1,830 USD total); fix 632M, 512 USD (28 percent); harden 290M, 240 USD; build 258M, 251 USD; blind 73M, 88 USD.
3. So build is the most expensive single session, and QC plus fix are the most expensive in total because they repeat (board: about 1.9 QC and 3.3 fix sessions per built task, see TOKENS.md).
4. Master chat: not measured. Claude's stats cache up to 24 Oct shows 2.53 billion cache read and 12.8M output tokens for claude-opus-5-5 over 19 sessions, master included (S7/FINDINGS.md:7). DCP showed "Compression #258" and "DCP | -8168.3K removed" in the master (UP/ANSWERS.md:55 to :59).
Prefill: QC and fix rounds in total, build per session. To confirm: what Ayush feels, and whether the master chat burns his Claude limit first.

Q25. Are cheaper models fine for mechanical steps?
Mark: PARTLY.
1. Ayush already moved some work off Opus 5.5: GPT for the learning part (MCT/decisions.jsonl:661 "for models use gpt for learning part"); opencode GPT 6.1 Sol for replays and blind scoring (:653, :682); Codex read only for screening and static QC (:741, :747); a pre QC check with Codex read only (:593).
2. He kept build, QC, fix and pilot design on Opus 5.5, and blinds on claude-opus-5 to match the paid run (MCT/decisions.jsonl:661; R31 workers Opus 5.5 high, UP/RULE_REVIEW.md:112).
3. S7 recommends lower effort or a cheaper model only for mechanical report assembly and extraction, after a paired test; savings UNVERIFIED (S7/FINDINGS.md:37). The only low effort datum: Codex smoke test at reasoning low, 12 s, 7,146 tokens, correct (REQ:72).
4. Smaller Claude models (Sonnet 5, Haiku 4.5) are listed in the Kiro provider (UP/inputs/opencode_settings_20261103.md:55 to :64) but no record shows one used or tested.
Prefill: yes for GPT or Codex on read only and scoring work; UNKNOWN for smaller models on tallies, diffs and intake (no test, no answer).

Q26. Every tool and model used now.
Mark: FROM RECORDS, except Cursor.
1. opencode 1.19.0, agent Sisyphus (oh-my-openagent 5.1.33), plugins DCP 3.2.0, opencode-anthropic-console, opencode-kiro 0.4.0 (UP/inputs/opencode_settings_20261103.md:6 to :9; UP/QUESTIONS.md:90, Q56).
2. Models in opencode: anthropic/claude-opus-5-5 variant high, master and default worker (MCT/auto/auto.py:63 to :64; UP/QUESTIONS.md:69, Q40); anthropic/claude-opus-5 for blinds (12 spawns, auto runs 31 Oct to 1 Nov events.jsonl); openai/gpt-6.1-sol for replays and scorers (8 spawns, same files); kiro/claude-opus-5.5 once, smoke test only (MCT/decisions.jsonl:427).
3. Codex CLI 0.163.0, ChatGPT login, default model gpt-6-sol, default reasoning xhigh (REQ:28, :72). Run by the master with codex exec (MCT/decisions.jsonl:589, :596; LH:6 to :29) and by Ayush pasting worker prompts (UP/ANSWERS.md:53).
4. Claude Code CLI 2.1.314 (REQ:29): used by the paid harness and Ayush's trajectory runs (MCT/decisions.jsonl:25, :188); not used for workers (S7/FINDINGS.md:13).
5. ChatGPT web for task premises and deep research (MCT/decisions.jsonl:212; MCT/open_questions.json:193 to :194); Gemini Deep Research by paste (MCT/decisions.jsonl:65; MCW/20261030_upgrade2/S9_external_research/FINDINGS.md:11). Gemini CLI is not installed (REQ:31).
6. A Codex bridge is the judge inside the paid harness (MCT/lessons.jsonl:51; MCW/20261028_sentinel-policy-recompute/regrade_r13_188771e/LOG.md:59).
7. Kiro: configured, but Ayush said workers "not kiro" (MCT/decisions.jsonl:172) and "No kiro" (:653).
8. Cursor: no record. UNKNOWN.

Q27. Which tool for which step, and why.
Mark: FROM RECORDS (31 Oct plan), with one mismatch to confirm.
1. Ayush's model split (MCT/decisions.jsonl:661): master Opus 5.5; learning on Codex GPT (subagents ok); opencode GPT without subagents for Docker work (replays, scoring); blinds anthropic/claude-opus-5; build, QC, fix and pilot design Opus 5.5.
2. Codex only for read only or static work: screening, static QC, report drafts (MCT/decisions.jsonl:593, :741, :747; MCW/20261030_upgrade2/UPGRADE2_PLAN_DRAFT_v1.md:19).
3. Why: to spare the Claude limit (MCT/feedback.jsonl:31); Codex is not proven for Docker gates or bundle edits (S7/FINDINGS.md:1, :47); blinds must use the model closest to the paid run agent (S7/FINDINGS.md:47, P13 rule).
4. By hand, Ayush pastes QC, build or fix prompts into opencode GPT 6.1 Sol, opencode Opus 5.5 or Codex (UP/ANSWERS.md:53). The board and issued prompts do not record which tool ran a prompt (only 2 board rows name Codex, 1 names GPT), so the real split of hand started sessions is UNKNOWN.
5. Mismatch: MCT/decisions.jsonl:653 says blinds d830ccb, 5c1644a, de212ed ran on Opus, but their spawn events have no model, so they ran on the auto.py default anthropic/claude-opus-5-5, not claude-opus-5 (auto/runs/20261031T1606_stage2cause/events.jsonl). Also MCT/decisions.jsonl:426 says an AUTO_MODEL environment variable was added to auto.py, but the current auto.py has no AUTO_MODEL (only the constant at :63).

Q28. Should auto mode start and watch Codex and the others?
Mark: PARTLY.
1. For research Ayush chose "master runs codex exec itself" (REQ:66). The master did so with a launcher, a supervisor script (10 minute ticks, max 3 parallel, resume once, 30 minute stuck kill, usage limit wait) and timed check ins (MCT/decisions.jsonl:596, :598; LH:6 to :73).
2. S7 recommends a worker adapter beside auto.py that records sha, provider, session id, pid, output path, start, end and exit code, and validates result_<sha>.json (S7/FINDINGS.md:9).
3. Caution from the records: the master once started Codex runs after answers but before "proceed" (MCT/feedback.jsonl:27).
4. For build, QC and fix steps that Ayush starts by hand in Codex or opencode GPT: no answer found. UNKNOWN.

Q29. Known limits per tool in practice.
Mark: FROM RECORDS, except "GPT skips parts of long prompts" (UNKNOWN, no record).
1. Codex: Docker socket and harbor inside its sandbox were never tested (S7/FINDINGS.md:11; S7/CLI_MATRIX.csv row codex), so Codex prompts say no Docker and no writes outside OUT (MCW/20261031_lever_hunt/PLAN_FINAL.md:117; MCW/20261031_learning/supervise_learning.sh:51). "Selected model is at capacity" after 26 s (LH:14; MCT/decisions.jsonl:668). A Codex job died when the launching shell's process group was killed; fix proposed: nohup plus disown (LH:25, :81). It waits on stdin unless given /dev/null; macOS has no timeout command (REQ:72). It names threads itself after turn 1, so session renaming runs again as the last step (MCT/lessons.jsonl:68); in Codex the rename is skipped with "Codex, not renamed" (MCW/20261102_screen12/REPORT.md:3). Phase A screen of 102 tasks used 99k tokens (LH:10).
2. opencode with GPT: Sisyphus subagents start on Claude and fail once the Claude limit is used up; hence the no subagent line (UP/QUESTIONS.md:92; MCT/feedback.jsonl:32).
3. opencode in general: an account rate limit is retried inside opencode while the session stays BUSY with an empty message, so auto.py does not see it; still open (MCT/feedback.jsonl:15). A build session stopped with finish=length after 32,000 reasoning tokens and no output (MCT/decisions.jsonl:666).
4. Claude CLI: rotating account, quota unknown; no heavy claude -p work without asking (REQ:67; S7/FINDINGS.md:13).
5. Harness: a login fault was first read as a usage limit (MCT/decisions.jsonl:188).
6. Not a limit but useful: blinds failed the same checks on Opus 5.5 and Codex 6 Sol (MCT/lessons.jsonl:67).
