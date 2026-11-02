# Harden lp1 r2 (leak fix after trajectory a5): district-heat-flex-procurement, issued 23 Oct 2026 13:02 IST

Board id: `eb6f232`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/district-heat-flex-procurement/P9_harden_lp1_r2.md`. Lever-plan round 2 of 3. Round 1 passed its local gate (old agent program 0.177), but a fresh claude-opus-5 scored tests 100 (trajectory a5). This round finds how each lever leaked to the fresh agent and closes it. QC folders now live under `/Users/mac/Desktop/Terminal Bench/QC/`; never write a `QC_*` folder at the root.

## Rules that survive compaction
- First thing: rename this session to `eb6f232`:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '%Board id: \`eb6f232\`%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='eb6f232' WHERE id='$SID'"; opencode session list | head -5
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
- BUNDLE (edit here): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement`
- RESULT (read only): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_district-heat-flex-procurement/traj_a5/job/` (`trajectory/<run>/Run 1/`: `agent/` steps, `verifier/reward-details.json`, `judge_response.txt`; `logs/pass-summary.json`). Score: a5 combined 81.25, tests 100, rubric 62.5, on the bundle after harden lp1 r1, P12 r2 (a3aeb84) and QC v5 (2fd95f2, 0/2/2). Previous round: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_district-heat-flex-procurement/harden_lp1_r1/` (DIAGNOSIS, STACKING_CHECK, HARDEN_REPORT; its agent program scored 0.177 locally, yet the fresh agent scored 100).
- Peer evidence (patterns only, never copy text/data/code): `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1..G5/GROUP_SUMMARY.md`
- Live QC kit: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (HEAD 71a653b2 or newer; record it once).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_district-heat-flex-procurement/harden_lp1_r2`

## Phase 1: leak diagnosis from trajectory a5 (no edits; do NOT stop after it)
1. Genuine check: clean run of the current BUNDLE tree (diff -rq the job's task copy against BUNDLE, ignoring judge-only files), no errors, judge read the response. If not genuine, stop and report "ARTEFACT: <reason>".
2. For EACH lever in WORK/LEVERS.md (L1, L2, L4, L7 and any older one still graded): find the trajectory step where the agent first applied the correct reading. Quote the step number and the agent's words/code. Name exactly what gave it away, one of: (a) the rule text is unambiguous enough that the reflex reading is never tempting (quote file:line); (b) a shipped example or file where the two readings differ (quote it); (c) the agent built its own check that exposed the wrong reading (quote it); (d) a test name, error message, schema hint or instruction phrase that points at the trap; (e) other (say what). Table: lever, step, agent quote, giveaway class, evidence file:line.
3. Explain the gap: why the round-1 agent program lost 0.82 locally while the fresh agent lost 0. If a lever only punishes a reading nobody takes, say so.
4. Save the a5 agent's final program as `OUT/agent_program/` (new reflex program; it must score <= 0.20 after Phase 2).
5. Write `OUT/DIAGNOSIS.md`, then continue (no "go" needed).

## Phase 2: harden per LEVER_PLAN_v1
- Fix the leaks found in Phase 1, lever by lever: class (b)/(d) remove or neutralise the giveaway; class (a) rework the lever so the wrong reading is the natural one a careful reader takes (the rule stays fully and singly stated, IN-15/IN-16); class (c) make the agent's natural self-check pass under the wrong reading (shipped data must not separate the readings). A lever that only punished a reading nobody takes is replaced by an unused LEVER_PLAN_v1 lever (L3, L5 or L6). Keep difficulty genuine: no hidden rules, no volume, no arithmetic burden, no puzzle. Fit each lever to the domain naturally. In `WORK/LEVERS.md`, record for each lever: rule text with file:line, reflex reading, constructed hidden cases, and the checks the wrong reading fails.
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
   - (c) run `OUT/agent_program/` (the a5 program, which scored 100) against the NEW tests locally and report its tests-channel score and the tests each misread fails. **It must score <= 0.20.** Also rerun `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_district-heat-flex-procurement/harden_lp1_r1/agent_program/` and report it. If not, strengthen the levers, max 2 tries, then stop and report "PILOT WEAK: <score>".
2. Run the 4 QC scripts, the validator and playground static with 0 FAIL. QL rule: list each check changed in `git diff 2690e960 HEAD -- Input_Bundle_QC/` as PASS or FIXED.
3. Warm the verifier image (round notes G), then one Docker block, tests only, from copies built by the live kit's `exe_copy.py` (plain and `--owner-only`): oracle x3 = 1.000 (oracle x3 per Ayush, kit asks x5), owner-only 1.000, nop 0.000, plus stub and forgery. Clash rules:
   - lock `/tmp/opencode-logs/locks/district-heat-flex-procurement.lock`;
   - TS with seconds + random hex;
   - no `--delete`, no prune;
   - one nohup chain with ALL_DONE; waits under 4 minutes;
   - kill-by-uid only inside your own container.
   Today the Docker max-2 rule is waived, but check `docker ps` and never start while 3 or more harbor runs are up.

## Deliverables
- `OUT/DIAGNOSIS.md`, `OUT/STACKING_CHECK.md`, `OUT/HARDEN_REPORT.md` (before/after lever table, counts, weight shares, gates, what was not run).
- `OUT/result_eb6f232.json`: {"sha":"eb6f232","slug":"district-heat-flex-procurement","step":"P9 harden lp1 r2","status":"DONE|ARTEFACT|PILOT_WEAK|PAUSED","leaks":{"<lever>":"<class a-e>"},"levers":[],"tests":N,"criteria":N,"isolated_share":x,"whole_doc_share":x,"shipped_only_share":x,"agent_program_score":x,"stacking":"PASS|FAIL","oracle":[],"owner":x,"nop":x,"stub":x,"forgery":x,"xref_findings":0,"qc_fail":0,"tree_sha":"<first 12>","report":"<path>"}. The `sha` value is the board id. It must parse.

Final reply (10 lines max): levers and where each rule is written, counts, weight shares, agent program score, stacking result, gates, report path. Next step: master issues P11 v2 QC.
