# GROUP_SUMMARY: poonam (board f2e6166)

Repo HEAD `2dfb1f8f7b86db305b1f6afa63279873e6e918e4`. Session renamed OK (opencode `ses_e8e7e3feaffe0iP6bZEnkabzbd`). The study was read-only. Nothing was executed except `stacking_check.py`.
Short ids: T1 = `00372225-134c-56e6-80ea-8bd47c66c816`, T2 = `66b1a1e2-7d80-50ad-9c7c-bc71d5f64c24`. Both were authored by Aryan Mehta (task.toml) and sit in the Poonam_Chourey delivery folder. The detail behind each claim is in `A_*.md` and `C_*.md`.

## 1. Table

| task | verdict | overall / tests / rubric | genuine test points lost | main lever shape |
|---|---|---|---|---|
| T1 (assay pipeline, Data Processing) | GENUINE | 56.72 / 42.0 / 71.43 | 58 of 100 | **Binding time of a defined quantity left unstated.** The note defines "fair share" from what the analytes "already hold" before the round loop, but never says whether it is computed once or every round. The agent recomputed it each round (derive_report.py:275). The reference fixes it before the loop (tests/test_output.py:250-264; solve.py:287). The disclosed core cascade (instruction.md:23) then turned one stage into 14 failed checks. This is a HIDDEN RULE and not one of TRUTH.md's 8 designed traps (TRUTH.md:6-20). |
| T2 (calendar reconciliation, Software Eng.) | PARTLY (gate stated) | 46.09 / 62.59 / 29.58 | 52 of 139 raw (= 37.41 on the tests scale): 10 direct + 42 through the gate | **Hidden stores that hold the separating cases × a per-store spine gate.** The agent was byte-exact on shipped, challenge, dense, mtime, revshift and encshift. Its spine failed only on the `eval` store (several axis shifts at once) and the `probe` store (stated edge rules whose shapes never occur in shipped data). `_assert_full_core` (test_output.py:2940-2950) then voided every leaf on those two stores. The specific wrong rule is UNDETERMINED: there are no verifier messages and I was not allowed to execute anything. |

Neither run has an artefact: exception_info is null in both, there were no timeouts, and every output file is present.

## 2. Test-design patterns, ranked by genuine test points they caused to be lost

