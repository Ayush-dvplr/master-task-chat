# R1 FINDINGS: the QL loop (board 086e1b4, 28 Oct 2026)

Scope: research and drafts only. Nothing in `master_chat_tasks/`, the harness, QC or Anubis was edited. Paths are relative to `/Users/mac/Desktop/Terminal Bench/` unless absolute. Short names: CR = `master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`, KN = `master_chat_tasks/knowledge/KNOWLEDGE.md`, PB = `knowledge/QC_FIX_PLAYBOOK_v3.md`, QR = `knowledge/QC_RULINGS.md`, LR = `knowledge/LEVER_RULES_v3.md`, DEC = `master_chat_tasks/decisions.jsonl`, H = `Terminal_2.0_Harbor_Harness/`.

## 1. How it works today

Team flow (KN:5): build, QC, 1 trajectory run, Anubis_Tasks_Samples, QL verify, Finalized_Tasks_RFP, 8 runs at final approval. Our QL is Sugam Agrawal (QR:141, DEC:208, DEC:265).

What already exists for the loop:
- The freeze rule. After a QC PASS nothing is hardened. Any later change goes only through the trajectory read-out, a QC recheck and 1 new run (CR:29 Never 10, LR:215). Push needs 1 valid run on the frozen tree sha that meets the gate. Any change after that run voids it (LR:210).
- The gate is tests < 85, rubric < 85, final < 50 (CR:49, CR:61, LR:89, `tools/intake.py:104`). Ayush lowered final to < 40 today, but that change is not written in any file yet.
- Fixing a QC report: P12 v4 has per-finding REAL / FALSE_POSITIVE / UNSURE with the kit rule ID and wording, and FIX / KEEP / REBUT lines that cite a playbook row (`prompts/templates/P12_recheck_fix_v4.md:7,43-57`). It also has the G1-G7 guards (PB:62-71), trap survival (PB:81-86), precheck CLEAN, and a Docker block of oracle x3 = 1, owner-only x1 = 1, nop x1 = 0 (P12:59-67). The next step is a P11 v3 recheck in MODE recheck, with carry-over against the previous copy (P11:3, STEP 0.4; QR:149-150).
- P8 v2 is the old "PL full QC report" recheck (P8:1-9). It is still the closest template to a QL report, but it reads the stale `_COMMON_RULES.md` (P8:9; P7:9 has the same problem).
- QL rulings are kept as rows in QR (CL-5 QL ruling QR:40-43, QL answers QR:141-147). There is no FP_DOSSIER yet. INDEX.md:14 says it is created when the first row lands.
- Trajectory read-out: `tools/trajectory_readout.py <run> --out TRIP.md` (KN:106-119). I checked it on the packaged layout: it reads `Output_RFP/sentinel-policy-recompute/trajectories/claude-opus-5/run_1` and wrote 28 rows, final 44.53, TIMEOUT 28 (command output, /tmp/R1-ql-loop-scratch/TRIP_rfp.md). So it works as-is on the run_N folders a QL zip carries.
- Harness queue: `auto.py harness BUNDLE` (`master_chat_tasks/auto/auto.py:1038-1081`) refuses when the harness is busy. It diffs BUNDLE against `H/Tasks_INPUT/<slug>` before and after `scripts/master_queue.py add`, and fails if they differ after the add (:1067-1077). A rerun of a slug archives the old job and bumps the attempt (`H/scripts/master_queue.py:166-167,353-366`).
- Packaging: `H/scripts/package_rfp_bundles.py` is the only delivery builder (:20). It copies environment/solution/tests from the bundle recorded in each run's `config.json task.path` (:15,152,236). It copies scores and never recomputes them (:70-92). Its `main` walks the whole jobs tree (:189,273-280). A one-task repackage was done in the sentinel precedent by importing `_package_run()` / `_score_from_report()` on a copy (`master_chat_work/20261028_sentinel-policy-recompute/regrade_r13_188771e/REGRADE_REPORT.md:119`).
- "Regrade only" precedent (sentinel, 28 Oct): Ayush relayed PL feedback "rubric must not be zero" (DEC:390-391). The session made one line edit to judge.toml:170 with no QC (REGRADE_REPORT.md:10-18), then precheck plus the 4 kit scripts (:29-36), synced Tasks_INPUT, and ran `harbor trials regrade` on a /tmp copy of `jobs/<slug>/trajectory/claude-opus-5/Run 1` against a staged task copy (:38-52). Regrade 1 gave rubric 0 (R16 flipped), so it stopped. Ayush chose option b (DEC:396), and regrade 2 met the gate at 44.53 (:89-114). It then backed up Output_RFP trajectories, cp'd judge.toml, rebuilt run_1 with the harness finalize scripts on a copy, and wrote before/after sha listings (:116-124). Ayush re-pushed (DEC:400).
- "Harden + QC + run" precedent (district, 28 Oct): a11 missed the gate, so a judge-only harden followed (`master_chat_work/20261028_district-heat-flex-procurement/harden_judge_8d509b8/HARDEN_REPORT.md`: tests unchanged, predicted final 42.75, oracle 1x3, owner 1, nop 0, tree 34a4d2f3e198). Then QC v9 PASS, freeze e9d91966ed25, run a12 at 44.84, and push (registry `tasks.json` district next field; DEC:400).
- Registry: both pushed tasks have stage `pushed`, next "wait for QL review" (registry/tasks.json). `tools/status.py:22` FIELDS has no tree_sha and no QL fields.

