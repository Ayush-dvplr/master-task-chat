# VRX-BE-2614 bioequivalence analysis handbook (revision 5)

This handbook fixes how the VRX-BE-2614 bioequivalence analysis is computed from the bioanalytical
injection data up to the confidence intervals. Rule ids (H1 ... H22) are used by the output contract.
"The memo" is `ba_stat_governance_memo.pdf`; only tables marked IN FORCE apply, and inside Table R-1
only rows whose status is IN FORCE apply. "The workbook" is `bioanalytical_workbook_v3.xlsx`. "The
profile" is `analysis_profile_be.yml`. Revision 5 replaces revision 4. It changes subject identity
chains and the workbook date system (H4), exact calibration coefficients (H6), the draw-time correction
journal and skipped clock times (H13), the emesis window passes (H16) and the rounding cadence (H22).

## H1 Authority

- Governing: the memo, the workbook sheets `RunPlan`, `QCLots`, `Randomization` and the calibrator
  sheet named by `nominal_sheet` in the profile, the profile, the ingest catalog, the alias register,
  the integration audit trail, the standard exclusion requests, the reassay request log, both tube
  manifests, the relabel journal, both dose logs, both draw-time logs and their corrections, the
  adverse event listing, the disposition log, the site calendar and this handbook.
- Not governing: the rerun pack `nca_rerun_pack.md`, the published report and statistics, the LIMS
  cache, the run status dashboard, the bulletin, the statistics quick reference, the legacy method
  sheet, the draft SAP, the early randomization list, the potency certificates, catalog entries whose
  `active` is false and every file the catalog does not list.
- The profile is the only source of: `nominal_sheet`, `analytes` (analysed analytes, in report order),
  `pivotal_analytes` (in order; the first one is the first pivotal analyte), `parameters` (in report
  order), `alpha`, `be_lower_pct`, `be_upper_pct`, `lambda_z_min_points`, `lambda_z_adj_r2_tolerance`,
  `extrap_limit_pct`, `carryover_limit_pct`, `emesis_window_factor`, `isr_limit_pct` and
  `subjects_in_scope`.

## H2 Ingestion

- The injection feeds are the catalog entries with `active: true`, read with the layout named in the
  entry (`feed_layouts.md`).
- Every cell is trimmed. Tokens (types, statuses, actions, levels, runs, subjects, tubes, reasons,
  codes) are compared upper-case. Injection ids are upper-cased.
- Kilocount fields are multiplied by 1000 and rounded to the nearest integer count. The semicolon
  export writes a decimal comma.
- Dilution tokens `N`, `1:N` and `xN` all mean the dilution factor N.

## H3 Revisions and voids

- Records with the same injection id and revision are copies of one record and count once.
- A record is admissible when it is void, when its integration is AUTO, or when it is MANUAL and the
  latest audit trail entry (by `ts`) for that injection id and revision has status APPROVED and a
  reason code marked `Y` in memo Table C-1.
- The effective record of an injection is its admissible record with the highest revision. When the
  effective record is void the injection is removed. Revisions are resolved before voids are applied.
  An injection without any admissible record is not used (it is neither voided nor effective).

## H4 Runs, dates and identities

- Run tokens resolve through table `run_alias` of `entity_alias_register.sqlite`; a run id resolves to
  itself.
- RunPlan rows whose `study` is the profile `study_id` define the runs: analyte, run type
  (ORIGINAL, REASSAY or ISR), calibrator lot, QC lot and analysis date. Rows of other studies and note
  rows are not runs.
- The analysis date is a serial day number in the workbook's date system. When the `workbookPr`
  element of `xl/workbook.xml` carries `date1904="1"` (or `true`), serial n is 1904-01-01 plus n days;
  otherwise it is 1899-12-30 plus n days. Example: serial 45000 is 2023-03-15 in the 1900 system and
  2027-03-16 in the 1904 system.