| # | pattern | mechanism | how graded | how it passes QC | tasks | points | SAFE/RISKY |
|---|---|---|---|---|---|---|---|
| P1 | Core-exact gate for whole-document checks | A helper requires the 2-3 core files to be byte-exact on a store before any whole-run or leaf check on that store can pay. | T1 `_full_core_matches` L1556-1564 gates 6 x5 checks. T2 `_assert_full_core`/`_gated` L2940-2952 gates every per-report check on a store. | The instruction states the cascade (T1 instruction.md:23 "shows up as many wrong figures at once"; T2 instruction.md:7). QC took this as CL-4 cover: the T1 QC report shows 0 warns, and the T2 QC report has W3 "prior QC accepted this as the task's design". | T1, T2 | T1 30 of 58, T2 42 of 52 | RISKY. It amplifies one miss 3-5x. It passes only with a plain instruction sentence, which matches the QC_FIX_PLAYBOOK CL-4 row. |
| P2 | Hidden stores or corpora re-run from a generator in tests/ | Tests regenerate the corpora from seeds, run the agent's program as an unprivileged user and compare bytes. T1 compares against an independent reference (L410-612). T2 compares against stored SHA-256 digests of reference output and carries no rule code (docstring L1-6). | T1: every figure is graded on shipped data and on a shadow corpus, plus challenge and eval. T2: 132 of 139 points are earned by re-executing on unseen stores (TRUTH.md:231-234). | Satisfies TS-19 (the generator stays in bounds), G3 and G8. QC tests_qc passed. Oracle 1.000. | T1, T2 | All 110 points lost were on re-runs or gated checks. Shipped-only checks were almost all passed. | SAFE |
| P3 | Probe store or corpus whose separating cases are hidden-only | Tiny corpora that each fire one rule with constants that differ from shipped (T1 probes L1077-1310). T2 has one probe store packed with fold, escape, parameter, boundary and override shapes that are absent from shipped data (L1178-1330; for example, a grep found no `BYMONTHDAY=-1` or quoted `CN="` in data/). | Per-probe digest or figure. | Each rule is stated in a doc, so IN-15 and TS-19 hold. W5: the separating case is hidden-only. | T2 probe (14 pts); T1 probes (staged/carry/round/sparse 20 pts, though there they failed only through the convergence reading or the gate) | 14 to 34 | SAFE when each probe check compares its own stage. RISKY when a probe compares a downstream figure: T1 `_staged_rounding_fixedpoint_exact` L1847 compares only the objective, so a convergence error cost a rounding check. |
| P4 | Definition placed before a loop, with no binding-time sentence | One paragraph defines a quantity from the current state, and the next paragraph runs rounds that change that state. | Indirect: through allocations, totals and the objective. | QC did not notice. An IN-16 reviewer would flag two readings. | T1 | 58 (root of all T1 loss) | RISKY. Effective here, but it fails IN-16 if spotted. Our safe version would be one far-away sentence that fixes the binding (W2/W3). |
| P5 | Combined-axis hidden store | One hidden store changes the epoch, declared revision, edition, cluster size and rotations at once. | Spine digest plus 11 leaves (38 pts). | Every axis is stated in a doc (TRUTH.md:137, 182-196). | T2 | 38 | RISKY. Effective, but it hides which rule failed (undiagnosable here). |
| P6 | Axis-equality mutation checks | For example, re-encoded store == challenge output, renamed store output differs from shipped only by names, with revshift and mtime variants. | `_p_encoding_shift`; core_spine_exact_on_mtime/revision_shift. | G6 mutation tests. | T2 (passed) | 0 | SAFE, but cheap for Opus: it handles encodings and names well (LEVER_RULES line 35). |

## 3. Leak-avoidance patterns (with the LEAK_LIBRARY row each would have fixed)

| pattern | evidence | would have fixed |
|---|---|---|
| L-a. **Silence on binding time inside a long, fully explicit note.** Every other sentence of the convergence note is exact (half-up, damping halving, cycle rule), so the gap reads as "obvious". The agent's literal transcription produced the wrong one of two readings without any doubt, even while its own trace showed masses going negative (trajectory step 20). | stage_note_convergence.md L3-L7. Agent step 20/32 claims. | CR-3 ("one sentence, no alternative reading"): we stated every rule so precisely that no second reading existed. Note that this lever is unstated, not hidden-but-stated. Our compliant version must state the binding somewhere far from its use (W2). |
| L-b. **Separating shapes only in hidden stores.** The rule plus a worked example sits in a doc, but shipped data never exercises the edge, so the agent's self-tests on shipped data cannot reveal a mis-coded edge (T2 probe; the agent ran only an in-memory policy-flag smoke test, step 96). | T2 test_output.py:1178-1330 vs a grep of data/; trajectory step 96. | RUN (the shipped stream separated the readings), CR-2 and V0 rows where shipped boundary rows let the agent watch each rule fire (W5/W6). |
| L-c. **Neutral hash-style data file names plus about 27 rule docs (14.5k words) with rules spread by topic.** The rule for a field sits in a topic doc, not next to the field. | T2 data/ names (`cell-b58c.xml`, `store-0a9a.json`); 27 md docs. | V0-2..V0-8 (W2 split-near-use), REMAP/REJ (numbered rule lists next to use). |
| L-d. **Many interacting stages, each with probes carrying different constants.** Hardcoding or transcription loses each probe (T1 lot probe uses lots 9/3; TRUTH.md:44). | T1 L1203, L1226, L1241. | ENC/STATE (self-testable rules): the probes make the score depend on the rule rather than the shipped number. They do not by themselves create failure. |
| Counter-example (leaked here too): T1 `footguns_and_gotchas.md` and the instruction's "Rules for the calculation" bullets spell out the 8 designed traps. Every one of them passed (C_00372225 §8). | generator L953; instruction.md bullets. | This confirms CR-1/W1: a trap that is spelled out is a free trap. |

