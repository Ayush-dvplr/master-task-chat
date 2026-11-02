# district-heat v0 trajectory (1 run, claude-opus-5, job 2026-10-21__23-29-37): NO SCORE
Copy: ./trajectory_job_2026-10-21__23-29-37_timeout/ (source .kiro-run-district-heat-flex-procurement-20261021T232853, read only)
- Harbor: AgentTimeoutError after 7200 s; verifier never ran (no reward, no ctrf); no trajectory.json saved.
- The agent did deliver /app/out (derive_report.py at 01:23, records at 01:24 IST). derive_report.py is mode 0600, so the latent permission trap (run_agent L897-911, never opened to nobody) WOULD have hit a verifier run.
- Scoring possible later by replaying these artifacts in Docker with a fixed verifier (as done for vendor/emberforge).

## Run 1 (job .kiro-run-...-20261021T173139): also NO SCORE
Copy: ./trajectory_job_20261021T173139_timeout/
- Same AgentTimeoutError after 7200 s; judge failed (no /logs/agent/trajectory.json); no ctrf.
- derive_report.py again 0600 (perm trap would hit).
- Both runs' visible-day outputs are byte-identical (region_East.json), so the agent's program was stable on the shipped data.

## What used the time (from agent/openhands_sdk.txt, the only agent log saved; ~385 KB each)
- Run 1: the program ran in 3-8 s on /app/data; the agent built its own 22-site stress cases (/tmp/max22) and timed them at 21-23 s against the instruction's 30 s limit, then kept re-tuning.
- Run 2: self-made stress runs hit 54-120 s, and several were killed at exactly 120.0 s (its own timeout); final shipped-data runs ~1 s.
- Conclusion: the 30 s limit on the exact search (LV-DH-1) drove open-ended performance tuning until the 2 h budget ran out. openhands_sdk.txt can stand in for trajectory.json when diagnosing P9 r2.
