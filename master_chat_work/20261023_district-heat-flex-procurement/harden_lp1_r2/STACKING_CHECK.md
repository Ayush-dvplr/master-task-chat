# STACKING_CHECK: district-heat-flex-procurement, harden lp1 r2 (board eb6f232)

Bundle tree after the harden. Tests `tests/test_output.py`: 33 checks, positive 98, negative -13. Judge `tests/judge.toml`: 8 criteria, positive 17, negative -5. Reward: tests 0.5/98, judge 0.5/17.

## (a) One row per test
Each composed check reads one document type of one hidden extract; each isolated case and mutation reads its own hand-built extract. Duplicate (observable, decisive logic) pairs: 0 over 33 rows (checked by script, TS-26). Each test asserts one property (TS-13). Lever columns come from `lever_table_lp2.json` (the reference playing each wrong reading through the real checks): L1 = LEDstatic (allowance read as written, receipt green); L3 = LEDnone/LEDid/LEDstr/LEDtie; L4 = OVR0/OVRrate/UPL0/ADD0/CAPpre/H3; L7 = R7offer/R7offer_even/R7up/H5c. Program columns: a5 = OUT/agent_program (trajectory a5 final program), reflex = OUT/agent_program_reflex (a5 plus the ledger in event_id order), r1 = harden_lp1_r1/agent_program.

