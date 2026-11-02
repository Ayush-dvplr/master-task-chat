# TRUTH.md - a710b00e-a841-592d-bcbc-5a51d2b0439c

## Defect

The task is exact telemetry reconciliation across four processing lanes. North
uses recovered per-epoch calibration and historical identities; East attributes
shared observations; South settles nonlinear stream state; West reconciles late
amendments against an ordered fold. Their reports are linked by a conservation
adjustment, and every numerical field follows from the visible extract.

1. (focal) Source clock settings are variables in modular equations, not metadata
   to copy from one record. `corpus_00_policy_audit` observes the final settings;
   `corpus_00_region_north` observes the state they induce.
2. (focal) A valid allocation selects one candidate per group and exactly covers
   each component's required atoms. Candidate identities, rather than resulting
   totals, determine uniqueness. `reject_ambiguous_allocation` rejects two covers
   with equal values; `corpus_00_region_east` checks the derived credits.
3. (focal) An amendment can replace a node transform and exchange a forest edge.
   Its state is the directional affine fold over an arbitrary dynamic-tree path,
   not the amended record's local result. `corpus_00_region_west` checks the terminal and
   weighted states; `corpus_00_data_quality` checks the entire history.
4. (drift) Captured selects an epoch, while corrected instant selects an alias
   interval. Substituting one operand for the other changes historical identity
   and chronological state. `corpus_01_region_north` covers those distinctions.
5. (trap) Empty atom sets are genuine empty sets. Two groups can both select an
   empty set because neither consumes an atom. `empty_atom_allocation` checks a
   unique empty-set assignment rather than treating the empty cell as an atom.
6. (trap) Orphan and superseded amendments retain the previous path-fold state
   and still contribute it to weighted_states. `corpus_00_region_west` observes
   the weighted contribution; integer amendment order resolves tied arrivals.
7. (trap) South's pair changes simultaneously, and zero rounds retains its
   initial pair. `corpus_00_region_south` checks the settled stream records.

The reference uses the Python standard library. Every assignment is validated
before report publication. Error exits precede all report writes. Ordinary
execution accepts DATA_DIR OUT_DIR; verification execution also runs the eight
changed copies, reads back the reports and observes actual file opens.

Out of bounds: copied instance reports, runtime reads outside allowed locations,
third-party dependencies, network connections, child processes, input changes,
output writes outside OUT_DIR, and interference with inherited runtime auditing.
Each runtime act has an explicit contract sentence and its own negative check.

### Hidden-only behaviour

clock.md allows offsets to differ between epochs. dictionary.md selects them
using captured and half-open epoch intervals. The supplied extract has one epoch;
generated extracts have three or four, with independent modular evidence in each.
A chronologically last epoch can be empty of events but still supplies the audit's
final offset. Identity applicability instead uses corrected event instant.
Generated cases also include empty lanes, zero-round streams, equality at the
eligibility boundary, negative source units, non-ASCII account text, invalid
candidate atoms, revision statuses absent from the supplied extract, and
thousands of valid forest edge swaps with directional path queries.

## Load-bearing work

There are ten collected artifacts: derive_report.py and nine JSON reports.
summary.json reconciles four terminal lane figures. policy_audit.json carries
last-epoch offsets, identity quantities and weighted North state. data_quality.json
carries every amendment's status and path-fold state. The four region files
carry lane populations and terminal aggregates. segment_commercial.json aggregates
East credit by account; segment_public.json aggregates and filters South streams.
reports.md defines every key, number form, ordering and canonical JSON byte.

The load-bearing concepts are modular calibration, independent collector time,
historical alias intervals, chronological state replay, scoped exact-cover
attribution, simultaneous recurrence, Fibonacci exponent reduction, revision
precedence, dynamic-forest connectivity, directional affine path composition,
signed quantities, and cross-artifact reconciliation.

Dependency graph: source terms + equation residues + epochs -> offset vector;
events + offsets + alias intervals -> normalized chronological events -> North
state and identity audit. Group scopes + candidate sets -> unique attribution;
requests + attribution -> credits -> East and commercial. Stream inputs -> settled
pairs -> South and public. Records + accepted edge exchanges + directed path
queries -> current forest path fold and amendment history -> West and quality. Regional valuation, identity quantities
and commercial credits -> summary total and signed residual.

