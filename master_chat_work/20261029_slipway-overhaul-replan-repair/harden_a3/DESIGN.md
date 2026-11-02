# DESIGN e2bfbf0 slipway-overhaul-replan-repair: NO CORE

Tree 62dbcde0c809 (unchanged; no BUNDLE edit made). QC kit HEAD 5574d77e. Fingerprints QC 12/12,
GEN 160/160 equal. Evidence: TRIP.md (this folder), WORK/KILL_TEST.md, WORK/proto/diag_a3*,
WORK/proto/variants.log.

## Why a3 scored 72.06 on tests
All 19 lost points are two reference/document disputes, not a3 errors (TRIP.md section 1):
- Q1 (graph 3, audit 3, probe_publication 3): spec_stage_p02_precedence_graph.md:20-23 rejects the
  lodgements naming a cycle job under EDG-UNKNOWNJOB; the reference drops them from 02 and 19.
- Q2 (eval_state 5, challenge_state 5): top-level `weighted_resource` of 11/18. Reference sums the
  twelve-place precinct strings; a3 rounds the exact rational sum. output_schema_reference.md:68
  names the key only; p10:24-26 says exact rational published to twelve places.
Settled for the documents, a3 = 68/68.

## Arithmetic for the bar
a3 program <= 60 needs N new lever points it fails with 49/(68+N) <= 0.60, N >= 14, every one
on a doc-backed WRONG. Lever share >= 40% needs (21+N)/(68+N) >= 0.40, already met at N >= 0.
Final < 40 with a3 tests 72.06 needs rubric < 8; a probe-band judge predicts a3 about 46 and
peer mid about 38 (below), so the test channel must fall too.

## Try 1: held-out seeds through write_corpus / _corpus / _reference (note 2b, G7-safe)
The generator is fixed-structure: mint (test_output.py l823) always builds the same six precinct
shapes, edges, groups GRP-201..208, rules CCR-301..308, and `_amendments` (l1398) the same 19
amendments; seeds move numbers only. Measured on 4 existing + 20 fresh seeds (13 abort in
write_corpus: SystemExit "no precinct was seated on a level charge"): a3 is EXACT on every
document of every buildable seed except Q1 (every seed) and Q2 (11 or 18 on 5 of 7 seeds).
Doc-backed lever points a3 loses: 0. Reference 0.05-0.12 s per corpus, engine 0.2-0.7 s, so no
v3.5 hidden-scale lever (and no engine runtime sentence is stated anywhere).

## Try 2: stated invocation variants via own program calls
Relative paths, spaces, read-only papers, stale out dir, cwd inside the papers, trailing slashes
(instruction: either order, create destination, path-independent, leave papers unchanged):
a3 rc 0 on 14 runs, outputs identical to its plain run. Lever points lost: 0. These rules are
also self-testable (LEAK_LIBRARY), and a3 did test them (steps 75, 96).

## Rejected candidates
- Build levers on Q1/Q2: a3 fails them on every seed, but each rests on a reference that
  contradicts (Q1) or is not fixed by (Q2, G1) the documents. QC would strike them; fixing the
  documents makes them stated, self-testable rules. Not a lever in any honest form.
- `inert` when a governed kind seeds nothing (class_rate_revision of an empty class): instruction
  line 21 defines inert as "reaching no cell", which favours a3 over the reference (l2890-2892).
- aliases_active, memo sitting, reversal of edge_lodged, SELF before UNKNOWNJOB on lodged edges:
  a3 is the more document-faithful side; the generator never fires them.
- New shapes (new mint family, extended reference): forbidden by note 5 / G7 (existing check
  bodies byte-identical, diff only registrations, seeds, weights) and a3 handles them more
  generally than the reference does.

## Judge channel (for the record; not built)
Probe band on the a3 trajectory: P-f broken tool first (step 36) pass, P-c outside recompute
(steps 78-80) pass, P-e relocated rerun (step 75) pass; P-d altered copy, P-h missing/malformed
input, P-g tie witness (R10 lost), P-a edge input: not done. With 10 probes w3 + J4 + J6 + J10:
a3 about 46%, peer mid about 38. Today 28 criteria, R6-R19 (47 pts) restate the 15 repairs that the
tests and negative detectors already grade (JD-8), and J3a/b/c and J4 are absent (QC_RISKS.md).
Predicted final with the judge alone: (72.06 + 38)/2 = 55; with Q1/Q2 settled: (100 + 38)/2 = 69.

## Verdict
NO CORE: no doc-backed behaviour reachable through the existing generator families or stated
invocations separates a3 from the reference; a3 program keeps every non-disputed lever point
(two tries measured, WORK/KILL_TEST.md). Hardening needs a new generator family with a reference
for quiet p13 branches (reversal of a lodged edge, restatement of a non-charge kind, supplement
completion), which note 5 forbids, plus a ruling on Q1/Q2 first.
