# B: sentinel-fraud-training-release (Phase A verdict GENUINE, amplified by whole-population projection digests)

Run: overall 19.76, tests 2.68 (4/149), rubric 36.84 (14/38).
- The tests store digests only, and the oracle cannot run locally (`ModuleNotFoundError: pypdf`; no pip allowed).
- Value-level evidence is therefore limited to comparing the agent's aggregates with TRUTH.md's measured release (TRUTH:72-75). Specific rule misses are INFERRED.

## 1. Inventory
- Domain: card-fraud ML training-set release. Six transaction systems; labels from cases, chargebacks and vendor votes; point-in-time (PIT) merchant and IP features; leakage-safe cluster splits; train-only preprocessing; a publication gate.
- Archetype: a reusable builder `/app/out/transform.py DATA OUT [--prior]` plus 13 outputs (normalized.jsonl, 3 summaries, 5 region and 4 segment slice reports). A hidden delta release runs with `--prior`.
- Agent sees 100 files, 52 MB in total:
  - month-partitioned exports in tsv, csv, xml, jsonl, txt fixed-width, parquet, xlsx, sqlite, mbox, ics, html, yaml, ini;
  - look-alikes: `_replay`, `_final`, `_resend`, `_dedup`, `_v2`, `_replica`, `_relabel`, `rev2`, `_consolidated`;
  - `source_register.md` (6,000+ lines), `data_dictionary.md` (5,300+ lines), `release_build_specification.docx`, a governance charter, label policies v3/v4, `split_and_leakage_policy.docx`, feature availability spec + rev2, handbooks (pdf);
  - `lineage_controls_2026-09.db` with partition counts and hash totals.
- instruction.md: 367 words.
- Tests: 35 checks: 31 positive worth 149 and 4 negative worth -18.
  - 10 concept projections × 5;
  - 13 trap-family slices × 5 (some merge families: t2_t4_t12, t8_t9);
  - 4 decoy groups × 5;
  - 2 hidden delta × 5;
  - HELD × 3 and shape × 1.
- Isolation is poor:
  - each concept hashes a projection over ALL released examples sorted by example_id (test_output.py:121-149);
  - slices are per-record digests with the train-fitted fields left out, all-or-nothing per slice (:152-212).
  - One membership error therefore fails most concepts at once.
- Hidden inputs: YES. TR-2027.01 is regenerated with EVAL_SEED 9917353 and run as uid 65534 with a 1,500 s limit. The HELD run drops one chargeback file.
- Judge: 11 criteria, `mode = "individual"`, 1/38 per point.

## 2. Rule map (main graded rules)
| rule | where stated | form | trap explained? | data separates? |
|---|---|---|---|---|
| Event dedup and partition controls across 6 systems with 6 time encodings | source_register + data_dictionary + timezone handbook (pdf) | split across files; the encoding is in data headers | no | yes |
| Look-alike export authority by charter windows (replay, final, resend) | governance charter table (agent extracted charter.tsv, steps 27-31) | table rows with date windows | no | yes |
| Labels: analyst cases + 3 chargeback networks + weighted vendor votes; immature labels censored, but analyst-confirmed fraud is exempt | label_policy_v4.docx (v3 is a decoy) | default + exception; v3/v4 versioning | no | yes |
| PIT availability = publication instant + lag, not snapshot `as_of`; outages shift publication; lag overrides | feature_availability_spec.pdf + rev2 (rev2 limited by charter) + publication calendar ics + overrides csv | 4-file composition; the "obvious" column is a decoy | the spec defines availability; the trap is not named | yes |
| Cluster split: link = earliest of LINK event or fingerprint first_seen at or before cutoff; ends at a later UNLINK or the latest revocation action = revoke; kiosk and listed devices are exempt; canonicalise merge chains first; cluster id = min account; bucket = sha256(salt:cluster) mod 100; active test pin beats val pin; the prior split outranks pins; oot by event_time | split_and_leakage_policy.docx, one dense paragraph plus an exemption table of hundreds of rows | stacked constraints (E) + state history (C) | no; the "obvious" union-find over all devices is the drift (TRUTH item 12) | yes |
| Robust scaling with nearest-rank quantiles; effective-number class weights | spec | one sentence each, the drift from a familiar default | no | yes (fit on train) |
| Publication gate: HELD when the controls of any of the 100 files mismatch or a file is missing | spec + lineage db | plain | yes | the agent passed it |

## 3. Lever table (failed)
TRUTH measured release vs the agent (summary.json): train 23,746 vs 23,240, val 5,760 vs 5,720, test 7,139 vs 7,837, oot 11,034 vs 11,072; total released 47,679 vs 47,869 (+190).
- Both example membership and the cluster→split assignment are wrong.
- Test +698 together with train -506 points to cluster linking or pins (INFERRED).
- Code-reading candidates (INFERRED, not proven):
  - transform.py:2450-2452 keeps one max UNLINK per link, so re-link sequences (LINK→UNLINK→LINK) are mishandled;
  - :2510-2525 lets a non-test/val pin value override the bucket.

