# VDO precise levelling recomputation handbook (revision 7)

This handbook governs the recomputation of a double-run precise levelling campaign of the Vellmar Delta
Geodetic Office: field book shards are settled into setups, setups are reduced to run height differences,
runs are paired into section values, the section values of every connected network component are adjusted
by exact weighted least squares with iterative data snooping, and the adjusted heights are compared with
an earlier epoch to classify subsidence rates. Rules are numbered H1 to H22. Where a rule names a table,
the table is in the governance memo (the PDF file); where it names a sheet, the sheet is in the rod
workbook (the XLSX file).

## H1 Authority

Order of authority, highest first:

1. this handbook;
2. memo tables whose title ends in [IN FORCE], as amended by the errata at the end of the memo;
3. the campaign profile `campaign_profile.yml` with the overlay `profile_overlay.yaml` layered on it (H4);
4. the registers listed in H2 and the workbook sheets the profile names;
5. the quick reference card, for the mean earth radius only;
6. OPERATIONAL NOTICE entries of the field bulletin whose status is IN FORCE, for met station
   substitutions only (H11).

Not authoritative for any figure: the saved adjustment run pack, the published heights and rates, the
network dashboard, the control height cache, memo tables marked [WITHDRAWN] or [SUPERSEDED], workbook sheets
other than the one the profile names, the scale values of the legacy rod register, PROPOSED or CANCELLED
bulletin notices, the refraction coefficient and tables printed on the quick reference card, shards that the
catalog does not list as ACTIVE for the campaign, and the `dir` notes written in some shards.

## H2 Registers

Registers are recognised by their content, not by their file names:

- ingest catalog: JSON whose top-level key `catalog` names it, with an `entries` list;
- run register: CSV with header `run_id,campaign,start_bm,end_bm,booked,level,pair,observer,setups,status,note`;
- run amendments: NDJSON objects carrying `amend_no`, `campaign`, `run`, `field` and `value`;
- section register: TSV with header starting `section_id	from_mark	to_mark	line_id`;
- line register: JSON with `"register": "levelling lines"` and a `lines` list with `class_history`;
- benchmark master: CSV with header `mark,block,description,established,status,easting,northing`;
- benchmark alias register: SQLite table `bm_alias`;
- instrument test register: SQLite tables `instrument_alias` and `two_peg`;
- disturbance journal: XML whose root element is `journal`;
- rulings addendum: XML whose root element is `addendum`;
- epoch register: SQLite tables `epochs` and `heights`;
- met station register: PSV with header `station_id|tokens|name|log_file|unit|status`;
- observer roster: NDJSON objects carrying `observer`, `level`, `valid_from`, `valid_to`;
- loop register: YAML with a top-level `loops` list;
- legacy rod register: YAML with a top-level `rods` list of `serial` and `type`.

## H3 Catalog and shards

Only catalog entries whose `campaign` equals the profile `campaign_id` and whose `status` is `ACTIVE` are
read. Each entry gives the file name and its layout id; `feed_layouts.md` defines every layout. The order
of those entries in the `entries` list is the catalog precedence order (first is highest). A file that is
not such an entry is not read, whatever it contains.

## H4 Profile layering

The profile gives `campaign_id`, `reference_date`, `epoch_reference`, `rod_certificate_sheet`,
`fallback_temp_c`, `met_max_gap_min`, the control point list, the rod pairs and the met station of every
line. An overlay entry applies when its `campaign` equals `campaign_id` exactly and its `effective` date is
on or before `reference_date`; applying entries in file order, each sets its `key` to its `value`, so a
later applying entry wins over an earlier one and every applying entry wins over the profile.

## H5 Setup settlement

A setup is identified by (run id, setup number). Among all records of a setup in the read shards, the
records with the highest revision number compete. When every competing record has the same decoded content
(instant, back and fore reading in metres, back and fore distance, rod temperature or its absence, back and
fore rod serial) and the same void state, the first in catalog precedence is kept and each other one is a
duplicate. Otherwise the record from the shard earliest in catalog precedence wins and each competing
record that differs from it in content or void state is a lost conflict, while one that matches it is a
duplicate. A winning record that is void drops the setup; a void record at a lower revision has no effect.
Every record at a lower revision than the highest is superseded.

## H6 Decoding