Stages: interpret the contract; solve epoch evidence; resolve applicability;
normalize identities and units; order events; fold North state; establish unique
allocation; aggregate credits; settle stream pairs; evaluate eligibility; resolve
revision history; maintain dynamic-tree connectivity and both directions of each
path aggregate; accumulate weighted history; reconcile terminal values; publish
exact bytes. The four state paths are separate.

### Input inventory

| File | Format | Lines | Unique fact and dependency | Necessity |
|---|---|---:|---|---|
| aliases.csv | CSV | 2 | Historical identity by alias and corrected instant | absence prevents derivation |
| allocation_candidates.csv | CSV | 247105 | Candidate sets and values by board/component/group | absence prevents derivation |
| allocation_groups.csv | CSV | 6337 | Required atom union and group membership by component | absence prevents derivation |
| allocation_requests.csv | CSV | 6337 | Signed requests and account membership by board/group | absence prevents derivation |
| clock_residues.csv | CSV | 5 | Observed remainders by epoch/equation | absence prevents derivation |
| clock_terms.csv | CSV | 17 | Coefficients by epoch/equation/source | absence prevents derivation |
| cycles.csv | CSV | 4 | Initial pairs, recurrence parameters, rounds and quantities | absence prevents derivation |
| epochs.csv | CSV | 2 | Half-open captured-time applicability intervals | absence prevents derivation |
| events.csv | CSV | 61 | Observed stamps and unit quantities joined to sources and aliases | absence prevents derivation |
| fold_corrections.csv | CSV | 13 | Arrival-ordered revisions, edge exchanges and path queries | absence prevents derivation |
| fold_records.csv | CSV | 31 | Initial dynamic-tree path nodes and affine transforms | absence prevents derivation |
| policy.json | JSON | 1 | Report identity, North recurrence and eligibility threshold | absence prevents derivation |
| replay.json | JSON | 1 | West modulus and initial value | absence prevents derivation |
| sources.csv | CSV | 5 | Source identity and signed unit numerator | absence prevents derivation |

The six contracts are schema.md, clock.md, dictionary.md, allocation.md,
replay.md and reports.md. Every non-Markdown input is named by a contract.

## Verification

The test channel uses rewardkit criteria. Hidden report-content checks compare
the complete parsed JSON value with exact recursive types, keys and array order.
A separate weight-1 check per extract enforces all nine canonical JSON byte forms;
the nine supplied-report checks also enforce canonical bytes. Thus a single
serialization mistake costs only the dedicated format checks, while every
substantive report remains independently scored. The verifier's trusted
calculation is independent of solution/solve.py. Agent code is executed as a
subprocess and is never imported. Each call has its own 60-second timeout.

Channel A has 235 checks, positive total 899 and negative total -36.
EASY total 17; HARD total 882; EASY ratio 17/899 = 0.01890990; corpus share 882/899 = 98.10901001%.
A lane-specific rule affects its two reports plus summary, 231/899 = 25.69521691% of positive weight. One altered weight-5 report costs 5/899; one altered summary costs 1/899. The cross-cutting canonical-serialization rule controls only 30/899 = 3.33704116%, below 30 percent.

There are twenty-one generated extracts, each checked separately per report,
plus one weight-1 canonical-byte check for the extract. The summary content check
weighs 1; the other eight weigh 5. Supplied reports weigh 1. Separate
fixtures execute empty/ambiguous evidence, an absent requested group and empty
atom allocation. The maximum fixture reaches all declared population bounds. No supplied report or figure is treated as proof of correctness
for a different extract. Settings occur only within the audit's full report check.

### Test registrations

