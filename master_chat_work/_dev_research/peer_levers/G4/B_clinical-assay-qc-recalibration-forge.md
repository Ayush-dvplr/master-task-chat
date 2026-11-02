# B: clinical-assay-qc-recalibration-forge

Paths are relative to the task dir. Evidence for the root cause is in `A_clinical-assay-qc-recalibration-forge.md` item 2 (local one-line patch reproduces all 21 artifacts).

## 1. Inventory
- Domain: clinical lab assay QC recalibration. Archetype: a reusable stdlib Python program `/app/out/derive_report.py DATA OUT` plus 21 artifacts from the shipped run (instruction.md L3).
- Agent sees 56 files in `/app/data`: one 5,186 B capture CSV (90 readings), 9 `stage_note_*.md`, `pipeline_contract.md`, `output_artifact_contract.md` (6,646 B), `precision_and_rounding.md`, `footguns_and_gotchas.md`, a live/draft `.xlsx`, a governance `.pdf` (constants in a zlib content stream), a `.docx`, sqlite files, and many superseded decoys (flat archive CSV, shim TSV, PSV scratch book, old YAML, relaxation notes, echo/shadow streams).
- instruction.md 612 words.
- Tests: 35 (6 shape @1, 13 @3, 11 @5, 5 negatives: -5,-5,-5,-3,-3). Some isolated (lot probe, QC exclusion, ordering, recovery floor, live sheet), most whole-output or gated.
- Hidden inputs: yes. A seeded xorshift generator `write_corpus` (`tests/test_output.py` L964) regenerates the visible run (SAMPLE_SEED) and makes CHALLENGE/EVAL corpora (L50-52) plus hand-built probes `_probe_corpus` (L1093-1308) for carry, round-control, sparse, cycling, lot, rounding. Expected values come from an independent `reference()` (L408) run at test time.
- Judge: 9 criteria (7 positive @3, negatives -3 and -5), gpt-5.6-sol. Reward split 50/50 (`reward.toml` 0.005 = 0.5/100, 0.0238 = 0.5/21).

## 2. Rule map (graded rules)
| rule | where stated | form | trap explained? | shipped data separates? |
|---|---|---|---|---|
| live sheet only (focal 1) | instruction; `sheet_selection_rule.md`; `footguns_and_gotchas.md` L3 | one plain sentence, repeated | yes, in footguns | yes (DRAFT sheet differs) |
| governance constants from PDF (focal 2) | instruction; governance source note | plain sentence, value in binary container | yes | yes |
| shared state chain (focal 3) | `pipeline_contract.md` L3 | stage order paragraph | partly ("many wrong figures at once") | yes |
| recovery floor before reweight (focal 4) | instruction; `stage_note_recovery.md`; footguns | plain sentence | yes | yes |
| effective lot = smaller (drift 5) | instruction; batching note; footguns | plain sentence | yes | yes, plus lot probe 9 vs 3 |
| staged Q16.16 rounding (drift 6) | instruction; `precision_and_rounding.md` L3 | plain sentence + definition | yes | yes |
| QC-fail excluded first (trap 7) | instruction; ordering note; footguns | plain sentence | yes | yes |
| shift after clamp, per-channel carry (trap 8) | `stage_note_admission.md` L3-7 | multi-sentence procedure | yes | yes |
| **fair share fixed for the whole settle** (NOT in TRUTH list) | nowhere explicit; `stage_note_convergence.md` L3, L5 imply it ("toward the fair share", "in proportion to what they already hold") | implied by a definition | no | yes: shipped b_open mass 40,697 vs cap 900 gives very different paths |
| convergence stop/cycle rules | `stage_note_convergence.md` L7-9 | long procedural paragraph | n/a | cycle only in probe |
| carryover clawback tie | `stage_note_carryover.md` L3 | one sentence | n/a | yes |

## 3. Lever table (failed checks and criteria)
| id | wt | rule graded | agent reading | correct reading | mechanism | self-test catch? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| analyte_allocations, convergence_rounds, tier_totals_partition, analyte_totals, four_analyte_docs (5 tests) | 3 each | settled masses after convergence | recompute fair share each round (step 25 `fair=d.fair_share(m,an,cap)` inside the round loop) | fair share computed once from admitted masses | one ambiguous definitional sentence; every downstream figure inherits it | N: no oracle; agent's trace looked plausible after it stopped at a zero flow (step 25 "stop zero 10") | NO, implied only. Treat as HIDDEN-ish | B dependent chain |
| convergence_anchor_tie_break_applied | 3 | probe, whole summary.json | same | same | same root, whole-doc comparison | N | same | B |
| core_three_files_all_exact_on_challenge, all_artifacts_exact_on_visible, held_out_eval_corpus | 5 each | whole-doc exactness | same | same | gate `_full_core_matches` L1517-1525 | N | same | B + gate |
| carry / round_control / sparse probe reproduced | 5 each | probe-only rules (carry survives, budget run-out, sparse) | probably right (my patched copy passes the hidden corpora, INFERRED for probes) | n/a | gated behind core exactness, so lost without being tested | N | yes for the probe rules | B (gate) |
| cycling_batch_reports_unsettled | 5 | cycle detection | cycle logic matches spec; fails on the fair-share root | same | same root | N: shipped run does not cycle | cycle rule stated L9 | C state history |
| staged_rounding_fixedpoint_exact | 5 | objective_value on rounding probe | same root (objective depends on settled masses) | same | same | N | yes for rounding | B |
| judge R4 | 3 | run twice and compare | ran once plus a perturbed copy (step 28) | two runs of the shipped data compared | conduct rule not stated | n/a | NOT stated (no twice/determinism sentence anywhere) | NEW: unstated conduct |
| judge R8 | 3 | code quality, no swallowed errors | `except zlib.error` fallback | let errors surface | ordinary review standard | n/a | criterion text is the rule; JD-18 allows it | NEW: code quality |

