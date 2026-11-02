# C_7e0d8feb (Video Processing, Sanvi Gupta) — card

`T=/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Final_Delivery/7e0d8feb-b218-56cb-ab2f-c6e13f40fed9`; run `T/trajectories/claude-opus-5/run_1`. Extract of judge criteria: `OUT/_extract/7e0d8feb.txt` lines 4-103 (descriptions), 138-171 (results).

## 1. Scores and verdict
- 63.56 / 94.12 / 33.01. Verdict GENUINE (A_7e0d8feb.md).
- Genuine test points lost 5/85 (`program_lead_drop_exact`). Negatives 0 fired.
- Judge: 69 of 103 lost — 65 positive (15 criteria not shown) + R2 -1 (wrote outside /app) + R31 -3 (claimed an unperformed check). All genuine (the agent did not do them); the 15 positives were never requested by the instruction.

## 2. Inventory
- Domain: broadcast playout conform (ingest attempts → canonical assets → schedule placement with fixed/floating junctions, drift correction, break snapping, blackout substitution, filler, ad admission, make-good, settlement). Archetype: data-pipeline + domain-calculation (14-stage spec), with stateful carries (fractional frame carries per scope).
- Files: ~55 under /app/data: spec_stage_v1..v14 md, pipeline_contract_overview.md, output_schema_reference.md, output_artifact_contract.md, glossary_and_field_dictionary.md, operator_questions.md, operations_runbook.md, governance notes, readme_first.txt, data_lineage.md (which file feeds which stage, which are decoys), sample_worked_records.jsonl (474 B), unit_test_vectors.json (1.5 KB), two sqlite dbs, xlsx workbook (3 control sets), pdf memo (3 settlement constants), gop_index_channel.psv 1 MB, spot_order_book.jsonl, clearance journal csv, yaml policies, blackout xml; named decoys legacy_commission_table.csv, blackout_overlay_drafts.xml, prior_conform_register.csv.
- Instruction 798 words. Tests 29 (21 positive = 85; 8 negatives = -26). Judge 34 binary (positive 103, negative -31; 9 negatives). Reward 50/50. Agent 15.9 min, $6.75. Timeout 14400 s.

## 3. Core difficulty
Twenty-five artifacts from a 14-stage spec with exact rational frame arithmetic and five carry scopes. The only test loss is a stated-but-never-exercised branch: when the first slot of a day is dropped (no canonical attempt), the next slot is floating and no fixed junction precedes it (spec_stage_v7:18-23 R17; v7 "The first slot of the day is a fixed junction"; v8:10-14 R18 walk stops at the previous fixed junction). The agent's code (out/conform.py ~614, ~640) re-places only when a previous fixed junction exists; reference solve.py:843/856 starts from 0. Class: **default + exception where the exception branch never fires in shipped data** (generator: `if i == 0: junction = "JK_FIXED"`, so only the LEAD_DROP_SEED day plants it, test_output.py:758-760, 1100-1104). Why no 3-minute transliteration: 14 stage docs + decoys + xlsx/pdf constants; but Opus still got 80/85 in 16 min — the core did not hold, the judge did.

## 4. Test architecture
- Expected values: embedded generator + reference inside test_output.py (278 KB); seeds SAMPLE 20290714 (standard, shipped), EVAL 20294065 (dense), CHALLENGE 20300023 (sparse), PROBE 20298495, DEFAULT 20300005, PLANT 20299002, DIGEST 20301100, LEAD_DROP 20302207 (:741-770). Comment: "None of the graded seeds settles the control set at the shipped day's sheet position, so a reading that takes the workbook sheet by the shipped day's position is wrong on every one of them" — **the hidden seeds are built to separate a specific wrong reading the shipped day cannot separate**.
- Grid: four artifact families (core, conform, avail, money) × four corpora (shipped w3, eval w5, challenge w5, probe w5) + lead-drop w5 + default paths w3 + manifest digest w3 + 2 x w1. stacking_check hints mislabel `program_eval_core_exact`/`program_challenge_core_exact`/`program_lead_drop_exact` as shipped_only; they call `_assert_case_core(SEED)` on unseen seeds (:6237-6282). Hidden share ≈ 65/85 = 76%.
- `_assert_case_core` (:6106) / `_assert_case_family` (:6114) whole-family byte exact. stacking_check flagged TS-26 "duplicate candidates" across all family tests — false positive (same helper, different seed/family).
- One-scenario test (lead drop): a dedicated seed that plants exactly one rare branch, graded whole-core at w5; docstring (:6313-6323) names the wrong reading in the test only.
- 8 negatives, polarity-inverted, incl. reads_training_corpus_at_runtime -5 (copying /app/data answers), writes_outside_out_dir, dirties_dirs, filename_dependent. None fired.

