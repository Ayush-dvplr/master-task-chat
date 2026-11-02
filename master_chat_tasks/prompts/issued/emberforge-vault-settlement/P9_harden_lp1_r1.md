# Harden r1 under LEVER_PLAN_v1: emberforge-vault-settlement, issued 23 Oct 2026 12:40 IST

First bundle after the 3 pilots, run as an exception to the pilot hold (Ayush 12:35). Board id: `e215748`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/emberforge-vault-settlement/P9_harden_lp1_r1.md`. Lever-plan round 1 of 3 (the two older harden rounds, 21-22 Oct, came before LEVER_PLAN_v1). QC v5 (67848e1) was 0/0/1; keep it clean.

## Rules that survive compaction
- First thing: rename this session to `e215748`:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '%Board id: \`e215748\`%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='e215748' WHERE id='$SID'"; opencode session list | head -5
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `WORK/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Keep `WORK/TODO.md` and `WORK/LOG.md` current after every step. Read files in pieces of at most 50 KB; list trajectory steps with python/jq, never print a whole trajectory.
- Read first, in full:
  - `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`;
  - `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md` sections C, E, F, G;
  - `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/LEVER_PLAN_v1.md` (THE authority for levers, writing, grading and judge);
  - `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_cohort-retention-reconciliation/harden_r2/DIAGNOSIS.md` section 0 (how levers leaked);
  - then `WORK/DESIGN.md`, `LEVERS.md`, `QC_DEFENCE.md`, `XREF.md`.
- Never commit, push, pull or open a PR. Read-only git only. Edit only BUNDLE and WORK. Never edit the harness clone, the QC kit, `QC assigned/`, `my tasks/`, `QC_*/bundles/`, `jobs/`, or the Anubis repo.

## Inputs
- BUNDLE (edit here): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement`
- RESULT (read only): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_emberforge-vault-settlement/baseline_v0/trajectory_job/trajectory/claude-opus-5/Run 1/` (agent steps, `verifier/reward-details.json`). This is the v0 trajectory (corrected Docker replay: tests 94.19, rubric 84.21); it PREDATES harden r1 and r2. Earlier rounds: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_emberforge-vault-settlement/harden_r1`, `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_emberforge-vault-settlement/harden_r2` and `p12_r1..r3` (read their reports first).
- Peer evidence (patterns only, never copy text/data/code): `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1..G5/GROUP_SUMMARY.md`
- Live QC kit: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (HEAD 71a653b2 or newer; record it once).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_emberforge-vault-settlement/harden_lp1_r1`

## Phase 1: short diagnosis (no edits; do NOT stop after it)
1. Baseline first: the v0 run predates two harden rounds, so do not treat it as the current score. Save its final program as the reflex program (step 3) and score it on the CURRENT tests (tests channel). If it already scores <= 0.20 AND the current tests already meet G1-G7, write that in DIAGNOSIS.md, skip Phase 2, and go straight to Phase 3 (status ALREADY_HARD).
2. A lever table from `reward-details.json` plus the trajectory: each existing lever, the step where the agent got it right, and what gave it away (rule next to its use, trap explained, shipped separating example, self-test).
3. Save the agent's final program (from the trajectory or `/app/out`) as `OUT/agent_program/`. It is the reflex program for step 5.
4. Write `OUT/DIAGNOSIS.md`, then continue (the cause is already known; no "go" is needed).

## Phase 2: harden per LEVER_PLAN_v1
- Levers for this task: L3 (stateful stream: the requisition ladder and forge caps are an ordered ledger) + L6 (scope carried by a definition) + L7 (per-item rounding unit), plus L1 (green control, wrong answer) only if the shipped data already carries a natural control. The pilots used cohort L1+L2+L3+L4/L5, vendor L2+L3+L5+L6, district-heat L1+L2+L4+L7, so no full set is repeated. Keep existing levers in WORK/LEVERS.md that still separate (LV-EF-1..4, L8); retire any the Phase 1 table shows leaked. Fit each lever to the domain naturally. In `WORK/LEVERS.md`, record for each lever: rule text with file:line, reflex reading, constructed hidden cases, and the checks the wrong reading fails.
- Writing W1-W7:
  - never explain the trap; no trap lists or rule counts in the instruction;
  - each rule in the file that governs its data;
  - overrides name the field exactly;
  - no worked example where the two readings differ.
  Every rule must be fully stated with one reading (IN-15, IN-16). Remove the old giveaways found in Phase 1.