Run ids are written `R-26-dddd`, `R26dddd` or `26/dddd` and all denote `R-26-dddd`. Readings are in the
unit the layout states. A reading taken on a rod whose type has HALF graduation (Table A-1) is recorded in
half-centimetre units: its value in metres is the decoded value divided by 2. Distances given in US survey
feet are converted with 1 ft = 1200/3937 m and rounded half to even to 0.1 m; other distances are exact in
the unit stated. A rod temperature in degrees Fahrenheit is converted with C = (F - 32) x 5/9 and rounded
half to even to 0.1 degC. An empty temperature field, `~`, `null` or a missing attribute means the setup has
no field temperature. Times are UTC, UTC with an offset, epoch seconds or local wall clock as the layout
states; a local wall clock time is converted with the transitions of `site_clock.yaml`.

## H7 Rods and certificates

The serial of a rod token is the run of digits in the token with leading zeros removed. When that serial
appears in the `former_serial` column of the workbook `Rods` sheet it is replaced by the `serial` of that
row. The rod type is the `type` of the serial in the `Rods` sheet; a serial absent from that sheet takes its
type from the legacy rod register. A layout that names a rod pair instead of rods takes the pair from the
run register after amendments; the profile `rod_pairs` entry lists rod A then rod B (as rod tokens); at odd
setup numbers rod A is the back rod and rod B the fore rod, at even setup numbers the other way round.

The certificate of a rod on a run date d is taken from the workbook sheet named by the effective
`rod_certificate_sheet`: among the rows of that rod with valid_from <= d <= valid_to, the one with the
greatest valid_from. A row whose only cell reads `continued` is not data.

## H8 Run register

Only rows whose `campaign` equals `campaign_id` are runs of the campaign. Amendments of the campaign are
applied to existing runs in ascending `amend_no`, whatever their order in the file; each sets the named
field (`status`, `setups`, `level` or `observer`) and a later amendment of the same field wins. The run
date is the site-local calendar date of the earliest instant among the run's kept setups. The `booked`
column is the office booking date and is not the run date.

## H9 Run validity

Each run receives the first status of this list that applies:

1. `VOID`: the status after amendments is VOID;
2. `NO_SETUPS`: no kept setup;
3. `UNRESOLVED_BM`: the start or end token does not resolve at the run date (H13);
4. `UNKNOWN_SECTION`: the resolved (start, end) pair is neither the (from, to) nor the (to, from) pair of a
   section; a run from the from-mark to the to-mark is forward (F), the other way round backward (B);
5. `SEQUENCE_GAP`: the kept setup numbers are not exactly 1 to `setups`;
6. `UNCERTIFIED_OBSERVER`: no roster record of the observer (codes compare case-insensitively) has
   valid_from <= run date <= valid_to;
7. `NO_TEST`: the instrument has no effective two-peg test (H10);
8. `INVALID_COLLIMATION`: the absolute collimation error of the effective test exceeds the Table I-1 limit;
   the `result` column of the test register is not used for this decision;
9. `NO_CERTIFICATE`: a back or fore rod of any kept setup has no certificate on the run date;
10. `RULED_OUT`: a ruling in force rejects the run (H15);
11. `VALID` otherwise.

## H10 Two-peg tests

An instrument token is upper-cased with runs of whitespace collapsed to one space and looked up in
`instrument_alias`. `tested_utc` is a UTC time written YYYY-MM-DD HH:MM:SS. The effective test of a run is the `two_peg` row of that instrument with the greatest
`tested_utc` that is not later than the instant of the run's earliest kept setup, ignoring rows whose result
is RETEST; equal instants go to the greater `test_id`. The collimation error c is in mm per 100 m of sight
length and is positive when the line of sight points upward, so every reading is too high by c x D / 100 mm.

## H11 Rod temperature

A setup with a field temperature uses it (source FIELD). Otherwise the met station of the run's section line is
used: profile `line_stations` lists for each line its stations, each with the site date `from` which it
applies, and the setup takes the entry with the latest `from` on or before the site-local date of its instant;
the station token resolves through the station register by `station_id` or any of its `tokens`,
case-insensitively. That station is replaced when an IN FORCE OPERATIONAL NOTICE of this campaign takes that station
offline on the site-local date of the setup instant: the notice's substitute station is then used instead.
The station's log file and unit come from the station register. Every log record is converted to degC
exactly (degF with C = (F - 32) x 5/9, tenths of degC divided by 10). The temperature at the setup instant
is the linear interpolation in time between the last record at or before the instant and the first record
at or after it (a record at the instant itself is used as it is), rounded half to even to 0.1 degC (source
MET). When either record is missing, or the two are more than `met_max_gap_min` minutes apart, the setup
uses `fallback_temp_c` (source FALLBACK).

