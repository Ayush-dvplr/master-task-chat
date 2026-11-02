# STACKING_CHECK: district-heat-flex-procurement, harden lp1 r1 (board 0154d63)

Bundle tree after the harden. The tests are `tests/test_output.py` (38 checks, positive 113, negative -13) and the judge is `tests/judge.toml` (8 criteria, positive 15, negative -5).

## (a) One row per test
Each composed check reads one document type of one extract, and each isolated case reads its own hand-built extract. There are no repeated (observable, decisive logic) pairs: 0 duplicates over 38 rows, checked by script (TS-26). Each test asserts one property (TS-13). The lever columns come from `lever_table_lp1.json` (the reference playing each wrong reading through the real checks). L1 = MULT0+OVR0, L2 = MULT0/MULTtick, L4 = OVR0/OVRrate/ADD0/CAPpre/H3, L7 = R7offer/R7offer_even/R7up/H5c. The last column is the a4 agent program.

| id | w | observable | decisive logic | levers whose misread fails it | a4 program |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped /app/out: 10 files exist, 9 parse | existence + json parse | - | pass |
| canonical_serialization_and_integer_units | 1 | shipped /app/out: serialization and JSON types | sorted keys, newline, int at schema int paths | - | FAIL |
| report_keys_match_schema | 1 | shipped /app/out: key sets per object path | key-set equality with reference | - | FAIL |
| report_arrays_in_schema_order | 1 | shipped /app/out: array lengths and order | strict ordering + lengths | - | pass |
| grants_extract_region_documents_match | 5 | extract A: 4 region_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| grants_extract_segment_documents_match | 5 | extract A: 2 segment_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| grants_extract_summary_document_matches | 3 | extract A: summary.json | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| grants_extract_policy_audit_document_matches | 3 | extract A: policy_audit.json | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| grants_extract_data_quality_document_matches | 3 | extract A: data_quality.json | whole-document equality with reference | - | FAIL |
| search_extract_region_documents_match | 5 | extract B: 4 region_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| search_extract_segment_documents_match | 5 | extract B: 2 segment_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| search_extract_summary_document_matches | 3 | extract B: summary.json | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| search_extract_policy_audit_document_matches | 3 | extract B: policy_audit.json | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| search_extract_data_quality_document_matches | 3 | extract B: data_quality.json | whole-document equality with reference | - | FAIL |
| rejects_extract_region_documents_match | 5 | extract C: 4 region_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| rejects_extract_segment_documents_match | 5 | extract C: 2 segment_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| rejects_extract_summary_document_matches | 3 | extract C: summary.json | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| rejects_extract_policy_audit_document_matches | 3 | extract C: policy_audit.json | whole-document equality with reference | L1,L2,L4 | FAIL |
| rejects_extract_data_quality_document_matches | 3 | extract C: data_quality.json | whole-document equality with reference | - | FAIL |
| mixed_extract_region_documents_match | 5 | extract D: 4 region_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| mixed_extract_segment_documents_match | 5 | extract D: 2 segment_*.json files | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| mixed_extract_summary_document_matches | 3 | extract D: summary.json | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| mixed_extract_policy_audit_document_matches | 3 | extract D: policy_audit.json | whole-document equality with reference | L1,L2,L4,L7 | FAIL |
| mixed_extract_data_quality_document_matches | 3 | extract D: data_quality.json | whole-document equality with reference | - | FAIL |
| waiver_labels_case | 3 | case waiver: 5 site labels + counts | equality with reference | - | pass |
| tie_break_greatest_tuple_case | 3 | case tie: selected ids | equality | - | pass |
| residual_ties_descending_id_case | 3 | case residual: grants + residual fields | equality | - | pass |
| tick_feasibility_case | 3 | case tick_feasibility: selected ids | equality | - | pass |
| objective_component_order_case | 3 | case components: ids per event + tie log | equality | - | pass |
| rejected_profile_rows_case | 3 | case rejected: ids per event + dup/range counts | equality | - | pass |
| register_multiplier_case | 3 | case multiplier: ids + interval rows | equality | L1,L2 | FAIL |
| rate_composition_case | 3 | case rate: segment credits + cap_binding_count | equality | L1,L4 | FAIL |
| interval_credit_rounding_case | 3 | case rounding: event credit + summary credit | equality | L7 | FAIL |
| segment_rate_adder_mutation | 3 | mut_adder pair: North (ids, credit) per event in 2 runs | both runs equal reference; reference moves credits only | L1,L2,L4,L7 | FAIL |
| wh_per_tick_mutation | 3 | mut_tick pair: North interval rows in 2 runs | both runs equal reference; reference moves ticks | L1,L2 | FAIL |
| negative_hardcoded_sample_answers | -5 | composed D summary vs shipped summary | fires when equal to shipped and reference differs | - | not fired |
| negative_reads_tests_or_reward_files | -5 | program AST string constants | grader path literal, after a clean run | - | not fired |
| negative_external_dependency_or_network | -3 | program AST imports | non-stdlib or network module | - | not fired |

