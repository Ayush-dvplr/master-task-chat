# PREMORTEM: fuel-card-settlement-consolidation (board 60e9db0)

Written 26 Oct 2026 18:05 IST, before any other design file. Rule ids R01..R42 are the register in DESIGN.md.

## 1. Opus's first 10 minutes (reconstructed from peer trajectories, H8 first fit, H9 shipped-only self-test)

| min | act |
|---|---|
| 0-1 | Reads instruction.md. Notes the command `cd /app && python3 out/transform.py --data <dir> --out <dir>`, the 14 output paths, "graded whole on fresh inputs, only an exact match counts". |
| 1-2 | `ls -R /app/data`, `wc -l`. Opens docs/RULES.md (register) and docs/output_schema.md first, because the schema names every key. |
| 2-5 | Reads docs/group_standard.md top to bottom once, then the five handbooks, skimming the ones whose export "looks like CSV". Opens docs/group_standard_2023.md, sees "Superseded by the Group Settlement Standard 2026" in its header and closes it after the first screen. Opens docs/reference_data.md once. |
| 5-6 | `head` on each export, processors.json, discount_tiers.ini, one screen of tax_rates.tsv, accounts.csv, cards.csv, batches.log. |
| 6-14 | Writes transform.py in one pass: one parser per processor that yields a common record; a reject function; tier volume per account; discount; tax; a writer per output family. Values that sit in prose (head-office offset, gallon factors, cap amounts) are typed in as constants the way the shipped handbook shows them. |
| 14-20 | Runs it on /app/data. Self-tests: no exception; ledger row count + rejected count = rows read per processor; sum of region files = summary totals; settled = net + tax - discount on every row; spot-reads 3 source lines against their ledger rows. All pass on shipped data. |
| 20+ | Writes the final answer quoting totals from summary.json. Builds no input that fires a branch the shipped month does not fire (H9). |

## 2. The program it writes, and where it goes wrong

Readings below are what the first-write program does. "Self-test" says why none of section 1's checks catches it.

| rule | its first-fit reading (H) | goes wrong on | why its self-tests miss it |
|---|---|---|---|
| R02b month boundary by local date | filters on the export's own date string, or on UTC date for UTC exporters (H8) | hidden: rows at 23:xx local on the last day that are 0x:xx UTC next day, and the mirror at the start | shipped month has no row within 14 h of either boundary; both readings give the same set |
| R04b card holder on business date | takes the card's current (open) row or first row (H8) | hidden: card reassigned mid-month | shipped cards.csv reassignments all end before the month; any row choice agrees |
| R05b segment in force on business date | uses the last accounts.csv row per account (H8) | hidden: account changes segment mid-month | shipped history rows all start before the month |
| R09b tax rate in force on business date | latest row per jurisdiction and class (H8) | hidden: rate change on day 10-20 | shipped rate changes all before the month |
| R14b tier floor inclusive | `>` instead of "at least" in a loop written fast | hidden: account at exactly a floor | no shipped account sits on a floor |
| R16 monthly discount cap, in ledger order | not implemented or applied to the account total at the end (H6, state consumed late) | hidden: enterprise accounts that pass the cap | no shipped account reaches its cap; cap section of the ini reads as dead config |
| R18 cross-processor reversal | looks up the original only in the reversal's own export | hidden: norvik reversal of a kestrel sale, oberon of a lumen sale | none shipped; it would reject them as `orphan_reversal`, which its count identity still balances |
| R19b orphan when the original was rejected | matches the reversal to the raw original record even if that record was superseded / out of period | hidden | no shipped reversal points at a rejected original |
| R21 closed account | ignores `closed_on` (blank on shipped for every account that trades in the month) | hidden | no shipped trade after a closing date |
| R23b batch REINSTATED | treats any WITHDRAWN line as final (H6) | hidden: WITHDRAWN then REINSTATED | shipped log has no REINSTATED |
| R27 CNG kilograms (decoy live clause, S5) | drops the whole 2023 standard; reads CNG quantity in the handbook's liquid unit | hidden: CNG lines on two processors | no CNG line shipped; the newer standard's carried-forward sentence sits in its last section |
| R36 marlow resubmission | keeps both, or rejects the later one as `duplicate` | hidden | no shipped resubmission |
| R39 norvik calibration | handled by its generic pump-test filter only for the shipped markers | hidden | quiet on shipped |
| R42 oberon split tender | one ledger row per txn_id, second tender dropped as duplicate | hidden | none shipped |
| W12 prose values | constants copied from the shipped handbook prose (head-office offset, gallon factors, CNG factor, tier floors if read by eye) | every hidden corpus whose handbook values differ | it only ever runs the shipped month |

