# DIAGNOSIS: tariff-engine-audit-repair, test-hardening round 2 (board 15b380e, 27 Oct 2026)

Phase A: the blind read (438809e, `/tmp/blind/tariff-engine-audit-repair-20261026T222609-a6f7`) staged `environment/` and `instruction.md` only; `diff -rq` against BUNDLE: empty. BUNDLE `tests/` is the round-1 set (test_output.py and reward.toml 26 Oct 21:52, judge.toml 25 Oct 15:22), no edit since.

## 1. How the blind program got every rule (one write, 22:53 start, first full write 22:59:42, no later fix)

The blind read has no harness trajectory; its "step" is the single first write (BLIND_REPORT order: instruction, Dockerfile, contract, repo src, data heads, visible tests). Program refs are `app/repo/src/tariff/`.

| rule | contract | program | what made it easy |
|---|---|---|---|
| Q1 estimated / replaced_estimate | :65, :111-119 | parser.py:32-49, :74-94 (actual reads first, then estimated) | sentence next to the field; toy r1/r2 is the whole method; reason name given |
| Q2 standing_changes | :92-99, :142-143 | core.py:74-84 `charge_on` | formula "latest `from` on or before the day" next to the key; toy is the method |
| Q3 several billing rows | :76-85, :127-128 | report.py:46-66 list per account, :114-126 loop by start | "one or more rows" said in the file paragraph; each row its own invoice is the literal output shape |
| Q4 allowance carried | :154-159 | core.py:121 `settle` returns left, report.py:116/125 `carry` | the carry is a formula on a quantity the loop already holds (left from the re-share loop) |
| Q5 several accounts rows | :41-43, :67-73 | report.py:52 list of windows per (account, meter) | "each of its rows" in the Active definition; a list instead of a dict |
| L11 plan codes | data only (rate_card.json `codes`) | report.py:36-44 name, else first plan holding the code | shipped data fires it on 2000 invoices; a KeyError would point at it |
| N1 re-share | :151-153 | core.py:100-119 loop | stated loop; shipped data fires a third pass |
| N2 month proration | :142-146 | core.py:86-96 | stated formula; shipped periods cross months |
| N3 account position | :38-40 | report.py:83-86 running `position` | stated definition; shipped two-meter accounts cross tiers |

Pattern: every rule is a stated formula on values the program already holds, sitting beside the field it governs, with a toy that is the method. None needs state that is not already in the per-row loop, and none needs a search over candidates. A careful reader transliterates them in one pass.

## 2. Arithmetic (226 positive points; 52 positive checks, 2 negatives)

- Owned Q groups: estimated 15, standing 15, meter_row 15, billing_row 10, carried 8, combined 6 = 69 (30.5%). A program missing two or three Q rules lands at 80-87; first write (all Q wrong) measured 69.5.
- Every other positive check is fired by shipped data too (N1-N3, L11, rounding, credit, exceptions 1-5, deliverables), so a shipped-data self-check already proves them; they carry no hidden-only behaviour.
- Rules with hidden-only behaviour: only Q1-Q5, and the careful reader codes all five. So the blind program loses 0.
- To land the blind program at 70-90 the new levers must own about 20-28% of the new positive total and the blind program must miss each of them on every hidden corpus without a crash.

## 3. Planned levers (all hidden-only: shipped data has none of the new keys and no `payments.csv`)

Contract wording stays plain: one sentence where the field is defined, one toy on invented values (2031, X1/Y9), no order directive beyond the existing `start` and `day` definitions, no word on what shipped files lack.

