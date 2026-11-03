SELF CHECK W1-006 (every cited line reopened from origin/main copies)

CONFIRMED
1. instruction.md:18 "every value is compared exactly"; line 20 holds the 25-minute and delta wording; line 24 asks for the status and split counts.
2. TRUTH.md:74 expected visible counts are train 23746, val 5760, test 7139, oot 11034. The agent's summary.json has 23240, 5720, 7837, 11072.
3. tests/test_output.py:35 EVAL_SEED; :121 _project; :186 _concept_ok; :208 all-records slice rule; :294 generator call build('P2', seed). The weights are at :657-691 (31 positive, total 149; negatives -18).
4. solution/solve.py:1689 parent = {}; :1691-1702 find and union (union writes only parent[rb]); :1717 components built from list(parent), which omits roots; :1725 cid.get(acc, acc) falls back to self.
5. Agent transform.py:2457 parent = {}; :2459-2460 find calls setdefault, so roots are included; :2486 cid = min(members) over the whole component.
6. split_and_leakage_policy.docx paragraph 3 (python-docx index 3) says "the cluster id is the smallest canonical account id of the component". Paragraph 1 says no cluster contributes to more than one of train, val and test.
7. reward-details.json: tests 4/149 (shape and HELD passed). Judge R4 = 0, R9 fired, and the judge score is 13.

HOW THE MAIN FINDING WAS CHECKED
1. Decoded SLICES from test_output.py and rebuilt the agent's per-record index with the test's own _sha and _canon logic.
2. Cluster rows in slices: 264. Rows that match the "root stays singleton, others take min of non-root" model: 261. Rows that match the policy's cluster id: 188.
3. Sliced examples: 8552. The agent matched 6037; after only re-clustering with that model and re-bucketing with the salt, 8127.
4. Every exclusion record that appears in a slice had the expected reason.

UNCONFIRMED
1. The reference could not be run here (pyarrow is missing locally), so the diff is inferred from digests, not from a full output comparison.
2. I did not trace the remaining 425 sliced example mismatches (approximate pin handling in my model, 2 label flips, others).
3. Hidden-tier failures are attributed to the same cluster rule by reasoning only; I did not run the generator.
4. "Builder ran in about one minute" comes from the agent's final message. The 79-minute run time comes from the trajectory timestamps (16:12 to 17:31).
5. I did not read the PDF documents, the charter prose in depth, or most of the data files.
