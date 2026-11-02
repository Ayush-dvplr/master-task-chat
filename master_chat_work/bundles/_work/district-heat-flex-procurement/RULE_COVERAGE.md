# RULE_COVERAGE - district-heat-flex-procurement (redesign r4, 25 Oct 2026)

One row per contract rule. Mutant = the verifier reference with that one rule switched to its wrong reading (`reference(root, frozenset({FLAG}))`), run as the agent program on the shipped data and graded by the embedded tests (positive 173). Source: `OUT/redesign_r4/mutant_grades.json`.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| valid continuity waiver recognised | environment/data/schema.md:149 | H1 (96/173) | 19 |
| label ranking: holds above waiver | environment/data/schema.md:147 | H1order (125/173) | 12 |
| SAFETY_HOLD ranks above COOLDOWN | environment/data/schema.md:147 | H1hc (165/173) | 2 |
| pending certificate label | environment/data/schema.md:147 | H1pend (165/173) | 2 |
| waiver_signed must be Y ([export] carries no rule) | environment/data/schema.md:29 | SIGNEDY (114/173) | 15 |
| greatest identifier tuple wins a tie | environment/data/schema.md:135 | H2 (158/173) | 3 |
| cap binds the final rate | environment/data/schema.md:142 | H3 (85/173) | 22 |
| leftover cents by decreasing remainder, ties descending id | environment/data/schema.md:235 | H4 (168/173) | 1 |
| quantise each Wh value when derived | environment/data/schema.md:129 | H5t (143/173) | 6 |
| credit rounding per interval amount | environment/data/rate_cards.xml:11 | H5c (90/173) | 21 |
| optimisation in ticks | environment/data/schema.md:180 | DH2 (143/173) | 6 |
| funded pool less credit cents | environment/data/schema.md:215 | DH3 (104/173) | 17 |
| duplicate profile row: earlier kept row wins | environment/data/schema.md:63 | DH4dup (98/173) | 15 |
| out-of-range profile row skipped | environment/data/schema.md:61 | DH4range (123/173) | 10 |
| duplicate needs an earlier kept row | environment/data/schema.md:63 | DH4seen (168/173) | 1 |
| unknown-region site row skipped | environment/data/schema.md:47 | DH4unknown (158/173) | 3 |
| weight doubled only for label CONTINUITY_WAIVED | environment/data/schema.md:222 | DH5raw (133/173) | 10 |
| blended cost before overdelivery | environment/data/schema.md:193 | C34 (98/173) | 21 |
| overdelivery before offer count | environment/data/schema.md:195 | C45 (104/173) | 19 |
| offer count is component 5 | environment/data/schema.md:196 | C5drop (118/173) | 11 |
| zero-weight beneficiaries not listed | environment/data/schema.md:244 | W0LIST (165/173) | 2 |
| register_multiplier applies | environment/data/schema.md:57 | MULT0 (50/173) | 31 |
| multiplier applies to Wh before ticks | environment/data/schema.md:57 | MULTtick (128/173) | 9 |
| override replaces base | environment/data/rate_cards.xml:5 | OVR0 (82/173) | 23 |
| override is a start rate, adjustments still apply | environment/data/rate_cards.xml:5 | OVRrate (82/173) | 23 |
| segment rate adder added | environment/data/program.ini:21 | ADD0 (112/173) | 17 |
| cap after adder | environment/data/schema.md:142 | CAPpre (108/173) | 17 |
| event uplift added | environment/data/schema.md:39 | UPL0 (82/173) | 23 |
| round each interval amount, not each offer | environment/data/rate_cards.xml:11 | R7offer (85/173) | 22 |
| interval amounts half to even | environment/data/rate_cards.xml:11 | R7up (153/173) | 4 |
| rounding unit is the interval amount | environment/data/rate_cards.xml:11 | R7offer_even (85/173) | 22 |
| allowance excludes offers | environment/data/site_allowances.tsv:11 | LEDnone (55/173) | 30 |
| chosen offers draw the allowance | environment/data/site_allowances.tsv:9 | LEDstatic (115/173) | 12 |
| events reach allowances in start order | environment/data/site_allowances.tsv:6 | LEDid (94/173) | 19 |
| start order by instant, not text | environment/data/site_allowances.tsv:7 | LEDstr (115/173) | 12 |
| equal instants served descending id | environment/data/site_allowances.tsv:7 | LEDtie (118/173) | 11 |
| second share over survivors shares every cent of F | environment/data/schema.md:238 | REENTRY (128/173) | 9 |
| dropped cents shared again | environment/data/schema.md:238 | DROPLEFT (125/173) | 10 |
| share under minimum_grant_cents receives nothing | environment/data/schema.md:237 | NODROP (150/173) | 5 |
| claims paid when they fit in F | environment/data/schema.md:231 | CLAIM0 (101/173) | 18 |
| unallocated cents carried to next event of region | environment/data/schema.md:217 | NOCARRY (107/173) | 16 |
| draws_from names the allowance drawn on | environment/data/site_allowances.tsv:2 | CHAIN0 (73/173) | 26 |
| draws_from followed to a site with blank draws_from | environment/data/site_allowances.tsv:3 | CHAIN1 (118/173) | 11 |
| credited relief ticks | environment/data/schema.md:205 | RELIEF (115/173) | 12 |
| units drawn from [units] (wh_per_tick, millicents_per_cent) | environment/data/schema.md:19 | UNIT10 (166/261, QL2) | 18 |
| feeder and segment codes read through [region_codes]/[segment_codes], several per region | environment/data/schema.md:21 | CODESHIP (151/261, QL2) | 20 |
| segment with no adder option has adder 0 | environment/data/schema.md:25 | ADDmiss (226/261, QL2) | 7 |
| interval with no kept profile row is 0 Wh | environment/data/schema.md:59 | GAPdrop (241/261, QL2) | 3 |
| allowance drawn only by events reached before (not by other regions of the same event) | environment/data/site_allowances.tsv:10 | LEDwithin (216/261, QL2) | 7 |
| excluded only when relief is more than what remains | environment/data/site_allowances.tsv:10 | ALWge (221/261, QL2) | 8 |
| claims paid when they add up to F exactly | environment/data/schema.md:231 | CLAIMlt (256/261, QL2) | 1 |

P12 rows (session 8556721, 29 Oct 2026): mutant run with the P12 tests (positive 237, hidden extracts H1/H2 carry the drawn units/codes, omitted adder, dropped profile rows, cross-region draw pair, exact allowance and exact-claims pools). Source: `WORK/p12/dout/TRAP_p12new.txt`.

QL2 rows (session 19f8e1f, 29 Oct 2026): the same mutants re-run with the QL2 tests (positive 261: 12 new bid_cost_rows/compliance_rows checks, new H1 seed with the Wh-feasibility guard). Losses kept or grew (UNIT10 90->95, CODESHIP 100->110, GAPdrop 15->20, LEDwithin 35->45; others equal). Source: `WORK/p12/dout/TRAP_q2.txt`.
