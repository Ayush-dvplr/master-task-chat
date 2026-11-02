# DESIGN_BLIND 44635de pilotage-dues-reconstruction (blind board eef02d3)

Blind program: `/tmp/blind/pilotage-dues-reconstruction-20261026T184623-24cb/app/derive_report.py` (434 lines,
byte-identical to its `out/` copy). Run as the instruction states, `python3 <program> --data <dir> --out <dir>`,
on the 0b corpora in `/tmp/pilot-0b/`; outputs in `/tmp/pilot-blind/out_<corpus>`; compared document by
document (parsed JSON, first differing path) and audit row by row against the prototype outputs in
`/tmp/pilot-0b/out/<corpus>` with `/tmp/pilot-blind/bdiff.py`.

## Result: exact everywhere, so the design is redone (Phase 0 step 3)

| corpus | exit | docs exact | audit rows differing | first differing record |
|---|---|---|---|---|
| shipped (seed 482617) | 0 | 9/9 | 0 of 2098 | none |
| hidden 1101 | 0 | 9/9 | 0 of 809 | none |
| hidden 1103 | 0 | 9/9 | 0 of 765 | none |
| hidden 1104 | 0 | 9/9 | 0 of 721 | none |
| extra: hidden 1102, 1105, 1106 | 0 | 9/9 each | 0 | none |
| extra: 1101 without vessel_register.tsv | 2 | stderr `ERROR unreadable input: vessel_register.tsv` | n/a | none |

Rules it got wrong: none of 25.

| lever | 1101 | 1103 | 1104 |
|---|---|---|---|
| LV-1 unique fit (2-fit Z, 3/4-fit Y before, 0-fit W) | exact | exact | exact |
| LV-2 notice day (notice day, eve, invoiced after) | exact | exact | exact |
| LV-3 expiry pro-rating (across, wholly on, adjacent) | exact | exact | exact |

Minutes to first full write: about 4 (blind report line 13). Self-check: one shipped run plus invariants;
it built no two-fit or no-fit corpus and traced no notice-day or expiry visit (report lines 19-20), yet its
first write was already right. Judge estimate: lower 12, upper 15 of 39 positive.

## Why each lever was transliterated (from its code)

- LV-1: lines 303-320 enumerate all 180 combinations and stop at the second match; the verdict sentence
  "no such combination, or has more than one" names the count test outright, so H8 never had room.
- LV-2: lines 199, 218-220 take the period from the boarding date string with `p <= bdate`; circular :16
  "Every date rule in this circular reads the boarding instant" is a directive, not a definition.
- LV-3: lines 211-216, 233-237 copy circular section 2a line by line (later of boarding and 00:00 on the
  expiry date; per rounded line x billed / on-board, half-even). The determinate formula, written as a
  procedure next to the due, is a recipe.
- The structure that made all three right: it builds every known visit first (instant, period, minutes,
  surcharge flag) and fits per station-period over that table, so each rule lands in one obvious place.

Arithmetic note for the master: with tests at 100 and the judge at 12-15 of 39, the blind final is about
65-69, under the kill line of 70; the step 4 gate (exact on sample and 3 seeds) still applies and is
followed here.

## Read 2 (board f21f8e4, design v2, 27 Oct 02:01)

Blind program: `/tmp/blind/pilotage-dues-reconstruction-20261026T222609-8cdf/app/derive_report.py` (620 lines,
app and out copies identical). Run as stated on /tmp/pilot-0b2 shipped, h1101, h1103, h1104, plus h1102,
h1105, h1106; every run rc 0 in 0.22-0.45 s. Diff tool `/tmp/pilot-blind2/bdiff2.py` against
/tmp/pilot-0b2/out/<corpus>; it detects the reflex variants fit, indep and q5 on h1101, so it can fail.

| corpus | docs exact | audit rows differing | first differing record |
|---|---|---|---|
| shipped | 9/9 | 0 of 2764 | none |
| h1101 | 9/9 | 0 of 970 | none |
| h1103 | 9/9 | 0 of 971 | none |
| h1104 | 9/9 | 0 of 929 | none |
| h1102, h1105, h1106 | 9/9 each | 0 of 992, 974, 930 | none |

Rules it got wrong: none of 39. Minutes to first full write: 3-4 (start 22:52:57, program about 22:56).
Judge estimate (its report): lower 9, upper 12 of 39 positive; it ran none of probes P1-P9.

Per lever and quiet rule, on h1101 / h1103 / h1104 (and h1102, h1105, h1106):
- LV-1 joint fit: exact / exact / exact (all region periods exact, incl. Y1 alone-multi, Y2, Z, W joint 0)
- LV-2 keyed notices: exact / exact / exact (3 planted disputed ids per seed, 0 wrong)
- LV-3 allowance draw: exact / exact / exact (7 planted disputed ids per seed, 0 wrong)
- Q1 assist, Q2 draft_m, Q3 Sunday to Monday, Q4 cancelled booking, Q5 minimum due, Q6 re-measured row,
  Q7 public without certificate, Q8 supersedes, Q9 cents form, Q10 `all` holidays: exact on every seed.

Verdict: exact on the shipped data and on all 3 seeds (and the other 3). Per master instruction no third
redesign; stopping with DESIGN BLIND EXACT for Ayush's decision.

Three IN-15/IN-16 risks settled (docs only; every data file byte-identical after regeneration, checked
with `diff -rq` on all 7 corpora; design_blind refreshed):
1. Cancelled booking and minimum_due: station_notices.md:18-19 now says the minimum_due does not apply;
   generator asserts every call_out_fee is above every minimum_due, so both readings agree anyway.
2. Rejected record of a superseded invoice: output_contract.md:34-36 now says it is left out of
   data_quality.json whatever its code; generator asserts no corpus holds such a record.
3. CANCEL with BOARD, duplicate accepted BOARD: tariff_circular.md:23-24 states one accepted BOARD or
   CANCEL line and one accepted RELEASE line per visit id, never BOARD and CANCEL together; generator
   asserts it on the written log.
EVIDENCE_MAP.md has one row per risk.

What the two reads show: a fully stated contract of 39 rules over 14 files, with every hidden branch
quiet on the shipped month, is still transliterated exactly in about 4 minutes; breadth and quiet
branches did not cost Opus a single row. The remaining discrimination is the judge probe band (blind
9-12 of 39), which gives a forecast final of about 0.5 x 100 + 0.5 x 23-31 = 62-65.

## Lessons for the master
- A determinate rule written as a procedure beside its use (circular 2a) is transliterated in one pass; the redesign keys each sharp rule from a file other than the one holding the field it reads | template_change: LEVER_RULES_v3.md:102 (already says so; make it a Phase 0 check)
- An explicit count test in the verdict sentence ("or has more than one") removes H8 entirely; S3 then needs a candidate space whose count is not a plain loop | template_change: LEVER_RULES_v3.md:69 (S3 row: note the stated verdict defeats first fit)
- Run the blind program on all 6 seeds and on one mutation; cheap and it rules out seed luck | no change: done here
- Two blind reads exact on 25 then 39 stated rules: stated sentences, however many and however quiet on the sample, do not cost Opus rows; only unstated-in-sample probes (judge) separate | template_change: LEVER_RULES_v3.md:200 (T1/T2 hardening forecast should be checked by a blind read before build)
