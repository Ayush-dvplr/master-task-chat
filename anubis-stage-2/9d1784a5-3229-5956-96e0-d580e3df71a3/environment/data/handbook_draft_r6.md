# Thermal heat-load budget handbook (revision 10, DRAFT for comment)

Draft changes under review; not approved by the qualification board.


## H1 Authority

1. The sources that govern the budget are: the memo tables whose title ends in (IN FORCE); the workbook sheets
   whose names the campaign profile gives under conductivity_sheet, calibration_sheet and capacity_sheet; the
   campaign profile; the site overlay under the condition of H13; the alias register and channel map; the
   catalogued shards and link files; the run log, harness ledger, intercept register, lot certificates, ruling
   addendum, cooler service log, sensor map, sensor inventory and site calendar; this handbook; feed_layouts.md and
   output_contract.md.
2. A memo table whose title ends in (WITHDRAWN) is never applied, even when it is printed first or carries the same
   header. A workbook sheet that the profile does not name is never applied, whether it is visible, hidden or
   described as approved in the README sheet.
3. The saved solve pack, the published budget and stage margins, the DAQ dashboard export, the conductivity cache,
   the quick reference card, the operations bulletin, the draft handbook, the legacy materials file and any overlay
   whose base_revision differs from the profile revision are lower-authority sources. They are read only for the
   comparisons of H24 and H25.
4. The generic calibration curves are applied only under H9.3.

## H2 Catalog

1. ingest_catalog_*.json lists the input files by kind with an order number. Only entries with status ACTIVE are
   read; an entry with status RETIRED is skipped even when its file exists.
2. A file that looks like a shard but is not listed in the catalog is not an input.
3. Catalog order (ascending order number) is the tie-break order of H5.2.
4. field_maps documents, per layout, which source field carries which canonical field. value_maps documents the
   void markers and missing-value sentinels of each layout.

## H3 Runs

1. A run token is canonicalised by taking its trailing integer n and writing KTC-Rnn with n zero-padded to two
   digits. Accepted spellings: KTC-R07, R07, r7, 26B-07, KTC-26B/07. A token that names another campaign
   (KTC-26A/..., KTC-25C/...) does not belong to this campaign and is ignored.
2. A run is in scope when the campaign profile lists it under runs. Records of runs that are not in scope are
   ignored and are not reported anywhere except the out_of_scope_readings counter of the dedup report.
3. In the run log the latest rev of each (run, event) pair is the effective entry; NOTE entries carry no
   information for the budget. The plateau window of a run is [PLATEAU_START, PLATEAU_END): a reading at exactly
   PLATEAU_START is inside, a reading at exactly PLATEAU_END is outside.
4. The effective CONFIG entry gives the shield configuration of the run.
5. A run whose effective ABORT entry has value ACTIVE is aborted. An ABORT entry later re-entered with value
   WITHDRAWN at a higher rev cancels the abort. An aborted run gets no readings, temperatures, links, loads or
   margins; its run verdict is ABORTED. output_contract.md names the comparison and summary reports that still
   carry a row for it.

## H4 Time

1. Run log times and layouts marked local are site wall time. A wall time maps to the earliest UTC instant whose
   site offset turns it into that wall time; a wall time inside a skipped hour uses the offset in effect before the
   jump. Site offsets come from site_calendar.yml: base_offset applies before the first transition, and each
   transition switches to offset_after at its at_utc instant.
2. Local-time reading layouts carry an isdst column. isdst = 1 means the larger of the site's offsets was in effect,
   isdst = 0 the smaller; the instant is the wall time minus that offset.
3. Epoch values are seconds or milliseconds since 1970-01-01T00:00:00Z as the layout says. Instants are compared at
   whole seconds: milliseconds are dropped (truncated toward the past), never rounded.
4. A calendar date used as an effective date (link catalog effective_from, calibration valid_from, service log
   date) takes effect at 00:00:00 UTC of that date. The date of a run is the UTC date of its plateau start.
5. Workbook dates are serial day numbers. When xl/workbook.xml carries workbookPr date1904="1" (or true), serial n
   is 1904-01-01 plus n days; otherwise serial n is 1899-12-30 plus n days.

   Example: with date1904 set, serial 44000 is 2024-06-22; without it, 44000 is 2020-06-19.

