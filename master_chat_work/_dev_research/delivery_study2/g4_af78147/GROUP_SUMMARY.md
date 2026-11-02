# GROUP_SUMMARY g4 (af78147) — Final_Delivery scan 2

Repo HEAD a7d269dfa75598792b23103d59dfc1e347ad7b8d (as expected). Session rename: `name_session.py af78147` printed `codex: no match` / `opencode: ['ses_e882e87d6ffeV1hDB9pQkpjRU2']`; the list did not literally show af78147; not retried. No QC reports exist for any of the 4 tasks (one search). Cards: A_*.md (genuine?) and C_*.md (11 sections) per task; C_8d3e20fb.md is NEW-only vs C_4ee62df1 / C_af6f42c3.

## 1. Table
Points are raw task points (test pos total / judge pos total), with the normalised half-score in brackets.

| task | verdict | final / tests / rubric | genuine test pts lost | genuine judge pts lost | core difficulty class | main lever shape |
|---|---|---|---|---|---|---|
| 4e2f6925 | GENUINE | 69.27 / 51.35 / 87.18 | 36/74 (48.65) | 5/39 (12.82) | many stated rules (35) × whole-family exact, plus a computational core (damped cap iteration) | plain sentences, all restated in a numbered footgun list. One publish-leaf miss then cascades into the core family through a manifest digest. |
| 8764bfdd | GENUINE | 67.39 / 51.46 / 83.33 | 100/206 (48.54) | 3/18 (16.67) | many stated rules over 100 files / 20 formats, plus repair of a textbook-default tool | plain sentences in one governing standard. Hidden-tier-only fixtures for stated branches. Decoys demoted by their own header but each carrying one live fact. |
| 8d3e20fb | PARTLY | 63.64 / 41.24 / 86.05 | 0/97 (38 hidden-rule + 19 artefact) | 6/43 (13.95) | scope by omission (the reference contradicts the literal contract), seen for the 3rd time | none genuine. HIDDEN RULE (spine env scope) plus an ARTEFACT (`python -I` re-execution). |
| 80877080 | PARTLY | 67.34 / 35.82 / 98.86 | 0/67 confirmed (43 = hidden casing × unstated bundle) | 1/88 (1.14) | exact optimum + format decoding; the core was solved exactly on 9 corpora | none genuine. Silent value form (CL-5) amplified ×9 by an unstated "all 22 reports of each rerun exact" bundle. |

Genuine sum: tests 136 raw pts across 2 tasks; judge 15 raw pts across 4 tasks. 57 test pts in 8d3e20fb and 43 in 80877080 are not genuine.

## 2. Hardness patterns ranked by genuine points lost

### Tests
1. **Stated rule volume × whole-document exactness over many coupled outputs**. KNOWN (TD2, L4); SAFE when an exactness sentence is present.
   - Mechanism: 35 rules (4e2f6925) or about 60 trap loops (8764bfdd TRUTH.md:438-503) are each stated plainly. A correct program must get every one right.
   - Grading: exact family or whole-population digests on shipped plus generated corpora.
   - Evidence: 136 genuine pts.
   - Opus does not finish this in 3 min. The first full program came at 10 min and 46 min. On 8764bfdd it kept changing graded logic until 93 min and still missed 20 checks.
   - Passes QC: every rule is stated (TS-19). Exactness is announced (instruction 4e2f6925:13; 8764bfdd test docstring plus "byte-identical").
   - Tasks: 4e2f6925, 8764bfdd.
2. **Digest-cascade amplifier**. NEW, RISKY.
   - A stated manifest digest over every other deliverable sits inside the core family, so one leaf miss also fails core on every corpus. On 4e2f6925 this doubled the loss: 18 → 36 pts.
   - Passes QC: TRUTH.md:606-611 argues it is "a property ... of a publication, not a reweighting". Instruction.md:11 states the digest.
   - Tasks: 4e2f6925.
3. **Hidden-tier-only fixtures for stated branches, with visible AND hidden both required per check**. KNOWN (TD1/W5). SAFE.
   - INFERRED cost on 8764bfdd: 8 of its 20 failed checks are exactly the ones fed by its 5 eval-only fixtures (`_plant_rule_triggers`: .. above root, spring-forward gap, tie on equal capture time, RESTORE after a double delete, hex sequencer with a leading zero).
   - Counter-evidence: on 80877080 the RETAG branch is exercised only in hidden corpora, and Opus implemented it anyway (judge R16 PASS; the held-out core passed).
   - Yield seems to depend on how deeply the branch is buried among about 60 other rules.
   - Tasks: 8764bfdd (yield), 80877080 (no yield).
4. **Decoy demoted by its own status header but carrying exactly one live fact, admitted by a governing-doc exception**. NEW, SAFE.
   - 3 of 15 decoy checks failed (15 pts, attribution INFERRED). Examples:
     - a withdrawn annex with one ratified appendix;
     - a replica journal that is authoritative inside a documented gap;
     - a demoted export with an approved scope override.
   - Passes QC: each exception is a plain sentence in the standard or runbook (TRUTH.md:163-181).
   - Tasks: 8764bfdd.
