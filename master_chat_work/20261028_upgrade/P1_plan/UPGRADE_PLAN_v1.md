# Upgrade plan v1 (board 3d3a74a, 28 Oct 2026 23:50 IST)

Nothing here is applied. The master applies it batch by batch only after Ayush says "proceed" and after the verify session has checked this file.

Path roots: `T` = `/Users/mac/Desktop/Terminal Bench`, `MT` = `T/master_chat_tasks`, `U` = `T/master_chat_work/20261028_upgrade`, `H` = `T/Terminal_2.0_Harbor_Harness`.
Source abbreviations: `R1F` = `U/R1_ql_loop/FINDINGS.md`, `R1T` = `U/R1_ql_loop/TOOL_CHANGE_SPECS.md`, `R1M` = `U/R1_ql_loop/MASTER_STEPS.md`, `R2F` = `U/R2_mac_setup/FINDINGS.md`, `R2A` = `U/R2_mac_setup/apply_safe.md`, `R3F` = `U/R3_hardness_md/FINDINGS.md`, `R4F` = `U/R4_teammate_repo/FINDINGS.md`, `R5F` = `U/R5_auto_issues/FINDINGS.md`, `R5I` = `U/R5_auto_issues/issues.csv`, `CR` = `MT/prompts/templates/_COMMON_RULES_v5.md`, `LR` = `MT/knowledge/LEVER_RULES_v3.md`, `KN` = `MT/knowledge/KNOWLEDGE.md`, `AP` = `MT/auto/AUTO_POLICY.md`.
Tags: **[CHECKED]** = I read the cited lines myself in this session (23:44-23:48 IST). **[UNVERIFIED]** = taken from an R-session and not re-read by me; the verify session should spot-check these.

## 1. Summary

1. Gate becomes tests < 85 AND rubric < 85 AND final < 40 (only the final number changes) in `intake.py`, `_COMMON_RULES_v5`, LEVER_RULES (v3.7 section), KNOWLEDGE, AUTO_POLICY, pipeline_v4 PLAN; design aims tighten to tests <= 60 and rubric <= 20 (predicted final <= 35).
2. Auto mode learns to see the usage limit (retry status, reset parse with seconds, budget rule) before anything else runs on it; this is the biggest loss found (R5: ~32 worker-hours lost overnight).
3. A QL loop is added: inbound home `master_chat_work/_ql/`, issue kind `ql`, intake events `ql_rerun` and `regrade`, tree sha on every run row, P16 (report triage), P17 (zip hand-back), QL reply template, FP dossier.
4. Mac: 8 SAFE items applied by the master at once; 9 NEEDS OK items wait for Ayush (sudo, Docker restart, DB vacuum, deletes, GUI).
5. Levers: L2 held-out instances and L6 process criteria become PROVEN; held-out w5 tier >= 50% (N2) + paired probe band (N1) become the default shape for the next new build (one pilot); L3, L5, L7, L8, L9 marked WEAK; unbounded induction, effort caps and judge-only bands marked FALSE.
6. Learning loop: P15 v2 with a persistent angle log `knowledge/ANGLES.md`; each run proposes its own next version; master accepts or rejects each version.
7. Order: Batch 0 answers + Mac SAFE, Batch 1 rules + gate + tool edits, Batch 2 auto limit/health fixes, then the 3 paused tasks resume; Batches 3-4 (QL templates, learning, auto cleanups, NEEDS OK) run beside them.
8. Cost: about 7 worker sessions (2 auto-code, 1 metered report, 1-2 schema design+build, 1 learning, 1 QL template check, 1 verify) and 3 paid runs (cold-chain, metered, schema), all inside the cap of 6/day; 0 paid runs for the upgrade itself.
9. Unchanged: Never list, Law-1, freeze after QC PASS, 1 valid run on frozen bytes before push, no re-run on the same bytes, tests < 85 and rubric < 85, cap of 6 paid runs/day, QL reruns ask Ayush each time.
10. Prediction honesty: of the 3 paused tasks only schema can be redesigned to a predicted final < 40 before its run; cold-chain (predicted ~56) and metered (39.8-45.7) are frozen and need their run first, then a trajectory read-out.

## 2. Workstreams and items

Field order in every item: What / Files / New files / Who / Depends / Verify (command -> expected) / Rollback / Risk / Source.

### A. QL loop (goals 1-2)

**A1 issue.py: kind `ql`, time box rule, `--by`**
- What: add `ql` to KINDS and TASK_KINDS; `pushed` joins the `passed` set unless an open QL round exists; time box (8 sessions) does not count sessions of kind `ql`, and for `qc`/`fix`/`harden` on a pushed task with an open QL round; time box counter resets when the stage changes (R5-08); round caps and the stop-at-PASS / no-harden-after-PASS checks stay; override writes `"by"` from a new `--by` flag (default `master (auto)` in auto mode, `Ayush` when Ayush typed it), same-minute file gets `_2` suffix (R5-24).
- Files: `MT/tools/issue.py:14-19` docstring, `:34` KINDS, `:36` TIME_BOX, `:37` TASK_KINDS, `:71` passed, `:89-90` time box, `:101` kind choices, `:118-122,137` file naming, `:136-142` decision row [CHECKED all line numbers].
- Who: worker session E-code-1 (same session as E1, one-off prompt `MT/prompts/issued/_upgrade/<TS>_E1_tools.md`; not a template).
- Depends: Q3 answer.
- Verify: `python3 MT/tools/issue.py --help | grep -c ql` -> `>=1`; a temp-registry dry case for a pushed slug with kind `ql` prints the prompt instead of a time-box refusal; `grep -n '"who"' MT/tools/issue.py` -> no hit.
- Rollback: copy `issue.py` to `/tmp/P1-upgrade-bak/issue.py` before edit; copy back.
- Risk: loosens an Ayush-approved rule (24 Oct U1, R5F R5-08). Mitigation: round caps kept, `--by` logged on every override.
- Source: R1T T1, R5I row R5-08 and R5-24 [line numbers CHECKED; the 24 overrides count UNVERIFIED].