- Grading G1-G7:
  - one test per downstream document on hidden reseeded inputs, each asserting only its own document;
  - isolated rule checks on supplied correct inputs, no whole-set asserts;
  - weight shares: isolated <= 30%, whole-document on hidden inputs >= 50%, shipped-only <= 5%;
  - negatives grade only cheating, at most 5 per act across both layers;
  - the instruction states "each output document is graded whole on fresh inputs";
  - at least 2 mutation tests on governed constants;
  - assertion messages recorded in ctrf;
  - caps 70/70; core weights never 1.
- Judge J1-J5:
  - no "states figure X" criteria;
  - one w3 conduct criterion per lever ("constructs its own input in which <case the shipped data lacks> and checks <observable>"; accepted under JD-7);
  - one honesty negative;
  - one named-shape code-quality criterion;
  - no criterion endorses a reading the tests penalise;
  - `[judge] mode = "batched"`.
- Mandatory format kept:
  - `chown root` + `chmod 755 /logs/verifier`;
  - tests/Dockerfile pip line exactly `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`;
  - `_grant_read` (H6/TS-30).
- Apply common rule 6 after any data edit. Update DESIGN.md ("Harden lp1 r1"), LEVERS.md, TRUTH.md, QC_DEFENCE.md, XREF.md. Run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/xref_check.py" "<BUNDLE>" "<WORK>/XREF.md"` until it prints 0 findings. Never rename the slug.

## Phase 3: STACKING_CHECK, then gates (once)
1. `OUT/STACKING_CHECK.md`:
   - (a) one row per test: id, weight, observable, decisive logic, and the levers whose misreading fails it. No two rows may share both observable and logic (TS-26); one property per test (TS-13);
   - (b) penalty groups by act across tests and judge, each sum of |w| <= 5 (AL-28);
   - (c) run `OUT/agent_program/` against the NEW tests locally and report its tests-channel score and the tests each misread fails. **It must score <= 0.20.** If not, strengthen the levers, max 2 tries, then stop and report "PILOT WEAK: <score>".
2. Run the 4 QC scripts, the validator and playground static with 0 FAIL. QL rule: list each check changed in `git diff 2690e960 HEAD -- Input_Bundle_QC/` as PASS or FIXED.
3. Warm the verifier image (round notes G), then one Docker block, tests only, from copies built by the live kit's `exe_copy.py` (plain and `--owner-only`): oracle x3 = 1.000 (oracle x3 per Ayush, kit asks x5), owner-only 1.000, nop 0.000, plus stub and forgery. Clash rules:
   - lock `/tmp/opencode-logs/locks/emberforge-vault-settlement.lock`;
   - TS with seconds + random hex;
   - no `--delete`, no prune;
   - one nohup chain with ALL_DONE; waits under 4 minutes;
   - kill-by-uid only inside your own container.
   Today the Docker max-2 rule is waived, but check `docker ps` and never start while 3 or more harbor runs are up.

## Deliverables
- `OUT/DIAGNOSIS.md`, `OUT/STACKING_CHECK.md`, `OUT/HARDEN_REPORT.md` (before/after lever table, counts, weight shares, gates, what was not run).
- `OUT/result_e215748.json`: {"sha":"e215748","slug":"emberforge-vault-settlement","step":"P9 harden lp1 r1","status":"DONE|ALREADY_HARD|PILOT_WEAK|PAUSED","levers":[],"tests":N,"criteria":N,"isolated_share":x,"whole_doc_share":x,"shipped_only_share":x,"agent_program_score":x,"stacking":"PASS|FAIL","oracle":[],"owner":x,"nop":x,"stub":x,"forgery":x,"xref_findings":0,"qc_fail":0,"tree_sha":"<first 12>","report":"<path>"}. The `sha` value is the board id. It must parse.

Final reply (10 lines max): levers and where each rule is written, counts, weight shares, agent program score, stacking result, gates, report path. Next step: master issues P11 v2 QC.
