# EA-IRMS batch recomputation handbook (revision 9)

Applies to facility batch reports of d15N versus AIR and d13C versus VPDB measured by elemental
analyser isotope-ratio mass spectrometry. Rules are numbered H1 to H17. Every rule carries a worked
example on toy values that do not come from any batch.

## H1 Authority

1. This handbook.
2. The governance memo `governance_memo.pdf`. Only tables whose title ends in `[IN FORCE]` apply.
   Tables marked `[WITHDRAWN ...]` or `[SUPERSEDED]` have no force, even when printed first.
3. The reference workbook `reference_workbook.xlsx`, and within it only the sheets that the analysis
   profile names (`rm_sheet`, `qc_sheet`, `elemental_sheet`, `weights_sheet`).
4. `analysis_profile.yml` and `site_clock.yaml`.
5. Operational records: shard exports, `ingest_catalog.json`, `sequence_tables.xml`,
   `tray_corrections.ndjson`, `alias_register.sqlite`, `reintegration_audit.db`,
   `session_events.psv`, `autosampler_events.txt`, `rm_capsule_register.psv`, `capsule_flags.jsonl`,
   `balance_calibration.tsv`, `sample_manifest.csv`, `client_requests.tsv`.

The published results, the published session parameters, the saved rerun pack, the LIMS cache, the
QC dashboard and the noticeboard carry no authority; they are inputs only to the comparison reports.
In `stat_quick_reference.txt` only Section AW (molar masses) is authoritative; its statistical
tables are superseded by the memo.

## H2 Tokens and aliases

Tokens are compared after trimming surrounding whitespace and upper-casing.

- A canonical session id matches `SQ-dddd-dd` or `LN-dddd-dd`. Any other session token resolves
  through table `session_alias`: a row applies when its `project` is `*` or equals the project of the
  record that carries the token. Follow rows until a canonical id is reached.
- A canonical instrument is `K1` or `K2`. Other instrument tokens resolve through
  `instrument_alias`, following rows until a canonical instrument is reached.
- Canonical materials are `RM-GLU-L`, `RM-GLU-H`, `RM-CAF` (class RM), `QC-SED`, `QC-MUS`, `QC-ALG`
  (class QC), `ELM-ACT` (class ELM), `BLK` (class BLK), `COND` (class COND) and every `sample_id` of
  `sample_manifest.csv` (class SAMPLE). Other material tokens resolve through `material_alias`: a row
  applies when its `project` is `*` or the session's project and its `valid_from` is on or before the
  session date (H6). When several rows apply to one token the row with the latest `valid_from`
  wins. Follow rows until a canonical material is reached. A token with no applicable row that equals
  a `client_id` of `sample_manifest.csv` resolves to that sample.

Example: rows `RUN-K9-9901 -> SQ9999-01` (`*`) and `SQ9999-01 -> SQ-9999-01` (`*`) resolve
`run-k9-9901 ` in two steps. Rows `QX -> QC-SED` (`*`, valid_from 2020-01-01) and `QX -> QC-MUS`
(`*`, valid_from 2026-05-02) send `QX` to QC-SED in a session dated 2026-05-01 and to QC-MUS in a
session dated 2026-05-02.

## H3 Site clock

The offset in effect at instant u is `base_offset`, replaced by `offset_after` of every transition
whose `at_utc` is on or before u. A local wall time maps to the instant u with u + offset(u) equal to
it. A wall time that names two instants (a repeated hour) means the earlier instant. A wall time
that names no instant (a skipped hour) is read with the offset in effect before that transition.

Example with base +01:00 and a transition to +02:00 at 2030-03-31T01:00:00Z and back to +01:00 at
2030-10-27T01:00:00Z: `2030-10-27 02:30` is 2030-10-27T00:30:00Z (the earlier of 00:30Z and 01:30Z);
`2030-03-31 02:30` does not exist and is read with +01:00 as 2030-03-31T01:30:00Z.

## H4 Ingestion

1. Replay `ingest_catalog.json` events in event order. A segment (file, session) is active when its
   latest REGISTER or RETIRE event is REGISTER. VERIFY events change nothing. The session of an
   event resolves with the catalog project.
