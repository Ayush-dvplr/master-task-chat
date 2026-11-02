import re
O="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261026_tariff-engine-audit-repair"
old=open(O+"/harden_t1/STACKING_CHECK.md").read()
rows=[l for l in old.splitlines() if l.startswith("| ") and l.count("|")==6 and not l.startswith("| test ") ]
rows=[r for r in rows if not r.startswith("| act") and "PASS" not in r]
rows=[r.replace("unowned accounts only","accounts no quiet rule or lever owns") for r in rows]
neg=[r for r in rows if r.split("|")[2].strip().startswith("-")]
pos=[r for r in rows if r not in neg]
new=[]
def add(name,obs,grp,lev):
    new.append(f"| {name} | 5 | {obs} | _check_owned(\"{grp}\", corpora) vs _Ledger | {lev} |")
for s,c in (("fresh_rescaled","fresh, rescaled"),("relocated_rotated","relocated, rotated"),("api_recoded_renamed","api, recoded, renamed")):
    add("revision_accounts_on_"+s,"U1-owned invoices (plans A one fit, B two fits, C no fit), corpora "+c,"revision","U1, U1first (plan B only), N1, N3")
for s,c in (("fresh_rescaled_relocated_rotated","fresh, rescaled, relocated, rotated"),("api_recoded_renamed","api, recoded, renamed")):
    add("revision_row_accounts_on_"+s,"U1+Q3-owned invoice chains, corpora "+c,"revision_rows","U1, Q3, Q4")
for s,c in (("fresh_rescaled","fresh, rescaled"),("relocated_rotated","relocated, rotated"),("api_recoded_renamed","api, recoded, renamed")):
    add("arrears_accounts_on_"+s,"D1+Q3-owned 4-invoice chains, corpora "+c,"arrears","D1, D1zero, Q3")
for s,c in (("fresh_rescaled_relocated_rotated","fresh, rescaled, relocated, rotated"),("api_recoded_renamed","api, recoded, renamed")):
    add("arrears_carried_accounts_on_"+s,"D1+Q2+Q3+Q4-owned 3-invoice chains, corpora "+c,"arrears_carried","D1, D1zero, Q2, Q3, Q4")
for s,c in (("fresh_rescaled","fresh, rescaled"),("relocated_rotated","relocated, rotated"),("api_recoded_renamed","api, recoded, renamed")):
    add("cumulative_read_accounts_on_"+s,"D2-owned invoices + exception rows, corpora "+c,"cumulative","D2, D2file, D2any, Q1")