**A2 intake.py: gate 40, events `ql_rerun` and `regrade`, tree sha**
- What: constant `FINAL_GATE = 40`; `:104` becomes `gate = t < 85 and r < 85 and o < FINAL_GATE`; `:11` and `:106` texts say `final<40`; `--event` choices add `ql_rerun`, `regrade`; `regrade` rows are written `valid: false` unless `--ayush-ok "<verbatim words>"` is given (and then only if Q1 = yes); row gets `tree_sha` computed from `--bundle` with the REGRADE_REPORT method; `gate_run` and `ql_rerun` are refused if the computed tree sha differs from the registry `tree_sha`.
- Files: `MT/tools/intake.py:11,:104,:106,:108-111,:124` [CHECKED].
- Who: E-code-1 worker.
- Depends: Batch 0 answers Q1, Q9.
- Verify: `grep -n "o < 50\|overall<50" MT/tools/intake.py` -> no hit; `grep -n "FINAL_GATE = 40" MT/tools/intake.py` -> 1 hit; run intake without `--apply` on the sentinel run dir used in R1 (`final 44.53`) -> prints `gate ... False`; `--event regrade` without `--ayush-ok` prints `valid: False`.
- Rollback: backup copy as A1.
- Risk: a row written before the change keeps its old `gate` meaning; scores.jsonl rows are history and are not rewritten.
- Source: R1T T2 [CHECKED intake.py lines]; sentinel 44.53 from R1F [UNVERIFIED].

**A3 status.py: fields `tree_sha`, `ql_round`, `ql_last`**
- What: add three fields to FIELDS; no new stage (pushed stays pushed).
- Files: `MT/tools/status.py:22-23` [CHECKED].
- Who: E-code-1 worker. Depends: none. Verify: `python3 MT/tools/status.py --help` lists the 3 fields; `python3 MT/tools/status.py <slug>` on a copy of the registry runs clean. Rollback: backup copy. Risk: low.
- Source: R1T T3.

**A4 one-slug repackage tool**
- What: `MT/tools/repackage_one.py --slug --run-dir --task-dir <frozen Tasks_INPUT>`; imports `_package_run()` from `H/scripts/package_rfp_bundles.py` and calls only that; refuses if `--task-dir` tree sha != registry `tree_sha`; backs up the old Output_RFP folder (incl. trajectories) to `/tmp/repack-<slug>-<TS>/`, writes a before/after sha listing. Never calls `main` (`:273-280`). The harness repo is not edited.
- Files: new `MT/tools/repackage_one.py`. `H/scripts/package_rfp_bundles.py:15,:117,:152,:236` read only [line refs from R1F, UNVERIFIED].
- Who: E-code-1 worker. Depends: Q4. Verify: dry run on the sentinel run (R1 precedent, sentinel REGRADE_REPORT.md:119) writes into `/tmp` only and the listing matches the pushed Output_RFP folder except score files. Rollback: delete the new file. Risk: `task.path` in config.json may point to `/tmp` after a regrade (R1F gap 7); the `--task-dir` override handles it.
- Source: R1T T4, R1F gap 7.

**A5 QL templates**
- What: move R1 drafts into templates: `P16_ql_report_triage_v1.md` (labels REAL / FALSE POSITIVE / PARTLY / OUT OF SCOPE, kit rule ids, carry-over), `P17_ql_handback_v1.md` (zip intake, INVENTORY.md, CHANGES.md, 4 paths), `QL_REPLY_TEMPLATE.md`. Fix inside them: gate text `final < 40`, `LEVER_RULES_v3.md` path unchanged, `_COMMON_RULES_v5.md`. Mark P7 v2 and P8 v2 as not used for QL work (they read the stale `_COMMON_RULES.md`, R1F line 9).
- Files: new `MT/prompts/templates/P16_ql_report_triage_v1.md`, `P17_ql_handback_v1.md`, `QL_REPLY_TEMPLATE.md`; `MT/prompts/templates/CHANGELOG.md` + 1 line: `- 2026-10-29 HH:MM QL loop (board 3d3a74a): P16 v1, P17 v1, QL_REPLY_TEMPLATE added from R1 086e1b4; P7 v2/P8 v2 retired for QL work.`
- Who: master copies; one checker session (Batch 3) runs `knowledge/PROMPT_CHECKLIST.md` on P16 and P17. Depends: Batch 1 (gate text). Verify: `grep -c "final < 40\|final<40" P16* P17*` >= 1 each; `grep -n "_COMMON_RULES.md" P16* P17*` -> no hit (only `_v5`); checklist session returns 0 fails. Rollback: delete the 3 files and the CHANGELOG line. Risk: reply template leaking lever/trap names (W1, CR:27) — the template forbids it and P16 has a W1 self-check (R1F).
- Source: `U/R1_ql_loop/drafts/*` (sizes CHECKED), R1F Part A/B.

**A6 QL knowledge: inbound home, FP dossier, INDEX, master steps**
- What: create `T/master_chat_work/_ql/` (one folder per slug, `<TS>_report/` and `<TS>_zip/` inside); create `MT/knowledge/FP_DOSSIER.md` with header `| date | slug | finding | kit rule file:line | why false | source (QC round / QL round) |` (INDEX already lists it as ACTIVE but the file is missing [CHECKED INDEX.md]); copy R1 MASTER_STEPS to `MT/knowledge/QL_MASTER_STEPS_v1.md`; INDEX lines for `_ql/`, P16, P17, QL_MASTER_STEPS_v1, FP_DOSSIER status fixed. QC_RULINGS row only after the QL agrees a finding was false (R1 Q6, adopted, not asked).
- Who: master. Depends: A5. Verify: `ls T/master_chat_work/_ql`; `head -3 MT/knowledge/FP_DOSSIER.md` shows the header; `grep -c "P16\|P17\|QL_MASTER_STEPS\|_ql/" MT/knowledge/INDEX.md` >= 4. Rollback: remove the new files and INDEX lines. Risk: low.
- Source: R1F Part A, R1M A1-A10/B1-B6.

