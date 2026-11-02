# CBHS streamflow computation handbook (revision 11)

This handbook fixes how the Corvel Basin Hydrometric Service computes the quarterly streamflow record of a network
from its logger shards, field visits, discharge measurements and ice observations. Sections are cited as H1 to H18.
Every computed figure follows these rules. A rule that names a memo table, a workbook sheet or a register takes its
values from that table, sheet or register at run time. File names below are the names used in the data directory.

## H1 Order of authority

1. Tables of the review board minutes `hrb_26-04_minutes.pdf` whose title ends with `[IN FORCE]`.
   The status of a table is the bracketed text at the end of its title line. A table whose status is anything else
   (WITHDRAWN, SUPERSEDED, DRAFT) is history and is never applied. A table may continue on later pages under a
   line `Table <id> (continued)` that repeats the column header. Text lines of a single cell (titles, notes, page
   footers) are not table rows. Cells of a row share one baseline and sit in columns 86 points apart.
2. The sheets of the rating workbook `cbhs_rt_26q2.xlsx` named by the profile: `rating_sheet` for rating points,
   `index_sheet` for rating versions and `site_sheet` for site constants. No other sheet is applied, whatever its title.
   Sheet names are the names in `xl/workbook.xml`; the part file of a sheet is found through its relationship id in
   `xl/_rels/workbook.xml.rels`. The workbook date system is the `date1904` flag of `xl/workbook.xml`. A sheet holds a
   title, notes and one header row; rows after the header that hold fewer than two cells (such as `continued`) are notes.
3. Settings: for each site, a setting present in its entry of `site_overlay.yaml` wins; otherwise the value of the
   workbook site sheet where H2 names one; otherwise the value of the profile block of the network; otherwise the
   default of this handbook.
4. The registers: station master `stn_master.csv`, cross-reference `stn_xref.sqlite` with `xref_addendum.yml`,
   equipment register `eqp_reg.tsv`, datum history `dtm_hist.psv`, field visit ledger `fv_ledger_q2.db` with
   `fv_amend.xml`, measurements `qm_main_26q2.csv` and `qm_late.xml`, ice observations `ice_obs_j2.ndjson`,
   unit-value edits `uv_edits.jsonl`, the ingest catalog `ingest_catalog.json` and the shards it lists.
5. Everything else is informational: the saved compute pack, the published daily values, statistics and shift
   worksheet, the dashboard export, the unit-value cache, bulletins, quick references, draft handbooks, draft
   profiles and the legacy rating export. None of it is an input to any computed figure. The comparison reports of
   H17 read some of it only to compare.

## H2 Scope, period and settings

- A station is in scope when its station master row has status ACTIVE and its network equals the profile `network`.
  Sites are reported in ascending station id.
- `dv_profile.yml` names the network, `period_start` and `period_end` (LST dates; the end date is excluded).
  The block `networks.<network>` holds the settings of that network: rating_sheet, index_sheet, site_sheet,
  max_gap_minutes, min_coverage_fraction, record_margin_hours and drift_tolerance_ft. Blocks of other networks
  do not apply.
- The record window runs from period_start 00:00 LST minus record_margin_hours to period_end 00:00 LST plus
  record_margin_hours, half open.
- Drift tolerance of a site: overlay `drift_tolerance_ft`, else the non-empty `drift_tol_ft` of the site sheet,
  else the profile drift_tolerance_ft.
- Maximum gap of a site: overlay `max_gap_minutes`, else the profile max_gap_minutes.
- Drainage area of a site: `drainage_area_mi2` of the site sheet. The station master area is a legacy figure in km2.

## H3 Time

- `site_clock.yaml` gives standard_offset_minutes and dst_rule. Local standard time (LST) is UTC plus the standard
  offset all year. Local wall-clock time is LST plus 60 minutes while daylight time is in effect; the UTC start and
  end of daylight time of each year follow the dst_rule and are listed under `transitions`.