- Run order is analysis date, then run id. Only runs of analytes listed in the profile are analysed.
- Subject tokens resolve through the rows of table `subject_alias` whose `study` is the profile
  `study_id`; a subject id of the Randomization sheet resolves to itself. Resolution repeats: when a
  token maps to another token that is not a Randomization subject, that token is resolved in turn,
  until a Randomization subject is reached. A token that never reaches one (it maps to nothing, or its
  chain comes back to a token already visited) is unresolved, and a record carrying it belongs to no
  subject. Example: `SCR-0001` maps to `XX-BE-0001-004`, which maps to `S004`, so `SCR-0001` is
  `S004`; one lookup stops at `XX-BE-0001-004`, which is not a subject.

## H5 Injection kinds

- Kinds: STD (levels CS1 to CS8), QC (LQC, MQC, HQC), DQC (dilution QC), UNK (a study or foreign
  sample), BLANK and ZERO. BLANK and ZERO injections are not used; their internal standard area may
  be zero.
- The response of an injection is its analyte area divided by its internal standard area.

## H6 Calibration

- Model and weighting per analyte come from memo Table M-2. The nominal concentration x of a
  standard is the `certified` value of (run calibrator lot, level) on the profile's nominal sheet.
- The curve minimises sum w (y - f(x))^2 over the retained standards, with w = 1/x^2 or 1/x as the
  table says, f(x) = a + b x (linear) or a + b x + c x^2 (quadratic). The coefficients are the exact
  minimiser, computed in rational arithmetic from the decimal nominal values and the integer area
  ratios, and then rounded as H22 says; every reading is made with the rounded coefficients.
- A response y reads back as x = (y - a) / b (linear) or x = 2 (y - a) / (b + sqrt(b^2 + 4 c (y - a)))
  (quadratic). A negative radicand gives no reading.
- Deviation % = 100 (reading - nominal) / nominal.

## H7 Calibration standard exclusions

1. Assignable cause: a request in `std_exclusion_requests.jsonl` whose status is APPROVED, whose code is
   marked `Y` in memo Table C-2 and whose injection is an effective standard injection of the named run
   removes that standard before any fit. Requests naming other injection kinds are ignored.
2. Iteration: fit the retained standards and read every retained standard back. The limit is
   `lloq_std_limit_pct` for level CS1 and `std_limit_pct` for the other levels. While at least one
   retained standard has |deviation| above its limit and more than (number of coefficients + 1)
   standards are retained, remove the single retained standard with the largest |deviation| / limit
   (ties: higher nominal, then higher sequence number) and refit.
3. A run with fewer than (number of coefficients + 1) standards after step 1 has no curve.

## H8 Run range

The run LLOQ and ULOQ are the lowest and highest nominal among the retained standards.

## H9 Run acceptance

A run is ACCEPTED unless one of these holds; the first that holds is its reason:

1. RULING: an IN FORCE `REJECT_RUN` row of memo Table R-1 names the run.
2. NO_CURVE.
3. STD_LIMIT: a retained standard is still outside its limit.
4. STD_COUNT: the fraction retained / total is below `min_std_fraction`, total being every effective
   standard injection of the run (assignable-cause exclusions included).
5. STD_LEVELS: fewer than `min_levels` distinct levels are retained.
6. QC_TOTAL: the fraction passing / total over the run's LQC, MQC and HQC injections is below
   `min_qc_fraction`.
7. QC_LEVEL: at some QC level, the fraction passing / injections at that level is below
   `min_qc_level_fraction`.

Fractions are compared exactly (4 of 6 is exactly 2/3). A QC passes when its reading exists and
|deviation| <= `qc_limit_pct` against the `certified` value of (run QC lot, level) in the QCLots sheet.
Without a curve no QC passes.

## H10 Dilution QC

A run whose effective study-sample injections include a dilution factor above 1 has DQC status PASS
when it holds at least two DQC injections and every DQC has |deviation| <= `dqc_limit_pct`, its
back-calculated value being reading x its own dilution factor; otherwise FAIL. Other runs have NA.

## H11 Study-sample results