**A7 Regrade exception text (only if Q1 = yes)**
- What: named exception in 3 places: "Regrade counts as push evidence only when the edit touches judge files only (no tests/, no instruction, no environment), the run was valid, Ayush wrote OK for this regrade (verbatim in decisions.jsonl), and the regraded run is repackaged with A4. Otherwise diagnostic only, never packaged."
- Files: `CR:65-66`, `KN:119`, `LR:215` [CHECKED texts]. Who: master in Batch 1. Verify: `grep -n "regrade" CR KN LR` shows the exception in all 3. Rollback: snapshot restore (see C0). Risk: conflicts with pipeline_v4 decision 5 (Way A diagnostic only) — Ayush's own sentinel push (DEC:390-400, R1F) already broke it once; the question makes it explicit.
- Source: R1F gap 1, R1 Q1.

QL flows (Part A report pasted, Part B zip) are run exactly as R1M A1-A10 and B1-B6, with these fixed decisions: gate for a QL "lower the score" round is final < 40; every QL paid run is asked of Ayush first and is outside the cap of 6 (Ayush 28 Oct); a zip that changes tests/ or judge files voids the old run and needs a new paid run (LR:210 [CHECKED]); a zip without trajectories asked to "degrade" = blind harden: 3 x P13 v2 blind reads, then P9 v4 with blind results as the evidence, P11 v3 full QC, freeze, ask, 1 run (R1F Part B).

### B. Mac / Docker / VS Code / opencode (goal 3)

All machine-state numbers below are from R2 [UNVERIFIED by me except auto.py:597 `--port 0`, CHECKED]. Every item has its backup/check/rollback written in `R2A`; the master follows `R2A` as written.

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

Sources: R2F SAFE list, R2A sections `## S1-S5` (line 5), `## S6` (33), `## S7` (38), `## S8` (44) [line numbers CHECKED].
Risk: B-S6 pin blocks plugin fixes until unpinned (accepted; R2 found @latest drift). B-S1/S2 hide `master_chat_work` from VS Code search — the master uses grep/rg, not VS Code search, so no loss.
Note (customize-opencode skill applies when the master edits `~/.config/opencode/`; load it at apply time).

NEEDS OK (wait for Ayush; Batch 4 unless Ayush says earlier):

| id | What | Who | When | Rollback | Question |
|---|---|---|---|---|---|
| B-N1 | `sudo pmset -b sleep 0 displaysleep 10 powermode 0` + habit: charger in, lid open during auto runs | Ayush (sudo) | any time | `sudo pmset -b sleep 1 displaysleep 2 powermode 1` | Q7 |
| B-N2 | Docker memory 12 -> 16 GiB | Ayush (Docker Desktop GUI, restart) | no Docker job running | GUI back to 12 | Q6 |
| B-N3 | Docker swap 1 -> 2 GiB | Ayush GUI | with N2 | GUI back | Q6 |
| B-N4 | daemon.json builder gc policy `[{keepStorage 10GB, unused-for 168h},{keepStorage 20GB, all}]` | Ayush GUI (restart) | with N2 | old daemon.json (gc defaultKeepStorage 20GB) | Q6 |
| B-N5 | backup + `VACUUM` of opencode.db (4.0 GB) with all opencode stopped | master after Ayush OK | end of day, no sessions | restore backup | Q8 |
| B-N6 | auto.py health: 15 s timeout + 2 strikes | merged into E2 (R5-07) | — | — | settled (E2) |
| B-N7 | close stale opencode pids 15335, 23171 | master after Ayush OK | after checking `ps -p` they still exist and are not Ayush's open window | none (process) | Q8 |
| B-N8 | delete `/tmp/opencode-logs` files > 7 days | master after Ayush OK | any time | none | Q8 |
| B-N9 | Spotlight privacy: add Terminal Bench | Ayush GUI | any time | remove from list | Q8 |

Also listed by R2 for Ayush's GUI: Battery > Low Power Mode Never; "Prevent automatic sleeping on power adapter when display is off" (R2F section 4). Not recommended by R2 and not done: files.autoSave, switching Docker engine, raising launchctl maxfiles. Docker tuning stays on the current Docker Desktop (Ayush: "tune current Docker only").

### C. Hardness levers and gate < 40 (goal 5, R3, R4)

**C0 How rules files are versioned (applies to C1-C4, A7, D3)**
- Decision: follow the v3.3-v3.6 precedent (all in-place in `LEVER_RULES_v3.md`, LR:1 header lists versions [CHECKED]; CHANGELOG 2026-10-27 22:30 edited 9 files in place [CHECKED]) but first freeze the old bytes: copy `LR` -> `MT/knowledge/LEVER_RULES_v3.6_snapshot.md`, `KN` -> `MT/knowledge/KNOWLEDGE_v3.6_snapshot.md`, `CR` -> `MT/prompts/templates/_COMMON_RULES_v5_g36_snapshot.md`, record their sha256 in LOG, add INDEX lines with status SNAPSHOT. Then edit in place as v3.7. Reason: 13 templates reference the `LEVER_RULES_v3.md` path and 4 reference `_COMMON_RULES_v5.md` [CHECKED by grep]; a new file name would force 17 template edits. This meets "never overwrite the old version" (old bytes kept under a version name). Asked as Q12 in case Ayush wants new file names instead.

