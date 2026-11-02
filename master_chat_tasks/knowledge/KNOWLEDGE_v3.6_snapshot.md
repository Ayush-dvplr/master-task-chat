# Knowledge base (distilled from reports 01-06, 21 Oct 2026 00:20 IST)
Facts only, each traceable to `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261020_analysis/reports/<x>/REPORT.md`. Read this instead of the reports unless detail is needed.

## Pipeline and tools
- Flow (team): build -> QC (fix loop until pass) -> 1 trajectory run -> Anubis_Tasks_Samples -> QL verify -> Finalized_Tasks_RFP -> 8 runs at final approval.
- Flow (ours, from 24 Oct 11:26, Ayush "1. a"): build -> precheck.sh clean -> private probe run on our harness (recorded `probe`, never submitted) -> kill rule (tests >= 95 -> drop or swap core) -> QC -> stop at first PASS -> 2 runs under gate -> PL.
- Final_Delivery reads (24 Oct, `master_chat_work/20261024_process/final_delivery/SYNTHESIS.md`): 6 delivered peers, combined 17.64 to 71.65, QC 0 fails on all; the main loss is amplification of stated-rule slips. Do not calibrate difficulty on wafer (accepted on 1 run, no QC report, partly a key/spec conflict). Second read (24 Oct 13:40): scores are bimodal per lever (strict read about 96 to 99, misread 41 to 72), so each lever alone must cost >= 25% of test points and 'all but one right' must stay overall < 70 (LEVER_RULES G10); Opus misses habits (LEVER_RULES 1b H1-H6) and code quality (4 of 6), not decoys. Our own QC fails, 44 reports, 90 fails: AL-27 17, TS-19 6, DS-22 5, JD-7 4, JD-18 4, S5 3; precheck.sh now checks S5, DS-22, AL-27 (RULE_COVERAGE.md), J3, J4.
- Harbor task format is identical in 0.23 and 0.24. What changed is the team bundle shape the QC enforces (rewardkit test_output.py + judge.toml + reward.toml, separate verifier, pinned network roles). Multi-step tasks are not allowed (S2, S3, T2). [research_kit]
- Reward = 0.5 x tests/P_t + 0.5 x judge/P_j. Checks are binary; weights are in {+-1, +-3, +-5}; the sum of negatives is at most the sum of positives. With tests < 0.20, overall < 0.30 needs judge < 0.40. [qc E]
- Statistics: with 9 runs, an observed mean of about 0.20 or less certifies < 0.30. A single build run finds spec gaps and cheats; it does not measure difficulty. [web]

## PL generator (Input Bundle Generator New, unchanged since 1096b244)
- 8 archetypes: build-repair, cli-config, data-pipeline, domain-calculation, format-recovery, performance, repo-patch, service-interaction. All 8 pass the validator in strict mode when fresh.
- Flags: `--out` and `--author "First Last <first.last@ethara.ai>"` are required. With no `--category` the category is random. `--force` runs rmtree on the target. Running it writes `memory/ideas.jsonl` and `__pycache__` INTO the clone, so run it from a copy or with `IBG_MEMORY_PATH` set and `PYTHONDONTWRITEBYTECODE=1`.
- VB 1.12: `artifacts` must equal the archetype's manifest list, which is read from the generator folder. The output set is fixed per archetype.
- Data is embedded in test_output.py as `_SHIPPED_DATA`. Any data edit means re-embedding, recomputing reward.toml, and updating the TRUTH sha256 values.
- Bugs and gaps:
  - instruction.md has blank words in 4 archetypes, and neither the validator nor QC catches it.
  - The other 7 archetypes produce the same text, bugs and tests for every seed and category, so they are near-duplicates.
  - Labelled fixtures (`want`/`expected`) let the agent fit the graded rule.
  - The 20k-line minimum is met by padding one file.
  - The code the agent repairs is 59 to 135 lines.
  - Formats are limited to csv, json, jsonl, md, txt, log, yaml and zip.
  - The judge pays for process.
  - The partial-solver ceiling of 0.35 is advisory only.
  - `--semantic` now reads reward.json (fixed in f0579497).
