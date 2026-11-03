P6 ADAPTER DESIGN (W1-033, 3 Nov 2026). Draft, nothing applied. Built only from the records; guesses are marked UNVERIFIED.

Paths: MCT = master_chat_tasks, S7 = master_chat_work/20261030_upgrade2/S7_cli_workers, LH = MCT/auto/runs/20261031T2154_leverhunt/REPORT.md.

PART 1. WHAT EXISTS TODAY
1. auto.py drives only opencode: one constant model anthropic/claude-opus-5-5 and variant high (auto.py:63 to :64), sent with every prompt (auto.py:369 to :374); spawn --model provider/model overrides it per worker and is kept for later sends (auto.py:390 to :401, :1204 to :1217; MCT/decisions.jsonl:653). It starts "opencode serve" (auto.py:764) and gives workers OPENCODE_PERMISSION (auto.py:116 to :145, :456).
2. Codex runs outside auto.py, from the master's bash with launcher and supervisor scripts (MCT/decisions.jsonl:589, :596, :598). Each Codex job wrote FINDINGS.md, QUESTIONS.md, result.json, last.txt, codex.log and status.txt into its OUT folder (MCT/decisions.jsonl:589).
3. intake.py SHA reads the board row's OUT folder, parses every result*.json, takes "status" or "verdict", lists the keys, and counts open TODO.md lines (MCT/tools/intake.py:80 to :110). It does not care which tool wrote the file.
4. Found while checking: intake marks a row done only for status "done", "complete", "completed", "PASS" or "pass" (intake.py:104). The Codex jobs wrote "DONE" in capitals (S7/result.json), which intake would mark partial. The adapter should write lowercase, or intake should compare without case.

PART 2. ONE SETTINGS BLOCK PER STEP (adds to drafts/P1/settings.json, replaces its two line "models")
Each step names: tool, provider, model, variant, max_prompt_kb, subagents, docker, writes. Values below are what the records show Ayush chose; the size limits are UNVERIFIED proposals.

"steps": {
  "master":   {"tool": "opencode", "provider": "anthropic", "model": "claude-opus-5-5", "variant": "high", "subagents": false, "dcp": "manual"},
  "build":    {"tool": "opencode", "provider": "anthropic", "model": "claude-opus-5-5", "variant": "high", "max_prompt_kb": 45, "subagents": false, "docker": true, "writes": "bundle, WORK, OUT"},
  "harden":   {"tool": "opencode", "provider": "anthropic", "model": "claude-opus-5-5", "variant": "high", "max_prompt_kb": 40, "subagents": false, "docker": true, "writes": "bundle, WORK, OUT"},
  "qc":       {"tool": "opencode", "provider": "anthropic", "model": "claude-opus-5-5", "variant": "high", "max_prompt_kb": 20, "subagents": false, "docker": true, "writes": "OUT"},
  "fix":      {"tool": "opencode", "provider": "anthropic", "model": "claude-opus-5-5", "variant": "high", "max_prompt_kb": 25, "subagents": false, "docker": true, "writes": "bundle, OUT"},
  "blind":    {"tool": "opencode", "provider": "anthropic", "model": "claude-opus-5", "variant": "high", "max_prompt_kb": 8, "subagents": false, "docker": false, "writes": "blind dir"},
  "score":    {"tool": "opencode", "provider": "openai", "model": "gpt-6.1-sol", "variant": "high", "max_prompt_kb": 12, "subagents": false, "docker": true, "writes": "OUT"},
  "research": {"tool": "codex", "provider": "openai", "model": "gpt-6-sol", "variant": "high", "max_prompt_kb": 15, "subagents": false, "docker": false, "writes": "OUT"},
  "paid_run": {"tool": "harness", "model": "claude-opus-5"}
},
"tools": {
  "opencode": {"enabled": true},
  "codex":    {"enabled": true, "parallel": 3, "resume_max": 1, "stall_min": 30},
  "claude_cli": {"enabled": false, "why": "account rotates, quota unknown (REQUEST.md:67)"},
  "kiro":     {"enabled": false, "why": "Ayush: not kiro (MCT/decisions.jsonl:172, :653)"}
}

Sources: master, build, QC, fix Opus 5.5 high; blinds claude-opus-5; opencode GPT without subagents for Docker work; Codex for learning (MCT/decisions.jsonl:661; R31 now a setting, upgrade_plan/RULE_REVIEW.md:123). Scoring on GPT 6.1 Sol (MCT/decisions.jsonl:653, :682; LH:35, :70). Codex 3 at a time, one resume, 30 minute stall (MCT/decisions.jsonl:595, :598, :668). Paid run claude-opus-5 (settings.json models.paid_run).
Conflict to confirm: research subagents. MCT/decisions.jsonl:661 says "learning Codex GPT (subagents ok)" and LH:6 ran phase A with subagents allowed, but :595 says "no sub-agents" and the learning run used --disable multi_agent (:596). The draft says false.
The R32 line applies whenever provider is openai inside opencode; the adapter adds it, not the author (upgrade_plan/PLAN.md:41).