**C1 Gate final < 40 everywhere**
- Current lines [all CHECKED]:
  - `intake.py:104` `gate = t < 85 and r < 85 and o < 50` -> `gate = t < 85 and r < 85 and o < FINAL_GATE` with `FINAL_GATE = 40  # Ayush 28 Oct: Target <40 now` (A2).
  - `CR:61` "tests < 85 AND rubric < 85 AND final reward < 50 on 1 valid run ... so final < 50 needs rubric < 100 - tests" -> "tests < 85 AND rubric < 85 AND final reward < 40 on 1 valid run (v3.7, Ayush 28 Oct 'Target <40 now'). Final = (tests + rubric)/2, so final < 40 needs rubric < 80 - tests; design for tests <= 60 and rubric <= 20."
  - `LR:210` gate text -> same sentence as CR:61, marked `[v3.7]`, old v3.6 sentence kept struck in the snapshot only.
  - `LR:89` and `CR:49` (v3.6 aims) -> see C2.
  - `KN:118` step 4 gate logic: "final >= 50" branches -> "final >= 40".
  - `AP` gate wording and `T/master_chat_work/_dev_research/pipeline_v4/PLAN.md` stage 6 and 7 lines ("final < 50", "final >= 50") -> 40 [stage 6/7 text CHECKED].
- Who: master (text) + E-code-1 (intake.py). Verify: `grep -rn "final < 50\|final<50\|overall<50\|final >= 50\|o < 50" MT/tools MT/knowledge MT/prompts/templates MT/auto T/master_chat_work/_dev_research/pipeline_v4/PLAN.md` -> hits only in `*_snapshot.md` files and CHANGELOG history lines. Rollback: snapshots + intake.py backup. Risk: issued prompts already in `prompts/issued/` keep 50; any session started from them before Batch 1 is judged at 50 — master re-issues paused-task prompts after Batch 1 (Batch F).
- Tests < 85 and rubric < 85 kept. R3 (R3F:136-145) calls rubric < 85 redundant but free; R4 (Q3) says keep; Ayush said keep unless evidence says otherwise; R3's evidence shows no harm -> keep. Settled, not asked.

**C2 Design aims and DESIGN READY bar (v3.7)**
- `CR:49` / `LR:89` [CHECKED] current: "plain first-write and all-but-one program aim at tests <= 75; each of 3 fresh blind reads tests <= 80; judge probe mid 15-20; auto go at DESIGN READY when kill table passes (each solver loses >= 15% of lever points ...)".
- Proposed v3.7 text: "[v3.7 28 Oct, gate final < 40] Plain first-write and all-but-one programs aim at tests <= 60. Blind bar: each of the 3 fresh blind reads scores tests <= 65 (none above 70). Judge: probe band, predicted probe mid <= 20. DESIGN READY needs, in DESIGN.md: (a) predicted final = (predicted first-write tests + predicted judge mid)/2 <= 35 (5 points margin for the ±10 final spread, LR:215 same-bytes spread); (b) lever share >= 40% of positive test weight (if the lever is fully lost and all else passes, tests <= 60), with the held-out w5 tier >= 50% when the N2 shape is used; (c) blind ceiling: no blind program above tests 65; (d) verifier worst case <= 90% of the stated verifier limit; (e) the kill table rule (>= 15% lever loss by WRONG output) unchanged. Overnight go at DESIGN READY unchanged."
- Evidence: final < 40 needs tests + rubric < 80; our 10 valid gate runs mean tests 78.7, rubric 23.5, only 1 below 40 (R3F:136-145 [UNVERIFIED]); tests >= 65 needs rubric <= 15 with no margin (R3F). Arithmetic (a)-(b) CHECKED by me.
- Who: master text, Batch 1. Verify: `grep -n "v3.7" CR LR` shows the new text in both. Rollback: snapshots. Risk: fewer designs reach DESIGN READY (intended); verifier time grows with more hidden worlds (schema shows the limit, F3).

**C3 Lever status table v3.7 (new section in LR, after the v3.6 section)**

| Lever | v3.7 status | Evidence | How to use |
|---|---|---|---|
| L2 held-out instances (Shape D, 1C) | PROVEN | shipped 62% vs held-out 42% pass, at w5 43% vs 23%; within-author r_tests -0.43 (R3F:98-109); HardExpert hidden share 0.68 vs 0.16-0.18, hidden pass 0.01 (R4F contrast) | default test lever; G3/G5, 0b, W5 BRANCH_FIRE |
| L6 process criteria / probe band (J2, P-a..P-h) | PROVEN | verify criteria 52% vs read 24%; our gate runs mean rubric 23.5 (R3F) | every judge; mid <= 20 |
| N2 held-out w5 tier >= 50% of positive test weight | PROMISING (pilot) | 8 tasks mean 34.8, 5 < 40; cur90 9 tasks mean 32.8 (R3F); R4 hidden share >= 0.5 median 35.7 vs 56.5 | default shape for the next new build (C4) |
| N1 pair channels (held-out w5 tier + probe band) | PROMISING (pilot) | halves anti-correlated r -0.40, -0.32 within author (R3F) | same pilot as N2 |
| L1 / LC2 weight on w5 (shipped w1, hidden w5) | PROMISING, amplifier only | within-task 73/83 but r weakens within author (R3F); R4 top1 share no signal | only on a held-out core via TS-20; never reweight after a run (KN T:113) |
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

- Stats in this table are [UNVERIFIED] (R3/R4 scripts in `U/R3_hardness_md/scripts/`, `U/R4_teammate_repo/scripts/`); the verify session should re-run one R3 script (L2 contrast) and one R4 script (hidden share contrast) before Batch 1.
- R3's 5 wrong doc claims (C10, C24, C51, C58, C60 in `U/R3_hardness_md/claims.csv`) are not lever rules; they go to the QL reply (C5).
- R3 and R4 disagree on interlocking (R3 WEAK, R4 LC4 candidate): picked WEAK, because R4's support is 2 tasks and our own L4 multi-doc build leaked; LC4 can be tried only inside the N2 pilot's held-out tier.

