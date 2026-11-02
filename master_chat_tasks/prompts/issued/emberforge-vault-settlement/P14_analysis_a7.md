# P14 Task analysis: emberforge-vault-settlement, trajectory attempt 7 (from template P14_task_analysis_v1, 23 Oct 2026)

=== PASTE BELOW ===

You are studying 1 finished Harbor 0.24 task of our own, emberforge-vault-settlement, after its seventh real trajectory run. The goal is to prove whether the low score is GENUINE (the agent misread a fully stated rule) or an ARTEFACT (permissions, harness, hidden rule, broken check), and to learn exactly where claude-opus-5 lost points. This is a trajectory autopsy (B1) of one task only. Board id: `5af6646`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/emberforge-vault-settlement/P14_analysis_a7.md`.

Why this matters: attempt 7 scored 27.31 / 29.63 / 25.0, which meets our gate (overall < 70, tests < 100, rubric < 100). Before we count it, we must be sure every lost point is a genuine misreading of a rule the agent could see. Attempt 4 scored tests 1.94 only because the delivered program was mode 0600 (not genuine), so permission artefacts are a known risk here. The harden lp1 r1 levers are L7 per-unit charge, L3 cap ledger (stateful stream) and L6 scope by definition (live window); two blind solves (P13 r1 Opus, r2 Codex) both scored tests 34.7 with failures on the four unseen seasons.

Read first:
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md` (sections 0-4)
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md`
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md`
- the `master_process` lines in `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/lessons.jsonl`

## Rules that survive compaction
- First thing: rename this session to `5af6646`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 5af6646
  If the list does not show it, note that in the report and carry on; never retry on another ID. Run it again as the last step.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- READ ONLY. No Docker, no harbor, no pip, no edits anywhere except OUT. Never edit the Anubis repo, the harness clone, our bundles, the WORK folder or the master records. Read-only git only (log/show/rev-parse). Never commit, push, pull or open a PR.
- You MAY run the agent's delivered program and our oracle locally with `python3` on copies placed under OUT (never inside the bundle or the job folder), to compare outputs. Standard library only.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` (one line per phase) and `OUT/LOG.md` (IST times) current after every step.
- Read files in pieces of at most 50 KB. `agent/trajectory.json` is large: use `python3`/`jq` to list steps (index, tool, command first 200 chars, output first 300 chars), then read only the steps you need. Never print a whole trajectory.
- Every claim has evidence: a quote with file:line, a trajectory step index, or command output. Anything inferred is marked INFERRED. Never guess a score.
- No repo HEAD to record (not a git checkout); write `"repo_head":"n/a"` and record `find "<task folder>" -type f -not -path '*/.git/*' | sort | xargs shasum | shasum` once as the bundle fingerprint instead.

## Inputs
| # | slug | task folder | recorded run (overall / tests / rubric) | run folder |
|---|---|---|---|---|
| 1 | emberforge-vault-settlement | `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement` | attempt 7 (23 Oct 20:30-21:12): 27.31 / 29.63 / 25.0 (8/22 tests) | `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_emberforge-vault-settlement/traj_a7/job/trajectory/claude-opus-5/Run 1` (job root one level up: `.../traj_a7/job`) |

History: attempt 1 (20 Oct, v0) 84.00 / 68.00 / 100; attempt 4 (21 Oct) 43.07 / 1.94 / 84.21, not genuine (0600 program); attempts 5 and 6 (23 Oct) failed on the Claude usage limit, no score. Use only these numbers for earlier attempts.

Recorded failures in attempt 7: all seven `whole_*` checks (w5: summary, vault_audit, reconciliation, data_quality, allocation, workshop_reports, guild_reports) differ on forge_a to forge_d (allocation only on forge_a and forge_d); `live_window_refusals` (w3) fails ("iso_live_window: the UNCREDITED_SALVAGE findings differs"); `unit_charge_season_total`, `cap_release_closures`, `mutation_family_multiplier`, `mutation_grade_step` and the four `structure_*` checks pass. Judge: R1 (multi-unit fractional charge season), R2 (cap after credited salvage season), R3 (window after credited forge season) failed; R4 passed; negatives R5-R8 did not fire.

Our own design notes (allowed here, this is our task): WORK = `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement` (DESIGN.md, LEVERS.md, PLAN.md, QC_DEFENCE.md, TRUTH.src.md, baselines.json, trap/, wrong/). Read LEVERS.md (the "Harden lp1 r1" section and later) and DESIGN.md to know what each lever was meant to catch.