## H5 Reading identity, revisions and voids

1. A reading's key is (final serial, instant at whole seconds). Tokens are resolved first (H6); a record whose
   token cannot be resolved is counted as unresolved and takes no part in deduplication.
2. Among the copies of one key, the copy with the highest rev wins. Equal rev: the copy in the shard with the later
   catalog order wins; within one shard, the later record in file order wins.
3. Voids are decided after the winner is chosen: when the winning copy is void, the key is removed. A void copy that
   loses to a higher-rev copy removes nothing.

   Example: copies of one key are (rev 1, void) in shard 2 and (rev 2, not void) in shard 1. The rev 2 copy wins
   and the reading stays. Removing every key that has any void copy first would wrongly drop it.

## H6 Sensor tokens

1. A serial token is canonicalised by upper-casing it, removing spaces, hyphens and underscores, and writing the
   leading letters, a hyphen and the digits: ls2210, LS 2210, LS_2210 and ls-2210 all become LS-2210.
2. A channel token names a DAQ unit and channel: D1C07, DAQ1-07, 1/07 and ch07@daq1 all mean D1C07. A channel is
   resolved with channel_map_history.db: the row whose [valid_from_utc, valid_to_utc) contains the reading instant
   (an empty valid_to_utc is open-ended) gives the serial. A channel with no such row is UNMAPPED_CHANNEL.
3. The serial (from either route) is then walked through sensor_relabel in the alias register: while a row has
   old_serial equal to the current serial, move to its new_serial. The walk ignores effective_utc and always runs
   to the end of the chain. The end of the chain is the final serial used by every other rule.

   Example: a reading carries QX-1111; the register holds QX-1111 -> RV-2222 and RV-2222 -> TM-3333. The final
   serial is TM-3333, even for readings taken before either relabel. One lookup would stop at RV-2222.
4. A final serial that is not listed in sensor_inventory.json is UNKNOWN_SENSOR.

## H7 Stage assignment

1. sensor_map_*.yaml gives, per final serial, a history of stage assignments with from_utc instants. The stage of a
   sensor for a run is the assignment in effect at the run's plateau start (latest from_utc at or before it).
2. Stage tokens are resolved through node_alias in the alias register (case-insensitive, trimmed). ST300, ST50 and
   ST4 are the measured stages. A sensor whose stage for the run is anything else takes no part in that run.

## H8 Units

1. Resistive raw values are in ohm; kohm is multiplied by 1000. Diode raw values are in volt; mV is divided by
   1000. Layouts that carry micro-units hold micro-ohm or micro-volt integers. All conversions are exact decimal
   arithmetic; never use binary floating point for a raw value.

## H9 Calibration

1. Calibration points come from the workbook sheet named by calibration_sheet: rows (serial, version, valid_from,
   point, raw, unit, T_K). A version applies from 00:00 UTC of its valid_from date; a reading uses the applicable
   version with the latest valid_from.
2. The family in sensor_inventory.json decides the interpolation space, never the serial prefix:
   PRT interpolates temperature linearly in resistance R; NTC interpolates temperature linearly in resistance R;
   DIODE interpolates temperature linearly in voltage V. The temperature is found between the two neighbouring
   points of the table in that space. A raw value outside the closed range spanned by the table is OUT_OF_RANGE.
3. A final serial with no applicable version uses the generic curve named by generic_curve in the inventory, from
   calibration_generic_curves.tsv, only when its cal_policy is GENERIC_OK. Otherwise its readings are
   NO_CALIBRATION.
4. The calibrated temperature is rounded to a whole mK (H22).

   Example (NTC): points (R 100 ohm, 10.000 K) and (R 50 ohm, 20.000 K). A reading of 80 ohm has conductance
   0.0125; the points have 0.01 and 0.02, so T = 10 + 10 * (0.0125 - 0.01) / 0.01 = 12.500 K = 12500 mK.
   Interpolating in resistance would give 14.000 K.

## H10 Reading screens