- A wall-clock time maps to the UTC instant whose wall-clock reading it is. Times inside the skipped spring hour
  do not occur in the data.
- An ISO time with a numeric offset is converted with that offset; a trailing Z means UTC.
- Every time written in a report is LST as `YYYY-MM-DD HH:MM`. A day is an LST calendar day.
- Workbook date serials count days in the workbook date system: day 0 is 1899-12-30 in the 1900 system and
  1904-01-01 in the 1904 system.
- A serial time (layout L18) is a fraction of LST days in the 1900 system; its instant is serial times 86400
  seconds rounded to the nearest whole minute.

## H4 Ingest and routing

- `ingest_catalog.json` lists the shard files in `file_order`, which is the processing order. A listed file that is
  absent from the directory is skipped. A file that is not listed is never read as a shard, whatever its name.
- A listed file is read with the layout id the catalog gives for it; `feed_layouts.md` describes every layout.
- Every reading value of a file is one record; a wide row gives one record per non-empty value. Lines that a layout
  marks as non-data (comments, repeated headers, heartbeats, notes, summary rows, page lines) are not records.
- Each record meets four tests in this order, and the first test it fails names its counter:
  1. its station token resolves (H5) at the record instant, else `unknown_site`;
  2. the station is in scope, else `out_of_scope`;
  3. an ACTIVE route of the same file, station and sensor covers the record instant, else `unrouted`.
     Routes are half-open UTC windows `[from_utc, to_utc)`. RETIRED routes never cover anything;
  4. the instant lies inside the record window, else `out_of_window`.
- A record that passes all four is `admitted`. Only admitted records take part in H6.

## H5 Station tokens

- A token is normalized by trimming it and writing it in upper case; an all-digit token shorter than 8 characters is
  left-padded with zeros to 8 characters.
- A normalized token equal to the id of a station master row is that station.
- Otherwise the cross-reference applies: the rows of table `xref` of `stn_xref.sqlite` and the rows of
  `xref_addendum.yml`. An addendum row whose normalized token and valid_from equal those of a register row replaces
  that register row. A row applies at instant u when `valid_from <= u < valid_to`; an empty or null valid_to is open.
  The target of the applying row is resolved again in the same way at the same instant, following at most six
  rows in all. A token with no applying row, or one that would need a seventh row, is unresolved.
- Tokens of the registers resolve at the instant of their entry: visit time, measurement instant (H11), ice entry
  time, edit time. Dashboard tokens resolve at 12:00 LST of the row date and cache tokens at the cached instant.
- Worked example: token `ashby-wr` normalizes to `ASHBY-WR`; a CHAIN row `ASHBYWR -> ASHBY-WR` and a SHORT row
  `ASHBY-WR -> 04117250` mean `ashbywr` resolves in two steps to `04117250`.

## H6 Revisions, duplicates and voids

- Admitted records with the same station, sensor and UTC instant are copies of one reading.
- The copy with the highest revision wins. Among copies of that revision, the copy in the file that comes latest in
  file_order wins. Copies of lower revisions count as `superseded`; the other copies of the winning revision count
  as `duplicates`.
- When the winning copy is a void, the reading is removed and counts as `voided`. A void never falls back to a
  copy of a lower revision.

## H7 Unit-value edits

- `uv_edits.jsonl` is applied in ascending `seq`, which is not its line order, to the readings that survive H6.
- An edit names a station token, a sensor and an LST time. Edits of stations out of scope are skipped and not
  listed.
- SET replaces the value and the unit (a value as the logger records it, before the datum offset) and sets the
  quality to G. It acts only on a reading that exists and is not deleted.
- DELETE removes an existing reading. RESTORE reinstates a reading as it was at its last DELETE; a RESTORE with
  no deleted reading to reinstate does nothing.
- An edit that does nothing is IGNORED; every other edit is APPLIED. Readings still deleted when the journal ends
  count as `edit_deleted`.

