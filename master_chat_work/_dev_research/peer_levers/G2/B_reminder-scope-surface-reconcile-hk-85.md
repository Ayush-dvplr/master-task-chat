# B: reminder-scope-surface-reconcile-hk-85 (PARTLY; 73.23 / 90.53 / 55.93)

TASK = `.../Abdus Samad Ali/reminder-scope-surface-reconcile-hk-85/`, RUN = `TASK/trajectories/claude-opus-5/run_1/`, TOP = `TASK/tests/test_output.py`, POL = `TASK/environment/data/scope_authority_policy.md`.

## 1. Inventory
- **Domain:** a change ledger for a release train, a stale derived snapshot, and a root-cause account. **Archetype:** multi-artefact incident reconciliation (9 JSON artefacts) plus a standalone stdlib reproducer program, `reproduce_scopes.py --input --out`, that has to work on any evidence directory.
- **Files the agent sees:** the policy (16 KB, 316 lines) and a superseded v1 (165 lines). Ledger shards: csv, psv and ndjson with differing column order, 52 records (traj step 18 "ledger count 52"), plus an `archive/` decoy. A sqlite db holding `journal` and a decoy `journal_staging`. An xlsx with an `active_` sheet and `draft_` sheets. Two docx addenda. A catalogue json and a draft yaml (void). `calibration/` with 3 controls plus a psv of published outputs. Derived layers: snapshot, prev snapshot, household index, runtime state, gate report, compiler notes.
- **Instruction:** 1016 words (`wc -w`), 11 lines of dense prose. It delegates every rule to the policy ("the policy document governs", instruction L3).
- **Tests:** 35 in total, 31 positive (weight 95) and 4 negative (-5, -5, -3, -3). Each check is isolated (`_grade` L680 maps an exception to False for that check only). 46/95 (48%) grade the shipped-data artefacts. 49/95 (52%) run the agent's reproducer on **hidden regenerated inputs**: the generator embedded in TOP (L30 `LOGICAL` inputs, L442-510 variant builders) rebuilds the xlsx, sqlite, docx and ledger from constants and applies one mutation per variant. The expected values are an embedded `EXPECTED` dict (L28).
- **Judge:** 33 criteria in batched mode, reading the trajectory. The 59 positive points are R1-R19 at weight 1 and R20-R27 at weight 5. The negative criteria are R28-R33.
- **Reward split:** 50/50 tests and judge (`reward.toml` weights 0.5/95 and 0.5/59).

## 2. Rule map (graded rules; representative, with every failed rule included)
| rule | where stated | form | trap explained? | shipped data separates readings? |
|---|---|---|---|---|
| ledger = union of `shard_*` in every format, read by header | POL L11-16 | one sentence plus a definition | partly ("column order differs between shards") | yes (3 formats, different column orders) |
| a re-exported seq: the last-sorting shard wins | POL L18-19 | one plain sentence | no | no (the shipped ledger has 52 distinct seqs, traj step 18) |
| BOM is not content; header whitespace stripped | POL L20-22 | one plain sentence | yes (named) | no |
| journal = table `journal`, ordered by `line_no`; `journal_staging` excluded | POL L40-43 | definition plus an exclusion | decoy named | yes (staging table present) |
| restricted map = the `active_` sheet, columns by header name; `draft_` sheets resolve nothing | POL L45-47 | definition plus a decoy | decoy named | yes (3 sheets) |
| **xlsx shared strings with phonetic `rPh` runs: main text only** | **nowhere.** Covered only by "columns are read by their header names" (POL L46) and instruction L9: "a directory holding a different ledger, journal, map or addendum must yield the values that evidence implies" | scope by omission; implied by the file-format standard (OOXML) | no | no (0 rPh in shipped sharedStrings) |
| **xlsx relationship Target may be an absolute part name** | nowhere (same two sentences) | scope by omission; implied by the format standard | no | no (shipped Target is relative) |
| **journal column names may be in another letter case** | POL L41 names the column `line_no`. SQLite identifiers are case-insensitive, so `ORDER BY line_no` works on `Line_No` | implied by the engine's semantics | no | no (shipped schema is lower case) |
| parameter recovery: window 2-30, weights 1-99, fits every control, tie rule largest window then breaking > additive > internal, window from retired lists only, weights from totals only | POL L215-223 | definition plus a tie rule, in one paragraph | no | partly (3 controls; the hidden `params_wide` variant L496 makes the tie rule bite) |
| addenda override the policy; higher-numbered addendum wins; v1 binds nothing | POL L28-35 | default plus exception | named | yes (A1 vs A2) |

