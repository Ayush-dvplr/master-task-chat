# Upgrade 2: draft plan v1 (31 Oct 2026, 00:45 IST)

Status: DRAFT. Nothing is built or changed. Written from the nine research reports S1-S9 in this folder. Still missing: the six external research reports (S9 PROMPTS.md, Ayush runs them later), Ayush's answers to section 4, and the plan verification session. Build starts only after Ayush says "proceed".

Rule for every item: nothing that works today may get worse. Each item names its check and how to undo it. Old files stay authoritative until the new path has passed its check.

Request items: U1-U16 in [REQUEST.md](REQUEST.md).

## 1. What the research found (one line each)

| Session | Main finding | Report |
|---|---|---|
| S1 memory | No single current-state file. 21 board/pending status mismatches (28-30 Oct). `state.json` and `README.md` still carry old gate text (<100/<100/<70) and the retired 35-check cap. Master's mistakes cluster in contradictory prompt conditions, stale artifacts and parsers. | [S1](S1_memory/FINDINGS.md) |
| S2 folders | 1,030 hard-coded paths. `auto.py` and `issue.py` find folders from their own location, so moving folders breaks them. 0 bytes are proven safe to delete today (all 79 QC copies are still referenced). | [S2](S2_folders/FINDINGS.md) |
| S3 database | `board.py`, `status.py`, `decide.py`, `issue.py`, `intake.py` write the same JSON files with no lock. A SQLite DB + per-sha inbox files works (schema tested: WAL, integrity ok). 144 of 352 board result paths are missing. | [S3](S3_database/FINDINGS.md) |
| S4 task study | anubis-stage-2 now has 102 tasks. In the 30 valid Opus runs under 40, held-out exact checks take 30.8% of lost points and judge trajectory criteria 26.6%. Fixes often break something new: judge overlap (30/58 reports), test revisions (26/58), stale prose (20/58). | [S4](S4_task_study/FINDINGS.md) |
| S5 build method | All 7 parked builds had no core that a blind solver missed. The beta generator does not make tasks easy by itself; it just has no kill test. 4 of our recent passes needed a timeout-share exception, yet schema and outage paid runs lost by WRONG, not timeout. | [S5](S5_build_method/FINDINGS.md) |
| S6 auto speed | Most auto fixes from upgrade 1 are applied. New bug: the `Paid runs:` parser reads the first digit (`auto.py:498-500`). There is still no shared Docker slot tool. 3 lanes saved about 16 min on warrant but each oracle ran 22-34% slower. | [S6](S6_auto_speed/FINDINGS.md) |
| S7 CLI workers | `codex exec` works for read-only report work. Bundle edits and Docker gates stay on opencode for now. The biggest time loss is waiting (35%) and sleep/poll loops (23%), not the model. | [S7](S7_cli_workers/FINDINGS.md) |
| S8 signing | SSH signing key held by Ayush + signed manifest of 140 rule files. A signature alone can't stop the master from editing files it owns. Real enforcement needs a separate macOS account. | [S8](S8_signing/FINDINGS.md) |
| S9 external | 6 research prompts and an intake process: any outside idea must pass a design-blind test on our own task before it counts. | [S9](S9_external_research/FINDINGS.md) |

## 2. Workstreams

### A. Memory, fresh-chat bootstrap, decision checks (U1, U2, U6)

| # | Change | Check | Undo |
|---|---|---|---|
| A1 | Clean the 21 board/pending mismatches and the stale texts: `state.json:29,31,89` and `README.md:30-35` gate lines to the current v3.7 gate (tests<85, rubric<85, final<40 + named task exceptions); drop the 35-check cap line. | S1 five examples resolve; `rg` finds no old gate text outside snapshots. | backups in `apply_bak/` |
| A2 | New `tools/generate_state.py` writes `master_chat_tasks/STATE.md` (<=12 KiB): active tasks + sha, open obligations, task exceptions, conflict block, each fact with source + time. Marks itself STALE if a source is newer. | Output matches `status.py` and `board.py` on the same moment; blank-chat test on a past handoff. | delete the file; nothing reads it yet |
| A3 | `BOOTSTRAP_PROMPT.md` (from S1 draft): identity, decision powers, standing feedback rules, path map, resume steps. | A fresh chat answers 10 fixed state questions correctly. | not used |
| A4 | Compaction checkpoint: 10 lines (active sha, next action, conflicts) written by the master before each compaction and on each "done". | Next turn after a compaction resumes without broad re-reads. | stop writing it |
| A5 | Pre-issue prompt lint in `issue.py`: one oracle count, no bar that the allowed edit surface can't reach (cold-chain 12:00 case), allowed-paths list, shipped-bytes rule stated once, one clickable link in the handoff. | Replays the historical mistakes in S1 table 3; each is caught; current good prompts pass. | `--no-lint` flag |