## H12 Setup reduction

Each reading r (metres) with sight distance D (metres), taken on a rod with certificate scale s (ppm) and
calibration temperature T0, rod type expansion alpha (ppm per degC, Table A-1), rod temperature T (H11), the
run's collimation error c (H10), the refraction coefficient k (Table I-1) and the mean earth radius R (quick
reference card) is reduced to

    r_c = r x (1 + s x 1e-6 + alpha x 1e-6 x (T - T0)) - c x D / 100000 - (1 - k) x D x D / (2 x R)

The scale and the expansion of each reading use that reading's own rod. The setup height difference is the
reduced back reading minus the reduced fore reading, rounded half to even to 0.00001 m; the raw difference is
the decoded back reading minus the decoded fore reading. The run height difference is the sum of its setup
height differences and the run length is the sum of all back and fore distances.

Worked example with c = 1.250, k = 0.13, R = 6371000, T = 24.3 and alpha = 0.80 for both rods: a back reading
1.52340 m at D = 32.4 m on a rod with s = -12.5, T0 = 20.0 reduces to 1.522909522... m; a fore reading 0.87655 m at
D = 29.8 m on a rod with s = 8.1, T0 = 20.0 reduces to 0.876126982... m; the setup height difference is
0.646782541... m, reported 0.64678 m, while the raw difference is 0.64685 m.

## H13 Benchmark tokens

A token is trimmed, upper-cased and stripped of spaces. `VD` followed by up to four digits, with or without
a hyphen, becomes `VD-` and the digits zero-padded to four; up to four bare digits become `VD-` and the
digits zero-padded to four; `MB` followed by up to three digits becomes `MB-` and the digits zero-padded to
three. The result then follows the alias register at the resolution date d: a row applies when its `token`
equals the current value, valid_from <= d and valid_to is empty or later than d (valid_to is exclusive);
when several rows apply, the one with the greatest valid_from wins; the current value becomes the row's
`canonical` and the lookup repeats until no row applies. The token resolves when the final value is a mark
of the benchmark master. Run tokens resolve at the run date, profile control points and loop marks at the
reference date, epoch register marks at the reference date of their epoch.

## H14 Sections

A section's class is the class of its line: the `class_history` entry of the line with the latest `from`
that is not after the reference date. For a section with at least one VALID forward and one VALID backward
run, every (forward, backward) pair is a candidate with discrepancy d = dh_forward + dh_backward (m) and
length K = (forward length + backward length) / 2000 (km). A candidate is accepted when
(1000 x d)^2 <= t^2 x K, where t is the Table T-1 section tolerance of the class. The section takes the
accepted candidate with the smallest |d|; ties go to the candidate whose later run date is latest, then to
the smaller forward run id, then to the smaller backward run id. Its value is (dh_forward - dh_backward) / 2
rounded half to even to 0.00001 m, from the from-mark to the to-mark. Status, first that applies:
`RULED_OUT` (a ruling in force rejects the section), `INCOMPLETE` (a direction has no VALID run),
`REJECTED_TOLERANCE` (no accepted candidate), `ACCEPTED`.

## H15 Rulings

Table J-1 rulings whose effective date is on or before the reference date are in force unless an addendum
ruling of this campaign with action CANCEL, issued on or before the reference date, targets their ruling id.
Addendum rulings of this campaign with action REJECT_RUN or REJECT_SECTION issued on or before the
reference date are in force. A ruling in force rejects its target run or section outright.

## H16 Control

Disturbance journal entries are replayed in ascending entry id. An ERRATUM entry cancels the entry whose id
its `refers` attribute names, whatever the erratum's own date, and does nothing else. For control status,
entries dated after the reference date are ignored; DISTURBED makes a mark disturbed, REVERIFIED makes it
sound again and INSPECTED changes nothing. Each profile control point, resolved at the reference date,
receives the first status that applies: `UNRESOLVED`, `NOT_IN_TABLE` (no Table C-2 height), 
`DEMOTED_DISTURBED` (disturbed at the reference date), `FIXED`. A FIXED mark is held at its Table C-2
height as amended by the errata; every other mark is an unknown.

