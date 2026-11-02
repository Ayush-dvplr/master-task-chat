# KILL_TEST (Phase 0, prototype)

Engine: `WORK/kill/core.py` (prototype reference, one module, wrong readings as `KILL_VARIANT` flags).
Generator: `WORK/kill/gen.py` (shipped seed 731905, 400 accounts, 12 statement months, every account anchor 1 / actual; hidden seeds 101 and 202, 10 tiers x 2 extracts each, 8-9 accounts per extract, anchors 2-28, random basis).
Runner: `WORK/kill/run_kill.py`, Docker only: `docker run --rm --memory 4g --cpus 2 python:3.12-slim` under `perl -e 'alarm 1500'`, after `dockfree.py` START=yes.
Log: `_runs/20261031/backdated-entitlement-replay/proto-20261031T1257/logs/kill5.log` (ALL_DONE).

Scoring (planned test layout without mutation and existence checks): per hidden tier and family (ledger = 4 region files, rollup = 2 segment files + summary, control = policy_audit + data_quality) one w5 check that needs every extract of that tier exact, both seeds; shipped one w3 check per family. Lever points = the hidden tiers.

Optimisation solver rows: N/A (replay task, no optimisation; the only search is the 56-candidate fit per account, which the reference does exhaustively).

| solver | instance | seconds (max per extract) | result | tests kept % | lever points kept % | shipped inputs fast |
|---|---|---|---|---|---|---|
| R0 reference: exact full search over 56 candidates, unique fit | ship + hid1 + hid2 | 1.33 | EXACT | 100.0 | 100.0 | yes (0.6 s) |
| R0s split-by-parent exact (groups solved independently, same engine) | same | 1.00 | EXACT | 100.0 | 100.0 | yes |
| R1 forward-only adjuster (one delta on the invoice holding the effective date, shipped anchor, posted cap, arrival order) | same | 0.36 | WRONG | 1.0 | 0.0 | yes |
| R2 latest-arrival-wins replay, first fit | same | 0.44 | WRONG | 2.9 | 0.0 | yes |
| R3 careful replay, shipped anchor 1/actual carried to every account | same | 0.72 | WRONG | 2.9 | 0.0 | yes |
| R4a careful wide replay, fit over the full stated domain, first fitting candidate (H8) | same | 0.40 | WRONG | 2.9 | 0.0 | yes |
| R4b careful wide replay, fewest-mismatch fit | same | 2.50 | WRONG | 2.9 | 0.0 | yes |
| R4c careful wide replay, unique fit, void invoices used as evidence | same | 0.77 | WRONG | 2.9 | 0.0 | yes |
| R5 first-write reflex program (first fit, all invoices as evidence, inclusive expiry, invoices before transfers, posted cap) | same | 0.43 | WRONG | 2.9 | 0.0 | yes |
| R5b first-write, paid-only evidence kept | same | 0.44 | WRONG | 2.9 | 0.0 | yes |
| R6 careful unique fit, two pair slips (inclusive expiry, invoices before transfers) | same | 0.76 | WRONG | 79.0 | 78.3 | yes |
| R7 careful unique fit, every invoice used as evidence | same | 0.99 | WRONG | 2.9 | 0.0 | yes |
| R8 careful unique fit, four pair slips (expiry, same day, cap, half-up) | same | 0.82 | WRONG | 64.4 | 63.3 | yes |
| A1 all but cycle-start inclusion | same | 0.94 | WRONG | 93.5 | 93.3 | yes |
| A2 all but exclusive expiry | same | 0.86 | WRONG | 85.4 | 85.0 | yes |
| A3 all but transfers before invoices on one day | same | 0.94 | WRONG | 93.5 | 93.3 | yes |
| A4 all but replayed transfer cap | same | 0.94 | WRONG | 93.5 | 93.3 | yes |
| A5 all but effective-date order | same | 1.04 | WRONG | 93.5 | 93.3 | yes |
| A6 all but half-even per line | same | 1.43 | WRONG | 91.9 | 91.7 | yes |
| A7 all but the live legacy key | same | 1.39 | WRONG | 93.5 | 93.3 | yes |
| blind 1861cfe (P13 design blind, first write ~3 min, program sha256 6e24c9d7cf98) | design_blind sample + bhid101 + bhid202 (40 extracts) | 0.42 | EXACT (41/41 extracts) | 100.0 | 100.0 | yes (1.11 s) |

Every loss is WRONG output (valid documents, wrong values); 0 crashes, 0 timeouts. Reference max 1.33 s against a stated 60 s per run (1/45 of the limit).

## History of the kill table (what changed the numbers)
- Run 1 (kill.log, 11 tiers, void evidence planted on one tier only): R4a first fit 73.5 tests, R5 first write 42.5.
- Run 2 (kill2.log): every void invoice rated at the superseded legacy default (ambient, every hidden extract carries one void that disagrees with the account's true fit; shipped voids agree because shipped truth is 1/actual). R4c withvoid 91.2 -> 2.9.
- Run 3 (kill3.log): R4a 70.9 (lost only PB1, PB1b, PB2 tiers); single pair slips A1-A7 85.4-93.5.
- Run 4/5 (kill4.log, kill5.log): ambient quiet account (no entitlement change in the window, so all 56 candidates fit: anchor_ambiguous) in the second extract of every non-PB tier. R4a/R4b 70.9 -> 2.9.

## Row 4 verdict (G-4 NO CORE rule)
Row 4 as the IDEA names it ("careful wide replay that fits anchor/basis over the full stated domain") is R4a/R4b/R4c/R7: each keeps 0% of lever points (WRONG). A row 4 that also checks that exactly one candidate fits, reads only paid invoices, and reads every pair sentence right is the reference itself (EXACT); with two typical pair slips (R6) it keeps 78.3% (loses 21.7%, above the 15% bar); with four (R8) 63.3%. Not NO CORE, but the honest statement is: a solver that transliterates every sentence, including the uniqueness sentence, is exact. The lever is H8 (first fit), H9 (shipped-only self-test: shipped has no ambiguous, no void disagreement, no pair) and the pair family.

## Strict-IDEA variant (IDEA line 15: every account fits uniquely, no ambiguous or unresolved accounts)
Run 3 without PB tiers and without quiet accounts: R4a/R4b would be EXACT on the fit (the first fit is the unique fit), so row 4 keeps 100% of the fit lever and only the pair family remains (A-rows 85-93). That is NO CORE for the fit lever, which is why this design deviates from IDEA line 15 (decision for Ayush).

## Design blind 1861cfe (31 Oct 14:58 IST, score-1861cfe/logs/score.log ALL_DONE)
The blind program is exact on the shipped sample and on all 40 hidden extracts of seeds 101 and 202: 0 WRONG, 0 TIMEOUT, 0 CRASH. It keeps 100% of lever points. Verdict: NO CORE (the bar was a loss of >= 40% of lever points by WRONG).