2. Read only files that have at least one active segment. Process files in the order of each file's
   first REGISTER event, and records within a file in document order (SQLite rows in ascending
   primary key or rowid order, the EAV table in ascending `rec`).
3. A peak record is one peak of one element. In the wide layout every filled element block of a row
   is one record.
4. Filters, applied in this order to every record: another project (`other_project`); a reference
   gas peak (`reference_peaks`); a session whose segment in this file is not active
   (`inactive_segment`); a record whose canonical session, counter, element and revision equal those
   of an earlier record that passed every filter (`duplicates`).
5. Revision admission. Revision 0 is always admitted. Revision r of (session, counter, element),
   r of 1 or more, is admitted when the latest `audit_trail` entry for that project, session,
   counter, element and revision (latest `entered_utc`, ties broken by the higher `entry_id`) has
   action APPROVE and a `reason_code` whose status in memo Table C-1 is ACCEPTED. The `gas` column of
   the audit trail uses the element tokens of maps E1 or E2 of the feed layouts.
6. The selected revision is the highest admitted revision. The void test applies to the selected
   revision only: when it is void the injection element is dropped, with no fall back to an older
   revision. Counters: `revisions_not_admitted` counts candidate revisions that are not admitted,
   `revisions_superseded` counts admitted revisions below the selected one, `voided` counts injection
   elements dropped by the void test, `kept` counts the rest.

Example: revisions 0, 1, 2 with revision 2 not admitted and revision 1 void: the selected revision is
1, it is void, the element is dropped; counters not admitted 1, superseded 1, voided 1.

## H5 Positions and materials

The position on a record is the autosampler counter. In `autosampler_events.txt` only SKIP events
in state `ok` count, once per event id; the counter of a SKIP event is the number in its detail
field, and its session token resolves with the profile project. In a session the tray position of counter c is c plus the
number of counted SKIP events (one per event id) whose counter is less than or equal to c; two
SKIP events with different ids at the same counter count twice. Trays no counter reaches were
skipped and never measured.

The material of a tray is its token in `sequence_tables.xml`, unless `tray_corrections.ndjson`
settles otherwise. Consider entries of the session's project with field `token` and status POSTED;
statuses and actions compare case-insensitively. A REVERSE entry cancels the entry its `reverses`
names; cancelling a REVERSE restores its target. The tray takes the value of the SET entry with the
highest `seq` that is still in effect; with none in effect it keeps the sequence token. The token then
resolves under H2. The capsule of a tray is its `capsule` attribute, compared case-insensitively.

Example: SKIP at counter 17 and counter 30 put counter 16 on tray 16, counter 17 on tray 18 and
counter 30 on tray 32. Entries 11 SET X, 12 SET Y, 13 REVERSE 12 leave X; adding 14 REVERSE 13
restores Y.

## H6 Times

All records of one injection carry the same time. The session start is the time of counter 1, and
the session date is the local calendar date of the session start. Run minutes of an injection are the
seconds from the session start to the injection, less the part of each PAUSE to RESUME interval of
that session in `session_events.psv` that lies before the injection, divided by 60 exactly. Event
times are typed local wall times (H3). A session fails the leak check when its last LEAK_CHECK event
(by time, ties by event id) has detail FAIL.

Example: start 10:00:00Z, pause 11:00 to 11:40 local at +01:00, injection at 10:55:00Z: run minutes
are 55 - 40 = 15.

## H7 Exclusions

Before any computation an injection (both elements) is excluded when memo Table R-1 has an IN FORCE
EXCLUDE_POSITION ruling of the session's project whose target is `<session token>/<tray>`, or when
its capsule has a flag in `capsule_flags.jsonl` whose effect in memo Table X-1 is EXCLUDE. Capsule
ids compare case-insensitively everywhere. An
excluded injection takes part in nothing below. The ledger names the ruling id, else the flag code.

## H8 Linearity

Linearity sessions are the sequences of kind LINEARITY. For each linearity session and element the
points are its non-excluded ELM-ACT injections with x = area (Vs) and y = raw delta. With at least
`linearity_min_points` points the slope is the least-squares slope rounded to 6 decimals; with fewer
the session has no slope for that element.

