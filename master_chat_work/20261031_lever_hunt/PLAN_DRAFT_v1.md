# Lever hunt + 3 tasks: plan draft v1 (31 Oct, ~17:50 IST)

Status: DRAFT. Nothing starts until Ayush says "proceed" and gives the run time.

## Goal (Ayush, 31 Oct)
Make more and more tasks that fail Opus AND pass our full QC kit. The anubis-stage-2 team does this; find their levers and how they get past QC, store everything in a lever library, and use it for new tasks and for rebuilding or hardening old ones. Stop the NO CORE loop that wastes time and tokens.

## Ayush's answers (31 Oct ~17:45)
- Whether stage-2 tasks pass QC is not known: find out how they handle and pass QC.
- "Pass QC" for our tasks = our full P11 kit, as today.
- Study all 102 stage-2 tasks.
- Store levers in a lever library (index + one card per lever).
- Run our QC kit read-only on 4-5 low-scoring stage-2 tasks.
- Next auto run: study + 1 pilot + 3 complete tasks. Complete = full QC PASS + paid run final < 40.
- New or rebuilt: a mix; the master picks per lever.
- Paid runs: no cap; gate final < 40; one harden + rerun on a miss.
- Study first, then build. A build starts as soon as a lever card is PROVEN.
- Run time: Ayush gives it before "proceed".

## What we already know
- 102 stage-2 tasks, all with a valid Opus run: 30 under 40, 15 under 30, 7 under 20 ([S4 TASKS.csv](../20261030_upgrade2/S4_task_study/TASKS.csv)).
- 5 of the lowest were studied today ([CAUSE_REPORT.md](../20261031_stage2_calib/CAUSE_REPORT.md)):
  - 78% of lost test points come from contracts our kit would flag: hidden data that breaks the docs, or undefined keys and IDs, amplified by whole-report checks.
  - 22% is a fair trap: PM2.5's shared-channel echo attribution. It still fails Opus's program on inputs with no clock changes.
- Our blind scored exactly like Opus on 3 of 3 tasks, so a blind is a good cheap gate for the tests score.
- Our own passes come from exact optimum on hidden larger instances (dispatch 14.7, schema 32.1, outage 34.8) and the warrant convention lever (37.7). Single-trick designs keep ending in NO CORE.

## Phases

### A. Screen all 102 (script + Codex read-only, about 1 h, no Docker)
One script reads every task and writes `SCREEN.csv` with:
- Opus final, tests and judge.
- Number of hidden inputs, and whether they are generated or fixed files.
- Check style: per field / per report / whole hash.
- Exception-to-False wrappers.
- Doc-vs-generator red flags: generator values outside the ranges the docs state, and keys or IDs the docs never define.
- Judge share of the loss.

Output: a shortlist of 8-10 tasks that score low AND look QC-clean, plus 4-5 tasks for the QC runs (billing and PM2.5 plus 2-3 others), chosen by fixed rules, not by eye.

### B. Deep dive (opencode GPT sessions, Docker, about 2-3 h)
- Replay and instrument Opus's saved outputs on each shortlisted task, reusing today's A1/A2 scripts. Label every lost point: RULE-MISREAD, LATENT-WRONG, EDGE-INPUT, FORMAT, UNFAIR, etc.
- 3 tasks per session, so 3-4 sessions.
- Opus blind on a task only when the replay shows a fair trap, to prove a careful agent also falls for it.

### C. How stage-2 handles QC (opencode GPT, 4-5 tasks, about 2 h)
- Our full P11 QC, read-only, report only, no fixes.
- Per task, a table: kit check → stage-2 PASS/FAIL → how their docs, tests or generator wording handle it.
- The aim is to learn the wording and structure that keep a hard task inside the kit, and which mechanisms the kit kills.

### D. Lever library (master + Codex draft)
- `master_chat_tasks/knowledge/LEVER_LIBRARY.md` as the index, plus `knowledge/levers/<id>.md`, one card per lever, with:
  - How the lever works.
  - Proof it fails Opus (replay rows).
  - Proof our blind fails (blind score).
  - QC fit (kit lines + phase C result).
  - Recipe: generator pattern, number of hidden inputs, check style, judge probes.
  - Old parked tasks it could rebuild.
