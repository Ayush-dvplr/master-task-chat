# Feed layouts

Every injection export carries the same eleven fields under different names. Status tokens map to
live or void; integration tokens map to AUTO or MANUAL.

| layout | container | injection | run | seq | kind | ref | dilution | analyte area | IS area | integration | revision | live / void |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| i_csv | comma CSV | injection_id | run_ref | seq | sample_type | sample_ref | dilution | analyte_area | is_area | integration | revision | state OK / VOID |
| i_tsv | tab TSV | INJ | RUN | SEQ | TYPE | REF | DIL | A_AREA | IS_AREA | INTEG (A, M) | REV | ST 0 / 9 |
| i_psv | pipe PSV | inj | run | seq | kind | ref | df | area_counts | is_area_kcounts (kilocounts) | int | rev | status live / dead |
| i_jsonl | JSON lines | injectionId | runRef | seqNo | sampleType | sampleRef | dilutionFactor (1:N) | analyteArea | isArea | integration | revision | status valid / void |
| i_ndjson | JSON lines | id | run | order | sample.type | sample.ref | sample.df | areas.analyte | areas.istd | proc.mode (A, M) | proc.rev | void false / true |
| i_xml | XML `inj` elements | @id | @run | @seq | @type | @ref | @df | area[@kind=analyte] | area[@kind=istd] | @integ | @rev | @status valid / voided |
| i_sqlite | SQLite table injection | inj_id | run_token | seq | stype | sref | dil | a_area | is_area | integ | rev | voided 0 / 1 |
| i_db | SQLite tables inj + area | inj.id | inj.run | inj.seq | inj.stype | inj.sref | inj.dil | area.value channel A | area.value channel IS | inj.integ | inj.rev | inj.flag V / X |
| i_json | JSON export.columns + export.rows | inj | run | seq | type | ref | df | area_analyte | area_istd | integration | rev | state ACTIVE / RETRACTED |
| i_yaml | YAML list under injections | inj | run | seq | type | ref | df (xN) | area_a | area_is | integ | rev | st L / V |
| i_yml | YAML list under records | injection | batch | position | kind | label | dilution (xN) | analyte_counts | istd_kcounts (kilocounts) | mode | revision | state ok / cxl |
| i_txt | `KEY=value; ...` lines, `#` comments | INJ | RUN | SEQ | TYPE | REF | DF (1:N) | AREA | ISAREA | MODE | REV | ST A / X |
| i_csvsemi | semicolon CSV | Injection | Batch | Pos | Type | Sample | Dilution | Area (kcounts), decimal comma | IS Area (kcounts), decimal comma | Integration | Rev | Valid Y / N |
| i_tsv2 | tab TSV | injection | run | seq | type | ref | df | analyte_area | is_area | integration | revision | status ok / void |
| i_jsonl2 | JSON lines | inj | run | seq | type | ref | df | a | is | mode | rev | st ok / void |
| i_psv2 | pipe PSV | inj | run | pos | t | ref | df | area | is_area | integ | rev | keep KEEP / DROP |

In `i_db` the areas live in table `area`, keyed by (inj_id, rev), one row per channel.

## Kind tokens

| layout | STD | QC | DQC | UNK | BLANK | ZERO |
|---|---|---|---|---|---|---|
| i_csv, i_xml, i_yaml, i_txt, i_csvsemi, i_tsv2, i_jsonl2 | STD | QC | DQC | UNK | BLANK | ZERO |
| i_tsv, i_json | Standard | QC | DilQC | Unknown | Blank | Zero |
| i_psv, i_yml | std | qc | dqc | unk | blank | zero |
| i_jsonl | STD | QC | DQC | SAMPLE | BLANK | ZERO |
| i_ndjson | cal | qc | dilqc | study | blank | zero |
| i_sqlite, i_psv2 | S | Q | D | U | B | Z |
| i_db | STD | QC | DQC | UNK | BLK | ZERO |

## Reference tokens

Standards: `CSk`, `STD-k`, `Lk`, `Cal k` (k = 1 ... 8). QCs: `LQC`, `QC-L`, `low`, `QCL` (likewise MQC as
`QC-M`, `mid`, `QCM`; HQC as `QC-H`, `high`, `QCH`; DQC as `QC-D`, `dil`, `QCD`). Unknowns carry the tube
barcode.

## Other inputs

| file | content |
|---|---|
| ingest_catalog_be.json | shards: file, layout, stream, active, rows |
| entity_alias_register.sqlite | run_alias(token, run_id, source); subject_alias(token, subject_id, study), where subject_id may itself be another token (H4) |
| integration_audit_trail.db | audit_entry(entry_id, injection_ref, revision, action, reason_code, approver, status, ts) |
| std_exclusion_requests.jsonl | request_id, run (token), injection, code, status, requested_at |
| reassay_request_log.csv | tube, analyte, run (token), reason, status, requested_on, requested_by |
| tube_manifest_main.csv | tube_id, subject (token), period, nominal_h (`PRE` = 0), status, tube_type, registered_at |
| tube_manifest_addendum.yaml | tubes: tube, subject, period, nominal_h (`UNS` = unscheduled), status, note |
| tube_relabel_journal.xml | relabel @old @new @status (ACTIVE / CANCELLED) @at; rows with a study attribute belong to that study |
| dose_admin_p1.csv | subject, period, event, local_time (site wall clock), dose_mg, kit, comment |
| dose_admin_p2.xml | event @subject @type @at (ISO with offset) @kit @mg |
| draw_times_g1.tsv | tube, subject, period, nominal_h, drawn_local (site wall clock), phlebotomist, comment |
| draw_times_g2.jsonl | tube, subj, per, nom, drawn_at (ISO with offset or null), by |
| draw_time_corrections.ndjson | seq, tube, field, value (site wall clock for drawn_local), status, entered, action (SET or REVERSE; absent means SET), reverses (seq of the cancelled entry, REVERSE only) |
| ae_listing.db | ae_events(ae_id, study, subject, period, pt, verbatim, onset_local (site wall clock), severity, outcome) |
| subject_disposition.psv | subject, event, period, event_date, note |
| site_calendar.yml | base_offset, transitions (at_utc, offset_after), informative daily table |
| analysis_profile_be.yml | profile knobs (handbook H1) |
| bioanalytical_workbook_v3.xlsx | RunPlan, CertNominal_*, QCLots, Randomization; headers are the first row whose first cell is `run_id`, `lot` or `subject`; sheet names live in xl/workbook.xml and reach their part through xl/_rels/workbook.xml.rels; serial dates follow the workbook date system (H4) |
| ba_stat_governance_memo.pdf | each page is one Flate content stream; every cell is a separate text object positioned with Tm, in no particular order; a row is the cells sharing a y position, left to right by x |
| ba_stat_governance_memo.pdf (tables) | tables P, M, C, E, T, R, S; a table continues on later pages under `Table X-n (continued)` with its header repeated |
