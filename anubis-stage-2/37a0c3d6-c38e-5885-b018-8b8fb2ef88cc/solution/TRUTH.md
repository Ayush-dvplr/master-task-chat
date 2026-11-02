# TRUTH: 37a0c3d6-c38e-5885-b018-8b8fb2ef88cc

## Defect

The published VRX-BE-2614 report (`be_report_published.csv`, `be_statistics_published.json`) came out of the saved rerun pack `nca_rerun_pack.md`, and the pack breaks the governing rules at almost every stage. The governing sources are the memo `ba_stat_governance_memo.pdf` (IN FORCE tables only), the workbook `bioanalytical_workbook_v3.xlsx`, the profile `analysis_profile_be.yml` and the handbook `be_analysis_handbook.md` revision 5.

Focal defects of the published run (each is a graded behaviour of the rebuilt analysis):

1. Q01 reports the latest accepted LIMS result per tube; H12 reports the earliest accepted ORIGINAL or RUN_FAIL result, uses the ALQ dilution result, the PK-repeat median, and keeps ISR results out.
2. Q02 fits curves on target nominals with the withdrawn Table M-1 weighting and one exclusion pass; Table M-2 sets VRX linear 1/x^2 and M1 quadratic 1/x on the certified values of the sheet named by `nominal_sheet` (CertNominal_2026), with iterative removal (H7), assignable causes from Table C-2 and exact rational coefficients rounded to six significant digits (H6, H22).
3. Q03 trusts `run_status_dashboard.csv`; H9 decides acceptance with exact fractions and the per-level QC rule. Six runs change status: VRX-R003, M1-R004, VRX-R010 and M1-R025 become ACCEPTED (the lab used 67 percent and "more than 75 percent"), VRX-R006 and M1-R008 become REJECTED for QC_LEVEL (HQC 1 of 3). VRX-R020 and M1-R022 are rejected by IN FORCE rulings whose targets BR-VRX-020 and BR-M1-022 resolve through `run_alias`; the RESCINDED rulings on VRX-R002 and VRX-R008 do not apply.
4. Q04 sets BLQ to LLOQ/2; P-1 sets BLQ to 0 before the first quantifiable value and drops it after.
5. Q05 uses nominal hours; P-1 and H13 use actual elapsed hours from dose instant to draw instant, with the site calendar (the offset moves from +02:00 to +01:00 at 2026-10-25T01:00:00Z, so wall-clock arithmetic is wrong across it), the draw-time correction journal with its SET and REVERSE entries, and elapsed hours rounded to four decimals.
6. Q07 uses the linear trapezoid; P-1 uses linear-up/log-down.
7. Q08 takes the last three points; H15 selects lambda_z by adjusted R-squared with the profile tolerance.
8. Q09 uses observed Clast; P-1 (amendment A2) uses predicted Clast.
9. Q10 applies no population rules; H16 applies RULING, WITHDRAWN, INCOMPLETE, EMESIS (iterated window passes), NOT_EVALUABLE and CARRYOVER.
10. Q11 corrects for potency; P-1 sets `potency_correction` to none and amendment A4 is REJECTED.
11. Q12 is a paired T minus R analysis with t(0.975, n-1) from `stat_quick_reference.txt`; H17 uses the crossover contrast (half the period 2 minus period 1 difference, RT minus TR, pooled within-sequence variance) and the Table T-1 quantile at p = 1 - alpha (1.678660 at 46 degrees of freedom for alpha 0.05).
12. Q13 decides on unrounded bounds; H17 decides on bounds rounded half away from zero to two decimals.
13. Concentrations are left unrounded; H22 rounds study-sample concentrations to four significant digits before reporting, medians, ISR and NCA.

Traps (documented, each with a one-sentence inverse):

