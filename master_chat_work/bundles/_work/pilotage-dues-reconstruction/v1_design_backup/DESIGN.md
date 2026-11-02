# DESIGN 44635de pilotage-dues-reconstruction (domain-calculation, data-science, Shape D, seed 482617)

## 1. Story and spine
A port's four pilot stations (North, South, West, East) lost their tariff tables. A circular fixes the
due formula and a short closed list of allowed values for each of four coefficients. A quarter of paid
invoices (one file per station, four formats) is the evidence; a batch of disputed invoices must be
judged against the recovered tariff. Window 2026-07-01 00:00 to 2026-09-30 23:59, port local time.

Spine stages:
1. Load: movements log (BOARD/RELEASE pairs), vessel register, holidays, notices, paid files, disputed batch.
2. Reject records per the data-quality rules; record each in data_quality.json.
3. Periods: per station, one period, or two split at the notice date (boarding instant decides).
4. Fit: per station and period, every combination of the closed lists that reproduces every accepted
   paid invoice to the cent; exactly one = resolved, zero or two-plus = unresolved with stated reason.
5. Recompute each accepted disputed invoice with its station-period tariff and the exemption rule;
   verdict.
6. Aggregate: policy_audit (row per disputed invoice), regions, segments, summary.
COUPLING sentence (tariff_circular.md, section "Verdicts"): "Every recomputed due and every verdict uses
the tariff recovered for that station and period, or the station's unresolved status."

## 2. Input files (13 files, 8 formats; /app/docs fixed rules, /app/data per corpus)
| file | format | rows (shipped) | depends on |
|---|---|---|---|
| docs/rule_register.md | md | ~40 | names every governing file and section (W10) |
| docs/tariff_circular.md | md | ~150 | formula, closed lists, fit rule, periods, verdicts, column layout of paid_west.txt |
| docs/exemption_policy.md | md | ~40 | segment, certificate expiry, pro-rata |
| docs/output_contract.md | md | ~120 | every output key, value form, ordering, codes and reason strings (DS-25) |
| data/pilot_movements.log | log | ~22,500 | BOARD line: time, station, visit, vessel, draft_dm, tugs; RELEASE line: time, visit; NOTE noise lines |
| data/vessel_register.tsv | tsv | ~2,100 | vessel id, name, gross tonnage, segment, exemption expiry or `-` |
| data/holidays.json | json | ~30 | station -> list of dates |
| data/station_notices.md | md | ~15 | table station, notice date (0 or 1 per station) |
| data/paid_north.csv | csv | ~2,250 | invoice_id, visit_id, invoice_date, amount |
| data/paid_south.jsonl | jsonl | ~2,250 | same fields |
| data/paid_west.txt | fixed width | ~2,250 | same fields, columns per circular table |
| data/paid_east.xml | xml | ~2,250 | one `<invoice .../>` element per line |
| data/disputed_batch.csv | csv | ~2,100 | invoice_id, visit_id, station, invoice_date, billed |
Total ~36,000 lines; every csv/tsv/jsonl/txt/log file >= 2,000 lines (A5).

Chains (length >= 4):
- C1 disputed row -> log BOARD/RELEASE -> register (GT, segment, expiry) -> exemption_policy pro-rata -> recomputed due -> verdict -> segment file.
- C2 paid record -> log boarding instant -> station_notices period -> circular closed lists (fit) -> region file -> summary.
- C3 log BOARD station and instant -> holidays.json station calendar -> surcharge line -> fit -> verdict.

## 3. Rules (25 stated; 3 sharp levers, the rest plain and firing on shipped)
Formula (tariff_circular.md "Due"): L1 tonnage = B x GT / 100; L2 draft = D x max(0, draft_dm - 60);
L3 towage = T x tugs; L4 surcharge = (N - 1) x (L1 + L2 + L3) when boarding is in [22:00, 06:00) or on
a holiday of that station, else 0. Each line rounded half-even to the cent; due = sum of lines.
Closed lists: B base_per_100gt {1.80, 1.95, 2.10, 2.25, 2.40}; D draft_per_dm {2.50, 3.00, 3.50, 4.00};
N night_factor {1.25, 1.40, 1.50}; T per_tug {35.00, 50.00, 65.00} (180 combinations, no size hint).

