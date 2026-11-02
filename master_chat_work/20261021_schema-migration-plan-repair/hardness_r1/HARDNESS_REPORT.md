# Hardness report r1: schema-migration-plan-repair (21 Oct 2026, 17:30 to 18:45 IST)

Verdict: **REBUILD**. Scores are tests-only, method (b), positive total P = 142.

## Method
- Method (b): each solver runs locally (Python 3.12.15, `APP_ROOT` set to its own app folder holding a copy of `environment/data`). Then the REAL `tests/test_output.py` runs under `uvx --from harbor-rewardkit==0.2.1 rewardkit` against a tests copy made by the QL procedure: `judge.toml` deleted, `reward.toml` = `weights = { test_output = 0.007042253521126761 }` (1/142). Harness: `raw/scripts/harness.py`.
- Proof: oracle 1.0000 (142/142), nop 0.0000. Same route for every solver below.
- Solvers: `_work/schema-migration-plan-repair/wrong/auditor_r1/make_solvers.py` writes each one as a small edit of `solution/solve.py`. One-line descriptions are in `wrong/README.md`. I wrote them from the contract files and did not read the builder's `wrong/` until mine were scored.
- Limits: macOS arm64 with other sessions running (load average 160 to 230), not Docker with 2 CPUs. No Harbor run.
- Bundle sha256 tree, before and after: `96d020574a902f05a8ef85d8ae57447d40b3e99c51326d95fa4d8bc8a3f1811a` (24 files). Unchanged.

## Solver table
| id | solver | score | earned | lost or paid (weights) |
|---|---|---|---|---|
| S0 | nop | 0.0000 | 0 | nothing paid |
| S1 | QC stub (empty files, `{}`) | 0.0070 | 1 | paid: artifacts_exist 1 |
| S1b | shipped repo.zip plus K19-shaped empty JSONs | **0.1197** | 17 | paid: artifacts_exist 1, archive_members_safe_src_layout 1, api_entry_points_importable 1, plan_tie_first_edge_decides 5, exec_correction_first_arrival_only 3, exec_correction_at_source_enables_step1 3, pipe_rejection_codes 3 |
| S2 | lazy: fixes only what the visible tests show (CLI paths, `__main__.py`), every lever at its shipped reading, honest reports | **0.1620** | 23 | S1b's 17 minus nothing, plus visible_repo_tests 3, module_parser_claims 1, test_fixes 1, repair_report 1 |
| S2_shipped | builder's S2: shipped repo, honest reports | 0.1338 | 19 | same as the builder's 0.134 (identical check set) |
| S3.LV-MR-1 | prerequisites checked on the received state | 0.7746 | 110 | -32 (22.5%): P1 5, P2 3, P3 5, P4 5, P8 3, ladder_small 3, medium 3, large_state 5 |
| S3.LV-MR-2 | product-graph Dijkstra, equal cost keeps the smaller last edge | 0.8873 | 126 | -16: P6 5, P7 3, ladder_small 3, large_tie 5 |
| S3.D | exhaustive state-aware enumeration (exact otherwise) | 0.8662 | 123 | -19: medium 3, large_state 5, large_tie 5, large_null 5, summary_json 1 |
| S3.LV-MR-4 | ini-only presence and fill, merged token lists | 0.9366 | 133 | -9: X1 3, X5 3, Q11 3 |
| S3.LV-MR-5 | fingerprint after migration, raw partner key, file order | 0.8944 | 127 | -15: Q3, Q4, Q5, Q6, Q7 (3 each) |
| S3.LV-MR-6 | FieldView drops nulls; signature and operations fixed at their call sites | 0.8944 | 127 | -15: P4 5, large_null 5, X4 5 |
| S3.LV-MR-7 | corrections up front, no re-check, planned = migrated | 0.8169 | 116 | -26: X3 5, X4 5, X5 3, Q8 5, Q9 5, Q10 3 |
| S3.F | one merge hop, no loop check, abort on bad line | 0.8521 | 121 | -21: I1 3, I2 3, Q2 3, Q3 3, Q8 5, cli 3, summary_json 1 |
| S3.REPORT | category = status, partners by id | 0.9577 | 136 | -6: summary_categories 3, summary_partner_order 3 |
| S3.C | shipped CLI, no `__main__.py` | 0.9577 | 136 | -6: cli 3, visible_repo_tests 3 |
| S4 | careful (definition below) | **0.6268** | 89 | -53: P3 5, P4 5, P6 5, P7 3, ladder_small 3, medium 3, large_state 5, large_tie 5, large_null 5, X1 3, X4 5, X6 3, Q4 3 |
| S4b | right on every single-lever case, wrong only where two rules meet | **0.7746** | 110 | -32: P4 5, medium 3, large_state 5, large_tie 5, large_null 5, X4 5, Q4 3, summary_json 1 |
| SC1 | best shortcut (S2 plus docstring-only edits) | **0.1761** | 25 | S2 plus module_core_claims 1, module_report_claims 1 |
| S5 | oracle | 1.0000 | 142 | nothing lost |