add("cumulative_row_accounts_on_all","D2+Q3-owned invoice chains, all 7 hidden corpora","cumulative_rows","D2, D2row, Q3")
add("cumulative_meter_row_accounts_on_all","D2+Q5-owned invoices + exception rows, all 7 hidden corpora","cumulative_meter_rows","D2, Q5")
hdr="| test | w | observable | decisive logic | levers whose misread fails it |\n|---|---|---|---|---|"
txt=f"""# STACKING_CHECK: tariff-engine-audit-repair, test-hardening round 2 (15b380e)

Source: `stacking_check.py BUNDLE` output kept in `stacking_raw.txt` (69 checks, 301 positive, -8 negative;
judge 14 criteria, 33 positive, batched), corrected below by reading `tests/test_output.py` (rendered from
WORK/test_output.src.py by WORK/embed.py). Lever columns are measured single-rule variants
(WORK/measure_variants.py; `/tmp/tariff-15b380e/cost2a.json`, `cost2b.json`, `cost3.json`) and Ledger off-flags
(BRANCH_FIRE): U1 = `U1_off`, U1first = `U1_first_fit`, D1 = `D1_off`, D1zero = `D1_missing_is_zero`, D2 =
`D2_off`, D2row = `D2_per_row`, D2file = `D2_file_order`, D2any = earlier non-accepted counts; round-1 columns
unchanged (L11, N1, N1n, N2, N2p, N3, TR4, Q1..Q5).

## (a) One row per test

{hdr}
""" + "\n".join(pos+new+neg) + f"""

Tool hints corrected: the TS-26 "duplicate group" of eight deliverable checks is a static artefact (each reads
a different artifact; unchanged from round 1). The 29 corpus checks compare only accounts no label owns; each
of the 37 owned-account checks compares one disjoint account set (an account carries exactly one label: a
quiet label, a pair, or one of the seven lever labels U1, U1+Q3, D1+Q3, D1+Q2+Q3+Q4, D2, D2+Q3, D2+Q5), so no
account's rows are paid twice (TS-26 PASS). A Q3 miss also fails the U1+Q3, D1 and D2+Q3 chains because those
accounts need several rows to exist (cascade, reported in (d)). TS-13 hints: none.

## (b) Penalty groups by act (AL-28, |w| <= 5 per act)

| act | tests | judge | sum |
|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 PASS |
| deleting or skipping a shipped visible test | negative_visible_test_removed -3 | - | 3 PASS |
| running the package on an edited copy of api_contract.md | - | R10 -3 | 3 PASS |
| claiming a check passed that its output contradicts | - | R9 -5 | 5 PASS |
| naming or reading grader files | - | R11 -5 | 5 PASS |

Tool hint corrected: its "UNMATCHED act" sum 6 joins two different acts (as in round 1). No variant (16
measured incl. blind_r1) fires either negative. AL-28 PASS.

## (c) Weight shares (G3)

| class (by code) | checks | points | share of 301 |
|---|---|---|---|
| hidden or mutated reruns (old corpus checks 123, owned quiet 69, owned lever 75, two_runs 3) | 56 | 270 | 89.7% |
| of which owned lever accounts (revision 15, revision_rows 10, arrears 15, arrears_carried 10, cumulative 15, cumulative_rows 5, cumulative_meter_rows 5) | 15 | 75 | 24.9% |
| of which owned quiet-rule accounts (unchanged) | 15 | 69 | 22.9% |
| shipped data (shipped_* 13, summary 1) | 4 | 14 | 4.7% |
| deliverable / artifact checks | 7 | 17 | 5.6% |

The tool labels the renamed/relocated/owned checks "isolated" by name; by code each re-runs the delivered
program on a generated hidden corpus (`_corpus_texts` = `_levers(*_quiet(_base_texts(corpus), seed), seed)`).
G3 PASS. Tests 69 (A3 WARN over 35 kept, TS-23), criteria 14 >= 8, judge batched, judge unchanged this round.

## (d) Cost table (G10), measured, tests share of 301

| program | tests | checks failed |
|---|---|---|
| oracle | 1.0000 | 0 |
| blind round-1 program (WORK/blind_r1) | 0.7508 | 15 (all lever checks; no crash) |
| U1 wrong alone (revisions ignored) / first revision / first fit | 0.9169 / 0.9169 / 0.9502 | 5 / 5 / 3 |
| D1 wrong alone (per-row credit) / no row read as paid 0 | 0.9169 / 0.7708 | 5 / 15 |
| D2 wrong alone (count billed as is) / file order / per row | 0.9169 / 0.9169 / 0.9834 | 5 / 5 / 1 |
| Q1 / Q2 / Q3 / Q4 / Q5 wrong alone | 0.8804 / 0.8970 / 0.7375 / 0.8372 / 0.9136 | 8 / 7 / 17 / 11 / 6 |
| first write (all eight wrong) | 0.5216 | 30 |
| all but one right (best single-rule-wrong) | 0.9169 | <= 92 PASS |

Each new lever alone 8.3% (5-12% PASS). Q3 (26.3%), Q4 (16.3%) and Q1 (12.0%) now cascade into lever chains
(T4 rare combinations). Full table: `WORK/COST_TABLE.md`.

## (e) Rule coverage (G11) and RULE_TRACE

`WORK/RULE_COVERAGE.md` round-2 rows: U1_off, U1_first_fit, U1_first_revision, D1_off, D1_missing_is_zero,
D2_off, D2_per_row, D2_file_order, each fails >= 1 positive test, none fires a negative. Round-1 rows M01-M70
were not re-run this round (14 patch targets moved with the solve.py edit); the reference reading for every
non-lever account is byte-unchanged (snapshot comparison), so their kills stand for the old checks.
`WORK/RULE_TRACE.md`: M71-M77 added (77 graded stated rules plus L11, 13 files, 8 formats); every generator
branch in `_levers_once` has a sentence row.

## (f) EVIDENCE_MAP, UNIQUENESS

`WORK/UNIQUENESS.md` U1 section: plan A three revisions, exactly one fits every paid amount; plan B two fit
(own tiers by the stated verdict); plan C none fits (own tiers). Open cases (two revised plans on one account,
a revised plan with no paid amount, a payment row naming no invoice) are never generated; EVIDENCE_MAP rows.

## (g) BRANCH_FIRE

Shipped 0 for U1, D1, D2 (no `revisions`, no `cumulative`, no `payments.csv`); each hidden corpus: U1 5
accounts, D1 4, D2 6 (plus U1first 3, U1nofit 2, D1zero 10-16, D2row 2, D2file 5-6, D2any 2). 300-seed sweep:
300 ok, 0 crash.

## (h) JUDGE_MAP

Unchanged this round: 14 criteria, 33 positive, probes R4, R5, R12, R13, R14 shown by solve.sh self-check.

## (i) Invocation (G8a)

instruction.md command `python -m tariff <data_dir>` with `/app/repo/src` on the path equals `_cli` in the
tests (unchanged).

STACKING PASS
"""
open(O+"/harden_t2/STACKING_CHECK.md","w").write(txt)
print(len(pos),len(new),len(neg))
