# QL QC report, round 2, district-heat-flex-procurement (pushed tree 2b289f9f9561, run a13 38.35)

Pasted by Ayush 29 Oct 12:17 IST. Verbatim, with ids QL2-F1..F15 added by the master in brackets.

## ❌ Fails

[QL2-F1] ❌ IN-16: summary.json event_count can be read two defensible ways, and the graded value contradicts the schema's own sum rule.
- Where: environment/data/schema.md L304-313 (with L280-285), tests/test_output.py L743, solution/solve.py L575.
- Schema evidence:
- L304 says "Keys: event_count, event_region_count, site_count (site rows), …".
- L308 says "All but the last two are totals over every event-region."
- L313 says "The global totals equal the sums over the region files and over the segment files."
- The region totals.event_count is "summed over the region's events entries" (L280-285), which is 500 per region. Summing the four region files therefore gives 2000.
- What is graded: test L743 sets summary.update(event_count=len(event_list), … and solve.py L575 sets "event_count": len(ex.events), so 500 is the graded value.
- Measured: a program that follows L313 fails summary_match (w3) with "wrong value: .event_count: expected 500, got 2000". It also fails summary_match_hard (w5) with "expected 26, got 104". That scores 229/237 = 0.966.
- Re-verified: twice, by reading the text and by the run.
- Bug/Error
- Fix: In schema.md §8.3, define event_count as the number of events in events.json and exclude it from the L313 "sums over the region files" sentence.

[QL2-F2] ❌ DS-24: the grader's ground truth for portfolio selection restates the oracle's search algorithm.
- Where: tests/test_output.py L455-533, against solution/solve.py L268-353.
- Truth path: bounded (test L455) is the truth solver, selected at L577: solver = search if lazy & SEARCH_FLAGS else bounded. It matches choose_portfolio step for step:
- The same twin classes, keyed on (relief, recovery, cost), with greatest id and multiplicity (test L466-475, solve L292-296).
- The same lane order by largest relief (L476-477, L296-297).
- The identical optimistic bound: min(caps[t][0], rel[t] + reach[i][t]) (test L494) against min(limit[t][0], relief[t] + top[rest][t]) (solve L315).
- The same strict cut: here > top["score"] (L502) against key > best["key"] (L324).
- The same tie count and max-id rule (L504-511, L326-332).
- Grants: _apportion (test L144-157) likewise restates largest_remainder (solve L383-393).
- What depends on it: the shared routine decides the graded value for these checks:
- selection, intervals, tie_decisions, segment_rows, ledger_quality, all totals and summary;
- all 16 wide checks (64 points).
- Why tests_qc missed it: its O1 line-overlap check reports 3%, because the code is paraphrased rather than copied.
- Mitigation measured: I patched the file's own merging-table search (L390) in as truth. It produced outputs identical to bounded on the shipped, H1 and H2 extracts. On the four wide extracts it had not finished after 43 minutes each, so the 64 wide points have no independent truth.
- Re-verified: twice, by side-by-side reading.
- Bug/Error
- Fix: Make the grader's truth an algorithmically different exact method, or rebuild the oracle's search on a different principle, then cross-check the two on every graded extract. One route is the existing merging-table search with wide extracts sized so it finishes.

[QL2-F3] ❌ TS-26: one observable, data_quality.unallocated_pool_count on the shipped run, is paid by two checks.
- Where: tests/test_output.py L1665, L1671-1673, L1643, L2204, L2264.
- Evidence:
- The quality_counts projection is lambda f: {k: v for k, v in f["data_quality.json"].items() if k not in QUALITY_LEDGER}. It excludes only ("allowance_blocked_offer_count", "empty_candidate_groups").
- The residual projection also includes "unallocated_pool_count": f["data_quality.json"]["unallocated_pool_count"].
- Both quality_counts_match (w3) and residual_match (w3) run on the shipped extract.
- Measured: setting unallocated_pool_count to +1 fails both checks with ".unallocated_pool_count: expected 89, got 90". With the hard twins added, one wrong count costs 16 points (221/237).
- Re-verified: twice, by reading the code and by the run.
- Bug/Error
- Fix: Add unallocated_pool_count to the keys the quality_counts projection excludes, so only the residual family grades it.

[QL2-F4] ❌ AL-2: two per-event fields in the region files are required by the rulebook but graded by no check.
- Fields: bid_cost_cents and compliance_counts in each region file's events entries.
- Where: environment/data/schema.md L272 and L278-279, instruction.md L7, tests/test_output.py L699 and L1654-1675.
- What the contract says:
- L272: "bid_cost_cents: the sum of the chosen offers' bid costs"
- L278-279: "compliance_counts: an object with all five labels as keys, counting the site rows of the event-region"
- instruction L7: "every value in it must be the one the rulebook defines".
- What the tests do: the reference builds these fields (L699 "compliance_counts": tally). No FAMILIES projection, wide view or mutation view compares them; the mutation _costs view is checked only on the reference side. The top-level region (L264) and segment name values are never compared either.
- Measured: I patched solve.py so every region file has all-zero per-event compliance_counts and bid_cost_cents set to 0. It passed all 47 positive non-wide checks and fired no negative. The wide checks project only selection, tie decisions and intervals. Result: 237/237 on the test channel.
- Re-verified: twice, by the FAMILIES read and by the run.
- Bug/Error
- Fix: Add a region_event_rows family (shipped w3 plus hard w5) that projects each region event's bid_cost_cents and compliance_counts.

[QL2-F5] ❌ CL-3: data_quality.json rows can be copied verbatim from export_manifest.tsv, so TRUTH's "(trap)" can never spring.
- Where: environment/data/export_manifest.tsv L2-3, tests/test_output.py L910 (_write_receipt), solution/TRUTH.md L57-58.
- Evidence:
- The manifest says "# Each line names a file and gives its records, counted the way data_quality.json counts the / # rows of that file."
- 13 of the 14 graded rows values equal the manifest records column exactly on shipped, H1 and H2, with zero differences. quality_counts_match (w3) and _hard (w5) grade them.
- _write_receipt writes an agreeing receipt for every generated extract.
- TRUTH L57-58 says "6. (trap) The export receipt … agrees with the files whatever reading a program takes". A program that copies from the receipt therefore scores identically, which is also a DS-22 failure: the bundle claims a trap that nothing can spring.
- Re-verified: twice, by computation and by reading the comment.
- Bug/Error
- Fix: Have _write_receipt emit, in the hidden extracts, a receipt whose records differ from the actual rows for at least one file, so copying records fails quality_counts_match_hard. Then reword TRUTH item 6 to describe that trap.

## 🟡 Minors

[QL2-F6] 🟡 DS-22: TRUTH says allowance_ticks_mutation grades the draws_from chains, but that mutation's extract has no draws_from rows.
- Where: solution/TRUTH.md L33-38, tests/test_output.py L1103-1124.
- Evidence: TRUTH says "Graded by selection_match_hard, … totals and allowance_ticks_mutation." The mut_allowance spec has no draws_from rows, and the CHAIN1 wrong reading does not separate that pair.
- Bug/Error
- Fix: Remove allowance_ticks_mutation from item 3's list, or plant a draws_from link in mut_allowance.

[QL2-F7] 🟡 AL-18: TRUTH calls every family's light check a shipped-data check, but tie_decisions_match runs on a generated extract.
- Where: solution/TRUTH.md L95-96, tests/test_output.py L2104-2105.
- Evidence: TRUTH says "twenty families, each a shipped-data check (w3)". In fact tie_decisions_match returns tie_case_passes(workspace) on the generated case_root("tie") extract. Shipped policy_audit.tie_decisions has 0 entries.
- Bug/Error
- Fix: Reword to "nineteen run on the shipped extract and tie_decisions_match on a generated tie extract".

[QL2-F8] 🟡 TS-13: canonical_serialization_and_integer_units grades two properties.
- Where: tests/test_output.py L1996.
- Evidence: the one w1 check asserts sorted keys and a trailing newline, and also asserts integer typing (no float, no bool, and every integer leaf of the reference is an int). These are two separate sentences in instruction L7.
- Suggestion/Improvement
- Fix: Split it into canonical_serialization and integer_units checks.

[QL2-F9] 🟡 TS-14: the name of negative_external_dependency_or_network promises a network check that the body never performs.
- Where: tests/test_output.py L2525-2539.
- Evidence: the body only compares imports against sys.stdlib_module_names. The description says "imports a module outside the Python 3.12 standard library."
- Bug/Error
- Fix: Rename it to negative_external_dependency.

## ⚠️ Warns

[QL2-F10] ⚠️ TS-23 (tests_qc A3): too many checks. tests/test_output.py L2542-2607 registers 66 checks; the cap is 35. Suggestion: fold each shipped/hard twin, or the four region_totals_*, into fewer checks.

[QL2-F11] ⚠️ IN-2: the instruction describes the grading, and describes it inaccurately. instruction.md L7 says "Each output document is graded whole on fresh inputs". In fact the checks grade per row family with partial credit; only summary.json is compared whole. Suggestion: "Every value in each output document must be the one the rulebook defines, on the shipped data and on any other extract."

[QL2-F12] ⚠️ JD-14: R3 and R12 pay twice for one constructed extract. In tests/judge.toml, R3 (L38-48) and R12 (L155-165) share a word-for-word construction clause, so one extract and one run earn 6 points. R12's hand count is 1 by construction; the observables differ, so this is not a fail. Suggestion: move R12 to the rate == cap boundary, where the expected count is 0.

[QL2-F13] ⚠️ JD-15: most of the judged channel rewards one specific set of self-tests.
- R1-R4, R8-R10 and R12 carry 24 of the 27 positive judged points (89%).
- Each prescribes one specific self-test scenario, and together they mirror solve.sh L233-516 one-to-one. solve.sh even prints "check R3 ok" and "check R12 ok".
- An agent that verifies by other equally strong means earns at most 3/27 judged points.
- These are odds-raising conduct criteria at w3, so they pass the gate; the concentration is the warn.

[QL2-F14] ⚠️ AL-19: the agent's program inherits the OpenAI key inside the verifier. At tests/test_output.py L1807, subprocess.Popen(_untrusted([...]), cwd=box, …) passes no env=. The program, running as nobody, therefore inherits OPENAI_API_KEY from task.toml [verifier.env], while the verifier allowlist reaches *.openai.com. Suggestion: pass a scrubbed env.

[QL2-F15] ⚠️ AL-27: some planted fixtures are dead or defused.
- case_spec "allowance_order" (test L1088) and "allowance_consumption" (L1103) are never planted (PLANTED L1159-1162) and never used.
- The planted tick_feasibility case was built for 10 Wh ticks, but H1's program.ini draws wh_per_tick = 25, which defuses it.
- The tick-quantised feasibility rule is therefore graded only by the wide checks. Computing in Wh changes 33/80, 19/80, 24/80 and 13/80 wide selections, so it is still graded.

[QL2-F16] ⚠️ AL-7: TRUTH contradicts itself on whether the oracle score was measured. solution/TRUTH.md L130 says "Measured in Docker (tests channel, stub rewardkit, 2 CPU) … the oracle scores 237". L232 says golden_score_measured: null  # no Harbor run recorded in this file, and L238 says "Not measured here." Both are scoped to the test channel; the prose is inconsistent.

[QL2-F17] ⚠️ DS-22: TRUTH describes the search bound too narrowly. solution/TRUTH.md L181-182 says the search stops a branch "once a lower bound on components 1 and 2 … is already worse". The bound in solve.py L315-324 covers the whole five-component key.