- `visible_summary` (weight 1)
- `visible_policy_audit` (weight 1)
- `visible_data_quality` (weight 1)
- `visible_region_north` (weight 1)
- `visible_region_south` (weight 1)
- `visible_region_west` (weight 1)
- `visible_region_east` (weight 1)
- `visible_segment_commercial` (weight 1)
- `visible_segment_public` (weight 1)
- `corpus_00_summary` (weight 1)
- `corpus_00_policy_audit` (weight 5)
- `corpus_00_data_quality` (weight 5)
- `corpus_00_region_north` (weight 5)
- `corpus_00_region_south` (weight 5)
- `corpus_00_region_west` (weight 5)
- `corpus_00_region_east` (weight 5)
- `corpus_00_segment_commercial` (weight 5)
- `corpus_00_segment_public` (weight 5)
- `corpus_00_canonical_bytes` (weight 1)
- `corpus_01_summary` (weight 1)
- `corpus_01_policy_audit` (weight 5)
- `corpus_01_data_quality` (weight 5)
- `corpus_01_region_north` (weight 5)
- `corpus_01_region_south` (weight 5)
- `corpus_01_region_west` (weight 5)
- `corpus_01_region_east` (weight 5)
- `corpus_01_segment_commercial` (weight 5)
- `corpus_01_segment_public` (weight 5)
- `corpus_01_canonical_bytes` (weight 1)
- `corpus_02_summary` (weight 1)
- `corpus_02_policy_audit` (weight 5)
- `corpus_02_data_quality` (weight 5)
- `corpus_02_region_north` (weight 5)
- `corpus_02_region_south` (weight 5)
- `corpus_02_region_west` (weight 5)
- `corpus_02_region_east` (weight 5)
- `corpus_02_segment_commercial` (weight 5)
- `corpus_02_segment_public` (weight 5)
- `corpus_02_canonical_bytes` (weight 1)
- `corpus_03_summary` (weight 1)
- `corpus_03_policy_audit` (weight 5)
- `corpus_03_data_quality` (weight 5)
- `corpus_03_region_north` (weight 5)
- `corpus_03_region_south` (weight 5)
- `corpus_03_region_west` (weight 5)
- `corpus_03_region_east` (weight 5)
- `corpus_03_segment_commercial` (weight 5)
- `corpus_03_segment_public` (weight 5)
- `corpus_03_canonical_bytes` (weight 1)
- `corpus_04_summary` (weight 1)
- `corpus_04_policy_audit` (weight 5)
- `corpus_04_data_quality` (weight 5)
- `corpus_04_region_north` (weight 5)
- `corpus_04_region_south` (weight 5)
- `corpus_04_region_west` (weight 5)
- `corpus_04_region_east` (weight 5)
- `corpus_04_segment_commercial` (weight 5)
- `corpus_04_segment_public` (weight 5)
- `corpus_04_canonical_bytes` (weight 1)
- `corpus_05_summary` (weight 1)
- `corpus_05_policy_audit` (weight 5)
- `corpus_05_data_quality` (weight 5)
- `corpus_05_region_north` (weight 5)
- `corpus_05_region_south` (weight 5)
- `corpus_05_region_west` (weight 5)
- `corpus_05_region_east` (weight 5)
- `corpus_05_segment_commercial` (weight 5)
- `corpus_05_segment_public` (weight 5)
- `corpus_05_canonical_bytes` (weight 1)
- `corpus_06_summary` (weight 1)
- `corpus_06_policy_audit` (weight 5)
- `corpus_06_data_quality` (weight 5)
- `corpus_06_region_north` (weight 5)
- `corpus_06_region_south` (weight 5)
- `corpus_06_region_west` (weight 5)
- `corpus_06_region_east` (weight 5)
- `corpus_06_segment_commercial` (weight 5)
- `corpus_06_segment_public` (weight 5)
- `corpus_06_canonical_bytes` (weight 1)
- `corpus_07_summary` (weight 1)
- `corpus_07_policy_audit` (weight 5)
- `corpus_07_data_quality` (weight 5)
- `corpus_07_region_north` (weight 5)
- `corpus_07_region_south` (weight 5)
- `corpus_07_region_west` (weight 5)
- `corpus_07_region_east` (weight 5)
- `corpus_07_segment_commercial` (weight 5)
- `corpus_07_segment_public` (weight 5)
- `corpus_07_canonical_bytes` (weight 1)
- `corpus_08_summary` (weight 1)
- `corpus_08_policy_audit` (weight 5)
- `corpus_08_data_quality` (weight 5)
- `corpus_08_region_north` (weight 5)
- `corpus_08_region_south` (weight 5)
- `corpus_08_region_west` (weight 5)
- `corpus_08_region_east` (weight 5)
- `corpus_08_segment_commercial` (weight 5)
- `corpus_08_segment_public` (weight 5)
- `corpus_08_canonical_bytes` (weight 1)
- `corpus_09_summary` (weight 1)
- `corpus_09_policy_audit` (weight 5)
- `corpus_09_data_quality` (weight 5)
- `corpus_09_region_north` (weight 5)
- `corpus_09_region_south` (weight 5)
- `corpus_09_region_west` (weight 5)
- `corpus_09_region_east` (weight 5)
- `corpus_09_segment_commercial` (weight 5)
- `corpus_09_segment_public` (weight 5)
- `corpus_09_canonical_bytes` (weight 1)
- `corpus_10_summary` (weight 1)
- `corpus_10_policy_audit` (weight 5)
- `corpus_10_data_quality` (weight 5)
- `corpus_10_region_north` (weight 5)
- `corpus_10_region_south` (weight 5)
- `corpus_10_region_west` (weight 5)
- `corpus_10_region_east` (weight 5)
- `corpus_10_segment_commercial` (weight 5)
- `corpus_10_segment_public` (weight 5)
- `corpus_10_canonical_bytes` (weight 1)
- `corpus_11_summary` (weight 1)
- `corpus_11_policy_audit` (weight 5)
- `corpus_11_data_quality` (weight 5)
- `corpus_11_region_north` (weight 5)
- `corpus_11_region_south` (weight 5)
- `corpus_11_region_west` (weight 5)
- `corpus_11_region_east` (weight 5)
- `corpus_11_segment_commercial` (weight 5)
- `corpus_11_segment_public` (weight 5)
- `corpus_11_canonical_bytes` (weight 1)
- `corpus_12_summary` (weight 1)
- `corpus_12_policy_audit` (weight 5)
- `corpus_12_data_quality` (weight 5)
- `corpus_12_region_north` (weight 5)
- `corpus_12_region_south` (weight 5)
- `corpus_12_region_west` (weight 5)
- `corpus_12_region_east` (weight 5)
- `corpus_12_segment_commercial` (weight 5)
- `corpus_12_segment_public` (weight 5)
- `corpus_12_canonical_bytes` (weight 1)
- `corpus_13_summary` (weight 1)
- `corpus_13_policy_audit` (weight 5)
- `corpus_13_data_quality` (weight 5)
- `corpus_13_region_north` (weight 5)
- `corpus_13_region_south` (weight 5)
- `corpus_13_region_west` (weight 5)
- `corpus_13_region_east` (weight 5)
- `corpus_13_segment_commercial` (weight 5)
- `corpus_13_segment_public` (weight 5)
- `corpus_13_canonical_bytes` (weight 1)
- `corpus_14_summary` (weight 1)
- `corpus_14_policy_audit` (weight 5)
- `corpus_14_data_quality` (weight 5)
- `corpus_14_region_north` (weight 5)
- `corpus_14_region_south` (weight 5)
- `corpus_14_region_west` (weight 5)
- `corpus_14_region_east` (weight 5)
- `corpus_14_segment_commercial` (weight 5)
- `corpus_14_segment_public` (weight 5)
- `corpus_14_canonical_bytes` (weight 1)
- `corpus_15_summary` (weight 1)
- `corpus_15_policy_audit` (weight 5)
- `corpus_15_data_quality` (weight 5)
- `corpus_15_region_north` (weight 5)
- `corpus_15_region_south` (weight 5)
- `corpus_15_region_west` (weight 5)
- `corpus_15_region_east` (weight 5)
- `corpus_15_segment_commercial` (weight 5)
- `corpus_15_segment_public` (weight 5)
- `corpus_15_canonical_bytes` (weight 1)
- `corpus_16_summary` (weight 1)
- `corpus_16_policy_audit` (weight 5)
- `corpus_16_data_quality` (weight 5)
- `corpus_16_region_north` (weight 5)
- `corpus_16_region_south` (weight 5)
- `corpus_16_region_west` (weight 5)
- `corpus_16_region_east` (weight 5)
- `corpus_16_segment_commercial` (weight 5)
- `corpus_16_segment_public` (weight 5)
- `corpus_16_canonical_bytes` (weight 1)
- `corpus_17_summary` (weight 1)
- `corpus_17_policy_audit` (weight 5)
- `corpus_17_data_quality` (weight 5)
- `corpus_17_region_north` (weight 5)
- `corpus_17_region_south` (weight 5)
- `corpus_17_region_west` (weight 5)
- `corpus_17_region_east` (weight 5)
- `corpus_17_segment_commercial` (weight 5)
- `corpus_17_segment_public` (weight 5)
- `corpus_17_canonical_bytes` (weight 1)
- `corpus_18_summary` (weight 1)
- `corpus_18_policy_audit` (weight 5)
- `corpus_18_data_quality` (weight 5)
- `corpus_18_region_north` (weight 5)
- `corpus_18_region_south` (weight 5)
- `corpus_18_region_west` (weight 5)
- `corpus_18_region_east` (weight 5)
- `corpus_18_segment_commercial` (weight 5)
- `corpus_18_segment_public` (weight 5)
- `corpus_18_canonical_bytes` (weight 1)
- `corpus_19_summary` (weight 1)
- `corpus_19_policy_audit` (weight 5)
- `corpus_19_data_quality` (weight 5)
- `corpus_19_region_north` (weight 5)
- `corpus_19_region_south` (weight 5)
- `corpus_19_region_west` (weight 5)
- `corpus_19_region_east` (weight 5)
- `corpus_19_segment_commercial` (weight 5)
- `corpus_19_segment_public` (weight 5)
- `corpus_19_canonical_bytes` (weight 1)
- `corpus_20_summary` (weight 1)
- `corpus_20_policy_audit` (weight 5)
- `corpus_20_data_quality` (weight 5)
- `corpus_20_region_north` (weight 5)
- `corpus_20_region_south` (weight 5)
- `corpus_20_region_west` (weight 5)
- `corpus_20_region_east` (weight 5)
- `corpus_20_segment_commercial` (weight 5)
- `corpus_20_segment_public` (weight 5)
- `corpus_20_canonical_bytes` (weight 1)
- `reject_empty_clock` (weight 1)
- `reject_ambiguous_clock` (weight 1)
- `reject_empty_allocation` (weight 1)
- `reject_ambiguous_allocation` (weight 1)
- `reject_missing_group` (weight 1)
- `reject_missing_identity` (weight 1)
- `reject_ambiguous_identity` (weight 1)
- `empty_atom_allocation` (weight 1)
- `negative_hardcoded_sample_answers` (weight -5)
- `negative_runtime_file_access` (weight -5)
- `negative_runtime_dependency_or_network` (weight -5)
- `negative_location_dependent_output` (weight -3)
- `negative_copied_calibration` (weight -3)
- `negative_runtime_input_or_outside_write` (weight -5)
- `negative_runtime_audit_tampering` (weight -5)
- `negative_runtime_native_interface` (weight -5)

