# ALTERNATIVES - ideas the master did not propose (board e66cd5f)

Written 24 Oct 2026 ~10:55 IST. Costs marked *guess* are estimates, not measured.

| # | Idea | Evidence | Cost | Risk |
|---|---|---|---|---|
| A1 | **Finish the two live candidates before any new build.** dispatch has a real trap (tests 67.33) and only needs rubric < 72.67 (sc:61); emberforge has a real 20-pt computation loss once I3 is restored (p14_a7). Both are already in P12 (9fe2a50, f99c855) | sc:61, sc:68, p14_a7 | 1 judge fix + 1 run each (~$9-13 per run, job-result.json) | emberforge loss may not repeat (n = 1) |
| A2 | **Repeat-run before calling a gate.** The gate (dec:63) is judged on one run; KNOWLEDGE.md:8 says one run does not measure difficulty, and 9 runs are needed to certify < 0.30. Run every gate candidate twice before PL | KNOWLEDGE.md:8; I did not find two runs on the same bundle sha in scores.jsonl (*guess*, not exhaustively checked), so run variance is unmeasured | +1 run per candidate | Doubles run spend on candidates only |
| A3 | **Standing false-positive dossier for PL.** PL accepts a proven real FP (brief). VARIANCE.md has 45 verdict flips on byte-identical text, e.g. sentinel JD-2 same observation opposite verdict. One file per check id with the flip evidence makes "proven FP" cheap | qc_reverse/B/VARIANCE.md | ~1 session to compile *guess* | PL may reject variance as proof; ask first |
| A4 | **One acceptance bar, written once.** Replace dec:61, dec:88, dec:93 and _COMMON_RULES_v2:42 with dec:101 (zero findings); re-label every `qc_clean` task that kept a minor or warn (dispatch 0/3/4, district 0/0/1, vendor 0/0/2, sensor 0/1/1 per status.py) | row 12 | 1 records edit by master | Reopens 4 tasks that looked done |
| A5 | **Write judge criteria from the probe run, not at build.** Aim each positive at an observable the run got wrong; ban criteria that only restate a TRUTH.md figure | sc:60 (12/15 judge pts states-figure), sc:61 (17/21), les:71 | 0 extra; moves work later | Judge built after a run must still pass JD-7 (oracle meets every criterion) |
| A6 | **Triage the 7 converted tasks by reading their v0 verifier output, not by re-hardening.** Drop >= 0.95 now (cohort-uplift 1.0, pcggc 1.0, specdec 1.0, 7ef8d80a 0.9911). For caldermoor 0.8722, numeric-reduction 0.874, season-ladder 0.8209 read which tests failed: a dispatch-style natural trap may already exist | status.py; dispatch natural trap found the same way (les:71). Permission artefact on these v0 runs UNVERIFIED (sc:11, sc:12) | ~0.3 h read per task *guess* | v0 scores may be artefacts; re-check validity first |
| A7 | **Per-test loss script.** A small read-only script that maps a verifier output to "points lost per check, per hidden input" so a run's real trap is visible in minutes instead of a full P14 group | P14 sessions did this by hand (3 groups); emberforge needed "one-line variant flips it" to attribute (p14_a7) | ~1 session to write *guess* | Low |
| A8 | **Kill rule on first probe.** Probe tests >= 95 -> kill or swap core; no QC, no harden. Write it into P2 v3 and the issuing tool | row 1, row 14 | 0 | Kills a task a second run would have failed (variance); accept that |
| A9 | **Time box per task, not only round counts.** Cap at ~8 sessions from idea to PL submit *guess*; schema and emberforge took 16 each | board.json rows per task | 0 | A hard number may cut a near-pass; allow one logged override |
| A10 | **Probe validity check.** Before trusting a probe score: oracle = 1.0 and nop = 0 in the harness, staged from the current path only (18 of 26 job configs pointed at the old copy, LEAK_REPORT:115) | sc:11, sc:12, sc:49-51 invalid; LEAK_REPORT:115 | ~10 min per probe *guess* | Low |
| A11 | **Raise harness max to 3 for probes** if Docker memory allows (master_queue.py:63 default is 3; held at 2) | harness traj note 20261023T1745 | 0 | Usage limits (emberforge a5, a6 no score); OOM |

## Research queue (read-only, no model calls)

| # | Question | Method | Cost |
|---|---|---|---|
| R1 | Do peer tasks pass the live kit 71a653b2 with zero findings? | Run the kit's deterministic scripts (no LLM) on 3-4 peer bundles from Anubis_Tasks_Samples/Pass@1_New: gm-arena, sentinel-fraud, slo-credit, lane | ~1 session |
| R2 | What did PL actually accept, and with which kit head / FP notes? | `gh api` GET on ShreeyankDoliya/Finalized_Tasks_RFP: list accepted tasks, read their QC files and commit dates vs kit history | ~1 session |
| R3 | Is a private probe run allowed before QC under the QL rule (dec:55)? | Ayush asks QL; not researchable | 1 message |
| R4 | Is the emberforge max-flow loss repeatable? | Covered by A1/A2 (one run) | 1 run |