## H8 Quality, units, datum and sensors

- Quality codes are G (good), S (suspect), E (estimated) and X (fault); feed_layouts.md maps each layout
  vocabulary to them. A layout without a quality field gives G. After H7, readings of quality X are removed and
  count as `sensor_fault`; S and E readings are kept.
- Unit: a record that carries its own unit (a unit column, a value suffix, a block, row or series unit, or a fixed
  layout unit) uses it. A record without one uses the unit of the equipment register row of its station and sensor
  with the latest valid_from_lst at or before the instant, whatever the event of that row.
- Feet: ft = m / 0.3048 = cm / 30.48 = mm / 304.8, exactly.
- Datum: the gage-datum stage is the value in feet plus `offset_ft` of the ACTIVE row of `dtm_hist.psv` of the
  station and sensor with the latest valid_from_utc at or before the instant. WITHDRAWN rows never apply.
- Sensor selection: at each station and instant the primary (P) reading is used when one survives; otherwise the
  backup (B) reading. A backup reading at an instant whose primary reading survives counts as `backup_unused`.
  `kept` counts the selected readings.

## H9 Field visits and gage-height corrections

- Visits are the rows of table `visit` of `fv_ledger_q2.db` (time in LST from vdate and vtime HHMM; `logger_ft` is
  the uncorrected gage-datum stage the logger showed) with their reference readings in table `vref`.
- `fv_amend.xml` is replayed in ascending `no`: field `reference` sets the reading of the named method, `action`
  sets the action, `time` sets the visit time (LST), `logger` sets logger_ft and `void` removes the visit.
  Amendments of a voided visit do nothing. Action and method words compare without regard to case.
- A visit listed in memo Table V-1 is disregarded. Voided and disregarded visits take no part in corrections.
- The reference reading of a visit is TAPE when present, else WIRE, else STAFF. CSG readings are never used.
- error = reference - logger_ft. applied = error when the absolute error is at least the drift tolerance (H2),
  otherwise 0.
- The used visits of a site in time order v0 .. vn define the correction c(t). For tk <= t < tk+1:
  c(t) = ak + (bk+1 - ak) x (t - tk) / (tk+1 - tk), where bk+1 is the applied value of vk+1 and ak is 0 when the
  action of vk is RESET and the applied value of vk otherwise. For t >= tn, c(t) = an.
- Corrected gage height = gage-datum stage + c(t), computed exactly and rounded to 2 decimals (H18). Backup
  readings take the same c(t).
- Worked example: a RESET visit at 2026-01-10 12:00 and a visit at 2026-01-24 12:00 with applied +0.06 give
  c = 0.06 x 13/28 at 2026-01-17 00:00. A reading of 1.312 m with offset -0.50 is 4.304461942 - 0.50 + 0.027857143
  = 3.832319085 ft, so the corrected gage height is 3.83.

## H10 Ratings

- Versions are the rows of the index sheet whose status is ACTIVE (any case). The effective instant of a version is
  its effective_date serial (H3) at its effective_time, in LST. The version in force at instant t is the ACTIVE
  version of the site with the latest effective instant at or before t.
- The points of a version are the rows of the rating sheet with its rating_id: gh_ft, q_cfs and offset_ft. Cells
  may hold numbers or text with surrounding spaces. Points are taken in ascending gh.
- Memo Table R-2 errata replace q_cfs of the point with the same rating_id and gh_ft.
- Evaluation R(h): when h equals the gh of a point, R is the q of that point. Otherwise take segment i with
  gh_i <= h < gh_i+1, segment 0 when h is below gh_0, and the last segment when h is above the last point:
  beta = ln(q_i+1 / q_i) / ln((gh_i+1 - e_i) / (gh_i - e_i)), with e_i the offset of point i, and
  R = q_i x ((h - e_i) / (gh_i - e_i)) ** beta. When h is below gh_0 and h <= e_0, R = 0.
