# Trajectory-driven hardening: how it can be done (READ-ONLY research) — cb612aa
First thing, rename this session: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" cb612aa` (if the output does not show cb612aa, note it in the report and carry on; never retry on another ID).

This prompt: /Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261027T1717_sentinel-policy-recompute.md. Your only writable place is OUT: /Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/trajectory_hardening/research_cb612aa

## Ayush's idea, in his words and as clarified
"trajectory folder ... contains all the information that we can use to check where the model tripped; take the flow in that, or slightly modify weights or add tests or rubrics in that directly for getting the desired score." Clarified answers:
- Allowed change kinds (all of them): re-weight existing checks; add tests at the points where the model tripped; add judge criteria; remove or down-weight what it passed easily. "Doing everything is legal but it must be QC pass after doing this, so check and verify with QC too." You do NOT run QC; you research how each change can be made so that it would pass QC.
- When: after a probe misses our gate.
- Push rule (Ayush, 27 Oct): push needs only 1 run on the QC-passed bundle that is under our gate (tests < 100 AND final < 70).
- Analyze BOTH ways of using a trajectory:
  - A. Re-grade the SAME saved run: change only tests/judge/weights (instruction.md and environment/ byte-identical) and re-score the saved trajectory and saved /app artifacts, with no new agent run.
  - B. Tune the bundle from the trajectory, then 1 NEW harness run on the QC-passed bundle.

Your job is to find out, from the files, what is possible and legitimate. Do not assume. Every claim cites a file path and line, a score row, or a QC rule ID with kit file:line. If you cannot find evidence, write UNKNOWN and say what single check would settle it.

## Hard rules
1. READ-ONLY outside OUT. Never edit bundles, Tasks_INPUT, jobs/, Output_RFP/, QC/, master_chat_tasks/, master_chat_work/ (except OUT), the QC kit, the harness code. No git writes. No harness runs. No Docker. No QC runs.
2. Scripts only as `perl -e 'alarm 300; exec @ARGV' python3 ...` (read/parse only). Read trajectories with python/jq in pieces; never print a whole trajectory. Before you finish, `ps` shows no python process of yours.
3. Proposals only. Apply nothing.

## Sources
- Runs: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/jobs/<slug>/` (21 task folders + `_archive`). Per run: `trajectory/<model>/Run N/agent/trajectory.json`, `agent/instruction.txt`, `verifier/test-stdout.txt`, `verifier/reward_raw.json`, `reward.json`, `judge_response.txt`, `artifacts/` (+ `manifest.json`), `report.json`, `result.json`, `config.json`, `trial.log`; job level `logs/` and `pass_summary.json`. Packaged copies: `Terminal_2.0_Harbor_Harness/Output_RFP/<slug>/` (what the client receives). Older runs may be in `jobs/_archive`.
- Scores and loss: `master_chat_tasks/registry/scores.jsonl`, `python3 master_chat_tasks/tools/loss.py <slug>` (read-only; per-check and per-criterion loss of the latest run).
- Bundles as run: `master_chat_work/bundles/<slug>/` and `Terminal_2.0_Harbor_Harness/Tasks_INPUT/<slug>/`; staged copy the harness ran: `Terminal_2.0_Harbor_Harness/.kiro-staged-tasks/<slug>/`.
- Harness code (to learn how a run is verified, packaged and whether re-verification exists): `Terminal_2.0_Harbor_Harness/` (runner scripts, harbor/rewardkit usage, packaging into Output_RFP). Look for any re-verify / re-judge / regrade path, what hashes or task fingerprints are written into the run record and the packaged output.
- QC kit (authority): `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (Final_checklist.md, gates 01-05, scripts). Our rulings: `master_chat_tasks/knowledge/QC_RULINGS.md`, `QC_FIX_PLAYBOOK_v2.md`, `LEVER_RULES_v3.md`, `LEAK_LIBRARY.md`; QC reports `QC/reports/<slug>/v*.md`.
- What we already do with trajectories (do not reinvent; compare): P-5 judge "probe band" (criteria for checks the probe skipped) in `master_chat_work/20261027_*/harden_w*_*/DESIGN.md` and `master_chat_work/2026102*_*/harden_*/DIAGNOSIS.md`.

