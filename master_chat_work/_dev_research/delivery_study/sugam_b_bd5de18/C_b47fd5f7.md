# C card: b47fd5f7 (crafting-season settlement)

Paths: T = `tests/test_output.py`, I = `instruction.md`, D = `environment/data/`, R = `trajectories/claude-opus-5/run_1/`. Repo HEAD 2dfb1f8f. Test version check: graded test names and weight 0.5/58 match the repo file, and there is no data drift (see A_b47fd5f7 and the drift check in LOG 11:18).

## 1 Scores and verdict
- Recorded 59.91 overall, 94.83 tests, 25.0 rubric (`pass_summary.json`, `report.json`). Harness judge score 3/12.
- Verdict **GENUINE**. One positive check failed (3 of 58 points): `test_quiet_rules_findings_and_funding`, with stdout "quiet_rules: data_quality.json differs from the settled season". The other 6 "failed" ctrf entries are negatives that did not fire, which is the good outcome.
- Rubric loss is about conduct (J2/J9 shape). R1-R3 ask whether the agent built targeted seasons, and it did not. The code-quality criterion R4 passed.

## 2 Inventory
- Domain: game-economy ledger settlement. Archetype: a rulebook corpus with withheld parameters that are recovered from worked rulings, plus a reusable program that is graded on reseeded hidden seasons.
- Files the agent sees (D, bytes): 7 rulebooks (`rulebook_admission/charge/editions/identity/requisitions/salvage/scarcity.md`, 1.5-2.7 KB each, numbered rules A1-A7, V1-V9, S1-S6, E1-E5…), `invariants.md` 3100 (N1-N9), `finding_codes.md` 2406, `record_shapes.md` 5134, `convention_register.md` 4074, `council_rulings.json` 933, `clerks_digest.md` 755 (a decoy shorthand), `season_charter.json` 392, `crafting_ledger.csv` 13725 (310 rows: 221 forge, 89 salvage), `recipe_editions.csv` 2696 (97 rows), `reagent_acquisitions.csv` 1790, `artifact_catalogue.csv` 448, `smith_identity_events.csv` 404, `workshop_registry.csv` 303, `reagent_registry.csv` 258, `requisitions.json` 705, `vault_opening.csv` 137, `patch_calendar.csv` 128.
- Instruction: 2894 B, 429 words, 13 lines.
- Tests: 24 checks, positive 58, negatives -10. Structure 5×1, whole-document 7×5, single-rule 4×3, mutation 2×3 (`stacking_check.py`; registrations T:3572-3595).
- Judge: 8 criteria, batched, positive 12, negative -10 (R1-R3 conduct 3 each, R4 code quality 3; R5 -1, R6-R8 -3).
- Reward split: test_output 1/116 per point (0.5/58), judge 1/24 (0.5/12), so 50/50.

## 3 Test architecture
- **Expected-value production:** an embedded independent reference `settle` at T:636-930. It is a fixpoint iterated from 0 and from the ceiling, and both runs must agree (T:911-925). It runs on seasons from an embedded deterministic generator (PRNG T:35; "withheld parameter axes" T:65; corpus model T:129). Rulebooks, register, invariants and record shapes are embedded byte for byte (T:1464-2210), so the reference never reads the agent's copy.
- **Hidden vs shipped:** SEASONS T:2949-2961. `forge_a..d` are four hidden reseeded seasons per whole-document check. There are single-rule seasons (`iso_unit_charge`, `iso_cap_release`, `iso_live_window`, `quiet_rules`) and charter-constant mutations (`mut_family`, `mut_grade`). No check grades the shipped season's figures directly, so all 53 value points are on hidden inputs (G3 is far beyond 30%).
- **Isolated vs whole-doc:** `_whole_share` T:3345-3363 gives one check per downstream document. Comment T:3340-3342: "a document earns its check only when it matches in every season". Each whole check asserts only its own document (G2), so a slip in data_quality cannot zero allocation.
- **Partial credit:** none inside a check. Each check is exact whole-document. The instruction states this, I:11: "A record counts only when it matches the settled season exactly. Each output document is graded whole on fresh inputs." (G5, CL-4 exemption).
- **Negatives / anti-cheat:** hardcoded answers T:3190 (-3), filename-dependent behaviour T:3204 (-1), reads training corpus T:3220 (-1), rebinds verifier deps T:3269 (-3), third-party import T:3281 (-1), network T:3317 (-1). The program runs as an unprivileged user in its own process group (T:2211-2214) with a 38 s limit (T:2968, as stated at I:7).
- **Mutation tests:** 2 (`_moves_only_charge`). Charter constants change, and only the charge document should move (G6).
- **Weight shares:** structure 5/58 = 9%, whole 35/58 = 60%, single-rule 12/58 = 21%, mutation 6/58 = 10%. This agrees with `stacking_check.py`.
- **Key functions:** `_check` T:3008 (records crash vs differ through `_note` T:2999); `_same` T:3076 (`json.dumps(sort_keys)`, type-exact); `_mut_nonapplying` T:2421-2433; `_trigger_quiet_rules` T:2436-2495 (docstring T:2437-2443: "other edits only set the scene and are not claimed as single-rule coverage").

