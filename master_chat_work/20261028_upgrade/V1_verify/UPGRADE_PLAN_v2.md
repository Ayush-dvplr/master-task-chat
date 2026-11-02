# Upgrade plan v2 (verify session 5125258, 29 Oct 2026 00:45 IST; from v1 board 3d3a74a)

Nothing here is applied. Ayush's 25 answers (`U/P1_plan/ANSWERS.md`) are folded in; only the chosen branch is written. The master applies it batch by batch after Ayush says "proceed". Verify evidence for every change: `U/V1_verify/VERIFY_REPORT.md`.

## Changes from v1

| # | Item | Change | Why (evidence in VERIFY_REPORT) |
|---|---|---|---|
| 1 | header, sec 7 | Questions removed; answers folded in; R1T/R1M paths fixed to `U/R1_ql_loop/drafts/...` | ANSWERS.md; files are under `drafts/` |
| 2 | A1 | Verify rewritten (dry run prints `DRY RUN ok: would write ...`, not the prompt; temp tree recipe); "24 overrides" -> 23 | issue.py:114-126; DEC count |
| 3 | A2 | Verify rewritten (`MET`/`not met`, not `False`; job district 44.84 and sentinel 40.48; would-be row printed without `--apply`); empty registry `tree_sha` refusal message; depends on A3 | intake.py:104-111; tasks.json has no tree_sha |
| 4 | A3 | Verify rewritten (`status.py` has no `--help`); freeze writes `tree_sha`; backfill cold-chain | status.py has no argparse |
| 5 | A4 | Calls `package()` (:216) into a /tmp staging dir, not `_package_run()` only; main is :273-298; sentinel REGRADE_REPORT full path | package_rfp_bundles.py:117, :216-238 |
| 6 | A7 | IN (Q1 a); pipeline_v4 PLAN.md :12, :59, :99 added | grep regrade |
| 7 | B-N1..N9 | Q6: N2-N4 by Ayush after the upgrade from `DOCKER_STEPS.md`; N4 JSON uses current GC keys; N5 by Ayush in Terminal.app (master is an opencode session); N7 pid 15335 still alive, 23171 gone | ANSWERS Q6, Q8; ps; Docker docs |
| 8 | C0 | `_COMMON_RULES_v5` snapshot name -> `_COMMON_RULES_v5_v3.6_snapshot.md` (Q12); counts 13/4 include CHANGELOG | ANSWERS Q12; grep -l |
| 9 | C1 | Site list completed (20 live lines in 11 files); verify grep rewritten so it can pass | grep run 00:31 IST |
| 10 | C2, C3 | Stats marked CHECKED (V1 re-ran R3 s05/s08 and R4 contrast) | /tmp/V1-verify-5125258 |
| 11 | D | Q14: Ayush asks Aditya Jain and Anjali Kumari for their scripts (new D6) | ANSWERS Q14 |
| 12 | E1 | Worker sequence fixed (A1-A4 Batch 1, E1 Batch 2, same session); Q17 macOS notification; Q18 log-only; verify recipe rebuilt (exp1 copy step, fake server as a unit test) | R5 /tmp files deleted; ANSWERS Q17/Q18 |
| 13 | E2, E5, E6 | Q19/Q20/Q16 folded; master_queue full path `H/scripts/master_queue.py` + backup | file location |
| 14 | F1 | Q22 a; CR:28 -> CR:29; RECHECK_FIX full path | CR:29; file path |
| 15 | F2 | OK source = ANSWERS Q23 a (REPORT.md:22 is an open question, not an OK); run with no other Docker-heavy job until N2 | REPORT.md:22; R2F:53 |
| 16 | F3 | Q24 a; DESIGN v2 must meet C2 (a) and (d); 42-45 worlds at 30 s fail both -> concrete bar, else park | arithmetic in VERIFY_REPORT check 3 |
| 17 | sec 5 | Batch 0 done items; G1 and G2 commands fixed; smoketest is a real (subscription) run; RESUME adds tree_sha backfill; B-N2..N4 moved after Batch 4 | checks 6, 7 |
| 18 | sec 1, 6, 8 | Summary items 4, 8, 10, risks and not-doing rows rewritten without open questions | ANSWERS.md |

Path roots: `T` = `/Users/mac/Desktop/Terminal Bench`, `MT` = `T/master_chat_tasks`, `U` = `T/master_chat_work/20261028_upgrade`, `H` = `T/Terminal_2.0_Harbor_Harness`.
Source abbreviations: `R1F` = `U/R1_ql_loop/FINDINGS.md`, `R1T` = `U/R1_ql_loop/drafts/TOOL_CHANGE_SPECS.md`, `R1M` = `U/R1_ql_loop/drafts/MASTER_STEPS.md`, `R2F` = `U/R2_mac_setup/FINDINGS.md`, `R2A` = `U/R2_mac_setup/apply_safe.md`, `R3F` = `U/R3_hardness_md/FINDINGS.md`, `R4F` = `U/R4_teammate_repo/FINDINGS.md`, `R5F` = `U/R5_auto_issues/FINDINGS.md`, `R5I` = `U/R5_auto_issues/issues.csv`, `CR` = `MT/prompts/templates/_COMMON_RULES_v5.md`, `LR` = `MT/knowledge/LEVER_RULES_v3.md`, `KN` = `MT/knowledge/KNOWLEDGE.md`, `AP` = `MT/auto/AUTO_POLICY.md`, `DEC` = `MT/decisions.jsonl`, `MQ` = `H/scripts/master_queue.py`, `ANS` = `U/P1_plan/ANSWERS.md`, `PV4` = `T/master_chat_work/_dev_research/pipeline_v4/PLAN.md`.
Tags: **[CHECKED]** = read by P1 (23:44-23:48) or V1 (29 Oct 00:17-00:45). **[UNVERIFIED]** = R-session value not re-read.

## 1. Summary

1. Gate becomes tests < 85 AND rubric < 85 AND final < 40 (only the final number changes) in all 20 live lines listed in C1; design aims tighten to tests <= 60 and rubric <= 20 (predicted final <= 35).
2. Auto mode learns to see the usage limit (retry status, reset parse with seconds, budget rule, REPORT line + macOS notification) before anything else runs on it; this is the biggest loss found (R5: ~32 worker-hours lost overnight).
3. A QL loop is added: inbound home `master_chat_work/_ql/`, issue kind `ql`, intake events `ql_rerun` and `regrade` (named regrade exception, ANS Q1), tree sha on every run row and in the registry, P16 (report triage), P17 (zip hand-back), QL reply template, FP dossier.
4. Mac: 8 SAFE items applied by the master at once; pmset (B-N1) and Spotlight (B-N9) by Ayush any time; Docker memory/swap/GC (B-N2..N4) by Ayush after the upgrade from `U/V1_verify/DOCKER_STEPS.md`; DB vacuum (B-N5) by Ayush in Terminal.app at end of day; stale pids and old logs (B-N7, B-N8) by the master.
5. Levers: L2 held-out instances and L6 process criteria become PROVEN; held-out w5 tier >= 50% (N2) + paired probe band (N1) become the default shape for the next new build (one pilot); L3, L5, L7, L8, L9 WEAK; unbounded induction, effort caps and judge-only bands FALSE.
6. Learning loop: P15 v2 with a persistent angle log `knowledge/ANGLES.md`; each run proposes its own next version; master accepts or rejects each version; Ayush asks Aditya Jain and Anjali Kumari for their scripts.
7. Order: Batch 0 Mac SAFE, Batch 1 rules + gate + tool edits, Batch 2 auto limit/health fixes, then the 3 paused tasks resume; Batches 3-4 (QL templates, learning, auto cleanups) run beside them; Docker GUI steps after Batch 4.
8. Cost: about 7 worker sessions (2 auto-code, 1 metered report, 1-2 schema design+build, 1 learning, 1 QL template check) and 3 first paid runs (cold-chain, metered, schema), up to 2 more after read-out harden (cold-chain expected, metered if it misses) and 1 C4 pilot run, all inside the cap of 6/day; 0 paid runs for the upgrade itself.
9. Unchanged: Never list, Law-1, freeze after QC PASS, 1 valid run on frozen bytes before push, no re-run on the same bytes, tests < 85 and rubric < 85, cap of 6 paid runs/day, QL reruns ask Ayush each time.
10. Prediction honesty: cold-chain (predicted ~56) and metered (39.8-45.7) are frozen and get their run first, then a trajectory read-out; schema gets a DESIGN v2 that must show predicted final <= 35 inside 90% of the verifier limit, else it is parked.