### B. Records database and inbox (U15)

| # | Change | Check | Undo |
|---|---|---|---|
| B1 | Quick fix first: `flock` around read-modify-write in `board.py`, `status.py`, `decide.py`, `issue.py`, `intake.py`. | Two parallel writers lose nothing (test). | revert files |
| B2 | Importer into a new `master.db` (S3 `schema.sql`), dry run only. Raw JSON kept per row. | Row counts and `status.py` view equal old files; `integrity_check ok`. | old files stay authoritative |
| B3 | Workers write `master_chat_tasks/inbox/<sha>.json` (temp file + rename). Master merges on Ayush's `done: <sha>` in one transaction; refuses changed hash or unknown sha. | Fixture corpus of real P2/P9/P11/P12/P13/P16/P17 results, incl. paused and partial. | inbox ignored, old flow kept |
| B4 | Cutover: DB authoritative, `BOARD.md`/`STATUS.md` generated; harness queue and auto state keep their own files. Daily backup via SQLite backup API. | One shadow day with both views equal. | restore files from snapshot |

### C. Folders, cleanup, private git repo (U3, U4)

| # | Change | Check | Undo |
|---|---|---|---|
| C1 | One path map file read by tools, auto and prompt issue; old paths stay valid. | Every `PATH_REFS.csv` row resolves; issue/intake/auto smoke runs. | revert |
| C2 | Private repo at the existing `master_chat_tasks` root, positive allowlist (631 files, 6.7 MB), `.gitignore` from S2. No bundles, jobs, trajectories, QC copies, DBs or secrets. First push only after Ayush reviews the staged list + secret scan. | `git status` shows only allowed paths; fresh clone runs the tools. | delete `.git` |
| C3 | Physical move to `master/{control,work,qc}` with compatibility links, only in an idle window (no workers, QC or harness). | Path checks pass before resume. | links back |
| C4 | Cleanup tool, dry run only: lists candidates by reference check (board, decisions, QC reports), never by age alone. Deletes only a batch Ayush approves. | Dry run lists 0 protected ids. | nothing deleted without OK |

### D. Auto mode and speed (U5, U14)

Order is by time saved × safety (S6 table 5).

| # | Change | Check | Undo |
|---|---|---|---|
| D1 | Strict `Paid runs:` parser: whole value, `no cap` only in the form Ayush approves (Q1), reject times/prose. Fix the 2 stale `test_upgrade_tools` A2Intake tests and the trajectory_readout metered timeout label (pending R10). | Unit cases `6`, blank, `00:40`, prose. | revert |
| D2 | `tools/dockslot.py`: shared Docker leases (flock), budget 8 vCPU / 15.6 GiB minus 3 GiB, task memory from task.toml, dead-lease cleanup, `docker events` wait instead of sleep polls. MQ and worker rules use it. | Two-acquirer test, dead lease, simulated 8+4 GiB contention, dry run next to a paid run. | rules fall back to today's text |
| D3 | QC/fix Step 10 in 3 lanes by default; 4 only after a same-tree 1/3/4-lane benchmark shows median oracle slowdown <=25% and no OOM/timeout. | Benchmark on an idle machine, rewards identical. | 1 lane |
| D4 | Gate reuse only in a P11 recheck after a P12 fix, on an identical tree sha with complete saved results: oracle x1 + nop spot check, `step10: reused <sha>`. Full QC always runs the full gate. | Changed byte forces full gate (test). | remove the block |
| D5 | Gate/blind/log paths move from `/tmp` to `~/tb_runs/<date>/` (the 30 Oct reboot wiped 77 of 80). | Reboot-survival check on a test dir. | old paths |
| D6 | Plan-scoped pre-approved defaults: exact slug, crash/timeout ceiling, tree, expiry (Q2). Out of range or different tree = stop and ask. macOS notification on every Needs-Ayush stop. | Cross-task, expired and changed-tree cases refused. | remove block |
| D7 | Background job manifest per worker (pid, pgid, start time, log) recorded on stop/resume; containers removed by run label, not task-name prefix. No automatic kill without Q17 OK. | Fake detached child; two same-task sessions, cancel one, other untouched. | old behaviour |

