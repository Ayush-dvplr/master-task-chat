# DESIGN_BLIND (board 60e9db0, blind read f60fbf4)

Blind program: `/tmp/blind/fuel-card-settlement-consolidation-20261026T210952-8cee/app/transform.py` (791 lines).
Run as stated: `python3 <program> --data <dir> --out <dir>`, cwd /tmp. Diffed per document against the prototype (`WORK/proto/solve_proto.py`).

## Timing and judge
- First full write about 4 minutes (21:15 to about 21:18), one run on the shipped month, self-check on shipped controls only (PASS).
- Not checked by the blind agent: missing input, month boundary, cross-processor reversal, altered inputs.
- Its judge estimate: lower 3/35 (8.6%), upper 17/35 (48.6%).

## Run 1 (corpora as the blind agent saw them)
| corpus | rc | documents exact |
|---|---|---|
| shipped | 0 | 13/13 |
| h11 | 0 | 0/13 (every lumen row rejected; first diff `normalized.jsonl` line 1) |
| h22 | 1 | none written: `Error: exports/lumen_settlement.txt: unparseable: unconverted data remains: 30` |
| h33 | 0 | 0/13 (same lumen cause) |

Cause: the hidden lumen layout widened `stamp`, `site` and `card`, and the handbook did not say which fields are numeric (zero padded) and which are text. That is a format hole (IN-16), not a lever. Fixed: `LUMEN_FIXED = {stamp, site, card, sign}` keep their width in every month; `handbook_lumen.md:4-7` now names `txn`, `line`, `quantity`, `amount` as zero-padded whole numbers and every other field as space-padded text. A blind copy patched only for that field read was exact on h22.

## Run 2 (after the fix, corpora regenerated)
| corpus | rc | documents exact |
|---|---|---|
| shipped | 0 | 13/13 |
| h11 | 0 | 13/13 |
| h22 | 0 | 13/13 |
| h33 | 0 | 13/13 |

## Per quiet rule (run 2)
| rule | h11 | h22 | h33 |
|---|---|---|---|
| Q1 R02b month boundary | exact | exact | exact |
| Q2 R04b card passes between accounts | exact | exact | exact |
| Q3 R05b segment change mid-month | exact | exact | exact |
| Q4 R09b tax row mid-month | exact | exact | exact |
| Q5 R14b volume exactly on a floor | exact | exact | exact |
| Q6 R16 monthly cap | exact | exact | exact |
| Q7 R18 cross-processor reversal | exact | exact | exact |
| Q8 R19b reversal of a rejected line | exact | exact | exact |
| Q9 R21 account closed mid-month | exact | exact | exact |
| Q10 R23b batch reinstated | exact | exact | exact |
| Q11 R27 CNG kg (2023 section 7, live clause) | exact | exact | exact |
| Q12 R36 marlow resubmission | exact | exact | exact |
| Q13 R39 norvik calibration | exact | exact | exact |
| Q14 R42 oberon split tender | exact | exact | exact |
| Q15 R20b duplicate settled by batches.log order | exact | exact | exact |
| decoy dead sections (2023 s1-s6, s8, s9) | exact | exact | exact |

Rules the blind program got wrong: 0 of 42 (and 0 of 15 quiet). Verdict: exact on the sample and on all 3 seeds, so the design goes back to Phase 0 step 3 (DESIGN.md section 9).

## Master points
1. Unstated cases. (a) A date before the first `effective_from` (tax or segment): every history starts before any line that reaches those checks on every corpus; the prototype counts 0 on all four corpora. (b) A card whose account is missing from `accounts.csv`: the generator drew a nonexistent account for some previous-holder rows; fixed (previous holders are real accounts or the row is dropped); 0 on all four corpora. (c) An unknown site: every site is drawn from `sites.csv`; 0 on all four corpora. Each gets an EVIDENCE_MAP row "never occurs in any corpus" and a generator assert (G12).
2. Reversal amounts "negated" (`group_standard.md` 11.3) is not one of the 15 quiet rules. Shipped reversals repeat the original's quantity and amount, so "negate the original row" and "recompute from the reversal's own fields" coincide on shipped data; they separate on hidden Q6 (cap) and Q7 (cross-processor reversal across tax inclusivity). The blind program got it right. The redesign adds Q16 (a reversal dated after a mid-month tax change, where only the negated-original reading keeps the original's tax).

## Read 2 (R2 design, blind read 5de8a10, run 27 Oct 02:01 IST)

Blind program: `/tmp/blind/fuel-card-settlement-consolidation-20261026T222609-2bf4/app/transform.py` (733 lines). Run as stated, outputs in `/tmp/fcs_blind2/`, diffed per document and per row (rows attributed to plants via the manifests) against the prototype outputs in `/tmp/fcs_out/`.

- First full write about 4 minutes (22:53 to 22:57); one run on shipped data plus a byte-identical repeat; self-check on shipped controls only (24,896 read = 21,928 settled + 2,968 rejected); missing-input path not run.
- Its judge estimate: lower 3/35 (8.6%), upper 17/35 (48.6%); 6 probes not performed (R1, R2, R3, R5, R7, R8).

| corpus | rc | documents exact | rows differing |
|---|---|---|---|
| shipped (/tmp/fcs/ship) | 0 | 13/13 | 0 |
| h11 (2028-09) | 0 | 13/13 | 0 |
| h22 (2026-04) | 0 | 13/13 | 0 |
| h33 (2029-03) | 0 | 13/13 | 0 |

Rules it got wrong: none (0 of 42 rules, 0 of 15 quiet branches, 0 of 7 R2 cases). First differing record: none on any corpus.

| case | h11 | h22 | h33 |
|---|---|---|---|
| U1 two fitting lines, `ambiguous_reversal` | exact | exact | exact |
| U2 ledger order of two unreferenced reversals | exact | exact | exact |
| U2r referenced reversals resolved first | exact | exact | exact |
| U3 rejected twin (superseded copy, duplicate copy, out of period) | exact | exact | exact |
| U4 six-day window | exact | exact | exact |
| U5 unreferenced reversal across a card reassignment | exact | exact | exact |
| Q16 reversal after a mid-month tax change | exact | exact | exact |
| Q1 to Q15 (each) | exact | exact | exact |
| decoy CNG clause (2023 s7) and dead sections | exact | exact | exact |

Wrong readings matched: none of firstfit, filestream, allparsed, refnotfirst, q16recompute, nowindow. Each of them moves rows on every hidden seed (COST_TABLE.md), and the blind program moves none.

Verdict: exact on the shipped month and on every hidden corpus. Per the master's instruction, no third redesign; the decision goes to Ayush.

## Lessons for the master
- A 42-rule plainly stated contract with a toy per quiet rule was transliterated in 4 minutes, exact on 3 seeds | template_change: LEVER_RULES_v3 section 1A: S1+S5+S6 without S3 or a stateful hidden key is not enough.
- Hidden layout changes must keep every field's class stated | no change: fixed in handbook_lumen.md:4-7.
- R2 (S3 unique fit with ordering and consumption, stated in 11.4-11.5 by reference to the check order and ledger order) was also transliterated exactly in 4 minutes on all corpora | template_change: LEVER_RULES_v3 section 1A: S3 alone, fully stated, is not enough against a careful reader.
- Breadth + quiet branches + decoy without a stateful key were transliterated (fuel-card R1 and pilotage v1, both exact in 4 minutes) | template_change: LEVER_RULES_v3 section 1A row S1/S6 note.