Plain rules (fire on shipped, self-correcting there): R1 local minute times and window; R2 visit = BOARD
plus RELEASE pair, on-board minutes; R3 GT/segment/expiry from register; R4-R6 lines; R7 night window by
boarding; R8 holiday by boarding date and station; R9 one surcharge even if night and holiday; R10
half-even per line; R11 closed lists; R13 reason strings; R15 at most one notice per station, first
period starts at window start; R16 segment; R18 verdict names; R19 difference, refund and shortfall
totals; R20 malformed_record; R21 duplicate_invoice (every copy of a repeated invoice_id rejected); R22 unknown_visit; R23 station_mismatch; R24 money strings with 2 decimals, list
orderings; R25 a missing or unparseable declared file stops the run, non-zero exit, message naming it.

### LV-1 R-FIT unique fit (governing: tariff_circular.md "Recovering a tariff" + "Verdicts")
Text: "A station's tariff for a period is the combination of listed values that reproduces every accepted
paid invoice of that station and period to the cent." Verdict enumeration, one clause: "`cannot_recompute`:
the station and period has no such combination, or has more than one." Reasons (output_contract, word
for word, circular Verdicts only): `no listed tariff reproduces every paid invoice`, `more than one listed
tariff reproduces every paid invoice`. No worked example (master change 2).
Reflex: first fit (H8). Hidden (master change 1), every corpus, asserted per seed: station Z one period
with exactly 2 fits (every paid visit with tugs or excess draft has excess_dm = 15 x tugs, so (D, T) and
(D + 1.00, T - 15.00) tie); station Y before-notice period with 3+ fits (one coefficient unexercised by its
paid invoices, seed-varied T, N or D); each multi-fit period has accepted disputed rows (first fit gives
a numeric verdict, rule gives cannot_recompute); station W 0 fits (some paid billed at draft rate 3.25).
Shipped: 5 station-periods, each exactly 1 fit (UNIQUENESS.md lists counts). Interaction: unresolved
status flows to verdicts, regions, segments, summary.

### LV-2 R-CHANGE notice date (governing: tariff_circular.md "Periods"; data in station_notices.md)
Text: definitions section: "A visit's instant is its boarding instant; every date rule in this circular
reads the boarding instant." Periods: "A notice starts a new period at 00:00 on its notice date; the
tariff before and the tariff from that instant are recovered separately." No worked example.
Reflex: period by invoice_date (it sits on every paid and disputed record), or strict `>` notice date,
or release instant. Hidden: notice station has visits boarding on the notice day, visits boarding 1-5
days before and invoiced on or after it, visits boarding 23:xx the eve and released after 00:00.
Shipped: one notice (North 2026-08-17); no North BOARD from 08-11 00:00 through 08-17 23:59.

### LV-3 R-EXEMPT partial visit (governing: exemption_policy.md)
Text: "A certificate covers on-board time before 00:00 on its expiry date. A visit is billed for its
on-board minutes from that instant; when only part of a visit is billed, each rounded line is multiplied
by billed minutes over on-board minutes and rounded half-even to the cent again." Visits wholly before:
due 0.00 (no paid invoice exists; a disputed one is overbilled). No worked example. Full determinate
text in section 10.
Reflex: all or nothing by boarding, expiry day inclusive ("valid until"), pro-rata of the total. Hidden
(own RNG stream): public certificate holders with visits across expiry midnight (paid and disputed),
wholly on the expiry day, ending before it. Shipped: no public visit on board in [expiry-1 12:00,
expiry+1 00:00). Interaction: a wrong reading changes paid predictions, so a fit is lost (cascade).

## 4. Outputs (all keys, value forms, codes, reasons and orderings written in output_contract.md)
- summary.json: disputes, verdict_counts{4}, refund_total, shortfall_total, unresolved[{station,
  period_start, reason}], resolved_periods.
- policy_audit.json: rows sorted by invoice_id: invoice_id, visit_id, station, period_start, segment,
  billed, recomputed|null, difference|null, verdict, reason|null, onboard_minutes, billed_minutes.