- Memo layout: every cell is a separate text object placed with an absolute `Tm`, shuffled within the page, written as literal, hexadecimal or TJ strings. Inverse: decompress each page stream, group text objects by y, order by x.
- Withdrawn tables printed first under the same header (P-0, M-1), a decoy normal quantile table (T-0) and rulings of another study. Inverse: use IN FORCE tables and rows of this study only.
- Workbook: sheet names reach their parts through `xl/_rels/workbook.xml.rels`; hidden CertNominal_DRAFT and Randomization_v0; decoy CertNominal_2026R; padded numeric text; `date1904="1"`. Inverse: select the sheet by name through the rels, read serial dates from 1904-01-01 (VRX-R001 serial 44876 is 2026-11-12).
- Subject alias chains: screening tokens such as SCR-5017 map to VRX-BE-2614-025, which maps to S025. Rows of VRX-FE-2609 reuse SCR-1668, SCR-3277 and SCR-5017. Inverse: follow `subject_alias` rows of this study until a Randomization subject is reached. These chains decide the RULING exclusion of S025, the WITHDRAWN status of S011 and S045 and the EMESIS status of S049.
- Correction journal: only POSTED `drawn_local` entries count; REVERSE entries cancel the entry they name, and a REVERSE naming a REVERSE restores its target (tube VB154541: SET 1048, REVERSE 1051, REVERSE 1054, so 1048 stays in effect); a PENDING reversal does nothing. Inverse: settle entries from the highest seq downwards and take the highest-seq SET still in effect.
- Emesis passes (H16): the window is `emesis_window_factor` x the mean Tmax of evaluable reference profiles of the first pivotal analyte over the candidates, recomputed after leaving out the previous pass's emetic subjects, stopping at the first repeated emetic set; a converging stop uses the last pass, a cycle uses the largest-window pass of the cycle. In the shipped corpus pass 1 (mean 2.1683 h, window 4.3366 h) marks S035, S044 and S049; pass 2 (window 4.1410 h) marks S044 and S049; pass 3 (window 4.2238 h) marks S044 and S049 again, so the analysis settles on pass 3 (3 passes, CONVERGED) and S035 (onset 4.2833 h) stays included. Decoys: Nausea (S008) and Retching (S023) are not emesis terms, S047 vomited during washout, S009 vomited outside the window, S045 is WITHDRAWN first. `lab_bulletin_nov.txt` describes the withdrawn single-pass median rule.
- Clock gaps (H13): a wall time in an hour skipped by a forward change reads with the offset before the change. The shipped calendar has no such time; it is graded on a held-out spring study.
- Rounding cadence (H22): coefficients six significant digits, concentrations four significant digits, elapsed hours four decimals, ratio and bounds two decimals; every later step uses the rounded value.
- Decoy files: the LIMS cache, the dashboard, the bulletin, the quick reference, the legacy method sheet, the draft SAP, the early randomization list, the potency certificates, the inactive catalog shard `ab_0re7.csv` and the uncatalogued `mv_runs_export.csv`.

## Load-bearing work

The solver must parse sixteen injection layouts (kilocount and decimal-comma fields, dilution tokens, four kind vocabularies), resolve revisions before voids with the audit trail and Table C-1, resolve runs, subjects (chains) and relabelled tubes, fit exact weighted curves with iterative removal, decide run acceptance and dilution QC, flag and report every tube, compute draw instants through the journal and calendar, run NCA with lambda_z selection, settle the emesis passes, apply the population precedence, and compute the crossover intervals. Values that exist only in binary files: the curve models, limits, fractions, C-1, C-2, E-1 codes, T-1 quantiles and rulings (PDF); the run plan, calibrator and QC certified values, randomization and the date system (XLSX).

Shipped results: VRX Cmax 92.36 [88.44, 96.44], AUClast 94.88 [91.22, 98.70], AUCinf 94.86 [91.20, 98.66], BIOEQUIVALENT; M1 is SUPPORTIVE. Published VRX ratios were 95.84, 98.68 and 98.54.

## Verification

Channel A (`tests/test_output.py`, rewardkit criteria) has 35 checks: 22 positive (positive total 70) and 13 negative (negative total 45).

- Ungated, weight 1 (6): deliverables present, the program writes exactly the twenty-two contract files on a fresh copy at another path, delimited headers, JSON top-level keys, manifest sizes and digests, UTF-8 with LF and a final newline.
- Gated shipped reports, weight 3 (8): standard back-calculation with QC results, ISR, lambda_z selection, exclusions with mean profiles, dedup with lineage, alias resolution, parameters used, and the summary with both published comparisons.
- Held-out re-execution, weight 5 (8): a reseeded corpus; a spring study (VRX-BE-2702) with evening dosing across a skipped hour and the 1900 date system; other Table M-2 weightings, limits and fractions with a 90 percent interval; M1 as first pivotal analyte with reordered parameters and other knobs; a corpus whose emesis passes cycle; a larger study with more relabels and reversal chains; the shipped corpus with new correction chains and reversals of shipped corrections; the shipped corpus under changed profile knobs, orders and scope.
- Full-core gate: every gated check requires the eight core reports (calibration fits, run acceptance, tube results, reported concentrations, sampling times, NCA parameters, populations, BE statistics) to be exact on the shipped corpus and on all eight held-out corpora. The instruction states this acceptance rule.
- Negatives: hardcoded shipped answers (-5), filename-dependent behaviour (-5), nondeterministic output (-3), grader paths in the source (-5), third-party imports (-3), echo of the published values (-3), withdrawn M-1 model (-3), linear trapezoid (-3), paired or two-sided interval (-3), unrounded concentrations (-3), single emesis pass (-3), REVERSE entries skipped (-3), one-hop subject alias lookup (-3).
- Comparison: numbers are compared under H21 (six significant digits, half away from zero, stage values as rounded, a value within one part in 10^12 of a midpoint may round either way); non-numeric cells compare exactly; JSON compares parsed values with booleans kept distinct.

