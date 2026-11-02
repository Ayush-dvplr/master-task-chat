# Shard feed layouts

Every shard is a peak export. The catalog names the layout of each file in its REGISTER events; file names carry no meaning.
Each record carries the project, a session token, an instrument token, the autosampler counter, the element, the peak type,
the revision, the void flag, the injection time, the peak area, the amplitude and the raw delta versus the reference gas.

Units: area `Vs` is volt-seconds with 4 decimals; `mVs` is millivolt-seconds (area x 1000) with 1 decimal. Amplitude `mV` is
an integer; `V` is volts with 3 decimals. Delta `permil` has 3 decimals; `milli` is an integer in thousandths of a permil;
`ratio` is 1 + delta / 1000 with 6 decimals. Element tokens: E1 N2/CO2, E2 N/C, E3 15N/13C, E4 28/44 (mass channel),
E5 nitrogen/carbon. Peak tokens (analyte/reference): P1 S/R, P2 SAMPLE/REF, P3 1/0 text, P3i 1/0 integer, P4 analyte/reference,
P5 PK/RG.

## Layout summary

| layout | family | time | area | amplitude | delta | element | peak | void true | void false | decimal comma |
|---|---|---|---|---|---|---|---|---|---|---|
| L01 | csv | local_iso | Vs | mV | permil | E1 | P1 | "V" | "" | no |
| L02 | tsv | epoch_s | mVs | V | permil | E2 | P2 | "VOID" | "OK" | no |
| L03 | psv | local_dmy | Vs | mV | permil | E3 | P3 | "DEAD" | "LIVE" | yes |
| L04 | jsonl_flat | epoch_ms | Vs | mV | milli | E3 | P3i | true | false | no |
| L05 | ndjson_nested | iso_off | Vs | mV | permil | E2 | P2 | "Y" | "N" | no |
| L06 | xml_attr | iso_z | mVs | mV | permil | E1 | P1 | "1" | "0" | no |
| L07 | sqlite_split | local_compact | Vs | mV | milli | E1 | P2 | 1 | 0 | no |
| L08 | sqlite_flat | epoch_s | Vs | V | permil | E2 | P1 | "VOID" | "" | no |
| L09 | yaml_blocks | iso_off | Vs | mV | permil | E1 | P2 | "true" | "false" | no |
| L10 | yml_grouped | local_iso | mVs | mV | permil | E5 | P4 | "void" | "ok" | no |
| L11 | json_columnar | epoch_s | mVs | mV | milli | E2 | P1 | 1 | 0 | no |
| L12 | fixed | local_compact | Vs | mV | permil | E1 | P5 | "X" | "-" | no |
| L13 | md | iso_z | Vs | V | permil | E3 | P2 | "VOID" | "" | no |
| L14 | csv_semi | local_dmy_slash | Vs | mV | permil | E2 | P1 | "V" | "" | yes |
| L15 | tsv_wide | epoch_ms | Vs | mV | permil | per block | none | "1" | "" | no |
| L16 | jsonl_nested | iso_z | Vs | mV | ratio | E1 | P2 | true | false | no |
| L17 | csv_comment | iso_off | mVs | V | permil | E4 | P3 | "1" | "0" | no |
| L18 | psv | epoch_ms | mVs | mV | milli | E4 | P5 | "Y" | "N" | no |
| L19 | xml_child | local_t | Vs | mV | milli | E5 | P4 | "true" | "false" | no |
| L20 | ndjson_flat | basic_z | Vs | V | permil | E1 | P1 | "void" | "ok" | no |
| L21 | sqlite_runlog | iso_off | mVs | mV | permil | E1 | P2 | "VOID" | "" | no |
| L22 | sqlite_eav | epoch_s | Vs | mV | permil | E2 | P1 | "1" | "0" | no |

## Field map