## 4. Where these tasks differ from our LEVER_RULES

- **Instruction states rules of its own (vs W10).** T1's instruction carries a rule bullet list (smaller lot, floor before reweight, staged rounding). All of them were passed, which confirms that W10 is right to forbid this.
- **Whole-store gating of leaves (vs G1/G2 "each test own rows, no early return").** Both tasks gate. QC accepted it when it is stated (G5 / the CL-4 kit exemption). It produced most of the lost points, so our G2 is stricter than QC needs. Using it is a policy choice, not a QC risk, provided G5 is met.
- **Expected values as stored digests (T2) vs an independent reference at test time (T1, our G9).** Both satisfy G9. The digest form also keeps the rules out of tests/, which our rules do not mention.
- **A hidden rule (T1) vs IN-15/TS-19 and our "rule fully stated" stance.** The 58-point loss came from a reading the spec never fixes, and QC missed it. Our rules forbid this, and we should keep forbidding it: it is luck, not design (TRUTH.md lists no measurement for it, L110-123).
- **TS-13 bundle passed QC.** T1 `_cycling_batch_reports_unsettled` L1785-1800 `and`-bundles four observables, yet the QC report shows 0 minors. QC_RULINGS treats this as MINOR.
- **Judge (J2/J8).** T2's judge has 19 process criteria such as "printed X" or "built a renamed/re-encoded copy" (R5-R20). The agent failed 15 of them, and an R31 overclaim negative fired (-5), giving a rubric of 29.58. This lies outside our J1-J9 emphasis on conduct. It is score-relevant but not a test lever.
- **Probe compares a downstream figure** (T1 staged probe, objective only). This would breach our G2 isolation. It passed QC.
- **Not in our rules:** a per-axis store family with equality checks (P6), the generator rewriting spec text together with each corpus (T1 `_write_specs` L936-963), and verifier path tokens assembled from fragments so that tests/ never names grader paths (T1 L1905-1916).

## 5. Anti-patterns and artefacts

- Artefacts: none. Both runs had no exception and no timeout, and every output was present. T2 cannot be diagnosed further because ctrf has no messages and test-stdout holds only the reward. That is a G7 gap, not an artefact.
- `stacking_check.py` false hints (corrected by reading the code): the T1 TS-26 group of all 30 positives (they go through wrapper functions); the T1 AL-28 "UNMATCHED act" group of 16 (actually 4 distinct acts); T2 TS-26 duplicates (same report on different stores); and isolated-vs-gated class labels in both.
- Anti-patterns: the footguns file (T1); `and`-bundled checks (T1); probe checks graded on a downstream figure (T1); unstated binding time (T1, an IN-16 exposure); an `except zlib.error: pass` in the agent code cost judge R8 in T1 (agent-side, not task-side).

## 6. Open questions for the master

1. T2: which rule broke the eval and probe spines? Answering needs one sanctioned execution of the agent's `schedule_repair.py` on the regenerated eval and probe stores, which was outside this study's permissions.
2. Do we adopt the stated per-store or core gate (P1)? It passes QC with a plain instruction sentence, but it converts 10 direct points into 52.
3. Can a binding-time lever (P4) be made IN-16-clean by a single distant sentence, and does Opus still miss it once the sentence exists? Our 25 Oct results suggest it will transliterate the sentence.
4. Should our hidden generators always include a "probe store" of stated-but-unshipped edge shapes (P3/L-b)?

## Lessons for the master
1. Both tasks lost most of their points through a stated core gate (T1 30 of 58, T2 42 of 52). One real miss counts 3-5x, and QC accepts it when the instruction says so.
2. The only fully traced miss (T1) was an unstated binding time, not a designed trap. Every trap that was spelled out (footguns file, instruction bullets) was passed.
3. Separating cases that exist only in hidden stores beat Opus's shipped-data self-tests (T2 probe and eval). Shipped data must not let the agent watch the edge fire.
4. Expected values as stored digests plus a generator in tests/ keep rules and the oracle out of reach and satisfy G8/G9.
5. Require failure messages in verifier output (G7). T2's loss cannot be diagnosed from the run folder.