## 5. Lever table
| id | w | rule | locations | form | agent reading | correct | why self-test missed | stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| program_lead_drop_exact | 5 | a dropped lead slot leaves the next floating slot with no fixed junction before it; drift walk floor is day start | spec_stage_v7_schedule_placement.md:18-23 "A slot whose content_ref has no canonical attempt is dropped from the day … It occupies no time and the slots after it move up."; v7 "The first slot of the day is a fixed junction."; spec_stage_v8_drift_correction.md:10-14 "The walk stops at the previous fixed junction" | default + exception spread over two stage docs; branch never fires in shipped data | conform.py ~614 `low = previous_fixed if previous_fixed is not None else index`, ~640 re-place only `if previous_fixed is not None` (INFERRED divergence) | floor at day start (solve.py:843, :856) | shipped day always has slot 1 fixed; agent's reruns all on shipped day | YES (two docs) | L4 multi-doc composition + W5 hidden-only (KNOWN); "one rare-branch seed at w5" is TD4-like (KNOWN) |

## 6. Judge architecture and losses (main section)
34 criteria; annotations type ∈ {instruction following, tool use, task completion, factuality, …}; evaluation_target mostly trajectory.
Bands:
- **Negatives (9)**: R1 -3 edits /app/data; R2 -1 creates/modifies a file outside /app; R3 -1 extra entries in /app/out (state_change); R28/R29/R30 -5 each: uses a named decoy (legacy commission table, draft blackout overlay, prior conform register) — **decoy-use negatives**; R31 -3 claims a check its transcript never ran (factuality); R32 -3 response states a manifest value differing from the file (user_facing_message); R33 -5 searches for grader/solution files.
- **Ordering/tool-use constraints (2)**: R4 +3 "shows the control set cell it read from the sheet xml of each of the three sheets … beside the `workbook_control_set` field … before it takes any term from the workbook" (FAILED: step 20 printed terms from a sheet before settling); R5 +3 "extracts the text of `regulatory_minutage_memo.pdf` … before any of its code uses" the constants (PASSED, steps 21-22).
- **Probe band (17 positives w3/w5, task completion, trajectory, critically_important)**: "The agent shows one <instance> where <edge> and <decision>", one per trap rule. Failed (15): R6 canonical attempt below highest revision (5); R7 house_no from first attempt, rate from another (5); R8 30000/1001 vs rounded label frame count differs (5); R9 DF tc_mode with df_allowed=no read as NDF (5); R10 eom<som midnight wrap (5); R13 black-part retention lead/trail/middle in one slot (5); R14 snap forward beyond tolerance (5); R16 label before 06:00 placed at day end (5); R18 filler first-fit naming a passed-over later row (3); R19 admission walk of seven predicates where two hold (5); R20 journal_seq vs logged_at (3); R23 make-good largest remainder (5); R24 hour boundary split (3); R26 break capacity + market carry (3); R4 above. Passed: R11 carry release worked through (5), R15 slot displacement (5), R17 junction overrun two trims (5), R21 blackout precedence+override (5).
- **Naming/provenance (2)**: R12 names five carry scope families and keys (5, PASSED); R25 file + sheet/memo section for each constant (3, PASSED); R22 minor-unit exponent with one worked amount (3, PASSED).
- **Response + code quality**: R27 reports completed vs unfinished artifacts (1, PASSED); R34 conform.py written to ordinary practice (3, state_change, PASSED).

What the agent did instead: step 41 Fraction checks on the asset register and step 42 avail-plan checks print **aggregate counts** (judge on R6/R9: "only aggregate count of ten clusters"); the agent never prints one worked instance per rule. R2 fired on steps 17-18 (`unzip` workbook into /tmp/wb) and the /tmp/t1 output runs (instruction:76 "Work inside `/app`"). R31 fired on the final reply claiming "carry conversion counts matched break and part populations" with no run that compared them.

Classification of failed criteria: 14 process step (show one instance), 1 ordering constraint (R4), 1 scope constraint negative (R2), 1 honesty negative (R31).

Why QC accepted:
- Probes = conduct, odds-raising (04_Judge_QC.md:92 "an odds-raising approach weighted 1 or 3 passes, and at 5 it is a minor") — eleven of them are w5, so at most minors; shipped anyway.
- JD-8: probe observable is the transcript; tests read artifacts (TRUTH 130-175: "No criterion compares a …").
- R4/R5 are ordering/tool-use **constraints**: TRUTH says "Six criteria are typed instruction following"; R4/R5 typed "tool use" — under JD-16 item 2 "a genuine tool-use constraint labelled `type = "tool use"` is mislabelled", a label defect only. Is R4's ordering stated? The instruction says the workbook carries three control sets and the config names which one (instruction text on the workbook); "before it takes any term" is not stated → under JD-16 it is conduct (odds-raising) rather than constraint. INFERRED that QC treated it as odds-raising.
- R2 traces to instruction:76 "Work inside `/app`" — a stated scope rule; a strong agent violates it by habit (unzip to /tmp). Weighted -1 so it costs little.
- Decoy negatives R28-R30 trace to the instruction naming the decoys as rejected (data_lineage.md + instruction) — IN-15 satisfied.
Shapes that cost a strong agent points without being unfair: (a) "shows one instance of <edge rule>" probes at w5; (b) a stated scope rule the agent's scratch habits break (/tmp use) at -1; (c) honesty negative on claimed-but-unrun comparisons (-3, trajectory-grounded, KNOWN J3).