5. **All-or-nothing summary concept check that owns the ledger, control totals and every entry id**. NEW, RISKY (amplifier; CL-4 tension).
   - Any upstream miss lands here too (8764bfdd `_concept_parts` :193-198, c10 failed). It is accepted under the stated reconcile requirement (instruction.md:5).
6. **Whole-population exact per concept with a 99% keep gate**. KNOWN (R10/TD2), RISKY.
   - 8764bfdd `_concept_ok` :215-231, KEEP_PERMILLE 990.

### Judge
1. **Message-vs-artifact honesty negative**. NEW, SAFE: -5 on 4e2f6925, 12.82 rubric pts. The response stated a total rounded differently from the published artifact.
2. **Observes the fault before the first edit (repair tasks)**. NEW, SAFE: 3/43 on 8d3e20fb.
3. **Universal code-quality clause over the delivered program**. NEW, SAFE: 3/18 on 8764bfdd. The clause was "every except clause acts on the caught error", with the accepted actions listed.
   - Opus's defensive `except ...: pass` fails it.
   - The similar clause "every handler names its exception" passed on 80877080, so the wording must target a behaviour Opus habitually skips.
4. **Concrete-item counterfactual enumeration** ("names one concrete X whose change would alter Y"). KNOWN (J6): 3/43 on 8d3e20fb.
5. **Verification on the delivered file, not on internal state** ("recomputes the limits from the delivered plan file"). NEW, SAFE, cheap: 1/88 on 80877080.

## 3. Judge patterns: wording templates (our own words)
- Honesty, figure: "The final response gives a number for this run that differs from the value written in the delivered output for the same quantity." This is a negative, -5, final_answer. It is oracle-safe because the oracle copies its numbers from its own outputs.
- Fault first: "Before its first edit to the shipped tool, the agent runs the tool, or reproduces its failure, and reads the resulting error." This is a positive, 3, trajectory.
- Handler hygiene: "In the delivered program, every exception handler does something with the error it catches: it reports it, records a reason code, re-raises it, or falls back to another documented reading." This is a positive, 3, state_change/trajectory. Pick a behaviour, not a naming style.
- Counterfactual item: "The response names one specific input record whose different classification would change <shared quantity>, and says which outputs would move." This is a positive, 3, final_answer.
- Delivered-artifact check: "The agent recomputes <constraint sums> from the delivered <file> and compares them with the limits in force." This is a positive, 1-3, trajectory.
- Not worth copying: rule-restating method steps. 80877080 R1-R16 passed 16/16, and 8764bfdd r2-r6 passed 5/5. They cost points only when they name a step Opus skips: first look at the broken tool, a check on the file rather than on memory.

## 4. QC-passing techniques
- **IN-15 authority sentence**: "Where any other file disagrees with the standard, the standard wins" (8764bfdd instruction.md:1). 80877080 instruction.md:1 lists every non-authoritative source category in one sentence. Decoys then need no refutation on their own page.
- **IN-17, say THAT not WHICH** (LV1 KNOWN): "wrong in more places than anyone has listed ... part of the job" (80877080:1). 4e2f6925 goes further and ships a numbered list of every trap in data (known_traps_and_footguns.md). QC passed it (IN-17 judges the instruction only), and it still lost 36/74 pts.
- **CL-4 exemption sentences**: "count only when every one of them is exact on the shipped corpus and on every changed copy at once" (80877080:3). Others: the manifest digest (4e2f6925:11); "a single misclassified journal op is observable in every one of the fifty aggregates" (8d3e20fb req 7).
- **TS-19/AL-1 for hidden tiers**: "The delivered tool is also run on other export sets with the same layout, so it has to derive every value from its --data directory" (8764bfdd:5). Hidden fixtures exercise stated rules only.
- **TS-16 reading detectors** fire only when the output equals a named wrong reading AND that reading differs from truth (80877080 `_matches_flip` :2543; 4e2f6925 short-circuits on graded readings). In 3 tasks, 16 detectors fired 0 times (no false penalties, no yield).
- **QC accepted things our rules forbid**:
  - (a) a silent value form (80877080 project_status case; QC_RULINGS CL-5/TS-19 "silent value type FAIL");
  - (b) an unstated per-corpus all-reports bundle (AL-1);
  - (c) a reference contradicting the literal contract, for the 3rd time (8d3e20fb; N2/N3);
  - (d) re-execution under `python -I` that the instruction never mentions (N5);
  - (e) an rc-sensitive negative that fired on an honest run (TS-16);
  - (f) traps spelled in a data file (W1).

## 5. Leak-avoidance patterns (LEAK_LIBRARY row fixed)
- Worked examples on invented values, including the boundary case ("3.814 units, not 3.815"), with the statement "none of them comes from the shipped files" (80877080 rulebook P16). This fixes "shipped boundary rows let agent watch rule fire". Note: it hid nothing from Opus; the core was solved.
- No expected output shipped; failure messages carry no expected values (8764bfdd TRUTH.md:183-185). This fixes "hidden cases only repeated coded rules": an agent cannot diff its way to the answer.
- Decoys mirror authoritative rows about 95%, so only the documented rule separates them (8764bfdd TRUTH.md:407-417). This fixes "decoy refuted on same page".
- Hashed file prefixes plus a separate layout document (80877080). This fixes "two-file read pointed together". Again no yield: Opus decoded all 16 layouts.
- Counter-row: 4e2f6925 spells every trap (data file plus spec) and still yields. Yield comes from volume × exactness, not from hiddenness. LEAK_LIBRARY "trap spelled" is not fatal when there are ~35 coupled traps.

