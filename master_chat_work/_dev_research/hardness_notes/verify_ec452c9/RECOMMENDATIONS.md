# Recommendations (proposals only; nothing applied)

Evidence for each item is in `CLAIMS.csv` (ids) and `ANALYSIS.md`.

## Adopt as-is

1. **Solvability probe, D2 section 17 (C027).** For every literal the oracle emits, classify it as STATED, DERIVABLE, UNREACHABLE or INVENTED. Any UNREACHABLE or INVENTED literal must be fixed before QC.
   - It targets DS-21, DS-25 and CL-10, which cost us match-replay v2 F1 (SC:74).
   - It is cheap and runs once per build.
   - Add it as a pre-QC step in `P2_build_v4.md`, next to the existing self-check.
2. **Law 1 as a lever filter (C028).** A computation lever counts only if a fast generic program writes valid but wrong output. Naive timeout alone does not count.
   - The sentinel r3 losses were all silent: 0 crashes, 21.4% lost (`harden_t3/HARDEN_REPORT.md:4`).
   - District-heat timeouts were grader artefacts (LR:221).
3. **Weight and check mechanics already in the kit:**
   - TS-20 weights by meaning (C069)
   - one check per compared value under CL-4 (C078)
   - no AL-28 stacking
   - JD-15 type labels (C079)

   Sentinel v1/v5/v6 failed on exactly these. They are already rules, so adopting them means checking them in `P2_build_v4.md` before the first QC, not new rules.
4. **No answer key visible to the agent; per-seed variation of hidden data; held-out hidden tier** (C045, C047, C075). These are already ours. Keep them.

## Adapt (exact change)

1. **`LEVER_RULES_v3.md` §1C (P-1 and P-3 entries).** Add one line: "Valid only when a named fast heuristic (greedy, first-tie, local optimum) writes plausible wrong output on the hidden instances. A lever that loses only by timeout gives a recovery signal (D2 law 1); do not count it."
2. **`LEVER_RULES_v3.md` P-2 entry.** Add one line: "Chain depth (p^n, D2 15.3) adds difficulty only when one stage has p<1 for a strong program. Schema e3e74e6 long replays were exact for blind and Opus (SCH:8). Put a P-1/P-3 stage inside the chain; keep weights by meaning (TS-20), not by stage position."
3. **`_COMMON_RULES_v4.md` variance note.** Cite the kvec pair as the variance example: the same bytes scored tests 17.12 and 37.93 (`C_daaca581_DIFF.md:3`). Use it to reject single-run evidence from outside guides as well as our own.
4. **`QC_RULINGS.md`.** Add one ruling: "Counterfactual or what-if figure criteria in the closing message (D2 9.3): AVOID. J1, JD-7 failures (QR:107, QR:154), AL-2/CL-1 (QR:133), JD-5 if several figures go in one criterion."
5. **`P9_harden_from_results_v3.md`.** Turn D2's "top 3 failure modes carry more than 1/3 of positive test weight" (C050) into a *read-out* after a probe, not a build quota: list which checks the probe failed and their share of the weight. The probe already gives this.

## Ignore (and why)

| Item | Claims | Reason |
|---|---|---|
| Withheld-but-derivable rules (D2 5.9, D1:46) | C043, C044 | Same as our L11. Leaked 3/3 (tariff 157/157; sentinel r2 98/98). QC AL-1/05:27/CL-10/DS-21 risk. Contradicts GOALS G11 and D2:1998 |
| Counterfactual judge figures (D2 9.3, D1:69) | C082, C083 | Opus answers figures right (LR:150); JD-7/JD-5 failures |
| Volume quotas: 50-60 files, ≥2000 lines, ≥12 trap types, ≥12 traps per file, ≥12/≥20 constraints | C052, C058, C059, C062 | Playground A5, not the kit (KNOWLEDGE.md:27; tests_qc.py:51). Stated breadth went exact (fuel-card, LR:79-86) |
| Reconciliation, entity, decoy and evidence traps as the main lever | C007, C037, C041, C042 | Our tests-100 rows SC:80-93; LR:103 |
| Calibration by reflex and mutant solvers, T1 F/P≥0.90, five profiles | C025, C091 | Did not predict real runs (LS:65, schema reflex 0.194 vs tests 100); GOALS G11 |
| Highest weights on the last stages | C111 | TS-20 conflict |
| Byte-identical rerun or negative-space negatives; quota of 8-10 negatives | C051, C070 | TS-16/TS-19 honest-agent risk; LR:135 G4 (16 detectors fired 0 times) |
| Provenance yaml in TRUTH | C102 | DS-27 (sentinel v1, v4) |
| D1 paths, ABLATION_MAX, the <6000-char rule | C002, C003, C055, C096 | Wrong facts here |
| 10% per channel target, pass@8 | C010, C036 | Not our gate (tests < 100 AND final < 70 on 2 runs) |

## Cheapest trials for the biggest UNTESTED claims

| Trial | Claim | Method | Settles it if |
|---|---|---|---|
| T1 | Back-half evidence beyond about 32k tokens of context (C066, D2:1031-1043) | On one existing P-1 bundle (sentinel 07363dd), regenerate *only* the shipped and hidden inputs so the deciding rows sit after token 32k of each file. Rules, tests and judge stay unchanged. Run 3 fresh P13 blind solves | Blind loss grows by ≥10 points vs 78.63. No harness run is needed until then |
| T2 | Terminal obligation stated once, early (C101, trap 47) | Move the instruction's final-output sentence to the first paragraph of one parked bundle that scored tests 100 (metered). Run 1 Opus probe | Tests drop below 95 (the kill line). Costs one probe; expect "no change", which would close the claim |
| T3 | Per-unit vs aggregate weakness (C049, "64 tests, 100 rubric") and the 18→28 naming lift (C084) | On sentinel gate_run a9b1d42 / 80.69, read the failed checks from the existing `report.json` and classify each as per-unit or aggregate. No new run. Treat C084 as unsourced and drop it unless D2's author supplies the run files | Per-unit share of the lost weight is ≥70% |