## Work
Step 1. Trajectory anatomy. For 3 runs (one pushed: e.g. match-replay or dispatch; one parked at tests 100: e.g. cohort-retention or data-product; sentinel attempt 7), document what each file holds and how to extract: the step list, tool calls and their outputs, files written, the agent's own checks, the final message, each test check result with its assertion message, each judge criterion verdict with its reason, and what the artifacts folder keeps (does it keep the agent's program so tests that execute agent code can be re-run? which task.toml `artifacts` entries control that?).

Step 2. Trip-point extraction method. Define a repeatable procedure (and a sketch of a read-only script, not run on anything but these files) that turns one run into a table: trip point (step id), what the model did, what the spec required (instruction/doc file:line), which check/criterion graded it (or none), and class: WRONG_AND_GRADED, WRONG_NOT_GRADED (a gap to add a test or criterion), RIGHT_EASY (passed with no effort: candidate to down-weight), SKIPPED_BEHAVIOUR (judge candidate), STATED_WRONG_FACT (closing message figure differs from its own artifacts). Apply it to all 21 tasks' latest runs; output per task counts and the top 5 WRONG_NOT_GRADED items with evidence.

Step 3. For each change kind (re-weight, add test, add criterion, remove/down-weight), write the legitimacy and QC test it must pass, with rule IDs from the kit: e.g. a new test must grade a requirement the instruction or docs state (no hidden rule), on hidden data generated like the shipped data, owned rows, one observable per check (TS-13), weights track importance not a run's failures (TS-20), CL-4 partial credit, A3 check cap, no trap wording (IN-17); a new criterion must be observable in trajectory/artifacts (JD-6), not satisfiable by doing nothing (CL-2), not one-route-only at high weight (JD-15), negatives disjoint (AL-28). For each, say the line between "using the trajectory to find a real gap" and "fitting the grader to one run's quirks" and give one concrete example of each from the 21 runs.

Step 4. Way A (re-grade the saved run): answer with evidence:
a) Is a saved run still a valid run of the changed bundle if instruction.md and environment/ are byte-identical? What does the harness record about the bundle at run time (hash, staged copy, task.toml), and would a packaged Output_RFP show tests/judge that differ from the ones the run was scored with?
b) Can it be done mechanically: do the saved artifacts contain everything the tests need (for tests that run the agent's program on hidden data, is the program saved?), can the judge be re-run on the saved trajectory, and does the harness have or allow a re-verify path? Quote the code.
c) Risks: QC/QL or the client checking run provenance; overfitting (a check that fails this run only because it was written after reading it); whether QC rules or our GOALS/feedback forbid it. Verdict: FEASIBLE+LEGITIMATE / FEASIBLE but RISKY (why) / NOT FEASIBLE (why).

Step 5. Way B (tune then 1 new run): expected effect of each change kind on the next run, using our history: for every past pair (run before a change, run after) in scores.jsonl, what changed in the bundle (diff the staged copies or QC copies) and how scores moved. Include run-to-run variance on unchanged bundles (same bundle, 2+ runs) so we know how much one run can move without any change. Verdict on how reliably a trajectory-guided change carries to the next run.

Step 6. A per-task plan for the current pipeline tasks only as illustration (sentinel, tariff, cold-chain, schema-migration, district-heat, metered-usage): which trajectory-driven changes would apply, under A and under B, each marked QC-SAFE / QC-RISKY (rule IDs). Proposals only.

## Deliverables in OUT
- TRAJECTORY_ANATOMY.md (Step 1), TRIP_POINTS.csv + TRIP_METHOD.md (Step 2, with the script sketch), LEGITIMACY_RULES.md (Step 3), WAY_A.md, WAY_B.md, PLAN.md (Step 6).
- result_cb612aa.json: {"sha":"cb612aa","step":"trajectory-hardening-research","runs_read":N,"tasks":N,"way_a":"FEASIBLE_LEGIT|FEASIBLE_RISKY|NOT_FEASIBLE","way_a_reason":"...","way_b_reliability":"...","run_variance_tests_pp":x,"run_variance_final_pp":x,"top_gaps":[...],"qc_safe_change_kinds":[...],"qc_risky_change_kinds":[...],"report":"/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/trajectory_hardening/research_cb612aa/WAY_A.md"}. It must parse.
Final message: 10 lines max: Way A verdict with the deciding evidence, Way B reliability with the variance number, the 3 most useful trip-point gaps found, and which change kinds are QC-safe.
