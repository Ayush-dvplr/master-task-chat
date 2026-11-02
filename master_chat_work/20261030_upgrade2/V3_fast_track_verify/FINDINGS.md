VERDICT: The fast-track plan is viable with the fixes in `FAST_TRACK_PLAN_v2.md`; Docker and full-suite release gates remain unverified here.

## 1. Today's claims

Finding: Five of nine claims are only partly right or overstate missing features. Evidence and RIGHT/WRONG judgments are in `VERIFY_REPORT.md` section 1, based on `auto/auto.py`, `tools/issue.py`, the active templates and `master_queue.py`. Recommendation: use the corrected descriptions and implementation boundaries in v2. Gain: avoids reimplementing existing guards. Risk: an incomplete inventory could miss a path; verify with the v2 diff and grep before switch-on.

## 2. Numbers

Finding: The 13-item QC table matches the report-mention measure (95 reports, 17 task folders); the three speed savings are estimates, not controlled measurements. Evidence: `scripts/count_qc_failures.py` and `S6_auto_speed/scripts/measure_lanes.py` outputs in `VERIFY_REPORT.md` sections 1–2. Recommendation: benchmark same-tree lanes and matched task pilots. Gain: credible speed decisions. Risk: benchmark load differs from production; record load and QC outcomes.

## 3. Ayush's answers

Finding: Exact task lines, 30% default, no-core park, QC note for QL and manual paid-run authority need explicit scope and preflight. The QC kit's five-oracle language leaves one paid-run-readiness decision. Evidence: `FAST_TRACK_PLAN_v1.md` section 4, `AUTO_POLICY.md:19-31`, `Final_checklist.md:354-367`. Recommendation: implement v2 Step 2 and ask only `QUESTIONS.md` question 1. Gain: fewer waits while preserving authority. Risk: broad pre-approval; test refusal cases.

## 4. Breakage and tests

Finding: LIMIT, busy-worker caps, queue FIFO/flock/resume, freeze hashes, worker permission and Docker cleanup are the primary regression boundaries. Baseline: auto unittest 73 run/24 socket errors; tools unittest 30 run/3 stale-fixture failures; harness unittest 0 collected. Evidence: `VERIFY_REPORT.md` section 4 and `auto_test.log`, `tools_test.log`, `harness_test.log`. Recommendation: repair fixture drift and run actual harness pytest plus all release tests in a host environment permitting loopback. Gain: protects current behavior. Risk: this sandbox cannot certify green; verify before enablement.

## 5. Design holes

Finding: Docker event delivery and `~/tb_runs` bind mounts could not be checked here; D4 lacks a durable complete manifest; A5 cannot prove semantic reachability by syntax. Evidence: `VERIFY_REPORT.md` section 5. Recommendation: fail closed on uncertain leases, save run evidence, pilot Codex confinement and mount behavior, and use arithmetic attestation. Gain: fewer polls/repeated gates without hidden quality loss. Risk: extra implementation time; verify each v2 gate.

## 6. Order

Finding: D1 before D6, D5 before D4, dockslot before production lanes, and empty Docker before benchmark are required dependencies. Evidence: `auto.py:498-500`, `P12_recheck_fix_v4.md:67,73`, `master_queue.py:612-628`, `MEASURE.md:208-210`. Recommendation: follow v2 Steps 0–9, including snapshots, CHANGELOG, rule hashes and rollback. Gain: reversible rollout. Risk: switching during live work; switch only between runs and verify smoke before wider use.