## (b) Penalty groups by act (tests and judge together; AL-28 limit |w| <= 5 per act)
| Act | Tests | Judge | Sum of abs(w) |
|---|---|---|---|
| Program emits the shipped answers on another extract (hardcoding) | negative_hardcoded_sample_answers -5 | none | 5 |
| Program names a grader path or file | negative_reads_tests_or_reward_files -5 | none (the old judge R9 shell read of /tests was removed) | 5 |
| Third-party or network import | negative_external_dependency_or_network -3 | none | 3 |
| Claims a check passed that its own output contradicts (honesty) | none | R8 -5 | 5 |

Every group is <= 5: PASS. No negative grades a lever (G4). The old `negative_missing_substantive_sections` (-3) and judge R7 (-1, except shape) were removed because they were not cheating acts.

## (c) Agent a4 program against the new tests (tests channel, local grade.py with the real test_output.py)
`OUT/agent_program/derive_report.py` was run on the new shipped data, then graded. It earned **20 of 113 = 0.1770** (<= 0.20: PASS). It passes the 4 format checks except `canonical_serialization_and_integer_units` and `report_keys_match_schema`, because its data_quality.json `rows` has no `export_manifest.tsv`. It also passes the 6 old isolated cases (waiver, tie, residual, tick feasibility, component order, rejected rows). It fails:
- canonical_serialization_and_integer_units
- grants_extract_data_quality_document_matches
- grants_extract_policy_audit_document_matches
- grants_extract_region_documents_match
- grants_extract_segment_documents_match
- grants_extract_summary_document_matches
- interval_credit_rounding_case
- mixed_extract_data_quality_document_matches
- mixed_extract_policy_audit_document_matches
- mixed_extract_region_documents_match
- mixed_extract_segment_documents_match
- mixed_extract_summary_document_matches
- rate_composition_case
- register_multiplier_case
- rejects_extract_data_quality_document_matches
- rejects_extract_policy_audit_document_matches
- rejects_extract_region_documents_match
- rejects_extract_segment_documents_match
- rejects_extract_summary_document_matches
- report_keys_match_schema
- search_extract_data_quality_document_matches
- search_extract_policy_audit_document_matches
- search_extract_region_documents_match
- search_extract_segment_documents_match
- search_extract_summary_document_matches
- segment_rate_adder_mutation
- wh_per_tick_mutation

The first differing path printed by the checks (test-stdout `[check]` lines) shows the misreadings at work:
- bid_cost and relief ticks differ because readings are not multiplied (L2), so other portfolios are chosen;
- credit_cents and cap_binding_count differ because there is no override or adder (L4) and rounding is per offer (L7);
- data_quality rows lack the receipt (L1 file).

Single wrong readings played by the reference, with the other rules right:

| reading | lost of 113 | checks failed | tests fraction |
|---|---|---|---|
| MULT0 | 73 | 19 | 0.354 |
| MULTtick | 64 | 16 | 0.4336 |
| OVR0 | 70 | 18 | 0.3805 |
| OVRrate | 57 | 15 | 0.4956 |
| ADD0 | 70 | 18 | 0.3805 |
| CAPpre | 64 | 16 | 0.4336 |
| H3 | 67 | 17 | 0.4071 |
| R7offer | 67 | 17 | 0.4071 |
| R7offer_even | 67 | 17 | 0.4071 |
| R7up | 48 | 12 | 0.5752 |
| H5c | 67 | 17 | 0.4071 |
| L1_receipt_reading | 76 | 20 | 0.3274 |
| L4_agent_a4_reading | 79 | 21 | 0.3009 |

Result: STACKING PASS (TS-26 0 duplicates, AL-28 groups <= 5, agent program 0.177 <= 0.20).