- data_quality.json: rejected[{file, line, code}] sorted by file then line; counts{4 codes}.
- region_<S>.json: station, periods[{period_start, status, reason|null, tariff{4}|null, paid_invoices}],
  verdict_counts, refund_total, shortfall_total.
- segment_<s>.json: segment, disputes, verdict_counts, billed_total, recomputed_total, refund_total,
  shortfall_total, exempt_minutes.

## 5. Rejection paths
Record level (data_quality.json, run continues): malformed_record, duplicate_invoice, unknown_visit,
station_mismatch. File level (run stops, exit non-zero, stderr names the file): any declared data file
missing or not parseable as its format (holidays.json invalid JSON, register header missing).

## 6. Test plan (tests/test_output.py; rewardkit; weights 5/3/1)
Invocation (G8a, stated): `python3 /app/out/derive_report.py --data <dir> --out <dir>`.
Hidden tier (G8): generator embedded in tests/, base RNG per seed, rare fixtures (LV-2, LV-3 plants) on
`random.Random(seed * 7919 + 17)`; runs as uid 1000 from a foreign cwd, data copied to /tmp.
| id | what | weight | count |
|---|---|---|---|
| shipped_outputs_exist | 10 files present, JSON parses | 1 | 1 |
| shipped_summary / shipped_audit | whole doc vs reference on /app/data | 3 / 3 | 2 |
| shipped_regions / shipped_segments / shipped_quality | whole docs | 1 each | 3 |
| hidden_<k>_summary, _audit (k=1..4) | whole doc exact | 5 each | 8 |
| hidden_<k>_regions, _segments | 4 or 2 files whole | 3 each | 8 |
| hidden_<k>_quality | whole doc | 1 | 4 |
| mutation_relocated (H1 copy, new data and out path, foreign cwd) | exact, only if H1 plain exact | 3 | 1 |
| mutation_shuffled (H1 rows shuffled within every file, same answer) | exact, only if H1 plain exact | 3 | 1 |
| mutation_missing_source (H1 minus vessel_register.tsv) | non-zero exit, stderr names file, only if H1 exact | 3 | 1 |
| negative_reads_tests | program text references /tests | -5 | 1 |
| negative_hardcoded_sample_answers | program text holds shipped answer figures (validator 7.4) | -3 | 1 |
Positive 87; hidden + mutation 77 (88.5%, G3 >= 70). 31 checks (A3). Per-row ownership (G1a): every
audit row belongs to exactly one audit test per corpus; a test whose doc set is empty fails. Each test
prints the first differing JSON path (G7). Every hidden seed asserted to fire all three branches and to
stay in stated bounds (G12, 300 seeds).

## 7. Judge plan (tests/judge.toml, batched; 16 criteria)
Probes, w3, important, process, trajectory: P1 P-g prints count of fitting combinations per station and
period; P2 P-a two-fit corpus run; P3 P-a no-fit corpus run; P4 P-b one disputed invoice line by line;
P5 P-c summary refund_total re-added from policy_audit outside the program; P6 P-d altered copy rerun
and the changed field shown; P7 P-a notice-day and eve-boarding visits and their periods; P8 P-a visit
across expiry midnight and its billed minutes; P9 P-e relocated rerun. 27/39 = 69% of positive judge.
J4 w3; J6a final reply lists every station-period with its four coefficients or reason (w3); J6b lists
every underbilled disputed invoice by id (w3); J10 order: runs the stated invocation after its last edit
(w3); J10 workdir w-1; J3a -3, J3b -5, J3c -3. Positive 39, negative 12. solve.sh self-check prints
`check P<n> ok` and one witness line per probe.

## 8. Expected loss per lever (tests channel, of 87; to be measured in COST_TABLE)
Each lever fires on every hidden corpus and changes summary, audit, regions and segments there:
16 x 4 = 64 plus 9 mutation = 73 (84%). One-fact-wrong (one audit row): 16 of 87 (18%).
All-but-one predicted final = (16 + judge mid 37) / 2 = 26.5 < 70.

## 9. Per lever, hidden input and check a careful solver loses
- LV-1: hidden_k_summary (unresolved list), _audit (cannot_recompute rows), _regions (status), _segments.
- LV-2: notice station: invoice-date or strict reading leaves the after period with no fit.
- LV-3: across-midnight and expiry-day visits: paid invoice no longer reproduces at that station.

