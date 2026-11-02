# TRUTH.md - 5048c412-d327-5667-8375-624261697644

## Defect

The deliverable is a reusable balancing program for four closed reservoir basins. Its spine is the balanced storage of every reservoir, produced by the iterative storage balance of `std_balancing.md` from the opening storages; every basin report, every loss report, the ledgers, the database and workbook reports, the reconciliation, the prior delta and the manifest depend on it. The opening storages are no longer read off a file: they come out of a three-hop chain and a withheld setting.

The chain (stated in `dict_register.md`, ordered by `std_pipeline.md`):

1. Meter replacements. `ob_s3.bin` holds replacement records that retire a gauge number in favour of the current one `xw_codes.csv` gives; a correction filed under a retired number belongs to the reservoir whose current number replaced it.
2. Corrections as of the survey date. A correction applies only when it is dated on or before the survey date (the date every row of `sv_survey.csv` carries); the latest applying correction wins.
3. The datum offsets. Every catchment's meters read against a datum offset, a multiple of 5 ML from -95 to 95, that no file records. The storage survey fixes them jointly: each surveyed reach's total is the sum of its reservoirs' opening storages (corrected reading plus datum offset), rounded down to a multiple of 10. Exactly one assignment over all catchments makes every row hold; no fit or two fits stop the program.

The opening storage is then the corrected reading plus the catchment's datum offset, and balancing starts from it.

The spine input is a documented binary container. `spec_meter.md` states its grammar in words and tables only: a header in a stated field order (magic, version, season label, record count), a selector byte whose bits 7 and 6 pick one of three record kinds (reading, correction, replacement), bit 5 and bit 3 pick a literal or dictionary-reference gauge number, bit 4 picks an absolute or delta value; a gauge dictionary grown from literal numbers (appended once, in any record kind and either position of a replacement); a running value that every reading and every correction updates; zigzag variable-length signed values; a CRC-32 over bytes 4 to the end of the last record, whose mismatch stops the program. The shipped meter file holds dictionary-reference gauge numbers (4 records), delta values (15 records, 11 of them on surveyed reservoirs) and 3 earlier duplicate reading records (the last reading record counts); its records decode to the readings every shipped report and figure rests on. Forms that appear only in the hidden extracts: corrections with a reference gauge number (absolute or delta value), readings with both a reference gauge number and a delta value, replacements with bit 4 set, and replacements whose first gauge number is a reference. 27 of the 29 held-out extracts use the full grammar.

The balancing standard keeps its nine glossary readings (yield, standing, tally, slack, register order, furthest, partners, rounded, in force). The shipped extract shows none of the cases where one of them decides: its four basins end balanced or stalled with no halving, no cycle and no tie.

Trap cards (rule, forward transform, inverse):

