# Final_Delivery synthesis (6 delivered peer tasks, read 24 Oct 2026, master 13:10 IST)

Goal (Ayush 12:50): "pass the QC with genuine and minimum minors or warn, and have good score in trajectory"; no cap on tests or criteria.

## Scores (combined = mean of tests and rubric; all regrades match, oracle 100, nop 0)
| task | tests | rubric | combined | kit f/m/w | main loss |
|---|---|---|---|---|---|
| collateral-gated-settlement-ladder | 30.38 | 90.16 | 60.27 | 0/0/0 | one type-coercion slip amplified (37 pts) |
| survey-raking-disclosure-audit | 41.41 | 41.03 | 41.22 | 0/0/0 | one ambiguous "it" amplified (75 test pts) |
| pa-household-ledger-reconciliation-forge | 44.44 | 98.86 | 71.65 | 0/0/1 | denominator + Decimal ties, 12 tests on one bug |
| slo-credit-closeout | 2.38 | 66.67 | 34.52 | 0/0/1 | 5 slips on ~5,600 of 21,021 records cost 205/210 |
| sentinel-fraud-training-release | 2.68 | 36.84 | 19.76 | 0/0/0 | digests + oracle defect + conduct |
| wafer-start-capacity-apportionment | 3.03 | 32.26 | 17.64 | 14 warns | amplification + key/spec contradiction |

## What the six say
1. Amplification is how delivered tasks score low. One stated-rule slip fails every whole-document or whole-population check downstream. QC passed this shape with 0 fails in all six (kit 0/0/0 on three). Our G1-G3 (isolated checks, no whole-set asserts, shipped-only <= 5%) paid partial credit and made our tasks easier than the delivered ones. Adopt amplification; require that every amplified slip traces to a stated single-reading rule (GENUINE), never to ambiguity, a hidden rule or an oracle defect.
2. The losses we must not copy are the ones that would fail our QC or the PL: answer key contradicting the contract (wafer 32.58 pts), oracle defects (sentinel union-find, 1,697 accounts), unstated tie-breaks, null conditions and flag semantics (slo, sentinel), bare "it" (survey 97 raw pts), agent-visible trap lists (pa), cascade early-return gates (wafer), slug text inside SHA-pinned test text (slo oracle 93.8% on the masked copy).
3. Judge: final-reply criteria are fine (dispatch QC v6 accepted R1-R5 that read the reply). Losers: conduct the oracle cannot show (collateral R15, wafer), exact counterfactual figures (wafer). Winners: per-item enumeration of the final answer (pa lost 2/2), trajectory-grounded honesty negative (slo R6, sentinel R9), code quality on the delivered program (slo R9; emberforge v8 failed JD-18 without one).
4. Hidden tier patterns that worked: embedded seeded generator + next-period run with `--prior` = agent outputs as a foreign uid (slo, sentinel); relocate + shuffle + scale-one-curve rerun (collateral 1.0375); variant reruns (row rotation, renamed dir, missing source, non-root, `python -I`, temp cwd) (wafer).
5. Lever patterns to add: strict type rule with easy-reject decoys (collateral L5); exact-decimal half-even recurrence with >= 3 planted ties (pa); multiplicative factor with a stated denominator (pa); one general normalisation rule exercised in a rarely joined event-log field (slo D).
6. Instruction sentences that worked: whole-file exactness stated up front (collateral instruction.md:38-42); an unseen-extract tier at other scales (wafer); "there is no count to check yourself against" (wafer); one arbiter sentence naming which document wins (sentinel); full output schema stated (slo).

## Rejected edits
- slo `LEVER_RULES_v1.md:43` "35/35 and zero warns": contradicts Ayush 12:50 (no cap; genuine minimum warns).
- pa `P2:82` "pair whole-document tests with an isolated absolute total so one factor cannot zero > 50%": anti-amplification, contradicts finding 1.
- survey/sentinel "avoid grouped whole-set asserts": same reason. Kept only the guard: no early-return cascade gates and every assert shows its first differing path.

## Applied (24 Oct 13:15, CHANGELOG line)
LEVER_RULES_v1 (L5 decoys, L8-L10, never-used list, W8-W9, section 3 rewritten G1-G9, section 4 J1-J7, section 7 delivered line), P2_build_v3 (design test plan, Phase 3 check_exact, Phase 4 grading, Phase 5 judge, Phase 6 instruction sentences), _COMMON_RULES_v3 (Never 6 extended, Never 11 key/contract, Always 12 cap text removed, Always 15 no bytecode in bundles, J1 line, gate arithmetic), QC_FIX_PLAYBOOK_v2 (AL-2 row: counterfactual figure -> graded rerun; AL-18 recipe), KNOWLEDGE (flow note, wafer calibration, gate sync), precheck.sh (trap-file words).
