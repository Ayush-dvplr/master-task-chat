Master (auto) message for B3 session `5696715`: score one Opus-5 blind program on spectral.

Strictly do not run subagents (no task, agent or background-agent tools). Do all work yourself in this main chat.

A fresh claude-opus-5 blind solved spectral (`cf9b2067`) from instruction + environment only:
- BLIND_DIR: `/Users/mac/Desktop/Terminal Bench/_runs/20261031/lever-hunt/blind-spectral-20261031T2300-bb34` (program `app/reconcile.py`, outputs `out/`, notes `work/BLIND_REPORT.md`, `work/FINAL_REPLY.md`, `work/JUDGE_ESTIMATE.md`). Read-only: do not edit anything there.

Do (same rules as your replay prompt: scratch under `/Users/mac/Desktop/Terminal Bench/_runs/20261031/lever-hunt/replay-5696715/`, dockfree START=yes before every container, harbor `--agent oracle` only, tests-only copy, early-exit poll loop):
1. Build a scratch tests-only copy of spectral whose `solution/solve.sh` copies the blind program into the path the instruction names and runs it exactly as the instruction says (no other help). Run it through your instrumented verifier (same as your spectral replay).
2. Table per lost check: check, weight, cause code (same codes as CAUSES.csv), and whether the recorded Opus run / your replay also lost it. Say specifically how the blind did on the three empty-axis extracts (the fixed-declared-universe lever, 15 raw) and the decimal-identity checks.
3. Write `/Users/mac/Desktop/Terminal Bench/_tester/lever_hunt/B_replay/B3/BLIND_SPECTRAL.md` (line 1 `VERDICT: blind tests X% vs replay 78.26%; fixed-universe lever kept|lost`) and `/Users/mac/Desktop/Terminal Bench/_tester/lever_hunt/B_replay/B3/result_blind.json` {"blind":"dec345f","tests":x,"lost_raw":x,"by_cause":{},"fixed_universe_lost_raw":x,"decimal_lost_raw":x} (must parse). Remove your containers.
Final reply (3 lines): blind tests %, fixed-universe result, report path.