| layout | field | meaning | notes |
|---|---|---|---|
| L01 | proj | project |  |
| L01 | seq | session token |  |
| L01 | inst | instrument token |  |
| L01 | pos | autosampler counter |  |
| L01 | gas | element | E1 |
| L01 | ptype | peak type | P1 |
| L01 | rev | revision |  |
| L01 | void | void flag | "V" means void |
| L01 | t_local | injection time | local wall time YYYY-MM-DD HH:MM:SS (H3) |
| L01 | area_vs | peak area | Vs |
| L01 | amp_mv | amplitude | mV |
| L01 | d_permil | raw delta | permil |
| L02 | Project | project |  |
| L02 | Sequence | session token |  |
| L02 | Line | instrument token |  |
| L02 | Counter | autosampler counter |  |
| L02 | Species | element | E2 |
| L02 | PeakKind | peak type | P2 |
| L02 | Revision | revision |  |
| L02 | Status | void flag | "VOID" means void |
| L02 | EpochS | injection time | UTC epoch seconds |
| L02 | Area_mVs | peak area | mVs |
| L02 | Amp_V | amplitude | V |
| L02 | dRaw | raw delta | permil |
| L03 | projekt | project |  |
| L03 | lauf | session token |  |
| L03 | geraet | instrument token |  |
| L03 | position | autosampler counter |  |
| L03 | isotop | element | E3 |
| L03 | peaktyp | peak type | P3 |
| L03 | revision | revision |  |
| L03 | zustand | void flag | "DEAD" means void |
| L03 | zeit | injection time | local wall time DD.MM.YYYY HH:MM:SS (H3) |
| L03 | flaeche_vs | peak area | Vs, decimal comma |
| L03 | amplitude_mv | amplitude | mV |
| L03 | delta | raw delta | permil, decimal comma |
| L04 | prj | project |  |
| L04 | run | session token |  |
| L04 | ln | instrument token |  |
| L04 | slot | autosampler counter |  |
| L04 | el | element | E3 |
| L04 | pk | peak type | P3i |
| L04 | rv | revision |  |
| L04 | void | void flag | true means void |
| L04 | ts_ms | injection time | UTC epoch milliseconds |
| L04 | a | peak area | Vs |
| L04 | amp | amplitude | mV |
| L04 | dm | raw delta | milli |
| L05 | meta.project | project |  |
| L05 | meta.sequence | session token |  |
| L05 | meta.instrument | instrument token |  |
| L05 | inj.position | autosampler counter |  |
| L05 | peak.gas | element | E2 |
| L05 | peak.type | peak type | P2 |
| L05 | rev | revision |  |
| L05 | void | void flag | "Y" means void |
| L05 | inj.time | injection time | ISO 8601 with the offset in effect |
| L05 | peak.area | peak area | Vs |
| L05 | peak.height_mv | amplitude | mV |
| L05 | peak.delta | raw delta | permil |
| L06 | inj@project | project |  |
| L06 | inj@seq | session token |  |
| L06 | inj@inst | instrument token |  |
| L06 | inj@pos | autosampler counter |  |
| L06 | peak@el | element | E1 |
| L06 | peak@kind | peak type | P1 |
| L06 | peak@rev | revision |  |
| L06 | peak@void | void flag | "1" means void |
| L06 | inj@t | injection time | UTC YYYY-MM-DDTHH:MM:SSZ |
| L06 | peak@area_mvs | peak area | mVs |
| L06 | peak@amp_mv | amplitude | mV |
| L06 | peak@d | raw delta | permil |
| L07 | injections.project | project |  |
| L07 | injections.seq | session token |  |
| L07 | injections.inst | instrument token |  |
| L07 | injections.pos | autosampler counter |  |
| L07 | peaks.el | element | E1 |
| L07 | peaks.kind | peak type | P2 |
| L07 | peaks.rev | revision |  |
| L07 | peaks.voided | void flag | 1 means void |
| L07 | injections.t_local | injection time | local wall time YYYYMMDDHHMMSS (H3) |
| L07 | peaks.area_vs | peak area | Vs |
| L07 | peaks.amp_mv | amplitude | mV |
| L07 | peaks.d_milli | raw delta | milli |
| L08 | project | project |  |
| L08 | sequence | session token |  |
| L08 | instrument | instrument token |  |
| L08 | counter | autosampler counter |  |
| L08 | gas | element | E2 |
| L08 | peaktype | peak type | P1 |
| L08 | revision | revision |  |
| L08 | void_flag | void flag | "VOID" means void |
| L08 | epoch | injection time | UTC epoch seconds |
| L08 | area | peak area | Vs |
| L08 | amplitude | amplitude | V |
| L08 | delta | raw delta | permil |
| L09 | project | project |  |
| L09 | sequence | session token |  |
| L09 | instrument | instrument token |  |
| L09 | position | autosampler counter |  |
| L09 | peaks.gas | element | E1 |
| L09 | peaks.type | peak type | P2 |
| L09 | peaks.revision | revision |  |
| L09 | peaks.void | void flag | "true" means void |
| L09 | time | injection time | ISO 8601 with the offset in effect |
| L09 | peaks.area_vs | peak area | Vs |
| L09 | peaks.amp_mv | amplitude | mV |
| L09 | peaks.delta | raw delta | permil |
| L10 | sequences.project | project |  |
| L10 | sequences.sequence | session token |  |
| L10 | sequences.instrument | instrument token |  |
| L10 | peaks.pos | autosampler counter |  |
| L10 | peaks.species | element | E5 |
| L10 | peaks.kind | peak type | P4 |
| L10 | peaks.rev | revision |  |
| L10 | peaks.state | void flag | "void" means void |
| L10 | peaks.t | injection time | local wall time YYYY-MM-DD HH:MM:SS (H3) |
| L10 | peaks.area_mvs | peak area | mVs |
| L10 | peaks.amp_mv | amplitude | mV |
| L10 | peaks.d | raw delta | permil |
| L11 | project | project |  |
| L11 | sequence | session token |  |
| L11 | instrument | instrument token |  |
| L11 | counter | autosampler counter |  |
| L11 | species | element | E2 |
| L11 | peak | peak type | P1 |
| L11 | revision | revision |  |
| L11 | void | void flag | 1 means void |
| L11 | epoch_s | injection time | UTC epoch seconds |
| L11 | area_mvs | peak area | mVs |
| L11 | amp_mv | amplitude | mV |
| L11 | d_milli | raw delta | milli |
| L12 | PROJECT | project | starts at column 1 |
| L12 | SEQUENCE | session token | starts at column 11 |
| L12 | INST | instrument token | starts at column 27 |
| L12 | POS | autosampler counter | starts at column 36 |
| L12 | GAS | element | E1; starts at column 41 |
| L12 | PT | peak type | P5; starts at column 46 |
| L12 | REV | revision | starts at column 50 |
| L12 | VOID | void flag | "X" means void; starts at column 54 |
| L12 | TIME | injection time | local wall time YYYYMMDDHHMMSS (H3); starts at column 59 |
| L12 | AREA_VS | peak area | Vs; starts at column 75 |
| L12 | AMP_MV | amplitude | mV; starts at column 86 |
| L12 | D_PERMIL | raw delta | permil; starts at column 93 |
| L13 | project | project |  |
| L13 | sequence | session token |  |
| L13 | instrument | instrument token |  |
| L13 | position | autosampler counter |  |
| L13 | isotope | element | E3 |
| L13 | peak | peak type | P2 |
| L13 | rev | revision |  |
| L13 | void | void flag | "VOID" means void |
| L13 | time_utc | injection time | UTC YYYY-MM-DDTHH:MM:SSZ |
| L13 | area_vs | peak area | Vs |
| L13 | amp_v | amplitude | V |
| L13 | delta | raw delta | permil |
| L14 | Projekt | project |  |
| L14 | Sequenz | session token |  |
| L14 | Geraet | instrument token |  |
| L14 | Pos | autosampler counter |  |
| L14 | Element | element | E2 |
| L14 | Typ | peak type | P1 |
| L14 | Rev | revision |  |
| L14 | Void | void flag | "V" means void |
| L14 | Zeit | injection time | local wall time DD/MM/YYYY HH:MM:SS (H3) |
| L14 | Flaeche | peak area | Vs, decimal comma |
| L14 | Amplitude | amplitude | mV |
| L14 | Delta | raw delta | permil, decimal comma |
| L15 | project | project | shared by both blocks |
| L15 | sequence | session token | shared by both blocks |
| L15 | instrument | instrument token | shared by both blocks |
| L15 | counter | autosampler counter | shared by both blocks |
| L15 | epoch_ms | injection time, UTC epoch milliseconds | shared by both blocks |
| L15 | rev_N | revision | element N block |
| L15 | void_N | void flag | element N block |
| L15 | area_N | peak area, Vs | element N block |
| L15 | amp_N | amplitude, mV | element N block |
| L15 | d_N | raw delta, permil | element N block |
| L15 | rev_C | revision | element C block |
| L15 | void_C | void flag | element C block |
| L15 | area_C | peak area, Vs | element C block |
| L15 | amp_C | amplitude, mV | element C block |
| L15 | d_C | raw delta, permil | element C block |
| L16 | project | project |  |
| L16 | sequence | session token |  |
| L16 | instrument | instrument token |  |
| L16 | position | autosampler counter |  |
| L16 | peaks[].gas | element | E1 |
| L16 | peaks[].type | peak type | P2 |
| L16 | peaks[].rev | revision |  |
| L16 | peaks[].void | void flag | true means void |
| L16 | time | injection time | UTC YYYY-MM-DDTHH:MM:SSZ |
| L16 | peaks[].area | peak area | Vs |
| L16 | peaks[].amp | amplitude | mV |
| L16 | peaks[].ratio | raw delta | ratio |
| L17 | project | project |  |
| L17 | sequence | session token |  |
| L17 | instrument | instrument token |  |
| L17 | counter | autosampler counter |  |
| L17 | mass | element | E4 |
| L17 | peak | peak type | P3 |
| L17 | rev | revision |  |
| L17 | void | void flag | "1" means void |
| L17 | ts | injection time | ISO 8601 with the offset in effect |
| L17 | area_mvs | peak area | mVs |
| L17 | amp_v | amplitude | V |
| L17 | d | raw delta | permil |
| L18 | PRJ | project |  |
| L18 | SEQ | session token |  |
| L18 | INST | instrument token |  |
| L18 | CTR | autosampler counter |  |
| L18 | MZ | element | E4 |
| L18 | PT | peak type | P5 |
| L18 | REV | revision |  |
| L18 | VD | void flag | "Y" means void |
| L18 | EPOCHMS | injection time | UTC epoch milliseconds |
| L18 | AREA_MVS | peak area | mVs |
| L18 | AMP_MV | amplitude | mV |
| L18 | D_MILLI | raw delta | milli |
| L19 | project | project |  |
| L19 | sequence | session token |  |
| L19 | instrument | instrument token |  |
| L19 | counter | autosampler counter |  |
| L19 | species | element | E5 |
| L19 | kind | peak type | P4 |
| L19 | revision | revision |  |
| L19 | void | void flag | "true" means void |
| L19 | time | injection time | local wall time YYYY-MM-DDTHH:MM:SS without offset (H3) |
| L19 | area_vs | peak area | Vs |
| L19 | amp_mv | amplitude | mV |
| L19 | d_milli | raw delta | milli |
| L20 | PROJ | project |  |
| L20 | SEQ | session token |  |
| L20 | INST | instrument token |  |
| L20 | POS | autosampler counter |  |
| L20 | GAS | element | E1 |
| L20 | PT | peak type | P1 |
| L20 | REV | revision |  |
| L20 | STATUS | void flag | "void" means void |
| L20 | TS | injection time | UTC YYYYMMDDTHHMMSSZ |
| L20 | AREA | peak area | Vs |
| L20 | AMP_V | amplitude | V |
| L20 | DELTA | raw delta | permil |
| L21 | runlog.project | project |  |
| L21 | runlog.sequence | session token |  |
| L21 | runlog.instrument | instrument token |  |
| L21 | peaktab.counter | autosampler counter |  |
| L21 | peaktab.gas | element | E1 |
| L21 | peaktab.peak | peak type | P2 |
| L21 | peaktab.rev | revision |  |
| L21 | peaktab.flag | void flag | "VOID" means void |
| L21 | peaktab.t | injection time | ISO 8601 with the offset in effect |
| L21 | peaktab.area_mvs | peak area | mVs |
| L21 | peaktab.amp_mv | amplitude | mV |
| L21 | peaktab.delta | raw delta | permil |
| L22 | project | project |  |
| L22 | seq | session token |  |
| L22 | inst | instrument token |  |
| L22 | pos | autosampler counter |  |
| L22 | el | element | E2 |
| L22 | type | peak type | P1 |
| L22 | rev | revision |  |
| L22 | void | void flag | "1" means void |
| L22 | t | injection time | UTC epoch seconds |
| L22 | area | peak area | Vs |
| L22 | amp | amplitude | mV |
| L22 | d | raw delta | permil |

