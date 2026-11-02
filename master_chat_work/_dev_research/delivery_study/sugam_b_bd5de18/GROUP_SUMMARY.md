# GROUP_SUMMARY: sugam_b (bd5de18)

Repo HEAD `2dfb1f8f7b86db305b1f6afa63279873e6e918e4`. The per-task evidence is in `A_<task>.md` and `C_<task>.md`. This study was read-only: nothing in the tasks was executed, and only `stacking_check.py` was run.

## 1 Table
| task | verdict | overall / tests / rubric | genuine test pts lost | main lever shape |
|---|---|---|---|---|
| ae640566 (observatory metrology) | ARTEFACT (INFERRED) | 59.59 / 34.97 / 84.21 | n/a | The task was revised after the run: 5 graded test names are missing from the repo (0.5/143 vs 0.5/135). The agent-seen contract said "Only records surviving all earlier non-standing rules occupy positions"; the repo `contract.md:140-143` now says the opposite. The agent followed its own text |
| af6f42c3 (policy compiler) | PARTLY | 69.5 / 45.83 / 93.18 | 26 value (+10 mixed; 16 gate) | Scope by omission: the env filter exists only in the profile paragraph, and the spine reference replays base only (`T:408,425` vs contract `:14-27`). The error cascades through the announced coupled bound (`I:11`). There is also an unstated key-vocabulary gate (`T:554-558`) |
| b47fd5f7 (season settlement) | GENUINE | 59.91 / 94.83 / 25.0 | 3 | A closed-list definition (E4, two causes) where a missing forge arguably fits. Loss is mostly rubric (conduct criteria) |
| ceab1cf6 (CLI repair) | GENUINE | 65.47 / 50.0 / 80.95 | 36 (+2 gate) | An ordering property that leaves the operand open (`I:5` "applies the scale before granularity"), costing 31 points over 9 checks. A data rule element whose shipped instance is a no-op (`width_even.html2:107`) cost 5 |
| d22ff871 (aquifer billing) | ARTEFACT (INFERRED) | 32.36 / 25.93 / 38.78 | n/a | Graded with a superseded test file (28 ctrf names, 0.5/81 vs repo 0.5/86). All 13 rerun checks failed, including rules that passed statically (likely the program was unreadable by `nobody`). The agent-seen schema steps 4-5 were ambiguous and were reworded later |

## 2 Test-design patterns (ranked by genuine points lost)
| # | pattern | SAFE/RISKY | mechanism | grading | QC pass | tasks |
|---|---|---|---|---|---|---|
| P1 | Operand-open ordering property: "X before Y" without naming which value X acts on | RISKY (two readings, IN-16) | Opus applies the order to the value it already holds (the finished field) and believes it complied | one fact repeated over shipped + 3 held corpora + views = 9 checks, 31 pts | passed | ceab1cf6 |
| P2 | Filter stated only in a sibling paragraph (scope by omission); the literal general paragraph has no filter | RISKY (literal text favours the agent = hidden rule) | Opus transliterates the general paragraph it reads first. Sibling outputs still match because later replays overwrite the difference | 1 wrong scalar feeds an announced coupled bound and moves every corpus, 26-36 pts | passed | af6f42c3 |
| P3 | Data rule element whose shipped instance is a no-op, inside a decoy-dense file | SAFE | Opus reads big files by partial `head` and keys on the rows it sees. The separating case exists only in a held corpus | 1 held check, 5 pts | passed | ceab1cf6 |
| P4 | Closed-list definition where an absent input arguably fits one listed clause | RISKY (IN-16, already failed once in this family) | Opus reasons "no X, so clause 2 holds" | 1 single-rule hidden season, 3 pts | passed | b47fd5f7 |
| P5 | Per-document whole grading on several reseeded hidden seasons + exactness stated in the instruction | SAFE (CL-4 exemption, G2/G5) | one check per document; a miss costs that document only | 7×5 whole, 4×3 single-rule, 2×3 mutation | passed | b47fd5f7 |
| P6 | Mirror views graded for consistency with the agent's own primary artifact, not the reference | SAFE in principle, RISKY in practice | avoids cascade double-pay, but an unstated key-set gate zeroed 13 pts | 7 view checks | passed | af6f42c3 |
| P7 | Hidden corpora that reorder decoys ahead of canonical rows and swap the base config | SAFE | beats first-row reads and shipped-number copying | 6×5 held checks (39%) | passed | ceab1cf6 |

