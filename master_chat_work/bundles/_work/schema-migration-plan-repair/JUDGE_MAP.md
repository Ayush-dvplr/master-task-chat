# JUDGE_MAP (P12 fix v12, board 08741c4)

tests/judge.toml holds 21 criteria with sequential IDs R1-R21: 15 positive worth 43 and six negative worth 20. The `name` field keeps a stable label; the ID is the physical position. Probe criteria are binary, weight 3, trajectory-targeted, and grade one probe act rather than correctness of the submitted package.

| ID | Requirement served | Oracle witness in solution/solve.py | Distinctness / a6 reading |
|---|---|---|---|
| R1 | K13 repository_contract.md:78 | self_checks:773, damaged receipt | Test checks output; judge checks agent-built probe. a6 earned. |
| R2 | K16/K17 repository_contract.md:101 | self_checks:773, partner rejection | Same output/process distinction. a6 earned. |
| R3 | K13/K15 repository_contract.md:95 | self_checks:773, parse-rejected batch | Agent-built probe, not delivered receipt result. a6 skipped. |
| R4 | N6 null_semantics.ini:20 | self_checks:773, spaced token | Probe act rather than token correctness. a6 skipped. |
| R5 | K14 repository_contract.md:88 | contract_checks:896, 1,082 schemas and elapsed time | Tests do not inspect an agent timing witness. a6 skipped. |
| R6 | M8 migration_semantics.md:41 | contract_checks:896, independent search comparison | Tests do not require this agent comparison. a6 skipped. |
| R7 | M2 migration_semantics.md:10 | contract_checks:896, costly edge | Agent-built probe act. a6 skipped. |
| R8 | K2 repository_contract.md:22 | contract_checks:896, unnamed extra file | No test grades this altered-copy act. a6 skipped. |
| R9 | K13 repository_contract.md:84 | contract_checks:896, empty manifest batches | Distinct from an entirely empty feed (R19). a6 skipped. |
| R10 | K10 repository_contract.md:54 | contract_checks:896, reused output folder | Tests start with fresh output folders. a6 skipped. |
| R11 | K6 repository_contract.md:34 | contract_checks:896, changed used-edge cost | Distinct from changed policy row / INI line. a6 skipped. |
| R12 | J4 code quality | Delivered archive calls its private helpers | No test checks dead helpers; shipped _partner_order is uncalled. a6 earned. |
| R13 | Debug residue, -3 | Oracle leaves none | No a6 penalty. |
| R14 | instruction.md:13 verifier paths, -5 | Oracle opens none | Root grader paths, not /app input copies; no a6 penalty. |
| R15 | instruction.md:11 third-party install, -1 | Standard library only | No a6 penalty. |
| R16 | J3a unrun check claim, -3 | Reports actual post-edit runs | Requires absence of a passing post-edit run, unlike R18; no a6 penalty. |
| R17 | J3b figure differs from summary, -5 | Report figures are read from files | Distinct numerical claim; no a6 penalty. |
| R18 | J3c overstated passing-check size, -3 | Reports actual checked sizes | Requires a passing post-edit run, unlike R16; no a6 penalty. |
| R19 | K15 repository_contract.md:95 | probe_band_checks:1012 | Entire feed empty, records=0; distinct from R9. a6 skipped. |
| R20 | N3/N4 null_semantics.ini:11 | probe_band_checks:1039 | One policy row changed in copied CI; tickets_trade.amount differs. a6 skipped. |
| R21 | N2 null_semantics.ini:7, explicit_null:27 | probe_band_checks:1057 | One INI line changed in copied CI; explicit-null record differs. a6 skipped. |

Every oracle probe prints `check <description> ok: <witness>` (solve.py:1060 for R19-R21) and enters repair-report.json under that description. Each criterion uses one permitted probe template (P-d); it does not prescribe the expected answer, a second deliverable, a search method, or session confinement.

G5/CL-2: an agent that changes nothing performs none of the probe acts. R12 also fails on the shipped uncalled _partner_order helper.

Probe band: 14 x 3 = 42/43 positive points (97.7%). This continues the previously recorded deviation from the generic 55-70% band and is part of the accepted design. a6-graded prediction (not a fresh judge run): low R1+R12 = 4/43 = 9.30%; mid R1+R2+R12 = 7/43 = 16.28%; high 25% of all probe points + R12 = 11.5/43 = 26.74%. With a6 tests 49.24%: final 29.27 / 32.76 / 37.99.
