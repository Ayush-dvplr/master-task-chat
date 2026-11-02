# Lever hunt + builds: FINAL plan (31 Oct ~19:00 IST)

This replaces [PLAN_DRAFT_v1.md](PLAN_DRAFT_v1.md), which is kept for the history of answers. Nothing starts until Ayush says "proceed".

## Goal
Make tasks that fail Opus AND pass our full QC kit. To do that:
- Learn how the anubis-stage-2 tasks get low scores.
- Learn how they get past QC.
- Store the levers in a library, to use for new tasks and for rebuilding old ones.

**Done after this run:** at least 2 tasks with full QC PASS + a paid run final < 40; aim for 3.

## Run
- Start: right after "proceed".
- End: 1 Nov 10:00 IST. New sessions may start up to 10:00. After that, at most 2 h of wind-down (until 12:00); nothing new starts.
- 5 workers / 2 harness. Paid runs: no cap.
- Master: this `oc master` chat, Opus 5.5.
- Overnight: the master decides every "ask Ayush" point itself, takes the recommended option, and logs it as "decided in place of Ayush" in REPORT + decisions.jsonl. Ayush can reverse it in the morning.
- Out of scope: Nikhil's task, QL replies, other parked tasks, upgrade-2 questions.
- Tester folder `/Users/mac/Desktop/Terminal Bench/_tester/lever_hunt/` holds all learning output: screen, QC-on-stage-2 reports, library draft, pilot.
  - Real tasks use the normal pipeline (bundles, Tasks_INPUT, registry, board).
  - No edits to `knowledge/`, `templates/` or the rule files. The library moves into `knowledge/` only after Ayush reviews it.

## Models

| Part | Tool | Model | Subagents |
|---|---|---|---|
| Master | opencode (this chat) | Opus 5.5 | — |
| A screen, C QC on stage-2 (static), D library draft | Codex | GPT | allowed |
| B replays/instrumenting, blind scoring, Docker gate runs | opencode | `openai/gpt-6.1-sol` | not allowed (written in every prompt) |
| Blinds (study, pilot, builds) | opencode | `anthropic/claude-opus-5` (= paid harness agent) | not allowed |
| E pilot generator/reference; F build, harden, full QC, fixes | opencode | Opus 5.5 | not allowed |
| Paid run | harness | `claude-opus-5` (unchanged) | — |

## Two tracks, in parallel from the start

### Track 1: learning (about 5-6 h)
- **A. Screen all 102 stage-2 tasks** (Codex + script, no Docker). Writes `SCREEN.csv`:
  - Opus final, tests and judge.
  - Hidden-input count and type.
  - Check style: per field / per report / whole hash.
  - Exception-to-False wrappers.
  - Doc-vs-generator red flags.
  - Judge share.

  Fixed rules pick a shortlist of 8-10 tasks that are low AND look clean, plus 4-5 for the QC runs (billing, PM2.5 + 2-3 more).
- **B. Deep dive** (opencode GPT, Docker; 3 tasks per session, 3-4 sessions):
  - Replay and instrument Opus's outputs and label every lost point, reusing the A1/A2 scripts and their local-base workaround for the private ECR image.
  - An Opus-5 blind only where the replay shows a fair trap.
- **C. Our QC kit on 4-5 stage-2 tasks** (Codex, static gates + QL only, no Docker or oracle). Per task: kit check → PASS/FAIL → how their docs, tests or generator handle it.
- **D. Lever library draft** in the tester folder: `LEVER_LIBRARY.md` + `levers/<id>.md`. Each card covers:
  - How the lever works.
  - Proof that Opus fails.
  - Proof that our blind fails.
  - QC fit.
  - Recipe.
  - Old tasks it could rebuild.
  - Status: CANDIDATE / PILOTED / PROVEN.

  Seed cards: PM2.5 echo attribution, exact optimum on hidden larger instances, warrant convention lever.
