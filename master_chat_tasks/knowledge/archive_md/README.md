# master_chat_tasks: records for the task-creation master chat

Role: advisor for CREATING and HARDENING Harbor tasks. Heavy work runs in other chats; this chat gives the next step, the target chat and a paste-ready prompt.
Created 20 Oct 2026, 21:19 IST. Skill: ayush-input-bundle-generator.

## Read order (after every compaction)
1. README.md (this file)  2. state.md  3. failures.md  4. decisions.md  5. log.md (last entries)
Then re-check live state (files, processes) before acting. Records can be stale.

## Standing rules (from Ayush, 20 Oct 21:19 IST)
- STRICT: only Terminal_2.0_Harbor_Harness, Anubis_Tasks_Samples, beta-task-generator, Finalized_Tasks_RFP. Read-only git/gh only. Never pull, commit, push, merge, checkout, reset or open a PR; give Ayush the commands. Every prompt I write must carry this rule.
- Never edit Terminal_2.0_Harbor_Harness or "QC assigned"/"my tasks" without explicit "proceed".
- No OPENAI_API_KEY: judge never runs. Label every score tests-only.
- Jobs over 4 min run in background, logs in /tmp/opencode-logs/<task>/. Never end a turn while a needed job runs.
- Ask when unclear. Replies short. Prompts for other chats in their own fenced block, target chat named above it.
- Record only rules, decisions, failures, state changes. IST times. No secrets.

## Active temp workspace
Until the discussion concludes, live work is in `../_tmp_master_tasks_20261020T2214/` (read its README + state.json first).
