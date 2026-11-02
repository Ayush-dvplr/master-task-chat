# TRUTH.md - f348165e-f7f6-5e73-b82d-b84ee751f3b0

## Defect

Nothing is broken. `/app/data` holds one settlement period of a model-serving platform: five request logs (`ev_01.rqb` to `ev_05.rqb`, one per traffic class, 5,856 request records in all, each a binary RQB1 container whose grammar `lg_rqb.md` gives), the register (`tn_reg.sqlite` with the tables tenant, pool and alias, sharded with the group crosswalk `xw_05.csv` and the pool profiles `pp_31.docx`), two correction layers (`am_07.tsv`, `ov_07.jsonl`), the method constants in binary documents (rate card `rc_23.xlsx`, model weights `mm_04.docx`, the meter sheet `ku_11.pdf`), the control file `ctl_r7.json`, a prior output `px_prev.json`, a plain-text tenant export `tn_mirror.csv`, and ten documents (`ct_svc.md`, `gl_00.md`, `lg_rqb.md`, `st_demand.md`, `st_settle.md`, `st_bill.md`, `pr_num.md`, `od_stage.md`, `ed_cases.md`, `fm_reports.md`). The deliverable is `/app/out/optimize.py` with three entry points (directory form writing 30 reports, one-log form printing a class result object, module function `aggregate`) that settles every pool and bills it exactly, and runs its `aggregate` call in at most 70 percent of the CPU time of a baseline that decodes the log again for every member in every round.

The work is one documented pipeline: decode the request logs (RQB1: header, selector modes, key and model tables, running instant, checksum), recover the units per RU of every pool from the meter sheet, build demand (window `(start, end]`, alias reach by effective instant, rejected and orphan requests dropped, cut requests counting prompt tokens only), apply corrections (amendments in seq order, overrides over amendments, cutoff and unmatched statuses), settle every pool by an iterative rebalancing loop (st_settle.md), bill (st_bill.md) and write 30 interlocked reports (fm_reports.md) including a SQLite ledger, an xlsx workbook and a sha256 manifest.

Items:

0. (focal) The register is sharded: pool rows carry only a group, the crosswalk maps the group to a profile code, and the profile row gives the starting step, patience and budget.
1. (focal) The units per RU of each pool is stated nowhere. The glossary gives its class (a multiple of 100 from 1200 to 5000, 39 values) and st_demand.md says the meter sheet settles it: a reading equals the sum, over the distinct members its keys reach at the reading instant, of the ceiling of the member's token units up to that instant divided by the units per RU of its pool. Every extract has its own values; an extract whose readings no assignment, or more than one assignment, meets is rejected.
2. (focal) Three hops come before that recovery, each stated once where it lives: a reading reaches the owner of a key at the reading instant (alias table, st_demand.md), membership is taken after corrections (ct_svc.md), and only requests completed at or before the reading instant count (st_demand.md).
3. (focal) The request logs are binary (lg_rqb.md): literal, delta and repeat records, a filler byte, a key table addressed back from its newest entry and a model table addressed from its first entry, a running instant that starts at the header base, zigzag signed fields, an optional class byte, and a CRC-32 over a stated region.
4. (focal) The settlement loop of st_settle.md decides every holding, round count and orchestration charge; its exact behaviour at nine points is fixed by glossary definitions of ordinary words (standing, improve, patience count, halve, furthest from its target, yield, round count, cycle, nearest whole unit).
5. (drift) The plain-text tenant export and the prior output look like convenient sources; the authority rule names the register as the only source of tenants, pools and aliases.
6. (drift) The `aggregate` call must beat a baseline that decodes the log per member per round.
7. (trap) Correction precedence, the half-open window, alias effective instants, and the nine loop words each have an everyday reading that agrees with the shipped extract on most pools.