- An UNK sample token resolves through the ACTIVE entries of `tube_relabel_journal.xml` (new to old)
  and is a study tube when the result appears in either tube manifest; otherwise it is foreign and
  not used.
- Tubes of subjects outside `subjects_in_scope` are dropped from every output.
- Reason: ISR when the run type is ISR; otherwise the reason of the reassay log row with the same
  tube, analyte and run whose status is not CANCELLED (normalised upper-case with `-` and spaces as
  `_`); otherwise ORIGINAL.
- Flag, first that holds: RUN_REJECTED (run not ACCEPTED), DQC_FAIL (dilution factor above 1 and DQC
  status FAIL), BLQ (reading below the run LLOQ), ALQ (no reading, or reading above the run ULOQ), OK.
- Concentration = reading x dilution factor for OK results, rounded as H22 says.

## H12 Reported concentration of a tube and analyte

1. An IN FORCE `EXCLUDE_SAMPLE` ruling naming the tube (directly or through an ACTIVE relabel) gives
   status EXCL, rule RULING.
2. Candidates are the results with flag OK, BLQ or ALQ whose reason is not ISR.
3. The base result is the earliest candidate (run order, then sequence number) with reason ORIGINAL or
   RUN_FAIL. No base gives NR, rule NONE.
4. A base ALQ uses the earliest candidate with reason ALQ and flag OK (status OK, rule ALQ_DILUTION);
   without one the status is NR, rule ALQ_NO_DILUTION.
5. A base BLQ gives status BLQ with the base reason as rule.
6. A base OK with at least two PK_REPEAT candidates (flag OK or BLQ) reports the median of the base and
   the first two repeats, BLQ counting as 0 (rule PK_REPEAT_MEDIAN; a zero median is BLQ). Otherwise
   the base value is reported with the base reason as rule.
7. A tube whose manifest status is NOT_COLLECTED gets status NOT_COLLECTED, rule NONE.

## H13 Times

- The dose instant is the DOSE event of the subject and period. `dose_admin_p1.csv` writes site wall
  clock without an offset; `dose_admin_p2.xml` writes ISO 8601 with an offset.
- The draw instant comes from the draw-time logs and the correction journal
  `draw_time_corrections.ndjson`. Only journal entries of field `drawn_local` with status POSTED count
  at all. An entry's `action` is SET (also when the field is absent) or REVERSE. A REVERSE entry names
  in `reverses` the seq of an earlier entry of the same tube and cancels it. An entry is in effect when
  it counts and no REVERSE entry that is itself in effect names it; since a REVERSE entry only names a
  lower seq, deciding from the highest seq downwards settles every chain. The draw time of a tube is
  the value of its highest-seq SET entry in effect, or the logged value when there is none; an empty
  value means the tube has no draw time. Example: tube T logged 07:40 has SET 10 (08:05), SET 11
  (09:05), REVERSE 12 naming 11 and REVERSE 13 naming 12; 13 is in effect, so 12 is not, so 11 is and
  T is 09:05. Without entry 13, 12 cancels 11 and T is 08:05; without entries 10 and 13, T is 07:40.
- A wall clock without an offset converts with the site calendar: the offset in force is the base
  offset before the first transition and `offset_after` of the latest transition at or before the
  instant. A wall time that maps to two instants (the clock went back) takes the earlier one. A wall
  time that maps to no instant (it falls in the hour skipped when the clock went forward) is read with
  the offset in force before that transition. Example with base +01:00 and a transition to +02:00 at
  2027-03-28T01:00:00Z: local 2027-03-28 02:30 is skipped and reads as 01:30Z; with a transition back
  to +01:00 at 2026-10-25T01:00:00Z from +02:00, local 2026-10-25 02:30 occurs twice and reads as 00:30Z.
- Elapsed hours = (draw instant - dose instant) / 3600 s, rounded as H22 says. A nominal time of 0
  (written `0` or `PRE`) has elapsed time 0. A tube without a draw time is NO_TIME and is not used in
  NCA.