No negative check fired for any solver. S1 = max(S1, S1b) = 0.1197.

S4 is written as a careful agent would code it in one sitting:
- Planner: Dijkstra on schema ids that carries the best path's state, with parent pointers and the smaller last edge kept on equal cost. This is the reflex on LV-MR-1 and LV-MR-2, and it is fast, so D holds in isolation.
- Nulls: `FieldView` is left alone, and nulls are fixed in `state_signature`, `_rename` and `_add` (C call-site reflex).
- Presence and fill come from the ini only, while token lists are fixed (LV-MR-4).
- The fingerprint is taken after token replacement (LV-MR-5).
- Corrections are applied at the top of every step for the current schema, so they repeat on revisits and never apply at the final schema (LV-MR-7).
- Everything else is right.

S4b uses state-aware enumeration, the call-site null fix and the fingerprint after tokens. Both are measured, not estimated.

### Independent check of the builder's numbers
| item | builder | auditor | note |
|---|---|---|---|
| S2_shipped | 0.1338 | 0.1338 | identical lost set |
| LV-MR-1 loss | 32 (22.5%) | 32 (22.5%) | confirmed (note 3) |
| LV-MR-2, D | 16, 19 | 16, 19 | identical |
| LV-MR-4 | 6 (W4b) / 3 (W4c) | 9 combined | additive; LEVERS counts 12, but Q4 (3) is lost only by LV-MR-5 readings |
| LV-MR-5 | W5m 12, W5b 3, W5c 6 | 15 combined | builder's W5c also lost Q11 because it keyed tokens by the raw value |
| LV-MR-6 | W6 18 (signature left wrong) | 15 (signature fixed at its call site) | S1 is lost only when the signature itself is left wrong |
| LV-MR-7 | max single W7b 23 | 26 (shipped executor and classify) | X6 is lost only by the every-arrival reading |
| F | WF1 14 + WF2 7 | 21 | identical; LEVERS counts 26, but P8 (3) is lost only by LV-MR-1 and Q1 (3) by no solver |
| REPORT | 6 | 6 | LEVERS counts 11; Q9 (5) is lost only by LV-MR-7 |
| C | 7 | 6 | my solver's own summary came from `cli.main` with absolute paths, so summary_json still matched |

## Underivability (right reading vs reflex reading, visible shipped data only)
Each delivered repo ran `run_pipeline` on `/app/data` (8,000 feed lines), and its records and summary were diffed with the oracle's (oracle visible run 3.3 s).

| lever | records differing (of 8,000) | other visible signal | verdict |
|---|---|---|---|
| LV-MR-1 | 671 (542 status) | 264 records fail with E_PREREQ_FAILED although no correction belongs to them (oracle: 0), which contradicts M7 | DERIVABLE |
| LV-MR-2 | 45 (45 plans) | visible domains are about 10 schemas, so brute force confirms the tie | DERIVABLE |
| D | not comparable | enumeration's visible run did not finish in 1,800 s (oracle 3.3 s) | DERIVABLE (run time) |
| LV-MR-4 | 355 | summary differs | DERIVABLE |
| LV-MR-5 | 5,757 (5,617 fingerprints) | 584 status | DERIVABLE |
| LV-MR-6 | 771 | 436 status | DERIVABLE |
| LV-MR-7 | 956 (955 payloads) | 20 status | DERIVABLE |
| F | visible run aborts (15 malformed lines in the shipped feed) | crash | DERIVABLE |
| REPORT | 0 records, summary differs (by_category, partners) | the shipped repo already has `category_of` and `_partner_order` | DERIVABLE |
| C | 0 records | 2 of 9 visible repo tests fail | DERIVABLE (visible tests) |

The shipped data carries no expected outputs. So "differs" means the visible inputs exercise every separating pattern, and an agent can confirm each rule by self-checks: execution consistency for LV-MR-1, brute force on small visible domains for LV-MR-2, its own run time for D, and the crash for F. No lever is HIDDEN-ONLY.

