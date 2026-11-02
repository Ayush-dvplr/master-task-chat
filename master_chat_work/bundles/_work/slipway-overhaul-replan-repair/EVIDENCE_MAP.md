# EVIDENCE_MAP (fix-v1 451146f; harden r2 bddb388 copy in fix1/EVIDENCE_MAP.before.md)

Line numbers are of the files under environment/data after the Phase 2 regeneration.

## Graded rules

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Q1 lodgements naming a JOB-CYCLE job are rejected under EDG-UNKNOWNJOB and listed once | shipped_graph_layer_exact, shipped_audit_documents_exact, package_probe_publication_exact, package_eval_state_exact, package_challenge_state_exact (doc 19) | spec_stage_p02_precedence_graph.md:3-6, :12, :20-23 | silently dropped (old reference); listed under JOB-CYCLE |
| Q2 top level weighted_resource is the exact sum of the precinct rationals, published once at twelve places | shipped_baseline_optimum_exact, shipped_final_optimum_exact, package_eval_state_exact, package_challenge_state_exact | spec_stage_p10_objective.md:27-29; spec_stage_p11_search.md:15; rounding_and_arithmetic_policy.yaml (mode exact_rational, applied_at publication); instruction.md (rounding where the stage paper places it and nowhere else) | sum of the rounded precinct strings |
| Q8 aliases_active is the count of active crosswalk rows | shipped_identifier_layer_exact and the identifier family of every package check | output_schema_reference.md:12-13 | size of the alias map (coincide on generated data) |
| Q3 a class rate revision on a class holding no job reaches no cell and is inert | none (latent, no generated round plants it) | spec_stage_p13_amendments.md:10-16 (instruction.md:21, which asked for it in the final message, is deleted in fix-v1 for AL-2) | governed |
| Q7 a reversal of a lodgement withdraws the lodged edge (exact inverse) | package_crosswalk_amendments_cascade_exact, package_crosswalk_amendments_state_exact, package_crosswalk_every_state_exact, package_crosswalk_every_publication_exact (AMD-120) | spec_stage_p13_amendments.md:13-15; cascade_precedence_directive.docx section 1 (reversal: seed set of the amendment it names); worked_examples.md "A reversal" | crash on the inverse; re-withdrawal |
| crosswalk applied to slot group memberships | package_crosswalk_groups_state_exact, package_crosswalk_every_state_exact | spec_stage_p01_identifier_and_revision.md:19-22; worked_examples.md:73-82; spec_stage_p08_slot_groups.md:3-11 | legacy id dropped as no job in force |
| crosswalk applied to charge rule subjects | package_crosswalk_rules_state_exact, package_crosswalk_every_state_exact | spec_stage_p01_identifier_and_revision.md:19-22; worked_examples.md:73-82; spec_stage_p10_objective.md:3-17 | rule never fires; subject published raw in doc 05 |
| crosswalk applied to amendment payloads | package_crosswalk_amendments_cascade_exact, package_crosswalk_amendments_state_exact, package_crosswalk_every_* | spec_stage_p01_identifier_and_revision.md:19-22; spec_stage_p02_precedence_graph.md:11-12; spec_stage_p13_amendments.md:10-16 | AMD-NOTARGET; EDG-UNKNOWNJOB |
| crosswalk applied to both ends of a precedence row (AL-27, place `edges`) | every package_crosswalk_*_exact check (all 11 held rounds plant it; docs 02, 03, 19 and everything downstream) | spec_stage_p01_identifier_and_revision.md:19-21 ("for a precedence row that means both of its ends"); spec_stage_p02_precedence_graph.md:11-12 (EDG-SELF "after the crosswalk", EDG-UNKNOWNJOB); worked_examples.md:73-82 (LEG-0042 on both ends) | lodgement rejected EDG-UNKNOWNJOB; edge dropped |
| crosswalk applied to the register in force (AL-27, place `register`) | every package_crosswalk_*_exact check (all 11 held rounds; berth_job_register_frozen.csv, the register round_header.json names) | spec_stage_p01_identifier_and_revision.md:3-4 (register named by register_in_force), :8-17 (row in force per job), :19-21 (every job identifier, in whichever paper it stands) | a legacy-id row read as its own job, so the job's row in force is wrong or the job is unknown |
| crosswalk applied to a payload field completed from the supplement (AL-27, place `supplement`) | package_crosswalk_amendments_*_exact, package_crosswalk_every_*_exact (5 held rounds that name `amendments`) | spec_stage_p13_amendments.md:3-8 (empty payload field completed from amendment_supplement.ndjson where row_provenance_ledger.csv records it in_force); spec_stage_p01_identifier_and_revision.md:19-21 | AMD-102 lodgement's required end left as a legacy id: EDG-UNKNOWNJOB |

