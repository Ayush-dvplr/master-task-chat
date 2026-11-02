# COST_TABLE (build try 3, measured on the FINAL tests)

All rows measured in Docker (python:3.12-slim, --memory 4g --cpus 2) with WORK/harness/score.py
against BUNDLE tests/test_output.py (44 checks, positive 152). Logs: WORK/proto/t4/score_<program>.txt.
"deliver" = the five compiler calls on the shipped corpus; "checks" = every registered check
(the verifier's share); total = deliver + checks.

| program | what it does | measured | adjusted | lever kept | loss kind (16 conv checks) | deliver s | checks s | total s |
|---|---|---|---|---|---|---|---|---|
| a1 program | a1's delivered tool.zip as is | 72/152 = 47.4 | 47.4 | 0/80 | WRONG x16 | 4.7 | 278.5 | 283.2 |
| P0s first-write | shipped readings fixed (hr site, start decided, window half) | 69/152 = 45.4 | 47.4 | 0/80 | WRONG x16 | 11.3 | 352.7 | 364.0 |
| P2n careful blind | infers hr {site, utc} x start {requested, decided, recorded} from the observations | 69/152 = 45.4 | 47.4 | 0/80 | WRONG x16 | 426.9 | 774.7 | 1201.6 |
| P3b binary | shipped reading vs legacy reading per convention | 69/152 = 45.4 | 47.4 | 0/80 | WRONG x16 | 315.1 | 627.3 | 942.4 |
| P4o all-but-one | infers hr {site, utc, every zone} and window; start fixed decided | 69/152 = 45.4 | 47.4 | 0/80 | WRONG x16 | 649.1 | 970.6 | 1619.7 |
| P6o careful wide (reference class, master ruling 1) | {site, utc, every zone} x {requested, decided} x {half, closed} | 149/152 = 98.0 | 100 | 80/80 | EXACT | 600.9 | 991.5 | 1592.4 |
| oracle tool (oracle_wip/conv) | solution inference | 152/152 = 100 | 100 | 80/80 | EXACT | 482.9 | 756.8 | 1239.7 |

"adjusted": score.py writes a synthetic report.json whose single repair names `engine.py`; the
kill program folders have no engine.py, so report_transcript_complete (w3) fails for them only.
A real delivery names its own module, so the adjusted score credits those 3 points. The a1
program has engine.py and passes it as measured.

Every kill program passes all 28 original checks except that harness artifact, fires no negative,
and fails all 16 conv checks with a wrong document (no crash, no timeout).

## Bars (go ruling and LEVER_RULES_v3 G10)
- a1 program 47.4 <= 60: PASS.
- blind and agent programs (P0s, P2n, P3b, P4o) 47.4 each <= 65, none > 70: PASS.
- first-write P0s 47.4 and all-but-one P4o 47.4 <= 65: PASS.
- every generic program loses 80/80 = 100% of lever points (>= 15%): PASS.
- crash/timeout share of the lever loss: 0/80 = 0% (<= 30%): PASS.
- G10 per dimension: start wrong alone (P4o: hr and window inferred, start fixed) loses 80/80;
  hr wrong alone (P2n: start inferred, zone clocks outside its readings) loses 80/80; each >= 25%.
- All-but-one predicted final with the design judge estimate: (47.4 + 30) / 2 = 38.7
  (peer judge 40: 43.7), below 70.
- Predicted a1-like final 38.7 (peer formula 43.7) <= 45 bar, < 50 target.
- P6o is reference class (master ruling 1), not a blind: the master's 3 fresh blinds decide.

## Verifier seconds (checks share; task.toml verifier timeout 2700 s, cap 2430 s)
- Worst case measured: P6o 991.5 s, P4o 970.6 s (aim 900-1,200 s): PASS.
- Oracle-class: oracle tool 756.8 s, P2n 774.7 s, P3b 627.3 s.
- Biggest single check: artifacts_reproduce_from_tool (re-runs the delivered tool on the shipped
  corpus): oracle 479.6 s, P6o 588.2 s, P4o 617.1 s, P2n 430.0 s, P3b 291.4 s, a1 5.5 s.
- Conv dev checks 6.6 to 41 s each (prod reuses the cached run, 0.0 s); no check reached the
  900 s per-call subprocess limit (test_output.py:29826).

## Shipped inputs fast (shipped oracle, solution/solve.py, Docker 4 GB 2 CPU, proto/t4/solve5.txt)
- Per compiler call on the shipped corpus: resolve-config 0.4 s (original tool before repair and
  repaired tool), compile dev 108.5 s, compile prod 110.5 s, audit 106.0 s, summarize 105.1 s:
  every call <= 120 s target (ruling 3). Whole oracle run 614.7 s (agent limit 7200 s), rc 0.
- Self-check witnesses r1 to r8 all discriminate between the settled reading and its rival.