## D lever timing (note 2)
- Enumeration (S3.D planner), 16x4 hidden ladder (`ladder_medium_state`): **1,855 s**, correct plan. That is 185x the 10 s limit, against the builder's estimate of about 1,950 s.
- The same planner at a 10 s limit on `ladder_large_state`, `ladder_large_tie` and `ladder_large_null` (45x3): all three timed out. `ladder_small`: 1.7 s, correct.
- Oracle, 3 runs each, slowest: large_state 1.009 s, large_tie 1.377 s, large_null 0.894 s, medium 0.862 s.
  - By the design's own formula, N = max(10, ceil(10 x 1.009)) = 11. The contract states 10.
  - That was measured on a loaded Mac, not 2 CPUs. One earlier oracle medium run took 9.7 s at load average about 220. The check allows 20 s, so the oracle's margin over the worst spike seen here is about 2x.

## Shortcut hunt (30 minutes, scratch copy of instruction.md and environment/ only)
1. Hardcoding the visible outputs: `summary.json` is only compared with the delivered package's own run (weight 1). Every value check builds its inputs from EVAL_SEED inside the tests, so hardcoding earns nothing beyond what an honest run earns.
2. Keying on file names or row counts: there are no hidden answers to key on, and `negative_filename_dependent_behaviour` covers renames.
3. Skipping a stage:
   - Fixing only what the visible tests show (S2) scores 0.1620.
   - Adding a docstring to one core and one report function also pays `module_core_claims` and `module_report_claims`. `_module_claims` compares `ast.dump`, and a docstring changes it. This is SC1, the best shortcut, at **0.1761**.
4. Image and verifier leaks:
   - `environment/Dockerfile` copies only `data/`.
   - The data holds no expected or seed values (grep for expected, want, answer, golden, the seeds: no hits), and repo.zip has no comments.
   - The tests run in a separate verifier image with `/tests` at mode go-rwx, and the child runs as nobody.
   - This was not checked inside a built image.
5. A self-consistent round-trip program does not apply here: there is no decode stage. The consistency checks (summary_json, test_fixes) pay any honest solver.

Best shortcut: 0.1761 (above 0.10).

## Extra measures
- Independence:
  - LV-MR-5 + LV-MR-7 lost 41 = 15 + 26, additive.
  - LV-MR-1 + LV-MR-6 lost 42 against 32 + 15 = 47. The pair overlaps by 5 on P4, the shared composition check, as designed.
- Composition share (measured): a check counts when 2 or more single-lever S3 solvers fail it. 12 checks qualify, weight 46 of 142 = **32.4%**. Single-lever checks hold 73 (51.4%). Checks failed by no S3 solver hold 23 (16.2%).
  - The composition checks are: cli (F, C), summary_json (D, F), P4 (1, 6), ladder_small (1, 2), medium (1, D), large_state (1, D), large_tie (2, D), large_null (D, 6), X4 (6, 7), X5 (4, 7), Q3 (5, F), Q8 (7, F).
  - DESIGN counted 56 (39%). Q4, Q6, Q9 and P8 measure as single-lever.
- Downstream isolation: confirmed.
  - S3.F (identity and feed wrong at stage 2 and 3) keeps every planner, executor and summary check.
  - S3.LV-MR-5 (stage 4) keeps every planner and executor check.
  - S3.LV-MR-1 (planner) keeps every executor, pipeline and summary check.

## Verdict: REBUILD
| condition | result | pass |
|---|---|---|
| S4 in 0.10..0.20 | 0.6268 | no |
| S2 at most 0.10 | 0.1620 (shipped 0.1338) | no |
| S1 at most 0.25 | 0.1197 | yes |
| every S3.k loses points | 6 to 32 each | yes |
| every counted lever HIDDEN-ONLY | 0 of 10 | no |
| best shortcut at most 0.10 | 0.1761 | no |
| S4b at most 0.30 (note 5) | 0.7746 | no: compositions too weak |

Causes:
- **S4 high.** Each lever's checks are isolated on supplied inputs (change 3), and no lever holds more than 22.5%. So a solver that falls for every NEW-lever reflex still keeps about 63%.
  - The checks S4 earns: STRUCT, visible tests and honesty 15; F 21; REPORT 6; C 6; B (X2) 3; the rest of the NEW-lever single checks.
  - For S4 to reach 0.20, about 80% of the weight must sit in checks that S4's misses break. Adding checks cannot get there: it would need over 300 new points.