- Card status: CANDIDATE → PILOTED → PROVEN.
- Seed cards: PM2.5 echo attribution, exact optimum on hidden instances, warrant convention lever, plus the new ones from B/C.

### E. Pilot (about 1.5 h)
- Mechanism-only pilot of the top 1-2 CANDIDATE levers: a tiny generator + reference, then 3 Opus blinds.
- A lever becomes PROVEN if every blind loses at least 40% of the lever points by WRONG answers, not time-outs.
- Not proven → next lever.

### F. 3 complete tasks (rest of the run)
- For each PROVEN lever, the master picks a new world or a parked task that fits: mix of new and rebuilt.
- Full pipeline: P2 build v5 with the lever card → DESIGN READY → design blind → build → 3 blinds → full QC → fix/recheck → freeze → paid run.
- Done = QC PASS + final < 40.
- A miss gets one harden + rerun. NO CORE gets at most 2 redesigns, then the next lever.
- Up to 3 builds run in parallel.

## Decision rules for auto (master decides alone)
- Shortlist and QC picks by the phase A rules.
- Lever PROVEN / not proven by the phase E bar.
- DESIGN READY go when: predicted final ≤ 35, the design blind loses ≥ 40% of the lever by WRONG, time-outs ≤ 30% (normal cap), and the verifier fits within 90% of its limit.
- QC minor or warning → PL note. QC fail → fix + recheck.
- Paid run after QC PASS + freeze. No cap.
- Stop and ask Ayush: any rule exception, a second miss on the same task, or all levers failing.

## Time and honesty
- Phases A-E: about 5-6 h.
- One full task: about 10-12 h (outage took about 11 h).
- 3 complete tasks will likely need a long night run plus part of the next day. The plan counts what is finished at the stop time and leaves the rest running.

## Answers v2 (31 Oct ~18:05) — these override the phases above where they differ
- **Target:** at least 2 tasks complete (QC PASS + paid run < 40), aim for 3.
- **Hangar `af5dddf` + depot `154f570`:**
  - They count as 2 of the tasks, and start only AFTER the study.
  - Their prompts are re-issued with the study's findings: levers, check style, judge probes.
  - NO CORE after 2 redesigns → park, then a new task from a PROVEN lever.
  - Master flagged a cost: about 5-6 h of waiting. Ayush chose to wait anyway.
- **Tester folder:** `/Users/mac/Desktop/Terminal Bench/_tester/lever_hunt/` holds everything learning-only:
  - The screen.
  - The QC-on-stage-2 reports.
  - The lever library DRAFT.
  - Pilot generators, scoring and scripts.

  Real tasks use the normal pipeline (bundles, Tasks_INPUT, registry) so they can be pushed. Nothing in `knowledge/`, `templates/` or the rule files is edited during the run. The library moves into `knowledge/` only after Ayush reviews it.
- **Phase C:** our kit on 4-5 stage-2 tasks, static gates + QL only, no Docker, no oracle runs.
- **Models:**

  | Part | Model |
  |---|---|
  | Master | Opus 5.5 |
  | Learning (A screen, C QC on stage-2, D library draft) | Codex GPT, subagents allowed |
  | B replays + Docker scoring/gates | opencode `openai/gpt-6.1-sol`, prompt says strictly no subagents |
  | Blinds | opencode `anthropic/claude-opus-5`, same as the paid harness agent |
  | E pilot generator/reference, F build/harden/design, full QC, fixes | Opus 5.5 |
  | Paid run | harness `claude-opus-5`, unchanged |

## Scenario rules (Ayush, 31 Oct ~18:20)