Out of bounds: writing shipped answers into the program (`negative_hardcoded_sample_answers`); opening files outside DATA_DIR, OUT_DIR and the program folder (`negative_reads_outside_scope`); connecting a socket, starting a process, reading the current time, or using random, uuid, secrets, a third-party module or a module from its own folder (`negative_forbidden_facility`); output that depends on the extract path, working directory or output directory (`negative_location_dependent_output`); writing into the extract or outside OUT_DIR (`negative_writes_outside_out_dir`); reports that differ between two runs (`negative_nondeterministic_output`).

## Load-bearing work

Collected artifacts: `/app/out/optimize.py` and the nine frozen reports. The verifier reruns the program on 37 hidden extracts: 0 to 17 are graded loop extracts, 18 to 35 each break one invariant (each also run as a near-twin with the defect removed), and 36 is the timed extract. On hidden extracts 4 and 10 the verifier passes an OUT_DIR that does not exist yet.

Report groups graded per hidden loop extract (exact comparison: text byte for byte, SQLite and xlsx value for value): scenario (weight 5: the five scenario files, perf_report.json, bottleneck_analysis.json and the printed result line of one log), pool (weight 5: pool_settlement.csv, tenant_holdings.tsv, round_trace.psv, exit_summary.xml, pool_members.json, holding_shift.xml), billing (weight 5: tenant_bills.csv, class_billing.json, invoice_lines.yaml, invoice_digest.md, overage.txt, rate_application.json), ledger (weight 3: billing_ledger.sqlite, billing_book.xlsx, reconciliation.json, delta_prior.csv, recommendations.json, data_quality.json, demand_by_model.tsv, orphans.csv, corrections_applied.csv, window_counts.csv, and the manifest against the run's own reports). A hidden extract the program rejects, or on which it times out, loses all 18 points.

Weight concentration: 275 of the 352 positive points (78.1 percent) sit on weight-5 checks of hidden extracts (54 group checks and the timed check). Loss percentages in the tables below are of 350 points, the positive test total without the two program-shape checks of weight 1.

### Depth levers

Withheld setting. Units per RU per pool, class {1200, 1300, ..., 5000}. In every extract (shipped, every hidden extract and every twin) exactly one assignment over the class meets the meter sheet, after the three hops. Shipped values: pl-bu1 1400, pl-la1 2700, pl-pe1 5000, pl-pe2 4900, pl-st1 1800, pl-vi1 4400, pl-vi2 4200. Class-wide proof on the shipped extract: the reference search (unary filter, then backtracking over all 39 values of every pool with bound pruning) visits every member of the class for every pool and finds one assignment. Plausible wrong members, each with every other pool at its value, and the reading that refutes it:

| pool | wrong value | refuting reading | value it gives | sheet |
|---|---|---|---|---|
| pl-bu1 | 1200 / 1300 / 1500 / 1600 | M15 | 61 / 59 / 57 / 56 | 58 |
| pl-la1 | 2500 / 2600 / 2800 / 2900 | M01 | 53 / 51 / 47 / 46 | 49 |
| pl-pe1 | 4800 / 4900 | M22, M23 | 83 / 80 | 82, 79 |
| pl-pe2 | 4700 / 4800 | M19, M25 | 63 / 70 | 62, 69 |
| pl-st1 | 1600 / 1700 / 1900 / 2000 | M03 | 46 / 44 / 39 / 37 | 41 |
| pl-vi1 | 4200 / 4300 / 4500 / 4600 | M02 | 57 / 55 / 53 / 52 | 54 |
| pl-vi2 | 4000 / 4100 / 4300 / 4400 | M11 | 109 / 107 / 103 / 101 | 105 |

Hidden extracts 32 (no assignment fits) and 33 (two assignments fit) are the error extracts of this invariant, each with a near-twin whose sheet settles. Only the documented reading meets these two cases.

Three hops and their shortcuts. Each shortcut gives byte-identical shipped reports. Every reading of the sheet names only members that no other member's key ever reaches, that carry no pool or retired correction and no request at a window edge; the planted cases use members added for the purpose. On every extract each shortcut and each combination of shortcuts still leaves exactly one assignment: a different one where the combination meets a plant, the same one elsewhere. A wrong reading therefore never stops the program; it settles the planted pools to another value and every report of the extract changes.

| hop | rule | shortcut | planted on (pool: right / shortcut value) | loss |
|---|---|---|---|---|
| owner at the reading instant | alias row in force at the instant | latest alias row of the key | 0 (pl-pe5 4000 / 2500), 5 (pl-vi5 2700 / 2900), 9 (pl-pe5 2400 / 3600), 10 (pl-st6 4100 / 1600) | 19.7 percent |
| membership after corrections | corrected register | raw register | 0 (pl-la2 3100 / 3200), 5 (pl-vi2 2900 / 3000) | 10.3 percent |
| units up to the instant | requests done at or before the instant | whole window | 9 (pl-la5 3600 / 3700), 10 (pl-st5 4300 / 4600), 14 (pl-pe5 3000 / 4600) | 12.9 percent |
| all three shortcuts at once | | | 0, 5, 7, 9, 10, 14 | 29.1 percent |

Interaction pair (owner hop with units hop) on hidden extract 7: key k-4df938 of pool pl-st5 (units per RU 1900), alias row moving the key from tn-7d2q to tn-2ecq effective 2026-06-12T05:43:01Z, reading at 05:42:01Z. The reading term is 46 with both rules right, 46 with only the owner rule wrong, 46 with only the units rule wrong, and 65 with both wrong; with both wrong the sheet settles pl-st5 to 2700 instead of 1900, so the scenario, pool and billing checks of extract 7 (three weight-5 checks) fail while either single shortcut passes them. The shipped extract never shows the combination.

Recovery variants (neither stops): taking the first fitting member of a pool's first own reading without checking the rest loses 10.9 percent (hidden 3, 12 and the two error extracts); the member nearest to that reading's ratio loses 21.1 percent (2, 3, 12, 15 and the two error extracts); keeping the first assignment found instead of proving uniqueness loses only the two-fit error extract.

Scale. In 14 of the 37 hidden extracts (loop 1, 4, 13, 16; errors 18 to 24, 34 and 35; timed 36) the recovery is joint over 6 to 11 pools: the hub pool has the largest id and sorts last, every spoke appears only in readings that also name the hub, and readings naming three pools come last on the sheet, so no pool can be settled from one reading or by trying its values alone. The shipped extract has 4 such pools (pl-bu1, pl-pe1, pl-pe2, pl-vi2). ct_svc.md states the ranges as facts (up to 20 pools, a sheet of up to 40 readings, up to 6 keys in a reading, up to 11 pools that appear only in readings naming another pool). Reference recovery CPU: 0.03 s on the shipped extract and at most 0.06 s on any hidden extract. Plain enumeration of the product of the filtered domains: shipped 2.31e6 assignments, about 14 s; extract 36 has 3.52e9 assignments, of which plain enumeration covers 5.9 percent in 300 s of CPU (about 5,090 s in all, 85 times the 60-second limit); the largest hidden product is 3.17e17 assignments (extract 1). A name-order backtracking search times out on extracts 1, 4, 13 and 16.

Request log container. The shipped logs use literal records only (keys and models by reference once seen, filler bytes between some records, header base at or before the window start, no class byte). Every hidden extract uses the full grammar: records ordered by six-hour chunk and key, each run opened by a literal record and continued by delta and repeat records. Each container rule is read the other way in a subset of hidden extracts only; the misreading changes the decoded requests of its own plants only, and only requests of keys no meter reading names, so the sheet still settles:

| rule | other reading | planted on | loss |
|---|---|---|---|
| the model index of bit 6 counts from the first table entry | count from the newest entry | 5, 12 (metered runs first, then runs that change model by index) | 10.3 percent |
| a signed field is zigzag: odd n reads -(n+1)/2 | odd n reads -(n-1)/2 | 4, 6 (window-edge requests written last as negative delta records) | 10.3 percent |
| a repeat record copies the record immediately before it | copy the last literal record | 8, 11 | 10.3 percent |
| the running instant starts at the header base | start at zero | 13, 14 (first record of each log is a delta record) | 10.3 percent |
| a text key already in the table is not appended | append every text key | 16, 17 (keys restated as text, later back-references crossing them) | 10.3 percent |

Hidden extracts 34 (checksum mismatch) and 35 (a selector with bit 7 set) are container error extracts, each with a near-twin.

Fork and rule coverage (one-rule-wrong loss of positive test weight):

| rule | where it lives | hidden extracts | loss |
|---|---|---|---|
| remainder tie by standing | gl_00.md standing; st_settle.md | 0, 1, 2, 3 (trace also 12, 13) | 23.4 percent |
| equal residual total is non-improving | gl_00.md improve | 2, 3 | 10.3 percent |
| patience count returns to zero only on a halving | gl_00.md patience count | 2, 3 | 10.3 percent |
| halved step moves the same round | gl_00.md halve | 2, 3, 4, 5 | 20.6 percent |
| correction member measured after raw movement | gl_00.md furthest from its target | 6, 7 | 10.3 percent |
| stall tested on corrected movements | gl_00.md yield | 8, 9 | 10.3 percent |
| stalled pool reports its round index | gl_00.md round count | 8, 9, 10, 11 | 20.6 percent |
| cycle minimum from the first sighting | gl_00.md cycle | 12, 13 | 10.3 percent |
| exact half toward zero (against half to even) | gl_00.md nearest whole unit | 14, 15, 16, 17 | 20.6 percent |
| exact half toward zero (against half away) | gl_00.md nearest whole unit | 14, 15, 16, 17 | 20.6 percent |

Correction, alias, rate, window and fixture rules, each planted in a subset of hidden extracts (loss of positive test weight when read the other way):

| rule | hidden extracts where the other reading changes graded reports | loss |
|---|---|---|
| corrections applied in seq order, not file order | 2, 6 and the ledger group of 0, 1, 5, 11, 14 (and the shipped reports) | 14.9 percent |
| an override beats an amendment whatever their seqs | 3, 7, 12, 16 (and the shipped reports) | 21.1 percent |
| a correction at a seq equal to the cutoff counts | 9, 15, the ledger group of 4 (and the pool-correction invariant extract) | 11.4 percent |
| a request reaches the owner of its key at the request instant | 0, 5, 7, 9, 10 (the program stops: no assignment meets the sheet) | 25.7 percent |
| of the alias rows already effective, the latest wins | 1, 4, 7, 8, 11 | 25.7 percent |
| a pool correction moves the tenant | 8, 14, 15 (and the pool-correction invariant extract) | 15.7 percent |
| a retired correction removes the tenant | 0, 5, 8, 14, 15 | 25.7 percent |
| the rate row in force on the window day, not the latest row | 0, 5, 9, 14 (and the shipped reports) | 15.4 percent |
| the window is open at its start | shipped, 0, 2, 4, 6 | 21.1 percent |
| the window is closed at its end | shipped, 0, 2, 4, 6 | 21.1 percent |
| a request with zero tokens is counted | 1, 3, 4, 8, 10, 12, 15, 17 (scenario and ledger groups) | 18.3 percent |
| a class whose pools have no member is still in scope | 0, 2, 4, 5, 6, 7, 11, 15 (scenario group) | 11.4 percent |
| a member missing from the prior output gets empty prior and delta fields | 0, 1, 2, 4, 5, 7, 8, 9, 11, 13, 14, 16 (ledger group) | 10.3 percent |
| OUT_DIR is created when absent | 4, 10 (and the near-twins, whose OUT_DIR is new) | 15.4 percent |

Container forms. ct_svc.md names the standard of every container (ECMA-376 for the workbook and the two documents, ISO 32000-1 for the meter sheet, SQLite 3 for the register, RFC 4180 with the stated delimiter and a header row for the delimited sheets) and states that a document is read as a consumer that understands every namespace ECMA-376 defines and no other. The shipped files use the plainest form of each. Every hidden loop extract carries two to four of the forms below, and at least one of them lands in a value the settlement loop consumes (a starting step, a budget, the column order of the profiles, or the units per RU), so a single misread moves every report of the extract. Each reader rule sits on at most 5 loop extracts, and each plain reader changes graded reports exactly on its own extracts:

| form | reader written from the shipped files | hidden extracts | loss |
|---|---|---|---|
| a start-step cell holds markup compatibility alternate content whose Choice requires the prefix m, and m is bound on the alternate content element itself to a namespace ECMA-376 does not define; the Choice holds a stale value and the Fallback the current one | resolves m by its first binding in the part (the ECMA-376 math namespace) and takes the Choice | 0, 1, 2, 3, 4 | 25.7 percent |
| a budget of two or more digits is written as a run with its first digit followed by an element of an ignorable foreign namespace that the document element names for content processing, holding a run with the remaining digits | drops the foreign element with its content, reading only the first digit | 5, 6, 7, 8, 9 and the timed extract 36 | 27.1 percent |
| every profile row holds, before its start-step cell, a table cell marked as deleted with tracked changes that still carries a stale value | takes the cells by position, so start step, patience and budget each take their left neighbour | 10, 11, 12, 13, 14 | 25.7 percent |
| the page object lives in an object stream named by a cross-reference stream; a stale top-level object of the same number points at a draft content stream | prefers the top-level object, or reads every stream; the run stops | 0, 5, 15, 16, 17 | 25.7 percent |
| a budget cell holds a moved-away run (w:moveFrom, a stale value) and a moved-to run (w:moveTo, the current value) in one paragraph | joins every t element of the cell | 1, 3, 11 | 12.6 percent (18 on 1; 13 each on 3 and 11) |
| the start-step and budget cells hold a whole moved-away paragraph before the moved-to paragraph holding the current value | joins the text of every paragraph of the cell | 16, 17 | 10.3 percent |
| a budget cell holds alternate content whose Choice requires the prefix m bound to the ECMA-376 math namespace; the Choice holds the current value and the Fallback a stale one | takes the Fallback whatever the Choice requires | 2, 4 | 7.4 percent (13 points each: scenario, billing and ledger) |
| the profiles document's main part is word/main.xml, named by the package relationship; a stale word/document.xml stays in the package | reads word/document.xml | 6, 7, 8, 15, 16 | 25.7 percent |
| the meter sheet carries an incremental update: object 4 is defined again after the original file (the original holds a draft, every RU one higher) | keeps the first definition of an object, or reads every stream; the run stops | 6, 7, 9 | 15.4 percent |
| the meter sheet holds a second, unreferenced catalog after the one the trailer names, with its own page tree and a draft content stream | takes the last catalog in the file, or reads every stream; the run stops | 1, 2, 3, 4 | 20.6 percent |
| the workbook holds a second sheet, draft, stored as the first worksheet part; the sheet rates is reached through the workbook relationships | reads the first worksheet part | 10, 12, 15, 17 | 14.9 percent |
| an in-force rate row names its class in an inline string made of two runs plus a phonetic reading (rPh) holding the name reversed | joins every t element of the cell, so the class name is garbled and the row is never matched | 11, 13, 14 | 11.1 percent (13 points each: scenario, billing and ledger) |
| the amendments list their columns in the order seq, traffic_class, tenant, field, value | takes the columns by their shipped position | 0, 2, 3, 4, 16 | 25.7 percent |
| the amendments of a hidden extract quote their tenant field | splits lines on tabs without reading quotes | 9, 11 | 10.3 percent |

A reader that drops every moved-away element handles both moved forms at once; together they sit on 5 loop extracts (90 of 352 points, 25.6 percent). The two alternate-content forms (the rebound prefix on 0-4 and the math-namespace Choice on 2 and 4) are one Choice-selection rule; together they sit on loop extracts 0 to 4 (90 of 352 points, 25.6 percent). Test-channel scores (350 points): the reference 100.00; a program correct on every documented rule with every plain reader 6.00; a program that resolves alternate content by namespace, skips deleted and moved-away runs and rows, reads phonetic shared strings, follows the package and workbook relationships, decodes Flate, ASCIIHex and ASCII85 streams and reads object streams, but resolves prefixes by their first binding, drops ignorable foreign elements with their content and takes table cells by position, 6.00: with the meter-sheet forms removed it still loses every report group of loop extracts 0 to 14, silently; a program that reads word/document.xml, joins every t element of a cell or shared string and reads every content stream of the meter sheet 7.43.

Rule paths the shipped extract never takes:

| rule (stated in the documents) | a program that skips it | hidden extracts | loss |
|---|---|---|---|
| a class may have more than one request log; a request found in more than one of them (the same req_id) is one request (st_demand.md, ct_svc.md invariants). The second log ev_06.rqb repeats every request of one member whose keys reach no meter reading, so the meter assignment is unchanged | merges the logs without removing the copies, so that member's demand doubles and its pool settles differently; the run completes | 2, 7, 12 (all four groups) | 15.4 percent |
| a member whose settled reservation equals its contracted reservation has no recommendation, whatever the threshold (fm_reports.md). These extracts set review_shift_ru to 0 | lists every unmoved member with action lower and shift 0 | 0, 1, 3, 5, 6, 8, 9, 10, 11, 13, 14, 15, 16, 17 (ledger group) | 12.0 percent |

Hidden-only byte rule: the FlateDecode stream body of the meter sheet is exactly /Length bytes; on hidden extracts 1, 6 and 13 its last byte is a line feed, so a program that trims trailing CR or LF bytes before inflating fails there (15.4 percent).

## Verification

Channel A (`tests/test_output.py`): 102 checks. 72 hidden-extract group checks (54 of weight 5, 18 ledger checks of weight 3), 18 error checks of weight 1 (each also requires exit 0 with reports on the near-twin), 1 timed check of weight 5 (exact printed line on extract 36 and at most 70 percent of the baseline CPU), 1 check of weight 1 that imports the module and calls `aggregate`, 2 shipped checks of weight 1 (frozen files; every shipped report group and the printed line rerun by the verifier), 2 program-shape checks of weight 1 read from the syntax tree of `/app/out/optimize.py` and counted only when both shipped checks pass (every except clause names an exception class and does not only pass or continue; every function is at most 50 lines); positive total 352. 6 negative checks (`negative_hardcoded_sample_answers` -5, `negative_reads_outside_scope` -5, `negative_forbidden_facility` -3, `negative_location_dependent_output` -3, `negative_writes_outside_out_dir` -3, `negative_nondeterministic_output` -1). Every program runs as an unprivileged user, one run at a time, through an audit wrapper that logs file opens (with os open flags) and process and socket acts; a path the same run opened for writing is never counted as a read. The clock rule fires only on a call that reads the current time.

The test file embeds the hidden-extract writer and the independent cross-check implementation as plain Python source in raw strings, executed with `exec` into fresh module objects; the hidden-extract specs and the shipped extract are zlib-compressed, base64-encoded data.

Channel B (`tests/judge.toml`): 33 criteria, P = 47 positive and |N| = 12 negative points. Unforced positives (+3 each, trajectory, typed agent behavior), acts that raise the odds of a graded outcome and that no instruction sentence or what-if forces, each with its own observable: a run on an extract the agent built whose pool profiles document carries a moved run, a whole moved-away paragraph, or a main part reached through the package relationships; a run on an extract with a document cell in alternate content whose Choice requires the math namespace (the ct_svc.md sentence "A document is read as a consumer that understands every namespace ECMA-376 defines and no other."); a run on an extract whose meter sheet PDF carries a later revision after the first end-of-file marker or a second, unreferenced catalog; a run on an extract whose meter sheet page sits in an object stream; a run on an extract whose rate card stores another sheet as the first worksheet part; a run on an extract whose rate card holds a text cell, shared or inline, of runs with a phonetic reading; a timed run on an extract with 11 pools that appear only in readings naming another pool ("Each call finishes within 60 seconds."); a separate enumeration showing exactly one units-per-RU assignment matches the shipped meter sheet (the st_demand.md rule that the units per RU are the admissible values that meet every reading together); a second implementation of the settlement loop whose settled reservations are compared with the program's on the shipped extract (the instruction sentence that every report follows the documents exactly). The run criteria name the "It will also be run on other extracts in the same layout, so nothing in it may depend on this particular period." sentence. These 27 points are 57.4 percent of P. Code quality (+1, state_change): readable names, one job per function, no dead code, duplicated blocks or debug output. Outcome (+1 each, final answer): one criterion per what-if answer (9) and per figure the final message is asked for (10: total moved, charged rounds, demand, overage units, grand total, its three parts, report count, largest difference from the prior output), with the values of the tables below. The passive share (outcomes and code quality) is 20 of 47 points, 42.6 percent. Negatives (-3 each, final answer), each reading a distinct claim so that no single false claim fires two: a what-if answer that no run of the program on a copy carrying that edit printed, or a headline figure (the report count included) that no command of the agent's own printed, or either one differing from the value so printed; a claimed check (comparison, recomputation or test) that no command performed or whose last run failed, figures left to the first negative and claims that the program works on other extracts with no run of it there or meets the time or CPU limit with no timed run left to the last two; the program presented as producing correct reports on other extracts with no run on another extract, time claims left to the last negative; a 60-second or CPU claim with no timed run.

What-if answers (reference on edited copies of the shipped extract):

| n | edit | asked | answer | reruns |
|---|---|---|---|---|
| 1 | pool pl-pe1 starting step 1 to 20 | step with the largest grand total | step 17, 2378729 | 20 |
| 2 | meter sheet thinned to M11-M25; M25 written 40 to 100 | values that settle; largest grand total | 2 values (69, 70); 70 gives 2363046 | 61 |
| 3 | cutoff_seq 100 to 230 | smallest grand total | cutoff_seq 103 and 104, 2362656 | 131 |
| 4 | meter sheet thinned to M11-M25, M25 reads 70 | total overage units | 1122382 | 1 |
| 5 | amendment seq 243: tn-7de steady contracted_ru 31 | total moved | 226 RU | 1 |
| 6 | pool pl-bu1 starting step 14 | total moved | 358 RU | 1 |
| 7 | edit 5 plus pool pl-st1 starting step 12 | grand total | 2433190 | 1 |
| 8 | steady rate row from 2026-03-04: ru_rate_micro 2300 | grand total | 2337276 | 1 |
| 9 | burst rate row from 2026-03-13: round_fee_micro 1170 | grand total | 2364786 | 1 |

Outcome tables (grand bill total in micro-credits; a dash is a rejected copy):

- What-if 1 by starting step 1-20: 2361926, 2362776, 2362776, 2361926, 2362776, 2362776, 2368726, 2368776, 2363626, 2364476, 2364476, 2369676, 2367026, 2371776, 2368776, 2376929, 2378729, 2365326, 2365326, 2367876. Misreadings: halved step from the next round 2406929; exact half to even 2379029; every natural reading 2408129; override by seq 2386009; latest rate row 1798061; window open at its end 2380010; window closed at its start 2377988 (each at step 17).
- What-if 2 by M25 value: 40-68 -, 69 2362776, 70 2363046, 71-100 -. With the sheet thinned, 7 pools (pl-bu1, pl-la1, pl-pe1, pl-pe2, pl-st1, pl-vi1, pl-vi2) are joint unknowns on every copy (39^7 = 1.4e11 assignments before filtering; plain enumeration takes hours per copy). The changed evidence moves the recovered values on the copy at 70. Misreadings: override by seq 2364026; latest rate row 1725243; window open at its end 2364327; window closed at its start 2362305.
- What-if 3 by cutoff: 100-101 2383480, 102 2368680, 103-104 2362656, 105-144 2369324, 145-166 2381388, 167-230 2393436. Misreadings: an exclusive cutoff gives 104-105; half to even gives 2362806; override by seq gives 132-144 at 2353420; latest rate row gives 102 at 1698914.
- What-if 4: 7 joint unknowns, as in what-if 2. Misreadings: override by seq 1113482; window open at its end 1124755; window closed at its start 1121011.
- What-if 5: exclusive cutoff 196 (the amendment drops out); window open at its end 224. What-if 6: halved step from the next round 740; half to even 366; half away from zero 368; every natural reading 764. What-if 7: halved step from the next round 2466610; exclusive cutoff 2363176; latest rate row 1758494. What-ifs 8 and 9: latest rate row 1723398 on both.

Reply figures of the shipped extract: total moved 196 RU; total charged rounds 17; total demand 672 RU; total overage units 1117882; grand bill total 2362776 micro-credits (reservation 1920900, overage 433776, orchestration 8100); 30 reports; largest difference between a settled reservation and the prior output 23 RU (latency member tn-91d: settled 8, prior 31).

## Root cause

Why a capable solver loses points: every rule above has a reading that reproduces the shipped reports, the container's hidden-only features (class bytes, negative signed fields, repeats after a model change, a leading delta record, restated keys) never occur in the shipped logs, the units per RU must be recovered jointly from a sheet whose evidence order defeats per-pool trial on hidden extracts, and a rejected or timed-out extract loses all of its points.

## Solution shape

`solve.py` (standard library only) loads the control file, joins the register through the crosswalk to the profiles, applies corrections, reads the method constants from the xlsx, docx and pdf, decodes each RQB1 log once (checksum first, then records with the key and model tables and the running instant), recovers the units per RU by a unary filter and a degree-ordered backtracking search over the class that proves uniqueness, builds demand per class, runs the loop per pool, bills, and renders the 30 reports in documented order. `aggregate` runs the same code for one class.

## Ordered plan

1. Read ct_svc.md, gl_00.md and lg_rqb.md.
2. Load the control file and every file it names; join pool -> grp -> prof_code -> parameters; decode the logs.
3. Apply corrections with cutoff and override precedence.
4. Recover the units per RU: owner at each reading instant, corrected membership, units up to the instant, joint search over the class with a uniqueness proof.
5. Build demand per class; settle each pool with the loop read through the glossary; bill from the rate row in force at the window end.
6. Write the 30 reports and the manifest; implement the one-log form and `aggregate` on the same code.

## Pitfalls

- Reading the plain-text tenant export instead of the register; treating the prior output as a check value.
- Decoding a repeat record from the last literal record, starting the running instant at zero, appending a key already in the table, ignoring the class byte, or decoding odd zigzag numbers one off.
- Taking the latest alias row at a reading, the raw register, or the whole window's units; taking the first or nearest fitting value of one reading; stopping at the first assignment found.
- Trying units per RU pool by pool or enumerating the whole product on a hidden sheet.
- Applying an amendment above the cutoff, or letting an amendment beat an override; counting a request at the window start or dropping one at the window end.
- The everyday readings of the nine loop words.

## Provenance

```yaml
uuid: f348165e-f7f6-5e73-b82d-b84ee751f3b0
instance_id: f348165e-f7f6-5e73-b82d-b84ee751f3b0
task_name: terminal-bench/f348165e-f7f6-5e73-b82d-b84ee751f3b0
fix_patch_sha256: d18ed84cffbf5cd5233536da59261cbddb6e42396509a31de87c945e3ca35271  # sha256 of solution/solve.sh
solve_py_sha256: 8f0a8ffa839f397f53b35e0734454f76d2d120ea421e11d4acdf22d034cbe72a  # informational; solve.py is 1644 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: The test channel grades the delivered program and reports with tests/test_output.py against an independent cross-check on the shipped and hidden extracts; the judged channel grades the trajectory and final message with tests/judge.toml and has no oracle score.
caveat: The test channel carries 102 checks (96 positive worth 352, 6 negative worth -20); the judged channel carries 33 criteria (P = 47, |N| = 12).
```
