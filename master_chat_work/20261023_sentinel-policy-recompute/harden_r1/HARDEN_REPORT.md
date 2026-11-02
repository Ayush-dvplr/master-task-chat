# Harden report: sentinel-policy-recompute, P9 v2 r1 (board 55d3b87)

Status: DONE. Bundle tree sha (first 12) 505104cc7e41 before, 28fad6d2c8b8 after.

## Baseline
claude-opus-5 scored 0.7778 combined: tests 22/22 (tests-only 1.000) and judge 15/27. No test failed and there was no permission artefact. Phase A GENUINE. Primary cause 4: every trap was written out as one sentence in instruction.md line 5 and repeated as key=value rules in the data. Conversion and QC fixes (cause 3) made the tier and iteration rules more explicit.

## Levers: before and after
| Lever | Before | After (rule location) | Reference playing only this wrong reading (tests-only) |
|---|---|---|---|
| Carried traps (B9, client version, half-open, ms, multiply-then-cap, tier, convergence) | LEAKED (listed in instruction:5 and reconciliation_rules.conf) | each stated once in the file that governs it; instruction list and trap keys removed | inclusive window 0.1290 |
| L3 stateful allowance | none | override_deltas.json conventions (allowance sentence) + quota_limits.cfg `[override_allowance]` | first-only 0.3548; no allowance 0.2581; per-principal allowance 0.2581 |
| L2 rev unit (make-it-match) | none | override_deltas.json conventions (`rev 1 row stores it in whole seconds`) + ranges | raw timeout 0.5161; heuristic below 100 ms 0.5161 |
| L7 per-term rounding | none | risk_weight_rounding.txt (worked example removed) | rounding the sum once 0.7419 |
| L1 honest green control | none | `controls` block, described as a parse and count control | trusting the stored control 0.8387 |

## Counts and shares
- Tests: 12 checks, P = 31, negatives -11 (hardcoded -5, forged transcript -3, URL or secret in artifacts -3). Weights come from the kit set {5,3,1,-3,-5}.
- Whole-doc on hidden reseeded corpora 64.5%, isolated plus mutation 29.0%, shipped-only 3.2%. There are 2 mutation tests.
- Judge: 15 criteria, P = 37, `mode = "batched"`. It includes one J2 conduct criterion per lever (R12 to R15), the J3 honesty negative (R9) and the J4 named-shape criterion (R10).
- reward.toml: test_output 0.5/31, judge 0.5/37.

## Gates
- STACKING PASS (OUT/STACKING_CHECK.md). The tool's AL-28 regex lumps distinct acts together; the manual grouping keeps every act at or below 5.
- Reflex gate: the agent program as shipped scores 0.0968 (it crashes on the new data). With the minimal make-it-match adaptation it scores 0.1613 (5/31). Both are at or below 0.20: PASS.
- xref_check: 16 entries, 0 findings.
- QC scripts: structure 0 fail (1 advisory warn), instruction PASS, tests PASS (K8, H6), judge PASS (G2).
- Validator (advisory): 3 fails remain. All 3 are the yaml provenance block (§15.5-15.7), which already fails in SOURCE.
- QL list: OUT/QL_CHECKS.md, every change PASS or FIXED.
- Docker, tests-only (harbor 0.24.0, TS 20261023T174334-428e, ALL_DONE 17:48:21):

  | Run | Result |
  |---|---|
  | oracle x3 | 1.0 / 1.0 / 1.0 |
  | owner-only | 1.0 |
  | oracle with programs chmod 600 | 1.0 |
  | nop | 0.0 |
  | stub | 0.0 |
  | forgery (shipped answers hardcoded into resolve) | 0.0; hidden documents and mutations fail, hardcoded negative fires |

## Not run
- No real agent run on the new bundle.
- The judge channel was not run live; Docker copies were tests-only.
- Playground was not run (removed in a72c20a4).

## Lessons for the master
- The 0.7778 baseline was tests 1.000 plus judge 15/27, not tests-only; check reward-details before reading a score.
- The kit locks weights to {5,3,1,-3,-5}, so the shares have to be planned with those weights from the start.
- Keeping shipped values unchanged (285/3/2250/51) while hidden corpora separate the readings stops shipped-only reflexes cold.
- Removing a reconcile key the solver's own code checks makes the reflex program crash, so also score a minimally adapted copy for an honest gate.