- playground: A5 needs at least 20k lines in total and at least 2k per csv/tsv/jsonl/txt/log file. D1 oracle must be 1.0, D2 nop 0.0, D3 stub 0.25 or less (WARN), D4 ablation at or below ablation_max. `--model` uploads content to OpenAI.

## QC (live = clone's Input_Bundle_QC, GitHub 9b8229f6)
- 307 checks, 109 of them manual-only and 15 that need a real judge run. IDs get renumbered between versions, so match on ID plus wording. Script-owned checks are now final, which means their blind spots get no reviewer recheck (comma timeouts, dashes in code, grader wording that is only a C6 WARN).
- A fresh scaffold passes all 4 scripts (one C6 WARN). It fails the manual gates on:
  - DS-27 (generator provenance in TRUTH)
  - IN-2 (the instruction describes the verifier)
  - TS-25/26 (positive absence tests, double payment)
  - JD-5/8/18 (a compound criterion, a judge overlap with tests, no code-quality criterion)
  - CL-2/CL-4 (they need computed numbers)
- Resolved (f0579497): validator 15.5 now FORBIDS authored_by/status/archetype/generator_seed/trailer_token in TRUTH, same as DS-27.
- Step 10 (official): exe_copy, then oracle 5 times exactly 1.000, nop 0.000, and the stub reported with the tests it paid. TESTS-ONLY. The QL interim procedure says oracle up to 3 times (see intake/).
- Counts: tests >= 10 and judge >= 8 (kit FAIL below); NO upper cap (Ayush 24 Oct 12:50, repeated). Above 35 tests the kit prints WARN A3, recorded with the count; delivered slo-credit-closeout shipped 48 tests with that warn accepted. QC target: zero fails, only genuine minors/warns, as few as possible (supersedes dec 101 zero-warn).
- Paste-ready rules: reports/qc/authoring_checklist.md (14 steps).

## Beta generator (Ayush, 0.23): what to reuse
- It is a controller only. The agent authors everything, and the hardness rules are prose.
- Strongest reusable parts:
  - Mode 12 QC Repair: Real / False positive / Vague triage, narrow selection, a scope-checked diff, a 3-strike pause, and an explicit difficulty-risk choice.
  - The per-run gate: test < 90, rubric < 90, combined < 30. (beta; ours is final reward < 70 on 2 valid runs (Ayush 26 Oct, D2), _COMMON_RULES_v4 Score conventions).
  - Oracle x2, nop, and a stub whose every paying test is reviewed.
  - Hidden reseeded corpora plus reruns of the delivered program.
  - The 19-field idea prompt with 3 finalists and 3 refinement rounds.
  - The harden diagnosis table (validity defect / weak difficulty / unsupported complaint; "do not add volume").
  - Feedback 5-way classification.
  - Mechanism cards {visible_rule, trigger, wrong_interpretation, root_cause}.
  - The unused red-team hack trial.
- Tension: the upstream recipe uses a spine plus a partial-solver ceiling under 0.35, while beta says "preserve partial signal". v2 must choose.

## Hardness evidence (web research, 40 sources)
- Works with every rule visible:
  1. hidden composition of documented rules (SpecBench: 100% on visible tests vs 25% on held-out ones)
  2. a dependent multi-stage chain
  3. audit-and-repair against a contract
  4. algorithmic lift on a size ladder
  5. a format-only validator, so the agent must self-verify
  6. stacked orthogonal constraints (96% -> 2%)
  7. infeasible instances with certificates
  8. weight on error and rejection paths
- Does not work: arithmetic or counting (Python solves it), small puzzles, volume, formatting, many corner cases, hidden rules (they fail QC), resource pressure, keeping only tasks that current models fail.
- Grading: grade downstream stages on oracle-fed inputs so one early slip does not zero everything. Hidden tests must come from a wider distribution than the visible ones. Tie judge items to outcomes, not effort.
- Anti-cheat: keep nothing graded reachable, strip git leftovers, and use explicit specific prohibitions (they work for Claude). Fix exploits in the scorer.

## Lessons from Ayush's own tasks
- district-heat v1: every rule was documented, so a careful model implemented them all (reviewer 3/10). Parked.
- A reviewer rating of 3/10 still corresponded to a real trajectory score under 50 overall. Only real runs count.

