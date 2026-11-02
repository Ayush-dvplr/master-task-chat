# Harness master: finish route B setup (Claude-subscription agent + Codex judge)
Issued 22 Oct 2026 14:45 IST by the task master chat. Paste this into the harness master chat.

## Context (verified by the task master, 22 Oct 13:40-14:43)
- Clone: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness` (main, a74bda85). The runner, ledger, queue, jobs and Tasks_INPUT have been copied in, and are kept out of git via `.git/info/exclude`. `.venv` is ready and the 14 runner tests pass.
- Route B (Ayush's choice, from the PL): agent `openhands-sdk` on `claude-opus-5`, paid by the Claude subscription, using `scripts/run-with-subscription.sh`. Judge `gpt-5.6-sol` on Codex, the default (`JUDGE_PROVIDER=codex`).
- Claude Code login: done by Ayush (keychain updated 14:41 IST). Codex CLI: logged in (auth mode chatgpt).
- Not done yet: `scripts/anubis-auth setup`. There is no pool file, and `~/.anubis/subscription.env` has no `ANUBIS_CC_ACCOUNT_POOL` or `ANUBIS_CC_BRIDGE_SECRET`.
- Gap: `scripts/master_queue.py` hardcodes `WRAPPER = "scripts/run-with-kiro-subscription.sh"` and the Kiro judge.
- Read `HYBRID_RUN_GUIDE.md` sections 1.2-1.5 and the header of `scripts/run-with-subscription.sh` before acting.

## Rules
- Never run logins yourself: no `claude` sign-in, no `kiro-cli login`, and no `anubis-auth setup` or `add` if they ask for interactive input. Give Ayush the exact commands to run in his own terminal. `source ... login` only affects his shell.
- Never print secret values. Name keys only.
- Do not start a real run. Only use `--dry-run` or `--skip-preflight`-free preflight checks that spend nothing.
- Edit `master_queue.py` only after Ayush approves the exact change list. It is untracked, so make a backup copy first.
- Record every step in `harness_master_tasks/` (pending.db Q03, log.jsonl, state.json `route`).

## Steps
1. Ask Ayush to run, from the clone folder:
   ```
   scripts/anubis-auth setup
   source scripts/anubis-auth login
   scripts/anubis-auth status
   ```
   Then verify on disk: the pool file exists, and the two `ANUBIS_CC_*` keys are set in `subscription.env` (check names only).
2. Check the usage wiring without spending anything: `scripts/.venv/bin/python3 scripts/preflight_usage.py` (or `.venv`, whichever the guide's 1.4 uses), plus the guide's 1.5 dry-run check.
3. Dry run: `scripts/run-with-subscription.sh -p Tasks_INPUT/schema-migration-plan-repair -a openhands-sdk -m claude-opus-5 -y --dry-run`. Confirm:
   - the agent model is `anthropic/claude-opus-5` on the Claude bridge, not Kiro;
   - the judge is `gpt-5.6-sol` through `codex_oauth`;
   - `--artifact /logs/agent/trajectory.json` is present, with an absolute `-o`/jobs dir.
   The Kiro wrapper injected `--allow-agent-host host.docker.internal`, `--ae LITELLM_LOCAL_MODEL_COST_MAP=True` and `--ae HOME=/tmp`. Report whether this wrapper does the same; if not, list what is missing.
4. Propose the `master_queue.py` change list to Ayush: wrapper path, judge model and provider, a per-run private `--jobs-dir`, and anything step 3 showed is missing. Wait for "approved" before editing. After editing, run its tests and do one `--dry-run` through the runner.
5. Reply with: the setup status, the dry-run findings, the proposed change list, and the open questions for the PL (which Claude account or pool; Odoo `ANUBIS_PROJECT_*` / `RFP_SUB_TYPE` values for this route; attempts per run).