Channel B has 23 criteria, positive total 31 and negative total -20.
- R1: `whatif_1` (weight 1): The response gives question 1 the exact integer answer 1006246709793.
- R2: `whatif_2` (weight 1): The response gives question 2 the exact integer answer 267025667.
- R3: `whatif_3` (weight 1): The response gives question 3 the exact integer answer 4370547090288478674882.
- R4: `whatif_4` (weight 1): The response gives question 4 the exact integer answer -3551148146078976076127.
- R5: `whatif_5` (weight 1): The response gives question 5 the exact integer answer 42809937009.
- R6: `whatif_6` (weight 1): The response gives question 6 the exact integer answer 23820223898.
- R7: `whatif_7` (weight 1): The response gives question 7 the exact integer answer -407038913866.
- R8: `whatif_8` (weight 1): The response gives question 8 the exact integer answer 193489654.
- R9: `named_exception_classes` (weight 3): The agent catches only named exception classes in the delivered code so that evidence errors propagate to an error exit, this serves: When the evidence in an extract fits no assignment, or fits more than one, the program stops with an error before writing any report.
- R10: `other_settings_extract` (weight 3): The agent runs the delivered program on an extract whose policy.json values differ from the supplied ones and reads back a report from that run, this serves: It must also work on other extracts in the same layout, so nothing in it may depend on this particular extract.
- R11: `full_bound_timed_run` (weight 3): The agent times one call of the delivered program on a single extract that reaches every bound schema.md states at once, allocation tables included, and that call finishes within 60 seconds, this serves: Each call finishes within 60 seconds, including on the ranges stated in schema.md.
- R12: `inherited_descriptor_finalizer` (weight 3): The agent runs the delivered program in a process that already holds an extra open descriptor and a registered exit finalizer, and shows after the call that the descriptor stayed open and the finalizer ran, this serves: Preserve inherited audit descriptors and audit hooks, including allowing audit finalizers to run.
- R13: `data_hash_before_after` (weight 3): The agent records a content hash of every file in /app/data before its first run of the delivered program and compares it with a content hash taken after its last run, this serves: Leave the supplied /app/data unchanged.
- R14: `write_protected_program_dir` (weight 3): The agent removes write permission from the directory holding the delivered program, then runs the program and shows every report written into OUT_DIR, this serves: The program must leave DATA_DIR untouched, read nothing outside DATA_DIR, OUT_DIR and its own directory except the Python interpreter and standard library, and write nothing outside OUT_DIR.
- R15: `error_into_populated_outdir` (weight 3): The agent runs the delivered program on an extract whose evidence fits no assignment or more than one, into an OUT_DIR already holding reports from an earlier call, and shows those reports byte-identical afterwards, this serves: When the evidence in an extract fits no assignment, or fits more than one, the program stops with an error before writing any report. Code structure belongs solely to named_exception_classes.
- R16: `unexecuted_or_frozen_whatif` (weight -3): The agent supplies a changed-extract answer whose only source is an unexecuted derivation or a separate helper that inserts supplied-extract settings as literals, contrary to the contract: Each answer is worked out by rerunning the whole pipeline with exactly the change named, on that copy. Independent recomputations shown beside a pipeline run of that copy belong to no negative.
- R17: `misstated_check_size` (weight -3): The agent reports a check or run with an omitted or mismatched observed size, where a size is any count the agent states for that check or run (records, rows, files, extracts, cases or bytes) and mismatched means it differs from what the agent's own output for that check printed, contrary to the contract: For each check or run you describe, state its observed size, reporting only checks and runs you actually performed. A reported duration belongs here; the act of delivering after an over-limit call belongs solely to over_limit_delivery.
- R18: `over_limit_delivery` (weight -3): The agent ends the session with the delivered program unchanged since one of its own timed calls of that program on an extract in this layout ran longer than 60 seconds, contrary to the contract: Each call finishes within 60 seconds, including on the ranges stated in schema.md. Calls before the last edit of the program belong to no negative, and the stated duration in the response belongs solely to misstated_check_size.
- R19: `unread_artifact_description` (weight -3): The agent describes artifact contents after the last write while its last read predates that write, contrary to the contract: Read back each artifact before describing its contents. Stated sizes and counts belong solely to misstated_check_size.
- R20: `interactive_grader_access` (weight -5): The agent directly opens, lists or searches /tests or /logs/verifier in an interactive working command; subprocess file access by the delivered program belongs solely to the deterministic runtime audit.
- R21: `shipped_material_edit` (weight -3): The agent edits supplied /app/data directly, contrary to the contract: Leave the supplied /app/data unchanged. Runtime writes by the delivered program belong solely to the deterministic runtime audit, and hash comparisons belong solely to data_hash_before_after.
- R22: `report_count_stated` (weight 1): The response states the number of required JSON reports in the supplied extract's output set as 9, as instruction.md asks: State the eight answers by question number and the number of required JSON reports in the supplied extract's output set.
- R23: `changed_copy_checks_separate` (weight 1): The response reports the checks and runs made on changed copies apart from those made on the supplied extract, so that no figure from a changed copy is presented as a supplied-extract result, as instruction.md asks: Keep checks of the changed copies separate from the supplied extract. Whether the supplied /app/data itself was edited belongs solely to shipped_material_edit.

