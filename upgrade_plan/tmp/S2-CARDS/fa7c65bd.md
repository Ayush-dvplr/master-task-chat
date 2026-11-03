TASK: fa7c65bd-ff01-50e7-b3ba-34fbd5df860d, Data Processing (spectrum clearing over revisioned grants, half-open time by frequency by cell slices, guard bands, exclusions, primary preemption, half-up money and signed largest remainder, nine JSON reports plus program), Opus tests 23.08, rubric 21.43, final 22.25.

1. VERDICT: DEFECT, about 100 percent of lost test weight (40 of 52 positive weight), confidence medium. One located divergence is an output schema the contract never states; it alone breaks grant_ledger.json in every scenario, so every whole-bundle digest fails. Further hidden divergences in slices or money cannot be excluded without rerunning.

2. LOSSES:
1. Eight fresh scenario checks, weight 5 each, 40 in all (revision cells order, revision scalar conflict, activation identifier, half-open boundary, guard abutment, correction tie, half-up midpoint, exclusion span). Each compares one SHA-256 over all nine reports. Cause: WRONG output. No crash, no timeout.
2. Passed: artifact set 1, canonical serialization 3, local safe source 3, determinism and no mutation 5 (12 of 52). No negative fired.

3. DIFFICULTY KIND: not applicable for the located loss (DEFECT). The scenario names target real design levers (set-valued cells in tie comparison, half-open abutment, guard shrinkage, signed residual ties, exact half), but the digest makes them unobservable once one shared report differs.

4. EVIDENCE:
1. Contract: environment/data/schema.md:53 gives grant_ledger.json as {effective_grants,revision_decisions} and lists the fields of decisions only; no line lists the fields of an effective grant. TRUTH.md calls them "effective, clipped grant facts".
2. Reference: solution/solve.py:126-133 appends the raw winning input row unchanged, so each effective grant carries revision, recorded_at and status as well, with cells in input order and the interval not clipped.
3. Agent: clear_spectrum.py:927-940 emits eleven chosen fields (grant_id, record_id, license_id, party_id, cells, low_khz, high_khz, start, end, priority, share_bps), without revision, recorded_at, status. grant_ledger.json therefore differs in every scenario, and tests/test_output.py:283-299 hashes all nine reports together.
4. The wrapper keys exceptions (exception_register) and entries (audit_trace) are also not named in schema.md:57-59; the agent guessed them the same as solve.py:322-323, so they did not cost points here, but they are the same kind of gap.

5. TEST DESIGN: one fixed base corpus embedded as zlib blobs, plus eight hand-written edits, one per documented interaction (test_output.py:76-182). Program run as nobody with stale outputs pre-written and a 120 second limit. Comparison is one digest over the whole nine-report bundle per scenario, against precomputed hashes. Amplification: total, any byte anywhere fails the scenario. Negatives: source string scans for visible identifiers, grader paths, network or subprocess.

6. INSTRUCTION: "Read the complete contract in /app/data/schema.md. It defines ... every output schema"; "write these deterministic reports"; "The reusable program is also executed on fresh extracts that exercise documented interactions"; 7200 seconds; stdlib only. Not said: the effective grant field list, the wrapper keys of two reports, or that grading is one digest per scenario over all reports.

7. RUBRIC: lost R2 to R11 (each wanted explicit assertions against independently calculated expectations; the agent ran fixtures and read outputs but asserted little), passed R1, R12, R13, R14. No penalty fired.

8. REUSABLE IDEA: none for the located loss. Design lessons kept: a whole-bundle digest turns any undocumented field into a total loss, so every emitted field must be listed in the contract; per-scenario edits that each touch one documented interaction are a clean way to target levers, if graded per report or per field.