## 2. Workstreams and items

Field order in every item: What / Files / New files / Who / Depends / Verify (command -> expected) / Rollback / Risk / Source.

### A. QL loop (goals 1-2)

**A1 issue.py: kind `ql`, time box rule, `--by`**
- What: add `ql` to KINDS and TASK_KINDS; `pushed` joins the `passed` set unless an open QL round exists; time box (8 sessions) does not count sessions of kind `ql`, and for `qc`/`fix`/`harden` on a pushed task with an open QL round; time box counter resets when the stage changes (R5-08); round caps and the stop-at-PASS / no-harden-after-PASS checks stay; override writes `"by"` from a new `--by` flag (default `master (auto)` in auto mode, `Ayush` when Ayush typed it), same-minute file gets `_2` suffix (R5-24). (ANS Q3 a.)
- Files: `MT/tools/issue.py:14-19` docstring, `:34` KINDS, `:36` TIME_BOX, `:37` TASK_KINDS, `:71` passed, `:89-90` time box, `:101` kind choices, `:118-122,137` file naming, `:136-142` decision row (`"who": "Ayush"` at :140) [CHECKED].
- Who: worker session E-code-1, Batch 1 (one-off prompt `MT/prompts/issued/_upgrade/<TS>_E1_tools.md`; not a template). The same session is continued for E1 in Batch 2 (`task_id`).
- Depends: none (Q3 answered a).
- Verify: `python3 MT/tools/issue.py --help | grep -c ql` -> `>=1`; temp tree: `mkdir -p /tmp/P1-a1/{tools,registry} && cp MT/tools/issue.py /tmp/P1-a1/tools/ && cp MT/board.json /tmp/P1-a1/ && cp MT/registry/tasks.json /tmp/P1-a1/registry/` (issue.py reads `HERE = tools/..`), then with a draft containing `<SHA>` and `name_session.py`: `python3 /tmp/P1-a1/tools/issue.py <draft> --slug sentinel-policy-recompute --kind ql --dry-run` -> prints `DRY RUN ok: would write ...` (not a time-box refusal; refusals are checked before the dry-run branch, issue.py:114-126); `grep -n '"who"' MT/tools/issue.py` -> no hit.
- Rollback: copy `issue.py` to `/tmp/P1-upgrade-bak/issue.py` before edit; copy back.
- Risk: loosens an Ayush-approved rule (24 Oct U1, R5F R5-08). Mitigation: round caps kept, `--by` logged on every override.
- Source: R1T T1, R5I R5-08 and R5-24; 23 override rows in R5's cited DEC ranges (62 time-box/cap overrides since 24 Oct) [CHECKED].

**A2 intake.py: gate 40, events `ql_rerun` and `regrade`, tree sha**
- What: constant `FINAL_GATE = 40`; `:104` becomes `gate = t < 85 and r < 85 and o < FINAL_GATE`; `:11` and `:106` texts say `final<40`; `--event` choices (`:124`) add `ql_rerun`, `regrade`; `regrade` rows are written `valid: false` unless `--ayush-ok "<verbatim words>"` is given (ANS Q1 a); every row gets `tree_sha` computed from `--bundle` (default `H/Tasks_INPUT/<job>`, intake.py:79) with the method that produced `8ca9c267f59b` and `583e77e1ae94` (non-trajectory tree sha, sentinel REGRADE_REPORT.md:18, :118); `gate_run` and `ql_rerun` are refused if the computed tree sha differs from the registry `tree_sha`, and refused with "registry tree_sha empty: set it at freeze (status.py set <slug> tree_sha=...)" when the field is empty. Without `--apply`, intake prints the would-be scores.jsonl row (incl. `valid`, `tree_sha`) and writes nothing.
- Files: `MT/tools/intake.py:11,:104,:106,:108-111,:124` [CHECKED].
- Who: E-code-1 worker, Batch 1.
- Depends: A3 (registry field), ANS Q1 a, Q9 a.
- Verify: `grep -n -e "o < 50" -e "overall<50" MT/tools/intake.py` -> no hit; `grep -n "FINAL_GATE = 40" MT/tools/intake.py` -> 1 hit; `python3 MT/tools/intake.py --job district-heat-flex-procurement | grep gate` -> `gate (tests<85, rubric<85, final<40): not met` (73.0/16.67/44.84; prints `MET` today); same for `--job sentinel-policy-recompute` (80.95/0.0/40.48 -> `not met`); `python3 MT/tools/intake.py --job sentinel-policy-recompute --event regrade` (no `--apply`) prints a row with `"valid": false`; worker confirms its tree sha function returns `8ca9c267f59b` on the frozen cold-chain bundle.
- Rollback: backup copy as A1.
- Risk: a row written before the change keeps its old `gate` meaning; scores.jsonl rows are history and are not rewritten.
- Source: R1T T2 [CHECKED intake.py lines; job values from `intake.py --job` read-only run, V1].

**A3 status.py: fields `tree_sha`, `ql_round`, `ql_last`**
- What: add three fields to FIELDS; no new stage (pushed stays pushed). Rule added to KN step "freeze" and AP:26: at every freeze the master runs `python3 MT/tools/status.py set <slug> tree_sha=<12 hex>`. Backfill in Batch 1 after A3: cold-chain `tree_sha=8ca9c267f59b` (REPORT.md:13); metered and schema get theirs at their freeze (F2, F3).
- Files: `MT/tools/status.py:22-23` [CHECKED]; KN freeze step; AP:26.
- Who: E-code-1 worker (code), master (rule text, backfill). Depends: none. Verify: `python3 MT/tools/status.py set cold-chain-backbone-quote zz=1` -> exits `bad field zz; allowed [...]` listing `tree_sha`, `ql_round`, `ql_last` and writes nothing (status.py has no `--help`; `--help` is read as a slug); after backfill `grep -c 8ca9c267f59b MT/registry/tasks.json` -> 1. Rollback: backup copy. Risk: low.
- Source: R1T T3.

