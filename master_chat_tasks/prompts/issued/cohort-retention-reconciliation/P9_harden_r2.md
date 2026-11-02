# P9 harden r2: cohort-retention-reconciliation, issued 23 Oct 2026 00:50 IST (from template P9 v1; after trajectory a2 100/100/100)

You are hardening ONE Harbor 0.24 bundle from a real harness result: `cohort-retention-reconciliation`. Board id: `7cbd9f5`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/cohort-retention-reconciliation/P9_harden_r2.md`. This is harden round 2 of 3 (drop rule: 3 rounds without passing the gate = task dropped).

## Rules that survive compaction
- First thing: rename this session to `7cbd9f5`:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '%Board id: \`7cbd9f5\`%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='7cbd9f5' WHERE id='$SID'"; opencode session list | head -5
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `WORK/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Keep `WORK/TODO.md` and `WORK/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- Read first, in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`, then `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md` sections C, E, F, G, then `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_converted_batch_notes.md` section 4, then `WORK/DESIGN.md`, `WORK/LEVERS.md`, `WORK/QC_DEFENCE.md`, `WORK/XREF.md`, `WORK/baselines.json`.
- Never commit, push, pull or open a PR. Read-only git only. Never edit the harness clone, the QC kit, `QC assigned/`, `my tasks/`, the QC copy under `QC_*/bundles/`, or any `jobs/` folder. Edit only BUNDLE and WORK.