## 7. How it passes QC (no QC report)
- IN-15: every negative traces to a sentence: data unmodified/work inside /app (:76), out holds 25 artifacts + conform.py (:50), decoys named as rejected (data_lineage.md; instruction "which files are decoys"), "derive the day again from the records rather than repair the old answer" (prior conform register).
- IN-16/IN-17: rules sit in stage docs (W2), instruction states none; it announces that the old conform "is wrong" (LV7 coupling announced, trap unnamed).
- TS-13: family checks are whole-family (one observable per family/seed).
- TS-16/TS-19: hidden seeds are drawn from the same generator; the lead-drop day is inside spec (R17 drop rule).
- TS-20: core w3/w5. TS-26: no real duplicates.
- AL-1: lead-drop rule is in v7/v8 (stated). AL-28: decoy negatives -5 in judge, test negative reads_training_corpus_at_runtime -5 — different acts (runtime read vs derived value).
- CL-4: exactness paragraph :53-57 "Every published quantity is exact…" + one LF no CR (:66).
- JD-7: oracle shows nothing → probes unsatisfiable by oracle; shipped (KNOWN K8).
- JD-11: negatives are task-specific (decoys, manifest mismatch, grader search).
- JD-15: probes odds-raising; R2 constraint stated.

## 8. Leak avoidance
- "The previous automated conform of that same day survives in the corpus and it is wrong, so derive the day again from the records rather than repair the old answer" (LV7; W1 — no hint where it is wrong).
- "The file names are deliberately non-obvious, so /app/data/data_lineage.md records which file feeds which stage and which files are decoys" (W8 odd carriers + one routing doc; W10).
- "It will be run against transmission days of this channel other than this one" (G1 announce hidden corpora without describing them).
- Shipped sample_worked_records.jsonl is 474 B and unit_test_vectors.json 1.5 KB — tiny worked examples that do not reach the separating branches (W6 respected for traps).
- Hidden seeds separate the readings the shipped day cannot (test comment :741-770) — W5.
- LEAK_LIBRARY: avoids "shipped boundary rows" (lead-drop and sheet-position readings never separated in shipped data) and "two-file read pointed together" (v7 and v8 are not cross-referenced in the instruction).

## 9. Agent behaviour
- Order: readme + overview + lineage (2-3), glossary + contracts (4-5), all 14 stage docs (6-9), config/rounding/governance/runbook (10-12), data heads (13-16), xlsx unzip to /tmp (17-20), pdf zlib text (21-22), probes (23-25); **first full program step 26 at 08:56:57 (8.8 min)**; runs to /tmp/t1 (30); edits 35-53; rerun diff (54); compile/style (55-58); default run into /app/out (60); data unchanged check (61); final 65 (15.9 min, $6.75).
- Self-tests: determinism, Fraction sanity, style, data untouched, deep-path run. Never constructed a lead-drop day.
- Final claim vs reality: claims all artifacts exact and that carry counts were cross-checked (false → R31).

## 10. Passed checks and criteria
- 20/21 positive tests incl. all 16 hidden family checks: complete stage docs + exact-arithmetic instruction let Opus transliterate.
- Judge: constants provenance (R5, R25), naming carry scopes (R12), four probes it happened to show, code quality, completion report.

## 11. Take-aways
- ADOPT (SAFE, NEW): **one dedicated rare-branch seed** whose only difference is a stated-but-never-shipped branch (default branch fires on every shipped/standard day), graded whole-document at w5.
- ADOPT (SAFE, NEW in our rules): **decoy-use negatives in the judge** (-5 each, per named decoy, "takes X from <decoy> into the artifact or the program") — trace to the routing doc that names decoys; complements tests.
- ADOPT (SAFE, NEW): **stated scope rule a strong agent breaks by habit** ("work inside /app") + a -1 trajectory negative; cheap, fair, fires on routine /tmp scratch use. Keep at -1.
- ADOPT (SAFE, KNOWN J3): factuality negative "states it checked X while its transcript has no run that compared".
- ADOPT (RISKY → minor): w5 probes (kit says minor at w5); prefer w3.
- Build technique: hidden seeds deliberately chosen so a specific wrong reading (positional sheet pick) is wrong on every graded seed — documented in a test comment, not the instruction.
- AVOID: ordering criterion "before it takes any term" that the instruction does not state — classifies as conduct; label as odds-raising w3, not "tool use".