**A4 one-slug repackage tool**
- What: `MT/tools/repackage_one.py --slug --run-dir --task-dir <frozen Tasks_INPUT>`; imports `package()` from `H/scripts/package_rfp_bundles.py` (`:216`, copies README/instruction/task.toml, environment/solution/tests, TRUTH.md, pass_summary.json and calls `_package_run` per run) and calls it with `out_root=/tmp/repack-<slug>-<TS>/staged` only (package() rmtree's `out_root/<task>`, :229-230, so it is never pointed at Output_RFP); refuses if `--task-dir` tree sha != registry `tree_sha`; backs up the old Output_RFP folder (incl. trajectories) to `/tmp/repack-<slug>-<TS>/old/`, writes a before/after sha listing, then copies the staged folder into Output_RFP. Never calls `main` (`:273-298`). The harness repo is not edited (ANS Q4 a).
- Files: new `MT/tools/repackage_one.py`. `H/scripts/package_rfp_bundles.py:15,:117,:152,:216-238` read only [CHECKED].
- Who: E-code-1 worker. Depends: A3. Verify: run on the sentinel run (R1 precedent, `T/master_chat_work/20261028_sentinel-policy-recompute/regrade_r13_188771e/REGRADE_REPORT.md:119`) with a fake Output_RFP root under `/tmp` -> staged listing matches the pushed Output_RFP folder except score files. Rollback: delete the new file. Risk: `task.path` in config.json may point to `/tmp` after a regrade (R1F gap 7); `--task-dir` overrides it.
- Source: R1T T4, R1F gap 7.

**A5 QL templates**
- What: move R1 drafts into templates: `P16_ql_report_triage_v1.md` (labels REAL / FALSE POSITIVE / PARTLY / OUT OF SCOPE, kit rule ids, carry-over), `P17_ql_handback_v1.md` (zip intake, INVENTORY.md, CHANGES.md, 4 paths), `QL_REPLY_TEMPLATE.md`. Fix inside them: gate text `final < 40`, `LEVER_RULES_v3.md` path unchanged, `_COMMON_RULES_v5.md`. Mark P7 v2 and P8 v2 as not used for QL work (they read the stale `_COMMON_RULES.md`, R1F line 9). P16 asks Ayush only when the QL asks to lower a score (ANS Q2 a).
- Files: new `MT/prompts/templates/P16_ql_report_triage_v1.md`, `P17_ql_handback_v1.md`, `QL_REPLY_TEMPLATE.md` (from `U/R1_ql_loop/drafts/`); `MT/prompts/templates/CHANGELOG.md` + 1 line: `- 2026-10-29 HH:MM QL loop (board 3d3a74a): P16 v1, P17 v1, QL_REPLY_TEMPLATE added from R1 086e1b4; P7 v2/P8 v2 retired for QL work.`
- Who: master copies; one checker session (Batch 3) runs `knowledge/PROMPT_CHECKLIST.md` on P16 and P17. Depends: Batch 1 (gate text). Verify: `grep -c "final < 40\|final<40" P16* P17*` >= 1 each; `grep -n "_COMMON_RULES.md" P16* P17*` -> no hit (only `_v5`); checklist session returns 0 fails. Rollback: delete the 3 files and the CHANGELOG line. Risk: reply template leaking lever/trap names (W1, CR:27) — the template forbids it and P16 has a W1 self-check (R1F).
- Source: `U/R1_ql_loop/drafts/*`, R1F Part A/B.

**A6 QL knowledge: inbound home, FP dossier, INDEX, master steps**
- What: create `T/master_chat_work/_ql/` (one folder per slug, `<TS>_report/` and `<TS>_zip/` inside); create `MT/knowledge/FP_DOSSIER.md` with header `| date | slug | finding | kit rule file:line | why false | source (QC round / QL round) |` (INDEX already lists it as ACTIVE but the file is missing [CHECKED]); copy R1M to `MT/knowledge/QL_MASTER_STEPS_v1.md`; INDEX lines for `_ql/`, P16, P17, QL_MASTER_STEPS_v1, FP_DOSSIER status fixed. QC_RULINGS row only after the QL agrees a finding was false.
- Who: master. Depends: A5. Verify: `ls T/master_chat_work/_ql`; `head -3 MT/knowledge/FP_DOSSIER.md` shows the header; `grep -c "P16\|P17\|QL_MASTER_STEPS\|_ql/" MT/knowledge/INDEX.md` >= 4. Rollback: remove the new files and INDEX lines. Risk: low.
- Source: R1F Part A, R1M A1-A10/B1-B6.

**A7 Regrade exception text (IN: ANS Q1 a)**
- What: named exception in every regrade rule: "Regrade counts as push evidence only when the edit touches judge files only (no tests/, no instruction, no environment), the run was valid, Ayush wrote OK for this regrade (verbatim in decisions.jsonl), and the regraded run is repackaged with A4. Otherwise diagnostic only, never packaged."
- Files: `CR:65-66`, `KN:119`, `LR:215`, `PV4:12` (decision 5), `PV4:59`, `PV4:99` [CHECKED]. Who: master in Batch 1. Verify: `grep -n "regrade" CR KN LR PV4` shows the exception text at every listed line. Rollback: snapshot restore (C0; PV4 backup to `/tmp/P1-upgrade-bak/PLAN.md`). Risk: Ayush's sentinel push (DEC:390-400) is now covered by the named exception.
- Source: R1F gap 1, ANS Q1.

QL flows (Part A report pasted, Part B zip) are run exactly as R1M A1-A10 and B1-B6, with these fixed decisions: gate for a QL "lower the score" round is final < 40; every QL paid run is asked of Ayush first and is outside the cap of 6 (Ayush 28 Oct; ANS Q5 a: a zip that changes tests/ or judge files voids the old run and needs a new paid run, LR:210 [CHECKED]); a zip without trajectories asked to "degrade" = blind harden: 3 x P13 v2 blind reads, then P9 v4 with blind results as the evidence, P11 v3 full QC, freeze, ask, 1 run (R1F Part B).

### B. Mac / Docker / VS Code / opencode (goal 3)

Machine-state numbers are from R2 except these [CHECKED by V1, read-only]: auto.py:597 `--port 0`; Docker Desktop 4.95.0, settings-store.json MemoryMiB 12288, no swap key (default 1 GiB); `~/.docker/daemon.json` = `{"builder": {"gc": {"defaultKeepStorage": "20GB", "enabled": true}}, "experimental": false}`; opencode.db 4.04 GiB; pid 15335 alive (`opencode --port 53366 ... -s ses_ea5ff5f97ffe6WB1VzP4StPOw6`), pid 23171 gone. Every SAFE item has its backup/check/rollback in `R2A`; the master follows `R2A` as written.

SAFE (master applies right after "proceed"; no sudo, no restart; Batch 0):

| id | What | File | Verify (from R2A) | Rollback |
|---|---|---|---|---|
| B-S1 | `files.watcherExclude` for jobs, QC copies, Anubis_Tasks_Samples, anubis-stage-1, master_chat_work, converted backups, `_tmp_master_tasks_*`, `.git/objects`, node_modules | VS Code user settings.json | JSON parses (`python3 -m json.tool`) | `.bak-20261028-r2` copy |
| B-S2 | `search.exclude` same list | same | same | same |
| B-S3 | `git.autoRepositoryDetection: openEditors`, `git.autofetch: false` | same | same | same |
| B-S4 | terminal GPU acceleration on, scrollback 5000 | same | same | same |
| B-S5 | telemetry off, `extensions.autoUpdate: false`, `update.mode: manual` | same | same | same |
| B-S6 | pin `@tarquinen/opencode-dcp@3.2.0`, `oh-my-openagent@5.1.33` | `~/.config/opencode/opencode.jsonc`, `tui.json` | JSON(C) parses; effect at next opencode start only | `.bak` copy |
| B-S7 | `caffeinate -i -s -w <master pid> &` during interactive blocks (AC only) | none (process) | `pmset -g assertions \| grep caffeinate` shows it | kill the pid |
| B-S8 | `typeset -U path PATH` as first line | `~/.zshrc` | `zsh -i -c 'echo $PATH' \| tr ':' '\n' \| sort \| uniq -d` -> empty | `.bak` copy |

Sources: R2F SAFE list, R2A sections `## S1-S5` (line 5), `## S6` (33), `## S7` (38), `## S8` (44) [CHECKED].
Risk: B-S6 pin blocks plugin fixes until unpinned (accepted; R2 found @latest drift). B-S1/S2 hide `master_chat_work` from VS Code search — the master uses grep/rg, so no loss.
Note: load the customize-opencode skill when editing `~/.config/opencode/`.

Ayush-approved items (ANS Q6, Q7, Q8):

| id | What | Who | When | Rollback |
|---|---|---|---|---|
| B-N1 | `sudo pmset -b sleep 0 displaysleep 10 powermode 0` + habit: charger in, lid open during auto runs (ANS Q7 a) | Ayush (sudo), steps in `DOCKER_STEPS.md` | any time | `sudo pmset -b sleep 1 displaysleep 2 powermode 1` |
| B-N2 | Docker memory 12 -> 16 GiB | Ayush (Docker Desktop GUI, Apply & restart) from `DOCKER_STEPS.md` | after the upgrade session (after Batch 4), no container running (ANS Q6) | GUI back to 12 |
| B-N3 | Docker swap 1 -> 2 GiB | Ayush GUI | with N2 | GUI back to 1 |
| B-N4 | daemon.json builder GC policy: keep 10 GB of cache unused for up to 7 days, cap 20 GB total (current keys `reservedSpace`/`keepDuration`; exact JSON in `DOCKER_STEPS.md`) | Ayush (Docker Engine tab, Apply & restart) | with N2 (one restart) | paste the old JSON back |
| B-N5 | backup + `VACUUM` of `~/.local/share/opencode/opencode.db` (4.04 GiB) with all opencode quit | Ayush in Terminal.app (the master is itself an opencode session and cannot stop all opencode) from the 3-line list in `DOCKER_STEPS.md` | end of day, no sessions | restore the backup copy |
| B-N6 | auto.py health: 15 s timeout + 2 strikes | merged into E2 (R5-07) | — | — |
| B-N7 | close stale opencode servers | master | re-check `ps -o pid,etime,command -p 15335 23171`; 23171 is already gone; 15335 (session `ses_ea5ff5f97ffe6WB1VzP4StPOw6`) only after Ayush confirms it is not his open window | none (process) |
| B-N8 | delete `/tmp/opencode-logs` files > 7 days (`find /tmp/opencode-logs -type f -mtime +7 -delete`) | master | any time | none |
| B-N9 | Spotlight privacy: add `~/Desktop/Terminal Bench` | Ayush GUI, steps in `DOCKER_STEPS.md` | any time | remove from list |

Also listed by R2 for Ayush's GUI: Battery > Low Power Mode Never; "Prevent automatic sleeping on power adapter when display is off" (R2F section 4). Not done: files.autoSave, switching Docker engine, raising launchctl maxfiles. Docker tuning stays on the current Docker Desktop.
Until B-N2 is applied: never run the metered harness (8 GiB) beside another Docker-heavy job (R2F:53: metered + 1 heavy + harness needs ~13-14 GiB).

### C. Hardness levers and gate < 40 (goal 5, R3, R4)

**C0 How rules files are versioned (applies to C1-C3, A7, D3)**
- Decision (ANS Q12 a): first freeze the old bytes: copy `LR` -> `MT/knowledge/LEVER_RULES_v3.6_snapshot.md`, `KN` -> `MT/knowledge/KNOWLEDGE_v3.6_snapshot.md`, `CR` -> `MT/prompts/templates/_COMMON_RULES_v5_v3.6_snapshot.md`, `PV4` -> `T/master_chat_work/_dev_research/pipeline_v4/PLAN_v3.6_snapshot.md`; record their sha256 in the master LOG; INDEX lines with status SNAPSHOT. Then edit in place as v3.7 (v3.3-v3.6 precedent: LR:1 header, CHANGELOG:48 edited 9 files in place [CHECKED]). Reason: 12 templates (+ CHANGELOG = 13 files) reference `LEVER_RULES_v3.md` and 3 templates (+ CHANGELOG = 4 files) reference `_COMMON_RULES_v5.md` [CHECKED by `grep -l`]; a new name would force 15 template edits.

**C1 Gate final < 40 everywhere**
- Live lines today (V1 grep 00:31 IST, 20 lines in 11 files) [CHECKED], each rewritten to 40 and tagged `[v3.7 Ayush 28 Oct "Target <40 now"]`:
  - `MT/tools/intake.py:11, :104, :106` (A2).
  - `CR:49` (v3.6 aims bracket -> C2), `CR:61` "tests < 85 AND rubric < 85 AND final reward < 50 ... so final < 50 needs rubric < 100 - tests" -> "tests < 85 AND rubric < 85 AND final reward < 40 on 1 valid run (v3.7, Ayush 28 Oct 'Target <40 now'). Final = (tests + rubric)/2, so final < 40 needs rubric < 80 - tests; design for tests <= 60 and rubric <= 20."
  - `LR:1` header (add v3.7 to the version list and gate), `LR:89` (-> C2), `LR:210` (same sentence as CR:61).
  - `KN:118` step 4: "final >= 50" branches -> "final >= 40".
  - `MT/knowledge/INDEX.md:6` gate note.
  - `MT/prompts/templates/P2_build_v5.md:66`, `P9_harden_from_results_v4.md:67` (v3.6 bracket -> v3.7 aims).
  - `AP:28` run row.
  - `MT/GOALS.md:18` (G11) and `:34`.
  - `MT/state.json:126` `test_phase_gate` (state.json:70 is a historic lesson; leave).
  - `MT/tools/lever_dose.md:3`.
  - `PV4:28, :38, :39, :56`.
- Who: master (text) + E-code-1 (intake.py). Verify: `cd T && grep -rn -e "final < 50" -e "final<50" -e "overall < 50" -e "overall<50" -e "final >= 50" -e "o < 50" master_chat_tasks/tools master_chat_tasks/knowledge master_chat_tasks/prompts/templates master_chat_tasks/auto master_chat_tasks/GOALS.md master_chat_tasks/state.json master_chat_work/_dev_research/pipeline_v4/PLAN.md | grep -v -e "_snapshot.md" -e "CHANGELOG.md" -e "/auto/runs/" -e "/auto/plans/" | grep -v "v3.7"` -> empty (auto/runs and auto/plans are history; any kept history bracket must carry `v3.7` on the same line). Rollback: snapshots + intake.py backup. Risk: issued prompts in `prompts/issued/` keep 50 — master re-issues paused-task prompts after Batch 1 (F).
- Tests < 85 and rubric < 85 kept (R3F:136-145; Ayush keep). Settled.

**C2 Design aims and DESIGN READY bar (v3.7)**
- `CR:49` / `LR:89` [CHECKED] current: "plain first-write and all-but-one program aim at tests <= 75; each of 3 fresh blind reads tests <= 80; judge probe mid 15-20; auto go at DESIGN READY when kill table passes (each solver loses >= 15% of lever points ...)".
- v3.7 text (ANS Q9 a): "[v3.7 28 Oct, gate final < 40] Plain first-write and all-but-one programs aim at tests <= 60. Blind bar: each of the 3 fresh blind reads scores tests <= 65 (none above 70). Judge: probe band, predicted probe mid <= 20. DESIGN READY needs, in DESIGN.md: (a) predicted final = (predicted first-write tests + predicted judge mid)/2 <= 35 (5 points margin for the final spread, LR:215 same-bytes spread); (b) lever share >= 40% of positive test weight (if the lever is fully lost and all else passes, tests <= 60), with the held-out w5 tier >= 50% when the N2 shape is used; (c) blind ceiling: no blind program above tests 65; (d) verifier worst case <= 90% of the stated verifier limit; (e) the kill table rule (>= 15% lever loss by WRONG output) unchanged. Overnight go at DESIGN READY unchanged."
- Evidence: final < 40 needs tests + rubric < 80; our 10 valid gate runs mean tests 78.7, rubric 23.5, 1 below 40 (R3F:137; V1 re-ran `s08_ours.py` -> same) [CHECKED].
- Who: master text, Batch 1. Verify: `grep -n "v3.7" CR LR` shows the new text in both. Rollback: snapshots. Risk: fewer designs reach DESIGN READY (intended); verifier time grows with more hidden worlds (F3).

**C3 Lever status table v3.7 (new section in LR, after the v3.6 section; ANS Q10 a)**

| Lever | v3.7 status | Evidence | How to use |
|---|---|---|---|
| L2 held-out instances (Shape D, 1C) | PROVEN | shipped 62% vs held-out 42% pass, at w5 43% vs 23%; within-author r_tests -0.43 (R3F:98-109); HardExpert hidden share 0.68 vs 0.16-0.18, hidden pass 0.01 (R4F contrast) | default test lever; G3/G5, 0b, W5 BRANCH_FIRE |
| L6 process criteria / probe band (J2, P-a..P-h) | PROVEN | verify criteria 52% vs read 24%; our gate runs mean rubric 23.5 (R3F) | every judge; mid <= 20 |
| N2 held-out w5 tier >= 50% of positive test weight | PROMISING (pilot) | 8 tasks mean 34.8, 5 < 40; cur90 9 tasks mean 32.8 (R3F); R4 hidden share >= 0.5 median 35.7 vs 56.5 | default shape for the next new build (C4) |
| N1 pair channels (held-out w5 tier + probe band) | PROMISING (pilot) | halves anti-correlated r -0.40, -0.32 within author (R3F) | same pilot as N2 |
| L1 / LC2 weight on w5 (shipped w1, hidden w5) | PROMISING, amplifier only | within-task 73/83 but r weakens within author (R3F); R4 top1 share no signal | only on a held-out core via TS-20; never reweight after a run (KN:113) |
| L4 exact published contract | PROMISING, multiplier | R3F | with G1 + CL-4 |
| LC1 bounded induction (finite stated domain, unique fit per hidden instance) | PROMISING (second pilot) | 59417607, aa314fee (R4 cards) | legal only if the domain is stated and EVIDENCE_MAP lists it (Never 6); one unlabelled witness max (Never 11) |
| LC3 counterfactual what-if figures in judge (J11) | PROMISING | 59417607 7/8 wrong, aa314fee 8/8 (R4F) | questions stated in instruction, 4-8 what-ifs; headline figures leak (LEAK_LIBRARY:12) |
| LC5 per-field-class authority order | PROMISING (needs pilot) | df8f123b only (R4F) | each class order written once (Never 8) |
| LC6 hazard-slice tests (T1) | PROMISING | 80202e15, 9f5486ac (R4F) | avoid a global HELD gate |
| L3 interlocking inputs / LC4 never-healing state | WEAK | regex-only signal; our L4 multi-doc leaked (CR-5, 1C) (R3F); R4 LC4 from 2 tasks | only inside a held-out tier |
| L5 trap tiers | WEAK | 92-96% from 6-10 tasks; habit levers leaked (R3F) | hidden-only fixtures (S6) |
| L7 honesty negatives as hardness | WEAK (keep as integrity) | 5.4% of judge points (R3F) | keep J3a-c, do not budget points |
| L8 determinism, L9 reward geometry, N3 small judge total | WEAK | 0.9% / structural (R3F) | G6 minimum only |
| Unbounded induction (forms/meanings unstated) | FALSE | flagged 5b2b0901, 8defd7be, d49e259f (R4 genuineness.md); breaks Never 6 | never |
| Instructed effort caps (e.g. "stop at 1500 s") | FALSE | 5b2b0901 instruction.md:36 (R4F); agents used median 23% of budget | never |
| Judge-only band (tests near 100, judge negatives) | FALSE | 725e575c tests 96.55, judge -25 (R4F); blocked by tests < 85 | never |
| Weight concentration (top-1 check share) | FALSE as a standalone lever | R4 A1 top1 ~0.05 no signal | amplifier only via L1 |

- Stats [CHECKED by V1]: R3 `s05_confounds_recipe.py` (L2, N1, N2, cur90) and `s08_ours.py`, R4 `contrast.py` (byte-identical output) re-run in `/tmp/V1-verify-5125258/`; all numbers above match.
- R3's 5 wrong doc claims (C10, C24, C51, C58, C60 in `U/R3_hardness_md/claims.csv`) are not lever rules; they go to the QL reply (C5).
- R3 and R4 disagree on interlocking (R3 WEAK, R4 LC4 candidate): WEAK, because R4's support is 2 tasks and our own L4 multi-doc build leaked; LC4 can be tried only inside the N2 pilot's held-out tier.

**C4 Pilot of the default shape (N1 + N2; ANS Q11 a)**
- What: the next new task built after Batch 1 uses: held-out w5 tier >= 50% of positive test weight with >= 6 hidden corpora (G3 Shape D), plus a probe-band judge mid <= 20. Induction (LC1) is a later, second pilot. Proof bar (R3F N1/N2): frozen QC-passed bytes, 1 valid run with tests <= 60 and rubric <= 20, and 2 of 3 blind reads lose >= 40% of positive test weight on the held-out tier while passing shipped checks.
- Files: none beyond C2/C3 text; DESIGN.md of that task. Who: P2 v5 build worker (normal pipeline). Depends: Batch 1. Verify: DESIGN.md shows (a)-(e) of C2; after the run, `intake.py --event gate_run` row. Cost: 1 paid run (inside cap). Risk: n=1; promote N1/N2 to PROVEN only after 2 pilots pass.

**C5 Reply to the QL on hardness.md (ANS Q13 a)**
- What: one full Markdown reply for the QL: claim list with verdict (41 confirmed, 18 partly, 5 wrong, 4 untestable [CHECKED in claims.csv]), the 5 wrong claims with evidence, R3's 4 QL questions (opus-5-5 runs in the sample; theme regex script; L6 counts; 59417607 hidden count and recipe claim), the 2 proven levers and 3 new candidates in plain terms. No names of our tasks' traps (W1, CR:27); our 4 tasks in the doc are named only by their sample id.
- New file: `T/master_chat_work/_ql/hardness_md/REPLY_hardness_v1.md`. Who: master (writing) from `U/R3_hardness_md/claims.csv` + R3F. Depends: A6 (folder). Verify: `grep -ci "trap\|lever_rules\|LR:" REPLY_hardness_v1.md` reviewed by hand; Ayush reads before sending. Risk: doc tasks 42e79476/b47fd5f7/8fbe0e42/b5c7b14c have registry vs Final_Delivery score differences (R3F) — reply says "scores differ, bytes not compared".

### D. Learning loop with angle log (goal 4)

**D1 Angle log**
- What: `U/R4_teammate_repo/ANGLES.md` (A1-A12 tried with strength, U1-U12 untried ranked) becomes the master copy `MT/knowledge/ANGLES.md`; INDEX line "ANGLES.md | before any P15 run | ACTIVE, master merges each P15 OUT/ANGLES.md". Sessions never write it (P15 v2 draft line 52 [CHECKED]); master merges each run's `OUT/ANGLES.md` after reading it.
- Who: master. Verify: `diff U/R4_teammate_repo/ANGLES.md MT/knowledge/ANGLES.md` -> empty at first copy. Rollback: delete. Risk: low.

**D2 P15 v2 and P14 v2 templates**
- What: copy `U/R4_teammate_repo/drafts/P15_research_angle_v2.md` and `P14_task_analysis_v2.md` to `MT/prompts/templates/`; set `[[ANGLES_FILE]]` default to `master_chat_tasks/knowledge/ANGLES.md` (draft line 12 [CHECKED]); CHANGELOG lines: the one proposed at P15 draft line 66 [CHECKED] and `- 2026-10-29 HH:MM P14 v2 (board 3d3a74a): score-convention check, no-message genuineness path, identifiability of withheld facts, instructed caps, channel split 50/P, weight geometry, judge composition (from R4 1d26a6e).`
- Who: master copies; checker session (same as A5 check, Batch 3) runs PROMPT_CHECKLIST on both. Verify: checklist 0 fails; `grep -n "\[\[ANGLES_FILE\]\]" P15_research_angle_v2.md` present. Rollback: delete files + CHANGELOG lines (v1 files untouched).

**D3 Self-improvement rule (ANS Q15 a)**
- What: each P15 run ends with `## Proposed prompt changes` and a CHANGELOG line (draft lines 58-59 [CHECKED]). Master reads each proposal, accepts or rejects each numbered edit with one reason in `MT/knowledge/ANGLES.md` ("Prompt versions" table: version, date, accepted edits, rejected edits, reason), then writes P15 v(N+1) as a new file; old versions stay. A version is accepted only if its run produced >= 1 angle rated S or M on a within-contributor contrast. Two runs in a row with only W/N angles -> master stops the loop and tells Ayush.
- Who: master. Depends: D1, D2. Verify: after the first run, `MT/knowledge/ANGLES.md` has new rows and a "Prompt versions" row.

**D4 First learning run**
- What: 1 worker session from P15 v2 on the top 2 untried angles (U1 self-test anatomy, U2 judge negative design; R4 ANGLES.md ranking), corpus `anubis-stage-1` + our Final_Delivery tasks; no paid runs, no Docker.
- Who: worker session (P15 v2). Depends: D2, Batch 2. Cost: 1 session. Verify: `OUT/result_<sha>.json` parses; REPLY.md has `## Proposed prompt changes`.

**D5 Teammate model cards**
- What: R4 cards (9 genuine models, 4 flagged; `U/R4_teammate_repo/cards/`, `genuineness.md`) copied to `MT/knowledge/TEAMMATE_MODELS_v1.md` (summary table + links to the cards kept in U), INDEX line "read when designing a new task". 725e575c listed as "not a hardness model" (tests 96.55).
- Who: master. Verify: INDEX line present. Risk: R4's genuineness labels are [UNVERIFIED]; the card file says so in its header.

**D6 Teammate scripts (ANS Q14 a)** (new in v2)
- What: Ayush asks Aditya Jain and Anjali Kumari for the scripts/notes behind their Hard/Expert tasks; when received, master stores them under `T/master_chat_work/_teammates/<name>/` and adds a row to `MT/knowledge/ANGLES.md` as an untried angle source. D4 does not wait for them.
- Who: Ayush (ask), master (store). Verify: none until received. Risk: none.

### E. Auto-mode fixes (R5)

Lines CHECKED by P1/V1: auto.py:65-70, :73, :79-80, :83, :87, :93-121, :271-275, :299-301, :403-430, :445-466, :566-577, :597, :693, :909-954, :970-975, :1038, :1174-1180, :1237-1259, :1294-1338, :1367-1376, :1391-1397, :1420; MQ:75, :230-235, :595-596, :616-625; package_rfp_bundles.py:113; AP:15, :26, :28-30, :37, :46, :47, :54. Each batch is one worker session with a one-off prompt in `MT/prompts/issued/_upgrade/`, code backups in `/tmp/P1-upgrade-bak/` (MQ also beside the earlier ones in `H/.master-queue/backup-<TS>-p1/`), and must end with `python3 -m unittest discover -s MT/auto/tests` green plus the new tests named below.

**E1 Limit detection and budget (R5-01, R5-02 a-c, R5-03, R5-13)** — Batch 2, worker E-code-1 continued from Batch 1 (A1-A4) with `task_id`
- What: `retry_ids` next to `busy_ids` (auto.py:299-301: `retry` status counted separately, not as busy); `LIMIT` event, `limit_since` in state; `cmd_spawn` and `cmd_harness` refuse while LIMIT; MQ pause; on LIMIT: REPORT line + macOS notification (`osascript -e 'display notification ...'`, ANS Q17 a); `LIMIT CLEARED` after 2 clean polls. RESET_IN_RE (auto.py:87) gains seconds (`s|sec|second`); resume = parsed reset + 5 min, keyed by task, not by reason (auto.py:1237-1259, MQ:623). 401 -> `AUTH` event, not limit (MQ:75, wrapper exit 8). Budget rule in code (ANS Q16 a): harness refused when LIMIT is set or > 2 workers busy at launch; while a paid run is RUNNING, max 3 busy workers (else MAX_BUSY_WORKERS 5).
- Verify: new unit test in `MT/auto/tests/test_auto.py` with a fake opencode server (stdlib `http.server` in a thread returning `retry` status; R5's `fake_oc.py` was not kept) -> LIMIT event within 2 polls, and a fake 401 -> `AUTH`; reset check: `mkdir -p /tmp/R5-auto-1 && cp MT/auto/auto.py /tmp/R5-auto-1/auto_copy.py && python3 U/R5_auto_issues/exp1.py` -> the `... soonest reset in 4698s` case at 17:54:49 gives `>= 19:13:07` (exp1.py hard-codes `/tmp/R5-auto-1/auto_copy.py`, which R5 deleted).
- Not in E1 (ANS Q18 a): R5-02(d) killing a running paid run on the first `accounts exhausted` — log-only; kill only after the log has shown the line on a real run once and Ayush OKs it.
- Risk: a false LIMIT blocks a night; mitigated by 2-poll clear and the REPORT line.

**E2 Watcher reliability (R5-04, R5-05, R5-06, R5-07 = R2 N6)** — Batch 2, worker E-code-2 (after E1 tests pass; same files, so serial)
- What: REPORT line + `osascript` notice when events stay undelivered (auto.py:1294-1338); stall watchdog `STALL_MIN = 20` (no new message 20 min while busy) beside LONG_BUSY_H 6 (auto.py:70, 1174-1180); `doom` class (ANS Q19 a): keep the deny (auto.py:119), one auto "continue" with a poll rule (only if the counter is rising), then BLOCKED; health check 15 s timeout + 2 strikes and an "answering again" event that clears the flag (auto.py:271-275, 1391-1397, cmd_resume :909-954 restart at :935).
- Verify: unit tests for stall and 2-strike health with mocked time; `python3 MT/auto/auto.py status` runs.

**E3 Stop and final report (R5-09, R5-11, R5-25)** — Batch 4
- What (ANS Q20 a): FINAL only after the last worker result and harness exit (auto.py:1367-1376, 1420); `auto.py stop --now` (cmd_stop 970-975 only writes the stop file today) that stops watcher, caffeinate, queue in one step; REPORT writes "Still running at stop" instead of empty sections.

**E4 Decisions file (R5-23)** — Batch 4, with A1's `--by`
- What: new `MT/tools/decide.py` that appends one validated row (`ist`, `by`, `slug`, `what`, `words`) to `MT/decisions.jsonl`; AP:54 field name `by` kept, issue.py switched to `by` (A1).

**E5 Policy and plan template (R5-10, R5-19, R5-22, R5-20)** — Batch 4, master text + worker code
- What: AP:46 "4 workers" -> "5 workers (Ayush 27 Oct 22:20; auto.py:65)"; AP:47 Docker cap: "2 heavy Docker workers" becomes enforced by MAX_HARNESS/MAX_BUILDS or reworded to "advice"; new `## Budget` section in AP (paid runs max 6/day, each only with no LIMIT and <= 2 busy workers; max 3 busy workers while a paid run runs; fresh window -> paid run first; on LIMIT hold, pause queue, resume at parsed reset + 5 min, REPORT line + notification; master counts as a worker; metered harness never beside another Docker-heavy job until B-N2); `--wind-down` flag on `auto.py harness` (AP:15) for runs added after AUTO STOP (within the cap); last-spawn cutoff 20 min before AUTO STOP; wind-down hard cap does not kill busy sessions mid-step (R5-20). `MT/auto/PLAN_TEMPLATE.md` (14 lines) gains fields `Paid runs:`, `Workers/harness/Docker:`, `Budget:`, `Wind-down:`, `Last spawn:`.
- Verify: `grep -n "Budget\|Wind-down\|Last spawn" MT/auto/AUTO_POLICY.md MT/auto/PLAN_TEMPLATE.md` -> hits in both.

**E6 LOW cleanups (R5-12, 14, 15, 16, 17, 21, 24 (in A1), 26)** — Batch 4, one worker
- What: MQ does not count workers' oracle/nop `harbor run` (MQ:230-235, 595-596); `cancel` clears PAUSED (R5-14; state paused True, queue 0 per P1's `auto.py status`); board rows closed via `board.py set` (auto.py 566-577, 693); `MT/tools/registry_check.py` for type drift; plan step at start minute today, not tomorrow (auto.py:403-430); wrapper exit non-zero on errored run (package_rfp_bundles.py:113 traceback); regression test that WORKER_PERMISSION allows harbor oracle/nop (auto.py:93-121). R5-18 zsh lesson goes to KN lessons, not code.

### F. Resuming the 3 paused tasks under gate < 40

Resume table: `MT/auto/runs/20261028T1553_evening/REPORT.md:13-15` [CHECKED]. Resume point: after G2. All 3 restart from new prompts issued after Batch 1 (gate 40 text). Rules carried (REPORT.md:17): miss -> harden once -> 1 new run; second miss -> Needs Ayush.

**F1 cold-chain-backbone-quote** (frozen tree 8ca9c267f59b = QC v4 copy 78b8d5b, MINOR G05-M1 PL note; REPORT.md:13)
- Prediction under the frozen bytes: lever 24/108 = 22.2%, first-write plain 84/108 = 77.8 tests, judge mid 34-40% (`T/master_chat_work/20261027_cold-chain-backbone-quote/harden_w1_678c839/HARDEN_REPORT.md:20, :29, :50`); later fixes left tests/ byte-identical (`T/master_chat_work/20261028_cold-chain-backbone-quote/p12_fix_v3_b0aca9b/RECHECK_FIX.md:107-112`) [CHECKED] -> predicted final ≈ (77.8 + 34)/2 ≈ 56: misses < 40.
- Next (ANS Q22 a): registry `tree_sha=8ca9c267f59b` (A3 backfill) -> 1 paid run on 8ca9c267f59b (the 17:41 run was invalid without trajectory, so this is not a same-bytes re-run of a valid run, REPORT.md:13) -> expected miss -> trajectory read-out -> P9 v4 harden to the C2 bar (tests <= 60, mid <= 20) -> P11 v3 recheck -> freeze -> 1 run. Never 10 (CR:29) and pipeline_v4 decision 1 allow change after QC PASS only this way.
- Cost: 1 paid run now, 1 later.

**F2 metered-usage-rating-pipeline** (QC v1 Step 10 done: oracle 1.0 x3, nop 0, stub 0, owner 1.0; REPORT.md:14)
- Prediction: `T/master_chat_work/20261027_metered-usage-rating-pipeline/harden_g36_361674d/DESIGN.md:114` tests 60.7-72.5, rubric 18.9, final 39.8-45.7 [CHECKED] -> most of the band misses < 40.
- Next (ANS Q23 a; this answer is the paid-run OK — REPORT.md:22 was the open question): short session finishes QC v1 Step 10 write-up + verdict + result json from the kept jobs in `T/master_chat_work/20261028_metered-usage-rating-pipeline/qc_v1_step10_ac12c0b/` (no rerun) -> PASS: freeze, `status.py set ... tree_sha=` -> 1 paid run, with no other Docker-heavy job until B-N2 (R2F:53) -> gate 40; miss -> trajectory read-out -> harden once -> 1 new run; second miss -> Needs Ayush. FAIL: P12 v4 fix.
- Cost: 1 session, 1 paid run (+1 if it misses).

**F3 schema-migration-plan-repair** (harden stage, Tasks_INPUT tree 308399b4016e = a6 bytes; DESIGN in `T/master_chat_work/20261028_schema-migration-plan-repair/harden_g36_a4f790c/`; REPORT.md:15)
- The kept DESIGN.md predicts final 41.4-46.0 (:84) with 34 worlds (L = 170, share 36.9%, a6-like tests 63.12; :36-39) and no judge change (:96) [CHECKED]: fails the bar.
- Arithmetic [CHECKED by V1 against DESIGN.md:27, :98-99; 2,700 s limit, 90% = 2,430 s]: tests alone needs L >= 280 (56 worlds) -> 2,880 s > 2,700 s, not feasible. 45 worlds -> tests 56.4, final ≈ 38.2 at mid 20, 2,550 s (94%); 42 worlds -> tests 58.1, final ≈ 39.0, 2,460 s (91%); 41 worlds -> tests 58.7, final ≈ 39.3, 2,430 s (90.0%). None of these meets C2 (a) predicted final <= 35, and 42-45 worlds break C2 (d).
- Next (ANS Q24 a, under the C2 bar adopted in Q9/Q10): P9 v4 harden session restarts at the DESIGN step (old DESIGN is input). DESIGN v2 is DESIGN READY only if it shows predicted final <= 35 AND verifier worst case <= 2,430 s. Example that fits: probe-band judge mid <= 15 and ~48 held-out worlds with per-world worst case <= 25 s (18 x 60 + 48 x 25 + 120 = 2,400 s; tests 291/531 = 54.8; final ≈ 34.9). If the design cannot show both, it is a miss -> park the task and tell Ayush (Q24 "a miss -> park"). If READY: build -> Phase 3 (a6 repo <= 60) -> P11 v3 recheck vs v11 copy 361ee0a -> freeze, `tree_sha` -> attempt 7 (time box issue.py:85-90).
- Cost: 1-2 sessions, 1 paid run (0 if parked).

## 3. Per-item fields

Written inside each item of section 2 (What / Files / New files / Who / Depends / Verify / Rollback / Risk / Source). Item count: A1-A7, B-S1..S8, B-N1..N9, C0-C5, D1-D6, E1-E6, F1-F3 = 45.

## 4. Lever rules update (v3.7 delta, summary)

- PROVEN: L2 held-out instances; L6 process criteria / probe band.
- PROMISING: N2 held-out w5 >= 50%, N1 pair channels (one pilot, C4), L1/LC2 w5 weight (amplifier), L4 exact contract (multiplier), LC1 bounded induction (second pilot), LC3 counterfactual what-ifs, LC5 authority order, LC6 hazard slices.
- WEAK: L3/LC4 interlocking, L5 trap tiers, L7 honesty negatives as hardness, L8 determinism, L9 reward geometry, N3 small judge total.
- FALSE: unbounded induction, instructed effort caps, judge-only bands, weight concentration as a standalone lever.
- Gate: `intake.py:104` `gate = t < 85 and r < 85 and o < 50` -> `gate = t < 85 and r < 85 and o < FINAL_GATE` (`FINAL_GATE = 40`); all 20 live lines in C1.
- DESIGN READY: predicted final <= 35, lever share >= 40% of positive test weight (held-out w5 tier >= 50% in the N2 shape), blind ceiling tests <= 65 (none > 70), verifier worst case <= 90% of limit, kill table unchanged (C2).
- Promotion rule: PROMISING -> PROVEN needs 2 of our tasks meeting the proof bar on frozen bytes.

## 5. Order and batches

| Batch | Items | Can run together | Evidence gate before the next batch |
|---|---|---|---|
| 0 | (done: Ayush answers 28 Oct; V1 verify) B-S1..S8 | yes | G0: R2A checks for S1-S8 all pass; Ayush "proceed" logged in decisions.jsonl |
| 1 | C0 snapshots, C1 gate text, C2 aims, C3 lever table, A7; A1-A4 code (worker E-code-1); A3 backfill of cold-chain tree_sha | text items by master in one sitting; code by worker | G1: the C1 verify grep prints nothing; `intake.py --job district-heat-flex-procurement \| grep gate` -> `final<40): not met`; `status.py set cold-chain-backbone-quote zz=1` lists the 3 new fields; snapshot sha256 lines in LOG |
| 2 | E1 (E-code-1 continued), then E2 (E-code-2) | serial (same files: auto.py, MQ) | G2: `python3 -m unittest discover -s MT/auto/tests` green incl. fake-server LIMIT/AUTH tests; exp1 reset case `>= 19:13:07`; `auto.py status` runs; one real auto run of `MT/auto/smoketest/PLAN.md` (2 tiny worker prompts t1/t2; uses subscription, no paid run; auto.py has no dry mode) starts, shows events, and `auto.py stop` ends it clean |
| — | **RESUME POINT: F2 metered (report session + run), F1 cold-chain (run), F3 schema (DESIGN v2)** under a new PLAN with the E5 Budget fields filled by hand | F1/F2 runs obey cap 6 and Budget (3 busy workers while a run; metered alone among Docker-heavy jobs) | each run: `intake.py --event gate_run --apply` row with tree_sha matching registry |
| 3 | A5, A6, C5, D1, D2, D5, D6; checker session for P16/P17/P14 v2/P15 v2 | yes, beside F tasks (no shared files) | G3: checker 0 fails; INDEX lines present |
| 4 | D4 learning run; E3, E4, E5, E6; B-N7, B-N8 (master); C4 pilot when the next new task is built | E3-E6 one worker serial; D4 parallel | G4: unit tests green; `grep` checks in E5 |
| after 4 | Ayush: B-N2..N4 from `DOCKER_STEPS.md` (one restart, no container running); B-N5 at end of day; B-N1, B-N9 any time | — | master runs `docker info` and checks Total Memory ~16 GiB and `docker buildx du` reclaim; logs it |

Rule: nothing in a later batch starts before the previous gate passes, except Batch 3 items, which may start at the resume point because they touch no code and no task (ANS Q21 a).

## 6. Not doing (and why)

- R4 Q4 band re-measure with 2 extra paid runs of each of 13 teammate tasks: 26 paid runs, > 4 days of cap.
- R3 Q1 dropping rubric < 85: Ayush keep; R3's own evidence says it is free (R3F:143).
- R5-02(d) automatic kill of a running paid run in the first fix: log-only first (ANS Q18 a).
- R2 not-recommended items (files.autoSave, Docker engine switch, launchctl maxfiles).
- Editing the harness repo `H/scripts/package_rfp_bundles.py`: the wrapper lives in `MT/tools/` (A4, ANS Q4 a). (MQ is edited in E1/E6 with backup, as in earlier master edits.)
- Re-scoring pushed tasks (sentinel 44.53, district 44.84) to < 40 on our own initiative: only when the QL asks (ANS Q2 a).
- Renaming LEVER_RULES to v4 / _COMMON_RULES to v6: snapshots + in-place v3.7 instead (ANS Q12 a).
- A new P18 "tool change" template: code work uses one-off issued prompts.
- Promoting N1/N2 to PROVEN now: 8-9 tasks, 3 from one author, 1 hole (R3F); needs our own pilot.

## 7. Questions

None open. All 25 answered 28 Oct (`U/P1_plan/ANSWERS.md`): option a everywhere; Q6 = recommended settings applied by Ayush himself after the upgrade from `U/V1_verify/DOCKER_STEPS.md`. New asks that come up during apply go to the Needs-Ayush list in the master LOG.

## 8. Risks and conflicts with current rules

| Rule | Conflict | Handling |
|---|---|---|
| Never 10 / freeze after QC PASS (CR:29, pipeline_v4 decision 1) | cold-chain and metered are predicted to miss < 40 but are frozen | run first, read trajectory, then harden (F1/F2; ANS Q22 a, Q23 a) |
| No re-run on the same bytes (LR:215) | cold-chain's 17:41 run was invalid (no trajectory) | not a re-run of a valid run (REPORT.md:13); any later valid miss -> trajectory read-out, never a re-run |
| Regrade never push evidence (CR:65-66, KN:119, LR:215, PV4:12/59/99) | sentinel was pushed on a regrade (DEC:390-400) | named exception with Ayush's verbatim OK per use (A7, ANS Q1 a) |
| Law-1 (LR:87-88) | QL zip edits may add a lever that fails Law-1 | P17 CHANGES.md stops on any lever change not passing the kill table; P16 asks Ayush before any lever/rule change |
| Never 6 / Never 8 / Never 11 | LC1 induction, LC5 authority order, QL reply text | LC1 legal only with stated finite domain + EVIDENCE_MAP; LC5 order written once; reply template forbids trap/lever names (W1, CR:27) |
| Cap of 6 paid runs/day | QL reruns outside cap | ask Ayush each time; intake event `ql_rerun` keeps them countable; Budget rule still applies |
| Time box 8 sessions (issue.py:36, 24 Oct U1) | pushed tasks in QL rounds would always be refused | A1 skips `ql` kind and resets at stage change; round caps kept (ANS Q3 a) |
| C2 bar vs ANS Q24 "~42-45 worlds" | 42-45 worlds break C2 (a) and (d) | F3: C2 bar wins; DESIGN v2 must meet it or the task is parked (Q24 "a miss -> park") |
| Gate change mid-flight | issued prompts in `prompts/issued/` still say 50 | re-issue paused-task prompts after Batch 1; history rows not rewritten |
| Shared subscription | upgrade workers compete with task workers | Batch 2 before resume; Budget: paid run first in a fresh window |
| Docker 12 GiB until after the upgrade (ANS Q6) | metered 8 GiB + another heavy job may not fit | metered runs alone among Docker-heavy jobs until B-N2 |
| registry has no `tree_sha` today | A2 refusal would block every run | A3 backfill (cold-chain) + freeze rule (metered, schema) before any F run |
| In-place rules edit | loses old text if snapshot skipped | C0 snapshot + sha256 is step 1 of Batch 1 |

## Lessons for the master
- Gate < 40 needs tests <= 60 AND rubric <= 20 at design time; none of the 3 paused designs meets that today, so expect read-out/harden rounds, not first-run passes.
- Fix limit detection (E1) before any long auto run; the overnight loss was a blind watcher, not a bad task.
- Frozen bytes stay frozen: a predicted miss is still run once, then read out.
- Every verify command in a plan must be run once (or dry-read against the tool's real output) before the plan ships; 6 of v1's verify lines could not pass as written.
- Keep rules edits in place with snapshots (v3.3-v3.6 precedent); 15 templates point at the current file names.