1. Each deduplicated reading of an in-scope, not aborted run is screened in this order and stops at the first
   reason that applies: INVALID_VALUE (the layout's missing-value sentinel or an empty value), OUT_OF_WINDOW,
   MAINTENANCE, EXCLUDED_SENSOR, NO_CALIBRATION, OUT_OF_RANGE. Readings that pass all of them are window readings.
   Unresolved records count as UNMAPPED_CHANNEL or UNKNOWN_SENSOR and are reported under their run.
2. MAINTENANCE: the reading instant lies in [start_utc, end_utc) of a maintenance block of the site calendar whose
   scope is ALL or names the sensor's stage for the run. A scope other than ALL is a stage token and resolves
   through node_alias exactly as in H7.2 (shell, for example, names ST300).
3. Rulings come from memo Table R-1. The ruling addendum is applied to them in ascending seq order: an ISSUED
   RESCIND sets the ruling to RESCINDED, an ISSUED REINSTATE sets it to IN FORCE; DRAFT entries are ignored. Only
   rulings IN FORCE after the addendum apply. EXCLUDE_SENSOR removes the sensor from that run (EXCLUDED_SENSOR).
   OFFSET_SENSOR adds its value in mK to every calibrated reading of that sensor in that run, before H11.
   EXCLUDE_LINK takes the link out of that run (H14.4).
4. Readings of runs that are aborted take no part and are not reported.

## H11 Sensor means

1. For each (run, final serial), take the window readings. Compute their median exactly (an even count takes the
   mean of the two middle values). A reading whose distance from the median is greater than spike_mK from the window mean is a SPIKE
   and is dropped; a distance equal to spike_mK is kept.
2. When fewer than min_readings readings remain, the sensor has no mean for the run (status SPARSE, or NO_READINGS
   when none remain). Otherwise the sensor mean is the mean of the remaining readings, rounded to a whole mK.

## H12 Stage temperatures

1. For each (run, measured stage), take the sensors assigned to the stage for the run that have a mean. Compute
   the median of their means exactly; a sensor whose mean is farther than outlier_mK from that median is dropped
   as an outlier (equal is kept). The stage temperature is the mean of the remaining sensor means, rounded to a
   whole mK. A stage with no sensor mean is NO_SENSORS.

## H13 Effective settings

1. The profile gives spike_mK, outlier_mK, min_readings and reserve_pct globally; a per-run entry in the profile's
   runs list overrides a global value for that run.
2. A site overlay applies only when its base_revision equals the profile's profile_revision. It then overrides, per
   run, only the keys it lists under overridable_keys; any other key in it is ignored. An overlay with another
   base_revision is ignored entirely.

## H14 Links

1. Link tokens: TL-031, tl31, TL 031 and TL031 all mean TL-031. Each token is then walked through link_alias in the
   alias register to the end of the chain (old_id -> new_id), like H6.3.
2. The revision of a link that a run uses is the catalog row of the final link id with the latest effective_from
   on or before the run's date (H4.4); equal effective_from takes the higher rev. When that revision has status
   VOID the link is scrapped for the run (status NO_GEOMETRY).
3. Installs: the latest rev of each (run, final link id) is effective; state INSTALLED puts the link in the run,
   REMOVED takes it out. Hot and cold node tokens resolve through node_alias; intercept ids stand for themselves.
4. A link taken out by an EXCLUDE_LINK ruling has status EXCLUDED; it is not solved and carries no load.

## H15 Amendments

1. Amendment entries target (final link id, rev, field). Action and status words are case-insensitive. Entries are
   settled from the highest seq down: an entry is in effect when its status is POSTED and no in-effect REVERSE
   names it; a REVERSE in effect cancels the entry its reverses field names.
2. A field's value is the value of its highest-seq in-effect SET entry; with none, the link file value stands.
   Fields: segN.length_mm, segN.area (an area spec), segN.material, jointP.bolts, jointP.torque, jointP.indium.

   Example: SET 101 = 40.0, SET 105 = 42.0, REVERSE 107 of 105, REVERSE 110 of 107. 110 is in effect and cancels
   107, so 105 is not cancelled: the value is 42.0. Skipping REVERSE entries also gives 42.0 here, but drops 40.0
   wrongly when 107 alone exists.

## H16 Geometry

1. Lengths are in mm; cm multiplies by 10 and in by 25.4 exactly.
2. Area specs: A:12.50mm2 is 12.50 mm2; A:0.1250cm2 is 12.50 mm2; R:6.0x2.5mm is a rectangle of 15.00 mm2;
   W:24x32AWG is 24 conductors of gauge 32, each with the area of memo Table W-1.
3. Materials resolve through material_alias (case-insensitive, trimmed, ACTIVE rows only, followed to the end of the
   chain) to a material code of the conductivity sheet.
4. A lot scale multiplies the conductivity of a segment when the lot certificate has status CERTIFIED and the
   segment's material is listed in the lot_scale_materials constant of the solver contract table (IN FORCE).
   Otherwise the scale is 1.
5. The geometry factor of a segment is G = area_mm2 / length_mm (in mm), kept exact.

## H17 Conductivity

1. The conductivity sheet holds rows (material, T_K, k, unit). W/m-K is used as is; mW/cm-K is multiplied by 0.1.
2. k(T) is linear between neighbouring tabulated temperatures and constant beyond the first and last points.
3. The conductivity integral is theta(T) = integral of k from 0 to T, with T in mK, so a segment carries
   q_uW = scale * G * (theta(T_a) - theta(T_b)) between end temperatures T_a > T_b. theta is piecewise quadratic and
   is evaluated exactly.

   Example: k = 2 W/m-K at 10 K and 4 W/m-K at 20 K; from 10000 mK to 15000 mK the integral is
   5000 * (2 + 3) / 2 = 12500, so a segment with G = 0.4 mm carries 5000 uW.

## H18 Joint conductance

1. The band of a link is the band of its cold node: ST50 gives W, ST4 gives C, an intercept gives its own band from
   the intercept register.
2. h_eff = h_base(class, band) from the joint table (IN FORCE) * bolts * low_torque_factor when torque is LOW *
   indium_factor when indium is set and the class starts with BOLT_. h_eff is then rounded to the h increment of the
   solver contract table (IN FORCE), half-even.

## H19 Link march and heat flow

1. The elements of a link, hot end first, are: joint 0, segment 1, joint 1, segment 2, ..., segment n, joint n.
   Joint positions that are not listed are skipped.
2. The march for a trial heat flow q (whole uW) starts at the hot node temperature. A segment moves T to the
   temperature T' with theta(T') = theta(T) - q / (scale * G), rounded to a whole mK. A joint moves T to
   T - q / h_eff, where q / h_eff is in mK and is rounded to a whole mK before it is subtracted. A march whose
   theta target falls below theta(0), or whose temperature falls below 0, has failed.