## 2. Gaps and risks

1. **The regrade rule conflicts with practice.** CR:65-66, KN:119 and LR:215 say a regrade is "never push evidence, never packaged". Sentinel was re-pushed on regrade 2 because Ayush told us to (DEC:391,396,400). The QL loop's "regrade only" path will hit this conflict every time (Q1).
2. **The gate change to final < 40 is not in any file.** It still reads 50 in CR:49,61, LR:89,210 and `tools/intake.py:11,104,106`. Both pushed tasks sit above 40 (sentinel 44.53, district 44.84; registry). If the QL asks to "degrade", they fail the new gate and cannot be fixed by regrade alone (Q2).
3. **`issue.py` has no QL kind and its refusals do not fit pushed tasks.** KINDS (`tools/issue.py:34`) has no `ql`. The `passed` set is `qc_pass, gate_runs, pl_ready` (:71), so a QC or harden on a `pushed` task is NOT refused. That is probably an accident, but the QL loop needs it. The time box (8 sessions, :19,:89) WILL refuse pushed tasks: sentinel needed a cap override at 26 sessions (DEC:390).
4. **`intake.py` cannot record a QL rerun.** `--event` allows only probe, gate_run, run (:124). The note row (:108) has no tree_sha, so the freeze-to-run link has to be checked by hand (KN:94-99 asks for it at every intake). INFERRED: QL-requested reruns outside the cap of 6 cannot be told apart in the log.
5. **There is no inbound home for QL material.** No folder or naming rule exists for a pasted QL report or a QL zip. QR stores rulings only. The FP_DOSSIER file is absent (INDEX.md:14), yet CR:45 and PB:58 send keeps there.
6. **P7 v2 and P8 v2 are stale.** They read `_COMMON_RULES.md` (v1) at P7:9 and P8:9, and have no playbook rows, G1-G7, carry-over or trap survival. A QL report fed through them would skip today's guards.
7. **Packaging risk on repackage.** `package_rfp_bundles.py` takes task files from `config.json task.path` (:15,152). After a regrade that path is a /tmp staged copy (REGRADE_REPORT.md:123), so running the packager later could pick up a vanished or edited path. `main` touches every job (:189). The single-task import route has no tool wrapper (Q5).
8. **A QL zip can be older than our bytes or touch locked files.** Nothing today compares a zip's tree sha to the frozen sha, Tasks_INPUT or Output_RFP. W1 / IN-17 (CR:27), IN-15 (CR:25), Law-1 (LR:87-88) and the freeze (CR:29) all apply to his edits as much as to ours. UNVERIFIED: whether the QL's zip layout equals Output_RFP's (`<uuid>/README.md instruction.md task.toml environment solution tests trajectories/`, package_rfp_bundles.py:9-12). The live Output_RFP folder for sentinel has no README.md (ls), so the docstring and reality already differ.
9. **The paid run cap.** The daily cap of 6 and "ask Ayush before each QL rerun" are not in any tool. `auto.py harness` checks only concurrency (:1047-1054).
10. **Regrade variance.** One regrade is one sample: borderline negatives flip on the byte-identical reply (REGRADE_REPORT.md:84,127). A "regrade only" request should say this to the QL before he reads the score as final.

## 3. Part A flow: a QL QC report pasted in chat