### E. Fast QC kit updates (U7)

| # | Change | Check | Undo |
|---|---|---|---|
| E1 | Every issued prompt carries the QC kit hash and rule-file hashes (short dispatch header, S7 R5). `issue.py` refuses if the kit changed since the template was last checked. | Change a kit file in a fixture; issue refuses with the changed file named. | flag off |
| E2 | Kit-change routine: diff old/new kit → one template-update session → CHANGELOG line → re-sign (H). | Dry run on the last real kit change. | — |

### F. Task study, build method, levers (U8, U9, U10)

| # | Change | Check | Undo |
|---|---|---|---|
| F1 | S4 scripts become read-only tools (`peer_inventory`, `lever_weights`, `fix_map`), rerun after each peer-repo refresh. | Reproduce S4 counts. | — |
| F2 | P12 fix receipt: before/after tree sha, changed check ids + weights, oracle/agent deltas, verifier budget, doc consistency scan. Targets the 5 "fix broke something" families. | Re-process the 11 FIX_MAP rows. | template line |
| F3 | Build recipe (S5 `DRAFT_BUILD_RECIPE.md`): design-blind core proof before full build; kill table must include a contention-aware decomposition solver (outage lesson) and a strong generic exact solver; loss split WRONG/TIMEOUT/CRASH; NO CORE stop; target declared on the idea card (Q4). Into P2/P9 templates + LEVER_RULES as v3.8. | Two pilots (F4) follow it end to end. | v3.7 snapshot |
| F4 | Lever pilots, cheapest first: N2+N1 held-out w5 + judge probe band; then LC1 bounded induction. LC3/LC5/LC6 only as add-ons once their own blind delta is non-zero. No paid run on a failed pilot. Promotion needs 2 frozen tasks with tests<=60, rubric<=20, 2/3 blinds losing >=40%. | 3 blinds × 3 seeds each. | lever stays PROMISING |
| F5 | Outside research (U12): Ayush runs the 6 S9 prompts; master checks each report through [INTAKE.md](S9_external_research/INTAKE.md); ideas enter F4 only after a design blind. | Source ledger checked. | — |

### G. Codex / Claude CLI workers (U11)

| # | Change | Check | Undo |
|---|---|---|---|
| G1 | Worker adapter next to `auto.py`: records provider, session id, pid, output path, exit code; validates `result_<sha>.json`; stdin closed, time-bounded. | Fake JSONL process test. | opencode only |
| G2 | Pilot: one report-only step on frozen input, opencode vs `codex exec -s read-only`, checker compares every claim. Then one P13 blind A/B as research only. | Same-input comparison table (time, tokens, misses). | — |
| G3 | No `claude -p` heavy work until the account and quota are settled (Q7). | — | — |

### H. Self-upgrade guard (U13)

| # | Change | Check | Undo |
|---|---|---|---|
| H1 | Ayush-held SSH signing key; signed manifest of the 140 protected files (rules, templates, knowledge, tools, auto policy/plans, opencode config). Verifier runs before master start, after compaction, before issue/spawn/harness. Mismatch = stop and name the files. | Fixture: edit/add/delete each fail; signed state passes. | launcher off |
| H2 | Approval flow: master writes a proposal diff; Ayush applies, runs `approve.sh`, types APPROVE + passphrase. Auto plans signed before unattended start (Q15). | Fixture auto run refuses spawn after an unapproved edit. | — |
| H3 | Optional hard enforcement: separate non-admin `tb-master` macOS account (Q14). Only after A–D are stable; needs mutable state split from `state.json`. | Write attempt on a protected file fails from that account. | keep current account |

### I. Token and time (U14)