3. The heat flow of the link is the largest whole q for which the march does not fail and ends at or above the
   cold node temperature. The junction temperatures are the march temperatures for that q.
4. A link whose hot node is not warmer than its cold node has q = 0 and status NO_GRADIENT. A link with a node
   that has no temperature is UNSOLVED.

   Example: hot 10000 mK, one segment with G = 0.4 mm and k as in H17, cold 9000 mK. q = 0.4 * (theta(10000) -
   theta(9000)) = 0.4 * 2000 = 800 uW when nothing is rounded. Rounding each element to a whole mK and taking the
   largest q that still ends at or above 9000 mK is the contract, not a solve that rounds once at the end.

## H20 Intercepts

1. An intercept is a floating node. For a trial temperature T (whole mK), f(T) = sum of q of the links whose cold
   node is the intercept + harness dissipation at the intercept - sum of q of the links whose hot node is the
   intercept, with every q from H19 at that T.
2. T_lo is the warmest cold-side node temperature and T_hi the coldest hot-side node temperature. The intercept
   temperature is the largest whole T in [T_lo, T_hi] with f(T) >= 0 (status BALANCED). When f(T_hi) >= 0 the
   intercept sits at T_hi (status CEILING). When f(T_lo) < 0 it sits at T_lo (status FLOOR).
3. The nominal_K of the intercept register is a design value and is used as the intercept temperature.

## H21 Loads, capacity, margins and verdicts

1. Harness dissipation: the bundle rows of harness_dissipation.psv (latest rev per bundle, voids removed); the node
   of a bundle is the node the intercept register assigns to it for the run; node_hint is stale and not used.
