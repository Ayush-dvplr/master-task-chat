# Setup plan v1 (draft, approved one part at a time), started 23 Oct 2026 08:31 IST

Ayush's choices (08:30):
- The plan covers 4 parts: templates, data/records, sessions, pipeline order.
- I write the plan here, and a separate session rewrites the template files after approval.
- Templates change only after the cohort pilot lands under the gate.
- Ayush approves one part at a time.

## Part 1: Prompt templates (status: APPROVED 08:33)
1. **One rules file, not copies.** Approved LEVER_PLAN_v1 becomes `master_chat_tasks/knowledge/LEVER_RULES_v1.md` (levers L1-L7, writing W1-W7, grading G1-G7, judge J1-J5). Templates point to it by path and version and never paste it, so a later change is made in one place.
2. **Templates that change:**
   - P2 build → v2: designs from LEVER_RULES.
   - P9 harden → v2: diagnosis with the 4-cause root-cause section, then LEVER_RULES.
   - P12 fix → v2: a fix may not undo a lever or add a giveaway.
   - P3 hardness check → v2: replay gate, below.
   - `_COMMON_RULES` adds W1 (never explain the trap) as a hard rule.
   - P11 QC stays v2: QC must stay blind to our lever notes.
3. **New gate in every build, harden and fix: STACKING_CHECK.md + replay.**
   - Map each test to its observable (TS-26/TS-13).
   - Penalty groups must stay ≤ 5 (AL-28).
   - Run a "reflex program" against the new tests: it must score ≤ 0.20 on tests before any trajectory.
   - The reflex program is the real agent's program from its last trajectory if one exists. If not (Q1 = a), a fresh read-only blind-solve session sees only instruction.md + environment/, writes its solution once with a quick self-check on shipped data, and that program is scored.
   - Every P12 fix round re-runs the reflex program after its fixes (Q2 = a). If the score rises above 0.20, the round compensates in the same lever family before finishing.
4. **Baseline rule:** a score from a run with a grader error (permission, crash, timeout, missing file) is never a baseline. Every result first gets the Phase A check (genuine / artefact / partly) used in the peer study.
5. **Kept as is:** the board-id rename, compaction rules, result json (sha = board id), oracle x3 (kit asks x5), and the clash rules.

## Part 2: Saving data and records (status: APPROVED 08:38)
1. **Peer research store, with the Q48 manifest.**
   - `master_chat_tasks/registry/peer_tasks.json` has one entry per researched task:
     - slug, author, repo path, Anubis commit;
     - `root_sha`: sha256 over the sorted root-level files and folders (each folder hashed by its contents);
     - date studied, group/board id, verdict (GENUINE/PARTLY/ARTEFACT), the patterns found, and the report path.
   - Before any new research prompt, a tool (`tools/peer_manifest.py check <path>`) lists only the tasks that are new or changed (sha differs). Unchanged tasks are never re-scanned.
   - `root_sha` covers the whole task folder, every file (Q3 = a), so any change triggers a re-scan.
   - The store and the tool are built by the same separate session that rewrites the templates, after all 4 parts are approved (Q4 = a). It fills the 20 Pass@1_New tasks.
2. **Lever bank.**
   - `registry/levers.json` gains L1-L7 with fields: peer evidence, the rule file used, reflex-program score per task, real trajectory result per task, and status (candidate → held / leaked).
   - The old CR-1..CR-5 and V0 levers are marked `leaked` with the cohort reason. A lever counts as `held` only on a real trajectory.
3. **Scores.**
   - Every line in `scores.jsonl` gains `valid` (true/false) and `artefact_reason`.
   - Only valid lines are baselines. The three past artefacts (cohort 58.67, vendor 52.41, district-heat timeout) get correction lines.
4. **Trajectory copies.**
   - The rule stays: copy immediately to `master_chat_work/<date>_<slug>/traj_aN/trajectory_job_<slug>_<6hash>`.
   - New: also save the agent's final program and outputs as `agent_program/`, to feed the reflex replay.
5. **Research and plans.**
   - `master_chat_work/_dev_research/` holds LEVER_PLAN, SETUP_PLAN and peer_levers.
   - The approved, live rules go to `master_chat_tasks/knowledge/` (LEVER_RULES_v1.md). `_dev_research` is the evidence; `knowledge/` is the authority.
6. **Unchanged:** the intake rule, board/pending/status/log, lessons pending review, and no chat summaries stored.

## Part 3: Session handling (status: APPROVED 08:38)
1. **Slots.** 5 working-session slots; the master chat and the harness chat together count as 1. Docker-heavy work returns to max 2 at a time (Q5 = a). TODAY (23 Oct) ONLY: waived because of the lever-design failure; I check memory on every done. Docker runs inside a session go one after another.
2. **Unchanged flow:** board id = session title; "done: <sha>" → I verify the result file, record it, and give the next link; no result file → paste the last reply.
3. **New session types:**
   - **Blind-solve** (reflex program, Part 1 Q1): read-only; sees only a copy of `instruction.md` + `environment/`, never tests/, solution/ or our notes. It writes its program once, self-checks on shipped data, then stops. The build/fix session scores that program against the tests. One per task, after the build or fix round, before any trajectory. Model: the closest available to the trajectory agent claude-opus-5 (Q6 = a). TODAY (23 Oct) ONLY: blind-solve skipped; tasks with no trajectory rely on the build session's reflex check plus the real trajectory.
   - **Template rewrite:** one session after Parts 1-4 are approved and the pilot passes. It writes the v2 templates, LEVER_RULES_v1.md, peer_tasks.json and peer_manifest.py. I check every file.
4. **Stops for Ayush.** A harden pauses after its diagnosis for "go". A session reports "PILOT WEAK" or "PAUSED" when its reflex score stays above 0.20 after 2 tries.
5. **Holds.** Every task built in the old lever style stays on hold until the pilot passes: sensor 93f2b9f, schema ace4b59, dispatch 0e646c4, the emberforge trajectory S80, and converted hardens S23-S31. A held prompt is reissued from the v2 templates, not run as written.

## Part 4: Task pipeline order (status: APPROVED 08:38)
1. **Pilot first:** cohort 7cbd9f5. Phase 2 → STACKING_CHECK (a2 program ≤ 0.20) → gates → P11 v2 QC → P12 if needed (reflex re-run) → 1 trajectory.
2. **If cohort passes the gate** (tests<100, rubric<100, overall<70):
   - the template-rewrite session runs, and I check its files;
   - then the held tasks go in this order, lowest valid baseline first. Each has a real a2/a4 trajectory program for its reflex replay:
     1. vendor (harden r2);
     2. district-heat (harden r2);
     3. then the tasks without a valid trajectory: emberforge, schema, dispatch, sensor, then converted S23-S31 by v0 score, lowest first.
3. **If cohort fails:** compare the new trajectory with LEVER_PLAN, then round 3 (the last). If round 3 fails, drop cohort per the drop rule and rethink the plan before touching other tasks.
4. **Ready for trajectory:** QC 0 FAIL, oracle x3 1.0, owner 1.0, nop 0, stacking check pass, reflex ≤ 0.20.
5. **Drop rule unchanged:** 3 harden rounds without passing. Round counts: cohort is at round 2. Vendor and district-heat are RESET to 0 (Q7 = b, Ayush 08:38): their earlier rounds were judged on permission-bug scores.
