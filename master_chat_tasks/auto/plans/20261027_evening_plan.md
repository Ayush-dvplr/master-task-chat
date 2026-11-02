# PLAN for this auto run (written by the master from Ayush's words; wins over AUTO_POLICY.md)

Until: 22:00 IST (27 Oct 2026)
Ayush's words (verbatim):
> Okay, so basically from now on till 10 PM, I want you to run on auto mode, but first of all make the list of everything and show me what will be you will be doing on auto mode. There will be two days for today. There will be four harness session and two sorry there will be four sessions and two harness sessions., and four additional docker sessions  apart from the ones using docker  Ask me questions if you got confused and do not assume also flag me if right now something is not possible to run in auto mode.

Answers (27 Oct ~20:30): "two days" = typo, ignore; Docker = up to 4 Docker of the 4 workers; none of the 5 issued prompts pasted (spawn all); free slots stay idle; sessions running at 22:00 finish (wind-down); 3 blinds each for new rounds only (metered, district, cold-chain), tariff and schema go straight to QC; order = QC + fix first.

## Limits
- Workers 4, harness 2. Docker cap 4 (overrides AUTO_POLICY "max 2 Docker-heavy"); still check `docker ps` and memory (`vm_stat`, swap) before each Docker spawn; if swap > 20 GB, hold new Docker spawns.

## Do, in this order
1. Spawn now: 04fcb4f tariff QC v3; c113d6e schema QC v3; 25c745d cold-chain Law-1 fix; 6f5046a metered blind 1.
2. Queue (fill free slots in this order): ef9234c district blind 1; metered blind 2; district blind 2; metered blind 3; district blind 3 (each a fresh /tmp/blind/<slug>-<ts>-<hex4> dir, P13 copy of the 20:25 blind prompt).
3. When all 3 blinds of a task are done: one Docker scoring session for that task's 3 blinds (exe_copy.py tests-only copy, method of 185c588). Each blind >= 10% loss and loss passes Law-1 v3.5 -> issue P11 v3 full QC. Else -> Needs Ayush.
4. 25c745d done (DONE) -> 3 fresh blinds for cold-chain (queue after step 2 items) -> score -> QC as step 3. NEEDS DOC CHANGE -> Needs Ayush.
5. QC PASS / minors only -> freeze (tree sha), `auto.py harness <Tasks_INPUT bundle>` 1 run. Gate met (tests<100 AND final<70) -> pl_ready, stop. Miss -> trajectory_readout + fix prompt (QC-safe), recheck, 1 new run; never re-run same bytes.
6. QC FAIL -> one P12 v4 fix session (G1-G7) -> P11 v3 recheck.

## Do not
- Push, commit, or edit rule files/templates/GOALS/policy.
- Start sentinel 3eb08a6 (held for QL review), wave 3 designs, new builds, Docker prune, Q52.
- Fill idle slots with anything not on this list.
- Start anything new after 22:00; running sessions finish (wind-down up to 2 h).