## 4 Lever table (failed checks)
| id | w | rule graded | rule locations (quote) | sentence form | agent's reading | correct reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| quiet_rules_findings_and_funding | 3 | a salvage naming a forge absent from the ledger carries only `MISSING_FORGE_REF` | D/invariants.md:23-35 N3 "carries a finding for each of those four that holds of it and for nothing else"; D/rulebook_editions.md:26-27 E3 "A salvage entry is governed by the edition in force on the day of the forge entry it salvages."; :31-34 E4 "An entry that names an artifact absent from the artifact catalogue resolves to no edition. An entry whose governing day falls outside every patch in the calendar resolves to no edition."; D/finding_codes.md:46 UNRESOLVED_EDITION detail "the artifact the entry named"; trigger T:2432 `salv[0]["forge_ref"] = "E99999"`; reference T:680-687 (missing forge → one finding, `continue`) | implied by a definition (E4 is a closed two-cause list) plus scope by omission (E3 says nothing about the case where the forge does not exist) | traj step #81: "A salvage naming a forge the ledger does not hold has no governing day, so it carries `MISSING_FORGE_REF` *and* `UNRESOLVED_EDITION`." Agent `settle_vault.py:591-609`; gov_day None → `edition_for` None (:259-260) | E4 is exhaustive: no governing day is not "outside every patch", so the edition finding does not hold | the shipped ledger has no missing-forge salvage (step #13 t+7.0 "missing refs: []"). The agent never built a season with one (judge R1-R3 = 0) | partly. Both readings fit the text, so this is a two-readings case (IN-16 risk) and close to a HIDDEN RULE | NEW: closed-list definition where "absent input" falls between two clauses (close to L6) |