Held-out legacy identifiers use active crosswalk rows only (a withdrawn crosswalk row maps nothing,
p01:21-22, and the generator never plants a withdrawn legacy identifier).

AL-27 (fix-v1): `carried_commitment_ledger.csv` (header `commitment_id,precinct,pool,quantity,state,note`, spec_stage_p09_capacity.md) and
`licence_validity_register.csv` (header `licence_code,state,valid_from_round,valid_to_round,note`, spec_stage_p04) carry no job identifier
column, so p01:19-21 has nothing to put through the crosswalk in them; planting one would need a new column and new doc text
(route-1 R2 / IN-17), so neither is planted. The generator plants per draw (test_output.py:1234 `_legacy`, :1252 edges, :1210 register,
:1599 supplement), `_assert_legacy` (:1534) returns the bare places and `write_corpus` redraws up to LEGACY_DRAWS = 8 (:3755).

## Q5: rules the removed known_traps_and_footguns.md stated, and where each stands now

| rule no. | rule the file stated | home now (file:line) |
|---|---|---|
| 1 | rows sealed for a later round are not read | spec_stage_p01_identifier_and_revision.md:8-11 |
| 2 | a withdrawn row in force sets the job aside; one behind a later sealed row does nothing | spec_stage_p01_identifier_and_revision.md:8-13 (row in force is the greatest revision at or below the round index) |
| 3 | capacity rows with a later effective round or another state settle nothing | spec_stage_p09_capacity.md:3-6 |
| 4 | only a charge rule in force is read | spec_stage_p10_objective.md:3-4 (NEW plain rule sentence; no other home existed) |
| 5 | only a lodged amendment row is an amendment | spec_stage_p13_amendments.md:3-4 |
| 6 | two amendments with one payload are each classified, seeded and cascaded | spec_stage_p13_amendments.md:10-11 (each amendment) |
| 7 | an exact inverse amendment is applied like any other | spec_stage_p13_amendments.md:13-15; worked_examples.md "A reversal" |
| 8 | a group of one open member or none binds nothing | spec_stage_p08_slot_groups.md:9-11 |
| 9 | a rule that never fires still stands in the solve key | spec_stage_p12_provenance.md:3-6 |
| 10 | the rebate needs two or more jobs in the closure, at any depth | spec_stage_p10_objective.md:13-16; spec_stage_p05_closure.md (closure at any depth) |
| 11 | two amount forms reaching the same mills are one amount; such a restatement moves nothing | spec_stage_p03_normalisation.md:20-21; cascade_precedence_directive.docx section 2 |
| 12 | a duplicated edge pair is one prerequisite; withdrawing either while the other stands leaves it | spec_stage_p02_precedence_graph.md:15-18; cascade_precedence_directive.docx section 5 |

The file, its write in the generator and its lineage row are removed; `grep -rn known_traps` over the
bundle returns nothing.

## 481e976 fix-ql1
- F2: p13:7-9 empty kind lodged as hard <- test_output.py:3023/:3029 `payload.get("kind", "hard")`.
- F3: output_schema_reference.md:160-162, :176-177 rejected amendments counted <- test_output.py:3490/:3514 `len(records)`.
- F10: output_schema_reference.md:165 manifest 01..23 then 25 <- p14:5-7, shipped publish.py.
- F6: delivered_engine_stdlib_only reads the bare (-S) sample run, doc 18 vs reference; new negative imports_outside_the_standard_library (-3) holds the import scan.