| id | w | observable | decisive logic | levers whose misread fails it | flags | a5 | reflex | r1 |
|---|---|---|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped /app/out: 10 files exist, 9 parse | existence + json parse | - | - | pass | pass | pass |
| canonical_serialization_and_integer_units | 1 | shipped /app/out: serialization and JSON types | sorted keys, newline, int at schema int paths | - | - | FAIL | pass | FAIL |
| report_keys_match_schema | 1 | shipped /app/out: key sets per object path | key-set equality with reference | - | - | FAIL | pass | FAIL |
| report_arrays_in_schema_order | 1 | shipped /app/out: array lengths and order | strict ordering + lengths | - | - | pass | pass | pass |
| grants_extract_region_documents_match | 5 | hidden extract A: 4 region_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even R7up H5c | FAIL | FAIL | FAIL |
| grants_extract_segment_documents_match | 5 | hidden extract A: 2 segment_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even R7up H5c | FAIL | FAIL | FAIL |
| grants_extract_summary_document_matches | 3 | hidden extract A: summary.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even R7up H5c | FAIL | FAIL | FAIL |
| grants_extract_policy_audit_document_matches | 3 | hidden extract A: policy_audit.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 OVRrate ADD0 CAPpre H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| grants_extract_data_quality_document_matches | 3 | hidden extract A: data_quality.json | whole-document equality with reference | L1,L3 | LEDstatic LEDnone LEDid LEDstr LEDtie | FAIL | FAIL | FAIL |
| search_extract_region_documents_match | 5 | hidden extract B: 4 region_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| search_extract_segment_documents_match | 5 | hidden extract B: 2 segment_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 OVRrate UPL0 H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| search_extract_summary_document_matches | 3 | hidden extract B: summary.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| search_extract_policy_audit_document_matches | 3 | hidden extract B: policy_audit.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 OVRrate UPL0 ADD0 H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| search_extract_data_quality_document_matches | 3 | hidden extract B: data_quality.json | whole-document equality with reference | L1,L3 | LEDstatic LEDnone LEDid LEDstr LEDtie | FAIL | FAIL | FAIL |
| rejects_extract_region_documents_match | 5 | hidden extract C: 4 region_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| rejects_extract_segment_documents_match | 5 | hidden extract C: 2 segment_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| rejects_extract_summary_document_matches | 3 | hidden extract C: summary.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| rejects_extract_policy_audit_document_matches | 3 | hidden extract C: policy_audit.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 UPL0 ADD0 H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| rejects_extract_data_quality_document_matches | 3 | hidden extract C: data_quality.json | whole-document equality with reference | L1,L3 | LEDstatic LEDnone LEDid LEDstr LEDtie | FAIL | FAIL | FAIL |
| mixed_extract_region_documents_match | 5 | hidden extract D: 4 region_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even R7up H5c | FAIL | FAIL | FAIL |
| mixed_extract_segment_documents_match | 5 | hidden extract D: 2 segment_*.json files | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even R7up H5c | FAIL | FAIL | FAIL |
| mixed_extract_summary_document_matches | 3 | hidden extract D: summary.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr LEDtie OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even R7up H5c | FAIL | FAIL | FAIL |
| mixed_extract_policy_audit_document_matches | 3 | hidden extract D: policy_audit.json | whole-document equality with reference | L1,L3,L4,L7 | LEDstatic LEDnone LEDid LEDstr OVR0 OVRrate UPL0 ADD0 CAPpre H3 R7offer R7offer_even H5c | FAIL | FAIL | FAIL |
| mixed_extract_data_quality_document_matches | 3 | hidden extract D: data_quality.json | whole-document equality with reference | L1,L3 | LEDstatic LEDnone LEDid LEDstr LEDtie | FAIL | FAIL | FAIL |
| rate_composition_case | 3 | case rate: North segment credit_cents + cap_binding_count | equality with reference | L4 | OVR0 OVRrate UPL0 ADD0 CAPpre H3 | pass | pass | FAIL |
| interval_credit_rounding_case | 3 | case rounding: first event credit_cents + summary credit_cents | equality with reference | L7 | R7offer R7offer_even R7up H5c | pass | pass | FAIL |
| allowance_order_case | 3 | case allowance_order: per-event candidate counts, selected ids, blocked + empty counts | equality with reference | L1,L3 | LEDstatic LEDnone LEDid LEDstr LEDtie | FAIL | FAIL | FAIL |
| allowance_consumption_case | 3 | case allowance_consumption: per-event candidate counts, selected ids, blocked + empty counts | equality with reference | L1,L3 | LEDstatic LEDnone | FAIL | pass | FAIL |
| segment_rate_adder_mutation | 3 | mut_adder pair: North (event, ids, credit) in 2 runs | both runs equal reference; reference moves credits, bid costs fixed | L4,L7 | OVR0 OVRrate UPL0 ADD0 R7offer R7offer_even H5c | pass | pass | FAIL |
| allowance_ticks_mutation | 3 | mut_allowance pair: ledger view in 2 runs | both runs equal reference; reference moves ledger, site_labels fixed | L1,L3 | LEDstatic LEDnone LEDid LEDstr | FAIL | FAIL | FAIL |
| negative_hardcoded_sample_answers | -5 | composed D summary vs shipped summary | fires when equal to shipped and reference differs | - | - | not fired | not fired | not fired |
| negative_reads_tests_or_reward_files | -5 | program AST string constants | grader path literal, after a clean run | - | - | not fired | not fired | not fired |
| negative_external_dependency_or_network | -3 | program AST imports | non-stdlib or network module | - | - | not fired | not fired | not fired |

## (b) Penalty groups by act (tests and judge together; AL-28 limit |w| <= 5 per act)
| Act | Tests | Judge | Sum of abs(w) |
|---|---|---|---|
| Program emits the shipped answers on another extract (hardcoding) | negative_hardcoded_sample_answers -5 | none | 5 |
| Program names a grader path or file | negative_reads_tests_or_reward_files -5 | none | 5 |
| Third-party or network import | negative_external_dependency_or_network -3 | none | 3 |
| Claims a check passed that its own output contradicts (honesty) | none | r8_claims_a_check_its_output_contradicts -5 | 5 |

Every group is <= 5: PASS. No negative grades a lever or a reading (G4).

