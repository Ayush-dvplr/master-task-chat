# PREMORTEM 49087b0 pilotage-dues-reconstruction (L-CONV redesign)

Design under test (from IDEA_v2 G-1..G-8): v1 world kept (4 stations, quarter 2026-07-01..09-30, 5-line due,
180 listed tariffs, notices split periods, paid invoices per station in 4 formats, disputed batch, exemptions,
rejections). New: six billing conventions are each stated, in the file that governs the quantity, as "the
station's convention", without listing a station's reading:
CV-A part assist block (assist line, circular s2), CV-D tenth of a metre a draft is billed at (vessel_register
header), CV-S whether a Sunday holiday is also kept on the Monday (holidays.json note), CV-B whether the
surcharge is reckoned on the assist line (circular s2), CV-H which holiday calendar of holidays.json the station
keeps (holidays.json header), CV-N the station's night window (circular s2; circular s1 says every time of day a
station sets is a whole hour). One sentence (circular s5): a station's conventions are the readings under which
every period of the station has a listed tariff reproducing every paid invoice of the period, and exactly one
combination does. Shipped: every station uses the headline combination (started block, round up, Sunday and
Monday, surcharge with assist, own regional calendar, 22:00-06:00), no notice is in force. Hidden w5 tier:
every station draws its own combination, notices split periods, some periods admit two tariffs.

## Opus first 10 minutes (reflex trajectory)
1. min 0-1: `ls /app/data`, reads instruction.md, output_contract.md, tariff_circular.md in full (they are
   short), skims rule_register.md, head of every data file (log, register tsv, holidays.json, notices md, the
   four paid files, disputed csv, certificates.json, exemption_policy.md).
2. min 1-3: lists the conventions the circular names beside the due lines (CV-A, CV-B, CV-N; CV-S and CV-H
   when it reads holidays.json; CV-D when it reads the register header). Reading of each family: the natural
   readings it can name in one breath: assist {started, completed}, draft {up, nearest, down}, Sunday
   {Sunday only, Sunday and Monday}, surcharge base {with, without}, calendar {the station's own regional
   calendar} (H1 nearest-named), night window {22:00-06:00, maybe 21-06/22-07/23-05}.
3. min 3-6: writes derive_report.py once: parsers, rejections, periods, a joint loop
   `for conv in product(natural space): for tariff in 180: if all(due == paid)`; keeps conv with a fit
   (first fit, H8, or a count over its natural space), recomputes disputed invoices, aggregates.
4. min 6-8: self-tests: runs on shipped data; every station fits (headline), every period has exactly one
   tariff; totals reconcile; invariants (refund_total = sum of positive differences) hold. It may time the
   loop and trim the window range for speed. It never builds a corpus whose station keeps another calendar
   or another night window (H9), because the shipped run already shows "1 of N readings fits".
5. min 8-10: closing message lists the readings the shipped invoices show.

## Where the first-write program goes wrong, and why no self-test catches it
| rule / source | wrong point | why its self-tests stay green |
|---|---|---|
| CV-H calendar (L-CONV) | searches only the station's own regional calendar (or own + national); a hidden station keeping the harbour or a neighbour's calendar fits no combination, or a rival with a shifted window absorbs the holiday flags | shipped every station keeps its own calendar; the natural space contains the truth |
| CV-N night window (L-CONV) | searches 22-06 and a 1-hour neighbourhood; hidden windows 19:00-05:00, 20:00-08:00, 23:00-04:00 are outside it | shipped window is 22-06 everywhere |
| CV-A / CV-D / CV-S / CV-B | covered when it names all readings; lost when it hard-codes the circular's headline reading (one convention everywhere) | headline reading fits shipped |
| S3 unique fit | first fit (H8): takes the first tariff (or first convention) that reproduces a period; hidden periods with two fitting tariffs must be cannot_recompute; counting (conv, tariff) pairs instead of convention combinations marks a resolved station unresolved | shipped every period has exactly one fit, so first fit == unique fit |
| notice split (S6) | ignores notices (shipped has none) or splits at the notice instant on another clock; hidden notices split periods at 00:00 of the notice date and the boarding instant decides | shipped notices file has no row in force |
| COUPLING | every slip above flows into the station's region file, its audit rows, both segment files and the summary of that corpus | totals are self-consistent under any wrong reading |

A plain first-write program is exact on the shipped data and on a fresh seed only if the seed draws the
headline combination for every station, which the hidden generator never does (every hidden corpus has at
least two stations off the headline in CV-H or CV-N). So the design is not transliterable in 3 minutes on the
lever: the program must search the whole stated domain of each family, which no shipped check prompts.

## Judge probes (planned) and whether its trajectory shows the act
| probe | template | Opus shows it in its first 10 minutes? |
|---|---|---|
| runs the program on a copy where one station's paid invoices are re-billed under another night window and reports the recovered window | P-d altered-copy rerun | no (H9) |
| shows one station where more than one candidate convention combination was checked and states how many fit | P-g uniqueness witness | partly: prints "1 of N fits" over its natural N; counted as pass about 50% |
| runs with a declared input removed and shows the message naming the file | P-h missing input | rarely |
| recomputes one disputed invoice outside the program | P-c | sometimes |
| runs from a relocated data and out directory | P-e | rarely |
| runs on an edge input (a period with no paid invoice) | P-a | no |
| one-instance witness: prints one station's recovered conventions and one invoice reproduced line by line | P-b | sometimes |
| runs the unmodified program before the first edit | P-f | n/a (fresh build, no tool) -> not used |

Predicted judge mid with probes at 25%: about 20 of 100.