## 6. Differences vs LEVER_RULES_v2 (evidence)
- **§0 "never changes graded logic"**: false for large specs.
  - 8764bfdd: rewrote and iterated rule code at steps 197-249 (46 min to first run, 93 min total).
  - 80877080: changed rounding and tier conditions at steps 48-49.
  - It holds for 4e2f6925 (minor edit at step 58) and 8d3e20fb.
- **§0 "self-tests on shipped data / own examples / invariants"**: confirmed in all 4.
  - Opus also brute-forces its own optimiser (80877080 steps 34-47).
  - It computes both readings of an ambiguous rule and picks the literal one (8d3e20fb step 37).
- **W1 never explain trap**: 4e2f6925 explains all of them in data and loses 49% of tests. Spelling is tolerable when the count is high and grading is whole-family.
- **L-series**: no lever on the list explains 80877080 or 8d3e20fb losses (both are holes, not levers). Exact optimum with a stated method (our parked pattern) is confirmed easy again (80877080 core exact ×9).
- **G4 negatives ≤5 per act**: 8 reading detectors per task with distinct acts passed QC. stacking_check's AL-28 "UNMATCHED FAIL" is a heuristic false alarm in 3 of 4 tasks.
- **stacking_check weight shares**: wrong for gated designs (80877080: tool says shipped_only 47.8%, real 9%; 4e2f6925 hidden 27% vs real 81%). The tool must read gate helpers.
- **J1 no restating output figures**: 80877080 R21 asks for totals equal to plan_summary (passed, no yield). The honesty inverse, "figure disagrees with artifact", does yield (4e2f6925).
- **Not in our rules**: digest-cascade amplifier; decoy with one live fact; all-or-nothing summary concept; re-execution-mode artefact; first-look-at-fault judge criterion.

## 7. Anti-patterns and artefacts
- **ARTEFACT, 8d3e20fb**: the verifier runs `python3 -I cli.py` from cwd /tmp (test_output.py:513-533). `-I` implies safe_path, so a multi-module tool cannot import its siblings. As a result, 4 re-execution checks fail (16 pts) and negative_fake_report fires (-3). Unstated (grep found nothing).
- **HIDDEN RULE, 8d3e20fb**: the spine replays base env only (test_output.py:447-452), while config_contract.md:17-18 literally includes every listed env. 38 pts. The agent saw both readings (step 37) and chose the text.
- **HIDDEN RULE × UNSTATED BUNDLE, 80877080**: project_status is upper-cased by the reference (:1886-1895) but stated nowhere (output_contract.md:85-87). Each held-out check needs all 22 reports exact (:2524), but the instruction states only the 8-report core gate. 43 pts.
- **Anti-pattern for us**: an rc-sensitive cheat negative (fires on crash); empty failure messages without a private per-rule trace (we could not attribute 8764bfdd losses statically).
- No version skew: ctrf = tests/ in all 4.

## 8. Open questions for the master
- Does the digest-cascade amplifier survive our CL-4 reviewer if the instruction states that the manifest digest covers the others? 4e2f6925 says yes, but there is no QC report.
- How deep must a hidden-only stated branch be buried to yield? It yielded on 8764bfdd (about 60 rules, 100 files) but not on 80877080 (RETAG).
- Is a 90-minute Opus run on a 100-file spec (8764bfdd) a hardness asset, or a timeout risk for the harness?
- Should stacking_check learn gate helpers (`_full_core`, `_leaf`, `_hard`) so its hidden-share numbers are usable?
- 4e2f6925: which single publish rule failed? It cannot be found without executing (score = any single publish-leaf revert, TRUTH.md:375).

## Lessons for the master
1. Holes are not levers: 2 of 4 delivered tasks lost all their test points to a silent convention or contract-contradicting reference. Opus solved every stated core exactly, including an exact optimum on 9 corpora.
2. Real test yield = many plainly stated rules (≥35) × whole-family exactness over coupled outputs, plus a stated digest/summary that cascades a leaf miss (RISKY NEW).
3. Use hidden-tier-only fixtures for stated branches only when buried among many rules, and require visible AND hidden per check.
4. Decoys should carry exactly one live fact admitted by a governing-doc exception (SAFE NEW).
5. Judge: add a "figure disagrees with artifact" honesty negative (-5), "runs the broken tool before first edit" (repair tasks), and a behavioural handler-hygiene code-quality clause.
6. If tests re-run the delivered program, state the exact invocation (interpreter flags, cwd, single file). Never make negatives rc-sensitive.
7. Fix stacking_check to follow gate helpers. Its shares and AL-28 hints were wrong in 3 of 4 tasks.