## 4. Contrast: what passed and why
Passed: all 6 shape @1; live sheet @5, recovery floor @5, carryover reprojection @5; smaller lot, ordering tiebreak, QC exclusion, batch totals, carryover ledger, excluded readings, clawback tie @3. Every one of these is a TRUTH-listed lever written as a plain sentence and repeated in `footguns_and_gotchas.md` with the trap named. This is exactly our leaked-lever pattern from the cohort DIAGNOSIS: rule named with its own exception, decoy refuted on the same page, so the agent coded it right first time. All 8 designed levers leaked. The only point that cost anything was a rule the author did not list as a lever.

## 5. Agent behaviour
- Order: step 2 `find`, step 3 contract/readme/supersession/profile, step 4 all nine stage notes, step 5 artifact contract, rounding, footguns, glossary, step 6 lookup tables, steps 8-13 xlsx/pdf/docx internals, step 14-17 remaining files, step 18 writes whole program in one create, 19-20 two small fixes, 21 run, 22-26 inspection and a hand trace of b_open convergence (step 25), 27 a `<=0` to `==0` tweak in fair_share, 28 perturbed-copy run, 31 final run and digest, 33 closing reply.
- It read every spec file fully before writing. No written plan.
- Self-tests: shipped data plus one hand-perturbed copy (lots 10/7, 20 readings moved to uncovered slots, step 28). No oracle, so neither could show the convergence error.
- Where it went wrong: step 25 trace prints fair shares that move every round and masses going negative (`[49193, -6, -4094, -4396]`); it accepted that as the spec's behaviour.
- Did not notice the error. Final claim "Done ... derived every figure from the authoritative inputs" (step 33) vs reality 17/21 artifacts wrong.
- 34 steps, about 10 minutes of tool work, 18 minutes wall.

## 6. Test design
- Expected values: independent reference at test time on a seeded generator plus probes. No fixed answer file.
- Partial credit: per-figure @3 checks on visible run; whole-doc @5 checks gated on 3 core files.
- Negatives: hardcoded shipped ids in string literals, verifier path tokens, non-stdlib import, nondeterminism, output moves when superseded files are perturbed (L1928-1938).
- Whole downstream document graded: yes (all_artifacts_exact_on_visible, core_three...).
- Shipped-data-only weight: shape 6 + visible-run figure checks (about 8 x 3 = 24) + all_artifacts 5, about 35 of 100 (INFERRED from the test list). The rest needs the program on unseen corpora.

## 7. Judge design
- Failed R4 (unstated conduct) and R8 (code quality). R8 is a reusable pattern: name concrete forbidden shapes (except that discards an error, existence check that silently reads a substitute file, leftover debug output) so the judge can quote a line.
- R4 breaks JD-15 point 1 unless it holds for every competent route: no sentence in the contract asks for a determinism re-run. RISKY for us.
- R1, R5, R6 (open spec before writing; inspect xlsx/pdf structure with a CLI tool before parsing) are process criteria the agent passed easily.

## 8. QC safety of the levers that worked
| lever | IN-15 | TS-16 | TS-19 | TS-20 | AL-28 | verdict |
|---|---|---|---|---|---|---|
| ambiguous "fair share" definition feeding a long chain | fails TS-19 / IN-8 unless the fixed-vs-per-round reading is stated | n/a | RISKY: an honest agent can read it the other way | ok | ok | NOT ALLOWED as is; SAFE only if written as a fully stated definition whose consequence is non-obvious (see GROUP_SUMMARY) |
| gate: whole-doc @5 checks behind core exactness | ok | ok | ok | RISKY: one root costs 58 points, stacking by gating (not a negative, so AL-28 does not apply literally) | ok | RISKY |
| R4 run-twice conduct | fails IN-15 (not stated) | n/a | n/a | n/a | ok | NOT ALLOWED unless stated |
| R8 code quality with named shapes | ok (JD-18) | n/a | n/a | ok | ok | SAFE |
| superseded-file perturbation negative | stated (supersession index) | fires only on use of retired files | ok | -3/-5 fine | own trigger | SAFE |

## 9. Writing style (technique, not content)
- `stage_note_convergence.md` L5 "The target is the batch mass when that mass sits at or below the batch cap, and the batch cap otherwise." Technique: the rule is a definition with a branch, no warning attached.
- L7 "A round counts as non-improving when its residual is greater than or equal to the previous residual" Technique: boundary (>=) folded into a definition, no "note that equal counts".
- L9 "where the cycle begins at the first sighting of the repeated state and states compare as their masses read in analyte name order" Technique: two edge rules tucked as a trailing clause.
- Counter-example (leaks): `footguns_and_gotchas.md` L3 lists every trap with its wrong reading. This file is why all 8 designed levers were passed.