An analytical session on instrument I with session date D uses, per element, the latest linearity
session on I with session date D that started before it and has a slope; failing that, the latest
linearity session on I with a slope whose session date lies from D minus `linearity_lookback_days`
to D minus 1. The slope is applied when its absolute value is at least the memo Table L-1 threshold
(status APPLIED); a smaller slope is not applied (BELOW_THRESHOLD); with no linearity session the
status is NONE. The slope not applied counts as 0.

d_lin = d_raw - k x (A - a_ref), with a_ref per element from the profile, rounded to 4 decimals.

Example: k = 0.006000, A = 20.0000, a_ref = 15: 1.2340 - 0.006 x 5 = 1.2040.

## H9 Drift

Drift points are the non-excluded injections of the profile `drift_material`, x = run minutes,
y = d_lin. With at least `drift_min_points` points the slope is the least-squares slope rounded to 8
decimals (status FITTED); otherwise 0 (INSUFFICIENT). The anchor is the mean x of the drift points
rounded to 4 decimals. d_drift = d_lin - slope x (x - anchor), rounded to 4 decimals.

## H10 Blank

Blank capsules are the non-excluded BLK injections whose area is at most the memo Table A-1
`blank_area_max_vs`; BLK injections above it are rejected. A_b is their mean area (4 decimals) and
d_b their mean raw delta (3 decimals); with no blank both are 0.
d_blank = (d_drift x A - d_b x A_b) / (A - A_b), rounded to 4 decimals.

Example: d_drift 2.0000, A 10.0000, d_b -1.000, A_b 0.1000: (20 + 0.1) / 9.9 = 2.0303.

## H11 Normalization

The reference set of an element is memo Table N-2. Candidate points are the non-excluded RM
injections of set materials whose amplitude lies inside memo Table A-1 (bounds included). Every set
material needs at least 2 candidates; otherwise the status is NO_NORMALIZATION. The y value of a
point is the certified value of its capsule lot (`rm_capsule_register.psv`) in the workbook sheet
named `rm_sheet`, column `d15N_air` or `d13C_vpdb`; x is d_blank.

Fit y = slope x x + intercept by least squares. While the point with the largest absolute residual
exceeds the N-2 reject limit: stop with LIMIT_STOP when removing it would leave its
material with fewer than 2 points; stop with MAX_REJECT when N-2 `max_rejections` points are already
removed; otherwise remove it and refit. With no residual above the limit the status is CONVERGED.
`fits` counts the fits made. A residual is the certified value minus the fitted value; removed
residuals are reported to 4 decimals; the final slope and
intercept are rounded to 6 decimals and d_norm = slope x d_blank + intercept, rounded to 3 decimals,
for RM, QC, ELM and SAMPLE injections.

## H12 Elemental content

Capsule mass = `mass_mg` of `weights_sheet` times the factor of `balance_calibration.tsv` for the
capsule's balance with valid_from on or before the weigh date and valid_to after it, rounded to 4
decimals. The response factor of a session and element is the mean over its non-excluded ELM-ACT
injections of (mass x 1000 x pct / 100) / (A - A_b) in micrograms per Vs, rounded to 6 decimals,
where pct is the `elemental_sheet` row of the capsule lot with status IN USE. For RM, QC and SAMPLE
injections pct = (A - A_b) x K / (mass x 1000) x 100, rounded to 3 decimals.

## H13 Session acceptance

Per session and element the reasons, in this order, are NO_NORMALIZATION; SLOPE when the slope lies
outside the N-2 `slope_min` to `slope_max` (bounds included); `QC:<material>` for every acceptance QC
material that fails; LEAK when the session failed the leak check. Acceptance QC materials are the
memo Table Q-1 materials for the element, in table order, except the profile `drift_material`. A
material is checked when the session holds at least one of its injections with d_norm: the mean
d_norm rounded to 3 decimals minus the assigned value (`qc_sheet` row with status CURRENT) is the
deviation, which fails when its absolute value exceeds the tolerance. The computed decision is
ACCEPT with no reason and REJECT otherwise. The latest (date, then ruling id) IN FORCE
ACCEPT_SESSION or REJECT_SESSION ruling of Table R-1 of the project whose target resolves to the
session and whose element is the element or ALL replaces the computed decision.