| Scenario | Action |
|---|---|
| Claude usage limit hit | Pause the Claude workers and keep GPT/Codex work going. Resume at the reset time. |
| Codex/OpenAI limit hit (learning parts AND opencode GPT Docker jobs: replays, blind scoring, gate runs) | Move to Claude (Opus) only when no build/QC/fix is running on Claude; otherwise wait for the OpenAI reset. |
| Study finds no new QC-clean lever | Hangar/depot go ahead with the proven exact-optimum family + the PM2.5 echo trap card. Report the finding. |
| Pilot: the top lever is not proven | Pilot the next CANDIDATE once. If that fails too, build hangar/depot without a new lever. |
| Time-out share above 30% | Allow up to 70%, only if the design blind also loses AND the reference is > 4x faster than the best plain solver. |
| Paid run misses the gate | One harden + one rerun. A second miss → park, and start a replacement if time allows. |
| QC keeps failing | At most 3 fix + recheck rounds; minors and warnings become PL notes. A 4th fail → park + report. |
| Docker down or memory/swap very high | Hold new Docker jobs. If Docker is down for 10 min → `open -a Docker`, then resume. Never prune. |
| Worker stalls or loops twice after one continue | Abort it and start a fresh session from its saved state, once per step. |
| Paid run error (infra, not a score) | Retry once after the reset or fix. A second error → report and move on. |
| Last new session | Any session may start up to the end time (Ayush). Sessions started late are cut off by the 2 h wind-down. |
| End time | Start nothing new. Running steps finish, with at most 2 h of wind-down. Report written. |
| Free disk < 20 GB | Delete only this run's `copies/` folders under `_runs` and `_tester`. Never bundles, QC copies, jobs or images. |

## Change (Ayush 18:45): hangar builds in parallel with the study
- **Hangar `af5dddf`** starts at the run start, in parallel with phases A-E.
- **Depot `154f570`** stays after the study. Hangar + depot = the 2 required tasks. A 3rd task, new and built from a study lever, only if time allows.
- **Hangar design bar:** v3.7 standard.
  - Predicted final <= 35.
  - The design blind loses >= 40% of the lever points by WRONG answers.
  - Time-outs within the scenario rule.
  - Verifier within 90% of its limit.
  - Paid gate: final < 40.
  - This replaces the stricter <=25 / 60% bar in the issued IDEA card. The prompt is re-written before spawn.
- **Hangar uses all proven levers:**
  - Exact optimum on hidden larger instances. The fleet-wide overtime coupling blocks the split-into-parts solver.
  - Held-out w5 tier, >= 50% of the test weight.
  - Judge probe band, judge mid <= 20.
  - Per-field partial credit, with no whole-report hashes.
- **Study findings while hangar is mid-build:**
  - The master adds small ones itself: judge probes, check split, an extra hidden-input family that does not change the core.
  - Anything needing a redesign or rebuild → stop hangar and ask Ayush.
- **Hangar NO CORE before the study ends:**
  - One redesign with proven levers.
  - Still NO CORE → pause until the study's levers are ready, then ask Ayush before the rebuild.

## Run (Ayush 18:35)
- Starts right after "proceed". Ends tomorrow 1 Nov 10:00 IST, with at most 2 h of wind-down (until 12:00). New sessions may start up to 10:00.
- 5 workers / 2 harness. Paid runs: no cap.
- Out of scope:
  - Nikhil's task (left untouched).
  - QL replies.
  - Other parked tasks.
  - The upgrade-2 questions.
- Master is this `oc master` chat (port 58456, session ses_ea5ff5f97ffe6WB1VzP4StPOw6).
- Honest timing: about 16 h. The study takes about 5-6 h, so the builds start around midnight and take about 7-9 h each, in parallel. 2 complete tasks are possible by 10:00 only if QC needs at most 1 fix round. Otherwise the finishing step runs into the wind-down.

## Old questions (answered above)
1. Run start and end time, and workers (default 5 workers / 2 harness).
2. Models: GPT opencode for Docker work (replay, QC, scoring) and Opus for blinds — what about the builds (P2/P9)?
   - Recommended: Opus for build design, because it's the hardest reasoning step.
   - Alternative: GPT for builds, to save Claude.
3. Hangar `af5dddf` and depot `154f570` (exact-optimum builds, held):
   - Recommended: let them count as 2 of the 3 tasks, since that family is proven.
   - Alternative: keep them held.
4. Phase C QC runs: full Step 10 Docker gates, or static gates only?
   - Recommended: static gates + QL only, because we don't need their oracle runs.
5. Knowledge base: add Ayush's goal statement and the lever-library pointer to `KNOWLEDGE.md` and `INDEX.md` on "proceed"?
   - Recommended: yes.