**C4 Pilot of the default shape (N1 + N2)**
- What: the next new task built after Batch 1 uses: held-out w5 tier >= 50% of positive test weight with >= 6 hidden corpora (G3 Shape D), plus a probe-band judge mid <= 20. Proof bar (R3F N1/N2): frozen QC-passed bytes, 1 valid run with tests <= 60 and rubric <= 20, and 2 of 3 blind reads lose >= 40% of positive test weight on the held-out tier while passing shipped checks.
- Files: none beyond C2/C3 text; DESIGN.md of that task. Who: P2 v5 build worker (normal pipeline). Depends: Batch 1, Q11. Verify: DESIGN.md shows (a)-(e) of C2; after the run, `intake.py --event gate_run` row. Cost: 1 paid run (inside cap). Risk: one pilot is n=1; promote N1/N2 to PROVEN only after 2 pilots pass.

**C5 Reply to the QL on hardness.md**
- What: one Markdown file for the QL: claim list with verdict (41 confirmed, 18 partly, 5 wrong, 4 untestable), the 5 wrong claims with evidence, R3's 4 QL questions (opus-5-5 runs in the sample; theme regex script; L6 counts; 59417607 hidden count and recipe claim), the 2 proven levers and 3 new candidates in plain terms. No names of our tasks' traps (W1, CR:27); our 4 tasks in the doc are named only by their sample id.
- New file: `T/master_chat_work/_ql/hardness_md/REPLY_hardness_v1.md`. Who: master (writing) from `U/R3_hardness_md/claims.csv` + R3F. Depends: A6 (folder). Verify: `grep -ci "trap\|lever_rules\|LR:" REPLY_hardness_v1.md` reviewed by hand; Ayush reads before sending. Risk: doc tasks 42e79476/b47fd5f7/8fbe0e42/b5c7b14c have registry vs Final_Delivery score differences (R3F, bytes UNVERIFIED) — reply says "scores differ, bytes not compared" rather than claiming either.

### D. Learning loop with angle log (goal 4)

**D1 Angle log**
- What: `U/R4_teammate_repo/ANGLES.md` (A1-A12 tried with strength, U1-U12 untried ranked) becomes the master copy `MT/knowledge/ANGLES.md`; INDEX line "ANGLES.md | before any P15 run | ACTIVE, master merges each P15 OUT/ANGLES.md". Sessions never write it (P15 v2 line 52 forbids it [CHECKED]); master merges each run's `OUT/ANGLES.md` after reading it.
- Who: master. Verify: `diff U/R4_teammate_repo/ANGLES.md MT/knowledge/ANGLES.md` -> empty at first copy. Rollback: delete. Risk: low.

**D2 P15 v2 and P14 v2 templates**
- What: copy R4 drafts to `MT/prompts/templates/P15_research_angle_v2.md` and `P14_task_analysis_v2.md`; set `[[ANGLES_FILE]]` default to `master_chat_tasks/knowledge/ANGLES.md` (draft line 12 already says the master moves it [CHECKED]); CHANGELOG lines: the one proposed at P15 draft line 66 [CHECKED] and `- 2026-10-29 HH:MM P14 v2 (board 3d3a74a): score-convention check, no-message genuineness path, identifiability of withheld facts, instructed caps, channel split 50/P, weight geometry, judge composition (from R4 1d26a6e).`
- Who: master copies; checker session (same as A5 check, Batch 3) runs PROMPT_CHECKLIST on both. Verify: checklist 0 fails; `grep -n "\[\[ANGLES_FILE\]\]" P15_research_angle_v2.md` present. Rollback: delete files + CHANGELOG lines (v1 files untouched).

**D3 Self-improvement rule**
- What: each P15 run ends with `## Proposed prompt changes` and a CHANGELOG line (draft lines 58-59 [CHECKED]). Master reads each proposal, accepts or rejects each numbered edit with one reason in `MT/knowledge/ANGLES.md` (a "Prompt versions" table: version, date, accepted edits, rejected edits, reason), then writes P15 v(N+1) as a new file; old versions stay. A version is accepted only if its run produced >= 1 angle rated S or M on a within-contributor contrast. Two runs in a row with only W/N angles -> master stops the loop and tells Ayush.
- Who: master. Depends: D1, D2. Verify: after the first run, `MT/knowledge/ANGLES.md` has new rows and a "Prompt versions" row.

**D4 First learning run**
- What: 1 worker session from P15 v2 on the top 2 untried angles (U1 self-test anatomy, U2 judge negative design; R4 ANGLES.md ranking), corpus `anubis-stage-1` + our Final_Delivery tasks; no paid runs, no Docker.
- Who: worker session (P15 v2). Depends: D2, Batch 2 (limit detection, so it is not lost to the shared limit). Cost: 1 session. Verify: `OUT/result_<sha>.json` parses; REPLY.md has `## Proposed prompt changes`.

**D5 Teammate model cards**
- What: R4 cards (9 genuine models, 4 flagged; `U/R4_teammate_repo/cards/`, `genuineness.md`) copied to `MT/knowledge/TEAMMATE_MODELS_v1.md` (summary table + links to the cards kept in U), INDEX line "read when designing a new task". 725e575c listed as "not a hardness model" (R4 Q2 settled by its own evidence: tests 96.55).
- Who: master. Verify: INDEX line present. Risk: R4's genuineness labels are [UNVERIFIED]; the card file says so in its header.

### E. Auto-mode fixes (R5)

