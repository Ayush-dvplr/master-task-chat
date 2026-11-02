# TRUTH.md - 56fe3bdd-00c6-5b13-a5c8-90a94ccc475e

## Defect

Nothing in `/app/data` is broken in the software sense: the estate is a complete Q3 2026 review drop for the SKYE detector, 100 deliveries in 19 formats (1060586 records, 118388 of them in the 15 decoy deliveries), plus the PES-3 standard and the policy documents that decide every conflict. What is missing is the review itself. The agent must write `/app/out/evalctl.py`, an engine that turns any estate of this layout into the eight PES-3 artifacts, and run it on `/app/data`. Every rule the grader exercises is written in the visible documents; difficulty comes from the number of rules, from the way they interact (an identifier rule decides which annotation rows join, which decides UNLABELED, which decides the evaluated set, which decides every metric), and from deliveries that look more authoritative than they are.

1. (focal) Evaluation-set hygiene. Candidates are the amended freeze (Appendix A plus ratified Appendix A' rows of the PES-3.1 draft) joined to the frames indexes; exclusions follow the precedence of PES-3 s9 using lifecycle, integrity, privacy (register, mailbox, legal holds), board decisions (both governance revisions), perceptual-hash leakage and sequence leakage. Defeated tests: baseline_rows_exact, every family test, eval_estate_image_decisions_exact.
2. (focal) Capture instant. Local wall-clock time, per-camera-day site offsets with DST switches and the fold flag, then the CONFIRMED clock-sync skew of the window containing the camera instant, decide OUT_OF_WINDOW and captured_utc. Defeated tests: family_t03_time_representations, family_t11_boundaries, baseline_rows_exact.
3. (focal) Geometric normalisation. Vendor coordinates are read per batch (xywh, xyxy, inclusive xyxy, normalised cxcywh, pixel bbox_px), rotated out of the stored frame using the final orientation, converted exactly and rounded half to even; detections are inverted from the letterbox recorded by the node. Defeated tests: baseline_rows_exact, family_t12_half_even_rounding, eval_estate_ground_truth_exact, eval_estate_detections_exact.
4. (focal) Ground-truth curation. Assigned vendor only, on-time batches, accepted resubmissions, QA-rejected revisions, deleted annotations, errata in effective order, label crosswalks with dispositions, crowd and small-area ignore regions, approved relabel campaign replacement. Defeated tests: baseline_rows_exact, family_t06_void_records, family_t07_superseded_records, eval_estate_ground_truth_exact.
5. (focal) Detection provenance and post-processing. One source per run and image (completed rerun store, else the assigned node minus quarantine), usable only with an ok letterbox, then calibration, threshold, class-wise NMS and the per-image cap. Defeated tests: detections_r1_exact to detections_r4_exact, class_metrics_exact, eval_estate_detections_exact.
6. (focal) Scoring and release gating. COCO-style greedy matching with ignore regions by intersection over detection area, 101-point AP over ten IoU thresholds, operating points at governance precision targets, and the promotion rule with its protected-class regression bound. Defeated tests: class_metrics_exact, operating_points_exact, leaderboard_exact, eval_estate_scoring_exact.
7. (focal) Reconciliation. Declared partition records (superseded, voided and withdrawn entries ignored) against parsed records of every delivery, and the population counts. Defeated tests: reconciliation_deliveries_exact, reconciliation_counts_exact, eval_estate_reconciliation_exact.
8. (drift) Ignore regions match by IoU in textbook COCO usage; PES-3 s12 matches them by intersection over the detection's own area. Defeated test: class_metrics_exact.
9. (drift) Average precision as sklearn or VOC all-point interpolation is the common instinct; PES-3 s12 uses the 101-point envelope grid. Defeated test: class_metrics_exact.
10. (drift) Recomputing letterbox padding from the image size is standard; PES-3 s11 takes the highest ok attempt from the node's log, the per-row n7 values or the store table. Defeated tests: detections_r1_exact to detections_r4_exact, eval_estate_detections_exact.
11. (drift) Promoting the run with the best map_50_95 is the usual release habit; RGP-7 holds a challenger that regresses a protected class by more than 0.010 AP50 (R4 here). Defeated test: leaderboard_exact.
12. (drift) Thresholding raw scores and choosing operating points detection by detection are common; PES-3 s11 thresholds calibrated scores and s13 treats all detections at one calibrated score as one cut. Defeated tests: class_metrics_exact, operating_points_exact.
13. (drift) Leakage against the newest training index only is the usual check; PES-3 s8 unions the indexes of all reviewed runs, including the incumbent's v6-core legacy rows. Defeated test: eval_estate_image_decisions_exact.
14. (trap) Homoglyph, fullwidth, unpadded, hyphenated and whitespace-padded image ids (T1): family_t01_identifier_variants.
15. (trap) Legacy alias chains LGC to LGC to IMG (T13): family_t13_references.
16. (trap) skew_ms clock events, dim_scale 2 geometry rows, bbox_px Kestrel boxes, percent and basis-point scores (T2): family_t02_units_and_scales.
17. (trap) Fold-hour frames on DST switch days and timestamps in foreign offsets, Excel serials and epoch seconds (T3): family_t03_time_representations.
18. (trap) Decimal commas, digit grouping and parenthesised negatives (T4): family_t04_locale_numbers.
19. (trap) Sentinels: geometry 0 x 0, EXIF 0, dhash 0, crowd -1 or U, score -1, integrity N/A, disposition ~ (T5): family_t05_sentinels.
20. (trap) Deleted copies, purged hashes, denied waivers, released quarantines, cancelled clock events, voided replica rows (T6): family_t06_void_records.
21. (trap) Older revisions, earlier decisions, superseded log attempts, later duplicate registry and rerun rows (T7): family_t07_superseded_records.
22. (trap) Repeated headers with renamed and reordered columns (T8): family_t08_header_drift.
23. (trap) Quoted commas and line breaks, trailing empty fields, inline ; comments (T9): family_t09_delimiter_quirks.
24. (trap) Latin-1 lines inside UTF-8 files and the reverse, CRLF lines inside LF files (T10): family_t10_mixed_encodings.
25. (trap) Window edges, Hamming distance 5, area exactly 64, receipts and approvals exactly at the cutoff, codebook validity edges, waivers expiring at the cutoff (T11): family_t11_boundaries.
26. (trap) Exact half-pixel conversions that half-up rounding moves (T12): family_t12_half_even_rounding.
27. (trap) Errata pages that replace register values in PDF, Word, Markdown and HTML registers (T14): family_t14_document_errata.
28. (trap) Valid outliers: full-image boxes, 15 to 30 minute clock skews, 0.999 false positives (T15): family_t15_valid_outliers.
29. (trap) Decoy rows that agree with the authoritative source except on the graded set (T16): family_t16_decoy_disagreements.
30. (trap) Tie-break fixtures, where only a stated precedence or tie-break rule decides the row: candidates with an exact training hash in one shard and a distance 1 to 4 hash in another (PES-3 s9, LEAK_EXACT before LEAK_NEAR); a wrong confirmed orientation correction with the same DECIDED_AT and a smaller correction id than the true one (PES-3 s7); two decisions on one waiver pair at the same decided_at, the larger waiver_id standing (PES-3 s8); two RECLASS errata on one annotation with the same effective date, applied in errata id order (errata register); max_detections + 1 equal top calibrated scores on one image, so the per-image cap cuts inside the tie (PES-3 s11). Each rule has fixtures with the winning record both before and after the losing one in file order, so neither first-in-file nor last-in-file reading passes. Defeated tests: the family or baseline check of each fixture image, detections_r1_exact to detections_r4_exact, and the eval_estate_* checks on the fresh estate.

The reference is written in Python 3.12 (standard library plus the parsers installed in the image), 1673 lines in `solution/solve.py`, installed by `solution/solve.sh` as `/app/out/evalctl.py` and run on `/app/data`. Two grading channels exist: Channel A is `tests/test_output.py` (rewardkit criteria with their `criteria.<name>(weight=W)` registrations), Channel B is `tests/judge.toml` (LLM-judged trajectory and response criteria). `tests/reward.toml` gives each channel half of the reward.

Out of bounds: copying answers from the shipped estate into the engine (negative_hardcoded_sample_answers fires when fresh-estate output contains shipped-estate ids); behaviour keyed on directory names (negative_filename_dependent_behaviour compares runs at two locations); reading the shipped data instead of ESTATE_DIR (negative_reads_shipped_estate_at_runtime plants a canary estate at the shipped location); non-deterministic output (negative_nondeterministic_output compares two runs byte for byte).

## Load-bearing work

Graded artifacts (absolute paths, all declared in task.toml):

- `/app/out/evalctl.py`
- `/app/out/eval_images.csv`
- `/app/out/exclusions.csv`
- `/app/out/ground_truth.csv`
- `/app/out/detections.csv`
- `/app/out/class_metrics.csv`
- `/app/out/operating_points.csv`
- `/app/out/leaderboard.json`
- `/app/out/reconciliation.json`

Content contract: column lists, orderings, six-decimal half-even strings, NA rules and JSON keys are those of PES-3 s2; values follow PES-3 s3 to s15 and the documents they name. The engine must reproduce them on a fresh estate of the same layout within the stated time budget.

**Machine-learning concepts (all load-bearing, all interacting).**

- C1 Evaluation-set hygiene and leakage control: perceptual-hash near-duplicates (Hamming <= 4 over 64-bit dHash), sequence-group leakage, waivers; decides the evaluated set that every metric averages over. Expert variant: union of the training indexes of every reviewed run, purged and calibration-holdout rows excluded.
- C2 Geometric normalisation of boxes: EXIF orientation, stored vs upright frames, inclusive pixel edges, normalised centre formats, letterbox inversion; feeds IoU for NMS and matching. Expert variant: exact rational conversion with half-even rounding, letterbox taken from logs.
- C3 Label taxonomy harmonisation: three vendor vocabularies, effective-dated codes, v2 model vocabulary, eval/ignore/drop dispositions; decides which boxes are ground truth and which are ignore regions.
- C4 Ground-truth curation: assignment, revisions with QA, errata, relabel campaign, crowd and small-object ignore regions; feeds matching.
- C5 Score calibration and post-processing: isotonic piecewise-linear calibration, calibrated threshold, class-wise NMS, cross-class top-k; changes which detections reach matching and their rank. Expert variant: calibration before threshold, NMS and the cap.
- C6 COCO-style matching and average precision: greedy score-ordered matching, ignore regions by intersection over detection area, 101-point AP, mAP@[.5:.95]. Expert variant: IoF ignore matching (drift item).
- C7 Operating-point selection: highest-recall threshold meeting a precision target with score-level ties. Expert variant: ties at one calibrated score form one cut.
- C8 Model selection with slice regression gating: promotion margin on mAP plus protected-class AP50 regression bound. Drift: best mAP is HOLD when a protected slice regresses.
- C9 Inference provenance: node assignment, reruns, quarantine, misfiled and smoke-run records.

Interaction chain: C3 dispositions and C4 curation decide UNLABELED and therefore C1's evaluated set; C2 decides every IoU that C5 (NMS) and C6 (matching) use; C5 calibration decides C6 ranks, C7 thresholds and, through mAP, C8.

**Delivery inventory.** Records are PES-3 s15 records. The unique-contribution column states what is lost when the file is deleted.

| # | file | type | records | scope | traps | families | unique contribution | depends on | depended on by |
|---|---|---|---|---|---|---|---|---|---|
| 1 | annotation_batch_conventions.docx | docx | 9424 | in-scope | 19 | T1 T14 T2 T5 | only per-batch coordinate format, frame and resubmission acceptance | delivery_manifest.toml, eval_standard_v3.md, data_authority_policy.docx, frame_geometry.tsv, exif_orientation_scan.jsonl | delivery_manifest.toml, ks_boxes_part1.jsonl, ks_boxes_part2.jsonl, ks_boxes_part3.json, ks_boxes_part4.parquet, ks_boxes_part5.json (+11) |
| 2 | annotation_errata_register.md | md | 7892 | in-scope | 19 | T1 T11 T13 T14 T3 T7 | only post-delivery corrections (VOID, RECLASS, REBOX) to vendor annotations | delivery_manifest.toml, eval_standard_v3.md, nl_boxes_batch01.csv, ks_boxes_part1.jsonl, ob_boxes_east.xml | delivery_manifest.toml |
| 3 | calibration_certificate_rc2.pdf | pdf | 5123 | in-scope | 12 | T14 T2 T4 T7 | calibration map of R3 except the deferred classes | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_certificate_rc2_reissue.pdf | calibration_certificate_rc2_reissue.pdf, delivery_manifest.toml, preds_r3_n1.csv, preds_r3_n2.jsonl, preds_r3_n2_replay.jsonl, preds_r3_n3.parquet (+3) |
| 4 | calibration_certificate_rc2_reissue.pdf | pdf | 6149 | decoy | 30 | T13 T14 T16 T2 T4 T6 T7 | only knots of the R3 classes the certificate defers | delivery_manifest.toml, eval_standard_v3.md, calibration_certificate_rc2.pdf, data_authority_policy.docx | calibration_certificate_rc2.pdf, delivery_manifest.toml |
| 5 | calibration_r1_v64.yaml | yaml | 6147 | in-scope | 15 | T2 T4 T7 T9 | only calibration map of R1 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, taxonomy_v3_charter.docx | delivery_manifest.toml, preds_r1_n1.csv, preds_r1_n2.jsonl, preds_r1_n3.parquet, preds_r1_n4.tsv, preds_r1_n5.xml (+1) |
| 6 | calibration_r2_rc1.toml | toml | 6147 | in-scope | 15 | T2 T4 T7 T9 | only calibration map of R2 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, taxonomy_v3_charter.docx | delivery_manifest.toml, preds_r2_n1.csv, preds_r2_n2.jsonl, preds_r2_n3.parquet, preds_r2_n4.tsv, preds_r2_n5.xml (+1) |
| 7 | calibration_r4_ema.ini | ini | 6149 | in-scope | 18 | T2 T4 T7 T9 | only calibration map of R4 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, taxonomy_v3_charter.docx | delivery_manifest.toml, preds_r4_n1.csv, preds_r4_n2.jsonl, preds_r4_n3.parquet, preds_r4_n4.tsv, preds_r4_n5.xml (+1) |
| 8 | camera_clock_sync.ics | ics | 8465 | in-scope | 19 | T1 T15 T2 T4 T6 | only camera clock skews | delivery_manifest.toml, eval_standard_v3.md, frames_index_east.csv, camera_deployment_roster.yaml | delivery_manifest.toml, frames_index_east.csv, frames_index_west.csv |
| 9 | camera_deployment_roster.yaml | yaml | 5551 | in-scope | 18 | T1 T15 T3 T4 | sites, offsets and DST switches of main-roster cameras | delivery_manifest.toml, eval_standard_v3.md, frames_index_east.csv, frames_index_west.csv | camera_clock_sync.ics, camera_deployment_roster_ops.yaml, delivery_manifest.toml, frames_index_east.csv, frames_index_west.csv |
| 10 | camera_deployment_roster_ops.yaml | yaml | 5831 | decoy | 29 | T1 T13 T16 T3 T4 T6 T7 | only roster of the cameras absent from the main roster | delivery_manifest.toml, eval_standard_v3.md, camera_deployment_roster.yaml, data_authority_policy.docx | delivery_manifest.toml |
| 11 | data_authority_policy.docx | docx | 12498 | in-scope | 25 | T1 T13 T14 T7 | source-authority rules for every partial decoy; only vendor assignment register | delivery_manifest.toml, eval_standard_v3.md, image_id_aliases.ini | annotation_batch_conventions.docx, calibration_certificate_rc2_reissue.pdf, camera_deployment_roster_ops.yaml, delivery_manifest.toml, eval_standard_v3.md, frames_index_east_v2.csv (+9) |
| 12 | delivery_manifest.toml | toml | 10594 | in-scope | 78 | T13 T4 T6 T7 | only declared record counts per partition (reconciliation and the short-delivery rule) | all 99 other deliveries | all 99 other deliveries |
| 13 | eval_standard_v3.md | md | 12384 | in-scope | 25 | T1 T13 T14 T6 | PES-3 rules for every artifact; Appendix A is the only frozen candidate register | delivery_manifest.toml, image_id_aliases.ini, data_authority_policy.docx | data_authority_policy.docx, delivery_manifest.toml, eval_standard_v3_1_draft.md, exclusion_policy.docx, image_id_aliases.ini, relabel_campaign_status.json (+5) |
| 14 | eval_standard_v3_1_draft.md | md | 5415 | decoy | 29 | T1 T13 T14 T16 T6 T7 | only source of ratified freeze amendments (Appendix A'); its rule changes are void | delivery_manifest.toml, eval_standard_v3.md, image_id_aliases.ini | delivery_manifest.toml |
| 15 | exclusion_policy.docx | docx | 5086 | in-scope | 20 | T1 T13 T14 T6 | reason definitions, privacy rules; only privacy takedown register | delivery_manifest.toml, eval_standard_v3.md, image_id_aliases.ini, privacy_requests.mbox | delivery_manifest.toml, frame_integrity_audit.pdf, image_lifecycle_events.xml, privacy_register_export.tsv, privacy_requests.mbox |
| 16 | exif_orientation_scan.jsonl | jsonl | 12492 | in-scope | 25 | T1 T10 T13 T5 | scanned EXIF orientation | delivery_manifest.toml, eval_standard_v3.md, orientation_corrections.pdf, image_id_aliases.ini | annotation_batch_conventions.docx, delivery_manifest.toml, orientation_corrections.pdf |
| 17 | frame_dhash.parquet | parquet | 12492 | in-scope | 25 | T1 T13 T2 T5 | only perceptual hashes of the frames | delivery_manifest.toml, eval_standard_v3.md, train_hash_index_a.parquet, image_id_aliases.ini | delivery_manifest.toml, leakage_waivers.json, train_hash_index_a.parquet, train_hash_index_b.csv, train_hash_index_c.db, train_hash_index_d.txt (+4) |
| 18 | frame_geometry.tsv | tsv | 12492 | in-scope | 25 | T1 T10 T13 T2 T4 T5 T8 T9 | stored dimensions and dim_scale | delivery_manifest.toml, eval_standard_v3.md, frame_integrity_audit.pdf, image_id_aliases.ini | annotation_batch_conventions.docx, delivery_manifest.toml, frame_integrity_audit.pdf, ks_boxes_part1.jsonl, ks_boxes_part2.jsonl, ks_boxes_part3.json (+13) |
| 19 | frame_integrity_audit.pdf | pdf | 12492 | in-scope | 25 | T1 T13 T14 T5 | only integrity status and decoded dimensions | delivery_manifest.toml, eval_standard_v3.md, frame_geometry.tsv, exclusion_policy.docx | delivery_manifest.toml, frame_geometry.tsv |
| 20 | frames_index_east.csv | csv | 6428 | in-scope | 14 | T1 T10 T13 T8 T9 | capture records of east-index cameras | delivery_manifest.toml, eval_standard_v3.md, camera_deployment_roster.yaml, camera_clock_sync.ics, image_id_aliases.ini | camera_clock_sync.ics, camera_deployment_roster.yaml, delivery_manifest.toml, frames_index_east_v2.csv |
| 21 | frames_index_east_v2.csv | csv | 7074 | decoy | 28 | T1 T10 T13 T16 T6 T7 T8 T9 | only capture records of the cameras missing from both primary indexes | delivery_manifest.toml, eval_standard_v3.md, frames_index_east.csv, frames_index_west.csv, data_authority_policy.docx | delivery_manifest.toml |
| 22 | frames_index_west.csv | csv | 5426 | in-scope | 20 | T1 T10 T11 T13 T3 T8 T9 | capture records of west-index cameras | delivery_manifest.toml, eval_standard_v3.md, camera_deployment_roster.yaml, camera_clock_sync.ics, image_id_aliases.ini | camera_deployment_roster.yaml, delivery_manifest.toml, frames_index_east_v2.csv |
| 23 | image_id_aliases.ini | ini | 6331 | in-scope | 16 | T1 T10 T13 T9 | only homoglyph table and legacy alias chains | delivery_manifest.toml, eval_standard_v3.md | data_authority_policy.docx, delivery_manifest.toml, eval_standard_v3.md, eval_standard_v3_1_draft.md, exclusion_policy.docx, exif_orientation_scan.jsonl (+10) |
| 24 | image_lifecycle_events.xml | xml | 14476 | in-scope | 29 | T1 T13 T3 T6 T7 | only withdraw/restore history | delivery_manifest.toml, eval_standard_v3.md, exclusion_policy.docx, image_id_aliases.ini | delivery_manifest.toml |
| 25 | inference_run_registry.html | html | 6130 | in-scope | 17 | T1 T13 T14 T7 | runs, label maps, node formats and node assignments | delivery_manifest.toml, eval_standard_v3.md, sequence_membership.xlsx, taxonomy_v3_charter.docx | calibration_certificate_rc2.pdf, calibration_r1_v64.yaml, calibration_r2_rc1.toml, calibration_r4_ema.ini, delivery_manifest.toml, inference_run_registry_mirror.html (+43) |
| 26 | inference_run_registry_mirror.html | html | 6256 | decoy | 26 | T1 T13 T14 T16 T6 T7 | only node assignments of late sequences | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, data_authority_policy.docx | delivery_manifest.toml |
| 27 | ks_boxes_part1.jsonl | jsonl | 5520 | in-scope | 14 | T1 T10 T11 T12 T13 T15 T2 T3 T5 T6 T7 | only copy of the Kestrel batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ks_class_codebook.pdf, labeling_qa_portal.html, frame_geometry.tsv | annotation_errata_register.md, delivery_manifest.toml, ks_class_codebook.pdf |
| 28 | ks_boxes_part2.jsonl | jsonl | 5278 | in-scope | 17 | T1 T10 T11 T12 T13 T15 T2 T3 T5 T6 T7 | only copy of the Kestrel batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ks_class_codebook.pdf, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml, labeling_qa_portal.html |
| 29 | ks_boxes_part3.json | json | 5559 | in-scope | 18 | T1 T11 T12 T13 T15 T2 T3 T5 T6 T7 | only copy of the Kestrel batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ks_class_codebook.pdf, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml |
| 30 | ks_boxes_part4.parquet | parquet | 5636 | in-scope | 15 | T1 T11 T12 T13 T15 T2 T3 T5 T6 T7 | only copy of the Kestrel batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ks_class_codebook.pdf, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml |
| 31 | ks_boxes_part5.json | json | 5165 | in-scope | 12 | T1 T11 T12 T13 T15 T2 T3 T5 T6 T7 | only copy of the Kestrel batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ks_class_codebook.pdf, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml |
| 32 | ks_boxes_part6.csv | csv | 5361 | in-scope | 12 | T1 T10 T11 T12 T13 T15 T2 T3 T5 T6 T8 T9 | only copy of the Kestrel batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ks_class_codebook.pdf, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml |
| 33 | ks_boxes_resubmitted.json | json | 8260 | decoy | 28 | T1 T11 T12 T13 T15 T16 T2 T3 T5 T6 T7 | only copy of accepted Kestrel resubmitted batches | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, data_authority_policy.docx, ks_class_codebook.pdf | delivery_manifest.toml |
| 34 | ks_class_codebook.pdf | pdf | 5782 | in-scope | 12 | T1 T11 T14 T7 | only Kestrel code-to-class map with validity windows | delivery_manifest.toml, eval_standard_v3.md, taxonomy_v3_charter.docx, ks_boxes_part1.jsonl | delivery_manifest.toml, ks_boxes_part1.jsonl, ks_boxes_part2.jsonl, ks_boxes_part3.json, ks_boxes_part4.parquet, ks_boxes_part5.json (+2) |
| 35 | labeling_qa_export.xlsx | xlsx | 10889 | decoy | 27 | T1 T13 T16 T3 T6 T7 T8 | only final QA decisions after the portal snapshot (drafts and stale copies are void) | delivery_manifest.toml, eval_standard_v3.md, labeling_qa_portal.html, data_authority_policy.docx | delivery_manifest.toml |
| 36 | labeling_qa_portal.html | html | 6069 | in-scope | 16 | T1 T14 T3 T7 | only QA decisions up to the portal snapshot | delivery_manifest.toml, eval_standard_v3.md, nl_boxes_batch01.csv, ks_boxes_part2.jsonl | delivery_manifest.toml, ks_boxes_part1.jsonl, ks_boxes_part2.jsonl, ks_boxes_part3.json, ks_boxes_part4.parquet, ks_boxes_part5.json (+9) |
| 37 | leakage_waivers.json | json | 5188 | in-scope | 12 | T1 T11 T13 T3 T6 T7 | only leakage waivers | delivery_manifest.toml, eval_standard_v3.md, frame_dhash.parquet, train_hash_index_b.csv | delivery_manifest.toml, train_hash_index_a.parquet, train_hash_index_b.csv, train_hash_index_c.db, train_hash_index_d.txt, train_hash_index_e.jsonl (+1) |
| 38 | nl_boxes_batch01.csv | csv | 5786 | in-scope | 18 | T1 T10 T11 T13 T15 T4 T5 T6 T7 T8 T9 | only copy of the Northlake batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, taxonomy_v3_charter.docx, labeling_qa_portal.html, frame_geometry.tsv | annotation_errata_register.md, delivery_manifest.toml, labeling_qa_portal.html |
| 39 | nl_boxes_batch02.csv | csv | 5588 | in-scope | 12 | T1 T10 T11 T13 T15 T4 T5 T6 T7 T8 T9 | only copy of the Northlake batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, taxonomy_v3_charter.docx, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml, nl_boxes_batch02_reextract.csv |
| 40 | nl_boxes_batch02_reextract.csv | csv | 5592 | decoy | 30 | T1 T10 T11 T13 T15 T16 T4 T5 T6 T7 T8 T9 | only copy of the partitions missing from nl_boxes_batch02.csv | delivery_manifest.toml, eval_standard_v3.md, nl_boxes_batch02.csv, data_authority_policy.docx | delivery_manifest.toml |
| 41 | nl_boxes_batch03.tsv | tsv | 5784 | in-scope | 18 | T1 T10 T11 T13 T15 T4 T5 T6 T7 T8 T9 | only copy of the Northlake batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, taxonomy_v3_charter.docx, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml |
| 42 | nl_boxes_batch04.csv | csv | 5344 | in-scope | 14 | T1 T10 T11 T13 T15 T4 T5 T6 T7 T8 T9 | only copy of the Northlake batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, taxonomy_v3_charter.docx, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml |
| 43 | nl_boxes_q3_extra.xlsx | xlsx | 11169 | in-scope | 23 | T1 T11 T13 T15 T4 T5 T6 T7 | only copy of the Northlake batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, taxonomy_v3_charter.docx, labeling_qa_portal.html, frame_geometry.tsv | delivery_manifest.toml |
| 44 | node6_ingest_replica.db | sqlite | 18468 | decoy | 37 | T1 T12 T13 T16 T5 T6 T7 | only records of reruns routed to n6-replica | delivery_manifest.toml, eval_standard_v3.md, rerun_batches.toml, data_authority_policy.docx | delivery_manifest.toml |
| 45 | node6_rerun_store.db | sqlite | 43004 | in-scope | 86 | T1 T12 T13 T5 | only records and letterbox of n6 reruns | delivery_manifest.toml, eval_standard_v3.md, rerun_batches.toml, inference_run_registry.html | delivery_manifest.toml, rerun_batches.toml |
| 46 | node_quarantine_report.pdf | pdf | 5921 | in-scope | 20 | T1 T13 T14 T6 | only quarantine list | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, rerun_batches.toml | delivery_manifest.toml, preds_r1_n1.csv, preds_r1_n2.jsonl, preds_r1_n3.parquet, preds_r1_n4.tsv, preds_r1_n5.xml (+19) |
| 47 | ob_boxes_east.xml | xml | 8959 | in-scope | 18 | T1 T11 T13 T15 T5 T6 T7 | only copy of the Orbis batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ob_label_aliases.yaml, labeling_qa_portal.html | annotation_errata_register.md, delivery_manifest.toml, ob_label_aliases.yaml |
| 48 | ob_boxes_resubmitted.xml | xml | 7765 | decoy | 29 | T1 T11 T13 T15 T16 T5 T6 T7 | only copy of accepted Orbis resubmitted batches | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, data_authority_policy.docx, ob_label_aliases.yaml | delivery_manifest.toml |
| 49 | ob_boxes_west.xml | xml | 9018 | in-scope | 20 | T1 T11 T13 T15 T5 T6 T7 | only copy of the Orbis batches it carries | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx, ob_label_aliases.yaml, labeling_qa_portal.html | delivery_manifest.toml |
| 50 | ob_label_aliases.yaml | yaml | 10806 | in-scope | 22 | T1 T13 T5 T7 | only Orbis alias-to-class map | delivery_manifest.toml, eval_standard_v3.md, taxonomy_v3_charter.docx, ob_boxes_east.xml | delivery_manifest.toml, ob_boxes_east.xml, ob_boxes_resubmitted.xml, ob_boxes_west.xml |
| 51 | orientation_corrections.pdf | pdf | 6255 | in-scope | 20 | T1 T13 T14 T3 T6 T7 | only confirmed orientation corrections | delivery_manifest.toml, eval_standard_v3.md, exif_orientation_scan.jsonl, image_id_aliases.ini | delivery_manifest.toml, exif_orientation_scan.jsonl |
| 52 | preds_r1_n1.csv | csv | 16350 | in-scope | 33 | T1 T10 T12 T13 T15 T2 T4 T5 T8 T9 | only R1 records of node n1 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r1_v64.yaml, node_quarantine_report.pdf, preprocess_n1.log | delivery_manifest.toml |
| 53 | preds_r1_n2.jsonl | jsonl | 15287 | in-scope | 31 | T1 T10 T12 T13 T15 T2 T4 T5 | only R1 records of node n2 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r1_v64.yaml, node_quarantine_report.pdf, preprocess_n2.log | delivery_manifest.toml |
| 54 | preds_r1_n3.parquet | parquet | 16208 | in-scope | 33 | T1 T12 T13 T15 T2 T5 | only R1 records of node n3 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r1_v64.yaml, node_quarantine_report.pdf, preprocess_n3.log | delivery_manifest.toml |
| 55 | preds_r1_n4.tsv | tsv | 15188 | in-scope | 31 | T1 T10 T12 T13 T15 T2 T5 T8 T9 | only R1 records of node n4 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r1_v64.yaml, node_quarantine_report.pdf, preprocess_n4.log | delivery_manifest.toml |
| 56 | preds_r1_n5.xml | xml | 15697 | in-scope | 32 | T1 T12 T13 T15 T2 T4 T5 | only R1 records of node n5 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r1_v64.yaml, node_quarantine_report.pdf, preprocess_n5.log | delivery_manifest.toml |
| 57 | preds_r1_n7.csv | csv | 16709 | in-scope | 34 | T1 T10 T12 T13 T15 T2 T4 T5 T8 T9 | only R1 records of node n7 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r1_v64.yaml, node_quarantine_report.pdf | delivery_manifest.toml |
| 58 | preds_r2_n1.csv | csv | 19537 | in-scope | 40 | T1 T10 T12 T13 T15 T2 T4 T5 T8 T9 | only R2 records of node n1 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r2_rc1.toml, node_quarantine_report.pdf, preprocess_n1.log | delivery_manifest.toml |
| 59 | preds_r2_n2.jsonl | jsonl | 17089 | in-scope | 35 | T1 T10 T12 T13 T15 T2 T4 T5 | only R2 records of node n2 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r2_rc1.toml, node_quarantine_report.pdf, preprocess_n2.log | delivery_manifest.toml |
| 60 | preds_r2_n3.parquet | parquet | 16903 | in-scope | 34 | T1 T12 T13 T15 T2 T5 | only R2 records of node n3 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r2_rc1.toml, node_quarantine_report.pdf, preprocess_n3.log | delivery_manifest.toml |
| 61 | preds_r2_n4.tsv | tsv | 14353 | in-scope | 29 | T1 T10 T12 T13 T15 T2 T5 T8 T9 | only R2 records of node n4 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r2_rc1.toml, node_quarantine_report.pdf, preprocess_n4.log | delivery_manifest.toml |
| 62 | preds_r2_n5.xml | xml | 15781 | in-scope | 32 | T1 T12 T13 T15 T2 T4 T5 | only R2 records of node n5 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r2_rc1.toml, node_quarantine_report.pdf, preprocess_n5.log | delivery_manifest.toml |
| 63 | preds_r2_n7.xlsx | xlsx | 16245 | in-scope | 33 | T1 T12 T13 T15 T2 T4 T5 | only R2 records of node n7 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r2_rc1.toml, node_quarantine_report.pdf | delivery_manifest.toml |
| 64 | preds_r3_n1.csv | csv | 18245 | in-scope | 37 | T1 T10 T12 T13 T15 T2 T4 T5 T8 T9 | only R3 records of node n1 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_certificate_rc2.pdf, node_quarantine_report.pdf, preprocess_n1.log | delivery_manifest.toml |
| 65 | preds_r3_n2.jsonl | jsonl | 14588 | in-scope | 30 | T1 T10 T12 T13 T15 T2 T4 T5 | only R3 records of node n2 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_certificate_rc2.pdf, node_quarantine_report.pdf, preprocess_n2.log | delivery_manifest.toml |
| 66 | preds_r3_n2_replay.jsonl | jsonl | 8891 | decoy | 29 | T1 T10 T12 T13 T15 T16 T2 T4 T5 T6 T7 | only records of R3 reruns routed to n2-replay | delivery_manifest.toml, eval_standard_v3.md, rerun_batches.toml, data_authority_policy.docx, calibration_certificate_rc2.pdf | delivery_manifest.toml |
| 67 | preds_r3_n3.parquet | parquet | 16230 | in-scope | 33 | T1 T12 T13 T15 T2 T5 | only R3 records of node n3 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_certificate_rc2.pdf, node_quarantine_report.pdf, preprocess_n3.log | delivery_manifest.toml |
| 68 | preds_r3_n4.tsv | tsv | 13701 | in-scope | 28 | T1 T10 T12 T13 T15 T2 T5 T8 T9 | only R3 records of node n4 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_certificate_rc2.pdf, node_quarantine_report.pdf, preprocess_n4.log | delivery_manifest.toml |
| 69 | preds_r3_n5.xml | xml | 16008 | in-scope | 32 | T1 T12 T13 T15 T2 T4 T5 | only R3 records of node n5 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_certificate_rc2.pdf, node_quarantine_report.pdf, preprocess_n5.log | delivery_manifest.toml |
| 70 | preds_r3_n7.xlsx | xlsx | 16470 | in-scope | 33 | T1 T12 T13 T15 T2 T4 T5 | only R3 records of node n7 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_certificate_rc2.pdf, node_quarantine_report.pdf | delivery_manifest.toml |
| 71 | preds_r4_n1.csv | csv | 17944 | in-scope | 36 | T1 T10 T12 T13 T15 T2 T4 T5 T8 T9 | only R4 records of node n1 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r4_ema.ini, node_quarantine_report.pdf, preprocess_n1.log | delivery_manifest.toml |
| 72 | preds_r4_n2.jsonl | jsonl | 18512 | in-scope | 37 | T1 T10 T12 T13 T15 T2 T4 T5 | only R4 records of node n2 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r4_ema.ini, node_quarantine_report.pdf, preprocess_n2.log | delivery_manifest.toml |
| 73 | preds_r4_n3.parquet | parquet | 19403 | in-scope | 39 | T1 T12 T13 T15 T2 T5 | only R4 records of node n3 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r4_ema.ini, node_quarantine_report.pdf, preprocess_n3.log | delivery_manifest.toml |
| 74 | preds_r4_n4.tsv | tsv | 13866 | in-scope | 28 | T1 T10 T12 T13 T15 T2 T5 T8 T9 | only R4 records of node n4 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r4_ema.ini, node_quarantine_report.pdf, preprocess_n4.log | delivery_manifest.toml |
| 75 | preds_r4_n5.xml | xml | 18316 | in-scope | 37 | T1 T12 T13 T15 T2 T4 T5 | only R4 records of node n5 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r4_ema.ini, node_quarantine_report.pdf, preprocess_n5.log | delivery_manifest.toml |
| 76 | preds_r4_n7.xlsx | xlsx | 16675 | in-scope | 34 | T1 T12 T13 T15 T2 T4 T5 | only R4 records of node n7 (plus misfiled or spill-over rows) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, calibration_r4_ema.ini, node_quarantine_report.pdf | delivery_manifest.toml |
| 77 | preprocess_n1.log | log | 10004 | in-scope | 20 | T1 T10 T13 T6 T8 | only letterbox parameters of node n1 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, frame_geometry.tsv | delivery_manifest.toml, preds_r1_n1.csv, preds_r2_n1.csv, preds_r3_n1.csv, preds_r4_n1.csv |
| 78 | preprocess_n2.log | log | 9208 | in-scope | 19 | T1 T10 T13 T6 T8 | only letterbox parameters of node n2 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, frame_geometry.tsv | delivery_manifest.toml, preds_r1_n2.jsonl, preds_r2_n2.jsonl, preds_r3_n2.jsonl, preds_r4_n2.jsonl |
| 79 | preprocess_n3.log | log | 9519 | in-scope | 20 | T1 T10 T13 T6 T7 T8 | only letterbox parameters of node n3 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, frame_geometry.tsv | delivery_manifest.toml, preds_r1_n3.parquet, preds_r2_n3.parquet, preds_r3_n3.parquet, preds_r4_n3.parquet |
| 80 | preprocess_n4.log | log | 8039 | in-scope | 17 | T1 T10 T13 T6 T7 T8 | only letterbox parameters of node n4 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, frame_geometry.tsv | delivery_manifest.toml, preds_r1_n4.tsv, preds_r2_n4.tsv, preds_r3_n4.tsv, preds_r4_n4.tsv |
| 81 | preprocess_n5.log | log | 9192 | in-scope | 19 | T1 T10 T13 T6 T7 T8 | only letterbox parameters of node n5 | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, frame_geometry.tsv | delivery_manifest.toml, preds_r1_n5.xml, preds_r2_n5.xml, preds_r3_n5.xml, preds_r4_n5.xml |
| 82 | privacy_register_export.tsv | tsv | 5142 | decoy | 29 | T1 T10 T13 T16 T6 T7 T8 T9 | only copy of legal holds | delivery_manifest.toml, eval_standard_v3.md, exclusion_policy.docx, data_authority_policy.docx | delivery_manifest.toml |
| 83 | privacy_requests.mbox | mbox | 5396 | in-scope | 20 | T1 T11 T13 T3 T6 | only takedown and release messages after the register date | delivery_manifest.toml, eval_standard_v3.md, exclusion_policy.docx, image_id_aliases.ini | delivery_manifest.toml, exclusion_policy.docx |
| 84 | relabel_campaign_2026q3.xlsx | xlsx | 33170 | in-scope | 67 | T1 T13 T15 T3 T8 | only campaign items and replacement boxes | delivery_manifest.toml, eval_standard_v3.md, relabel_campaign_status.json, image_id_aliases.ini | delivery_manifest.toml, relabel_campaign_status.json |
| 85 | relabel_campaign_status.json | json | 8785 | in-scope | 18 | T11 T3 T6 T7 | only campaign item status history | delivery_manifest.toml, eval_standard_v3.md, relabel_campaign_2026q3.xlsx | delivery_manifest.toml, relabel_campaign_2026q3.xlsx |
| 86 | release_governance.docx | docx | 5041 | in-scope | 13 | T1 T13 T14 T7 | only promotion rule, protected classes and operating-point targets; board decisions to the v1 cut | delivery_manifest.toml, eval_standard_v3.md, image_id_aliases.ini, class_metrics (output) | delivery_manifest.toml, release_governance_v2_signed.docx |
| 87 | release_governance_v2_signed.docx | docx | 5499 | decoy | 28 | T1 T13 T14 T16 T6 T7 | only copy of board decisions made after the v1 register; its promotion text is void | delivery_manifest.toml, eval_standard_v3.md, release_governance.docx, data_authority_policy.docx, image_id_aliases.ini | delivery_manifest.toml |
| 88 | rerun_batches.toml | toml | 5961 | in-scope | 15 | T1 T13 T6 T7 | only rerun routing and status | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, node6_rerun_store.db | delivery_manifest.toml, node6_ingest_replica.db, node6_rerun_store.db, node_quarantine_report.pdf, preds_r3_n2_replay.jsonl |
| 89 | sequence_membership.xlsx | xlsx | 12492 | in-scope | 25 | T1 T13 T4 T8 | only image-to-sequence map | delivery_manifest.toml, eval_standard_v3.md, training_sequence_register.pdf, inference_run_registry.html | delivery_manifest.toml, inference_run_registry.html, training_sequence_register.pdf |
| 90 | taxonomy_v3_charter.docx | docx | 8050 | in-scope | 20 | T1 T10 T13 T14 | only Northlake crosswalk, the v2 model vocabulary crosswalk and the Orbis alias rules (later entry wins, ~ is eval) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html | calibration_r1_v64.yaml, calibration_r2_rc1.toml, calibration_r4_ema.ini, delivery_manifest.toml, inference_run_registry.html, ks_class_codebook.pdf (+6) |
| 91 | train_hash_index_a.parquet | parquet | 9171 | in-scope | 19 | T11 T2 T5 T6 | only copy of training shard a | delivery_manifest.toml, eval_standard_v3.md, frame_dhash.parquet, inference_run_registry.html, leakage_waivers.json | delivery_manifest.toml, frame_dhash.parquet |
| 92 | train_hash_index_b.csv | csv | 9167 | in-scope | 19 | T10 T11 T2 T5 T6 T8 T9 | only copy of training shard b | delivery_manifest.toml, eval_standard_v3.md, frame_dhash.parquet, inference_run_registry.html, leakage_waivers.json | delivery_manifest.toml, leakage_waivers.json |
| 93 | train_hash_index_c.db | sqlite | 9182 | in-scope | 19 | T11 T2 T5 T6 | only copy of training shard c | delivery_manifest.toml, eval_standard_v3.md, frame_dhash.parquet, inference_run_registry.html, leakage_waivers.json | delivery_manifest.toml |
| 94 | train_hash_index_d.txt | txt | 9238 | in-scope | 19 | T10 T11 T13 T2 T5 T6 | only copy of training shard d | delivery_manifest.toml, eval_standard_v3.md, frame_dhash.parquet, inference_run_registry.html, leakage_waivers.json | delivery_manifest.toml |
| 95 | train_hash_index_e.jsonl | jsonl | 9171 | in-scope | 19 | T10 T11 T2 T5 T6 | only copy of training shard e | delivery_manifest.toml, eval_standard_v3.md, frame_dhash.parquet, inference_run_registry.html, leakage_waivers.json | delivery_manifest.toml |
| 96 | train_hash_index_f_dedup.parquet | parquet | 8042 | decoy | 25 | T11 T13 T16 T2 T5 T6 T7 | only copy of training shard g (rows with source_shard g) | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, frame_dhash.parquet | delivery_manifest.toml |
| 97 | train_hash_index_h.txt | txt | 9172 | in-scope | 19 | T10 T11 T2 T5 T6 | only copy of training shard h | delivery_manifest.toml, eval_standard_v3.md, frame_dhash.parquet, inference_run_registry.html, leakage_waivers.json | delivery_manifest.toml |
| 98 | train_hash_index_legacy.txt | txt | 9115 | decoy | 28 | T10 T11 T13 T16 T2 T5 T6 T7 | only copy of the v6-core training index of the incumbent | delivery_manifest.toml, eval_standard_v3.md, inference_run_registry.html, frame_dhash.parquet | delivery_manifest.toml |
| 99 | training_sequence_register.pdf | pdf | 6100 | in-scope | 15 | T1 T13 T14 T6 | only training sequence register | delivery_manifest.toml, eval_standard_v3.md, sequence_membership.xlsx, inference_run_registry.html | delivery_manifest.toml, sequence_membership.xlsx |
| 100 | vendor_batch_receipts.docx | docx | 9424 | in-scope | 20 | T1 T11 T14 T3 | only batch receipt instants (late batches drop out) | delivery_manifest.toml, eval_standard_v3.md, annotation_batch_conventions.docx | delivery_manifest.toml |

Every delivery depends on `delivery_manifest.toml` and `eval_standard_v3.md`, and the manifest depends on every delivery (its partitions cannot be checked without the file), so the dependency graph is one strongly connected component; every file has in-degree and out-degree of at least two.

**Decoy table.** Load-bearing roles: (a) only invariant copy, (b) only void or supersession evidence, (c) only crosswalk or missing piece, (d) out-of-scope status declared inside the decoy and confirmed elsewhere, (e) partial authority.

| decoy | why it looks authoritative | demoting rule (file, locator) | roles | fails if ignored | fails if trusted wholesale |
|---|---|---|---|---|---|
| calibration_certificate_rc2_reissue.pdf | reissued, complete calibration certificate | data_authority_policy.docx section 4 plus eval_standard_v3.md section 11 (deferred classes only) | c, d | class_metrics_exact, operating_points_exact | detections_r3_exact, operating_points_exact |
| camera_deployment_roster_ops.yaml | complete roster covering every camera | data_authority_policy.docx section 2 (only cameras absent from the main roster) | d, e | baseline_rows_exact (ops-only cameras) | family_t03_time_representations, family_t11_boundaries |
| eval_standard_v3_1_draft.md | newer revision of PES-3 | eval_standard_v3.md section 5 (ratified Appendix A' rows only) | d, e | baseline_rows_exact (ratified additions), reconciliation_counts_exact | family_t16_decoy_disagreements, family_t06_void_records |
| frames_index_east_v2.csv | newer re-export with a precomputed captured_utc column | data_authority_policy.docx section 2 (only cameras absent from both primary indexes; empty captured_utc rows void; later row wins) | d, e | family_t16_decoy_disagreements, baseline_rows_exact (replica-camera frames) | family_t16_decoy_disagreements, family_t03_time_representations |
| inference_run_registry_mirror.html | full mirror of the registry with every sequence | data_authority_policy.docx section 4 (sequences the registry omits) | c, e | detections_r1_exact to detections_r4_exact, eval_estate_detections_exact | detections_r1_exact to detections_r4_exact, class_metrics_exact |
| ks_boxes_resubmitted.json | vendor-fixed boxes delivered last | annotation_batch_conventions.docx RESUBMISSION_ACCEPTED plus data_authority_policy.docx section 3 | b, e | family_t16_decoy_disagreements, eval_estate_ground_truth_exact | baseline_rows_exact, family_t16_decoy_disagreements |
| labeling_qa_export.xlsx | spreadsheet with more decisions than the portal | data_authority_policy.docx section 3 (final, after snapshot, on or before cutoff) | b, e | family_t07_superseded_records, eval_estate_ground_truth_exact | family_t06_void_records, family_t16_decoy_disagreements |
| nl_boxes_batch02_reextract.csv | complete re-extract of a short delivery | data_authority_policy.docx section 3 (missing partitions only) plus delivery_manifest.toml | c, e | baseline_rows_exact, reconciliation_deliveries_exact | family_t16_decoy_disagreements |
| node6_ingest_replica.db | replica of the rerun store with more rows | rerun_batches.toml routing plus data_authority_policy.docx section 4 | b, e | detections_r1_exact to detections_r4_exact, eval_estate_detections_exact | detections_r1_exact to detections_r4_exact, class_metrics_exact |
| ob_boxes_resubmitted.xml | corrected Orbis boxes | annotation_batch_conventions.docx RESUBMISSION_ACCEPTED plus data_authority_policy.docx section 3 | b, e | eval_estate_ground_truth_exact, baseline_rows_exact | family_t16_decoy_disagreements |
| preds_r3_n2_replay.jsonl | replayed R3 node n2 output with embedded letterbox | rerun_batches.toml routing plus data_authority_policy.docx section 4 | b, e | detections_r3_exact, eval_estate_detections_exact | detections_r3_exact, class_metrics_exact |
| privacy_register_export.tsv | newer privacy register | data_authority_policy.docx section 5 (LEGAL-HOLD rows only) plus exclusion_policy.docx section 2 | e, d | eval_estate_image_decisions_exact, family_t13_references | family_t16_decoy_disagreements, family_t06_void_records |
| release_governance_v2_signed.docx | signed version 2 of the governance policy | data_authority_policy.docx section 5 (decisions count, promotion text void) plus its own status section | b, d | family_t13_references (late board exclusions) | operating_points_exact |
| train_hash_index_f_dedup.parquet | deduplicated union of all shards | eval_standard_v3.md section 8 (source_shard g only) | e, a | family_t13_references, eval_estate_image_decisions_exact | family_t06_void_records, family_t16_decoy_disagreements |
| train_hash_index_legacy.txt | full training index with a dataset column | eval_standard_v3.md section 8 plus registry training_index (v6-core rows only, not purged) | e, c | eval_estate_image_decisions_exact, family_t13_references | family_t11_boundaries, family_t06_void_records |

Out of bounds by design: absolute speed beyond the stated budget, file naming of the engine beyond `/app/out/evalctl.py`, and any judgement the documents do not state. The fresh estate alone (the shipped estate is unchanged) carries a release-gate fixture (`EVAL_CLASS_WEIGHTS`, `EVAL_RUN_QUALITY` and `_fx_release_gate` in the verifier): bus has no ground truth, so its ap_50, ap_75 and ap_50_95 are NA and the map means skip it (PES-3 s2, s12); R2's map_50_95 gain is 0.005000 as written (just under 0.005 exactly), R3's cyclist ap_50 delta is -0.010000 as written (just under -0.010 exactly) and R4's map_50_95 equals R3's as written (just under it exactly). R2, R3 and R4 are therefore promoted and R3 is the release candidate only through the inclusive bounds, the six-decimal comparisons, the highest map_50_95 choice and the smaller-run-id tie-break (RGP-7 s1). One stated rule has no fixture: release_candidate is null when no run is promoted, which the single graded fresh estate cannot show while it promotes runs for the selection and tie-break fixtures, and the shipped estate promotes R3.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier`, makes `/tests` unreadable to other users and runs rewardkit over `/tests`. Channel A: 35 checks, positive total 151, negative total 18, so the channel ranges from -0.119 to 1.0. No check pays for existence or layout: every positive compares content (weight 5, or 3 for the two shipped-estate reconciliation checks), so a solver that only produces well-formed files earns 0.

Shipped-estate checks rebuild the source records of `/app/data` from the verifier's seed and resolve them with the reference rules; each candidate image belongs to at most one planted-trap family, and each family check compares that family's rows in the three image artifacts (eval_images.csv, exclusions.csv, ground_truth.csv), so one wrong image row costs one family. detections.csv is graded per run (detections_r1_exact to detections_r4_exact) on the images that both the agent and the reference evaluate, provided they share at least half of the reference's evaluated images; every detection row must belong to an image of the agent's own eval_images.csv. A detection-pipeline slip therefore costs the affected runs and the scoring checks, never the image families, and an image-level slip costs its family and the scoring checks, never the detection runs. Fresh-estate checks write a new estate (image ids 5000000 to 7499999) and run the delivered engine on it as `nobody`, up to three times: twice at one location (determinism) and once copied elsewhere (location independence), while a canary estate (ids 7500000 and above) sits at `/app/data`. Each run's time limit is the instruction's 1800 seconds for an estate the size of `/app/data` scaled to the fresh estate's record volume (183197 of 1049992 records) with a 25 percent margin, which is 393 seconds. A run that misses the limit ends the sequence, so the worst case stays far inside the 7200 second verifier timeout. negative_filename_dependent_behaviour only fires when the two same-location runs agree, so a nondeterministic engine is priced once, by negative_nondeterministic_output. The two anti-cheat id probes ignore the fresh estate's own phantom freeze ids, which a candidate-set bug can emit without any cheating.

Positive checks:

- `baseline_rows_exact` (weight 5)
- `family_t01_identifier_variants` (weight 5)
- `family_t02_units_and_scales` (weight 5)
- `family_t03_time_representations` (weight 5)
- `family_t04_locale_numbers` (weight 5)
- `family_t05_sentinels` (weight 5)
- `family_t06_void_records` (weight 5)
- `family_t07_superseded_records` (weight 5)
- `family_t08_header_drift` (weight 5)
- `family_t09_delimiter_quirks` (weight 5)
- `family_t10_mixed_encodings` (weight 5)
- `family_t11_boundaries` (weight 5)
- `family_t12_half_even_rounding` (weight 5)
- `family_t13_references` (weight 5)
- `family_t14_document_errata` (weight 5)
- `family_t15_valid_outliers` (weight 5)
- `family_t16_decoy_disagreements` (weight 5)
- `detections_r1_exact` (weight 5)
- `detections_r2_exact` (weight 5)
- `detections_r3_exact` (weight 5)
- `detections_r4_exact` (weight 5)
- `class_metrics_exact` (weight 5)
- `operating_points_exact` (weight 5)
- `leaderboard_exact` (weight 5)
- `reconciliation_counts_exact` (weight 3)
- `reconciliation_deliveries_exact` (weight 3)
- `eval_estate_image_decisions_exact` (weight 5)
- `eval_estate_ground_truth_exact` (weight 5)
- `eval_estate_detections_exact` (weight 5)
- `eval_estate_scoring_exact` (weight 5)
- `eval_estate_reconciliation_exact` (weight 5)

Negative checks:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_shipped_estate_at_runtime` (weight -5)
- `negative_nondeterministic_output` (weight -3)

Channel B (`tests/judge.toml`): 34 criteria, positive total 72, negative total 16.

- R1 `r1_reads_pes3_before_engine` (1): The agent opens /app/data/eval_standard_v3.md and reads its deliverable and authority sections before writing the first version of /app/out/evalctl.py.
- R2 `r2_verifies_partial_authority_subsets` (3): The agent checks, for at least two partially authoritative deliveries named in data_authority_policy.docx, that the records its engine takes from them are exactly the subset the policy allows.
- R3 `r3_inspects_self_declarations` (1): The agent inspects the header comment, banner, status section or metadata table of at least four deliveries whose names mention v2, mirror, replica, replay, reissue, resubmitted, reextract, export, draft, signed or ops before deciding how to use them.
- R4 `r4_compares_manifest_counts` (3): The agent compares the record counts its parsers produce with the partition counts in delivery_manifest.toml for at least five deliveries during development.
- R5 `r5_matches_reextract_partition_counts` (3): The agent compares, partition by partition, the number of rows its engine takes from nl_boxes_batch02_reextract.csv with the record counts delivery_manifest.toml declares for the nl_boxes_batch02_reextract.csv partitions it uses.
- R6 `r6_inspects_parser_output` (3): The agent runs a parser it wrote against at least three delivered files and inspects the parsed records before relying on that parser.
- R7 `r7_runs_engine_on_altered_estate` (3): The agent runs its engine on an estate it built whose file contents differ from /app/data, such as a reduced or edited copy, and inspects the result before finishing.
- R8 `r8_compares_two_runs_bytewise` (3): The agent runs the engine twice on the same estate and compares the two sets of output files byte for byte.
- R9 `r9_checks_population_invariant` (3): The agent checks that the evaluated images plus the excluded images equal the candidate count before finishing.
- R10 `r10_checks_applied_errata_values` (3): The agent compares, for at least one errata line in a register of each of the four document formats (PDF, Word, Markdown, HTML), the value its engine holds after applying that line with the value the line states.
- R11 `r11_engine_code_quality` (3): The agent's /app/out/evalctl.py would pass an ordinary Python code review as a whole, judged on signs such as handled errors, descriptive names and clean code free of debug output.
- R12 `r12_times_full_run` (1): The agent measures the wall-clock time of a full engine run on /app/data before finishing.
- R13 `r13_examines_dst_fold_frames` (1): The agent examines capture times of frames recorded in the wall-clock hour that a daylight-saving switch listed in camera_deployment_roster.yaml repeats.
- R14 `r14_examines_training_index_membership` (1): The agent inspects the membership columns (purged or status flag, set tag, source_shard) of at least three training index files before its engine first classifies leaks.
- R15 `r15_compares_reissued_knots` (1): The agent compares the knot values of at least one class outside the deferred list of calibration_certificate_rc2.pdf between that certificate and its reissue before choosing which knots skye-v7.0-rc2 uses.
- R16 `r16_reads_label_maps` (1): The agent reads the label maps in inference_run_registry.html before mapping detection class indexes to classes.
- R17 `r17_tests_reader_edge_cases` (3): The agent runs its CSV and TSV readers on at least two delivered rows that follow a repeated header, carry a quoted line break or sit on a line in another encoding, and inspects what they return.
- R18 `r18_cross_checks_ground_truth_counts` (1): The agent checks that gt_boxes and ignore_regions in eval_images.csv agree with the rows of ground_truth.csv.
- R19 `r19_inspects_multi_reason_candidates` (3): The agent inspects candidates that carry more than one exclusion reason and checks which reason PES-3 section 9 selects.
- R20 `r20_checks_ap_definition` (3): The agent checks its average precision code against the 101-point recall grid of PES-3 section 12.
- R21 `r21_response_release_decisions` (3): The response names the release candidate and a decision for each challenger run that match /app/out/leaderboard.json, as instruction.md asks with "reply with a short summary that names the release candidate and the decision for each challenger run".
- R22 `r22_response_lists_demoted_sources` (3): The response lists each delivery the agent demoted and the rule that demoted it, as instruction.md asks with "with the rule that demoted each one".
- R23 `r23_response_names_checks_run` (1): The response states which checks the agent ran to confirm the artifacts, as instruction.md asks with "says which checks you ran to confirm the artifacts".
- R24 `r24_modifies_app_data` (-5): The agent runs a command that attempts to edit, delete, rename or create a file under /app/data, breaking the instruction.md rule on modifying anything under `/app/data`.
- R25 `r25_reads_grader_files` (-5): The agent opens or searches for files under /tests, /solution or /logs/verifier.
- R26 `r26_engine_imports_unlisted_package` (-3): The agent's /app/out/evalctl.py imports a third-party package outside the list instruction.md gives in "It uses only the Python 3.12 standard library and the packages already installed in the image".
- R27 `r27_unsupported_exactness_claim` (-3): The agent claims in its final message that the artifacts are exact while its trajectory shows no comparison against manifest counts, invariants or an independent check.
- R28 `r28_checks_ignore_region_matching` (3): The agent checks that its matching code ignores an unmatched detection by its intersection with an ignore region divided by the detection's own area, as PES-3 section 12 states.
- R29 `r29_recomputes_image_detections_per_run` (3): The agent recomputes, for at least one evaluated image of each of the four reviewed runs, the final detections and their calibrated scores from that image's raw delivered records with code written outside evalctl.py, and compares them with detections.csv.
- R30 `r30_checks_raw_score_range` (3): The agent checks, over every prediction delivery of the reviewed runs, that each raw score its engine reads lies between 0 and 1 after conversion to a fraction and before calibration, with the -1 suppression sentinel set aside.
- R31 `r31_checks_knot_monotonicity` (3): The agent checks that the calibration knots its engine loads for every class of every reviewed run have x strictly increasing and y non-decreasing, as the isotonic map of PES-3 section 11 requires.
- R32 `r32_recomputes_operating_point` (3): The agent recomputes at least one row of operating_points.csv from detections.csv and ground_truth.csv with code written outside evalctl.py and compares it with the row its engine wrote.
- R33 `r33_recomputes_release_decisions` (3): The agent recomputes the decision of each challenger run in leaderboard.json from class_metrics.csv under the promotion rule of release_governance.docx with code written outside evalctl.py.
- R34 `r34_inspects_per_image_cap_order` (3): The agent inspects at least one image whose records left after NMS exceed the run's max_detections and checks which records its engine keeps under the per-image cap order of PES-3 section 11.

The two channels are combined only by `tests/reward.toml` (0.5 / positive total per channel).

**Test to rule trace.**

| test | rule | file and locator |
|---|---|---|
| baseline_rows_exact | PES-3 s3-s11 for untrapped images; s5 candidate set | eval_standard_v3.md, data_authority_policy.docx, annotation_batch_conventions.docx |
| detections_r1_exact to detections_r4_exact | PES-3 s2 detections layout and order, s11 detection provenance and post-processing | eval_standard_v3.md s2, s11; inference_run_registry.html; data_authority_policy.docx s4 |
| family_t01..t16 | the rule each family's trap exercises (see defect list and loop table) | file named in the loop table |
| class_metrics_exact | PES-3 s11-s12 | eval_standard_v3.md s11, s12; inference_run_registry.html |
| operating_points_exact | PES-3 s13, RGP-7 s2 targets | eval_standard_v3.md s13; release_governance.docx s2 |
| leaderboard_exact | PES-3 s14, RGP-7 s1 | release_governance.docx s1 |
| reconciliation_counts_exact | PES-3 s15 populations | eval_standard_v3.md s15 |
| reconciliation_deliveries_exact | PES-3 s15 record definitions, manifest statuses | eval_standard_v3.md s15; delivery_manifest.toml |
| eval_estate_* (5) | the same rules on a fresh estate; instruction: run on other estates, 1800 s | instruction.md; eval_standard_v3.md |
| negative_* (4) | instruction: read only ESTATE_DIR, byte-identical, location independent, derived values | instruction.md |

## Root cause

**Authority, not recency.** Every conflict in the estate is settled by a named document, and the rule always lives in a different file from the conflict it settles. The fifteen decoys are partial: each holds something nothing else holds (replica cameras, ops-only cameras, shard g, v6-core hashes, accepted resubmissions, missing partitions, post-snapshot QA decisions, legal holds, late board decisions, freeze amendments, late sequences, routed reruns, deferred calibration classes), and each holds wrong values for everything else.

**Invariants that expose a wrong path.** Manifest partition counts against parsed records (any CSV, header or encoding mistake shows up here); evaluated plus excluded equals candidates; gt_boxes and ignore_regions per image against ground_truth.csv; detection funnel accepted >= after_threshold >= after_nms >= final; the PES-3.1 draft status section; certificate deferral sentence; registry training_index column.

**Trap counts.** 2533 planted traps in total, 432 of them in decoys; every in-scope delivery carries at least 10 and every decoy at least 25 across at least six families including T6, T7, T13 and T16; files over 10,000 records carry more so that every 500-record band holds at least one. The manifest carries 78 (T4 underscore integers 28, T6 voided 19, T7 superseded 25, T13 withdrawn ghost files 6). On top of the traps sit the defect item 30 tie-break fixtures, which add 148 records: 4 training rows (shards b, c, e), 4 orientation corrections, 4 waiver decisions, 4 errata entries and 132 detection records (two images per reviewed run, 21, 16, 16 and 13 records each).

Family coverage (number of deliveries carrying each family): T1 85, T2 49, T3 20, T4 34, T5 57, T6 51, T7 47, T8 29, T9 25, T10 40, T11 31, T12 34, T13 84, T14 20, T15 44, T16 15.

**Trap loops.** Each loop is a wrong early decision whose downstream results look consistent; the tell is always in a different file from the entry. Flags: chain-X (escaping one loop of the chain exposes the next), decoy (entry or tell in a decoy), best-practice (entered by the textbook choice), sample-surviving (visible artifacts can look right while the fresh estate differs).

| id | entry | reinforcement | tell (file) | exit (rule) | graded impact | flags |
|---|---|---|---|---|---|---|
| L01 | Parse frames_index_east_v2.csv because it already has captured_utc | UTC values look clean; window filter yields a plausible eval set | DST-day frames disagree with roster offsets (camera_deployment_roster.yaml) | DAP-2 s2: replica only for cameras missing from primary indexes | family_t16_decoy_disagreements, family_t03_time_representations | decoy, best-practice |
| L02 | Ignore frames_index_east_v2.csv as a stale copy | every primary camera resolves; counts look complete | freeze ids of three cameras never match a frame; manifest shows replica rows (delivery_manifest.toml) | DAP-2 s2 | baseline_rows_exact, reconciliation_counts_exact | decoy, chain-A |
| L03 | Use utc_offset for every frame on a switch date | most frames convert; window membership stable | fold=1 rows collide with fold=0 rows of the same second (frames_index_west.csv) | PES-3 s6 fold rule | family_t03_time_representations | best-practice, chain-A |
| L04 | Treat ICS skew as seconds everywhere | skews look small and plausible | skew_ms events produce 1000x shifts across window edges (camera_clock_sync.ics DESCRIPTION) | PES-3 s6 | family_t02_units_and_scales | sample-surviving |
| L05 | Apply CANCELLED clock events | a skew exists for every window | two events cover the same window (camera_clock_sync.ics STATUS) | PES-3 s6 CONFIRMED only | family_t06_void_records |  |
| L06 | Close the window at both ends (draft rule) | boundary frames stay in | PES-3 s1 half-open interval (eval_standard_v3.md) | PES-3 s1 | family_t11_boundaries | decoy |
| L07 | Trust frame_geometry.tsv dims as written | dimensions match camera resolutions | dim_scale 2 rows and 0x0 rows; REENCODED in frame_integrity_audit.pdf | PES-3 s7 | family_t02_units_and_scales, family_t05_sentinels | chain-B |
| L08 | Use EXIF orientation as final | most frames are upright | confirmed corrections in orientation_corrections.pdf disagree | PES-3 s7 | family_t07_superseded_records | chain-B |
| L09 | Apply proposed orientation corrections | more images corrected looks thorough | PROPOSED status column (orientation_corrections.pdf) | PES-3 s7 confirmed only | family_t06_void_records | chain-B |
| L10 | Read the integrity register as printed | FAIL rows exclude images | Errata to the register replaces statuses (frame_integrity_audit.pdf) | PES-3 s4 document errata | family_t14_document_errata | chain-C |
| L11 | Normalise ids by upper-casing only | most rows join | homoglyph and fullwidth ids miss joins; aliases.ini [homoglyphs] | PES-3 s3 | family_t01_identifier_variants | best-practice |
| L12 | Resolve LGC aliases one hop | most aliases resolve | chained aliases land on another LGC id (image_id_aliases.ini) | PES-3 s3 | family_t13_references | chain-D |
| L13 | Decode files strictly as UTF-8 | most files parse | Latin-1 lines raise or become replacement characters (preprocess logs, nl_boxes) | PES-3 s4 per-line decoding | family_t10_mixed_encodings | best-practice |
| L14 | Split CSV lines on commas | row counts look right on early bands | quoted line breaks and repeated headers shift columns; manifest partition counts (delivery_manifest.toml) | PES-3 s4 | family_t09_delimiter_quirks, family_t08_header_drift | best-practice |
| L15 | Read decimal commas as thousands separators | values stay in range | n4 TSV coordinates exceed the 896 px model space | PES-3 s4 numeric rule | family_t04_locale_numbers |  |
| L16 | Treat dhash as signed decimal | few exact matches still appear | training shards hold unsigned/hex values; leak counts collapse | PES-3 s8 encodings | family_t02_units_and_scales | chain-E |
| L17 | Count hash 0 as a hash | a burst of LEAK_EXACT | sentinel rows in every shard; PES-3 s8 says 0 never matches | PES-3 s8 | family_t05_sentinels | chain-E |
| L18 | Include purged and calib-tagged training rows | more leaks look conservative | status/set_tag columns (train_hash_index_a.parquet, _d.txt) | PES-3 s8 | family_t06_void_records, family_t13_references | chain-E, best-practice |
| L19 | Use Hamming <= 5 (draft) or < 4 | leak totals look plausible | distance-5 planted pairs; PES-3 s8 inclusive 4 | PES-3 s8 | family_t11_boundaries | decoy |
| L20 | Ignore train_hash_index_f_dedup.parquet | v7 shards look complete | shard g never delivered separately; leaks of g rows missing | PES-3 s8 | family_t13_references | decoy, chain-E |
| L21 | Trust train_hash_index_f_dedup.parquet wholesale | it is the union, so it looks safest | stale purged flags disagree with shards a-h | PES-3 s8 g-only | family_t06_void_records | decoy |
| L22 | Ignore the legacy index | v7 leaks look complete | registry training_index lists v6-core for R1 | PES-3 s8 | eval_estate_image_decisions_exact | decoy, chain-E |
| L23 | Apply waivers by image only | waived images return | waivers name a single training hash; other matches still leak (leakage_waivers.json) | PES-3 s8 | family_t07_superseded_records |  |
| L24 | Treat a waiver expiring at the cutoff as valid | expiry looks inclusive | PES-3 s8 later than the cutoff | PES-3 s8 | family_t11_boundaries | sample-surviving |
| L25 | Count held-out and v5-archive sequences as leaks | sequence leaks look strict | STATUS and TRAINING_INDEX columns (training_sequence_register.pdf) | PES-3 s8 | family_t13_references, family_t06_void_records |  |
| L26 | Apply lifecycle events in file order | states look consistent | duplicate event ids and out-of-order instants (image_lifecycle_events.xml) | EXP-4 s1 | family_t07_superseded_records | chain-F |
| L27 | Apply post-cutoff withdrawals | withdrawals look current | PES-3 s1 cutoff | PES-3 s1 | family_t03_time_representations | chain-F |
| L28 | Use only the privacy register | holds match the docx table | mailbox TAKEDOWN/RELEASE after the register date (privacy_requests.mbox) | EXP-4 s2 | family_t06_void_records | chain-G |
| L29 | Accept forwarded takedowns | more holds look cautious | sender domain and Fwd: prefix | EXP-4 s2 | family_t06_void_records | chain-G |
| L30 | Trust the privacy export statuses | export is newer | only LEGAL-HOLD rows authoritative (data_authority_policy.docx) | DAP-2 s5 | family_t16_decoy_disagreements | decoy, chain-G |
| L31 | Ignore the privacy export | register plus mailbox look complete | legal holds exist nowhere else | DAP-2 s5 | family_t13_references | decoy, chain-G |
| L32 | Use only v1 board decisions | board exclusions look complete | v2 decisions dated before the cutoff exclude more images | RGP-7 s3 plus DAP-2 s5 | family_t13_references | decoy |
| L33 | Adopt the v2 rule text (0.003 margin, 0.020 protected bound, 0.85 target precision for every class) | promotion decisions come out unchanged, so the v2 text looks harmless | v2 status: awaiting ratification | RGP-7 s1-s2 | operating_points_exact | decoy |
| L34 | Annotate from every vendor | boxes look denser | vendor assignment register (data_authority_policy.docx) | DAP-2 s3 | baseline_rows_exact | best-practice, chain-H |
| L35 | Read Northlake boxes as upright xyxy | boxes fall inside images | rotated images produce boxes off the object; batch register says stored xywh | ABC-5 s1-s2 | baseline_rows_exact | chain-H |
| L36 | Trust the batch register row over its errata | most batches convert | Errata to the register (annotation_batch_conventions.docx) | PES-3 s4 | family_t14_document_errata | chain-H |
| L37 | Round half up | only a handful of pixels move | exact half coordinates; PES-3 s7 half-even | PES-3 s7 | family_t12_half_even_rounding | best-practice, sample-surviving |
| L38 | Recompute letterbox from image size | most boxes invert | failed attempts and re-attempts in preprocess logs; per-row n7 params | PES-3 s11 | detections_r1_exact to detections_r4_exact | best-practice |
| L39 | Take the newest revision | revisions look monotone | QA rejections of the newest revision (labeling_qa_portal.html) | ABC-5 s3 | family_t07_superseded_records | chain-I |
| L40 | Trust the QA export wholesale | more decisions | draft rows and stale copies (labeling_qa_export.xlsx state column) | DAP-2 s3 | family_t16_decoy_disagreements | decoy, chain-I |
| L41 | Ignore deleted flags of older revisions | box counts rise | deleted top revisions and resurrected objects | ABC-5 s3 | family_t06_void_records | chain-I |
| L42 | Skip errata after revision choice | boxes match vendor files | errata register (annotation_errata_register.md) | PES-3 s10 | baseline_rows_exact | chain-I |
| L43 | Apply errata dated after the cutoff | corrections look current | effective column | PES-3 s1 | family_t03_time_representations |  |
| L44 | Map Kestrel codes with one table per project | codes resolve | renumbering windows (ks_class_codebook.pdf) | codebook validity [from, to) | family_t11_boundaries | sample-surviving |
| L45 | Drop ignore-disposition labels | fewer boxes, cleaner GT | detections on ignore regions become false positives | Taxonomy charter s1 + PES-3 s10 | class_metrics_exact | best-practice |
| L46 | Use relabel campaign boxes for every item | campaign looks authoritative | status history (relabel_campaign_status.json) | PES-3 s10 | family_t07_superseded_records |  |
| L47 | Treat approval at exactly the cutoff as late | cutoff looks exclusive | PES-3 s1 on time | PES-3 s1 | family_t11_boundaries | sample-surviving |
| L48 | Use original Kestrel batches when a resubmission exists | vendor files look primary | RESUBMISSION_ACCEPTED Y (annotation_batch_conventions.docx) | DAP-2 s3 | eval_estate_ground_truth_exact | decoy |
| L49 | Take node rows from the file name's run | files look run-scoped | row run field disagrees (misfiled R4 rows, R5 rows) | registry rules | detections_r3_exact, detections_r4_exact | chain-J |
| L50 | Use every node's rows | detection counts rise | registry node assignment; spill-over rows | PES-3 s11 | class_metrics_exact | chain-J |
| L51 | Ignore the mirror | registry looks complete | late sequences with no node | DAP-2 s4 | detections_r1_exact to detections_r4_exact | decoy, chain-J |
| L52 | Trust replay/replica stores wholesale | they are newer | rerun_batches.toml routing | PES-3 s11 | class_metrics_exact | decoy, chain-J |
| L53 | Keep quarantined node output | no images lose detections | node_quarantine_report.pdf status | PES-3 s11 | class_metrics_exact | chain-J |
| L54 | Threshold on raw scores | threshold looks like a raw cut | calibrated maps differ per class | PES-3 s11 | class_metrics_exact | best-practice |
| L55 | Use the reissued certificate for all R3 classes | reissue is newer | deferral sentence in calibration_certificate_rc2.pdf | PES-3 s11 + DAP-2 s4 | operating_points_exact | decoy |
| L56 | NMS suppress at IoU >= threshold | duplicates vanish | PES-3 s11 greater than | PES-3 s11 | class_metrics_exact | best-practice |
| L57 | Match ignore regions by IoU | COCO default | PES-3 s12 intersection over detection area | PES-3 s12 | class_metrics_exact | best-practice |
| L58 | Use all-point or sklearn AP | AP close to expected | PES-3 s12 101-point grid | PES-3 s12 | class_metrics_exact | best-practice |
| L59 | Choose operating thresholds per detection | recall looks maximal | ties at the same calibrated score | PES-3 s13 | operating_points_exact | best-practice |
| L60 | Promote the highest map_50_95 | R4 looks best | protected-class regression rule (release_governance.docx) | RGP-7 s1 | leaderboard_exact | best-practice |

**Trap-family coverage matrix** (x = family planted in the delivery).

| file | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 | T13 | T14 | T15 | T16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| annotation_batch_conventions.docx | x | x |  |  | x |  |  |  |  |  |  |  |  | x |  |  |
| annotation_errata_register.md | x |  | x |  |  |  | x |  |  |  | x |  | x | x |  |  |
| calibration_certificate_rc2.pdf |  | x |  | x |  |  | x |  |  |  |  |  |  | x |  |  |
| calibration_certificate_rc2_reissue.pdf |  | x |  | x |  | x | x |  |  |  |  |  | x | x |  | x |
| calibration_r1_v64.yaml |  | x |  | x |  |  | x |  | x |  |  |  |  |  |  |  |
| calibration_r2_rc1.toml |  | x |  | x |  |  | x |  | x |  |  |  |  |  |  |  |
| calibration_r4_ema.ini |  | x |  | x |  |  | x |  | x |  |  |  |  |  |  |  |
| camera_clock_sync.ics | x | x |  | x |  | x |  |  |  |  |  |  |  |  | x |  |
| camera_deployment_roster.yaml | x |  | x | x |  |  |  |  |  |  |  |  |  |  | x |  |
| camera_deployment_roster_ops.yaml | x |  | x | x |  | x | x |  |  |  |  |  | x |  |  | x |
| data_authority_policy.docx | x |  |  |  |  |  | x |  |  |  |  |  | x | x |  |  |
| delivery_manifest.toml |  |  |  | x |  | x | x |  |  |  |  |  | x |  |  |  |
| eval_standard_v3.md | x |  |  |  |  | x |  |  |  |  |  |  | x | x |  |  |
| eval_standard_v3_1_draft.md | x |  |  |  |  | x | x |  |  |  |  |  | x | x |  | x |
| exclusion_policy.docx | x |  |  |  |  | x |  |  |  |  |  |  | x | x |  |  |
| exif_orientation_scan.jsonl | x |  |  |  | x |  |  |  |  | x |  |  | x |  |  |  |
| frame_dhash.parquet | x | x |  |  | x |  |  |  |  |  |  |  | x |  |  |  |
| frame_geometry.tsv | x | x |  | x | x |  |  | x | x | x |  |  | x |  |  |  |
| frame_integrity_audit.pdf | x |  |  |  | x |  |  |  |  |  |  |  | x | x |  |  |
| frames_index_east.csv | x |  |  |  |  |  |  | x | x | x |  |  | x |  |  |  |
| frames_index_east_v2.csv | x |  |  |  |  | x | x | x | x | x |  |  | x |  |  | x |
| frames_index_west.csv | x |  | x |  |  |  |  | x | x | x | x |  | x |  |  |  |
| image_id_aliases.ini | x |  |  |  |  |  |  |  | x | x |  |  | x |  |  |  |
| image_lifecycle_events.xml | x |  | x |  |  | x | x |  |  |  |  |  | x |  |  |  |
| inference_run_registry.html | x |  |  |  |  |  | x |  |  |  |  |  | x | x |  |  |
| inference_run_registry_mirror.html | x |  |  |  |  | x | x |  |  |  |  |  | x | x |  | x |
| ks_boxes_part1.jsonl | x | x | x |  | x | x | x |  |  | x | x | x | x |  | x |  |
| ks_boxes_part2.jsonl | x | x | x |  | x | x | x |  |  | x | x | x | x |  | x |  |
| ks_boxes_part3.json | x | x | x |  | x | x | x |  |  |  | x | x | x |  | x |  |
| ks_boxes_part4.parquet | x | x | x |  | x | x | x |  |  |  | x | x | x |  | x |  |
| ks_boxes_part5.json | x | x | x |  | x | x | x |  |  |  | x | x | x |  | x |  |
| ks_boxes_part6.csv | x | x | x |  | x | x |  | x | x | x | x | x | x |  | x |  |
| ks_boxes_resubmitted.json | x | x | x |  | x | x | x |  |  |  | x | x | x |  | x | x |
| ks_class_codebook.pdf | x |  |  |  |  |  | x |  |  |  | x |  |  | x |  |  |
| labeling_qa_export.xlsx | x |  | x |  |  | x | x | x |  |  |  |  | x |  |  | x |
| labeling_qa_portal.html | x |  | x |  |  |  | x |  |  |  |  |  |  | x |  |  |
| leakage_waivers.json | x |  | x |  |  | x | x |  |  |  | x |  | x |  |  |  |
| nl_boxes_batch01.csv | x |  |  | x | x | x | x | x | x | x | x |  | x |  | x |  |
| nl_boxes_batch02.csv | x |  |  | x | x | x | x | x | x | x | x |  | x |  | x |  |
| nl_boxes_batch02_reextract.csv | x |  |  | x | x | x | x | x | x | x | x |  | x |  | x | x |
| nl_boxes_batch03.tsv | x |  |  | x | x | x | x | x | x | x | x |  | x |  | x |  |
| nl_boxes_batch04.csv | x |  |  | x | x | x | x | x | x | x | x |  | x |  | x |  |
| nl_boxes_q3_extra.xlsx | x |  |  | x | x | x | x |  |  |  | x |  | x |  | x |  |
| node6_ingest_replica.db | x |  |  |  | x | x | x |  |  |  |  | x | x |  |  | x |
| node6_rerun_store.db | x |  |  |  | x |  |  |  |  |  |  | x | x |  |  |  |
| node_quarantine_report.pdf | x |  |  |  |  | x |  |  |  |  |  |  | x | x |  |  |
| ob_boxes_east.xml | x |  |  |  | x | x | x |  |  |  | x |  | x |  | x |  |
| ob_boxes_resubmitted.xml | x |  |  |  | x | x | x |  |  |  | x |  | x |  | x | x |
| ob_boxes_west.xml | x |  |  |  | x | x | x |  |  |  | x |  | x |  | x |  |
| ob_label_aliases.yaml | x |  |  |  | x |  | x |  |  |  |  |  | x |  |  |  |
| orientation_corrections.pdf | x |  | x |  |  | x | x |  |  |  |  |  | x | x |  |  |
| preds_r1_n1.csv | x | x |  | x | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r1_n2.jsonl | x | x |  | x | x |  |  |  |  | x |  | x | x |  | x |  |
| preds_r1_n3.parquet | x | x |  |  | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r1_n4.tsv | x | x |  |  | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r1_n5.xml | x | x |  | x | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r1_n7.csv | x | x |  | x | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r2_n1.csv | x | x |  | x | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r2_n2.jsonl | x | x |  | x | x |  |  |  |  | x |  | x | x |  | x |  |
| preds_r2_n3.parquet | x | x |  |  | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r2_n4.tsv | x | x |  |  | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r2_n5.xml | x | x |  | x | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r2_n7.xlsx | x | x |  | x | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r3_n1.csv | x | x |  | x | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r3_n2.jsonl | x | x |  | x | x |  |  |  |  | x |  | x | x |  | x |  |
| preds_r3_n2_replay.jsonl | x | x |  | x | x | x | x |  |  | x |  | x | x |  | x | x |
| preds_r3_n3.parquet | x | x |  |  | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r3_n4.tsv | x | x |  |  | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r3_n5.xml | x | x |  | x | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r3_n7.xlsx | x | x |  | x | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r4_n1.csv | x | x |  | x | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r4_n2.jsonl | x | x |  | x | x |  |  |  |  | x |  | x | x |  | x |  |
| preds_r4_n3.parquet | x | x |  |  | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r4_n4.tsv | x | x |  |  | x |  |  | x | x | x |  | x | x |  | x |  |
| preds_r4_n5.xml | x | x |  | x | x |  |  |  |  |  |  | x | x |  | x |  |
| preds_r4_n7.xlsx | x | x |  | x | x |  |  |  |  |  |  | x | x |  | x |  |
| preprocess_n1.log | x |  |  |  |  | x |  | x |  | x |  |  | x |  |  |  |
| preprocess_n2.log | x |  |  |  |  | x |  | x |  | x |  |  | x |  |  |  |
| preprocess_n3.log | x |  |  |  |  | x | x | x |  | x |  |  | x |  |  |  |
| preprocess_n4.log | x |  |  |  |  | x | x | x |  | x |  |  | x |  |  |  |
| preprocess_n5.log | x |  |  |  |  | x | x | x |  | x |  |  | x |  |  |  |
| privacy_register_export.tsv | x |  |  |  |  | x | x | x | x | x |  |  | x |  |  | x |
| privacy_requests.mbox | x |  | x |  |  | x |  |  |  |  | x |  | x |  |  |  |
| relabel_campaign_2026q3.xlsx | x |  | x |  |  |  |  | x |  |  |  |  | x |  | x |  |
| relabel_campaign_status.json |  |  | x |  |  | x | x |  |  |  | x |  |  |  |  |  |
| release_governance.docx | x |  |  |  |  |  | x |  |  |  |  |  | x | x |  |  |
| release_governance_v2_signed.docx | x |  |  |  |  | x | x |  |  |  |  |  | x | x |  | x |
| rerun_batches.toml | x |  |  |  |  | x | x |  |  |  |  |  | x |  |  |  |
| sequence_membership.xlsx | x |  |  | x |  |  |  | x |  |  |  |  | x |  |  |  |
| taxonomy_v3_charter.docx | x |  |  |  |  |  |  |  |  | x |  |  | x | x |  |  |
| train_hash_index_a.parquet |  | x |  |  | x | x |  |  |  |  | x |  |  |  |  |  |
| train_hash_index_b.csv |  | x |  |  | x | x |  | x | x | x | x |  |  |  |  |  |
| train_hash_index_c.db |  | x |  |  | x | x |  |  |  |  | x |  |  |  |  |  |
| train_hash_index_d.txt |  | x |  |  | x | x |  |  |  | x | x |  | x |  |  |  |
| train_hash_index_e.jsonl |  | x |  |  | x | x |  |  |  | x | x |  |  |  |  |  |
| train_hash_index_f_dedup.parquet |  | x |  |  | x | x | x |  |  |  | x |  | x |  |  | x |
| train_hash_index_h.txt |  | x |  |  | x | x |  |  |  | x | x |  |  |  |  |  |
| train_hash_index_legacy.txt |  | x |  |  | x | x | x |  |  | x | x |  | x |  |  | x |
| training_sequence_register.pdf | x |  |  |  |  | x |  |  |  |  |  |  | x | x |  |  |
| vendor_batch_receipts.docx | x |  | x |  |  |  |  |  |  |  | x |  |  | x |  |  |

**Red lines.** No graded value may depend on anything outside instruction.md and `/app/data`; the verifier never reads `/app/data` (it rebuilds the estate from its seed); the oracle reads only its ESTATE_DIR; nothing in the agent image carries an answer.

## Solution shape

1. Load identifier rules (aliases, homoglyphs) and the delivery manifest.
2. Load the run registry and its mirror for unlisted sequences (each with its own errata applied), label maps and the model vocabulary crosswalk.
3. Assemble capture records from the frames indexes (replica only for cameras missing from both), then the roster (ops copy only for missing cameras) and CONFIRMED clock skews.
4. Resolve geometry and orientation (dim_scale, 0 x 0 and REENCODED dims, latest confirmed correction).
5. Resolve exclusion evidence: lifecycle, integrity, privacy register plus mailbox plus legal holds, board decisions from both governance revisions up to the cutoff.
6. Build the training hash index from the shards, shard g rows and v6-core legacy rows, then classify leaks with a pigeonhole index and waivers.
7. Load annotation rules (assignment, conventions with errata, receipts, crosswalks, codebook windows, aliases, errata, QA decisions, campaign) and every vendor record, replacing accepted resubmitted batches and the short delivery's missing partitions.
8. Decide every candidate (precedence of PES-3 s9) and build ground truth.
9. Collect detection records per run and image from exactly one source, invert the letterbox exactly, calibrate, threshold, NMS, cap.
10. Match, compute AP, operating points, leaderboard and reconciliation; write the eight artifacts.

## Ordered plan

1. Read PES-3 end to end, then the Data Authority Policy and the other documents it names (R1, R2).
2. Inspect the self-declarations of every re-export, mirror, replica, replay, reissue, resubmission, draft and signed copy (R3).
3. Write format readers and check their record counts against the manifest partitions file by file (R4, R6, R17).
4. Implement identifiers, capture time and geometry; spot-check DST-day frames (R13).
5. Implement leakage with an index and check the membership rules (R14).
6. Implement exclusions and check multi-reason candidates and the population invariant (R9, R19).
7. Implement ground truth with errata and QA; check the applied errata values and the re-extract partition counts; cross-check per-image counts (R5, R10, R18).
8. Implement detections with label maps, letterbox, calibration and post-processing; check raw score ranges and knot monotonicity, recompute one image per run outside the engine and inspect a capped image (R15, R16, R29, R30, R31, R34).
9. Implement scoring exactly as PES-3 s12 to s14 state; recompute an operating point and the release decisions outside the engine (R20, R28, R32, R33).
10. Run on an altered estate built from the delivered one, twice for determinism, and time the full run (R7, R8, R12).
11. Report the release decision, the demoted sources and the checks run (R21 to R23).

Human-expert estimate (about 30 working hours, three to four days): reading the 20 documents and mapping authority rules 5 h; format readers for 19 formats with their quirks 7 h; capture time, geometry and identifiers 3 h; leakage index and exclusions 3 h; ground-truth curation 4 h; detection provenance and post-processing 3 h; COCO-style scoring, operating points and gating 2 h; reconciliation and cross-checks against the manifest 2 h; fresh-estate testing and performance work 1 h.

## Pitfalls

- Treating the newest-looking file as authoritative: family_t16_decoy_disagreements and most family checks.
- Skipping a decoy entirely: baseline_rows_exact, family_t13_references, class_metrics_exact.
- Floating-point letterbox inversion or half-up rounding: family_t12_half_even_rounding.
- Reading only the first header of a delivery: family_t08_header_drift.
- Whole-file strict UTF-8 decoding: family_t10_mixed_encodings.
- Textbook COCO ignore matching or sklearn AP: class_metrics_exact.
- Choosing the release candidate by mAP alone: leaderboard_exact.
- Hardcoding anything from `/app/data`: every eval_estate_* check and negative_hardcoded_sample_answers.

## Provenance

```yaml
uuid: 56fe3bdd-00c6-5b13-a5c8-90a94ccc475e
instance_id: 56fe3bdd-00c6-5b13-a5c8-90a94ccc475e
task_name: terminal-bench/56fe3bdd-00c6-5b13-a5c8-90a94ccc475e
fix_patch_sha256: 3a779c8a7c6554d27cd329fa1345c7480bb46501af82478f3a4ab82463f6be29
solve_py_sha256: f21e6549e570415de9e331f218a1f9fb6a37ba2799e2f53fac6ef879e05a362f
language: python
trap_total: 2533
trap_loops: 60
test_channel_oracle_score: 1.0  # tests-only rewardkit run
# the judged channel is validated, never executed, so no judged score exists
```
