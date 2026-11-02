Hi Sugam,

Thank you for the second review of **district-heat-flex-procurement** (your report of 29 Oct 2026). Here is what we found for each point.

| # | Your point (short) | Our verdict | Evidence | What changed |
|---|---|---|---|---|
| F1 | `summary.json` `event_count` reads two ways (500 vs 2000) | Fixed | IN-16 "No significant ambiguity in anything that is graded" (01_Instruction_QC.md:46); schema.md:309 and :313 allowed both readings | schema.md:309-317 now says `event_count` is the number of events in `events.json`, each counted once, and the sum sentence names the keys it covers and says `event_count` is not such a sum. The graded value (500) is unchanged |
| F2 | Grader's portfolio truth restates the oracle's search | Fixed | DS-24 "The oracle is an independent implementation, not a copy of the verifier" (02_Data_Solution_QC.md:69); test_output.py:455 `bounded` matched solve.py:268-353 | `bounded` removed. The grader now uses its own exact method (a layered state table over sites, no shared bound or cut). It runs live on the shipped data and both hidden extracts; for the four wide extracts its optima were computed once and stored. It agrees with the old truth and the oracle on all 320 event-regions. Wide inputs, their points and the 120 s limit are unchanged |
| F3 | Shipped `unallocated_pool_count` paid by two checks | Fixed | TS-26 (03_Tests_QC.md:53); test_output.py:1665 | The shipped `quality_counts_match` projection no longer includes that key; `residual_match` owns it. The two hard checks stay, because they read different extracts (H1 vs H2). No weight moved |
| F4 | Per-event `bid_cost_cents` and `compliance_counts` never graded | Fixed | AL-2 "Everything promised is graded" (05_Alignment_Integrity_QC.md:33); zeroing both fields scored 237/237 | Two separate checks (one per field, so TS-13 holds): shipped (w3), H1 (w5) and each wide extract (w1). Test points 237 → 261; reward.toml normaliser updated. Zeroed values now fail |
| F5 | `data_quality.json` row counts copyable from `export_manifest.tsv` | Fixed, by a different route | CL-3 "The graded answer is earned, not copied" (Final_checklist.md:490); 13 of 14 row counts matched the receipt | The `records` column is removed from the shipped receipt and from the hidden-extract generator. The receipt now lists file, field and field sum, which stay true. We did not use the suggested false counts, because shipped data must not contain wrong values. schema.md:101-104 and TRUTH.md:57-58 updated |
| F6 | TRUTH says `allowance_ticks_mutation` grades `draws_from` chains | Fixed | DS-22 "TRUTH.md describes the bundle that actually shipped" (02_Data_Solution_QC.md:78); that extract has no `draws_from` rows | Removed from the list in TRUTH.md:32-38 |
| F7 | TRUTH calls every light check a shipped-data check | Fixed | AL-18 (05_Alignment_Integrity_QC.md:75); `tie_decisions_match` runs on a generated extract (test_output.py:2103-2105) | TRUTH.md:96-98 now names that exception |
| F8 | `canonical_serialization_and_integer_units` grades two properties | Not changed: this is how the rule reads | TS-13 (03_Tests_QC.md:44); test_output.py:1995-2014 grades one property, the JSON encoding contract | none |
| F9 | `negative_external_dependency_or_network` name promises a network check | Not changed: accepted earlier | TS-14 (03_Tests_QC.md:45); same warning recorded in the previous QC and accepted in round 1 (F10) | none |
| F10 | Too many checks (66) | Not changed | TS-23 is a warning; no check-count cap applies to this task set, and merging checks to cut the count would mix properties | none (now 78 checks after F4) |
| F11 | Instruction describes the grading | Not changed: this is how the rule reads | IN-2 allows stating WHAT the work is judged on (01_Instruction_QC.md:32); instruction.md:7 says values must match the rulebook on fresh inputs and names no test, weight or credit mechanism | none |
| F12 | R3 and R12 pay twice for one extract | Not changed | JD-14: different facets are not a duplicate (04_Judge_QC.md:91); your report also notes the observables differ (credit_cents vs cap_binding_count) | none |
| F13 | Judge concentrates on one set of self-tests | Not changed | JD-15 allows conduct criteria that raise the odds of a correct result (04_Judge_QC.md:92, :139); your report notes they pass | none |
| F14 | Agent program inherits the OpenAI key in the verifier | Not changed | AL-19 (05_Alignment_Integrity_QC.md:65): the bundle reads and ships no credential; the inherited value is the pinned placeholder | none |
| F15 | Dead or defused planted fixtures | Fixed | AL-27 (05_Alignment_Integrity_QC.md:38); `allowance_order` and `allowance_consumption` (test_output.py:1086-1106) were never built; H1 never used 10 Wh ticks | Both unused specs deleted; start-instant ordering stays graded by the `mut_allowance` pair. The H1 selection guards now include the Wh-feasibility reading, so the chosen hidden seed exercises it |
| F16 | TRUTH contradicts itself on whether the oracle score was measured | Not changed | AL-7 (05_Alignment_Integrity_QC.md:43); TRUTH.md:130 is a marked test-channel figure, :232 is the full-run score, and :238 says exactly that | none |
| F17 | TRUTH describes the search bound too narrowly | Fixed | DS-22 (02_Data_Solution_QC.md:78); solve.py:310-326 bounds on all five parts | TRUTH.md:191 now describes the five-part key as the code does |

**Checks after the changes:** local QC scripts clean; reference solution 1.0 (3 runs); owner-only 1.0; empty submission 0.0; full recheck QC v11 PASS (0 fails, 0 minors, 0 warnings).

**New run** (29 Oct 2026, same files as delivered): tests 72.41, rubric -7.41, final 32.5. The delivered package is updated.

**Files delivered:** same folder as before, version `9d1e071a5792`.

If you see any of the "not changed" points differently, please tell us which rule line you read, and we will look again.

Regards,
Ayush