All line numbers below were checked for auto.py:65-70, :87, :271-275, :299-301, :597 and AP:15, :26, :30, :32, :37, :46, :47, :54 and issue.py [CHECKED]; others are R5's [UNVERIFIED]. Each batch is one worker session with a one-off prompt in `MT/prompts/issued/_upgrade/`, code backups in `/tmp/P1-upgrade-bak/`, and must end with `python3 -m unittest discover -s MT/auto/tests` green plus the new tests named below.

**E1 Limit detection and budget (R5-01, R5-02 a-c, R5-03, R5-13)** — Batch 2, worker E-code-1 (together with A1-A4)
- What: `retry_ids` next to `busy_ids` (auto.py:299-301: `retry` status counted separately, not as busy); `LIMIT` event, `limit_since` in state; `cmd_spawn` and `cmd_harness` refuse while LIMIT; master_queue pause; `LIMIT CLEARED` after 2 clean polls. RESET_IN_RE (auto.py:87) gains seconds (`s|sec|second`); resume = parsed reset + 5 min, keyed by task, not by reason (auto.py:1237-1259, master_queue.py:623). 401 -> `AUTH` event, not limit (master_queue.py:75, wrapper exit 8). Budget rule in code: harness refused when LIMIT is set or > 2 workers busy at launch; while a paid run is RUNNING, max 3 busy workers (else MAX_BUSY_WORKERS 5).
- Verify: R5's fake server `/tmp/R5-auto-*/fake_oc.py` replayed (returns `retry` status) -> LIMIT event within 2 polls; `python3 U/R5_auto_issues/exp1.py` case `parse_reset('... soonest reset in 4698s', 17:54:49)` -> `>= 19:13:07`; a fake 401 -> `AUTH`.
- Not in E1: R5-02(d) killing a running paid run on the first `accounts exhausted` — log-only in E1; kill only after Q18 and after the log has shown the line on a real run once.
- Risk: a false LIMIT blocks a night; mitigated by 2-poll clear and the REPORT line.

**E2 Watcher reliability (R5-04, R5-05, R5-06, R5-07 = R2 N6)** — Batch 2, worker E-code-2 (after E1 tests pass; same files, so serial, not parallel)
- What: REPORT line + optional `osascript` notice when events stay undelivered (auto.py:1294-1338); stall watchdog `STALL_MIN = 20` (no new message 20 min while busy) beside LONG_BUSY_H 6 (auto.py:70, 1176-1180); `doom` class: keep the deny (auto.py:119), one auto "continue" with a poll rule (only if the counter is rising), then BLOCKED; health check 15 s timeout + 2 strikes and a "answering again" event that clears the flag (auto.py:271-275, 1391-1397, cmd_resume :935).
- Verify: unit tests for stall and 2-strike health with mocked time; `auto.py status` runs.

**E3 Stop and final report (R5-09, R5-11, R5-25)** — Batch 4
- What: FINAL only after the last worker result and harness exit (auto.py:1367-1376, 1420); `auto.py stop --now` (cmd_stop 970-975) that stops watcher, caffeinate, queue in one step; REPORT writes "Still running at stop" instead of empty sections.

**E4 Decisions file (R5-23)** — Batch 4, with A1's `--by`
- What: new `MT/tools/decide.py` that appends one validated row (`ist`, `by`, `slug`, `what`, `words`) to decisions.jsonl; AP:54 field name `by` kept, issue.py switched to `by` (A1).

**E5 Policy and plan template (R5-10, R5-19, R5-22, R5-20)** — Batch 4, master text + worker code
- What: AP:46 "4 workers" -> "5 workers (Ayush 27 Oct 22:20; auto.py:65)"; AP:47 Docker cap: "2 heavy Docker workers" becomes enforced by MAX_HARNESS/MAX_BUILDS or the line is reworded to "advice"; new `## Budget` section in AP (paid runs max 6/day, each only with no LIMIT and <= 2 busy workers; max 3 busy workers while a paid run runs; fresh window -> paid run first; on LIMIT hold, pause queue, resume at parsed reset + 5 min; master counts as a worker); AP:15 `--wind-down` flag for runs added after AUTO STOP (within the cap); last-spawn cutoff 20 min before AUTO STOP; wind-down hard cap does not kill busy sessions mid-step (R5-20). `MT/auto/PLAN_TEMPLATE.md` (14 lines) gains fields `Paid runs:`, `Workers/harness/Docker:`, `Budget:`, `Wind-down:`, `Last spawn:`.
- Verify: `grep -n "Budget\|Wind-down\|Last spawn" AP MT/auto/PLAN_TEMPLATE.md` -> hits in both.

**E6 LOW cleanups (R5-12, 14, 15, 16, 17, 21, 24 (in A1), 26)** — Batch 4, one worker
- What: master_queue does not count workers' oracle/nop `harbor run` (master_queue.py:230-235, 595-596); `cancel` clears PAUSED (R5-14; live state today: paused True, queue 0 [CHECKED with `auto.py status`]); board rows closed via `board.py set` (auto.py 566-577, 693); `MT/tools/registry_check.py` for type drift; plan step at start minute today, not tomorrow (auto.py:403-430); wrapper exit non-zero on errored run (package_rfp_bundles.py:113 traceback); regression test that WORKER_PERMISSION allows harbor oracle/nop (auto.py:93-121). R5-18 zsh lesson goes to KN lessons, not code.

### F. Resuming the 3 paused tasks under gate < 40

Resume table: `MT/auto/runs/20261028T1553_evening/REPORT.md:13-15` [CHECKED]. Resume point: after Batch 2 evidence gate (G2). All 3 restart from new prompts issued after Batch 1 (gate 40 text).