### U1 unique fit: plan revisions settled by paid figures (S3)
- Data: a plan in `rate_card.json` may carry `revisions`, a list of objects each with its own `tiers`. New optional input `payments.csv` (`account,start,paid`) gives the amount paid for some invoices.
- Rule: an account's invoices on such a plan are rated with the one revision under which every one of those invoices that has a paid amount totals exactly that amount; when no revision or more than one does, they use the plan's own `tiers` (stated verdict, word for word in the contract).
- Evidence across records: witnesses are several invoices of the account; the total of a later witness depends on allowance carried from earlier invoices (Q4) and on D1, so the fit is settled only by the whole account chain.
- Careful-reader reading it targets: first revision that fits (H8), or fit tested per invoice without the carry/credit chain, or "no witness -> plan tiers" never needed because every revised account has a witness.
- Hidden planting per corpus: one-fit accounts (2-3), two-fit decoys (revisions agree on the witnessed invoice, differ on an unwitnessed one; truth = plan tiers), zero-fit (truth = plan tiers), fit that flips with carry (T4 with Q4), fit that flips with D1.
- Wrong document: invoice lines priced on the wrong revision (or on plan tiers); totals plausible, no crash. Blind round-1 program: ignores `revisions` and `payments.csv`, prices one-fit accounts on plan tiers: wrong on every corpus.

### D1 derived state: arrears cancel the next credit
- Rule (Credit paragraph): an invoice gets no credit (credit 0.00, total = subtotal) when the account's previous invoice by `start` has a paid amount below that invoice's total.
- State built from earlier records: the previous invoice's computed total (after its own carry, revision and credit), compared with `payments.csv`.
- Careful-reader reading it targets: per-row credit; comparing paid with the previous row's subtotal; using the previous row in file order.
- Planting: arrears accounts with subtotal >= commitment on the following invoice; paid == total (no arrears) and paid > total controls; chains of three invoices where arrears on invoice 2 changes invoice 2's total and so invoice 3's arrears; T4 with U1 (fallback totals above paid), Q4, Q3.
- Blind round-1 program: no `payments.csv` read, credits every committed invoice: wrong total and credit on every corpus.

### D2 derived state: cumulative register reads (with reset)
- Rule (meter_reads paragraph): a read may carry `cumulative` true: its `quantity` is the meter's running count on `day`, and the quantity it bills is that count minus the count of the same meter's latest earlier accepted cumulative read by `day`; 0 when there is none, and the whole count when the count is below that earlier one.
- State built from earlier records: the previous accepted cumulative read of the meter, which can sit in the previous billing row (Q3), behind a replaced estimate (Q1) or in an inactive gap (Q5, not accepted).
- Careful-reader reading it targets: bill the count as is; base on any earlier read (including rejected ones) or on file order; base reset per billing row; negative quantity on reset.
- Planting: meters with 3-5 cumulative reads crossing two billing rows, a reset, a rejected read between two counts, an estimated count replaced by an actual, mixed plain and cumulative reads on one meter. Exceptions are unchanged by the rule (classification ignores `cumulative`), so only invoices of planted accounts move.
- Blind round-1 program: bills the running count: wrong energy lines on every corpus.

### T3/T4 plan
- Own RNG per corpus (as `_quiet`), new owned groups `revision`, `arrears`, `cumulative` plus their combination accounts folded into the group that owns the rare pair; unowned rows stay equal to the round-1 document (`_assert_quiet` extended).
- Weights in {1,3,5}: about 23 points per new group over 7 corpora (one 5 and six 3s), new total about 295; each new lever alone about 7.8%; blind round-1 program about 75; a first-fit U1 program loses the decoy share. Q4 weight may move from 8 to 10 to stay at or above 5% after dilution.
- Every new no-fit / tie case is settled by the stated verdict; cases left open (two revised plans on one account, a cumulative count that falls without being a reset, a revised plan with no witness) are never generated, each with an EVIDENCE_MAP row (IN-16).

## 4. Risks checked before go
- Blind program on new forms: `csv.DictReader` and `row.get` ignore the extra file and keys; `_plan` copies only known keys. To be confirmed by running WORK/blind_r1 on each new corpus (no crash).
- Shipped data: no edits; `_SHIPPED_DATA`, shipped document and all round-1 checks keep their values.
