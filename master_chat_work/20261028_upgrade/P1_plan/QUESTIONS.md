# Questions for Ayush (board 3d3a74a, upgrade plan v1)

Merged from R1-R5 and the plan session; duplicates joined. Each: options, recommended answer, why. Plan: `UPGRADE_PLAN_v1.md`.

## A. QL loop (goals 1-2)

**Q1. Can a regrade be push evidence?** (R1 Q1)
- a) Yes, named exception: only judge files changed, the run was valid, you write OK for that regrade, repackaged with the one-slug tool. b) No, keep the ban (regrade = diagnostic only) and every judge edit needs a new paid run.
- Recommend a). Why: you already pushed sentinel on a regrade (44.53); the written rule says never. One of the two must change; a) keeps a paid run per judge-only fix and still needs your word each time.

**Q2. Does final < 40 apply to tasks already pushed (sentinel 44.53, district 44.84)?** (R1 Q2)
- a) Only when the QL asks to lower the score. b) Yes, harden both now.
- Recommend a). Why: both passed the gate in force when pushed; b) costs 2+ paid runs and reopens frozen bytes with no QL request.

**Q3. issue.py for QL work and the time box** (R1 Q3 + R5 Q3 merged)
- a) Add kind `ql`; QL rounds on pushed tasks skip the 8-session time box; the time box resets when the stage changes; round caps stay; every override records who (`master (auto)` or `Ayush`). b) Keep the time box as is and override by hand each time.
- Recommend a). Why: the box refuses every pushed task today (24 overrides logged, all written as "Ayush"); round caps still stop endless loops.

**Q4. One-slug repackage tool** (R1 Q5)
- a) New tool in `master_chat_tasks/tools/` that calls the harness packager for one task only; harness repo untouched. b) Keep the hand method (~8 manual steps, sentinel precedent).
- Recommend a). Why: fewer manual steps on every QL push; it refuses bytes that are not the frozen tree.

**Q5. A QL zip that changes tests or judge files** (R1 Q7)
- a) Voids the old run: new paid run, asked of you each time (outside the cap of 6). b) Allow trajectory-only checks on the changed bytes without a run.
- Recommend a). Why: the score must come from the exact bytes we push (LEVER_RULES 210).

## B. Mac / Docker / opencode (goal 3)

**Q6. Docker Desktop settings** (R2 N2, N3, N4)
- a) Memory 12 -> 16 GiB, swap 1 -> 2 GiB, builder gc policy (10 GB unused > 7 days, 20 GB total); one Docker restart when no job runs. b) Memory/swap only. c) None.
- Recommend a). Why: 32 GiB Mac; build cache is 28.8 GB with 20.8 GB reclaimable; one restart covers all three.

**Q7. Sleep on battery** (R2 N1)
- a) You run `sudo pmset -b sleep 0 displaysleep 10 powermode 0` AND keep the charger in with the lid open during auto runs. b) Habit only. c) Neither.
- Recommend a). Why: the Mac slept 71 min (19:32-20:43) on battery with the lid closed; that was the largest single loss R2 found.

**Q8. Clean-ups that delete or stop things** (R2 N5, N7, N8, N9) — pick any
- N5 back up then VACUUM opencode.db (4.0 GB) at end of day with all opencode stopped; N7 close stale opencode processes 15335 and 23171 (~1.6 GB) if still present and not your window; N8 delete `/tmp/opencode-logs` files older than 7 days (849 MB total); N9 you add the Terminal Bench folder to Spotlight privacy.
- Recommend all four. Why: all reversible or low value data; N5 only with a backup and nothing running.

## C. Hardness levers and gate < 40 (goal 5)

**Q9. Design aims for the new gate** (R3 Q3, extended by the plan)
- a) First-write and all-but-one programs aim tests <= 60; each blind read tests <= 65; judge probe mid <= 20; DESIGN READY needs predicted final <= 35 and lever share >= 40% of positive test weight. b) Keep v3.6 aims (tests <= 75, blind <= 80).
- Recommend a). Why: final < 40 means tests + rubric < 80; with v3.6 aims a design predicts ~45-56 (our 3 paused tasks).

**Q10. Lever status table v3.7** (R3 Q4 + R4 levers)
- a) Adopt as written in plan C3: L2 held-out and L6 process criteria PROVEN; L3, L5, L7, L8, L9 WEAK; unbounded induction, effort caps, judge-only bands FALSE; new candidates PROMISING. b) Adopt only the PROVEN/FALSE rows now.
- Recommend a). Why: matches both research sessions; WEAK rows keep their legal uses (honesty negatives stay as integrity checks).

**Q11. Default shape for the next new task** (R3 Q2 + R4 Q1)
- a) Next new build: held-out heavy-weight tier >= 50% of positive test weight + probe-band judge (one pilot, 1 paid run); bounded induction as a second, later pilot. b) Bounded induction first. c) No pilot.
- Recommend a). Why: the held-out tier is the best-supported lever in both studies; induction needs a uniqueness script we do not have yet.

**Q12. How to version the rules files**
- a) Keep file names; snapshot the old bytes as `*_v3.6_snapshot.md` with sha256, then edit in place as v3.7 (the v3.3-v3.6 way). b) New files `LEVER_RULES_v4.md` and `_COMMON_RULES_v6.md` and update the path in 17 templates.
- Recommend a). Why: zero template edits, old text kept; b) touches 17 templates for a path change.

