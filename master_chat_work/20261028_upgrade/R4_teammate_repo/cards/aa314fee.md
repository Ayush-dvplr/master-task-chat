# aa314fee (Anjali Kumari, Optimization) final 17.64 = tests 3.03 / judge 32.26
Verdict: GENUINE. Which downstream rule broke is UNVERIFIED: the verifier stdout holds only the reward.

## What the agent did
- 62 steps, 28.1 of 180 min. derive_report.py created step 30 (12.7 min), 3 runs (first step 33, last 60).
- It settled the two withheld rules correctly from governance_observations.log: order_book governs before cutover, contradicted 0 times vs 2240 for the registry reading (final message).
- Two runs gave byte-identical files and identity checks were zero, so it declared success.

## Where it lost
- Tests (W=66): only 2 w1 checks pass (artifacts parse, runs clean). These fail: the backbone, cumulative shortfall spine, site-cycle fill, unseen alpha/beta, identity triangle, substitution, and row-order permutation (w5 each), plus 8 w3 checks.
- Judge (P=62): all 8 counterfactual figures off by small amounts (#1 2628042 vs 2628151; #3 3169 vs 2823 lots), w5 each, 40 points. #17 source naming and #18 module structure.

## Levers that held
- L3/P-2 carried-state cascade. The carried shortfall "never heals": one wrong decision at cycle 5 still shows at C24 (TRUTH.md:8). Small rule slips become whole-ledger mismatches.
- Interlocking allocation (new name L12 shared fill level). Every grant in a cell depends on every claim in that cell (TRUTH.md:7), so per-row errors spread.
- S5 withdrawn-practice decoy. legacy_runbook.md proportional sharing is withdrawn but habitual (TRUTH.md:7).
- L11 bounded. The two withheld rules are settled by a log against named candidate readings (TRUTH.md:9).
- Drift and trap: duplicate `quantity` column (the first governs), errata single conversion, admission by recorded instant, epochs of reused ids (TRUTH.md:11-16).

## Fair yet hard
42 files from 13 systems. Every rule except the two withheld ones is written down. The withheld two are decidable from the log.

## Style
Exact whole-document tests on the shipped corpus and two unseen extracts; a row-order permutation check (P-4 robustness). The judge is 8 x w5 counterfactual figures (J11) plus honesty negatives (withdrawn practice presented as governing, figures not from a run).