(Sole cause INFERRED from code reading. The other quiet_rules edits — admission edges, STOCK_FLOOR detail, same-day acquisition, strict-before window, identity — were checked against the agent's code as equivalent; see A_b47fd5f7.)

## 5 How the tests handle QC
- **TS-13** (one property per check): each whole check is one document across 4 seasons. Single-rule checks pair a finding with its funding effect ("findings_and_funding"), a bundled `and` (MINOR shape, vendor v1:69). `stacking_check.py` flagged `structure_canonical_serialisation` with 4 asserts.
- **TS-16** (narrow negative trigger): each negative names one act, e.g. reads training corpus T:3220 and filename-dependent behaviour T:3204. The weights are small (-1 to -3).
- **TS-19** (learnable): the hidden seasons stay inside I:7's stated bounds ("up to 48 requisitions", 38 s on 2 CPUs). The withheld conventions are learnable because I:5 points to the register and D/convention_register.md:73-75 says the rulings "agree with exactly one draw". The quiet_rules lever is the risky spot (above).
- **TS-20** (5/3/1 weights): whole document 5 (core), single rule 3 (sub-goal), structure 1 (T:3572-3592). Matches 03_Tests_QC.md:51.
- **TS-26** (double payment): each document is graded once. Single-rule seasons grade only the moved facts (docstring T:2437-2443), so this passed.
- **IN-15**: the negatives match I:13 (rules of engagement) and I:7 (filename independence, missing-file exit).
- **IN-16**: E4's closed list vs a missing forge. Two readings stayed in. Compare QC_RULINGS IN-16 FAIL "emberforge v1:34". This task family has already been failed on IN-16 once, so this case is RISKY even though it passed.
- **AL-28**: no single act is priced above -5 across layers. Hardcoding is -3 in tests plus judge R8 (reads grader files -3), and these are different acts.
- **CL-4**: amplification is limited by per-document grading and the instruction's I:11 exactness statement (Final_checklist.md:491: "An instruction that states out loud that only an exact match counts has set that bar deliberately").
- **JD-7**: R4 code quality must be met by the oracle. Not checked (no execution allowed); INFERRED to be met because QC passed.

## 6 Leak avoidance
| quote | W |
|---|---|
| I:5 "Some conventions the council draws for a season are written down nowhere in the rulebooks. The register says what the council may draw and how the draw that governs a season is fixed." | W1: says *that* parameters are withheld, never which value |
| D/convention_register.md:73 "A ruling is not a figure of the season it is published with." | W7: honest control. Worked cases cannot be copied as answers |
| I:3 "where any other note … says less or says otherwise, they govern." with D/clerks_digest.md:10-12 "one of the three most recent forges" vs D/rulebook_salvage.md:15-16 "three live forge entries … strictly before the salvage's own day" | W2/W3: the decoy is refuted by one global precedence clause in the instruction, not beside the decoy line |
| D/invariants.md:23-35 N3 "for each of those four that holds of it and for nothing else" | W3: a clause inside an enumeration |
| D/rulebook_editions.md:31-34 E4 two plain causes | W3: definition with branches |
- **Shipped data does not separate readings** for the quiet_rules lever (no missing forge). The separating case exists only in hidden seasons (W5).
- No visible tests or examples beyond the rulings, which are single reductions and never season figures (W6).
- Neutral naming: entry ids `E…`, `L…`; the trigger uses `E99999`.
- Rule placement: rules are numbered in 7 rulebook files plus an invariants file, so a composition spans many files (L4).
- LEAK_LIBRARY comparison: avoids CR-2 (the decoy is resolved in the instruction, not two paragraphs later beside use) and V0-1/REJ (the rulebooks *are* numbered, but each rule is a definition, not a procedure step). The risk is ENC (self-testable). The rulings let the agent brute-force the one draw (agent: 840 draws → 1, t+14-16).

## 7 Agent behaviour
- Read order: everything in D at t+0.1-0.6 min. Convention probe at t+0.8. Ledger referential checks at t+7.0 ("missing refs: []").
- First full program at t+13.0 (1331 lines), run at once.
- Graded logic was not changed after the first program. Minutes 16-62 rewrote only the allocation (MaxFlow) and checked it by brute force (0 mismatches).
- Self-tests: brute-force of all convention combinations (distinct outcomes 1), a random index check, determinism, a missing-file exit, a 24-requisition stress test. None used an input outside shipped shapes (no missing forge, no out-of-calendar day).
- Where it went wrong: step #81's assertion of the double finding.
- Final claim at t+103: "The season is settled", with a readings list. The claim holds on the shipped season; it is wrong on one hidden rule (3 points).

## 8 Passed checks
- All 7 whole-document checks over 4 hidden seasons passed: withheld-draw recovery, identity, windows, caps, scarcity and allocation. These were easy for Opus because every rule is a plain numbered sentence and the rulings pin the draw uniquely, so a careful literal transliteration is correct.
- Single-rule checks unit_charge, cap_release and live_window, and both mutations, passed. The rule text is stated plainly and the agent read every file.
- Structure 5/5.

## 9 Take-aways
- SAFE: put the withheld parameters in a register of candidates plus worked single-reduction rulings that fix one draw. This is learnable, not copyable, and QC passed it.
- SAFE: grade each document whole on several reseeded seasons, with one check per document and exactness stated in the instruction. Amplification is bounded and CL-4 passes.
- SAFE: a decoy summary note, overruled by one global precedence sentence in the instruction.
- RISKY: a closed-list definition where an absent input arguably fits a listed clause. This is a two-readings case (IN-16 was failed before in this family).
- AVOID: relying on this lever shape for points. It cost only 3/58, because Opus reads closed lists literally and mostly right.