- R is computed in IEEE binary64 with natural logarithms and the power operator, then rounded to 4 significant
  figures (H18) from the exact value of the binary64 result. A gage height above the last point is above rating.
- Inverse R^-1(Q): take segment i with q_i <= Q < q_i+1 (segment 0 below q_0, the last segment above the last point) and
  h = e_i + (gh_i - e_i) x (Q / q_i) ** (1 / beta), in binary64, rounded to 2 decimals (H18).
- Worked example: points (2.00, 15.0, offset 1.20) and (3.00, 61.0, offset 1.20) give beta = 1.7298944 and
  R(2.50) = 34.741240 -> 34.74; R(1.20) = 0; R^-1(34.2) = 2.4882536 -> 2.49.

## H11 Measurements

- Measurements come from `qm_main_26q2.csv` (q_cfs) and `qm_late.xml` (cubic metres per second; cfs = cms /
  0.028316846592 exactly, without rounding). When both files hold a meas_no, the entry with the later entered_utc
  wins.
- The instant of a measurement is the midpoint of start and end, truncated down to the whole minute. Its station
  token resolves at that instant; measurements of stations out of scope are not reported.
- Memo Table M-1: verdict REJECT makes the measurement REJECTED; verdict REGRADE replaces the field grade with the
  grade of the table; ACCEPT, or no row, keeps the field grade.
- Record gage height: the exact mean of the corrected gage heights (H9) of the selected readings (H8) whose instant
  lies in [start, end], both ends included, rounded to 2 decimals. When there is none the measurement is NO_RECORD.
  The field sheet gage height is informational.
- Decisions are taken in this order: REJECTED; NO_RECORD; ICE when the instant lies in an ice period (H13) of the
  site, whatever the cover field says; otherwise the open-water evaluation.
- Open-water evaluation, per site in instant order, under the version in force at the instant: shift_in_use is the
  shift of the latest SHIFT decision so far under the same version, 0.00 when there is none; rated Q =
  R(gh + shift_in_use); deviation = (measured - rated) / rated x 100, rounded to 1 decimal; the tolerance is the
  memo Table T-2 percentage of the grade, and grade P has none. The decision is SHIFT when the grade has a
  tolerance and the absolute deviation is strictly greater than it, with shift = R^-1(measured) - gh; otherwise CHECK.
- ICE measurements: shift_in_use is the curve shift s(t) of H12 at the instant, rated Q = R(gh + s(t)) and
  k = measured / rated, rounded to 3 decimals.
- Worked example (points of H10): gh 2.50 with shift_in_use 0.04 gives rated R(2.54) = 36.61; a grade G measurement
  of 41.6 cfs deviates by 13.6 percent; R^-1(41.6) = 2.64, so the shift is 0.14.

## H12 Shift curves

- Each ACTIVE version of a site has a curve: a START point at its effective instant with shift 0.00, followed by
  the SHIFT points of its measurements in instant order.
- The shift s(t) at an instant under a version varies linearly in time between consecutive points and stays at the
  last point after it; it is rounded to 2 decimals.

## H13 Ice periods and winter factors

- `ice_obs_j2.ndjson` is replayed in ascending `entry`. ON and OFF entries create events at at_lst for their station
  (resolved at that time). AMEND sets the time of its target event to its own at_lst. WITHDRAW removes its target
  event. An AMEND or WITHDRAW whose target does not exist, or was withdrawn, does nothing.
- Per site, events sorted by time and then entry: an ON opens a period when none is open, an OFF closes the open
  period, and any other event does nothing. A period still open at the end has no end. A period is [on, off).
- The K points of a period are its ICE measurements (H11) as (instant, k). In the period K(t) is the first k up to
  the first point, varies linearly in time between points (rounded to 3 decimals) and keeps the last k after the
  last point. A period without K points uses default_k of memo Table W-1 for the site.