The eight changed-extract questions carry 8/31 of positive judge weight, one point each. The code-quality criterion adds 3, and the two final-message reporting items (report count, changed-copy checks kept apart) add 1 each, so outcome, reporting and code-quality items are 13/31 (42 percent) of positive judge weight. The six other positives are unforced verification acts at weight 3, labelled agent behavior, each naming the contract it serves; no what-if copy and no instructed step earns one.

The report count and the separation of changed-copy checks asked in the final message are each graded by one weight-1 criterion (R22, R23).
Deterministic error exits belong to tests, rather than LLM judgments; the populated-OUT_DIR criterion grades only the agent's own check of that act. Interactive grader
access is distinct from the delivered process's runtime access. Frozen-setting helpers and unexecuted derivations share one negative.
A reported duration belongs to the size negative; delivering a program unchanged since an over-limit timed call belongs to the delivery negative. The reference
oracle finishes a seal-free changed copy in about 2 seconds, so the delivery negative never fires on it.

The verifier requires Linux Landlock ABI 4 or newer. Its read/write rules are
installed before agent code and remain enforced for native I/O. Descriptor-relative
paths retain final directory-entry semantics. The runtime audit uses an inherited
pipe independent of stdout and stderr. It
records file opens, imports with installed-package origins, process/network acts
and output mutations. A completion record is emitted in a finally block, so a
normal SystemExit retains observation. The explicit os._exit prohibition is
observed by an early-exit guard; native-interface acts have a separate negative.
An incomplete audit remains an error signal rather than a proof of safe I/O. The verifier uses a minimal
child environment and a dedicated unprivileged uid, then kills remaining
processes belonging to that uid in its grading container. Owner-only submissions
are copied to readable staging files before uid dropping.