Channel B (`tests/judge.toml`) has 35 criteria: positive total 92, negative total 23, 84 positive points on critically important criteria, five instruction-following criteria. Most positive trajectory criteria name one discovery: memo rows rebuilt by position, CertNominal_2026 CS1 0.4988, date1904 serial 44876, six-digit coefficients, the VB154541 reversal chain, the study filter on reused SCR tokens, the emesis passes, the first-pass S035 window, the cycle rule, the skipped-hour rule, the crossover contrast, T-1 1.678660 at 46 df, the H12 base result, the BR-VRX-020 and BR-M1-022 rulings and the VRX-R007 dilution QC failure. Six more check that the agent ran its program on copies of the corpus with a changed memo, site calendar, alias register, draw-time correction journal, adverse event listing and relabel journal, the inputs the instruction says change on later runs. The final-message criteria read facts that no output file carries, so no fact is graded in both channels: the defect list, the decoy sources set aside, S035 as the first-pass-only emesis subject, and a double-reversal tube with its surviving entry (VB154541 1048, VB672393 1075, VB880599 1128 or VB959733 1103). Negatives: presenting the published ratios (-5), potency correction from rerun pack step Q11 (-3), BLQ set to half the LLOQ as in step Q04 (-3), shell access to /tests or /logs/verifier (-5), writes under `/app/data` (-5), package installs (-1), clutter in `/app/out` (-1). No judged negative prices an act that a test negative also prices.

`tests/reward.toml` weights: test_output 0.007142857142857143 (0.5/70), judge 0.005434782608695652 (0.5/92).

Test-channel scores measured locally on the shipped bundle: the reference solution 70/70 = 1.000, an empty output 0.000, empty files at every path 0.014, a program that writes the shipped answers 0.014 (the hardcoding negative fires). Every single-rule variant of the reference solution scores at most 0.086 on the test channel. No judged-channel score is claimed for any run.

Is it solvable from agent-visible material alone? Yes: every rule is in the handbook, layouts, contract or memo, each new rule with a worked example on toy values. Do the checks grade what the instruction asks? Yes; the instruction names every report path and the exactness rule, and delegates columns and rounding to the contract and handbook. Is there a shortcut? No: the heavy weight re-runs the program on corpora built at grading time, and the gate requires the core on all of them.

## Root cause

The rerun pack was written against the lab's view of the data (bulletin, dashboard, legacy method sheet, LIMS cache, quick reference) instead of the governance memo, the workbook and the handbook, so it computes from target values, nominal times, latest results and paired statistics, ignores the correction journal, alias chains, populations and rounding cadence, and reports figures that are biased upwards for VRX.

## Solution shape

`solution/solve.py` is one standard-library program, `run_be.py DATA_DIR OUT_DIR`:

1. Read the profile, the memo (character scanner over positioned text objects), the workbook (rels mapping, date system), the alias register (run aliases; subject chains walked per study), the relabel journal, manifests, dose logs, draw logs and the correction journal (entries settled from the highest seq downwards), adverse events, disposition, audit trail, requests, reassay log and the catalogued shards.
2. Copies, admissibility, revisions then voids.
3. Per analysed run: assignable causes, exact Gauss-Jordan weighted fits in fractions with coefficients rounded to six significant digits, iterative removal, QC and DQC, acceptance reasons in order.
4. Study-sample results with four-significant-digit concentrations, then H12 reporting.
5. Elapsed hours (calendar with overlap and gap rules) rounded to four decimals; NCA and lambda_z.
6. Emesis passes on the mean reference Tmax with repeat detection; population precedence; crossover statistics.
7. Rendering with six-significant-digit numbers, then the manifest.

`solution/solve.sh` copies it to `/app/out/run_be.py` and runs it on `/app/data`.

## Ordered plan

1. Decode the memo and workbook; list IN FORCE tables and the nominal sheet.
2. Ingest active shards; apply copies, the audit trail, revisions and voids.
3. Resolve runs, subject chains and tubes.
4. Fit curves exactly, round coefficients, iterate removals, decide runs.
5. Flag and report tubes with rounded concentrations.
6. Settle the correction journal, convert wall clocks, round elapsed hours.
7. NCA, emesis passes, populations, crossover statistics.
8. Render every report under the contract; write the manifest; check the program on copies of the corpus with a changed memo, site calendar, alias register, draw-time correction journal, adverse event listing and relabel journal; run once on `/app/data`.

## Pitfalls

- Reading memo text in stream order instead of grouping by y and x.
- Taking M-1, P-0 or T-0 because they come first.
- Reading run dates in the 1900 system.
- Fitting in floats and rounding nothing, or rounding coefficients only at output.
- One alias lookup, or alias rows of the other study.
- Skipping REVERSE entries, or treating them as empty SET values.
- One emesis pass, or the bulletin's median rule, or a loop that never stops on the cycling corpus.
- No rule for skipped clock times.
- Rounding concentrations or elapsed hours only at the end.
- Paired analysis or the two-sided quantile.

## Provenance

- Bundle: 37a0c3d6-c38e-5885-b018-8b8fb2ef88cc, schema 1.4.
- Agent input: `environment/data/`, 51 files.
- solve.py SHA-256: cd37e8de9130151c16c74aefd51c7dd1bf863ebcc571ce2c5e1bac069c76926b