## Inputs
- BUNDLE (edit here): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cohort-retention-reconciliation`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cohort-retention-reconciliation`
- RESULT (read only, master's copy): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_cohort-retention-reconciliation/traj_a2/trajectory_job_cohort-retention-reconciliation_bb8ec0/`. Inside: `trajectory/claude-opus-5/Run 1/` (agent steps, `verifier/reward.json`, `reward-details.json`, `reward_raw.json`), `logs/pass-summary.json`.
- Score: claude-opus-5, tests 100.0, rubric 100.0 (judge RAN, 19/19 criteria met), overall 100.0; 20/25 checks passed, the 5 not passed are `negative_*` penalties that did not fire. Previous real run (v0, before harden r1): 58.67, lost only to the permission trap.
- QC kit (live rules): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` at HEAD 71a653b2 or newer. Record `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD` once.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_cohort-retention-reconciliation/harden_r2`

## Master's notes
- Gate for the next real run: tests < 100 AND rubric < 100 AND overall < 70. Design aim: a careful solver scores 0.10-0.20 on the tests channel.
- Harden r1 levers CR-1..CR-5 (families A + B + E + F) plus retained V0-1..V0-8 ALL leaked on a real run. Treat every one as LEAKED until the trajectory proves otherwise.
- Suspected cause (UNVERIFIED, prove or refute it): P12 r1 (board 0b8ac36) and the QC rounds may have made the task easier. Check whether they did: TRUTH/judge figures stated in the instruction, R4 "14 reason entries" exposure, the serialization check requiring the full doc set, solve.py rewrite, or rule text moved next to its use.
- The judge criteria are mostly "states figure X" (R1-R5...). An agent that runs its own program on shipped data meets them all. Replace them with criteria that need the full hidden-rule chain or that grade process quality from the trajectory's real mistakes (JD-7, JD-8, JD-15, JD-18).
- New lever set must NOT repeat A + B + E + F. Use levers A + B + 1-2 of C/D/E/F as defined in converted batch notes section 4 and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/levers.json` (prefer `held`, avoid `leaked`), with at least one of C/D so the set differs from r1, and several new levers. No hidden rules, no volume/arithmetic/puzzle difficulty. Every rule stays stated in the task files; difficulty comes from composition, scope by omission, split-across-files rules, decoy defaults contradicted on rare shipped boundaries, and dependent chains.
- Caps: 70 tests and 70 judge criteria, never exceeded. TS-20: do not set core weights to 1.

## Phase 1: diagnose (no edits)
Follow template P9 v1 Phase 1 (`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/P9_harden_from_results_v1.md`):
1. Per-check pass/fail from `reward-details.json`; map every check and every judge criterion to its lever via LEVERS.md. Table: lever, points available, points earned, HELD/LEAKED.
2. For each LEAKED lever, name what made it derivable (visible example, rule next to its use, a check the reflex reading passes, an agent self-test). Quote the trajectory step id or file line.
3. Compare with `baselines.json`: which solver S-k the agent matched.
4. Test the suspected cause above: diff the harden r1 state (tree sha in `baselines.json` / HARDEN_REPORT) against the current BUNDLE, and say which changes made it easier.
5. Steps where the agent went wrong or skipped verification: candidate judge criteria.
6. Write `OUT/DIAGNOSIS.md`, then STOP. Say "DIAGNOSIS READY: <path>" and wait for Ayush's "go" (he may pass on master changes).

## Phase 2: harden (after "go")
Template P9 v1 Phase 2, plus:
- Replace each LEAKED mechanism with one only hidden cases separate, or add separating hidden cases so the agent's reading fails. Several NEW levers, each with rule text, reflex reading, constructed hidden cases, and checks the wrong solver fails.
- Re-weight: rule-isolating checks at most ~30%, shipped-data-only checks at most 5%; grade whole downstream documents on reseeded hidden inputs; keep partial credit.
- Judge: rewrite as above; keep one honesty negative and one code-quality criterion; `[judge] mode = "batched"`.
- Keep the mandatory format: `chown root` + `chmod 755 /logs/verifier`, tests/Dockerfile pip line exactly `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`, `_grant_read` (H6/TS-30).
- Apply common rule 6 after any data edit. Update DESIGN.md ("Harden round 2"), LEVERS.md, TRUTH.md, QC_DEFENCE.md, XREF.md; run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/xref_check.py" "<BUNDLE>" "<WORK>/XREF.md"` until it prints 0 findings. Never rename the slug.

## Phase 3: verify, once
1. The 4 QC scripts (live kit), validator and playground static: 0 FAIL. QL rule: list each check changed in `git diff 2690e960 HEAD -- Input_Bundle_QC/` as PASS or FIXED.
2. Warm the verifier image first (round notes G). Then one Docker block, tests only, from copies built by the live kit's `exe_copy.py` (plain and `--owner-only`): oracle x3 = 1.000 (oracle x3 per Ayush, kit asks x5), owner-only x1 = 1.000, nop x1 = 0.000, stub, forgery. Clash rules (round notes G): bundle lock `/tmp/opencode-logs/locks/cohort-retention-reconciliation.lock`, TS with seconds + random hex, no `--delete`, one nohup chain with ALL_DONE, waits under 4 minutes, kill-by-uid only inside your own container.
3. Re-score S2, S4 and the solver matching the agent's a2 reading: S4 0.10-0.20, the agent's reading at 0.20 or below.

## Deliverables
- `OUT/DIAGNOSIS.md`, `OUT/HARDEN_REPORT.md` (before/after lever table, new checks, new judge criteria, weight shares, every gate result, what was not run, new baselines).
- `OUT/PL_NOTE.md` only if a design choice needs explaining to the PL.
- `OUT/result_7cbd9f5.json`: {"sha":"7cbd9f5","slug":"cohort-retention-reconciliation","step":"P9 harden r2","status":"DONE|DIAGNOSIS_READY|PAUSED","leaked":[],"new_levers":[],"families":[],"tests":N,"criteria":N,"isolated_share":x,"shipped_only_share":x,"oracle":[],"owner":x,"nop":x,"stub":x,"forgery":x,"s4":x,"agent_reading":x,"xref_findings":0,"qc_fail":0,"tree_sha":"<sha256 over sorted paths+contents, first 12>","report":"<path>"}. The `sha` value is the board id `7cbd9f5`, not a git sha. It must parse.

Final reply (10 lines max): levers that LEAKED and why (one line each), whether the P12/QC rounds made it easier, new lever ids and families, check and criterion counts, isolated share, oracle x3 / owner / nop / stub / forgery, S4 and agent reading, QC results, report path. Next step: master issues P11 v2 QC.