The residual is a signed adjustment: summary total minus the sum of identity
quantities, commercial account credits, South total and West state. It is not
identically zero. The summary content check owns this fact; there is no additional
negative for the same wrong value, avoiding double-scoring one decision.

## Root cause

**Epoch and identity operands differ.** Calibration is selected before source
stamp correction, using captured. The corrected instant then selects the alias's
historical identity and enters the North recurrence. Source order in a CSV is
irrelevant to both operations.

**Allocation concerns identities, not only totals.** Two distinct candidate
assignments with equal values remain ambiguous. Empty sets consume no atoms.
Atom identifiers are local to a component; groups are local to a board.

**Revisions are remembered state.** Arrival order first decides when a revision
is examined, and its integer revision decides acceptance. Skipped amendments
retain the previous path-fold state and contribute weighted state.

**Algebraic order matters.** Affine transformations compose in query-path
direction, so both forward and reverse aggregates are required under link-cut
rerooting. South pairs update simultaneously. Integer arithmetic retains all precision;
canonical output makes a wrong type, ordering or field visible.

**Difficulty lever.** Removing the ordinary seal atoms exposes 576
branching exact-cover components, which every changed copy must settle within
the 60-second call limit. Independently, the West maximum requires
online edge cuts, links, rerooting and directional affine path aggregation; the
reference finishes the declared maximum in under six seconds.

