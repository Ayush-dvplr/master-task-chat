# S7: Codex and Claude CLI as workers; token and time efficiency
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/S7_cli_workers/`

Goal (Ayush U11, U14): the master can run `codex exec` directly (tested: 12 s, 7,146 tokens, model gpt-6-sol). Decide when worker jobs should run as `codex exec`, as `claude -p` (Claude Code CLI; its login rotates among Ayush's friends, quota unknown), or as opencode sessions, and how to cut tokens/time without hurting quality.

Do not run codex or claude yourself (you are inside codex; nested runs are the master's job). Use help texts (`codex exec --help`, `codex --help`, `claude --help`), local config (`~/.codex/config.toml` keys only, never auth), local session logs for measurement (`~/.codex/sessions/` if present, `~/.claude/projects/*/*.jsonl` token fields, `~/.claude/stats-cache.json`, opencode DB read-only: per-session token counts if stored).

Answer with evidence:
1. Capabilities matrix (`CLI_MATRIX.csv`): codex exec / claude -p / opencode worker: non-interactive start, resume, sandbox and file-write limits, can it run Docker/harbor, output to file, JSON events, session titles, cost/limit visibility, failure modes (stdin wait, approvals). Note what the master's auto.py would need to drive each.
2. Measured cost: tokens and wall time per step type (P11 QC, P12 fix, P13 blind, P9 harden, P2 build) from the opencode DB (read-only) or logs; where are tokens spent (re-reading rule files, long tool outputs, polling loops, compaction)?
3. Savings without quality loss: concrete patterns (shorter standing rules via references, cached rule digests, smaller polls, scripts instead of reasoning, lower reasoning effort for mechanical steps, model per step), each with estimated saving and the risk to task quality.
4. Which step types are safe to move to codex exec first (read-only analysis, report writing) and which must stay (Docker gates, edits to bundles) with reasons; a pilot plan to compare one step type head-to-head on the same input.