PART 3. ONE SHARED RESULT FORMAT
Every tool writes into the board row's OUT folder:
1. result_<sha>.json with the fields intake already reads: "status" (lowercase: done, partial, failed), "verdict" where the step has one, "files" (list). Plus adapter fields, all additive so intake.py keeps working: "sha", "step", "tool", "provider", "model", "variant", "session_id", "started", "ended", "exit_code", "subagents_used", and "tokens" (input, output, reasoning, cache_read, cache_write) when the tool reports them (opencode database; Codex JSON events, S7/FINDINGS.md:7).
2. The step's own report files (QC report, RECHECK_FIX.md, FINDINGS.md and so on), unchanged.
3. For Codex, also last.txt (from -o), codex.log and status.txt, as the 30 Oct jobs did.
4. intake.py SHA then works the same for every tool. Each job's token fields feed the TOKENS measurement without the S7 database join.

PART 4. HOW A PROMPT IS ADAPTED PER TOOL
The master writes one prompt from the template; issue.py (or the adapter) adds a short tool block at the top and checks the size against max_prompt_kb.
1. Every tool: board sha, OUT path, the result_<sha>.json fields above, and the session rename step (opencode runs name_session.py; Codex skips it and writes "Codex, not renamed", as the templates already say).
2. opencode with GPT: "Strictly do not run subagents (no task, agent or background tools); do all work in this main chat." (MCT/feedback.jsonl:32; R32). Reason: Sisyphus subagents start on Claude and fail once the Claude limit is used up (upgrade_plan/QUESTIONS.md:92).
3. Shorter prompts for GPT: no record shows GPT skipping parts of long prompts. A lower max_prompt_kb for GPT is UNVERIFIED; ask Ayush (Q29) before adding it.
4. Codex: "No Docker, no harbor, never run claude, opencode or codex, read only outside OUT, main chat only" (MCW/20261031_learning/supervise_learning.sh:51; MCW/20261031_lever_hunt/PLAN_FINAL.md:117). The adapter refuses any step with docker true or writes containing bundle for Codex, until a pilot proves Docker and path confinement under its sandbox (S7/FINDINGS.md:1, :11, :47).
5. opencode with Claude: today's prompts, no extra block.

PART 5. HOW auto.py WOULD START EACH TOOL
1. opencode (Claude or GPT): already supported. Change: spawn --step <kind> reads tool, provider, model and variant from settings.json instead of the constants at auto.py:63 to :64, so prompt() sends the step's variant too. Note: MCT/decisions.jsonl:426 says an AUTO_MODEL variable was added on 29 Oct, but the current auto.py has none; confirm which copy is live.
2. Codex: a small runner beside auto.py (S7 recommendation R1, S7/FINDINGS.md:9). It starts codex exec with -s read-only or workspace-write, -C <root>, -o OUT/last.txt, --json, stdin from /dev/null, in its own session group (the nohup plus disown fix, LH:81), and records pid, Codex session id, OUT path and start time in the run state. The watcher then checks: process alive, log growing (stall after 30 minutes), exit code, result_<sha>.json parses. On "at capacity" or a usage limit (LIMIT_RE, auto.py:99) it resumes once with codex exec resume, then reports; it never falls back to Claude without the step's rule (MCT/decisions.jsonl:662, :668). After the job, a rule check greps the Codex log for Docker or writes outside OUT (MCW/20261031_learning/CHECKINS.md:4).
3. Codex jobs count against tools.codex.parallel, not the worker limit, since they use no Mac Docker and a different quota (UNVERIFIED that this is what Ayush wants).
4. Kiro and claude -p: disabled. Kiro passed one smoke test through opencode (MCT/decisions.jsonl:427), so turning it on later is a settings change only.
5. Why it may be better not to: if Ayush keeps starting Codex and opencode GPT by hand (upgrade_plan/ANSWERS.md:53), the shared result format and the board row are enough for intake, the card and the token count; auto start is then only a convenience. This is Q28.

PART 6. OPEN POINTS FOR AYUSH
1. Q28: should auto.py start Codex jobs, or does the master's bash plus the shared format do?
2. Research on Codex: subagents allowed or not (conflict in Part 2)?
3. Should GPT prompts be shorter than Claude prompts? Only if Ayush has seen GPT skip parts (no record).
4. Which steps may move to GPT or Codex after a paired test (Q25), and who approves the test.
5. Confirm blinds use claude-opus-5 every time (three 31 Oct blinds ran on the default Opus 5.5).