**F1 cold-chain-backbone-quote** (frozen tree 8ca9c267f59b = QC v4 copy 78b8d5b, MINOR G05-M1 PL note; REPORT.md:13 [CHECKED])
- Prediction under the frozen bytes: lever 24/108 = 22.2%, first-write plain 84/108 = 77.8 tests, judge mid 34-40% (HARDEN_REPORT.md:20, :29, :50 in `master_chat_work/20261027_cold-chain-backbone-quote/harden_w1_678c839/` [CHECKED]); later fixes left tests/ byte-identical (RECHECK_FIX v3 :107-112 [CHECKED]) -> my predicted final ≈ (77.8 + 34)/2 ≈ 56: misses < 50 and < 40.
- Next under the rules: the bytes are frozen after QC PASS; Never 10 (CR:28 area) and pipeline_v4 decision 1 allow later change only via trajectory read-out + recheck + 1 new run. So: 1 paid run on 8ca9c267f59b (the 17:41 run was invalid without trajectory, so this is not a same-bytes re-run of a valid run, REPORT.md:13) -> expected miss -> trajectory read-out -> P9 v4 harden to the C2 bar (tests <= 60, mid <= 20) -> P11 v3 recheck -> freeze -> 1 run. Q22 offers the alternative (Ayush exception: harden now, skip the predicted-miss run, save 1 paid run).
- Cost: 1 paid run now, 1 later.

