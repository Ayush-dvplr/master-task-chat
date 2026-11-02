# Harness chat: run 3 trajectories (issued 23 Oct 2026 00:05 IST)

Paste below the line into the harness master chat only AFTER the Docker network check prints under 5 s.

---

Run trajectories for 3 QC-clean bundles. Gate for this phase: tests < 100, rubric < 100, overall < 70%.

1. Preflight: `docker ps` (0 task containers), `scripts/anubis-auth doctor` (all checks passed), `codex login status` (logged in). Stop and report if any fails.
2. Network check, must print under 5 s:
   `docker run --rm python:3.12-slim python -c "import urllib.request,time;t=time.time();urllib.request.urlopen('https://pypi.org/simple/pillow/',timeout=120).read();print(round(time.time()-t,1),'s')"`
   If slower, stop and report; do not start runs.
3. Clean the failed network run (README rule): delete only `.kiro-run-district-heat-flex-procurement-20261022T225525/`. Then `.venv/bin/python scripts/master_queue.py resume`.
4. Add the 3 bundles, in this order:
   `.venv/bin/python scripts/master_queue.py add "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cohort-retention-reconciliation" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement"`
   (max 2 at once; the third starts when one finishes).
5. Save the runner PID and stop. When a run finishes: give the master chat the job folder path and the `scores` line for that task. If a run fails at startup with a network error, do not retry; report it.