## 3. Lever table (failed checks and criteria)
| id | w | rule | agent's reading (evidence) | correct reading | mechanism | self-test on shipped data catches it? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| reproducer_variant_workbook_phonetic_runs | 3 | the shared-string text is the main `<t>` only | `"".join(node.text for node in item.iter(t))` (agent `reproduce_scopes.py` L133-135), which concatenates every descendant `<t>`, the phonetic reading included | read `si/t` plus `si/r/t`, skipping `rPh` | **legal-but-unseen encoding:** the format allows a variant the shipped file never uses. The agent's generic "join all text" is right on every shipped byte | N: shipped sharedStrings has no rPh | NO. Only implied by OOXML plus "a different map must yield the values that evidence implies". Treat as HIDDEN-ish (RISKY) | NEW: format-spec robustness |
| reproducer_variant_absolute_workbook_targets | 3 | resolve rels Target relative to `xl/` or absolute from the package root | the agent anticipated it and got it wrong: `target = "xl/" + target.lstrip("/")` (L144-145) makes `xl/xl/...` | an absolute target is taken as-is without the leading `/` | same as above; also an **untested defensive branch**: code written for a case the agent never exercised | N: shipped Target is relative, so the branch never ran | NO (format standard only). RISKY | NEW: format-spec robustness |
| reproducer_variant_journal_column_case | 3 | read `journal` by column name | `SELECT *`, then a dict keyed by `cursor.description`, then `row["line_no"]` (L109-114) | name the columns in SQL (case-insensitive in SQLite) or fold the case | **engine semantics vs host-language semantics:** SQLite treats the name case-insensitively and a Python dict does not | N: the shipped schema matches the expected case | partly: the column name is stated and its case-insensitivity is a property of SQLite. RISKY | NEW: format-spec robustness |
| judge R19 | 1 | trajectory shows control_01 fits windows 3-9 and control_02 narrows to 6 | agent ran recovery inside the program with no per-control print (traj steps 17-19) | n/a | unstated outcome | n/a | NO. HIDDEN RULE | n/a |
| judge R20, R24, R25, R26 | 5 each | specific verification procedures for parameter recovery: regenerate published controls from chosen parameters, replay control_03 alone, build your own control, list every fitting candidate before the tie | the agent's self-tests were a minimal evidence dir (step 28), A1-only (step 29) and a ledger mutation (step 30) | n/a | **process criteria at weight 5 for verification habits the instruction never asks for** | n/a | NO. Conduct, odds-raising at w5 (= minor under JD-15) | n/a |
| judge R23 | 5 | the response/trajectory reports candidate counts per control | not done | n/a | unstated reporting item | n/a | NO. HIDDEN RULE (outcome with no contract sentence) | n/a |

## 4. Contrast: what passed and why it was easy
- **Every rule stated as one sentence with its exception named passed:** BOM, the re-export winner, `journal_staging` excluded, `draft_` sheets, addendum precedence, the v1 decoy, header whitespace, catalogue class names vs ranks (`catalogue_names` w5 passed), the tie rule (`recovered_parameters` w5 passed). These match our DIAGNOSIS cause 4 exactly ("Each sentence named its own exception"): coded right on the first write. The hidden variants for these rules only repeated rules the agent had already coded, as in our CR-1..CR-5.
- **Shipped-data artefacts (46 points) all passed.** The data showed each rule firing (traj step 19 prints the inert reasons).
- Of the 15 variant checks, only the 3 that test an *unstated format property* failed. All 12 that test a *stated rule* on new data passed. This is the clearest evidence in the group that **hidden reseeded inputs alone do not create difficulty; what the variant exercises does.**