## H14 Replicates and reporting

Samples are the `samples_in_scope` of the profile. The effective request of a sample is its latest
ACTIVE row of `client_requests.tsv` (by requested_on, ties by request_id); `sample_ref` is a sample id
or a client id. An element outside the request is NOT_REQUESTED. The values are the d_norm of the
sample's non-excluded injections in sessions accepted for the element, ordered by session start and
tray. While at least 3 values remain: with s the n-1 standard deviation, stop when s is 0; take the
value farthest from the mean, G = its distance / s, and remove it when G
exceeds the memo Table G-1 value for n in the column of the profile `grubbs_alpha`; otherwise stop.
Comparisons are exact.

A sample element with n values is REPORTED (n of 2 or more), SINGLE (1) or NO_DATA (0). The mean is
rounded to 2 decimals, the sd (n of 2 or more) to 2 decimals and the mean pct of the kept injections
to 2 decimals. C:N molar = (pct_C / M_C) / (pct_N / M_N) from the reported 2 decimal pct values and
the molar masses of quick reference Section AW, rounded to 2 decimals, when both elements are
REPORTED or SINGLE.

Example: values 5.000, 5.010, 7.000, n = 3: mean 5.67, s 1.1518, G 1.1547 exceeds 1.1543, so 7.000
goes and 5.000, 5.010 are reported as 5.00 with sd 0.01.

## H15 Arithmetic and rounding

Arithmetic is exact on the decimal values written in the files: no binary floating point. Every
rounding is round half to even at the stated decimals, and every stage consumes the rounded value of
the stage before it:

| stage | decimals |
|---|---|
| linearity slope | 6 |
| drift slope, anchor | 8, 4 |
| blank mean area, mean delta | 4, 3 |
| d_lin, d_drift, d_blank | 4 |
| normalization slope, intercept | 6 |
| d_norm, QC mean | 3 |
| response factor, capsule mass | 6, 4 |
| injection pct | 3 |
| sample mean, sd, mean pct, C:N | 2 |
| run minutes in the ledger | 4 (exact value used in fits) |

Example: 2.0345 rounds to 2.034 and 2.0355 to 2.036 at 3 decimals; the mean of 1.244 and 1.246 is
exactly 1.245 and rounds to 1.24 at 2 decimals.

## H16 Reading the workbook

Sheets are found by name through `xl/workbook.xml` and its relationships, never by part file name.
The workbook is an ECMA-376 SpreadsheetML package; read cells, shared strings and positions as that
standard defines them, not by the habits of one writer.
The header row of a sheet is the first row whose first cell equals the key column name (`material`
or `capsule_id`); rows below whose second cell is empty are notes. Numeric text is trimmed. Date
cells are serial day numbers counted from 1904-01-01 when the `workbookPr` element carries
`date1904` set to 1 or true, and from 1899-12-30 otherwise.

Example: serial 45000 is 2027-03-16 under date1904 and 2023-03-15 otherwise.

Example rows: a header row `capsule_id | project | mass_mg | balance | weighed | operator` may sit
below two title rows; a later row holding only `continued from bench sheet 2` is a note.

## H17 Reading the memo

A table starts at a title row `Table <id>: <title> [<status>]` and continues on later pages under a
row `Table <id> (continued)` that repeats the header. Rows are rebuilt from the positioned text of
each page; a text line that begins with the word Table but is not a title row is prose.

The memo is a PDF 1.4 file. Its strings, text objects and text-positioning operators follow ISO
32000-1 (sections 7.3, 7.8 and 9.4); read them as that standard defines them, not by the habits of
one writer.

Example: three text objects at y 700 with x 36, 114 and 192 form one row of three cells, whatever
their order in the content stream; a cell may be a literal string, a hexadecimal string or a TJ
array whose numbers are spacing and carry no text.

## Glossary

- Session: one analytical or linearity sequence on one instrument.
- Injection element: one element (N or C) of one injection.
- Run minutes: elapsed time with pauses removed (H6).
- Reference set: the RM materials used to normalize one element (H11).