Live QC kit for Phase B section 8: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (`01_Instruction_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`).
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_emberforge-vault-settlement/p14_a7`

## Phase A: is the score genuine?
Write `OUT/A_emberforge-vault-settlement.md` with a verdict GENUINE / ARTEFACT / PARTLY and the evidence:
1. `result.json` exception_info, agent timeout or step limit, verifier errors; `verifier/test-stdout.txt` and `reward-details.json` for tracebacks, `Permission denied`/`Errno 13`, `No such file`, timeouts, import or collection errors, skipped tests.
2. Permissions: the mode and owner of the delivered `/app/out/settle_vault.py` (from `artifacts/app/out` and the trajectory's last `ls -l`), and whether tests/test.sh or test_output.py runs it as another user. Rule out the attempt 4 artefact explicitly.
3. Did the verifier actually run the agent's program on the four hidden seasons? Show for each failing whole_* check that the program ran and produced the document (not missing, not a crash).
4. Root cause: copy the delivered program to OUT, run it and the oracle (`solution/solve.py`) on the shipped data and, if the test file can build them, on the hidden seasons; diff the documents. Name the FIRST divergent field and trace it to one rule. For that rule, quote every visible location (file:line). Verdict per divergence: GENUINE (rule fully stated, agent misread it) / HIDDEN RULE (not stated anywhere the agent sees) / CHECK BUG (oracle or test wrong).
5. Judge: did it read the trajectory? R1-R3 failed because no targeted season was built: is each criterion meetable (JD-7: the oracle trajectory meets it) and is it graded on behaviour, not a figure? Confirm from `judge_response.txt` that R5-R8 did not fire.
If ARTEFACT, write one paragraph and skip Phase B except instruction/test design worth noting.

## Phase B: how it is built and where points were lost
Write `OUT/B_emberforge-vault-settlement.md` with these sections:
1. **Inventory**: domain, archetype, files the agent sees (names, sizes, rows), instruction length (words), tests and weights, isolated vs whole-output checks, hidden seasons (how generated), judge criteria count and mode, reward split.
2. **Rule map**: every graded rule: ALL locations (file:line, quote); sentence form (one plain sentence / split across files / data header / example / implied by a definition / scope by omission / default + exception); trap explained in the text (Y/N); shipped data separates the readings (Y/N).
3. **Lever table** for L7, L3, L6 and every other failed check or criterion: id, weight, rule graded, the step where the agent first coded it (quote), right on the first write (Y/N), did a self-test touch it (Y/N, step), why it held or leaked, fully stated somewhere visible (if NOT: HIDDEN RULE, not allowed for us), family (A-F or NEW), nearest LEVER_RULES id.
4. **Contrast** with the two blind solves (`scores.jsonl` rows for 1cd546e and 0c22dae, their result files listed on BOARD.md): same failures or different? Did the real agent fail for the same reason?
5. **Agent behaviour** (trajectory autopsy): files read and order; did it read every rulebook fully; plan; minute of first full program write and whether graded logic changed after it; self-tests (data used, levers covered); where it hesitated or nearly went right; step count; time per phase; final claim vs reality.
6. **Test design**: how expected values are produced; partial credit; whole-document cascade (does one upstream misreading fail all seven whole_* checks, and is that a TS-26 double payment or a natural cascade per LEVER_RULES G1?); weight shares (use `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<task folder>"` and correct its hints).
7. **Judge design**: any criterion breaking JD-7/JD-8/JD-15/JD-18 (quote the rule).
8. **QC safety**: for each lever that cost points, would it pass our live QC? At least IN-15, IN-16, TS-13, TS-16, TS-19, TS-20, TS-26, AL-27, AL-28. SAFE / RISKY (why) / NOT ALLOWED. Compare with `knowledge/QC_RULINGS.md`.

## Phase C: summary
Write `OUT/GROUP_SUMMARY.md`:
1. Table: task, verdict A, overall/tests/rubric, genuine points lost on tests, genuine points lost on judge, artefact points.
2. **Root cause**: the one (or few) misreadings that cost the points, with step evidence and the rule quote.
3. **Would a QC reviewer call it fair?** One paragraph per lost lever: fully stated, reachable, not reflexive.
4. **Score artefacts** found in Phase A (or "none").
5. **Recommendation** for the master: COUNT (genuine, gate met), FIX (name the defect and the smallest fix), or RERUN (cannot tell from one run, say why).
6. Open questions for the master chat.
7. `## Lessons for the master` (max 5 lines).

`OUT/result_5af6646.json`: {"sha":"5af6646","group":"emberforge-a7","status":"DONE","repo_head":"n/a","bundle_fingerprint":"<sha>","tasks":[{"slug":"emberforge-vault-settlement","verdict":"GENUINE|ARTEFACT|PARTLY","tests":29.63,"rubric":25.0,"genuine_tests_points_lost":x,"artefact_points":x,"root_cause":"<one line>","levers":["L7|L3|L6|other"]}],"recommendation":"COUNT|FIX|RERUN","report":"<OUT>/GROUP_SUMMARY.md"}. The `sha` value is the board id. It must parse.

Final reply (10 lines max): verdict and why; root cause with the rule quote; which of L7/L3/L6 caught the agent; any artefact; recommendation; report path.