## 5. Agent behaviour
- Read order (traj): step 2 `find /app`; step 3 the whole policy via `cat`; step 4 both docx addenda; step 5 catalogue and fixtures; step 6 all shards; steps 7-8 the derived layers; step 9 sqlite (`select *`, printing column names); steps 10-11 the xlsx workbook.xml, rels, sharedStrings and sheet2; step 12 calibration; step 13 the digest fixture check. It read every spec file in full before writing code.
- Plan: no explicit plan message. It wrote the whole reproducer in one go (step 14/16), ran it (step 17) and inspected the internals (steps 18-19).
- Self-tests: step 28 a minimal evidence directory; step 29 drop A2 (A1-only window 3); step 30 mutate a ledger value. **None mutated a file format** (no xlsx or sqlite structural variant), so none could hit the 3 failing cases.
- 37 steps, about 11 min wall time (result.json). Final message (step 36) claims full success. Reality: 3 reproducer variants crash or give wrong values. It never noticed and never gave up; it simply never tested those cases.

## 6. Test design
- Expected values: an embedded `EXPECTED` dict (TOP L28). Variant inputs are rebuilt at test time by an in-file generator from `LOGICAL` constants (L30, L442-510), so they are hidden and deterministic.
- Partial credit: each variant grades only its own `VARIANT_FIELDS` (L630-660, L664-668), so one bug does not cascade.
- Negatives: hard-coded sample answers (a ledger changed but the shipped digest returned, L897), reading outside `--input` (planted directory, L907), nondeterminism (L935), control digest == surface digest (L949). None fired.
- Anti-cheat: agent code runs unprivileged, /tests is closed (`chmod -R go-rwx /tests`), the program is copied to a fresh dir, and `python -E -s -S` stops the environment and site injection.
- Shipped-data-only weight: 46/95 = 48%.

## 7. Judge design
- Failed: R19, R20, R23, R24, R25, R26 (26/59). Every one is a parameter-recovery **process** item, and no sentence in the instruction or policy asks for it (JD-15: outcome items R19 and R23 have no contract sentence, so they FAIL; conduct items R20, R24, R25 and R26 are odds-raising at weight 5, so they are minor).
- A reusable pattern (safe form): "The agent changes one calibration control on a scratch copy ... reruns parameter recovery, and shows that the recovered window or weights move" (R22, w5, passed). This is a falsification-style verification that holds for every competent route; at weight 1 or 3 it is clean.
- JD-18: R-list has no explicit code-quality criterion among those I printed (INFERRED; I did not read all 33 descriptions).
- AL-28: tests `negative_hardcoded_sample_answers` (-5) and judge R28 (-5, "adopts a value from the generated export snapshot") are different acts. No stacking found.

## 8. QC safety of the levers that worked
| lever | IN-15 / TS-19 | TS-16 | TS-20 | AL-28 | verdict |
|---|---|---|---|---|---|
| format-spec robustness variants (phonetic run, absolute target, column case) | the graded behaviour "read the map / journal correctly from any valid file" is stated (instruction L9 plus POL L41, L46), but the specific encodings are not. A strict TS-19 reviewer could say "undocumented edge case" | n/a | 3 each = key edge case, fine | n/a | **RISKY.** It becomes SAFE if the spec has one sentence such as "the workbook is any valid OOXML package; read it as the format defines" plus the variant as a hidden test. Do not name the specific encodings. |
| conduct process criteria at w5 | JD-15 conduct needs no sentence, but w5 on an odds-raising route is minor; outcome-type ones (R19, R23) fail | n/a | n/a | n/a | **NOT ALLOWED** as written; allowed at w1-3 if phrased as verification any competent route does |

## 9. Writing style (technique, not content)
1. POL L18-19 "A record sequence may be re-exported in more than one shard; the copy in the shard whose file name sorts last governs": a **modal possibility ("may") with no instance in the shipped data**. The rule is stated, but nothing on disk makes the agent see it fire. (The agent still coded it; for a single-sentence rule this was not enough.)
2. POL L45-46 "its columns are read by their header names": a **general reading principle instead of an enumerated list of quirks.** It covers future variants without naming them. This is the sentence that makes the robustness variants defensible.
3. Instruction L9 "a directory holding a different ledger, journal, map or addendum must yield the values that evidence implies": a **generalisation promise** that licenses hidden structural variants.
4. POL L220-223 tie rule "the largest window and, separately, the largest `breaking` weight, then ..." plus "The window is settled by the retired lists alone and the weights by the grand totals alone": **two independent orderings packed into one sentence with "separately".** The agent still got it right, so this alone is not a lever.