## H17 Adjustment

Accepted sections form a graph on their marks; each connected component is adjusted on its own and is named
by its lowest mark id. A component without a FIXED mark is UNCONSTRAINED and is not adjusted. Heights and
section values are taken in millimetres; each section is an observation H_to - H_from with weight
p = 1 / (sigma^2 x K), sigma being the Table K-1 sigma of the section class, so the a priori unit variance is
1. The least squares solution is computed exactly in rational arithmetic. The residual of an observation is
v = adjusted H_to - adjusted H_from - section value (mm). Its cofactor is qvv = 1/p - a Qxx a', where a is
its design row and Qxx the inverse normal matrix. Observations with qvv = 0 are untestable; every other
observation has w = v / sqrt(qvv) and is tested against the Table K-1 critical value c_w by comparing the
squares: w^2 > c_w^2. The a priori unit variance is used; s0 never enters the test.

Data snooping repeats the adjustment: after each adjustment, if no tested observation has w^2 > c_w^2 the
loop stops (STOP_CLEAN); else if the component has already lost the Table K-1 maximum number of removals it
stops (STOP_BUDGET); else if removing one observation would leave the redundancy below the Table K-1
minimum it stops (STOP_REDUNDANCY); else the tested observation with the largest w^2 (ties: smaller section
id) is removed and the component is adjusted again (REMOVE). The final adjustment is the last one made.
Component status: CLEAN (stopped clean without a removal), SNOOPED (stopped clean after removals),
STOP_BUDGET, STOP_REDUNDANCY, UNCONSTRAINED.

## H18 Statistics

For the final adjustment of a component: vtpv = sum of p x v^2, redundancy r = observations - unknowns,
s0 = sqrt(vtpv / r) when r > 0. The global test passes when lower <= vtpv <= upper with the Table X-2 bounds
for r degrees of freedom; r = 0 gives NO_REDUNDANCY. The standard deviation of an adjusted height is
sqrt(qxx) mm with the a priori unit variance; FIXED marks have 0.

## H19 Loops

Each loop of the loop register lists its marks in traversal order and closes from the last mark back to the
first; marks resolve at the reference date. Every consecutive pair must be joined by an ACCEPTED section
(H14, whether or not snooping later removed it and whether or not its component is constrained), else the
loop is INCOMPLETE. The misclosure is the sum of the section values along the traversal (a section traversed
from its to-mark to its from-mark counts negative) in mm, K is the sum of the section lengths K, and the loop
passes when misclosure^2 <= t^2 x K with t the Table T-1 loop tolerance of the loop class.

## H20 Rates

The prior epoch is the epoch register epoch named by `epoch_reference`; its heights rows are the marks of
that epoch. The interval in years is the number of days from that epoch's reference date to the profile
reference date divided by 365.25. For every mark with an adjusted height (FIXED or ADJUSTED), using the
reported height and the reported standard deviation of this campaign (H22) and the prior height and sigma:
rate = (height - prior height) x 1000 / years (mm per year), sigma_rate = sqrt(sigma^2 + prior sigma^2) /
years. A rate is significant when rate^2 > k^2 x sigma_rate^2 with k the Table R-1 significance factor.
Class, first that applies: CONTROL (FIXED mark), DISTURBED (a journal DISTURBED entry that is not cancelled,
dated after the prior epoch's reference date and on or before the profile reference date; a later
REVERIFIED does not clear it), NEW (no prior height), ALERT (significant and rate <= the Table R-1 alert
rate), SUBSIDING (significant and negative), UPLIFT (significant and positive), STABLE.

## H21 Comparisons

The comparison reports set the recomputed figures against the published heights, the published rates, the
network dashboard and the control height cache. Their shapes are fixed by the output contract.

## H22 Rounding and reporting

Every rounding is half to even. Values are rounded only at these stages: decoded feet distances (0.1 m),
rod temperatures (0.1 degC), setup height differences (0.00001 m) and section values (0.00001 m). All other
quantities are carried exactly and rounded only when reported, to the decimals of the output contract.
Rates and their classes use the reported heights and the reported standard deviations.
