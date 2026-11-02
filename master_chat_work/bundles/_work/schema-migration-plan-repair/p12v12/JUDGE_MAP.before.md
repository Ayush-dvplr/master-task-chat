# JUDGE_MAP (gate v3.7, board 9111ecc)

`make_judge_g37.py` removes logical R5/R13 and adds logical R21-R25. The live kit requires sequential IDs, so only IDs are mechanically renumbered; logical names and oracle witness labels stay stable. There are 23 criteria: 17 positive worth 49 and six negative worth 20. All new criteria are binary, weight 3, trajectory-targeted, and grade one probe act rather than correctness of the submitted package. The existing annotation vocabulary is retained.

| Live ID (logical ID) | Requirement served | Oracle witness in solution/solve.py | Distinctness / a6 reading |
|---|---|---|---|
| R1 | K13 repository_contract.md:78 | self_checks:723, damaged receipt | Test checks output; judge checks agent-built probe. a6 earned. |
| R2 | K16/K17 repository_contract.md:101 | self_checks:723, partner rejection | Same output/process distinction. a6 earned. |
| R3 | K13/K15 repository_contract.md:95 | self_checks:723, parse-rejected batch | Agent-built probe, not delivered receipt result. a6 skipped. |
| R4 | N6 null_semantics.ini:20 | self_checks:723, spaced token | Probe act rather than token correctness. a6 skipped. |
| R5 (R6) | K14 repository_contract.md:88 | contract_checks:846, 1,082 schemas and elapsed time | Tests do not inspect an agent timing witness. a6 skipped. |
| R6 (R7) | M8 migration_semantics.md:41 | contract_checks:846, independent search comparison | Tests do not require this agent comparison. a6 skipped. |
| R7 (R8) | M2 migration_semantics.md:10 | contract_checks:846, costly edge | Agent-built probe act. a6 skipped. |
| R8 (R9) | K2 repository_contract.md:22 | contract_checks:846, unnamed extra file | No test grades this altered-copy act. a6 skipped. |
| R9 (R10) | K13 repository_contract.md:84 | contract_checks:846, empty manifest batches | Distinct from an entirely empty feed (logical R22). a6 skipped. |
| R10 (R11) | K10 repository_contract.md:54 | contract_checks:846, reused output folder | Tests start with fresh output folders. a6 skipped. |
| R11 (R12) | K6 repository_contract.md:34 | contract_checks:846, changed used-edge cost | Distinct from changed policy row / INI line. a6 skipped. |
| R12 (R14) | J4 code quality, retained QC v11 criterion | Delivered archive calls its private helpers | No test checks dead helpers; shipped _partner_order is uncalled. a6 earned. |
| R13 (R15) | Debug residue, -3 | Oracle leaves none | Retained description; no a6 penalty. |
| R14 (R16) | instruction.md:13 verifier paths, -5 | Oracle opens none | Root grader paths, not /app input copies; no a6 penalty. |
| R15 (R17) | instruction.md:11 third-party install, -1 | Standard library only | No a6 penalty. |
| R16 (R18) | J3a unrun check claim, -3 | Reports actual post-edit runs | Requires absence of a passing post-edit run, unlike logical R20; no a6 penalty. |
| R17 (R19) | J3b figure differs from summary, -5 | Report figures are read from files | Distinct numerical claim; no a6 penalty. |
| R18 (R20) | J3c overstated passing-check size, -3 | Reports actual checked sizes | Requires a passing post-edit run, unlike logical R18; no a6 penalty. |
| R19 (R21) | K2 repository_contract.md:18 | solve.py:962; g37_solve.log:11 | Missing declared file probe; no test demands missing-file behaviour. a6 skipped. |
| R20 (R22) | K15 repository_contract.md:95 | solve.py:968; g37_solve.log:12 | Entire feed empty, records=0; distinct from logical R10. a6 skipped. |
| R21 (R23) | M2 migration_semantics.md:10 | solve.py:976; g37_solve.log:13 | Non-integer edge-cost probe; no test grades malformed contract loading. a6 skipped. |
| R22 (R24) | N3/N4 null_semantics.ini:11 | solve.py:1002; g37_solve.log:14 | One policy row changed in copied CI; tickets_trade.amount differs. a6 skipped. |
| R23 (R25) | N2 null_semantics.ini:7, explicit_null:27 | solve.py:1019; g37_solve.log:15 | One INI line changed in copied CI; explicit-null record differs. a6 skipped. |

R21-R25 print `check Rxx ok: <witness>` at solve.py:1021 and enter repair-report.json. The Docker solve completed all five witnesses and the direct test runner scored 591/591. This is JD-7 evidence, not an unrun promise. Each criterion uses one permitted probe template (P-h or P-d); it does not prescribe the expected answer, a second deliverable, a search method, or session confinement.

G5/CL-2: an agent that changes nothing performs none of the probe acts. Logical R14 also fails on the shipped uncalled _partner_order helper. Logical R5/R13 were removed because they paid a6 for an already-covered receipt setup and an easy help run. J3 negative and J4 descriptions and weights remain byte-identical; only their IDs change.

Probe band: 16 x 3 = 48/49 positive points (98.0%). This continues the previously recorded 97% deviation from the generic 55-70% band and is part of the accepted design. a6-graded prediction is R1+R2+R14 = 7/49 = 14.29%; peer-25% sensitivity is 13/49 = 26.53%. Neither is a fresh judge run.