1. **Intake (master, no session).** Save the pasted text verbatim to `master_chat_work/_ql/<slug>/<YYYYMMDDTHHMM>_report/QL_REPORT.md` with a header line holding IST time, sender, task, and the frozen tree sha from the registry. Number findings `QL<n>-F<k>` in the order given (n = QL round for this slug). Record the tree sha of BUNDLE, Tasks_INPUT and Output_RFP (-x trajectories) with the command REGRADE_REPORT.md:7 uses. If they differ, stop and ask. Add a registry `next` note: "QL round n received".
2. **Triage session (draft P16).** A new session runs on a read-only copy. For each finding it quotes the finding, names the kit check by ID and wording (`qc_reverse/A/checks.json` kit file:line), cites bundle file:line, and runs the script-owned check. It also checks QR, FP_DOSSIER and QC_DEFENCE, plus the carry-over rule (QR:149-150): a finding on an unchanged line that our last QC PASSed or KEPT needs a live kit line the earlier reason misses. Each finding gets one label: REAL, FALSE POSITIVE, PARTLY (real core, wrong scope or fix), or OUT OF SCOPE (asks for something no kit line demands, or a SUGGEST, PB:53). The output is TRIAGE.md, plus master FIX / KEEP / REBUT lines in PB:73-79 format for every REAL or PARTLY finding. If there are no real findings, skip to step 6.
3. **Master check, then ask Ayush.** Ask Ayush only when a REAL fix touches a lever (PB lever effect harder or easier), or when a finding asks for a rule change. Otherwise issue the fix.
4. **Fix (P12 v4 as-is, with the QL report as QC_REPORT and our last QC copy as PREV_QC_COPY).** "No new error" proof, all already in P12:59-67: G7 byte diff of changed files, precheck CLEAN, the 4 kit scripts, stacking_check, trap survival, and Docker oracle x3 = 1 / owner-only x1 = 1 / nop x1 = 0. The stub score is recorded in result json.
5. **QC recheck.** P11 v3 MODE recheck against our last QC copy (P11 STEP 0.4). PASS means freeze: write the new tree sha into the registry.
6. **Ask Ayush before the run**, because it is outside the daily cap. On yes: `auto.py harness <BUNDLE>`, then intake with `--event ql_rerun` (spec) and a trajectory read-out. If the gate is met, repackage the one task (spec T3) with the sentinel step 6 method: back up `trajectories/`, take before/after sha listings, keep Output_RFP (-x trajectories) equal to Tasks_INPUT equal to the frozen tree. Registry: stage `pushed` (after Ayush says pushed), tree_sha, ql_round, traj_* fields. If the gate is missed, use the KN:118 path (no re-run of the same bytes) and ask Ayush.
7. **Reply to the QL.** `master_chat_work/_ql/<slug>/<TS>_report/REPLY_QL.md` from QL_REPLY_TEMPLATE.md. Each finding gets a verdict, its evidence, what changed (file:line before → after), and the run result. Plain language, no lever, trap or internal tool names (CR:27 W1 applies to the reply too). FALSE POSITIVE rows also become FP_DOSSIER rows and, when the QL agrees, a QR ruling row.

## 4. Part B flow: QL zip handback

1. **Safe intake (master or P17 Phase 0).** Copy the zip to `master_chat_work/_ql/<slug>/<TS>_zip/` with its sha256, then `unzip -q` into `/tmp/ql-<slug>-<TS>/x/`. Refuse absolute paths or `..` (`unzip -l` first). Write INVENTORY.md: every file with sha256, size and path; the bundle root (the folder holding task.toml); whether `trajectories/` is present and which run_N it has; and the tree sha of the bundle part (-x trajectories).
2. **Diff.** `diff -rq` and `diff -U0 -r` of the zip bundle against the frozen Tasks_INPUT and against Output_RFP (-x trajectories). Write CHANGES.md with one line per changed file: what changed, and which of instruction / tests / judge / data / solution / env it touches. Every change is classed as his edit, ours-newer (our bytes are newer than his base), or packaging-only.
3. **Conflicts. Any of these stops the session and asks Ayush:**
   - His edit states a trap rule or explains a trap (W1 / IN-17, CR:27), changes rules of engagement (IN-15), or adds a lever the Law-1 filter would drop (LR:87-88).
   - His edit lands on a frozen file while we have an unpushed fix on the same file. Use a 3-way diff (frozen base, ours, his) and record which hunks overlap.
   - The zip's base is not our newest pushed tree: its unchanged files differ from frozen Tasks_INPUT. That means the zip is older than our newest bytes.
   - Any change at all to tests/ or judge.toml, which voids the run under LR:210 and needs a new run.