## 10. Master changes (go, 26 Oct 18:15)
1. LV-1 weight: hidden corpus station roles (shuffled per seed): X notice, both periods resolved, LV-2 and
   LV-3 plants; Y notice, before period 3+ fits, after period resolved with LV-3 plants; Z no notice,
   exactly 2 fits; W no notice, 0 fits. Generator counts fits by brute force and rejects the seed unless
   counts are (X1 1, X2 1, Y1 >= 3, Y2 1, Z 2, W 0) and each multi-fit period has >= 1 accepted disputed
   row. COST_TABLE reports the first-fit program's loss with the W plant replaced by a resolved period.
2. Toy examples only for plain rules (formula lines and half-even); none for fit counts, notice days or
   expiry midnight. BRANCH_FIRE: each lever's hard branch 0 on shipped, >= 2 per hidden corpus.
3. Exempt time, determinate (exemption_policy.md): on-board minutes = whole minutes from boarding to
   release; billed minutes = on-board minutes at or after 00:00 on the expiry date (all of them for a
   commercial vessel or a public vessel boarding on or after that instant; none for a visit released at
   or before it). Lines: L1 = half-even(B x GT / 100), L2 = half-even(D x excess), L3 = half-even(T x tugs),
   L4 = half-even((N - 1) x (L1 + L2 + L3)) when the surcharge applies else 0.00. Partial visit: each of
   L1..L4 (already rounded) x billed / on-board, half-even again; due = sum. The tariff is always the one
   of the period holding the boarding instant, even when billed minutes start in a later period.
4. `cannot_recompute`, its two conditions and both reason strings appear once, in tariff_circular.md
   section Verdicts. output_contract.md refers to "the verdict names of tariff_circular.md section
   Verdicts" and never restates them. No sentence anywhere says a period may be ambiguous.
5. instruction.md: job, paths, invocation, exactness, rerun promise; no counts, no limits, no lists.
6. Phase 0b prototype carries all plants on 3 hidden seeds.
Duplicate rule made order-free (shuffle mutation): an invoice_id seen more than once in the paid files,
or more than once in disputed_batch.csv, has every copy rejected as duplicate_invoice. Mutation_shuffled
compares summary, audit, regions and segments (data_quality holds line numbers).

## 11. Redesign v2 after the design-stage blind read (26 Oct 21:20)
Blind result (DESIGN_BLIND.md): 9/9 documents exact, 0 audit rows differing, on shipped and seeds
1101-1106. All three levers were sentences Opus transliterated: LV-1 verdict clause names the count test,
LV-2 carried a directive ("Every date rule in this circular reads the boarding instant"), LV-3 was a
procedural formula beside the due. v2 keeps Shape D (3 sharp rules), the COUPLING sentence, the outputs,
31 checks and the 16-criterion judge, and moves each lever to a form the blind program did not read:
a rule keyed in a different file from the field it reads (LEVER_RULES :102), joint recovery across
periods (interacting levers, :104) and a stateful allowance keyed wider than the visit (:101).

### LV-1 R-FIT v2 (S3, joint candidate space)
Circular section 5, definition with a branch: "A station's tariff gives each coefficient one listed
value in each of its periods, and reproduces every accepted paid invoice of the station, each with the
values of its own period, to the cent." The verdict clause stays word for word, once, in section 6:
"`cannot_recompute`: the station and period has no such combination, or has more than one." A period's
combination is its four values inside a station tariff. Reflexes: first fit (H8); per-period fit that
ignores the notice file (the v1 and blind structure). Hidden (every corpus, roles shuffled by
`rng.sample`, Z no longer biased): Y-before has >= 3 fits alone and 1 jointly; Y-after has >= 3 fits
jointly (its free coefficient is named by the notice and unexercised after); Z has no notice and exactly
2 fits; W has 1 fit per period alone and 0 jointly. Generator asserts (X1 1, X2 1, Y1 alone >= 3 and
joint 1, Y2 joint >= 3, Z 2, W1 and W2 alone 1 and joint 0), each multi-fit period with >= 2 accepted
disputed rows whose verdict differs under first fit, and rejects the seed otherwise. The off-list draft
plant (v1 W) is dropped: the no-fit case now comes only from W, which a per-period program resolves.