Rules that fire on shipped data (R01, R03, R06-R13, R15, R17, R19, R20, R22, R24-R26, R28-R35, R37, R38, R40, R41) can still be misread, because no answer is shipped: e.g. region from processors.json `home_region` instead of the site (R03), tax extracted as `gross*rate` instead of `gross - gross/(1+rate)` (R10), half-up instead of half-even on the planted ties (R12), AdBlue counted as tier volume because it is measured in litres (R08). Its self-tests are all internal identities that hold under either reading. Expected first-write slip rate on these: low (each is a plain sentence), so they are breadth cost, not the main loss.

## 3. Expected program state at 46 minutes

A careful agent re-reads the group standard once after its first run and fixes what it spots in text (likely R16 cap if it noticed the ini section, R14b). Peer evidence (8764bfdd, 93 minutes, still 20 checks missed) says it rarely revisits the decoy or builds month-boundary inputs. Predicted misses at end: 3 to 6 of the 15 quiet rules plus W12 prose constants on 1 to 3 values. Any one quiet slip breaks every hidden corpus for the ledger family and every family whose totals carry the slipped rows (through the COUPLING tier), so tests land near the recipe's 25-55.

## 4. Planned judge probes: would its trajectory show the act?

| probe | act | Opus shows it? |
|---|---|---|
| J-P1 (P-a) | runs transform.py on an input with a cross-processor reversal and shows the reversal's ledger row | no (H9) |
| J-P2 (P-a) | runs on an input with a sale at 23:30 local on the month's last day and shows its business date | no |
| J-P3 (P-b) | prints one source line from each of 3 processors next to its ledger row | sometimes (spot reads) |
| J-P4 (P-c) | recomputes one region total outside transform.py and compares with region_<r>.json | sometimes (sums regions vs summary, usually inside its own code) |
| J-P5 (P-d) | runs on a copy with one changed tier floor or tax rate and shows a dependent figure moved | rarely |
| J-P6 (P-e) | runs with --data and --out pointing at a relocated copy | rarely |
| J-P7 (P-h) | runs with one export missing and shows the stopping message naming it | rarely |
| J-P8 (P-b) | shows one account whose tier comes from volume summed over 2 or more processors, with its per-processor litres | sometimes |
| J4 | every handler acts on its error; missing input stops naming the file | about half |
| J6 | final reply lists every processor with rejected rows and each reason | yes |
| J10 | runs from /app with the stated command | yes |

## 5. Transliteration check (registry/tasks.json:707-734)

Would a first-write program be exact on shipped AND on a fresh hidden seed? On shipped: likely yes or close (no answers shipped, nothing to compare, but the rules that fire there are plain). On a fresh hidden seed: no, unless it implements all 15 quiet branches from text and parses every re-rendered prose value. The design keeps hardness in rules it has no input to exercise (S6), in the decoy's one live clause (S5), and in breadth (S1); none of it depends on a size limit or a hint sentence. Proceed to DESIGN.md.

## 6. Addendum R2 (21:35): unique fit for reversals with an empty reference

The blind read showed the first write is exact on every plainly stated `if` (DESIGN_BLIND.md). What its program does with 11.4-11.5: it parses each export in file order and handles a reversal when it reads it. The natural code is an index `(processor, card, product, quantity, amount) -> [sale lines]` built from every parsed line, and `index[key].pop(0)` or `[0]` for a reversal with no reference (H8). Where that goes wrong: U1 two settled twins (takes the first, never counts); U3 the twin rejected by batch standing or period sits earlier in the file (the index was built before rejection); U4 the window (if it filters at all, it filters before choosing, but a pop from a list sorted by file order breaks the window once a line is consumed); U2/U2r the ledger-order and referenced-first sequencing (a streaming program resolves in file order and consumes the line a later referenced reversal names). Its self-tests: shipped controls only (rows_read = settled + rejected, totals balance); every shipped empty-reference reversal has exactly one fitting line, so `pop(0)` and the counted unique fit coincide and every control reconciles. It never builds two identical sale lines (H9). Judge: P-g needs an input with two fitting lines; Opus is not expected to show it.