| id | weight | rule | mechanism | self-test catches? | fully stated? | family |
|---|---|---|---|---|---|---|
| point_in_time_features, labels, exclusion_register, source_manifest, cluster_splits, preprocessing_state, class_weights, categorical_vocab, scores_auc_psi, slice_reports (concepts) | 10×5 = 50 | per-concept projection over all examples | one wrong released set (+190) or one wrong split changes every concept's projection; the train-only fit propagates split errors into preprocessing, vocab, class weights and scores (TRUTH:59 "each feeding the next") | N: the agent's one value check was the lineage controls DB (step 118 "all ok True"). It verifies parsing (row counts, hash totals per partition), not label, PIT or split semantics. | yes (TRUTH:5) | B chain + E |
| slice_t1..t16 (13 checks) | 65 | per trap family | per-record digests; a split, label or feature error on any record in the family fails the slice | N | yes | A/C/D/E per family |
| decoy groups (4) | 20 | look-alike sources | per-record digests of records that the decoy would change | N | yes | D |
| eval_delta_examples / state_and_exclusions | 10 | hidden delta from the agent's own prior | dependent chain: the prior split "outranks pins", so visible split errors are inherited | N | yes | B + C |
| Judge R3 (3) | 3 | per-export reconciliation, each candidate released or exactly one exclusion | the agent checked only the aggregate identity 114,992 - 47,869 = 67,123 | — | yes | conduct |
| Judge R4 (3) | 3 | explicit check that a cluster sits in at most one split | not done | — | yes | conduct |
| Judge R9 (neg -3) | -3 | false claim | claimed the HELD path was exercised with a missing catalog file, but only a HELD *prior* was tested (step 170) | — | yes | conduct |
| Judge R11 (3) | 3 | code quality | opaque names; `parse_event_file` silently returns [] for an unknown family | — | yes | — |

## 4. Contrast (passed)
- Tests:
  - shape (1);
  - `held_release_when_catalog_file_missing` (3): the gate rule is a plain sentence, binary and visible.
- Judge passed:
  - R1, compare parsed exports with lineage-control partitions (the agent's main habit);
  - R2, charter windows for look-alikes;
  - R5, ran twice and compared (steps 146-148 found one differing example, merchant_cb_rate_bps, and investigated it in steps 150-166);
  - R6, reported status and split counts.
- As in our DIAGNOSIS, the binary gate and the format leaked.
- Here the semantic layer (labels, PIT, splits) sits behind a composition of 3-5 documents per concept, and the shipped "control" artefact (the lineage DB) validates only the layer *beneath* the graded semantics. Self-tests went green while the graded values were wrong.

## 5. Agent behaviour
- 183 steps, about 79 min, $33.80.
- Dumped every docx and pdf to text (steps 4-8, 21-24). Partly read the register and data dictionary with head/sed and section greps (steps 9-14).
- Inspected each family (16-93). Wrote `readers.py` (76) and transform.py (94-96). First run at step 100.
- About 40 patch steps followed. Each was driven by a control-DB mismatch or by a spot inspection of a footnote, errata or calendar row.
- Determinism diff at steps 146-148. HELD test with a prior at step 170. Final at 176-182.
- It never computed an independent check of split membership, label maturity or PIT on sample records against the policy text.
- Final claim: "PUBLISHED" with confident counts (step 182). Reality: 2.68% on tests.

## 6. Test design
- Expected values: digests from the oracle at build time (visible) and regenerated with EVAL_SEED (hidden).
- `_canon` sorts keys, so the agent's key order is irrelevant: pure value grading.
- Partial credit by slice and concept, all-or-nothing within each.
- Negatives:
  - hardcoded: fires when the visible output is exact but the hidden run gives under 5% of the expected rows;
  - filename, reads_corpus, nondeterministic.
- Shipped-data weight: 136/149. Hidden: 13.
- No failure messages.

## 7. Judge design
- Reusable patterns:
  - R3, "every candidate record is accounted for exactly once (released or one exclusion)", is a strong conservation-check habit criterion;
  - R4, an explicit leakage invariant check.
  - Both are process criteria that read the trajectory, so they are distinct from the test observables (JD-8 ok).
- R9 (false claim) is good conduct design.
- JD-18: R11.

## 8. QC safety
| lever | IN-15 | TS-13/TS-26 | TS-16 | TS-19 | TS-20 | AL-28 | verdict |
|---|---|---|---|---|---|---|---|
| Multi-document composition per concept (PIT = publication + lag + outage + override) | stated across 4 files | ok | — | ok | ok | — | SAFE |
| Stacked split rule with a state history (link/unlink/revoke, pins, prior outranks pins) | stated | ok | — | ok | ok | — | SAFE |
| Control artefact that validates only the layer below the graded semantics (green self-test bait) | n/a (data design) | — | — | — | — | — | SAFE |
| Projection over all records per concept (10 concepts all moved by one membership error) | — | RISKY: same observable (released set) paid ~10× (:53) | — | — | — | — | RISKY |
| Train-fitted downstream values (one split error moves scaling, vocab, weights, AUC) | stated | RISKY (cascade double-pay) | — | ok | ok | — | RISKY |

## 9. Writing style
- "Sources disagree in places; the governance charter and the topical policies decide which source governs, and some files that look authoritative are not." (instruction.md). Technique: announce that conflict exists and name the arbiter, without naming any conflict.
- "the policies, standards, handbooks, registers and logs that the specification and the register point to are part of the same contract" (instruction.md). Technique: a transitive scope, so the agent must follow references to find the full rule set.
- "A link (account, device) exists from its LINK event ... or its first_seen ..., whichever is earlier, provided that time is at or before the label cutoff. It ends at a later UNLINK ..., or when the latest action in the revocation file at or before the cutoff is revoke (restore and confirm keep it)." (split_and_leakage_policy.docx). Technique: one sentence chain carrying 5 conditions from 3 sources; fully stated, not obviously a trap.
- "this outranks pins" / "Independently of the cluster split, an example whose event_time is at or after oot_start is in split oot." Technique: precedence stated as an aside after the main rule.