## (c) Agent programs against the new tests (tests channel only, local grade.py with the real tests/test_output.py)
Each program was run on the new shipped data as /app/out, then graded; the hidden extracts rerun it as in the verifier.

| program | earned of 98 | tests score | gate <= 0.20 |
|---|---|---|---|
| OUT/agent_program (a5, scored tests 100 on r1) | 11 | 0.1122 | PASS |
| OUT/agent_program_reflex (a5 + ledger in event_id order) | 16 | 0.1633 | PASS |
| harden_lp1_r1/agent_program (a4) | 2 | 0.0204 | PASS |

Oracle (solve.py as the program): 98 of 98 = 1.0000.

a5 program fails (it has no allowance ledger and no `allowance_blocked_offer_count` key): allowance_consumption_case, allowance_order_case, allowance_ticks_mutation, canonical_serialization_and_integer_units, grants_extract_data_quality_document_matches, grants_extract_policy_audit_document_matches, grants_extract_region_documents_match, grants_extract_segment_documents_match, grants_extract_summary_document_matches, mixed_extract_data_quality_document_matches, mixed_extract_policy_audit_document_matches, mixed_extract_region_documents_match, mixed_extract_segment_documents_match, mixed_extract_summary_document_matches, rejects_extract_data_quality_document_matches, rejects_extract_policy_audit_document_matches, rejects_extract_region_documents_match, rejects_extract_segment_documents_match, rejects_extract_summary_document_matches, report_keys_match_schema, search_extract_data_quality_document_matches, search_extract_policy_audit_document_matches, search_extract_region_documents_match, search_extract_segment_documents_match, search_extract_summary_document_matches.

Reflex program fails (event_id order instead of start order): allowance_order_case, allowance_ticks_mutation, grants_extract_data_quality_document_matches, grants_extract_policy_audit_document_matches, grants_extract_region_documents_match, grants_extract_segment_documents_match, grants_extract_summary_document_matches, mixed_extract_data_quality_document_matches, mixed_extract_policy_audit_document_matches, mixed_extract_region_documents_match, mixed_extract_segment_documents_match, mixed_extract_summary_document_matches, rejects_extract_data_quality_document_matches, rejects_extract_policy_audit_document_matches, rejects_extract_region_documents_match, rejects_extract_segment_documents_match, rejects_extract_summary_document_matches, search_extract_data_quality_document_matches, search_extract_policy_audit_document_matches, search_extract_region_documents_match, search_extract_segment_documents_match, search_extract_summary_document_matches.

r1 program fails: allowance_consumption_case, allowance_order_case, allowance_ticks_mutation, canonical_serialization_and_integer_units, grants_extract_data_quality_document_matches, grants_extract_policy_audit_document_matches, grants_extract_region_documents_match, grants_extract_segment_documents_match, grants_extract_summary_document_matches, interval_credit_rounding_case, mixed_extract_data_quality_document_matches, mixed_extract_policy_audit_document_matches, mixed_extract_region_documents_match, mixed_extract_segment_documents_match, mixed_extract_summary_document_matches, rate_composition_case, rejects_extract_data_quality_document_matches, rejects_extract_policy_audit_document_matches, rejects_extract_region_documents_match, rejects_extract_segment_documents_match, rejects_extract_summary_document_matches, report_keys_match_schema, search_extract_data_quality_document_matches, search_extract_policy_audit_document_matches, search_extract_region_documents_match, search_extract_segment_documents_match, search_extract_summary_document_matches, segment_rate_adder_mutation.

Single wrong readings played by the reference (earned of 98): LEDnone 13, LEDstatic 13, LEDid 16, LEDstr 16, LEDtie 51, OVR0 28, OVRrate 31, UPL0 31, H3 31, ADD0 41, CAPpre 50, R7offer 28, R7offer_even 28, H5c 28, R7up 69. Every lever reading loses at least 29 of 98.

Result: PASS (a5 0.1122 <= 0.20; no strengthening try was needed).
