# TRIP: hangar-check-replan attempt 1 (claude-opus-5, run_1)

Source: OUT/gate_run_a1 (copy of Output_RFP run_1). Final 75.0 = tests 100.0 (137/137) + judge 50.0 (21/42).
Program: OUT/gate_run_a1/artifacts/app/out/derive_report.py (826 lines). Step numbers are trajectory steps.

## 1. What a1 read (every doc and data file)

| step | read |
|---|---|
| 3 | `find /app` (full tree) |
| 4-8 | README.md, data_conventions.md, planning_policy.md, overtime_policy.md + deferral_policy.md, output_schema.md (all six docs, in full) |
| 9 | heads / wc of fleet_limits.toml, check_types.json, fleet_register.csv, check_requests.csv, published_plan.csv |
| 10-11 | awk over 2027A OPEN rows of check_requests.csv |
| 12-13 | both docx: `_rels/.rels` and a table dump of word/document.xml |
| 14 | base_calendar.jsonl non-OPEN days in season per base |
| 15-16 | register tails grep; request ids in published_plan |

Never opened: nothing. Every doc and both Word files were read before the first write (step 17).

## 2. Rules implemented and how each was checked

| rule (doc:line) | a1 code | how a1 checked it (step) |
|---|---|---|
| reject order, line numbers (data_conventions.md:34-46) | read_csv_rows + reason chain, physical line_num | shipped run only (21-22); no malformed folder |
| available day, clip to day 1 (data_conventions.md:51-53) | revised table else own; max(1, .) | shipped run; synth folders (27-29) |
| closed / no-start days (data_conventions.md:54-56) | calendar + notice closures clipped to season | shipped; synth |
| Word tables (data_conventions.md:20-23) | `docx_tables` L103-127: rels officeDocument, `tbl.findall(w:tr)` direct children, `tr.findall(w:tc)`, join of every `w:t` under the cell | only the shipped files and its own synth.py docx (27: one `w:tr` per row, one run per cell) |
| line rules, finish = s+p-c-1 (planning_policy.md:5-20) | plan_base exact DP, feasible_starts | verify.py: reference DP over every start day on shipped (23-24) and on synth folders (52-53) |
| lexicographic terms + start/finish tie lists (planning_policy.md:22-41) | mixed-radix scalar + vectors | synth.py full enumeration, seeds 0-160, 4-8 requests (27-29, 35, 40) |
| shared pool (overtime_policy.md:9-10) | merge_bases keeps min per total shifts | verify_merge.py full split enumeration on shipped (25-26), not rerun after later edits (R16) |
| allowance order and settlement (overtime_policy.md:12-27) | sort (class, due, id), take=min(ot,left) | cross-sum of reports (44); no replay of the order (R4 lost) |
| deferral reason (deferral_policy.md:3-9) | can_fit_alone over compressions | synth |
| missing input (data_conventions.md:58-59) | die(path) | removed check_types.json (47) |

## 3. Shipped-fitted literals

None. Literals are documented constants only: transitional W namespace (L15), BASES (L17), SEGMENT_OF (L19),
CLASS_ORDER (L20). Family 4b (LC1) has nothing to break.

## 4. Where checking stopped

- Performance work (30-43) up to 60 requests per base x 120 days; equality rechecked with diff (35, 40, 49).
- Season id swap (46) and missing file (47) are the only input-shape tests.
- Word input was tested only in the markup its own generator writes (27): plain `w:tr` rows, one run per cell.
  Row-level content controls (`w:sdt`), row-level `w:customXml` and `mc:AlternateContent` runs were never tried.
- R16: the merge check (26) was not rerun after edits 33-39; the final message claims it.

## 5. Fuzz: a1 program vs the test reference (Docker, hangar-tests, --memory 4g --cpus 2)

Harness WORK/h1_a1/fuzz.py (generator + reference = tests/test_output.py L37-830 verbatim in refgen.py).
Equivalence mutators (D_*, C_*) change markup or layout only, so the expected answer is the reference on
the unmutated folder; S_* mutators change values inside documented ranges and use the reference on the
mutated folder. Logs: `_runs/20261102/hangar-check-replan/harden1-20261102T0200/{equiv,alt,sem,branch}.jsonl`.

