# Batch notes: converted-task harden-rebuild r1 (master chat, 22 Oct 2026 15:50 IST)

Every converted-task prompt issued on 22 Oct tells you to read this file in full, AFTER `20261022_round_notes.md`. This file overrides the round notes where they differ. If this file and your own prompt disagree, stop and report the conflict.

## 1. Scope and source (Ayush decisions 15:43, Q42)
- 12 tasks from `/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/`. emberforge (covered by S12) and 07d51b69 (dropped) are out.
- `QC assigned/` is READ ONLY. Copy the task once into `master_chat_work/bundles/<slug>/` (`cp -Rp`), then work only on the copy. If the copy already exists, do not copy again; continue from `_work/<slug>/TODO.md`.
- Most of these tasks already went through QC fix rounds (`QC assigned/qc_report/<slug>/` v1..vN, triage, fixplan). Treat the latest `vN.md` + `fixplan_vN.md` as the QC history, but re-check against the live QC: the QC has moved since (section 2).
- Flow per task: this session = harden-rebuild + gates. Then Ayush: PL QC -> P8 recheck of FAILs -> P7 fix of REAL only -> 1 trajectory. Not your job here.

## 2. Upstream state (overrides round notes section A)
- Expected harness HEAD = `f3765e67` (Ayush pulls it before you start). Check with `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD`. If HEAD is older than `f3765e67`, stop and say "PULL NEEDED". If newer, record it and continue (section 8). Read-only git only.
- QL rule (16:00 22 Oct): QC against ALL `Input_Bundle_QC/` changes since `2690e960` (a72c20a4, a74bda85 K8, c9e3454a H6/TS-30, d9f94333 G2, f3765e67 H6 interpreter switches) and fix every issue before any trajectory. Read `git -C <clone> diff 2690e960 HEAD -- Input_Bundle_QC/` once and list every changed check in HARDEN_REPORT.md with PASS/FIXED.
- f3765e67: H6 now skips interpreter switches (e.g. `python3 -u prog.py`) when locating the executed program; re-run tests_qc after your permission fix.
- d9f94333 changes one thing: `tests/judge.toml` `[judge]` header now has `mode = "batched"` (was `individual`); judge_qc.py G2 FAILs otherwise. Match the header in `Input_Bundle_QC/Final_checklist.md` exactly.
- From c9e3454a, still binding: H6 / TS-30 (any check that runs an agent-written program under a dropped uid must make it readable first; use the templates' `_grant_read()` pattern), the owner-only oracle run (`exe_copy.py --owner-only`) in Step 10.
- Every converted bundle today (verified by the master 15:38): `chmod 755 /logs/verifier` (keep it), NO `_grant_read`, NO `litellm==1.105.0` pin. So each one needs: the K8 pip line exactly `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`, the permission fix, and the judge header change.

## 3. Evidence you have
- One real claude-opus-5 trajectory per task, 19-21 Oct, in the OLD clone: `/Users/mac/Desktop/Terminal Bench/Harbor_Harness/Terminal_2.0_Harbor_Harness/jobs/<slug>/trajectory/claude-opus-5/Run 1/` (`agent/trajectory.json`, `artifacts/`, `verifier/{reward.json,reward_raw.json,ctrf.json}`). Copy (never move) the whole `jobs/<slug>/` folder to `OUT/baseline_v0/trajectory_job_<slug>_<first 6 hex of sha256 of its result.json files concatenated>/` before reading; the job folder can be overwritten.
- The reward recorded is the combined reward and was produced with no judge key (`reward_raw` only). First establish from `ctrf.json` / `reward.json` the tests-channel score and whether the judge half was skipped, zero or scored. Label every score "tests-only" unless a judge result is actually present.
- Check whether the permission trap depressed the score (a test that ran an agent program as another uid and hit Errno 13 / PermissionError). If yes, the real tests score is higher than recorded; estimate it by reading, and say UNVERIFIED.

## 4. Hardening (what "harden" means here)
- Apply round notes section B in full (the 13 study rules are binding).
- Levers: every task uses families A + B plus 1-2 of C/D/E/F, as defined by `family` in `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/levers.json`. Read that file: prefer levers with status `held`, avoid `leaked`, and do not copy another task's full lever set. Each new lever needs: rule text, the reflex reading, constructed hidden cases, and checks the wrong reading fails. Measure every lever (map each check to a lever in `WORK/LEVERS.md`).
- No hidden or unwritten rules; no volume, arithmetic, puzzle or formatting difficulty; instruction stays plain and short and states the end state.
- Judge: outcome facts the agent states, failable, no overlap with tests (JD-8), true of any correct run (JD-7) and met by every competent route (JD-15), one code-quality criterion (JD-18), one honesty negative. A stated-fact criterion needs the instruction to ask for that fact plainly. Do not set core tests to weight 1 (TS-20). Caps: 70 tests, 70 criteria.
- Target: careful-solver tests score 0.10-0.20 with partial credit kept; per-run gate tests < 90, rubric < 90, overall < 30.

## 5. Converted-task specifics
- No generator archetype: `validate_bundle.py` is advisory only (open Q23). Report its result; fix only cheap ones.
- There is no `_work/<slug>/` yet. Create `master_chat_work/bundles/_work/<slug>/` with `DESIGN.md` (reconstructed from the bundle + conversion notes), `LEVERS.md`, `baselines.json`, `TODO.md`, `PLAN.md`, `LOG.md`. Conversion history: `/Users/mac/Desktop/Terminal Bench/QC assigned/converted_tasks_report/<slug>.conversion_notes.md` and `<slug>.verify.md`.
- If the bundle carries a datagen or embed script, follow round notes E (update and regenerate, or edit directly and mark stale). After any data edit apply common rule 6 (re-embed `_SHIPPED_DATA`, recompute `reward.toml` `0.5/P` per channel, update every sha256 in TRUTH.md).

## 6. Gates (round notes D, Q29 C still in force)
Run once each: the 4 QC scripts 0 FAIL; validator (advisory); `exe_copy.py` then tests-only in Docker: oracle x2 = 1.0, `--owner-only` oracle = 1.0, oracle with every delivered program `chmod 600` = 1.0, nop x1 = 0.0; tests-channel forgery <= 0.05; judge "not run", checked by reading. Max 2 Docker runs at once on this Mac (another rebuild session may be running; check `docker ps` and wait if 2 are up). Background long runs with logs under `/tmp/opencode-logs/<slug>-<ts>/`; never wait on one command longer than 4 minutes.

## 7. Never
Commit, push, pull, open a PR, edit the harness clone, edit `QC assigned/` or `my tasks/`, run a stale `_work` script, read or touch `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214`.


## Kill-by-uid caution (master 20:45, from S10/S11 Docker runs)
kill-by-uid hits every process of that uid, including other checks running in parallel: the first oracle runs scored 0.11-0.28. Serialise every check that runs agent code under the dropped uid (a file lock around each run) or kill only the run's own process group/session. Re-check oracle x2 after adding it.


## 8. Added 21:40 (sessions starting after 21:40)
Read round notes sections F and G in full and apply them: write `_work/<slug>/QC_DEFENCE.md` and `XREF.md` while you harden (for converted tasks reconstruct the design intent from the bundle, conversion notes and the trajectory; mark inferences INFERRED), run xref_check.py before the gates, write `OUT/result_<sha>.json`, follow the clash rules. Expected harness HEAD is now `3fb1650b` (T14 author-name check, harmless); a newer HEAD: record it and continue.