## Family notes

- `csv`: comma-separated, one header row, one record per row.
- `tsv`: tab-separated, one header row, one record per row.
- `psv`: pipe-separated, one header row, one record per row.
- `csv_semi`: semicolon-separated, one header row, decimal comma in every numeric field.
- `csv_comment`: comma-separated after leading lines that begin with #, columns in the order of the header.
- `jsonl_flat`: one JSON object per line.
- `ndjson_flat`: one JSON object per line.
- `ndjson_nested`: one JSON object per line with objects meta, inj and peak; area and delta are JSON strings that may carry spaces.
- `jsonl_nested`: one JSON object per injection with a peaks array; every array element is one record.
- `json_columnar`: one JSON document; export.columns names the fields of every array in export.rows.
- `xml_attr`: element inj holds project, seq, inst, pos and t; each child peak is one record.
- `xml_child`: each record element holds one child element per field.
- `yaml_blocks`: a YAML 1.2 list of injection blocks; each item of peaks is one record.
- `yml_grouped`: a YAML 1.2 document; sequences is a list of groups with sequence, project and instrument; each item of peaks is one record.
- `fixed`: fixed-width text; a header line and a ruler line; field i starts at the column given in the table.
- `md`: a Markdown table after a heading; one row per record.
- `tsv_wide`: tab-separated; one row per injection and revision index with an N block and a C block; an empty block is no record.
- `sqlite_flat`: SQLite table export.
- `sqlite_split`: SQLite tables injections and peaks joined on inj_id; one peaks row per record.
- `sqlite_runlog`: SQLite tables runlog and peaktab joined on run_key; one peaktab row per record.
- `sqlite_eav`: SQLite table kv(rec, field, value); all rows of one rec form one record.

The wide layout L15 carries no reference peaks. In the EAV layout the field names are those of the field map.