- **E. Pilot the top CANDIDATE:**
  - A tiny generator + reference (Opus 5.5), then 3 Opus-5 blinds, scored by GPT.
  - PROVEN = every blind loses >= 40% of the lever points by WRONG.
  - Not proven → pilot the next CANDIDATE once. If that also fails, the builds go ahead without a new lever.
  - If no CANDIDATE is found at all, the builds use the known levers and the finding is reported.

### Track 2: hangar `af5dddf` (from the start)
- The IDEA card and build prompt are rewritten before spawn, then `issue.py --lint` clean.
- **Levers:**
  - Exact optimum on hidden larger instances. A fleet-wide overtime limit couples the 4 bases, which blocks the split-into-parts solver.
  - Held-out w5 tier, >= 50% of the test weight.
  - Judge probe band, judge mid <= 20.
  - Per-field partial credit, no whole-report hashes.
- **Design bar (master sends go):**
  - Predicted final <= 35.
  - The design blind loses >= 40% of the lever points by WRONG.
  - Time-outs within the rule below.
  - Verifier worst <= 90% of its limit.
  - Reference <= 1/4 of the per-run limit.
- **Study findings while hangar is mid-build:**
  - The master adds small ones itself (judge probes, check split, an extra hidden-input family that doesn't change the core).
  - A redesign or rebuild is decided by the master overnight and logged.
- **Redesigns:**
  - 1 before the study ends. If still NO CORE, pause until the study's levers are ready.
  - 1 more after the study (total 2).
  - Then park, and start a replacement task from a PROVEN lever.

### After the study: depot `154f570`, then a 3rd task if time allows
- Depot gets the same bar as hangar, with its prompt rewritten using the study findings.
- 2 redesigns max, then park and start a replacement task from a PROVEN lever.
- A 3rd task (new or rebuilt, the master picks) only from a PROVEN lever.

## Task pipeline (every build)
1. P2 build v5 → DESIGN READY → design blind (Opus 5) → master go.
2. Build → 3 fresh Opus-5 blinds.
3. Full P11 QC (Opus 5.5) → fix/recheck (max 3 rounds; minors and warnings are PL notes; a 4th fail → park).
4. Freeze: bundle == Tasks_INPUT == QC copy, tree sha in the registry.
5. Paid run, `auto.py harness`.
6. Final < 40 = done (pl_ready; Ayush pushes).
7. A miss → one harden + one rerun. A second miss → park, then a replacement if time allows.

## Scenario rules

| Scenario | Action |
|---|---|
| Claude limit | Pause Claude workers and resume at the reset; GPT/Codex work keeps going. |
| Codex/OpenAI limit (learning or GPT Docker jobs) | Move to Claude only when no build/QC/fix is running on Claude; otherwise wait for the reset. |
| Time-out share > 30% of lost points | Allow up to 70% only if the design blind also loses AND the reference is > 4x faster than the best plain solver; otherwise redesign. |
| Docker down 10 min or memory/swap very high | Hold Docker jobs; `open -a Docker`; never prune. |
| Worker stalls or loops twice after one continue | Abort and start a fresh session from its saved state, once per step. |
| Paid run error (infra) | Retry once after the reset or fix; a second error → report and move on. |
| Free disk < 20 GB | Delete only this run's `copies/` under `_runs` and `_tester`. |

## Master check-ins
Timed plan lines every 30 min from 19:30 to 02:00, while the Codex steps run. At each check-in:
- Look at the Codex jobs (status, last.txt, result json) and act if one finished or failed.
- Do a rule check on the Codex logs: no Docker, no writes outside OUT.
- Otherwise do nothing.

## Do not
- Push or commit.
- Edit `knowledge/`, `templates/`, rules or policy.
- Edit `anubis-stage-2`.
- Touch pushed or parked tasks (except a parked world chosen for a rebuild), Nikhil's task, or QL replies.
- Docker prune.
