# PLAN: night 30 Oct ~01:00-10:00 (Ayush 00:20-00:55; gate v3.7). STARTED 30 Oct ~01:12 (Ayush: "start")

Until: 10:00 IST
Paid runs: 99 (= no cap; Ayush said "No cap"); each run only on frozen QC-passed bytes, never twice on the same bytes
Workers/harness/Docker: 5 / 2 / 3 Docker-heavy (Docker VM 16 GiB; check `docker ps` + `sysctl vm.swapusage` before each Docker-heavy spawn; swap > 20 GB -> hold)
Budget: paid run only with no LIMIT and <= 2 busy workers; <= 3 busy while it runs
Wind-down: running sessions and running paid runs finish their current step after 10:00; nothing new
Last spawn: 09:40
Model: anthropic/claude-opus-5-5 (auto.py default)

Ayush's words (verbatim, 30 Oct 00:40-00:55):
> Push a6 47.84 | Target <50, pred <=45 | Full QC, then fresh run | Keep <40 | No cap | harden and rerun but take decisions wisely | option 1 is good but can you do that as these session are opened in normal mode and do not assume ? | 5 workers / 2 harness / 3 Docker-heavy, Claude Opus | Last spawn 09:40, finish step | Park
> Slipway: Harden, target <40 | Schema option b: Yes, approve if narrowest | Crash/timeout cap: Keep existing exceptions only | Warrant: Yes, <50 is pass

Gates: metered, schema, slipway: tests < 85 AND rubric < 85 AND final < 40. Warrant: tests < 85 AND rubric < 85 AND final < 50 (pass = ready to push). Gate met -> stage pl_ready (Ayush pushes).
Crash/timeout share of lost lever points: 30%; exceptions only tariff 60%, schema 70%. A design needing more -> Needs Ayush.
On a miss: at most one harden + one rerun per task, and only if the harden's DESIGN READY bar is met with a measured kill table; NO CORE or a new rule exception -> Needs Ayush.

## Start (after Ayush says "start"; 145bdba finished, 6740572 + 6ebf33a stopped by Ayush ~00:58, windows closed)
1. `auto.py start --until 10:00 --plan plans/20261030_night_plan.md --label night --workers 5 --harness 2 --no-adopt`; then `auto.py adopt 6ebf33a`, `adopt 6740572` (found by title in the opencode DB; state interrupted). 145bdba is not adopted (done). Check master_queue paused flag (`master_queue.py status`); `master_queue.py resume` only if it shows a stale PAUSED reason.
2. Paid run first (budget: <= 2 busy workers at launch): `auto.py harness <Tasks_INPUT/metered-usage-rating-pipeline>` (frozen bbc865f36130 = bundle = QC copy 145bdba, QC v4 PASS 0/0/0; registry stage gate_runs).
3. `auto.py send 6740572 @prompts/issued/warrant-asof-entitlement-compiler/20261030T0100_continue_target50.md`; `auto.py send 6ebf33a @prompts/issued/schema-migration-plan-repair/20261030T0105_continue.md`.
4. `auto.py spawn e2bfbf0 prompts/issued/slipway-overhaul-replan-repair/20261030T0100_harden.md` (3 busy while the run is up = budget max; Phase 0 is reading only).
Docker at start: c6740572a (warrant profiling, alarm 900 s) may still be up; schema's slow block is ALL_DONE.

## Tracks (priority metered > schema > slipway > warrant)
### metered-usage-rating-pipeline (QC v4 145bdba PASS 0/0/0, frozen bbc865f36130; master checked 01:05)
Paid run at start (Start step 2) -> after run: copy jobs/<slug> to master_chat_work/20261030_<slug>/gate_run_aN, trajectory_readout TRIP.md, intake --event gate_run --apply. Gate met -> pl_ready. Predicted final 39.8-45.7: a miss -> one harden round from that trajectory -> P11 v3 recheck v5 (prev copy 145bdba) -> freeze -> 1 new run.
### schema-migration-plan-repair (P12 fix 6ebf33a, DS-20 option a)
DONE -> verify (oracle g2/g4 + stress <= 2.5 s, identical plans, budget) -> P11 v3 recheck v14 (prev copy QC/copies/68bec9e) -> freeze -> attempt 7. PAUSED for option b -> approve only the narrowest contract wording (Ayush yes); docs changed -> 3 fresh blinds -> recheck v14 -> freeze -> attempt 7.
### slipway-overhaul-replan-repair (harden e2bfbf0 from a3 77.52)
DESIGN READY -> go only if bar met (pred final <= 35, a3 program <= 60, lever share >= 40%, crash/timeout <= 30%, verifier worst 900-1,200 s) -> build -> docs changed -> 3 blinds -> full P11 v3 QC (MODE full, first QC) -> fix if FAIL -> freeze -> run. NO CORE -> Needs Ayush.
### warrant-asof-entitlement-compiler (design try 3, 6740572)
DESIGN READY with pred final <= 45 -> go -> build -> WORK/BLIND_BRIEF.md + 3 fresh blinds -> full P11 v3 QC -> freeze -> attempt 2. NO CORE -> Needs Ayush.
### tariff (pushed by Ayush, a6 47.84) / district (pushed) / cold-chain, multicorner (parked)
Nothing. Set tariff stage=pushed once Ayush confirms the push.

## Rules per event
- Every DONE: verify on disk (files, shas, tree method `find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`) before the next step; one evidence check, no re-verification.
- QC prompts: python substitution from the task's previous QC prompt (sha, prompt name, _progress_vN, prev report, prev copy) + Note line (Docker 16 GiB VM, <= 2 other Docker-heavy, rising-counter polls). Use `tools/board.py new` for shas, `issue.py --override` with Ayush's words when it refuses.
- Log every decision in decisions.jsonl and REPORT.md (Master log).

## Do not
Push or commit. Edit rule files, templates, GOALS or policy. Touch pushed (tariff, district, sentinel, ...) or parked tasks (cold-chain, multicorner). Start new tasks. Docker prune. Re-run on the same bytes. Type into a session Ayush still has open.

## Added 02:40: Ayush 02:29 overrides 'Start new tasks' in Do not (one new task only: outage-window-replan) and closes slipway (parked) and metered (pl_ready, a4 44.05 accepted).
Ayush: park slipway; metered ready to push (accepts a4 44.05; verifies after the run). "if time is remaning ... create 1 or 2 new task any domain anything as per your recomendation QC passed and under the gates score". Answers: start now in parallel, 1 task, master picks, "just try and build so that it is QC clear and gap under cap of <40 overall (no cap on runs)".
### 5. outage-window-replan (new, lowest priority for Docker)
1. P2 build v5 (board 7d363c8, prompt prompts/issued/outage-window-replan/20261030T0245_build.md, IDEA prompts/issued/outage-window-replan/IDEA.md). DESIGN READY bar met -> master go; NO CORE -> stop, Needs Ayush.
2. DESIGN BLIND READY -> master issues 1 P13 blind read -> continue.
3. DONE -> 3 fresh P13 blinds -> full P11 v3 QC -> fix/recheck -> freeze -> 1 paid run (gate final<40). One harden+rerun on a miss under the usual rules.