### LV-2 R-CHANGE v2 (S2, keyed in station_notices.md)
station_notices.md rows become `| <station> | <notice_date> | <coefficients> |`, the last cell naming one
or more section 3 coefficients. Its governing sentence (rule_register points to it): "A notice starts a
new period at 00:00 on its notice date and gives new values only to the coefficients its row names."
Circular section 1 keeps the definition "A visit's instant is its boarding instant." and section 4 keeps
"A visit belongs to the period that holds its instant."; the directive sentence on date rules is deleted.
Shipped: one notice, North 2026-08-17, naming all four coefficients, so per-period and joint recovery
agree (quiet). Hidden: X names two coefficients, its periods resolve both ways (control) and carry the
v1 notice-day, eve and invoiced-after plants (3 each); Y and W notices name one to three coefficients
(drawn per seed). A wrong period reading moves X paid invoices across the notice date, the joint fit
then has 0 combinations and both X periods turn `cannot_recompute` (COUPLING amplifies).

### LV-3 R-EXEMPT v2 (S8 midnight split plus a stateful allowance, own RNG)
New file certificates.json: `{"<certificate_id>": {"holder": str, "expiry": "YYYY-MM-DD",
"allowance_minutes": int}}`; vessel_register.tsv last column becomes `certificate` (public: an id,
commercial: `-`). exemption_policy.md: "A certificate covers on-board time of the vessels registered
under it, before 00:00 on its expiry date, up to its allowance_minutes in total. Visits draw on the
allowance in the order of their instants, the lower visit id first on a tie." Covered minutes of a visit
= the smaller of its on-board minutes before that 00:00 and the allowance left; billed minutes =
on-board minutes - covered minutes; due per circular 2a (unchanged pro-ration: each rounded line x
billed / on-board, half-even again). "Visit" is the circular section 1 defined term (BOARD plus RELEASE
with one id), so uninvoiced visits, visits at other stations and visits whose invoice is rejected all
draw. Shipped (quiet): one vessel per certificate, allowance above any vessel's covered total, no public
visit on board within 12 h of its expiry midnight. Hidden (rare RNG `random.Random(seed*7919+17)`, each
>= 2 per corpus): certificates shared by 2-3 vessels at different stations; allowance exhausted inside
a visit (partial billed minutes with no midnight); an uninvoiced visit drawing before an invoiced one; a
visit wholly before expiry billed in full because the allowance is gone; v1 midnight splits kept. Paid
invoices of public vessels are priced with the stated reading, so a wrong allowance reading also breaks
the station fit (COUPLING). Reflexes: no cap (exact on shipped), per-vessel allowance, only invoiced
visits draw, order by visit id or file line, inclusive expiry day. Files: 14 in 8 formats.
Scope flag for the master: the allowance extends S8 with an H6 stateful key; decision needed at go.

### Plain-rule changes
Section 2a cross-case sentence (master change 3) reworded as a definition: "A visit's period, tariff
and surcharge test do not depend on its billed minutes." Toy examples stay only for the due lines and
half-even. Fatal list adds certificates.json not one JSON object of that form. data_quality unchanged
(certificates.json has no record lines). segment `exempt_minutes` = sum of covered minutes of disputed
rows.

### Expected loss v2 (tests, of 87)
Every lever fires on every hidden corpus and changes summary, audit, regions or segments there: each
alone 16 x 4 + 9 mutation = 73 (84%). First-fit loss with W removed: Y1, Y2, Z rows on 4 corpora, 64 +
9 = 73. Judge probes P7 becomes "shows per-period and joint candidate counts at a notice station", P8
"traces one certificate's draws in instant order"; both expected FAIL for a transliterating program.
Forecast: tests 25-45, judge 12-15 of 39 (blind measured), final 25-38; upper 60 if both v2 levers land.

## 12. v2-go: breadth, quiet rules, ownership (master go 26 Oct 21:26)
Files: 14 (certificates.json added), 8 formats. Rules: 3 sharp + 36 plain = 39 graded.
Master change 1: certificates section in exemption_policy.md states that every visit draws, whether
invoiced or not and at whichever station; draw-order sentence kept word for word; EVIDENCE_MAP row added.