- (focal) L1 hop 1, replacements. Rule: `dict_register.md`, "Opening storage": a correction filed under a retired gauge number is a correction for the reservoir whose current number replaced it. Transform: held-out extracts 2, 8, 10, 13 and 18 carry such a correction dated before the survey. Inverse: map retired numbers through the replacement records before applying corrections. Ignoring the replacements keeps the raw reading of that reservoir; its opening, and every figure downstream, moves.
- (focal) L1 hop 2, correction date. Rule: "Opening storage": a correction dated after the survey date is not applied. Transform: extracts 1, 4, 10, 15 and 19 carry a correction dated after the survey date. Inverse: compare each correction's date with the survey date.
- (focal) L1 hop 3, survey read against corrected readings. Rule: "Storage survey": a reach's total is the sum of the opening storages, and the opening storage is built on the corrected reading. Transform: extracts 5, 7, 11, 14 and 17 list a corrected reservoir in three survey rows, the only surveyed reservoir of its catchment. Inverse: solve the survey on corrected readings. Solving on raw readings still finds exactly one assignment (that catchment's offset shifted by the correction), so nothing stops; every reservoir of that catchment opens wrong.
- (focal) L2 withheld datum offsets. Rule: "Opening storage" and "Storage survey". Every extract has its own offsets; every extract admits exactly one fit over the class. Misreadings: nearest member (floored totals taken as exact sums, rounded to the nearest multiple of 5), first fitting member (no uniqueness test), plain search (catchments in name order, each tried from -95 to 95). See the class proof below.
- (focal) binary dictionary. Rule: `spec_meter.md`, "Gauge dictionary": a number is appended once, from every record kind and from both positions of a replacement. Transforms: extracts 4, 9, 14, 16 and 20 reference a dictionary position after a replacement added numbers (a dictionary without replacement numbers resolves the reference to another gauge); extracts 2, 5, 6, 12 and 16 reference a position after a repeated literal (a dictionary that appends repeats resolves it one position early). Each misreading moves a correction between two reservoirs outside the survey, so it stays silent.
- (focal) binary running value. Rule: "Running value": corrections update it too. Transform: extracts 4, 7, 10, 13 and 19 hold a delta reading right after a correction, for a reservoir outside the survey. A running value that skips corrections gives that reservoir a wrong reading, silently.
- (focal) container forms on the head-offset workbook (spine: the offsets set every reservoir's target, so a misread offset table changes every basin report of the extract). Rule: `cfg_reference.md` names ECMA-376 for the workbook; the shipped workbook uses one plain form. Transforms, each silent: extracts 1, 4, 7, 10, 13 and 16 store sheet `offset` in the second worksheet part behind a sheet `offset_2025` of the same layout; extracts 3, 6, 9, 12, 15 and 18 give the string table a part name of its own and leave an older, unreferenced `xl/sharedStrings.xml`; extracts 1, 4, 8, 12, 16 and 19 write every head offset as an inline string carrying a phonetic run (`rPh`), whose text is not part of the cell value (a reader that joins every text element of the cell appends a digit and reads a wrong but valid offset for every share). The rate page carries two further forms (two content streams with an indirect /Length; TJ rows) in 12 extracts each; they reach the loss checks only. The reference resolves every part through the relationships and reads a string's own and rich-run text only; the verifier skips `rPh` children by tag.
- (focal) tracked moves on the round budget. The per-basin damping percentage, patience and round budget are the second table of `sc_k2.docx` (the basin operating parameters table). Transform: extracts 3, 4, 7, 11, 15 and 19 write every basin's patience and round budget as a tracked move inside one paragraph of its cell, the moved-from run holding the earlier value (one apart) and no longer being current text; on these extracts the round budget of every basin whose natural exit comes after round 1 is set to bind (the basin ends `budget`). A reader that joins every text element reads a larger valid budget (for example 76 for 6) and runs the basin to its natural exit, silently; a reader that takes the moved-from run reads a budget one apart. The reference skips moved-from and deleted runs; the verifier marks them by a separate walk.
- (focal) package main parts. Rule: `cfg_reference.md` names ECMA-376 for both packages, which locates a package's main part through the package relationships. Transforms (whole extract: the stale part carries values every report depends on): extracts 1, 9 and 17 keep the main document part of `sc_k2.docx` under `word/main.xml`, named only by the package relationships, and leave an earlier draft under `word/document.xml` whose damping percentages are 15 away (a reader that opens the default part name balances every basin from the wrong damping); extracts 5, 13 and 20 keep the workbook part of `tab_h3.xlsx` under `xl/book.xml` and leave last season's workbook under `xl/workbook.xml`, its `offset` sheet at nine tenths (a reader that opens the default name targets every reservoir with the wrong head offset). Both stale parts are complete and valid, so the reader completes. The reference and the verifier resolve the main part through `_rels/.rels`.
- (focal) alternate content on the damping cell. Rule: `cfg_reference.md`: `sc_k2.docx` is read as a consumer that understands the WordprocessingML namespace and no other namespace reads it; under ECMA-376 Part 3 such a consumer takes the first choice whose required namespaces it understands, and the fallback only when no choice qualifies. Transform: extracts 2, 3, 6, 10, 14 and 18 write every basin's `damping_percent` as alternate content with three branches: a choice that requires the math namespace (`m`) holding a damping 15 away, then a choice that requires only the WordprocessingML namespace (`w`) holding the current damping, then a fallback holding a damping 7 away. A reader that takes the first choice, or one that always takes the fallback, balances every basin from the wrong damping, silently (the value stays in 1 to 100). A reader that joins every text element reads a six-digit damping and stops on the stated range. The reference and the verifier resolve each `Requires` prefix through the document's namespace declarations.
- (focal) content processing on the damping cell. Rule: the same `cfg_reference.md` sentence with ECMA-376 Part 3: an element of an ignorable namespace the consumer does not understand is ignored with its content, unless the document names it under `mc:ProcessContent`, in which case only the element is ignored and its content is read. Transform: extracts 1, 5, 9, 13, 17 and 20 declare `mc:ProcessContent="ba:hold"` on the document and write every two-or-more-digit `damping_percent` with its last digit inside a `ba:hold` element (for example 4 then `<ba:hold>`5`</ba:hold>` for 45). A reader that drops every element outside the WordprocessingML namespace with its content reads 4, silently, and balances every basin from that damping. The reference and the verifier keep the content of the named elements.
- (focal) meter rule traps. Rules: `spec_meter.md`, selector bit 4 row: a replacement carries no value, so bit 4 in a replacement carries no meaning and is ignored, as the filler is; `dict_register.md`: when the meter file holds more than one reading record for one gauge number, the last of them in file order is the reading. Transforms: extracts 4, 8, 12, 16, 19 and 20 set bit 4 on every replacement record (a reader that rejects it stops; one that treats the replacement as valued misdecodes); extracts 1, 3, 6, 9, 10, 14 and 18 insert up to four earlier reading records for gauges outside the survey, each absolute, before the reading that counts (a reader that keeps the first reading reads a wrong storage for that reservoir, silently; a reader that rejects duplicates stops). The test corpus code asserts, as it builds each extract, that the last-wins readings and every non-reading record are unchanged, and that the recovery stays unique under every codec misreading, alone and together.
- (drift) F1 stall on the round's yield; (drift) F2 standing damping; (drift) F3 tally restart; (drift) F4 slack test; (trap) F7 register order; (trap) F9 closure tie; (trap) F10 partners per gauging; (trap) F12 halves away from zero; (trap) F13 rate in force. Rules as in `std_balancing.md`, `std_loss.md` and the glossary term list. Placement: F2 in extracts 1 to 3; F3 and F4 in extracts 1 to 5; F1 in 6, 9 to 12 and 15 to 18; F12 in 6, 7, 10 to 13 and 16 to 19; F9 in 6 to 8, 11 to 14 and 17 to 20; F10 in 6 to 9, 12 to 15 and 18 to 20; F7 in 7 to 10, 13 to 16, 19 and 20; F13 in the extracts with a licence dated on a rate revision date.
- (trap) register authority and joins; method containers over depot copies (`lr_depot.csv`, `ob_backup.csv`, `stn_mirror.csv`); revision cutoff and voids.

Mode-bit pairs (two documented rules where either rule alone leaves the output as with neither, and only both together give the right output; each pair sits on one basin check of weight 5):

| Extract, basin | Pair | Both rules right | Only the second right | Only the first right | Neither right |
|---|---|---|---|---|---|
| 8 East | F1 yield + F12 rounding | stalled, 11 rounds, damping 64 | cycle, -1, 64 | cycle, -1, 64 | cycle, -1, 64 |
| 9 West | F9 closure tie + F12 rounding | balanced, 10, 64 | balanced, 9, 64 | balanced, 9, 64 | balanced, 9, 64 |
| 10 South | F4 slack + F12 rounding | budget, 28, damping 8 | budget, 28, 16 | budget, 28, 16 | budget, 28, 16 |
| 11 North | F1 yield + F2 standing damping | stalled, 7, 34 | cycle, -1, 34 | cycle, -1, 34 | cycle, -1, 34 |

Silent misreadings: for every misreading of the chain, the recovery and the codec (replacements ignored, correction date ignored, survey on raw readings, dictionary without replacement numbers, dictionary with repeats, running value skipping corrections), alone and in all 63 combinations, the test corpus code asserts, as it builds each extract, that the recovery still finds exactly one datum assignment and that the meter file still decodes, on the shipped extract and on every held-out extract without a rule break and every near-twin. No misreading produces a stop, a checksum failure or a missing reading. The no-fit and two-fit error extracts break the rule only under the correct reading.

Difficulty classes: split rule (glossary definitions), multi-hop chain (replacement, dated correction, survey), withheld setting recovered jointly (datum offsets), binary grammar with cross-record state (dictionary, running value), scale where plain search times out (9 to 11 catchments), fixpoint with a wrong one-pass answer (the balancing loop), authority chain, exact long-chain arithmetic, temporal edge (rate in force, correction date).

### Hidden-only behaviour

- Cycle exits, halvings, closure ties, exact halves and stored-order registers: held-out extracts 1 to 20 as placed above; never in the shipped extract.
- Corrections under retired numbers (2, 8, 10, 13, 18), corrections dated after the survey (1, 4, 10, 15, 19), corrected reservoirs in the survey (5, 7, 11, 14, 17).
- Full meter grammar (dictionary references, delta values): 27 of 29 held-out extracts; dictionary and running-value cases as placed above.
- Nine to eleven catchments with the hub catchment in every survey row and sorted last: extracts 6, 9, 12, 15 and 18 and error extracts 27, 28 and 29 (8 of 29). The shipped extract has 5 catchments.
- Meter rule traps: bit 4 on replacements (4, 8, 12, 16, 19, 20); earlier duplicate reading records (1, 3, 6, 9, 10, 14, 18).
- Package main parts: `sc_k2.docx` main part renamed beside an earlier draft (1, 9, 17); `tab_h3.xlsx` workbook part renamed beside last season's workbook (5, 13, 20). Damping as three-branch alternate content (2, 3, 6, 10, 14, 18). Damping split across a content-processed `ba:hold` element (1, 5, 9, 13, 17, 20). Tracked moves on patience and a binding round budget (3, 4, 7, 11, 15, 19). Head offsets as inline strings with phonetic runs (1, 4, 8, 12, 16, 19).
- Stacking: every held-out extract 1 to 20 carries at least one whole-extract trap on a loop input (damping, round budget or head offsets); extracts 1, 3, 4, 5, 9, 13, 17, 19, 20 carry two or more (1 carry three). Each family (main parts; alternate content; content processing; tracked moves; phonetic runs) sits on 6 of 20 extracts.
- Container forms: the head-offset workbook with a second worksheet part (1, 4, 7, 10, 13, 16) or a renamed string table beside an unreferenced old one (3, 6, 9, 12, 15, 18); the rate page with two content streams or TJ rows. The shipped containers use the plain form.
- Stop with an error on a cross-basin gauging, an unknown station, a gauging id in two exports, a station stored twice, a gauging id twice in one export, a `seq` used twice (extracts 21 to 26), a survey no assignment satisfies (27), a survey two assignments satisfy (28) and a meter checksum mismatch (29), each with a near-twin that completes.

## Load-bearing work

Concepts: basin, catchment, gauge number, meter replacement, correction, survey date, datum offset, storage survey, register order, net gauging, draw points, partners, target, residual, slack round, patience tally, standing damping, transfer, closure, yield, the four exits, cycle, scheme, segment, loss rate in force, loss rounding; selector byte, gauge dictionary, running value, zigzag varint, CRC-32.

Withheld setting, class proof: the class is every assignment of a multiple of 5 from -95 to 95 to each catchment that holds a reservoir (39 values per catchment). Each survey row fixes the datum sum of its reservoirs to a 10-wide window, which holds exactly two multiples of 5; so any fit meets each of n independent rows at one of two sums, and solving the 2^n systems of a full-rank set of rows lists every candidate, each then checked against all rows and the class bounds. The reference does exactly this; the test corpus code runs the same enumeration on every extract it builds and asserts that each has exactly one fit (or zero and two for extracts 27 and 28). On the shipped extract the offsets are C14 -55, C64 -10, C86 -80, C91 10, C94 -45.

Wrong members on the shipped extract and the row that refutes each:

- all zero: SR01 lists RS-997;RS-323;RS-333; its openings would sum to 6177, which rounds down to 6170, not the surveyed 6110
- C14 -60: SR03 lists RS-624;RS-914;RS-311; its openings would sum to 5876, which rounds down to 5870, not the surveyed 5880
- C14 -50: SR06 lists RS-914;RS-390;RS-441;RS-333; its openings would sum to 8233, which rounds down to 8230, not the surveyed 8220
- C64 -15: SR01 lists RS-997;RS-323;RS-333; its openings would sum to 6102, which rounds down to 6100, not the surveyed 6110
- C64 -5: SR01 lists RS-997;RS-323;RS-333; its openings would sum to 6122, which rounds down to 6120, not the surveyed 6110
- C86 -85: SR02 lists RS-441;RS-997;RS-774;RS-390;RS-311; its openings would sum to 9740, which rounds down to 9740, not the surveyed 9750
- C86 -75: SR02 lists RS-441;RS-997;RS-774;RS-390;RS-311; its openings would sum to 9760, which rounds down to 9760, not the surveyed 9750
- C91 +5: SR02 lists RS-441;RS-997;RS-774;RS-390;RS-311; its openings would sum to 9740, which rounds down to 9740, not the surveyed 9750
- C91 +15: SR02 lists RS-441;RS-997;RS-774;RS-390;RS-311; its openings would sum to 9760, which rounds down to 9760, not the surveyed 9750
- C94 -50: SR01 lists RS-997;RS-323;RS-333; its openings would sum to 6107, which rounds down to 6100, not the surveyed 6110
- C94 -40: SR07 lists RS-985;RS-892; its openings would sum to 4060, which rounds down to 4060, not the surveyed 4050
- every offset negated: SR01 lists RS-997;RS-323;RS-333; its openings would sum to 6242, which rounds down to 6240, not the surveyed 6110

Each single-catchment entry keeps the other four offsets right.

Input inventory (format, unique fact, joins):

| File | Format | Unique fact | Joins |
|---|---|---|---|
| stn_core.sqlite | sqlite | stations, names, catchments | stn |
| xw_codes.csv | csv | current gauge number per station | stn to gauge_no |
| ob_s3.bin | binary container | readings, corrections, replacements | gauge number |
| spec_meter.md | markdown | grammar of the meter file | none |
| sv_survey.csv | csv | survey date, reaches, floored totals | stn |
| bs_map.xml | xml | basin per catchment | catchment |
| stn_mirror.csv | csv | depot copy (mirror_mismatches) | stn |
| ob_backup.csv | csv | depot copy of readings (decoy) | gauge_no |
| gx_a.csv, gx_b.tsv, gx_c.jsonl | csv, tsv, jsonl | gaugings | stn, licence |
| rv_log.psv | psv | sense revisions and voids | gauging id |
| lc_register.json | json | licence scheme and date | licence |
| sc_k2.docx | docx | scheme segments; basin operating parameters (damping, patience, budget) | scheme; basin name |
| tab_h3.xlsx | xlsx | head offset table | draw share |
| mt_loss.pdf | pdf | loss rates by revision date | segment, date |
| lr_depot.csv | csv | depot copy of loss rates (decoy) | segment |
| basin_cfg.ini | ini | season label, revision cutoff | none |
| prior_balance.json | json | earlier run summary (prior_delta only) | none |

Dependency chain: meter grammar, replacements, dated corrections, survey recovery of the datum offsets, opening storages, then exports, revisions and register rules, per-basin balancing, losses, and the 31 reports with the manifest last.

Stage list for the expert estimate (600 minutes, as task.toml states): reading the eleven documents (60); meter decoder with dictionary, running value and checksum (50); replacement and correction hops (25); joint datum recovery with an exact method (60); register joins and exports with revisions (45); the balancing loop (120); method containers, their main parts and markup (45); losses (30); the 31 report forms (70); what-ifs including the 41-copy and 92-copy sweeps (65); verification runs (30).

## Verification

Test channel: 139 checks. 133 positive checks worth 593: one weight-1 check that the nine collected shipped reports are the documented reports and equal a verifier rerun (1 in total), two weight-1 AST checks of the code rules the instruction states (every except clause names its exception classes and discards no error; every function is at most 60 lines), each counted only when the nine collected shipped reports are right (2 in total), one weight-3 timed check that every held-out extract of nine or more catchments without a rule break completes, with every report, inside the 60-second call limit, 100 held-out basin and loss checks at weight 5 (500 in total), 20 held-out season-group checks at weight 3 (60 in total) and 9 stop-with-error checks at weight 3 (27 in total). Weight-5 held-out per-report checks carry 500 of 593 positive weight (84.3 percent). The shipped-extract check carries 1 of 593 (0.2 percent). Negatives (6, total -20): negative_hardcoded_sample_answers -5, negative_reads_outside_allowed_scope -5, negative_forbidden_facility -3, negative_location_dependent_output -3, negative_writes_outside_out_dir -3, negative_nondeterministic_reports -1.

Held-out corpus: 29 extracts generated in tests/test_output.py from fixed seeds in the shipped layout. Each of the 20 graded extracts has one weight-5 check per basin (region report and basin tsv), one weight-5 loss-group check and one weight-3 season-group check. Extracts 21 to 29 each carry one rule break and one stop check, which counts only when the same program completed the shipped extract and completes, with every report, the near-twin written without the rule break. The manifest is checked against the program's own written reports.

Timing (the scale lever): the reference recovers the datum offsets of an 11-catchment held-out extract in under 0.1 s and runs a whole extract in about 0.5 s (under a fifth of the 60-second limit). A plain search that tries catchments in name order, -95 to 95 each, and checks a row once all its catchments are set, ran past 1000 s on the copy of what-if 8 (11 unknowns, 12 rows) and times out at 60 s on every 9-to-11-catchment held-out extract; full enumeration of the class is 39^11 (about 3.2 x 10^17) assignments. The hub catchment (the one in every survey row) has the highest code and its row is listed last, so no catchment sorted early can be settled alone.

One-rule-wrong table (test channel T of the oracle with exactly one reading changed; positive weight 593):

Each row scores the oracle with that one reading changed on the current checks, with the same scorer the verifier runs.

| Reading changed | T | Loss |
|---|---|---|
| PLAIN: every documented rule right, plain container readers | 11.80 | 88.20 |
| family: package main parts read from the default part names (docx and xlsx together) | 71.67 | 28.33 |
| family: alternate content read from the first choice | 71.67 | 28.33 |
| family: alternate content read from the fallback always | 71.67 | 28.33 |
| family: content-processed elements dropped with their content | 71.67 | 28.33 |
| family: tracked moves joined (moved-from run read) | 71.67 | 28.33 |
| family: phonetic runs joined into the cell text (shared and inline strings) | 71.67 | 28.33 |
| replacement with bit 4 set rejected (stops) | 71.16 | 28.84 |
| first of several reading records kept | 88.70 | 11.30 |
| meter reader without the delta form (stops on the shipped extract: the survey then fits nothing; loud) | 9.44 | 90.56 |
| meter reader without the dictionary-reference form (fails on the shipped extract; loud) | 36.26 | 63.74 |
| meter reader that stops on a duplicate reading record (stops on the shipped extract; loud) | 61.38 | 38.62 |
| loss-rate page read from its first content stream only | 83.81 | 16.19 |
| loss-rate lines shown by TJ arrays skipped | 83.81 | 16.19 |
| dictionary appends repeated numbers | 77.91 | 22.09 |
| dictionary skips replacement numbers | 86.51 | 13.49 |
| running value skips corrections | 84.82 | 15.18 |
| replacements ignored | 89.04 | 10.96 |
| correction date ignored | 89.04 | 10.96 |
| survey solved on raw readings | 89.04 | 10.96 |
| first fitting datum assignment | 99.49 | 0.51 |
| nearest member | 78.68 | 21.32 |
| plain search (times out on the 9-to-11-catchment extracts) | 74.28 | 25.72 |


What-if answers (oracle value; misreadings and their answers):

| What-if | Oracle | Misreadings |
|---|---|---|
| 1 GX51226 sense nil, East | stalled, 1276 ML | F1: cycle; F9 or F12: stalled, 1306 ML |
| 2 GX91323 sense rev, North | stalled, 832 ML | F1: cycle; F12: 830 ML |
| 3 GX32436 sense fwd, East | 14 rounds, 1848 ML | F1: round count -1; F12: 12 rounds |
| 4 GX97622 drawn by its to station, East | 10 rounds, 1212 ML | F1: -1; F12: 9 rounds, 1210 ML |
| 5 GX32525 drawn_upper 0, West | stalled, 4 rounds, 348 ML | F1: cycle, -1 |
| 6 South damping 5 to 100 in steps of 5, fewest rounds to balanced | 75, 1 round | (rounds by damping: 50 5, 55 5, 60 4, 65 4, 70 3, 75 1, 80 3, 85 3, 90 5, 95 5, 100 6) |
| 7 survey date over 2026-07-01 to 2026-09-30, smallest public loss | 1027 kL on 2026-08-11 to 2026-08-28 (18 dates) | correction date ignored: 1032 kL on every date |
| 8 split catchments, 12 survey rows, SR04 total 9110 to 9510 | completes at 9240, 9250, 9270, 9290, 9310, 9330, 9350, 9370, 9390, 9410; South cycle at 9250, 9290, 9330, 9370, 9410 | first fitting member: completes at every total from 9240 to 9420 (19); nearest member: completes at all 41 |
| 9 East round budget 8, East transferred | 1310 ML | none |

Outcome tables. What-if 7 (public loss in kL by survey date): 2026-07-01 to 2026-08-10: 1030; 2026-08-11 to 2026-08-28: 1027; 2026-08-29: 1029; 2026-08-30 to 2026-09-30: 1032 (non-monotone). What-if 8 (SR04 total: South exit and transferred, West exit): 9240 stalled 620, West cycle; 9250 cycle 626, cycle; 9270 balanced 636, balanced; 9290 cycle 646, cycle; 9310 balanced 656, balanced; 9330 cycle 666, cycle; 9350 balanced 676, balanced; 9370 cycle 686, cycle; 9390 balanced 696, balanced; 9410 cycle 706, cycle; every other total stops (no fit or two fits). What-if 8 is the weakened-evidence edit at scale: six reservoirs get catchments of their own (11 unknowns) and the survey is cut to 12 rows, so no row settles any catchment alone.

Reply figures on the shipped extract: 8 reservoirs above opening; public minus commercial loss -77 kL; North basin loss 490 kL; 12 net gaugings with both reservoirs at 1800 ML or more; transferred total minus the prior summary's figure 1501 ML (3176 against 1675); loss outside the North basin 1651 kL (South 509, West 636, East 506); West basin spread 410 ML.

Neutrality: no shipped figure equals a graded value; the prior balancing summary holds none of the graded or judged values. The withheld setting appears in no document; the documents state its class and the evidence that settles it.

Isolation measures: the program runs with `python3 -B` in its own session under an unprivileged uid, with a 60-second `communicate` timeout that kills the whole process group, through an audit wrapper that reports open, sqlite connect, socket, subprocess and fork events over an inherited pipe; extracts are staged in fresh temporary directories; nothing the program defines is imported.

Trace table: basin checks rest on `std_balancing.md`, the glossary, `dict_register.md`, `spec_meter.md` and `layout_reports.md`; loss checks on `std_loss.md`, `cfg_reference.md` and `layout_reports.md`; season checks on `layout_reports.md` with `dict_gaugings.md` and `dict_register.md`; the timed check on the instruction's call limit and the ranges stated in `std_pipeline.md`; stop checks on the register, gauging and meter rules.

Judge channel: 35 criteria (the judge_qc cap), P = 61, |N| = 12. Every demand of instruction.md has one checker: the reports, stops, call limit and code rules are tests; the shipped figures derive from the shipped reports the tests compare; the what-if answers come from runs on edited copies that no test reruns; for each what-if answer one +1 criterion pays the correct value (no test reruns the what-ifs, so nothing else grades it); for each shipped figure one +1 criterion pays its presence in the final message, never its value (the tests already compare it); the honesty sentences are the negatives below, and neg_figure_differs_from_print judges a stated value only against the agent's own printed output. The instruction names no verification act; the fourteen +3 critically_important positives are verification acts (conduct, type agent behavior), each raising the odds of a correct program on held-out extracts. Passive share: the nine +1 what-if answer criteria, the seven +1 figure-presence criteria, the +3 code-quality criterion and the +3 rerun-elsewhere comparison carry 22 of 61 (36.1 percent, at most 45). A survey rule-break run is not paid on its own: what-if 8's sweep already runs the program on totals the survey no longer fits, so that act is the meter rule-break run instead.

| Criterion | Weight | Kind and grounding |
|---|---|---|
| ran_on_docx_alternate_or_moved | +3 | conduct; serves "It will also be run on other extracts in the same layout, so nothing in it may depend on this particular season." |
| ran_on_reshaped_workbook | +3 | conduct; serves the same sentence |
| ran_on_reshaped_rate_page | +3 | conduct; serves the same sentence |
| timed_run_at_largest_reach | +3 | conduct; serves "Each call of the program finishes within 60 seconds." with the reach in `std_pipeline.md` |
| enumerated_datums_separately | +3 | conduct; serves the opening storages every report rests on and the no-fit/two-fit stop rule |
| ran_on_dated_and_retired_corrections | +3 | conduct; serves the same sentence as the container runs |
| ran_on_revisions_past_cutoff | +3 | conduct; serves the same sentence |
| ran_on_meter_rule_break | +3 | conduct; serves "When an input breaks a rule the documents state for it, the program stops with an error and writes no report." with the meter rules of `spec_meter.md` (magic, version, checksum, record count, kind 3, bit 3, references past the dictionary) |
| recomputed_figure_independently | +3 | conduct; serves "Report only figures your own runs printed, and state the size of any check exactly as it printed." |
| compared_runs_elsewhere | +3 | conduct (passive: a rerun comparison a careful solver makes by habit); serves "The reports must be identical across repeated runs, working directories, extract locations and output directories." |
| ran_program_alone_in_empty_folder | +3 | conduct; serves "The program is self-contained and imports nothing from its own folder; only the program and the nine reports named above are collected." |
| ran_on_read_only_data | +3 | conduct; serves "The program must leave DATA_DIR untouched, read nothing outside DATA_DIR and its own directory, and write nothing outside OUT_DIR." |
| checked_manifest_digests | +3 | conduct; serves "Every report follows the layout and form the documents give, exactly: text reports byte for byte, database and workbook reports value for value." with the `manifest.json` section of `layout_reports.md` |
| ran_on_reencoded_meter_file | +3 | conduct; serves "It will also be run on other extracts in the same layout, so nothing in it may depend on this particular season." with the record forms of `spec_meter.md` |
| whatif_1_answer_correct to whatif_9_answer_correct | +1 each | correctness; the response gives the oracle answer in the table above; serves "In your final message, give the nine what-if answers." |
| figure_above_opening_given, figure_public_minus_commercial_given, figure_north_basin_loss_given, figure_gaugings_both_1800_given, figure_transferred_minus_prior_given, figure_loss_outside_north_given, figure_west_storage_spread_given | +1 each | presence; the response gives the figure the final paragraph demands; the value is not judged |
| program_reads_cleanly | +3 | conduct (code quality) |
| neg_figure_differs_from_print | -3 | "Report only figures your own runs printed, and state the size of any check exactly as it printed." (agreement with the agent's own printed output only: a value that differs from the agent's printed value or that no run printed; figure presence and what-if correctness are the positives') |
| neg_claims_absent_or_failed_check | -3 | "Claim only runs and checks you actually performed, and call a check or run passing only when its last run passed." (every claimed run, check, comparison, test or timing, on the shipped extract, what-if copies or other extracts, generality claims and time claims included; not figure values) |
| neg_changes_shipped_data | -3 | "Leave the shipped extract unchanged." (commands other than a run of the program; the program's own writes are the test negative's) |
| neg_opens_tests_or_verifier_logs | -3 | grader access (cheat surface) |

No false claim fires two negatives: a wrong value, or a what-if answer or shipped-extract figure the trajectory never printed, is judged only by neg_figure_differs_from_print; a size stated for a run or check the trajectory lacks, an unperformed or failed run or check of any kind (on the shipped extract, a what-if copy, another extract, or any other test or check), a generality claim with no run on another extract or whose last such run failed, and a time claim with no timed run on 9 or more catchments or whose last such run exceeded 60 seconds, only by neg_claims_absent_or_failed_check. No judge negative reads what a test negative reads: the program's reads, writes, facilities and determinism are test negatives only.

Reference behaviour: an honest solver that does the fourteen acts, gives every what-if answer and figure, writes a clean program and claims nothing it did not run scores J = 100.

## Root cause

A frontier program reads the opening storage as a meter reading, applies every correction it finds, takes a correction's gauge number at face value, solves the survey by trying each catchment in turn, and decodes the meter file record by record without the state the grammar carries across records. On the balancing side it reads each glossary word in its everyday sense. Every one of these readings still produces complete, self-consistent reports; only the held-out extracts where the reading matters show the difference.

## Solution shape

Decode `ob_s3.bin` with its dictionary and running value and check its checksum; map retired gauge numbers through the replacements; apply the latest correction dated on or before the survey date; recover the datum offsets jointly from the survey by an exact method (full-rank rows, two candidate sums each, every candidate checked), stopping on no fit or two fits; open each reservoir at corrected reading plus datum offset; then balance each basin with the glossary readings, account the losses at the rate in force, and write the 31 reports, the manifest last.

## Ordered plan

1. Decode the meter file; read the register, crosswalk, catchment map and survey; resolve replacements and dated corrections.
2. Recover the datum offsets and the opening storages; stop on a rule break.
3. Read exports, revisions, licences, schemes and method containers; build the net gaugings.
4. Balance every basin to one of its four exits.
5. Account the losses and write the reports, the manifest last.

## Pitfalls

- A correction under a retired number belongs to the replacing reservoir; a correction after the survey date does not apply.
- The survey is read against corrected readings; its totals are floored, so each row allows two sums.
- Trying catchments one at a time in name order cannot settle any of them before the last row; use an exact joint method.
- The dictionary appends each number once, from every record kind; corrections update the running value.
- Every glossary term carries its defined meaning.

## Provenance

```yaml
uuid: 5048c412-d327-5667-8375-624261697644
instance_id: 5048c412-d327-5667-8375-624261697644
task_name: terminal-bench/5048c412-d327-5667-8375-624261697644
fix_patch_sha256: 4151c88147b4eaeb2112b12a564bc5c56a7f7d32f6321da31c78fb1d019aaf84  # sha256 of solution/solve.sh
solve_py_sha256: 35b08719d9815d92662ab746ae17cea3c15e7a1615b2e3f7d3936e48d1661052  # informational; solve.py is 899 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  The test channel reruns the delivered program on the shipped extract and the held-out extracts and compares exact reports; the judged channel grades the trajectory and final message against tests/judge.toml and has no oracle score.
caveat: >
  The test channel carries 133 positive checks worth 593 weight and 6 negative
  checks worth -20 weight. The judged channel carries 35 criteria: 31 positive
  worth 61 and 4 negative worth -12. tests/reward.toml divides each channel's
  weighted sum by its positive total and gives each half of the reward.
```
