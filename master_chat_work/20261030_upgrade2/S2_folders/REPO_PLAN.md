# Draft: private repository for master control

## Boundary

Create the new private GitHub repository with its worktree rooted at the **current** `Terminal Bench/master_chat_tasks/`. Do not initialize Git at `Terminal Bench/`. This confines normal staging to master control and keeps the separate harness and teammate repositories outside it. Later, if the folder restructure is approved and verified, move this repository with `master_chat_tasks` to `master/control`; retain the old compatibility link.

## Include

- `tools/`, `auto/` source, tests, plans, and `AUTO_POLICY.md` (exclude `auto/runs/`).
- `prompts/templates/`, `prompts/issued/`, and `prompts/drafts/` as provenance and future prompt sources.
- `knowledge/`, `registry/`, `README.md`, `GOALS.md`, `BOARD.md`, `board.json`, `state.json`, `open_questions.json`, `decisions.jsonl`, `feedback.jsonl`, `lessons.jsonl`.
- A future text/JSON export of `pending.db`, generated only at a quiescent snapshot point; define schema and importer before relying on it.

The measured candidate is 631 files and 6,734,167 bytes (`python3 scripts/repo_scan.py`, 30 Oct 2026). This size excludes Git metadata. Recompute before the first commit because master state is live.

## Exclude

Keep `master_chat_work/`, `QC/`, the harness clone, task bundles, run jobs, trajectories, QC copies, Docker data, and all other root folders outside the repository. Exclude `pending.db`, `log.jsonl`, `auto/runs/`, credentials, environment files, caches, and large/binary artifacts inside control. See the draft `.gitignore`; stage from an explicit allowlist in addition to ignore rules. `git add .` is not the staging policy.

## First push

1. Ayush chooses the GitHub owner and private repository name and confirms the remote is private.
2. At a quiet point, copy or freeze a consistent board/registry/state snapshot; scan candidate file **contents** and Git history with a credential scanner. The broad `rg -n` triage found 991 locations (`SECRET_SCAN_RG_LOCATIONS.txt` contains location only), so human review is required before publication.
3. Initialize at `master_chat_tasks`, add the remote, stage the allowlist, inspect `git diff --cached --name-only` and size. Reject any path outside the allowlist or any secret. Commit and push an initial `main` branch only after Ayush approves that concrete staged tree.
4. Protect `main`; master works on `upgrade2/<topic>-YYYYMMDD` branches. Commit messages use `<area>: <imperative summary>`, for example `prompts: update QC kit references` or `control: add path map`.

## Routine push/pull

- Master may push review branches after local checks and secret/path review. Ayush approves merges to `main`, especially changes to rules, prompts, `AUTO_POLICY.md`, and control tools. Exact routine push authority remains an Ayush question in `QUESTIONS.md`.
- Pull only when no active writer is modifying board, registry, decisions, or state; fetch and fast-forward from an approved `main`. If history diverges, stop and review, do not reset live state. Export/check the live pending DB separately because it is intentionally outside Git.
- After a fresh clone, verify path configuration, control script imports, prompt rendering, board/registry consistency, and the pending-state import before using it as the live master.

No repository, remote, commit, or push was created in this research session.
