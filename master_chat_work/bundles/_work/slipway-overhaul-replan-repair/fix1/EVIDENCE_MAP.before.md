# EVIDENCE_MAP (harden r2, bddb388)

Line numbers are of the files under environment/data after the Phase 2 regeneration.

## Graded rules

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Q1 lodgements naming a JOB-CYCLE job are rejected under EDG-UNKNOWNJOB and listed once | shipped_graph_layer_exact, shipped_audit_documents_exact, package_probe_publication_exact, package_eval_state_exact, package_challenge_state_exact (doc 19) | spec_stage_p02_precedence_graph.md:3-6, :12, :20-23 | silently dropped (old reference); listed under JOB-CYCLE |
| Q2 top level weighted_resource is the exact sum of the precinct rationals, published once at twelve places | shipped_baseline_optimum_exact, shipped_final_optimum_exact, package_eval_state_exact, package_challenge_state_exact | spec_stage_p10_objective.md:27-29; spec_stage_p11_search.md:15; rounding_and_arithmetic_policy.yaml (mode exact_rational, applied_at publication); instruction.md (rounding where the stage paper places it and nowhere else) | sum of the rounded precinct strings |
| Q8 aliases_active is the count of active crosswalk rows | shipped_identifier_layer_exact and the identifier family of every package check | output_schema_reference.md:12-13 | size of the alias map (coincide on generated data) |
| Q3 a class rate revision on a class holding no job reaches no cell and is inert | none (latent, no generated round plants it) | spec_stage_p13_amendments.md:10-16; instruction.md:21 (an amendment classified as reaching no cell at all) | governed |
| Q7 a reversal of a lodgement withdraws the lodged edge (exact inverse) | package_crosswalk_amendments_cascade_exact, package_crosswalk_amendments_state_exact, package_crosswalk_every_state_exact, package_crosswalk_every_publication_exact (AMD-120) | spec_stage_p13_amendments.md:13-15; cascade_precedence_directive.docx section 1 (reversal: seed set of the amendment it names); worked_examples.md "A reversal" | crash on the inverse; re-withdrawal |
| crosswalk applied to slot group memberships | package_crosswalk_groups_state_exact, package_crosswalk_every_state_exact | spec_stage_p01_identifier_and_revision.md:19-22; worked_examples.md:73-82; spec_stage_p08_slot_groups.md:3-11 | legacy id dropped as no job in force |
| crosswalk applied to charge rule subjects | package_crosswalk_rules_state_exact, package_crosswalk_every_state_exact | spec_stage_p01_identifier_and_revision.md:19-22; worked_examples.md:73-82; spec_stage_p10_objective.md:3-17 | rule never fires; subject published raw in doc 05 |
| crosswalk applied to amendment payloads | package_crosswalk_amendments_cascade_exact, package_crosswalk_amendments_state_exact, package_crosswalk_every_* | spec_stage_p01_identifier_and_revision.md:19-22; spec_stage_p02_precedence_graph.md:11-12; spec_stage_p13_amendments.md:10-16 | AMD-NOTARGET; EDG-UNKNOWNJOB |

Held-out legacy identifiers use active crosswalk rows only (a withdrawn crosswalk row maps nothing,
p01:21-22, and the generator never plants a withdrawn legacy identifier).

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