| branch or mutator | doc line | folders | MATCH/DIFF | first DIFF field | who is right |
|---|---|---|---|---|---|
| branch h1 | all docs | 300 | MATCH 300 | - | - |
| branch h2 | all docs | 300 | MATCH 300 | - | - |
| branch h3 | all docs | 300 | MATCH 300 | - | - |
| branch h4 | all docs | 300 | MATCH 300 | - | - |
| branch h5 | all docs | 300 | MATCH 300 | - | - |
| branch h6 | all docs | 300 | MATCH 300 | - | - |
| branch shipped | all docs | 300 | MATCH 300 | - | - |
| C_* layout equivalents (8: blankline, colorder, crlf, extra_col, jsonl_style, quoted, toml_style, types_extra) | data_conventions.md:45-46; data_conventions.md:9-16 | 768 | MATCH 768 | - | - |
| D_* Word markup equivalents (12: abs_target, bookmarks, decoy_table, extra_rels, header_spaces, prefix, rename_part, rowprops, sdt_run, sdt_tbl, split_runs, tracked) | data_conventions.md:20-23 | 1184 | MATCH 1184 | - | - |
| S_* value mutants inside documented ranges (22: avail_after_end, avail_before_start, avail_late_in, avail_own_out, calendar_random, closure_from_before, closure_outside, closure_past_end, due_far, dur1, empty_requests, grants0, grants_big, grants_rand, ids_varlen, pool0, pool_big, pool_small, pub_outside, rates_types, shift_cost, status_case) | data_conventions.md:31-32; data_conventions.md:51-53; data_conventions.md:54-56; output_schema.md; overtime_policy.md:14-24; overtime_policy.md:3-7; overtime_policy.md:9-10; planning_policy.md:22-29; planning_policy.md:24-25; planning_policy.md:28-29; planning_policy.md:30-31; planning_policy.md:36-41 | 264 | MATCH 255; SKIP 9 (id collision) | - | - |
| D_alt_allow | data_conventions.md:20-23; overtime_policy.md:14 | 96 | MATCH 0; DIFF 96 (W96 C0 T0) | summary.json.settlement.allowance_granted: 1348 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_alt_avail | data_conventions.md:20-23,51-53 | 96 | MATCH 46; DIFF 50 (W50 C0 T0) | summary.json.plan_terms.first: 826 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_alt_closure_days | data_conventions.md:20-23,54-55 | 96 | MATCH 1; DIFF 94 (W94 C0 T0); SKIP 1 | policy_audit.json.checks[22].deferral_reason: 'no_slot' vs 'plan_trade | reference (a1 misreads ECMA-376 markup) |
| D_altcontent | data_conventions.md:20-23 | 96 | MATCH 0; DIFF 96 (W0 C96 T0) | cannot use input file /tmp/fzu0mz7agj/d19/disruption_notice.docx: no t | reference; a1 stops (not a lever, Law 1) |
| D_altcontent_data | data_conventions.md:20-23 | 96 | MATCH 0; DIFF 96 (W1 C95 T0) | summary.json.plan_terms.first: 472 vs 726 | reference (a1 misreads ECMA-376 markup) |
| D_cellsdt_allow | data_conventions.md:20-23 | 103 | MATCH 0; DIFF 103 (W0 C103 T0) | KeyError: 'allowance_shifts' | reference; a1 stops (not a lever, Law 1) |
| D_cxml_row_allow | data_conventions.md:20-23; overtime_policy.md:14 | 103 | MATCH 0; DIFF 103 (W103 C0 T0) | summary.json.settlement.allowance_granted: 34 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_cxml_row_avail | data_conventions.md:20-23,51-53 | 103 | MATCH 58; DIFF 45 (W45 C0 T0) | summary.json.plan_terms.first: 824 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_cxml_row_closure | data_conventions.md:20-23,54-55 | 103 | MATCH 0; DIFF 102 (W102 C0 T0); SKIP 1 | summary.json.plan_terms.first: 660 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_dot_target | data_conventions.md:20-21 | 99 | MATCH 0; DIFF 99 (W0 C99 T0) | cannot use input file /tmp/fzu0mz7agj/d15/disruption_notice.docx: "The | reference; a1 stops (not a lever, Law 1) |
| D_sdt_allrows_allow | data_conventions.md:20-23; overtime_policy.md:14 | 102 | MATCH 0; DIFF 102 (W102 C0 T0) | summary.json.settlement.allowance_granted: 0 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_allow | data_conventions.md:20-23; overtime_policy.md:14 | 97 | MATCH 0; DIFF 97 (W97 C0 T0) | summary.json.settlement.allowance_granted: 35 vs 48 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_avail | data_conventions.md:20-23,51-53 | 99 | MATCH 64; DIFF 35 (W35 C0 T0) | summary.json.plan_terms.first: 826 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_class | data_conventions.md:15,20-23 | 101 | MATCH 4; DIFF 97 (W0 C97 T0) | cannot use input file /tmp/fzu0mz7agj/d4/planning_limits.docx: no clas | reference; a1 stops (not a lever, Law 1) |
| D_sdt_row_closure | data_conventions.md:20-23,54-55 | 98 | MATCH 0; DIFF 96 (W96 C0 T0); SKIP 2 | summary.json.plan_terms.first: 560 vs 820 | reference (a1 misreads ECMA-376 markup) |
| D_sdt_row_item | data_conventions.md:15,20-23 | 100 | MATCH 0; DIFF 100 (W0 C100 T0) | cannot use input file /tmp/fzu0mz7agj/d3/planning_limits.docx: missing | reference; a1 stops (not a lever, Law 1) |

Total folders: 5904 (branch 2100 + one rotating equivalence mutant on each branch folder 2100 + equiv 1320 + alt 120 + sem 264). Every generator branch MATCH 300/300.

Reference bug recorded (not a lever): blank lines or embedded newlines in check_requests.csv make the reference line number the record index + 1, while data_conventions.md:45 says file line number (a1 is right). No hidden folder contains blank lines; C_blankline scored a1 against the docs-right shifted lines (MATCH).
