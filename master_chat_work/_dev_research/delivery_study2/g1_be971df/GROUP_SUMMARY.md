# GROUP_SUMMARY g1 (be971df): Final_Delivery scan 2, lowest finals (34-48)

Repo HEAD a7d269dfa75598792b23103d59dfc1e347ad7b8d. Session rename: name_session.py printed an opencode match (`ses_e882f029…`), not the literal id `be971df` (noted, not retried). Per-task evidence: `A_<id>.md` (Step 1) and `C_<id>.md` (Step 2) in this folder.

**Main answer.** In 4 of 5 tasks Opus wrote a program that is exactly right on the shipped data and wrong on hidden corpora. The reason is that the shipped instance never fires the branch that matters:
- degenerate full-rank rate card: 18b5d99f;
- no mid-season change: 3f39299a;
- no four-arm, SHORTENED or tie structure: b42c61b9.

Its self-checks miss this every time, for one reason: they re-derive its own reading on shipped data, or on a "changed copy" that changes values but not structure. In 2 of those 4 tasks the wrong program has the same signature: fitting code that returns the **first** fit instead of requiring a **unique** fit (18b5d99f, 3f39299a). The fifth task (6d12f970) is the only one where the shipped data separates the readings. There, Opus solved a 12-constant recovery, a fixpoint and branch-and-bound, and lost on two cheap settlement rules next to that hard core.

## 1. Table
| task | verdict | final / tests / rubric | genuine test pts lost | genuine judge pts lost | core difficulty class | main lever shape |
|---|---|---|---|---|---|---|
| 6d12f970 | GENUINE (judge: version skew, the regrade used an older judge.toml; failures are real under it) | 33.9 / 3.09 / 64.71 | 94/97 | 12/34 (run rubric) | stated rule misread + implied rule, beside a computational core | definition later redefined by an operational clause ("net" before vs after cap), plus precedence implied by a definition-by-exclusion. Whole-settlement compare on every tier amplifies it |
| 18b5d99f | GENUINE | 36.81 / 7.77 / 65.85 | 95/103 | 14/41 (all negatives) | computational core + scale behind a degenerate shipped instance | rule family stated as a closed candidate space; shipped card full rank; hidden cards underdetermined (39^5..39^11); first-consistent instead of unique |
| 7c2e77a1 | PARTLY (46 test pts artefact) | 37.97 / 10.94 / 65.0 | ≤11 (INFERRED, unpinned) | 1 certain (20 INFERRED cascade from the artefact) | other: oracle defect / hidden rule with no evidence path | hard-coded expected constants from an oracle that bisects over 5 inverted window rows; the stated containment rule and the test's own `_truth` agree with the agent |
| 3f39299a | GENUINE (lever is a HIDDEN RULE that QC passed as a WARN) | 39.66 / 5.17 / 74.14 | 110/116 | 15/58 | unstated rule behind a degenerate shipped instance + exact-fit uniqueness | finishing pass plants an undocumented mid-season settings change in all 22 hidden corpora; one assignment fits the whole shipped season |
| b42c61b9 | GENUINE by design, cause unpinned | 47.53 / 8.96 / 86.11 | 61/67 | 10/72 | breadth + stated branches that fire only on hidden corpora + stated all-corpora gate | `_full_core` gate: 7 core reports exact on shipped + 8 held-out at once, otherwise 61 pts are lost |