## 3 Leak-avoidance patterns
| pattern | evidence | LEAK_LIBRARY row it would fix |
|---|---|---|
| Say *that* something is withheld or decoyed, never which value or row | b47 `I:5` "written down nowhere in the rulebooks"; ceab `I:1` "carry decoy rows" | ESC/EXT (explains trap); common cause "trap spelled out" |
| Worked cases declared not to be figures of the shipped season, so controls cannot be copied | b47 `convention_register.md:73`; ceab `sample_config_*.json:3` "context only - do not copy" | common cause "shipped boundary rows let agent watch rule fire"; RUN (shipped separating stream) |
| A decoy summary note overruled by one global precedence sentence in the instruction, not beside the decoy | b47 `I:3` "where any other note … says less or says otherwise, they govern" vs `clerks_digest.md:10-12` | CR-2 (decoy resolved two paragraphs later), REV (decoy refuted on same line) |
| Announce the coupling, not the trap | af `I:11` "a misclassified journal op moves the effective bound of every corpus" | ENC (self-testable). The coupling claim gives no reading of the misclassification itself |
| Separating rows exist only in hidden or held inputs; shipped instances are no-ops | ceab width (band 0 already even); b47 no missing-forge salvage shipped | common cause "shipped boundary rows let agent watch rule fire" |

## 4 Differences vs our LEVER_RULES
- **Section 0 confirmed:** in all 5 trajectories Opus read every spec in the first minute and wrote one full program at 3.8-13 min (d22 t+3.8, ae t+8.4, ceab t+8.4, af t+12.0, b47 t+13.0). Graded logic was never changed afterwards. Its self-tests were on its own claims or invariants (af `verify.py`, ceab `genalt.py` run-and-differ, b47 brute force on shipped data).
- **Line 43 nuance (NEW):** Opus does not only key on the field named per line. In ceab it kept the *operand of the shipped bug* while fixing its order, so in repair tasks the defect's operand survives the fix. Candidate rule: "an ordering property whose operand is carried by the defective code".
- **W5 vs a hidden rule:** our map says separating cases hidden-only. Peers do this (P3/P4), but their two biggest wins (P1, P2) are levers where the visible text supports the agent's reading too. That is a HIDDEN RULE by our standard, and our map lists "ambiguous fallback scope" under "Never used". QC passed both here, so this is evidence that QC tolerates them, not evidence that they are safe.
- **G1 coupling:** peers price one lever across many checks through repetition across corpora (ceab 9 checks) or through an announced coupled bound (af). Our G1 uses owned-row coupling. Theirs is cheaper to build but carries TS-26 double-pay exposure.
- **G3:** af6f42c3 has 0% hidden-input grading yet passed QC; ceab is 39%; b47 is 91%. Our ≥30% rule is stricter than what QC enforces.
- **G9:** ceab hardcodes expected constants with a comment "Independently derived", where we embed a reference. QC accepted it.

## 5 Anti-patterns / artefacts
- **Repo ≠ graded run (2 of 5).** ae640566 and d22ff871 were revised after the graded run (tests, and contract/schema text). Recorded scores therefore describe a task version that no longer exists. Always diff ctrf names and the per-point weight against the repo test file before attributing a lever.
- **Program unreadable by the unprivileged runner** (d22, INFERRED). The current file adds `_grant_read` for 0600 editor files (`T:511-516`), which suggests the graded version lacked it (TS-19 vendor v1:36 shape).
- **Checks stricter than the output contract** (ceab transcript replay `T:1038-1081` vs `output_contract.md:54-57`; provenance `child.text`). There are also **unstated key vocabulary and value types** (af `T:554-558`, `T:664-665`). These are cheap points lost to format, not rules.
- **Two scoring channels:** the harness `reward.json` (judge in-harness) differs from the recorded `report.json` (offline re-judge) for d22 (50.96 vs 32.36). Test percentages agree.

## 6 Open questions
- ae640566: the second wrong fact in policy_audit under the graded version cannot be pinned without the graded test file.
- d22ff871: the cause of the 17 static money points is unresolved. The agent's money chain equals the *current* reference by reading. Did the graded reference use the old ambiguous steps 4-5?
- af6f42c3: the split of the 10 "mixed" points between value and gate is INFERRED.
- Did QC see P1/P2 as two-readings cases and accept them, or not notice? No QC report is in any folder.

## Lessons for the master
1. Before analysing any delivered task, diff graded ctrf names and per-point weight against the repo test file: 2/5 here were revised after grading.
2. The biggest peer wins came from an under-specified operand or scope (P1, P2). QC passed them, but they are hidden rules; prefer P3-style no-op shipped instances with held separating cases.
3. Bound amplification per document on reseeded hidden seasons and state exactness in the instruction (P5); avoid paying one fact across 9 checks.
4. Never gate a whole view family on an unstated key vocabulary, value type or format stricter than the contract.
5. Repair tasks: Opus keeps the defective code's operand while fixing the order, which is a lever worth naming in LEVER_RULES.