**F2 metered-usage-rating-pipeline** (QC v1 Step 10 done: oracle 1.0 x3, nop 0, stub 0, owner 1.0; REPORT.md:14 [CHECKED])
- Prediction: last harden DESIGN predicted tests 60.7-72.5, rubric 18.9, final 39.8-45.7 (`master_chat_work/20261027_metered-usage-rating-pipeline/harden_g36_361674d/DESIGN.md:114` [CHECKED]) -> borderline; most of the band misses < 40.
- Next: short session finishes QC v1 Step 10 write-up + verdict + result json from the kept jobs in `master_chat_work/20261028_metered-usage-rating-pipeline/qc_v1_step10_ac12c0b/` (no rerun) -> PASS: freeze -> 1 paid run (Ayush already OK'd the metered paid run, REPORT.md:22) -> gate 40; miss -> trajectory read-out -> harden once -> 1 new run; second miss -> Needs Ayush (REPORT.md:17 rule carried). FAIL: P12 v4 fix.
- Cost: 1 session, 1 paid run.

**F3 schema-migration-plan-repair** (harden stage, Tasks_INPUT tree 308399b4016e = a6 bytes; DESIGN in `master_chat_work/20261028_schema-migration-plan-repair/harden_g36_a4f790c/`; REPORT.md:15 [CHECKED])
- The kept DESIGN.md predicts final 41.4-46.0 (:84) with 34 worlds (L = 170, share 36.9%, a6-like tests 63.12; :36-39) and no judge change (:96) [CHECKED]: fails the new bar.
- My arithmetic (CHECKED against DESIGN.md:27, :98-99; needs the verify session): at a6 rubric 28.95, tests must be < 51.05 -> L >= 280 (56 worlds) -> verifier worst case 18x60 + 56x30 + 120 = 2,880 s > 2,700 s limit: not feasible by tests alone. With a judge probe band mid <= 20 as well: 45 worlds (L = 225) -> a6-like tests 291/516 = 56.4, final ≈ (56.4 + 20)/2 = 38.2, worst case 2,550 s (94% of limit, above C2(d) 90%) -> 42 worlds gives 2,460 s (91%) and tests 291/501 = 58.1, final ≈ 39.0 (thin). So schema needs a DESIGN v2 that adds both more held-out worlds AND a judge probe band, or a faster per-world check.
- Next: P9 v4 harden session restarts at the DESIGN step with the C2 bar (the old DESIGN is input, not the plan), then build -> Phase 3 (a6 repo <= 60 now, was <= 75) -> P11 v3 recheck vs v11 copy 361ee0a -> freeze -> attempt 7. Q24 asks whether to spend attempt 7 (time box/drop rule issue.py:85-90 [CHECKED]) or park the task.
- Cost: 1-2 sessions, 1 paid run.

## 3. Per-item fields

Written inside each item of section 2 (What / Files / New files / Who / Depends / Verify / Rollback / Risk / Source). Item count: A1-A7, B-S1..S8, B-N1..N9, C0-C5, D1-D5, E1-E6, F1-F3 = 44.

## 4. Lever rules update (v3.7 delta, summary)

- PROVEN: L2 held-out instances; L6 process criteria / probe band.
- PROMISING: N2 held-out w5 >= 50%, N1 pair channels (one pilot, C4), L1/LC2 w5 weight (amplifier), L4 exact contract (multiplier), LC1 bounded induction (second pilot), LC3 counterfactual what-ifs, LC5 authority order, LC6 hazard slices.
- WEAK: L3/LC4 interlocking, L5 trap tiers, L7 honesty negatives as hardness, L8 determinism, L9 reward geometry, N3 small judge total.
- FALSE: unbounded induction, instructed effort caps, judge-only bands, weight concentration as a standalone lever.
- Gate: `intake.py:104` `gate = t < 85 and r < 85 and o < 50` -> `gate = t < 85 and r < 85 and o < FINAL_GATE` (`FINAL_GATE = 40`); `CR:61` and `LR:210` sentence in C1.
- DESIGN READY: predicted final <= 35, lever share >= 40% of positive test weight (held-out w5 tier >= 50% in the N2 shape), blind ceiling tests <= 65 (none > 70), verifier worst case <= 90% of limit, kill table unchanged (C2).
- Evidence for each row: table in C3. Promotion rule: PROMISING -> PROVEN needs 2 of our tasks meeting the proof bar on frozen bytes.

## 5. Order and batches

| Batch | Items | Can run together | Evidence gate before the next batch |
|---|---|---|---|
| 0 | Ayush answers QUESTIONS.md; verify session checks this plan; B-S1..S8 | yes (Mac items independent of everything) | G0: verify session PASS; R2A checks for S1-S8 all pass; Ayush "proceed" logged in decisions.jsonl |
| 1 | C0 snapshots, C1 gate text, C2 aims, C3 lever table, A7 (if Q1 yes), A1-A4 code (worker E-code-1 starts here) | text items by master in one sitting; code by worker | G1: the C1 grep shows no live `< 50`; intake.py on the sentinel run prints `gate ... False` with `final<40`; snapshot sha256 lines in LOG |
| 2 | E1 (same worker as A1-A4), then E2 | serial (same files: auto.py, master_queue.py) | G2: `python3 -m unittest discover -s MT/auto/tests` green; fake-server LIMIT test and exp1 reset test pass; `auto.py status` runs; 1 dry auto plan (smoketest PLAN.md) starts and stops clean |
| — | **RESUME POINT: F2 metered (report session + run), F1 cold-chain (run), F3 schema (DESIGN v2)** under a new PLAN with the E5 Budget fields filled by hand | F1/F2 runs obey cap 6 and Budget (3 busy workers while a run) | each run: `intake.py --event gate_run` row with tree_sha matching registry |
| 3 | A5, A6, C5, D1, D2, D5; checker session for P16/P17/P14 v2/P15 v2 | yes, beside F tasks (no shared files) | G3: checker 0 fails; INDEX lines present |
| 4 | D4 learning run; E3, E4, E5, E6; B-N1..N9 per Ayush answers (N2-N4 only when no Docker job; N5 only with all opencode stopped); C4 pilot when the next new task is built | E3-E6 one worker serial; D4 parallel | G4: unit tests green; `grep` checks in E5; Docker `docker info` shows new memory after N2 |

Rule: nothing in a later batch starts before the previous gate passes, except Batch 3 items, which may start at the resume point because they touch no code and no task.

## 6. Not doing (and why)

- R4 Q4 band re-measure with 2 extra paid runs of each of 13 teammate tasks: 26 paid runs, > 4 days of cap, for a ranking we already have from stored report.json.
- R3 Q1 dropping rubric < 85: Ayush said keep unless evidence says otherwise; R3's own evidence says it is free (R3F:143).
- R5-02(d) automatic kill of a running paid run in the first fix: log-only first (Q18).
- R2 not-recommended items (files.autoSave, Docker engine switch, launchctl maxfiles).
- Editing the harness repo `H/scripts/package_rfp_bundles.py` (R1 T4 suggested a wrapper "next to" it): the wrapper lives in `MT/tools/` instead (A4), harness untouched.
- Re-scoring pushed tasks (sentinel 44.53, district 44.84) to < 40 on our own initiative: only when the QL asks to lower the score (Q2).
- Renaming LEVER_RULES to v4 / _COMMON_RULES to v6 (17 template edits) unless Q12 says so.
- A new P18 "tool change" template: code work uses one-off issued prompts; no repeat use yet.
- Promoting N1/N2 to PROVEN now: 8-9 tasks, 3 from one author, 1 hole (R3F); needs our own pilot.

## 7. Questions

See `QUESTIONS.md` (25 questions, grouped A-F, each with options and recommendation; settled items listed at the end).

## 8. Risks and conflicts with current rules

| Rule | Conflict | Handling |
|---|---|---|
| Never 10 / freeze after QC PASS (CR Never list, pipeline_v4 decision 1) | cold-chain and metered are predicted to miss < 40 but are frozen | run first, read trajectory, then harden (F1/F2); exception only by Q22 |
| No re-run on the same bytes (LR:215) | cold-chain's 17:41 run was invalid (no trajectory) | not a re-run of a valid run (REPORT.md:13); any later valid miss -> trajectory read-out, never a re-run |
| Regrade never push evidence (CR:65-66, KN:119, LR:215, pipeline_v4 decision 5) | sentinel was pushed on a regrade (R1F, DEC:390-400) | Q1: named exception with Ayush's verbatim OK per use, or keep the ban and fix the record |
| Law-1 (LR:87-88) | QL zip edits may add a lever that fails Law-1 | P17 CHANGES.md stops on any lever change not passing the kill table; P16 asks Ayush before any lever/rule change |
| Never 6 / Never 8 / Never 11 (stated rules, no trap explanation, no shipped answer) | LC1 induction, LC5 authority order, QL reply text | LC1 legal only with stated finite domain + EVIDENCE_MAP; LC5 order written once; reply template forbids trap/lever names (W1, CR:27) |
| Cap of 6 paid runs/day | QL reruns outside cap | ask Ayush each time; intake event `ql_rerun` keeps them countable; Budget rule still applies to the subscription limit |
| Time box 8 sessions (issue.py:36, 24 Oct U1) | pushed tasks in QL rounds would always be refused | A1 skips `ql` kind and resets at stage change; round caps kept; Q3 |
| Gate change mid-flight | issued prompts in `prompts/issued/` still say 50 | re-issue paused-task prompts after Batch 1; history rows not rewritten |
| Shared subscription | upgrade workers compete with task workers for the same limit | Batch 2 before resume; Budget: paid run first in a fresh window |
| In-place rules edit | loses old text if snapshot skipped | C0 snapshot + sha256 is step 1 of Batch 1 |

## Lessons for the master
- Gate < 40 needs tests <= 60 AND rubric <= 20 at design time; none of our 3 paused designs meets that today, so expect read-out/harden rounds, not first-run passes.
- Fix limit detection (E1) before any long auto run; the overnight loss was a blind watcher, not a bad task.
- Frozen bytes stay frozen: a predicted miss is still run once, then read out (unless Ayush makes an exception).
- R3/R4 statistics are research numbers; promote a lever to PROVEN only after it passes on our own frozen bytes twice.
- Keep rules edits in place with snapshots (v3.3-v3.6 precedent); 17 templates point at the current file names.