4. **Four request paths:**
   - **Trajectory only:** no byte change. Run the read-out on the zip's run_N (works, §1). Report TRIP and the gate with the new final < 40 rule. If the zip also has edits, the trajectory is not evidence for those bytes. Say so and ask.
   - **Regrade only:** the sentinel method (REGRADE_REPORT.md:38-124). Stage a copy of Tasks_INPUT plus his edits and the a-run staging lines, copy the source trial from `jobs/<slug>/trajectory/claude-opus-5/Run N`, and run `harbor trials regrade` once. Stop if rubric is 0 or the gate is missed, otherwise run step 6 Output_RFP. Allowed only for judge.toml or other non-test edits that Ayush clears (Q1). In Output_RFP the following change: tests/judge.toml, run_N/{config,report,result}.json, verifier/{reward*,score}.json, test-stdout.txt, and pass_summary.json. Agent trajectory and artifacts stay byte-identical.
   - **Lower the score (harden):** with trajectories, P9 v4 from the zip's run (TRIP first). Without trajectories, harden blind: 3 × P13 v2 blind solves on the zip's instruction and environment, then the harden session (P9 v4 with the blind programs as the "run"), then P11 v3 full QC, freeze, ask Ayush, 1 run. Target final < 40.
   - **QC + fix his changes:** P11 v3 MODE recheck with PREV_COPY = our last QC copy (`QC/copies/<sha>/<slug>`), so CHANGED_LINES = his edits only. Then P12 v4 on the findings, recheck, freeze, ask, 1 run.
5. **After any path:** sync BUNDLE, Tasks_INPUT and Output_RFP; registry tree_sha and ql_round; write REPLY_QL.md.

## 5. Drafts

All in `OUT/drafts/`:
- `P16_ql_report_triage_v1.md`: Part A triage session (read-only, labels + master directions block).
- `P17_ql_handback_v1.md`: Part B intake, diff, conflicts and path routing (no edits, no runs; stops for Ayush).
- `QL_REPLY_TEMPLATE.md`: the reply to the QL.
- `MASTER_STEPS.md`: the master's checklists for A and B, including asks and the cap.
- `TOOL_CHANGE_SPECS.md`: the issue.py, intake.py, status.py, rules-text and packaging-wrapper changes (anchors, no code).

## 6. Questions for Ayush

1. A regrade the QL or PL asks for: may it be push evidence and be packaged (as sentinel was, DEC:400), when the edit is judge-only and you say so? Recommended: yes, judge-only edits and only on your word. Write it as a named exception in CR:65-66, KN:119 and LR:215.
2. The new gate final < 40: does it apply to tasks already pushed at 44.53 and 44.84 when the QL hands them back? Recommended: only when the QL asks for a lower score. Otherwise keep the gate they were pushed under.
3. Should a QL rerun count as a new kind in issue.py (`ql`), with the time box skipped for pushed tasks and your yes logged per run? Recommended: yes (spec T1).
4. QL inbound home: `master_chat_work/_ql/<slug>/<TS>_{report|zip}/`. Recommended: yes.
5. Repackaging one task: should we add a small harness-side wrapper over `_package_run()` that is used only for one slug (spec T4), or keep the hand method from sentinel? Recommended: wrapper, because the hand method needs about 8 manual steps.
6. FALSE POSITIVE replies: do we wait for the QL's agreement before writing a QR ruling row, and write the FP_DOSSIER row at once? Recommended: yes.
7. If his zip edits a test or judge file of a pushed task, a new paid run is required (LR:210). Do we ask you each time even when he asked only for "trajectory only"? Recommended: yes, and tell the QL the trajectory does not cover his edits.

## Lessons for the master
- The rules say regrades are never packaged, but sentinel was packaged on your word. Settle it as a written exception before the first QL regrade | template_change: _COMMON_RULES_v5.md:65-66, KNOWLEDGE.md:119, LEVER_RULES_v3.md:215
- The final < 40 gate exists only in chat | template_change: _COMMON_RULES_v5.md:49,61; LEVER_RULES_v3.md:89,210; tools/intake.py:104
- issue.py time box (:89) blocks every pushed task, so QL work needs kind `ql` | template_change: tools/issue.py:34,71,89
- P7/P8 v2 read the v1 rules; never use them for QL reports, use P16 then P12 v4 | template_change: P8_fail_recheck_v2.md:9 (retire)
- trajectory_readout.py already works on Output_RFP/zip run_N layout | no change: verified by run on sentinel run_1