**Q13. Reply to the QL on hardness.md**
- a) Send one Markdown reply: 41 confirmed, 18 partly, 5 wrong, 4 untestable claims, the 5 wrong ones with evidence, 4 questions back (opus-5-5 runs inside the sample, theme regex, L6 counts, one task's hidden count), proven and new levers in plain words; you read it before sending. b) Send only the 5 wrong claims. c) Don't reply.
- Recommend a). Why: you asked to verify the doc; the 4 questions are things only the QL can answer.

## D. Learning loop (goal 4)

**Q14. Ask teammates for scripts** (R4 Q6)
- a) You ask Aditya Jain and Anjali Kumari for the uniqueness scripts behind their induction tasks. b) We write our own.
- Recommend a). Why: the bounded-induction pilot needs a uniqueness proof; theirs exist.

**Q15. Learning loop stop rule**
- a) The research prompt proposes its own next version every run; master accepts a version only if its run found at least one strong or medium angle; two weak runs in a row -> stop and tell you. b) Run every version without a stop rule.
- Recommend a). Why: keeps the loop from spending sessions on angles that show nothing.

## E. Auto-mode fixes (R5)

**Q16. Budget and worker caps** (R5 Q1 + policy drift R5-19)
- a) Paid runs max 6/day, each only when no usage limit is active and <= 2 workers busy; max 3 busy workers while a paid run runs, 5 otherwise; AUTO_POLICY's "4 workers" corrected to 5 to match your 27 Oct word. b) Keep today's rules (no budget check).
- Recommend a). Why: 5 of 7 runs hit the shared limit; one paid run went into an empty window.

**Q17. When the usage limit hits** (R5 Q2)
- a) Hold all spawns and paid runs, pause the queue, resume at the parsed reset + 5 min, REPORT line + macOS notification. b) Hold without notification.
- Recommend a). Why: the master chat itself sat in retry and missed events.

**Q18. Kill a running paid run on the first "accounts exhausted"** (R5 Q4)
- a) Log only in the first fix; switch to kill + requeue after the log has caught it once on a real run. b) Kill from day one. c) Never kill.
- Recommend a). Why: a wrong kill loses a valid run; one observed case proves the match first.

**Q19. opencode doom_loop guard** (R5 Q5)
- a) Keep the deny; auto sends one "continue" with a poll rule (only if a counter is rising), then BLOCKED. b) Allow the loop.
- Recommend a).

**Q20. Stop and wind-down** (R5 Q6, Q7, Q8 merged)
- a) `auto.py stop --now` in one step; runs added after AUTO STOP only via `--wind-down` and inside the cap; no new worker spawned in the last 20 min before AUTO STOP. b) Keep manual stop.
- Recommend a). Why: the 1553 stop needed hand kills; runs started after STOP were not tracked.

## F. The 3 paused tasks

**Q21. When do the paused tasks resume?**
- a) After the gate change and the limit fixes are tested (Batch 2). b) Now, before any upgrade. c) After the whole upgrade.
- Recommend a). Why: resuming before the limit fix risks another lost night; waiting for everything delays 3 runs for clean-ups.

**Q22. cold-chain-backbone-quote: predicted final ~56 on frozen bytes**
- a) Run the 1 paid run as planned (only legal way to change frozen bytes is via a trajectory read-out), then harden for < 40. b) Exception: harden now without the run (saves 1 paid run, breaks the freeze rule once).
- Recommend a). Why: the freeze rule exists to stop untested edits; the run also gives the trajectory the harden needs.

**Q23. metered-usage-rating-pipeline: predicted 39.8-45.7**
- a) Finish the QC report (no rerun); if PASS, freeze and run (your OK of 28 Oct stands); miss -> read-out, harden once, 1 new run. b) Hold until a redesign for < 40.
- Recommend a). Why: the low end of the band can pass; b) would need a harden after QC, which the rules forbid without a run.

**Q24. schema-migration-plan-repair: kept design predicts 41.4-46.0**
- a) Redo the design for < 40 (more held-out worlds plus a probe-band judge, ~42-45 worlds, predicted ~38-39), then build, recheck, attempt 7. b) Park the task. c) Build the kept 34-world design anyway.
- Recommend a). Why: c) is predicted to miss; tests alone cannot reach < 40 inside the 2,700 s verifier limit, so the judge must change too. If attempt 7 misses -> park.

**Q25. QL reruns and the daily cap**
- a) As you said: outside the cap of 6, asked each time; they still wait for a fresh usage window. b) Count them inside the cap.
- Recommend a). (Included only to confirm the window rule; the cap part is your 28 Oct word.)

## Settled by evidence or your words (not asked)
- Keep tests < 85 and rubric < 85 (your word; R3 says rubric < 85 is redundant but costs nothing; R4 says keep).
- Inbound QL folder `master_chat_work/_ql/` (R1 Q4): no conflict, master decision.
- False-positive order (R1 Q6): FP dossier row at once, rulings row after the QL agrees.
- 725e575c is not a hardness model (R4 Q2): tests 96.55, judge-only.
- No reference rollups beyond one unlabelled witness (R4 Q5): already Never 11.
- 2 extra paid runs for each of 13 teammate tasks (R4 Q4): not doing (26 runs).
- auto.py health check change (R2 N6 = R5-07): part of the auto fixes (Q16-Q20 "proceed" covers it).
- auto.py port: it is random (`--port 0`), not 4096; prompts saying 4096 are stale (R2, checked).
