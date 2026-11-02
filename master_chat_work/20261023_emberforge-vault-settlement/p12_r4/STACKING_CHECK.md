# STACKING_CHECK P12 r4

Static tool: 21 tests, nine judge criteria, positive test 55, negative test -8, positive judge 12, negative judge -11; no TS-26 duplicate candidates. Its 32.7% isolated hint includes three structural w1 checks. The five rule and mutation checks alone are 15/55 = 27.3%.

## (a) Test map

| Check | w | Observable | Logic | Wrong reading fails | Codex reflex |
|---|---:|---|---|---|---|
| `structure_program_delivered` | 1 | source parses | file read and compile | none | PASS |
| `program_imports_stdlib_only` | 1 | module imports | AST top-level modules in stdlib | none | PASS |
| `structure_program_takes_directories` | 1 | output paths | explicit and default directory run | none | NOT_RUN |
| `structure_canonical_serialisation` | 1 | JSON bytes and key order | forge_a record form | none | PASS |
| `structure_reruns_byte_identical` | 1 | repeat output bytes | same corpus twice | none | PASS |
| `whole_summary` | 5 | summary.json | all four whole seasons | L7, L3, L6, I6, H7 | FAIL |
| `whole_vault_audit` | 5 | vault_audit.json | all four whole seasons | L3, L6, I6 | FAIL |
| `whole_reconciliation` | 5 | reconciliation.json | all four whole seasons | L7, L3, L6, I6, H7 | FAIL |
| `whole_data_quality` | 5 | data_quality.json | all four whole seasons | L3, L6, I6 | FAIL |
| `whole_allocation` | 5 | allocation.json | all four whole seasons | L3, L6, I6 | FAIL |
| `whole_workshop_reports` | 5 | workshop_*.json | all four whole seasons | L7, L3, L6, I6, H7 | FAIL |
| `whole_guild_reports` | 5 | guild_*.json | all four whole seasons | L7, L3, L6, I6, H7 | FAIL |
| `unit_charge_season_total` | 3 | season charge | iso_unit_charge | L7 | PASS |
| `cap_release_closures` | 3 | CAP_REACHED IDs | iso_cap_release | L7, L3 | PASS |
| `live_window_refusals` | 3 | UNCREDITED_SALVAGE IDs | iso_live_window | L6 | FAIL |
| `mutation_family_multiplier` | 3 | charge ledger | mut_family, vault stable | L7 | PASS |
| `mutation_grade_step` | 3 | charge ledger | mut_grade, vault stable | L7 | PASS |
| `negative_hardcoded_sample_answers` | -3 | replayed summary | changed corpus | none | quiet |
| `negative_filename_dependent_behaviour` | -1 | name-dependent output | same corpus, new name | none | quiet |
| `negative_reads_training_corpus_at_runtime` | -1 | reads shipped corpus | other data dir passed | none | NOT_RUN |
| `negative_rebinds_verifier_dependencies` | -3 | import/path hook | grader tampering | none | quiet |

Each whole check reads a different document. `structure_program_takes_directories` is NOT_RUN in the host scorer because it renames `/app/data`; Docker grades it.

## (b) Penalties

| Act | Tests | Judge | Maximum magnitude |
|---|---|---|---:|
| shipped-answer replay or related shortcut | hardcoded -3, filename -1, reads shipped corpus -1 | none | 5 |
| verifier hook | rebind -3 | none | 3 |
| writes `/app/data` | none | R5 -1 | 1 |
| online lookup | none | R6 -3 | 3 |
| false validation claim | none | R7 -3 | 3 |
| grader file read | none | R8 -3 | 3 |
| program network connection | none | R9 -1 | 1 |

## (c) Weight shares and caps

- Whole hidden documents 35/55 = 63.6%; rule and mutation checks 15/55 = 27.3%; structural checks 5/55 = 9.1%; shipped-output-only presence 1/55 = 1.8%.
- 21 tests and nine criteria fit 70/70 caps; core whole documents weigh 5, structural checks weigh 1.

## (d) Reflex replay

| Program | Before earned / P | After earned / P | After loss |
|---|---:|---:|---:|
| Codex | 19.75/54 | 17/55 | 38 |
| adapted | 5.25/54 | 5/55 | 50 |
| L7 | 22/54 | 23/55 | 32 |
| L3 | 27.25/54 | 17/55 | 38 |
| L6 | 17.25/54 | 17/55 | 38 |
| no_reinstate | 54/54 | 20/55 | 35 |
| no_apprentice_relief | 54/54 | 35/55 | 20 |

After L7/L3/L6 variants are rebased onto the corrected I6/H7 oracle. Each retains exactly one lever misreading. Codex weighted tests contribution after is 0.1545, below 0.20.

**STACKING PASS**

## Lessons for the master

- The static isolated share includes structural checks; correct it from the code.
