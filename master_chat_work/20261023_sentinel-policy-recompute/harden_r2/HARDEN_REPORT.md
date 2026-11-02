# Harden round 2: sentinel-policy-recompute (0074a64)

Phase A was GENUINE. The primary cause was 4 (the levers were weak by design), and the QC rounds' grading changes (cause 3) contributed. The full diagnosis is in DIAGNOSIS.md. Master rulings 1-9 were applied.

## Levers (rule location; all agent-visible files)
| lever | rule | alone loss (tests) | one fact wrong |
|---|---|---|---|
| N1 region override allowance (replaces L3) | quota_limits.cfg:7 (keyed by region; region from tenant_catalog.xml), values :9-23 | 23/44 52.3% | per-tenant counter 52.3%, one counter 45.5% |
| N2 timeout unit by version cutover (replaces L2; L1 stays as amplifier) | units_reference.txt:6-7; conventions line 5 gives `rev` a neutral meaning only | 15/44 34.1% | unit from rev 34.1% |
| N3 window admit count + draw_order (replaces L7 as a counted lever) | override_precedence.conf:5-6 (`admit=` attr on every window in effective_windows.xml) | 23/44 52.3% | admits drawn by the resolved tenant only 52.3%; each draw_order direction 34.1% |
| L7 per-term rounding (noise) / L1 green control (amplifier) | risk_weight_rounding.txt:2-3 / conventions controls sentence | 18.2% / 11.4% | info |

COUPLING: the hidden-a..d whole-document corpora engage N1+N2+N3 together. hidden-d plants both draw_order directions: OV-F003-d2 is refused by its region while its window still has admits, and OV-K042-d5 is refused by its window while its region still has allowance (ruling 3).

## Grading
- Tests: 15 checks, P=44, all weights in {5,3,1,-3,-5}. There are three row-owned `_hard` families at w5 (region_allowance, unit_cutover, window_admit; each corpus separates only its own lever) and the coupling policy/curve/trace tests at w5 each. The rest are cli init/set 3, mutation_risk 3, mutation_allowance 3, validate 3, rerun 1, and one merged shipped check at w1. Negatives are -5/-3/-3.
- Shares: hidden or mutated 90.9%, isolated `_hard` 34.1%, whole-document 34.1%, shipped-only 2.3%.
- Judge: 15 criteria, P=37. R11 now reads "The agent produces /app/out/profile_dev.json and /app/out/profile_prod.json by running its repaired sentinel-ctl." (rewritten positively for judge_qc J10). R12/R13/R14 are the N2/N1/N3 conduct criteria; solve.sh prints `check R12 ok`..`check R15 ok`. R6, R7, R10 and R15 are kept. JUDGE_MAP.md is updated.
- reward.toml weights: test_output 0.5/44, judge 0.5/37.

## Cost table (G10, WORK/COST_TABLE.md)
All-but-one overall at the measured judge (19/37 = 51.35):

| only this lever wrong | overall at judge 51.35 | at rubric 90 (info) |
|---|---|---|
| N1 | 49.5 | 68.9 |
| N1, one-counter reading | 53.0 | 72.3 |
| N2 | 58.6 | 78.0 |
| N3 | 49.5 | 68.9 |
| draw_order | 58.6 | 78.0 |

Every value is under 70: G10 PASS. The probe-1 reading (own tenant rows, region value, no admits) costs 70.5%.

## Gates
- Reflex gate: the probe-1 agent program, adapted only for the region-key lookup, scored 0.1591 (7/44). Build mode scored 0.1818 and the unadapted program 0.1364, so all three are ≤ 0.20: PASS.
- STACKING_CHECK.md: STACKING PASS.
- RULE_COVERAGE.md: 16 rules and 21 mutants; every mutant fails at least one test.
- xref_check: 50 entries, 0 findings.
- precheck: PRECHECK CLEAN. The kit scripts exit 0, apart from the binary-skip X1 note.
- Validator (advisory): 3 fails, all in the yaml provenance block (§15.5-15.7). The same block fails in SOURCE too, so these predate this round.
- No bytecode. No decoy/trap/pitfall/footgun names in agent-visible files. TRUTH sha lines were rewritten by script last.
- Docker, tests-only (TS 20261024T221700-adcf, ALL_DONE 22:20:38): oracle 1.0/1.0/1.0, owner-only 1.0, nop 0.0, stub 0.0. Forgery (shipped answers hardcoded into resolve) scored 0.0455: it keeps only the cli, validate and shipped checks, and the hardcoded negative fires.
- Tree sha: 02b044e82de0.

## Not run
- No real agent run and no live judge. The next step is one harness probe, then P11 QC.

## Lessons for the master
- In the probe-1 trajectory, a habit lever that is written in a sentence of the governed file was read in one pass. Keying the counter wider than the habit key (region, window across tenants) is what the agent's per-line-field program cannot express.
- judge_qc J10 rejects any "not" in a positive criterion, so state a conduct ruling as the positive behaviour only.
- Validator §15.3 needs the literal `## Pitfalls` heading in TRUTH.md; do not rename it.