Quiet plain rules (BRANCH_FIRE 0 on shipped, >= 2 disputed rows per hidden corpus, one toy example each on
invented values; plants only commercial vessels, only disputed visits, only in jointly resolved periods
X1, X2, Y1, disjoint from lever plants, one quiet rule per plant row; no paid invoice ever hits one):
| id | governing file | rule | shipped quiet form | reflex |
|---|---|---|---|---|
| Q1 | circular s2 | BOARD may end ` assist=<minutes>`: assist line 40.00 per started 30 minutes, outside the surcharge base | no suffix | strict regex rejects line / round minutes |
| Q2 | circular s1 | BOARD may give `draft_m=<d.dd>` instead of `draft_dm`; metres rounded up to the next 0.1 m | never | round / truncate / reject |
| Q3 | circular s2 | a holiday falling on a Sunday is also kept on the following Monday | no Sunday holiday | no Monday surcharge |
| Q4 | station_notices.md | `CANCEL <station> <visit_id> <vessel_id>` line: due is the station call-out fee, no surcharge, 0 minutes, instant = CANCEL time | no CANCEL line | unknown_visit |
| Q5 | station_notices.md | a commercial visit's due is never below the station minimum due | minimum never binds | missing floor |
| Q6 | exemption_policy.md | register column `measured_from`; a vessel may have more rows; row in force at the instant | one row, `-` | last row wins |
| Q7 | exemption_policy.md | public vessel with certificate `-` has no cover, billed in full | every public vessel has one | treat as covered / crash |
| Q8 | output_contract.md | disputed column `supersedes`: the invoice an accepted disputed invoice supersedes is left out of every output | column empty | both rows kept |
| Q9 | circular s6 | disputed billed may be whole cents followed by `c` | never | malformed_record |
| Q10 | circular s2 | holidays.json key `all`: dates kept at every station | `"all": []` | ignored |

Shipped-firing plain rules added: N1 rejection `early_invoice` (invoice date before its visit's instant
date); N2 rejection `already_paid` (disputed invoice whose visit has an accepted paid invoice); precedence
malformed_record, duplicate_invoice, unknown_visit, station_mismatch, early_invoice, already_paid; N3 segment
key `vessels` (distinct vessels of its disputed rows); N4 summary key `largest_refund` {invoice_id, amount},
lower id on a tie, null when no overbilled row. Guards: non-plant commercial GT >= 3000 (due above every
minimum); no non-plant visit on an `all` date or on a kept Monday at that station.

Test plan v2-go: 34 checks, P = 112. Shipped 18 (exist 1, audit 5, summary 3, regions 3, segments 3,
quality 3). Hidden k = 1..4: audit_plain 5 (rows not owned by a quiet check), regions 5 (periods plus totals,
totals recomputed with quiet-owned rows replaced by the program's own), quality 3 (quiet-owned lines masked,
counts adjusted) = 52. Whole-document aggregates: summary_c1 3, segments_c2 3. Q1..Q10 w3 pooled over the 4
corpora (owned rows by invoice id plus owned lines; never passes with nothing compared) = 30. Mutations
relocated (foreign cwd) 3 and missing_source 3, invariance against the program's own plain run. Negatives
negative_reads_tests -5, negative_hardcoded_sample_answers -3. Hidden share 94/112 = 83.9%.
OWNED: hidden audit rows -> audit_plain_ck or Qn; region docs -> regions_ck; rejected lines -> quality_ck or
Qn; summary c1, segments c2 -> whole-document checks (amplification); summary and segments on the other
hidden corpora are graded through their rows only. Planned costs: quiet alone 9/112 = 8.04% (all-but-one
91.96); all ten quiet skipped 36/112 -> 67.9; each lever alone >= 40/112.

## Lessons for the master
- A lever stated as a directive or a procedure beside its field is transliterated in minutes; key it in another file or across records | template_change: LEVER_RULES_v3.md:102 add "a directive sentence restating a definition is itself the leak"
- A first-fit program is exact on any instance where every coefficient is exercised; the shipped guard must assert that, and hidden corpora must break it | no change: covered by LEVER_RULES H8