## Upstream at bfe40804 (P10, 22 Oct 09:50; full detail master_chat_work/20261021_upstream/UPSTREAM_DIFF.md)
- Generator and QC at bfe40804 are byte-identical to f0579497: 8c37863a and bde868c4 were undone by the kiro-bridge merge.
- Judge annotations: exactly mode, type, evaluation_target, importance (kept). TRUTH provenance keys forbidden (kept).
- test.sh: `chmod 700 /logs/verifier` in every template; QC H5 warns on anything else (755 now warns).
- Input dirs: named dirs under environment/ allowed. repo-patch = environment/repo + environment/ci; service-interaction = environment/service + data/ (was data/*.zip). Validator 1.4/5.5 enforce it.
- Playground: --ablation sample|full|off, --jobs; A3 check removed.
- PL bugs still present: IN-15 and JD-15 still name the retired key `kind`; blank words (generate_bundle.py:1856-1857); Final_checklist oracle x5 (:273,:350); CATEGORIES.md stale.

## Upstream at a74bda85 (master, 22 Oct 13:00; 3 commits after bfe40804)
- 2690e960: `chmod 755 /logs/verifier` restored in all templates; H5 OK at 755, WARN at 700 (700 breaks Harbor's host-user reward read on Linux). Supersedes the bfe40804 700 line above.
- a72c20a4: `playground.py`, `task_memory.py` removed; validate_bundle.py aligned with QC; archetype `ablation_max` gone. The playground line above is historical.
- a74bda85: tests_qc K8 FAIL unless tests/Dockerfile pins `litellm==1.105.0` on the rewardkit pip line; 1.107.0 quarantined (withdrawn 21 Oct, remote-code payload).
- structure_qc S4 / tests_qc input mounts understand `COPY . /app/`.
- Fingerprints at a74bda85 (generator 160 files, QC 12); old set in fingerprints/archive_bfe40804/.

## Upstream at c9e3454a (22 Oct 13:59, pulled by Ayush 14:57)
- QC H6 (tests_qc) + TS-30: FAIL when checks run an agent-written program under a dropped uid without making it readable. Step 10 adds an owner-only oracle run (`exe_copy.py --owner-only`). Templates add `_grant_read()` (chmod a+r on agent paths under /app and a+rx on parents before setpriv). This is the PL's fix for our permission-bug note.
- Fingerprints at c9e3454a; old set in fingerprints/archive_a74bda85/.

## Harness runner (harness chat, 24 Oct 10:40)
- Queue ask (to the harness chat): "queue these and start:" then one absolute bundle path per line (`/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/<slug>`). Optional lines: "queue only, don't start"; "put X at the front/end"; "reply when all finish with: queue table, job folder, scores line"; "gate: tests<100, rubric<100, overall<70"; QC/board ids for its decision log. Other commands: status, scores, cancel <task>, resume, dry-run <task>.
- Two harness checkouts exist: live `Terminal_2.0_Harbor_Harness/` (git 976c1666, tracked by fingerprints) and old `Harbor_Harness/Terminal_2.0_Harbor_Harness/` (git b1ffb283). A harness chat may run in either; read the job folder it names. Intake a job from the old one with `intake.py --job SLUG --harness Harbor_Harness/Terminal_2.0_Harbor_Harness --bundle master_chat_work/bundles/SLUG --event probe|gate_run`, and `loss.py <that jobs/SLUG dir>`. (24 Oct 15:43, match-replay probe 866ff04.)
- Issued run/probe prompt file = ONLY the paste text above (no master notes; those go in the board note). Each bundle path appears ONCE per ask. A second run of the same bundle is a separate ask after the first finishes (rerunning a folder archives the old copy to task-archive, attempt +1). (Ayush 24 Oct 15:30.)
- It diffs each bundle against Tasks_INPUT/, runs `scripts/master_queue.py add`, starts the runner, never edits bundles, never retries a startup network error. Rerunning a slug archives the old job and bumps the attempt number.
- Capacity (corrected 24 Oct 11:10 from .master-queue/state.json, 37 runs): run time median 26 min, mean 38, range 1-137 (schema a4 116 min was the outlier). Harness chat says Docker fits one task at a time (state max_concurrent=2). Serial = ~1.5 runs/hour, ~12-15 usable runs/day with Ayush feeding the queue.
- Grader isolation holds (leak audit e59fc8d): separate verifier, build context environment/ only. Leak risk = author notes (TRAP/inverse/_traps/decoy labels) inside environment/data. 18 of 26 job configs staged from the OLD `Harbor_Harness/` path: scores from those runs may not match the current bundle; check job-config path + tree sha at every intake.

## Peer task samples (Ayush, 24 Oct 11:26)
- New peer uploads land in `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Pass@1_New/<QL>/<author>/<task>/` (QLs Dinshi_Jain, Poonam_Chourey, Sugam_Agrawal; 17 authors). Older samples elsewhere in Anubis_Tasks_Samples are QC failed: do not mine them for "how to pass".
- Each task folder: instruction.md, task.toml, environment/, solution/{TRUTH.md,solve.sh,solve.py}, tests/{test_output.py,judge.toml,reward.toml,test.sh,Dockerfile}, Output/{logs,trajectory}, trajectories/claude-opus-5.
- Q57 scope: ONLY `Pass@1_New/Dinshi_Jain/Aditya Patel/` (detbench-release-gate-eval, estate-manifest-consolidation, kvec-meter-settlement-reconciliation).

## T. Master decides from the trajectory (pipeline v4, decision 8; Ayush "proceed" 27 Oct)
Source: master_chat_work/_dev_research/pipeline_v4/PLAN.md section T. After every harness run that misses the gate (no re-run on the same bytes: ±17.5 tests / ±20 final variance):
1. `python3 tools/trajectory_readout.py "<jobs/<slug>/trajectory/claude-opus-5/Run N>" --out <OUT>/TRIP.md`. It scores from `verifier/reward-details.json` (report.json "passed" on negatives is unreliable), cites `test-stdout.txt` lines and judge reasons, splits lost test points TIMEOUT / CRASH / WRONG (Law 1 v3.5: WRONG counts; TIMEOUT/CRASH counts only on hidden scale with a stated limit, cost 10-30% inside lever checks), flags FALSE_CLAIM (final message claims success while positive tests fail; 8/21 runs did) and EASY.
2. Fill the TRIP table by hand from `agent/trajectory.json` + `artifacts/`: `| step | what the agent did | what the docs require (file:line) | check/criterion | class |`. Classes LOST_GRADED, WRONG_UNGRADED (only by reading, never by keyword), EASY, SKIPPED, FALSE_CLAIM.
3. Decide: why it scored (points per lever family, first-write step, stress tests, self-checks); what to change, QC-safe form only:
   | Edit | QC-safe form | Flagged if done directly |
   |---|---|---|
   | Raise points | only a core check of the main job, to the TS-20 level the instruction ordering supports | raised because the run failed it (TS-20) |
   | Add test | rule the docs already state that old data never tried (AL-27), hidden data from the same generator, one observable (TS-13) | unstated rule or one run's quirk (AL-1, AL-4) |
   | Add judge item | odds-raising habit the oracle shows, w1/w3, observable in trajectory or a declared artifact (JD-6, JD-7, JD-15) | w5 preference or "used method X" |
   | Add penalty | FALSE_CLAIM negative -3, disjoint from other negatives (AL-28) | stacked on an act another negative charges |
   | Lower easy points | only where one observable is paid twice: merge or split (TS-26, JD-14, TS-13) | lowered because the model passed it |
4. Next step (gate v3.6, Ayush 27 Oct 22:20 "new gate is test < 85 , rubrics < 85 and overall < 50"): tests >= 85 -> new or stronger test lever; tests < 85 but rubric >= 85 or final >= 50 -> judge probe band (mid 15-20) + penalties, and more test lever if rubric alone cannot reach final < 50 (final = (tests + rubric)/2); gate met on QC-passed frozen bytes -> push. Write the fix prompt from the table (P12 v4, guard rules G1-G7, QC_FIX_PLAYBOOK_v3 1b), then QC recheck (P11 v3 MODE recheck), then 1 new run.
Regrade (`harbor trials regrade SOURCE -p TASK`) is diagnostic only, run when Ayush asks; never push evidence, never packaged (package_rfp_bundles.py:73 copies scores).
