# PREMORTEM 44635de pilotage-dues-reconstruction

Planned surface (from IDEA + gate notes): /app/docs holds rule_register.md, tariff_circular.md,
exemption_policy.md, output_contract.md; /app/data holds paid_north.csv, paid_south.jsonl,
paid_west.txt (fixed width), paid_east.xml, disputed_batch.csv, pilot_movements.log,
vessel_register.tsv, holidays.json, station_notices.md. The agent writes /app/out/derive_report.py and
the nine JSON documents; the instruction promises a rerun on fresh data in the same format, exact match.

## How claude-opus-5 solves it in the first 10 minutes
1. Reads instruction.md, then docs/rule_register.md (it names every governing file), then
   tariff_circular.md top to bottom, exemption_policy.md, output_contract.md. `head` on every data file,
   `wc -l`, one `grep -c` on the log event types.
2. Writes derive_report.py in one pass (about 350 lines): parsers for the 4 paid formats (csv, json
   lines, fixed width by the column table in the circular, ElementTree), BOARD/RELEASE pairing in the
   log, register join for GT, segment and exemption expiry, holiday sets per station, notices table.
3. Due function: four lines (tonnage, draft, towage, night/holiday), Decimal half-even per line. This is
   exercised by every shipped invoice, so any slip here shows as "no tariff fits" on shipped and is fixed.
4. Fit: `itertools.product` over the closed lists (5 x 4 x 3 x 3 = 180), per station and period, and
   (H8) `for combo in product(...): if all(match): return combo`, else `None`. On shipped exactly one
   combination fits each of the 5 station-periods, so first fit = unique fit and nothing looks wrong.
5. Periods: reads the notices table, splits the station at the notice date. Reflex: compares the notice
   date with the date it already holds on the invoice record (`invoice_date`) or with `board.date() >
   notice` (strict). Shipped has no North movement from 6 days before the notice through the notice day,
   so all three readings put every shipped invoice in the same period.
6. Exemption: reads "public vessels holding a certificate are exempt until its expiry date" and writes
   `exempt = segment == "public" and expiry and board.date() <= expiry` (all or nothing, expiry day
   inclusive). Shipped has no public visit on board at any time from noon the day before an expiry to the
   end of the expiry day, so the all-or-nothing inclusive rule and the stated pro-rata rule agree on
   every shipped visit.
7. Self-tests (H9): runs on /app/data; prints the recovered tariff per station and period (one each);
   checks every paid invoice reproduces; spot checks two disputed rows by hand from the program's own
   functions; checks JSON keys against output_contract.md. It never constructs a corpus with two fitting
   tariffs, a boundary-day movement or a visit across an expiry midnight. About 25 minutes to first full
   write, done at 35-40 minutes.

## Per sharp rule: where the first-write program goes wrong, and why its self-tests miss it
| rule | wrong point in the program | why no self-test catches it | hidden input that fires it |
|---|---|---|---|
| R-FIT unique fit / unresolved | returns the first fitting combination; a no-fit period may fall back to "best match" | shipped: every period has exactly 1 fit, so first = unique and no-fit never happens | one station-period whose paid invoices never use a tug (3 fits), one with invoices billed at an unlisted draft rate (0 fits); both have disputed rows that need the free coefficient |
| R-CHANGE period by boarding instant, inclusive of the notice day | period chosen by `invoice_date`, by release time, or `>` the notice date | shipped: no movement at the notice station from notice-6 through the notice day, so every reading gives the same split | movements boarding on the notice day; boarding 1-5 days before and invoiced on or after it; boarding 23:xx the eve and released after 00:00 |
| R-EXEMPT partial visit, ends at 00:00 on expiry date | all-or-nothing on boarding time, expiry day inclusive, or pro-rata of the total instead of each line | shipped: no public visit touches [expiry-1 12:00, expiry+1 00:00) | public visits across expiry midnight (paid and disputed), wholly on the expiry day, ending just before it |

Cascade: every slip above changes a station-period's fit (paid invoices stop reproducing, or a second
fit is hidden), so it changes that station's verdicts, region file, both segment files and the summary
(COUPLING sentence). Each fires on every hidden corpus.

Plain rules that fire on shipped (half-even per line, night window, holiday per station, tonnage per
100 GT, draft threshold, towage, malformed/duplicate/unknown records, money as strings, ordering): the
program is exact on them after its shipped run, because a wrong reading leaves "no tariff fits" on shipped
or fails a key the contract names. They carry no hardness and are not counted as levers.

Verdict: the first-write program is exact on shipped and wrong on every hidden seed (each corpus fires
all three branches). Before 0b the prototype will run a first-fit, invoice-date, inclusive all-or-nothing
variant on the sample and 3 seeds to confirm (G-9).

## Per planned judge criterion: would the trajectory show the act?
| criterion | template | shows it? (mid) |
|---|---|---|
| prints the count of fitting listed tariffs per station and period | P-g | rarely: it prints the tariff, not a count (25%) |
| builds a two-fit input and runs the program | P-a | no, H9 (10%) |
| builds a no-fit input and runs the program | P-a | sometimes for robustness (20%) |
| recomputes one disputed invoice line by line | P-b | yes, often by hand in python (55%) |
| recomputes a summary total outside the program | P-c | sometimes (35%) |
| reruns on an altered copy and shows the change | P-d | rarely (15%) |
| builds a notice-day movement and shows its period | P-a | no (10%) |
| builds a visit across an expiry midnight and shows its due | P-a | no (10%) |
| relocated rerun with data and out elsewhere | P-e | sometimes, because the rerun promise is stated (30%) |
| J4 handler conduct | J4 | usually (70%) |
| J6 final reply lists each station-period tariff | J6 | usually (70%) |
| J6 final reply lists each underbilled invoice id | J6 | sometimes (45%) |
| J10 runs the stated invocation after last edit | J10 | usually (80%) |

## Redesigns already made because of this premortem
- Recipe "paid invoices fitted per station" became per station and period, so the notice rule couples
  into the fit and its slip changes a fit, not one row.
- The free-coefficient hidden case keeps disputed rows that use the free coefficient (tugs > 0), so a
  first fit gives a numeric verdict that differs, not one that happens to coincide.
- Periods keyed by boarding instant with `invoice_date` present on every paid record: the boundary
  slip is a real reading, never a missing fact (boarding instant is stated in the circular definitions).

## Addendum v2 (after the design-stage blind read, 26 Oct 21:20)
The forecast above was wrong: the blind program (about 4 minutes to first write) was exact on every
branch. It enumerated all 180 combinations and stopped at the second match (the verdict clause names the
count), placed periods by the boarding instant (a directive sentence told it to), and pro-rated per
rounded line (the formula sat in section 2a). v2 first-10-minute program, per v2 lever:
| lever | where the transliterating program goes wrong | hidden input |
|---|---|---|
| LV-1/LV-2 joint | fits each period alone with the section 5 loop it already writes; the notice file's last cell is read as a label | Y1 (3+ alone, 1 joint), W (1 alone each, 0 joint) |
| LV-1 first fit | if it stops at the first match after reading "the combination" | Y2, Z |
| LV-3 allowance | keeps covered = minutes before expiry midnight (shipped never reaches the cap), or caps per vessel, or draws only from invoiced visits | shared certificates, exhausted allowance, uninvoiced draws |
A program that gets both v2 levers right is the risk case (final up to 60); the kill line is the master's
3 blind reads.

## Lessons for the master
- Shape D premortem must name the shipped gap that hides each branch | no change: covered by BRANCH_FIRE.md
- Free-coefficient fits need disputed rows that use the free coefficient, else first fit can coincide | no change: design note only