## H14 Formulation

The workbook Randomization sheet gives the sequence: TR is test in period 1 and reference in period 2,
RT the reverse.

## H15 Non-compartmental analysis

Per in-scope subject, dosed period and analyte:

- Points are the scheduled tubes (numeric nominal) with an elapsed time, ordered by elapsed time (ties
  by nominal). OK values are used as reported; BLQ is 0 before the first OK point and dropped after
  it; NR, EXCL, NOT_COLLECTED and NO_TIME tubes are dropped.
- A profile with fewer than three positive points is NOT_EVALUABLE.
- Cmax is the largest value and Tmax its first time; tlast and Clast are the last positive point.
- AUClast integrates from the first point to tlast: a falling segment with both ends positive uses
  (C1 - C2) / ln(C1 / C2) x (t2 - t1); every other segment uses (C1 + C2) / 2 x (t2 - t1).
- Lambda_z candidates are the positive points after the Cmax point. For each n from
  `lambda_z_min_points` to their count, regress ln C on t over the last n of them (ordinary least
  squares). A fit is eligible when its slope is negative; adjusted R^2 = 1 - (1 - R^2)(n - 1)/(n - 2).
  The chosen fit is the eligible one with the most points among those whose adjusted R^2 is at least
  the best eligible adjusted R^2 minus `lambda_z_adj_r2_tolerance`. No eligible fit gives
  NO_LAMBDA_Z.
- lambda_z = -slope; half-life = ln 2 / lambda_z; Clast_pred = exp(intercept - lambda_z tlast);
  AUCinf = AUClast + Clast_pred / lambda_z; extrapolation % = 100 (Clast_pred / lambda_z) / AUCinf.
  Extrapolation above `extrap_limit_pct` flags EXTRAP_GT_LIMIT.

## H16 Analysis populations

Each randomized subject (Randomization sheet) gets, per analysed analyte, the first applicable reason:

1. NOT_IN_SCOPE: not in `subjects_in_scope`.
2. RULING: an IN FORCE `EXCLUDE_SUBJECT` row names the subject (tokens resolve as H4 says; rows of
   other studies do not apply).
3. WITHDRAWN: the disposition log has a WITHDRAWN event for the subject.
4. INCOMPLETE: a period has no DOSE event.
5. EMESIS: the subject is emetic in the pass the analysis settles on (below).
6. NOT_EVALUABLE: either profile of the analyte is NOT_EVALUABLE.
7. CARRYOVER: in either period the reported pre-dose (nominal 0) OK value exceeds
   `carryover_limit_pct` / 100 x Cmax of that profile.

Emesis is decided in passes. The candidates are the subjects in scope without a RULING, WITHDRAWN or
INCOMPLETE reason. In a pass, a candidate is emetic when an adverse event of this study whose
preferred term is marked `Y` in memo Table E-1 starts between the dose instant of its period and the
pass window after it, both ends included, the onset being measured in elapsed hours rounded like draw
times. The pass window is `emesis_window_factor` x the mean Tmax (arithmetic mean) of the evaluable
reference-formulation profiles of the first pivotal analyte over the candidates, leaving out, from
pass 2 on, the candidates found emetic by the pass before. The passes stop at the first pass whose
emetic set equals the set of an earlier pass. If that earlier pass is the one just before, the analysis
settles on the last pass (CONVERGED). Otherwise the passes cycle (CYCLE) and the analysis settles on
the pass with the largest window among the passes from the repeated one to the one before the last,
the earlier pass on equal windows. Example: pass 1 (window 4.20 h) finds {S1, S2, S3}; pass 2, leaving
them out, has window 4.00 h and finds {S1, S2}; pass 3, leaving out S1 and S2, has window 4.10 h and finds
{S1, S2}, the set of pass 2, so the analysis settles on pass 3 (CONVERGED). Had pass 3 found
{S1, S2, S3}, the set of pass 1, the passes cycle over passes 1 and 2 and settle on pass 1 (CYCLE).

