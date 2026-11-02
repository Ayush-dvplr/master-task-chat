# PREMORTEM: how claude-opus-5 solves backdated-entitlement-replay in its first 10 minutes

Written before any other design file. Assumes the design sketched in the build notes: one program
`/app/out/derive_report.py --input <dir> --output <dir>`, 14 flat files in /app/data, a rule register,
per-account latent anchor day (1-28) and proration basis (actual | thirty) recovered from the account's
own paid invoices, backdated corrections replayed with carry-forward credit lots and transfers.

## Minute 0-3: reading order
1. `instruction.md` (job, output paths, exactness, rerun promise, invocation, 7200 s).
2. `ls -la /app/data`, `wc -l`, then `rule_register.md` (it is named in the instruction as the place
   the rules live). Opus follows the register top to bottom.
3. `billing_terms.md`, `correction_policy.md`, `credit_policy.md`, `output_contract.md` in full.
4. `head` of every data file; `legacy_terms.yaml` header ("superseded ... except credit_expiry_cycles").
5. Quick pandas-free inspection: python one-liners over `invoice_lines.csv` and `invoice_register.tsv`.
   On shipped data it sees: every invoice issued with anchor day 1 behaviour (proration days counted to
   the 1st of the next month), every account's prorations consistent with anchor 1 / actual.

## Minute 3-8: the program it writes once
- Loads everything with csv/json; Decimal with ROUND_HALF_EVEN (the glossary says half-even once).
- Fit: loops anchor 1..28 x basis {actual, thirty}; rates the account's invoices; on first candidate
  that reproduces the lines it `break`s (H8). Most likely evidence set: every invoice of the account,
  or every non-void invoice, compared on proration amounts only (proration is "where the anchor shows").
- Unresolved branch: written as the docs say ("none or more than one -> unresolved") only if the
  sentence is short and in the same paragraph as the fit; when the fit loop already `break`s, the
  ">1" branch is dead code that never runs. On shipped data every account fits uniquely, so the
  branch never executes and the bug is invisible (H9).
- Replay: builds an event timeline per account item; inserts corrections; sorts by
  (date, arrival_seq). Re-rates all window invoices. This part is close to right: the stated replay
  rule is plain and Opus transliterates plain sentences (LEVER_RULES 1C S5 study).
- Credits: per account lots; applies lots by expiry; transfers by log timestamp; overpayment lots.
  Likely slips: expiry boundary read as inclusive ("expires on" = last usable day) when the stated
  rule is exclusive; same-day transfer vs invoice order taken from timestamps (invoices at 00:00)
  when the stated order puts transfers first; transfer cap taken from the original world (requested)
  instead of the replayed balance; credit_expiry_cycles taken from the shipped yaml constant 12 and
  then never exercised because 12 cycles run past the window.
- Writes the 10 output files with json.dump(indent=2, sort_keys=False) following output_contract.md.

## Minute 8-10: self-tests it runs
- Runs on shipped data; checks every file exists and parses; checks invariants (corrected totals sum,
  closing credit = issued - applied - expired +/- transfers). All pass.
- May write a tiny two-account example by hand to check a correction re-rates the next invoice.
- Does NOT build an input with a non-1 anchor, a 30-day-only account, a lot expiring on an issue
  date, a transfer on an issue date, or two corrections out of arrival order (H9): none of these
  occur in the shipped files, and the shipped run already looks complete.

## Per rule: where the first-write program goes wrong and why its self-tests miss it
| rule / source | first-write behaviour | why no self-test catches it |
|---|---|---|
| R-FIT unique fit (S3, P-B) | first fitting candidate wins (H8); ambiguous accounts get the first combination (anchor 1 / actual) instead of unresolved | shipped: every account fits exactly one combination |
| R-FIT evidence = paid only | includes void invoices (rated under the retired default) -> zero fits on hidden accounts whose void invoice disagrees | shipped void invoices coincide with the truth because every shipped account is anchor 1 / actual |
| R-FIT basis on 30-day cycles | prorations only in 30-day cycles do not separate actual from thirty; program picks actual | shipped accounts all have a proration in a 31/28-day cycle |
| R-CYCLE start inclusive (PA1) | a correction or change dated exactly on the cycle start is prorated (zero days or a full cycle) instead of billed in full on that cycle | shipped never has a change on an anchor day |
| R-REPLAY order (PA5) | arrival order instead of effective order for same-item corrections | shipped corrections never overlap on one item |
| R-EXPIRY exclusive (PA2) | lot usable on its expires_on date | shipped lots never expire on an issue date |
| R-SAMEDAY transfers first (PA3) | invoice issued before the transfer on the same day | shipped transfers never fall on an issue date |
| R-CAP after replay (PA4) | moves the requested amount from the log | shipped transfers are always fully covered |
| R-HALF (PA6) | half-up (legacy yaml dead key) or float round | shipped prorations never land on a half cent |
| S5 legacy yaml | ignores the whole file (keeps 12 by guess) or uses dead keys | shipped N=12 runs past the window, so any N >= window length gives the same output |
| coupling anchor -> everything | a wrong anchor moves cycle starts, so it moves before_window rejection, first_affected_statement_month, PA1/PA2/PA3 dates, credits and closing balances in region, segment and summary files | shipped anchors all 1 |

## Per planned judge criterion: does the trajectory show the act?
| probe (template) | expected in a first-write trajectory |
|---|---|
| P-a edge input with a non-1 anchor account | no (H9) |
| P-a correction on a cycle start | no |
| P-a lot expiring on an issue date | no |
| P-a transfer on an issue date | no |
| P-g one account where all 56 combinations were checked, count stated | rarely: first-fit loops never count |
| P-c recompute one corrected invoice total outside the program | sometimes (25%) |
| P-c recompute one closing credit outside the program | sometimes (25%) |
| P-d changed correction quantity moves a corrected total | rarely |
| P-e relocated input and cwd rerun | sometimes |
| P-h missing declared file run | rarely |
| J4 exception handlers act / missing input names file | often yes |
| J6 per-item enumeration of unresolved accounts / rejected corrections | yes on shipped, but shipped list is short |
| J10 order (data untouched, program under /app/out) | yes |

## Redesign trigger check
A first-write program exact on shipped data AND on a fresh hidden seed would require: unique-fit with
counting, paid-only evidence, cycle-start inclusive, exclusive expiry, transfers-first, cap after
replay, effective order, half-even, live yaml key. Each is one plain sentence, so a careful reader
CAN get all of them; the design relies on (1) the fit sitting in the hard branch that shipped never
fires (S2 + S3, H8), (2) the anchor coupling multiplying any fit slip into every document of that
extract, (3) 16-20 small extracts each owning one pair so a single slip costs only its tiers (P-A),
and (4) the void-invoice partial evidence (paid only). Risk accepted: stated-pair replay alone was
solved 3/3 by blinds (LEVER_RULES 1C); the kill test row 4 decides NO CORE.