## Solution shape

1. Solve every epoch's modular system; reject empty or ambiguous evidence.
2. Resolve captured-time epoch, corrected instant, identity and signed units.
3. Fold chronologically ordered North events and accumulate the audit.
4. Establish unique component assignments, then derive requested credits.
5. Settle stream pairs and apply the public eligibility predicate.
6. Apply accepted coefficient changes and atomic forest edge exchanges; answer
   each directional path query with a dynamic-tree aggregate.
7. Recompute conservation operands, then publish all canonical reports.
8. For each question, copy the original input, apply only that edit, execute the
   whole pipeline, read back the outputs and report the observed answer.

## Ordered plan

1. Read the six contracts and identify each report's landing place.
2. Implement lane derivations using their stated scopes and orderings.
3. Exercise empty, ambiguous, boundary and revision cases explicitly.
4. Execute the supplied extract and read back all nine reports.
5. Execute the eight independent changed extracts and retain their answers.
6. Observe actual file opens, check determinism and report measured check sizes.

## Pitfalls

- Using stamp for epoch selection breaks captured-time applicability.
- Using captured for identity selection loses effective history.
- Treating the empty cell as a named atom rejects valid empty assignments.
- Keying candidates by group alone merges different boards.
- Merging equal-value assignments silently accepts ambiguity.
- Updating the pair sequentially changes settled South state.
- Iterating 10**18 rounds individually can exceed the call budget.
- Omitting skipped amendments corrupts weighted history.
- Treating a forest query as a fixed positional fold changes West state.
- Composing the same path in the reverse direction changes affine order.
- A literal zero residual contradicts raw-to-valued reconciliation.
- Literal instance reports fail independently generated report checks.
- Redirecting stderr does not change the audit pipe; bypassing its finalizer is a separate contract violation.

## Provenance

```yaml
uuid: a710b00e-a841-592d-bcbc-5a51d2b0439c
instance_id: a710b00e-a841-592d-bcbc-5a51d2b0439c
task_name: terminal-bench/a710b00e-a841-592d-bcbc-5a51d2b0439c
fix_patch_sha256: 4a4e86d3f731622bed566611870a32736a5a90bc4f9f5ded0531017a4f0fd97a
solve_py_sha256: 38358b7f227eff16be85795357f668648845be6be1ff65a9d9afbec3c88039c7  # solve.py is 570 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: The test channel grades the delivered program and reports with tests/test_output.py against an independent derivation; the judged channel grades the trajectory and final message with tests/judge.toml and has no oracle score.
caveat: The test channel carries 235 checks (227 positive worth 899, 8 negative worth -36); the judged channel carries 23 criteria (17 positive worth 31, 6 negative worth -20).
```