2. The load of ST50 or ST4 is the sum of q of the links whose cold node is the stage, plus the harness dissipation
   at the stage, plus the parasitic load of the run's shield configuration from the parasitic table (IN FORCE).
3. Capacity: the run's cooler (profile) gives a model through its serial (CC-0417 is GM-K15, CC-0522 is PT-K41);
   the capacity sheet gives (model, stage, T_K, capacity_W) points, linear in T and held at the end values outside
   the map (map status OUT_OF_MAP). The derate of the cooler on the run's date is the value of the latest DERATE or
   RESTORE entry of the cooler service log on or before that date (RESTORE means 0). capacity_uW =
   capacity_W * 1000000 * (100 - derate_pct) / 100, rounded once to a whole uW.
4. reserve_uW = capacity_uW * reserve_pct / 100 rounded to a whole uW; margin_uW = capacity_uW - load_uW.
5. Stage verdict: OVER_TEMP when the stage temperature exceeds the limit of Table L-1, else OVERLOAD when the margin
   is negative, else MARGINAL when the margin is below the reserve, else PASS. Equal to the reserve is PASS.
6. Run verdict: INCOMPLETE when any link of the run is UNSOLVED or any measured stage is NO_SENSORS; otherwise the
   most severe stage verdict in the order OVER_TEMP, OVERLOAD, MARGINAL, PASS.

## H22 Rounding

1. Every rounding in this handbook is round half to even, to the stated unit, at the stated step, and the rounded
   value is what the next step consumes: calibrated readings (whole mK), sensor means (whole mK), stage
   temperatures (whole mK), h_eff (h increment), every march element (whole mK), capacity and reserve (whole uW).
   Carrying full precision and rounding once at the end is a different and wrong result.

   Example: 2.5 rounds to 2, 3.5 to 4, -2.5 to -2.

## H23 Reported numbers

1. Decimal outputs are written in plain decimal notation, never with an exponent. The output contract states the
   places of every decimal field.

## H24 Authority audit

1. Every value quoted by a lower-authority source is compared with the governing value: a conductivity at a
   temperature (the governing k(T) rounded half-even to as many decimal places as the quoted text has), a joint
   base conductance, a gauge area, a parasitic load, a solver constant, a stage temperature, or a per-run overlay
   setting. Equal is AGREE, anything else DISAGREE.

## H25 Published comparison

1. The published budget is compared link by link (published q in mW, three places, is exactly 1000 times the uW
   value) and the published stage margins stage by stage, as the output contract lays out.


## Draft constants

| key | value |
|---|---|
| JOINT BOLT_AL/C | 254.6 |
| JOINT BOLT_AL/W | 1809.3 |
| JOINT BOLT_CU/C | 379.5 |
| JOINT BOLT_CU/W | 2322.0 |
| JOINT BOLT_SS/C | 55.4 |
| JOINT BOLT_SS/W | 648.0 |
| JOINT CLAMP_SS/C | 97.25 |
| JOINT CLAMP_SS/W | 880.0 |
| JOINT EPOXY_G10/C | 143.0 |
| JOINT EPOXY_G10/W | 1210.0 |
| JOINT SOLDER_PB/C | 702.0 |
| JOINT SOLDER_PB/W | 3900.0 |
| AWG 22 | 0.3255 |
| AWG 24 | 0.2047 |
| AWG 26 | 0.1288 |
| AWG 28 | 0.0810 |
| AWG 30 | 0.0509 |
| AWG 32 | 0.0320 |
| AWG 34 | 0.0201 |
| AWG 36 | 0.0127 |
| AWG 38 | 0.0080 |
| AWG 40 | 0.0050 |
| PARASITIC SC-A/ST4 | 68333 |
| PARASITIC SC-A/ST50 | 2409091 |
| PARASITIC SC-B/ST4 | 49166 |
| PARASITIC SC-B/ST50 | 1800000 |
| PARASITIC SC-C/ST4 | 87500 |
| PARASITIC SC-C/ST50 | 3109091 |
| PARASITIC SC-D/ST4 | 42777 |
| PARASITIC SC-D/ST50 | 1400000 |
| FACTOR h_increment_mW_per_K | 0.1 |
| FACTOR indium_factor | 1.80 |
| FACTOR low_torque_factor | 0.60 |