A subject without a subject-level reason is included for Cmax and AUClast; for AUCinf it needs a
lambda_z in both periods (else PARAM_NA) and no EXTRAP_GT_LIMIT flag (else EXTRAP).

## H17 Average bioequivalence

For each analysed analyte and profile parameter, over the included subjects, with y = ln(value):

- d = (y period 2 - y period 1) / 2 per subject; n_TR and n_RT count the subjects per sequence.
- estimate = mean d (RT) - mean d (TR); s^2 = pooled within-sequence variance of d with
  n_TR + n_RT - 2 degrees of freedom; SE = sqrt(s^2 (1/n_TR + 1/n_RT)); MSE = 2 s^2;
  CV intra % = 100 sqrt(exp(MSE) - 1).
- Least-squares means per formulation: the average over the two sequences of the sequence mean of y;
  the geometric least-squares mean is exp of it.
- The confidence level is 100 (1 - 2 alpha) %. t is the memo Table T-1 value at p = 1 - alpha for the
  degrees of freedom. Ratio and bounds are 100 exp(estimate) and 100 exp(estimate -/+ t SE).
- Ratio and bounds are rounded half away from zero to two decimals; PASS needs the rounded lower bound
  >= `be_lower_pct` and the rounded upper bound <= `be_upper_pct`. Pivotal analytes are
  BIOEQUIVALENT when every parameter passes; other analytes are SUPPORTIVE and their results INFO.
- Fewer than one subject in a sequence, or zero degrees of freedom, gives NOT_ESTIMABLE.

## H18 Mean profiles

Per analysed analyte, over the subjects included for its Cmax: per formulation and scheduled nominal
time, OK values as reported and BLQ as 0 (other statuses skipped); n, arithmetic mean and SD with
divisor n - 1 (empty below two values).

## H19 Incurred sample reanalysis

Per analysed analyte: every tube with reported status OK and an ISR result with flag OK forms a pair
with the earliest such ISR result. diff % = 100 (repeat - reported) / mean(repeat, reported); a pair is
within when |diff %| <= `isr_limit_pct`. ISR passes when within x 3 >= pairs x 2 and there is a pair.

## H20 Comparison with the published report

Per subject, period, analyte and parameter (Cmax, AUClast, AUCinf) present in either the published
report or the recomputation: diff % = 100 (recomputed - published) / published; MATCH when
|diff %| <= 1, DIFF otherwise, ONLY_PUBLISHED or ONLY_RECOMPUTED when one side is empty.

## H21 Formats

Delimited files have a header row and LF line ends, and every file ends with a newline. Instants are
ISO 8601 UTC with `Z`. Empty values are empty cells (delimited) or null (JSON). Booleans in delimited
files are Y and N. Counts and other whole-number fields are written as integers. Every other number is
written as its value rounded half away from zero to six significant digits; a value that H22 already
rounded to fewer digits is written as it is. Trailing zeros and exponent notation do not change a
written value (`12.3400` and `1.234e1` both denote 12.34), and a value lying within one part in 10^12
of a rounding midpoint may be rounded to either neighbour.

## H22 Rounding cadence

Values are rounded at these stages, half away from zero, and every later step uses the rounded value:

1. Calibration coefficients a, b and c (H6): six significant digits.
2. Study-sample concentrations (H11): four significant digits. Reported values, PK-repeat medians,
   ISR pairs, NCA, carryover and mean profiles all use these.
3. Elapsed hours of draws (H13) and emesis onsets (H16): four decimal places.
4. Ratio and confidence bounds (H17): two decimal places, alongside the unrounded values.

Nothing else is rounded before it is written: responses, readings, deviations, QC values, regression
fits, NCA parameters, medians and statistics are carried at full precision. Example: a reading of
12.34567 ng/mL at dilution 10 is 123.4567 and is used and written as 123.5; a draw 25 h 1 min after the
dose is 25.0167 h; a fitted slope of 0.0118246813 becomes 0.0118247 before any reading is made.