- **S4b high.** It fails 7 of the 12 composition checks and still scores 0.77, because compositions hold only 32% of the weight.
  - The weakest compositions are X5, Q3, Q8 and P8: every natural single-lever reading passes them or breaks them alone.
  - X5 also passes when two wrongs cancel: FieldView dropping nulls plus ini-only presence give the right answer (seen in S4).
- **S2 high.** Unrepaired shipped code earns 14 points: P6 (DFS in sorted order finds the lexicographically smallest of the equal-length plans), X6 and X7 (corrections up front match first and source arrival), and Q1 (the shipped codes are already right). Structure, visible and honesty checks add 9 more.
- **Shortcut.** Module claims accept docstring-only edits.
- **Derivability.** The shipped feed and graph exercise every separating pattern.

## Fix list (smallest first)
1. Break the 14 points the shipped code earns.
   - P6: make the winning plan longer than the losing one (3 edges against 2, same cost, first edge decides, last edges disagree), so fewest-steps and last-edge both fail.
   - X6: give step 1 a `rename:g>h`, so applying corrections up front leaves `h` in the payload.
   - X7: replace it with a correction pinned at the canonical schema, applied on the final arrival. No solver loses X7 today, and the loop-top executor S4 uses would fail it.
   - Q1: add an alias-cycle line and a state-unreachable line, so the shipped one-hop identity and the received-record planner fail it.
   - Expected effect (arithmetic on the measured lost sets, not measured): S2 0.162 to 0.063, S1b 0.120 to 0.021.
2. Close the claim padding. `_module_claims` should strip docstrings (or compare `ast.dump` without `Expr(Constant)` statements) before diffing. Expected effect (arithmetic, not measured): SC1 0.176 to 0.162. Together with fix 1, SC1 and S2 drop to about 0.06.
3. Move weight into compositions of 3 or more NEW levers through `run_pipeline`, and make the isolated single-lever gadgets the minority.
   - For example: ladders fed through the pipeline with null tokens, an alias and a mid-path correction (LV-MR-1 x 4 x 5 x 7); a tie whose winning plan then meets a correction (LV-MR-2 x 7); planning on an explicit null whose fill comes from field_policy (LV-MR-1 x 4 x 6).
   - Keep one isolated check per stage for downstream isolation. Re-measure S4 and S4b; target S4b at most 0.30.
4. Add new levers that S4 already misses and no check tests yet:
   - a correction pinned at the canonical schema (final arrival);
   - a holder that fails planning still holds its identity (K16, "passes the partner stage");
   - an empty partner token line means no tokens (N7; `or default` falls back to the default list).
5. Derivability: regenerate the shipped graph and feed so that each lever's readings agree on the visible data.
   - Prerequisites only on fields no visible operation touches.
   - No equal-cost alternative plans.
   - No explicit null on prerequisite or add fields.
   - Corrections pinned only at the source schema.
   - No replays across aliases or tokens.
   - No malformed feed line, if F is to stay hidden. Otherwise accept F as derivable and count it out of hardness.
   - After the data edit, apply common rule 6.
6. Optional: restate N in K14 from a 2-CPU measurement. 10 x 1.009 s from this machine gives 11.

## Not run or not checked
- No Harbor or Docker run (method (b) only). Timings are from a loaded Mac, not 2 CPUs.
- Judge channel not run.
- The image leak check was done by reading files only.

## Upstream note
Harness HEAD is bde868c4, while the knowledge fingerprints are at 9b8229f6 (GEN 50 changed and 9 missing, QC 9 changed). The master's own qc-push migration report (17:26 IST) covers this, and this audit used no GEN or QC rule. That report also records that this bundle now fails `validate_bundle` §1.4 and §5.5, because the repo-patch archetype moved to `repo/` + `ci/` inputs. A rebuild has to carry that layout change as well.

## Files
- This report and `baselines.json`: `master_chat_work/20261021_schema-migration-plan-repair/hardness_r1/`
- Solvers: `master_chat_work/bundles/_work/schema-migration-plan-repair/wrong/auditor_r1/` (`make_solvers.py`, `solvers/`), `wrong/README.md`
- Raw results: `hardness_r1/raw/` (`results/*.json` per solver with per-check details, `derive.json`, `composition.json`, timing logs, `scripts/` with the harness). The scratch folder was deleted.