Covered inside A2/A4 (short state + checkpoint instead of broad re-reads; S3 estimate ~10-12k tokens saved per bootstrap), D2 (event wait instead of 23% poll time), E1 (short dispatch header), F1 (scripts instead of re-reading trajectories), G2 (cheaper worker only for mechanical report work after a paired check). Rule: lower reasoning or cheaper models never for P2 build, P9 design, P11 judgement or P12 lever-keeping fixes until a paired test shows the same findings.

## 3. Order

| Batch | Items | Gate before next |
|---|---|---|
| 0 | Ayush answers section 4; plan verification session (V2) writes v2 | V2 verdict PASS or PASS WITH FIXES |
| 1 | A1, B1, D1, A5, F2 (small, high value, no behaviour change for good prompts) | all tool tests green; lint replays pass |
| 2 | A2-A4, E1, C1, C2 (repo created, first push after review) | blank-chat test; path checks; staged-list review |
| 3 | D2-D7 (speed) | dockslot tests + idle benchmark |
| 4 | B2-B4 (DB, shadow day) | view parity |
| 5 | F3, F4 pilots, F5 intake, G1-G2 | pilot results |
| 6 | H1-H2, then H3 if chosen; C3 move and C4 cleanup in an idle window | fixture refusals; idle-window path checks |

Running tasks are not touched during batches 1-4 except through the normal tools. The Nikhil QC `0d957b9` is not affected.

## 4. Questions for Ayush (recommended option first)

1. **Paid-run cap text.** (A) Allow `Paid runs: no cap` only as that exact phrase written by you in a run plan; everything else must be a whole number, default 6. (B) Always a number. — You have used "no cap" before, so A.
2. **Task-specific crash/timeout ceilings in a plan.** (A) Yes: exact slug, %, tree and expiry; auto may send go inside it, stops above it. (B) Ask you every time.
3. **New builds whose blinds lose only by timeout/crash.** (A) NO CORE by default; an exception only with your OK, a named wrong-answer solver and one paid run. (B) General 60-100% allowance. (C) Always reject.
4. **When is the gate <35?** (A) Declared on the idea card for lever pilots; others keep <40. (B) <35 for every new build.
5. **Beta generator prompts.** (A) Pilot the recipe in our pipeline on 2 tasks first, then propose beta edits with evidence. (B) Edit beta now.
6. **Study cohort.** (A) All 102 current anubis-stage-2 tasks. (B) A 52-task list you give.
7. **Claude CLI.** (A) No Claude pilot until the account owner and quota are settled. (B) One small report-only pilot now.
8. **GitHub repo.** Exact owner and name? Suggested: your account, `terminal-bench-master`, private.
9. **Who approves pushes.** (A) Master pushes review branches; you approve the first push and every merge to `main`. (B) Master merges routine changes; you approve only protected files.
10. **Folder move.** (A) Move into `master/{control,work,qc}` in an idle window after path checks. (B) Keep current names forever.
11. **Cleanup.** (A) Dry run + your OK for every deletion batch. (B) Auto-delete verified unreferenced temp/run data after the age limits.
12. **Old JSON files after DB cutover.** (A) DB authoritative; old files frozen as snapshots; only generated views. (B) Write both for a transition period.
13. **Gate confirm.** Current gate is v3.7 (tests<85, rubric<85, final<40, plus named task exceptions). S3 suggested the older v4 text; that text is stale. Confirm v3.7 so A1 can fix README/state.json.
14. **Separate macOS account for the master.** (A) Later, after batches 1-4 (real enforcement). (B) Never; signing detects changes but can't block them.
15. **Auto plan approval.** (A) You sign each plan before an unattended start. (B) Sign only the template.
16. **Plugin code in the signed set.** (A) Pin versions and include the loaded package files. (B) Sign config only.
17. **Stopping leftover background jobs.** (A) Record only; you OK each kill. (B) Auto may kill jobs it can prove it owns (pid + start time + path).

## 5. Still missing before the final plan

- External research reports R1-R6 (S9 prompts), saved under `S9_external_research/returned/`.
- Plan verification session V2 (prompt to write after your answers).
- Not measured yet: idle-machine lane benchmark (D3), real token savings (I), Claude quota (G3).