- In a period, Q = K(t) x Q_open rounded to 4 significant figures.

## H14 Unit values

- For every selected reading in the record window: gh = corrected gage height (H9); shift = s(t) of the version in
  force (H12); gh_eff = gh + shift; Q_open = R(gh_eff) (H10); in an ice period K and Q follow H13, otherwise
  Q = Q_open.
- Flags, in this order and written together with no separator: B for a backup reading, I inside an ice period,
  > above rating. A backup reading inside an ice period carries `BI`.

## H15 Daily values

- Per site and LST day of the period, take the selected readings in instant order. Between two consecutive readings
  at most max_gap_minutes apart (H2) Q varies linearly; a longer interval is a gap and carries nothing.
- The integral of a day is the integral of that piecewise-linear Q over the parts of the segments inside the day,
  with the values at the day edges interpolated on their segment. The coverage is the total duration of those parts.
- A day whose coverage is below min_coverage_fraction x 24 hours is INC and has no value. Otherwise the daily mean
  is integral / coverage, exactly, rounded with the discharge table of H18.
- Codes: INC; ICE when a reading of the day is flagged I; B when one is flagged B; > when one is flagged >; joined by
  `;` in that order. n_readings counts the readings whose instant lies in the day.
- Worked example: readings at 23:30 (40.10) and 00:30 (40.70) give 40.40 at midnight, and the half hour after
  midnight contributes (40.40 + 40.70) / 2 x 1800 to the next day.

## H16 Monthly and period statistics

- Months are the LST calendar months of the period. complete_days counts days with a value. mean is the exact mean
  of the rounded daily values of those days, rounded with the discharge table; min and max are taken over the same
  values. volume_af = their sum x 86400 / 43560, rounded to 1 decimal; runoff_in = volume_af x 12 / (drainage area x
  640), rounded to 2 decimals. complete is true when every day of the month has a value. A month without a complete
  day has empty values.
- Period: peak is the largest unit-value Q with its instant in the period, the earliest on ties. min_7day is the
  smallest exact mean of seven consecutive period days that all have values (rounded daily values), rounded with the
  discharge table, the earliest start on ties. mean is the discharge-table rounding of the exact mean of the rounded
  daily values of the days with values. Day counts follow the daily codes; shift_points and ice_measurements count
  SHIFT and ICE decisions.

## H17 Comparisons

- Published daily values: a row compares with the recomputed value of the same site and date. Differences are
  recomputed minus published. Equal values MATCH.
- Published shift worksheet: a row agrees when the recomputed decision is the same and, for SHIFT, the shift too.
  A row whose meas_no has no recomputed measurement is NOT_FOUND.
- Dashboard: a row disagrees when its daily value differs from the recomputed one (empty equals empty) or its ice
  flag differs from Y for a recomputed day coded ICE and N otherwise.
- Unit-value cache: an entry is CURRENT when a unit value exists at its instant with the same Q, STALE when it
  differs, MISSING when there is no unit value.

## H18 Rounding

- Every rounding is half to even, at the named points only: corrected gage height 2 decimals; record gage height
  2 decimals; R and K x Q_open 4 significant figures; R^-1 2 decimals; shift curve values 2 decimals; deviation
  1 decimal; k and K(t) 3 decimals; daily, monthly, seven-day and period means by the discharge table; volume
  1 decimal; runoff 2 decimals; coverage hours 2 decimals.
- Discharge table, with the band chosen from the unrounded value: below 1, 2 decimals; from 1 to below 10,
  1 decimal; from 10 to below 1000, whole numbers; 1000 and above, 3 significant figures.
- Arithmetic between rounding points is exact decimal or rational arithmetic, except the binary64 evaluation of H10.
- Examples: 9.96 -> 10.0; 999.5 -> 1000; 1234.5 -> 1230; 0.125 -> 0.12.