## 2. Hardness patterns ranked by genuine points lost
### Tests
1. **Degenerate or benign shipped instance; all weight on hidden corpora where the branch fires** (266 pts: 18b5d99f 95, 3f39299a 110, b42c61b9 61). KNOWN in part (S2 "data-rule no-op on shipped", §0b "branch never firing on shipped data"). NEW as a deliberate *core* design: the shipped instance collapses the hard core to a closed form (full-rank system / single fit / ≤3 arms), and the tests put 77-95% on corpora where it does not collapse. How graded: whole-document exact per hidden corpus, generated at grade time. How it passes QC: an instruction sentence promising reruns on "other extracts … with their own …" (TS-19/AL-1). The general space is stated (18b5d99f rule families; b42c61b9 handbook branches). 3f39299a states nothing and passed on a WARN. SAFE when the general rule is stated (18b5d99f, b42c61b9); RISKY when it is not (3f39299a).
2. **First-fit versus unique-fit in recovery code** (205 pts, 18b5d99f + 3f39299a, inside pattern 1). NEW. The reference collects every candidate that reproduces the evidence and requires exactly one (18b5d99f test_output.py:751-761; 3f39299a TRUTH "collects every fit, raises on 2+"). Opus returns the first fit (18b5d99f optimize.py:532-570; 3f39299a derive_report.py:387-500, `identify_procedure` returns `combinations[0]`) and seeds with presets. On shipped data first = unique, so no self-test can tell them apart. SAFE: it is graded only through outputs; the judge mirrors it as a program property.
3. **Cheap trap next to a hard core, with the defined quantity silently redefined later** (94 pts, 6d12f970). NEW. "Net = charge less rebate" is followed three lines later by "the order settles the remainder" (cost_policy.md:8-13). Opus spent its self-test budget on the hard parts (brute-force placement, synthetic corpus generator) and documented the literal definition reading in AGENTS.md. RISKY: it is an IN-16 two-readings exposure; the agent named both forks.
4. **Implied precedence via a definition-by-exclusion in the schema file**, decoyed by a procedural "resolve X before Y" sentence (inside 6d12f970's 94). NEW variant of L6 (scope carried by a definition). RISKY (same IN-16 exposure).
5. **Amplification and gates** (every task). KNOWN (K3, R9). Whole-settlement compare (6d12f970), whole-record canon (7c2e77a1), all-or-nothing per extract (3f39299a, 18b5d99f), and an all-corpora core gate (b42c61b9). Each one converts 1-2 slips into 85-95% loss. QC accepts it when the instruction states exactness (CL-4 via FC:491).

### Judge
1. **Conduct/property criteria that mirror the hidden tier**: 3f39299a 15 (changed-extract run, path discipline, unique settings fit, unique procedure fit, no preset fallback); 6d12f970 12 (menu of "run on a constructed corpus of kind X" criteria; the agent did 3 of 7). NEW shapes (uniqueness, no preset fallback) on top of KNOWN J2.
2. **Honesty-of-coverage and side-script negatives** (18b5d99f 14): exponential enumeration -5; what-ifs answered by a side script carrying shipped constants -3; misstated size of its own check -3; claims recovery on weak cards never run -3. NEW (R19/R20 shapes).
3. **"Executed the spec's own worked example for branch X"** where X never fires on shipped data (b42c61b9 9). NEW.
4. **Counterfactual closing figures** (7c2e77a1 20, INFERRED artefact cascade): these turn engine slips into judge points. KNOWN shape (J1), heavy weights here (w5 each).

## 3. Judge patterns (wording templates, our own words)
- T1 uniqueness property: "The delivered program accepts a recovered value only when exactly one candidate in the stated space reproduces the evidence, and stops with a stated error otherwise." (oracle must satisfy it; JD-7)
- T2 empty-fit path: "When no candidate reproduces the evidence, the program takes an explicit failure path and does not substitute a preset or estimated value."
- T3 constructed-input menu (w1 each, 5-7 items): "The agent runs its delivered program on an input it built in which <one structural property> differs from the shipped data, and checks <named output property>." A byte-identical copy does not count.
- T4 worked-example run: "The agent runs its implementation of <rule section> on the example printed in <file §>, and compares its result with the printed value."
- T5 coverage honesty (negative -3): "The response states that <capability> works on <case class>, but no step in the trajectory runs it on a case of that class."
- T6 count honesty (negative -3): "The response gives a size or count for its own check that differs from what the trajectory printed."
- T7 side-script negative (-3): "A what-if answer comes from a script other than the delivered program that carries values fixed from the shipped data."
Why these cost a strong agent points: Opus verifies by re-deriving its own reading on shipped data, so any criterion that needs an input where the readings differ, or a uniqueness assertion, catches it. None restates an output figure (JD-8 clean). Each is checkable from the trajectory or code.

## 4. QC-passing techniques
- **CL-4 / gates:** an explicit exact-bar sentence. Examples: 7c2e77a1 "one frame out of place on one event fails the artifact holding it"; 3f39299a "Every report must match exactly, byte for byte"; b42c61b9 "a near miss anywhere earns nothing". QC: WARN accepted (b42c61b9 QC :101; 3f39299a QC :86; 18b5d99f QC :75-77).
- **TS-19 / AL-1 for hidden corpora:** a promise sentence that enumerates what changes in reruns (b42c61b9 instruction.md:3; 18b5d99f instruction.md:7 "an extract in this layout in its own right"). 6d12f970's generator also re-renders the rule documents per corpus, so every mutated rule is stated for that corpus.
- **IN-16 without stating the rule:** a closed candidate space plus a uniqueness proof in TRUTH (18b5d99f: 1 of 666 rankings, 1 of 16 standing rules; QC :63-66). 3f39299a: 0 assignments fit the whole hidden season, exactly 1 per half.
- **IN-15 / hidden rule accepted as WARN:** 3f39299a QC F0e/DS-21/CL-10: "It is still reachable … Hard, not impossible, so warn." It is backed by weak cues (a "settings at the close of the season" field; a what-if that changes settings mid-season). Our QC_RULINGS IN-15 treats an unstated graded rule as a FAIL.
- **JD-8:** QC rewrote output-rule criteria into process criteria (b42c61b9 F3). That is how the worked-example criteria were born.
- **IN-17:** the instruction says the material is wrong and that "finding that out is the task", without naming any defect (7c2e77a1, b42c61b9).
- Accepted although our rules forbid it: one shared gate over ≥85% of points (vs G10 independence); a hidden rule with no sentence (3f39299a, vs IN-15/N3); an oracle quirk on malformed rows (7c2e77a1, no QC report, vs never-used (a) "malformed lookup line with no stated outcome").

## 5. Leak-avoidance patterns
- LA1 The degenerate shipped instance itself: no shipped record separates the readings, so even a careful self-test cannot find the trap (18b5d99f, 3f39299a, b42c61b9). Would fix LEAK_LIBRARY common cause "shipped boundary rows" and vendor row RUN ("shipped stream separates").
- LA2 The rule family is stated as a space ("each has the form set out below … same in every extract"), never as the instance (18b5d99f legacy_notes.md:3-48). Would fix V0-2..V0-8 (single-sentence rule) and CR-1 (trap spelled).
- LA3 Hidden-tier behaviour appears only inside a what-if counterfactual, which Opus computes once and does not generalise (3f39299a instruction what-ifs). Would fix ESC/EXT (explains trap).
- LA4 Worked examples on invented toy cases only, never on shipped records (b42c61b9 handbook H1.5/H10.3/H12). This is LV3, KNOWN. Would fix CR-2 / REV (decoy refuted on the same page).
- LA5 A hard core next to a cheap rule pulls verification effort away (6d12f970). There is no LEAK_LIBRARY row; the closest is "two-file read pointed together", inverted.
- LA6 Decoys refuted collectively by one authority sentence (b42c61b9 handbook:3-11) or by a "governs" sentence (3f39299a source_authority.md). KNOWN LV6.

## 6. Differences from LEVER_RULES_v2
- **Rule statement.** Ours: every graded rule is a plain sentence (§2, IN-15). Theirs: 18b5d99f states the space and not the instance; 3f39299a states nothing (TRUTH "Known hard edges": "instruction.md and the documents never say that settings may change"); 6d12f970 has a definition with an implicit redefinition.
- **Independent levers.** Ours: G10, ≥3 independent levers each ≥25%. Theirs: one gate or one shared stage carries 85-95% (18b5d99f weak-card stage, 3f39299a finishing pass, b42c61b9 `_full_core`, 6d12f970 net).
- **Hidden share.** Ours: G3 ≥30%. Theirs: 77% (6d12f970), 92% (18b5d99f), 95% (3f39299a), 91% gated (b42c61b9); only 7c2e77a1 has 17%.
- **What-ifs.** Ours: J1 caps them at ≤6, w≤3. Theirs: 8-9 what-if/closing figures at w5 (18b5d99f R1-R8, 3f39299a R1-R8, 7c2e77a1 R1-R9). Opus answered all of them right in 18b5d99f and 3f39299a: the figures pay a strong agent, and the judge loss comes from negatives and process criteria.
- **Worked examples.** Ours: W6, no worked example where readings differ. b42c61b9 prints worked examples for hidden-only branches and still holds, because the examples are toy cases and the shipped data never fires the branch.
- **Not in our map:** the first-fit vs unique-fit lever; degenerate shipped instance as a design goal; a generator that renders the rule docs; per-corpus binary authorities (xlsx/PDF writers in the test file); grading lane ties by cost-equivalence instead of a tie-break.
- **Things we do that they do not:** we write ≥3 levers each with a sentence (a sentence gets transliterated, LEVER_RULES §0). Their hardest losses came from no sentence at all, or from a sentence about the space. They also do not use mutation tests per rule; their mutated corpora are whole-report.

## 7. Anti-patterns and artefacts
- 7c2e77a1: expected constants hard-coded from the oracle (bisect over inverted rate windows). This contradicts the stated containment rule (conform_contract.md:63; format_notes.md:75 "Windows for one key do not overlap") and the test's own `_truth` linear scan. It costs 46 test pts plus about 20 judge pts. No QC report was found.
- 6d12f970: the run was regraded with an older judge.toml (different R11-R13 names, R8-R13/R16-R22 weights): version skew on the judge half only.
- b42c61b9: the test cache was thread-unsafe under rewardkit's 8 parallel checks (oracle 9/67 before the fix, QC :35-46). The run's 91 s verifier time fits the fixed file (INFERRED).
- In all 5, ctrf carries no failure messages, so root causes for 7c2e77a1 held-out (11) and b42c61b9 (61) cannot be pinned statically.
- stacking_check.py is blind to `_pass(_all(...))` indirection (6d12f970) and to `_full_core` / `_finish` coupling (b42c61b9, 3f39299a). Its isolated/duplicate hints were wrong.
- 3f39299a: a decoy document asserts the opposite of the hidden rule ("do not change during a season"), so the hidden rule reads as a contradiction rather than a lever.

## 8. Open questions for the master
1. Do we adopt "state the space, not the instance" (18b5d99f rule families + uniqueness proof) as the sanctioned way to withhold a rule under IN-16/IN-15? It held 92% hidden loss and passed QC with 3 warns.
2. Is a degenerate shipped instance acceptable for our cores given §0b ("branch never firing on shipped data never counts")? 18b5d99f and b42c61b9 state the general rule, so it is stated rather than determinate. Does that satisfy us?
3. Should the uniqueness requirement ("exactly one candidate reproduces the evidence") be stated in our contracts, or left as a property only the hidden corpora and the judge enforce?
4. 3f39299a passed QC with an unstated rule as a WARN. Do we treat that ruling as precedent, or keep IN-15 strict?
5. Can ctrf messages be obtained for 7c2e77a1 and b42c61b9 (one grader run with assertion text) to pin the 72 unexplained points?

## Lessons for the master
1. Make the shipped instance degenerate for the core (full rank, single fit, small arity) and put most test weight on generated corpora where the core must search. State the general space, not the instance.
2. Add a "unique-fit, not first-fit" lever: the reference requires exactly one candidate; the hidden corpora contain near-degenerate evidence; judge T1/T2 mirror it as program properties.
3. Make judge criteria target the verification Opus skips: constructed-input runs (T3), worked-example runs (T4), and coverage/count honesty negatives (T5/T6). Drop figure-only criteria, which Opus answers right.
4. Let the generator render the rule documents per hidden corpus (and the binary authorities, if any), so every mutated rule stays stated (TS-19 by construction).
5. Revisit G10 and G3. Peers win with one shared core gated by an exact-bar sentence and 77-95% hidden share, at the cost of a reward cliff. Allow it when the gated core is stated.
6. Never hard-code shipped expected values from the oracle alone. Assert at build time that a second reference agrees on the shipped data, and give every malformed row a stated outcome.
7. Place a cheap stateful rule next to the hard core only with one settling sentence. Silent redefinition of a defined term lost 94 pts here, but it is an IN-16 exposure we should not copy.
