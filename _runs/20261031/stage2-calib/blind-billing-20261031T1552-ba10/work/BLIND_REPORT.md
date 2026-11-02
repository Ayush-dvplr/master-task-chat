# Blind report d830ccb (stage2-calib-billing, P13)

Session rename: `name_session.py d830ccb` at 16:06:38 IST printed `codex: no match`, `opencode: ['ses_e6e77df83ffebNinKBMWWq8wYA']`; I cannot confirm that ID is this session.

## Files read, in order
instruction.md, environment/Dockerfile, environment/data/billing_standard.md, record_dictionary.md, report_layout.md, cycle.json, plans.csv, code_aliases.csv, service_catalog.csv, zone_rules.csv, holidays.csv, rate_card.csv (+cmp with rate_card_final.csv), head of clients.csv, closings.csv, legacy_closings.txt, exchange_register.csv, amendments.jsonl (+tail). The judge file was read only at step 5.

## Timing
Started 16:06 IST. First full write of app/transform.py at about 16:09, so 3 minutes. Written once and not edited after; copied to out/transform.py.

## Self-check
Covered: run on shipped data (13 reports, 1518 billed of 1536 received, residual 0), checking that region and segment totals add up, data checksums unchanged, byte-identical rerun from another cwd and output dir, 19 what-if runs on changed copies (29184 closings, 1.76 s), and a static check for no except, subprocess or network calls. Result: PASS. No crash, so no crash fix (crash_fixed false). Details are in work/CHECKS.md lines 1-16.

## Judge estimate
Lower 11, upper 14 out of 58 positive weight; no negatives fired. Only Q2 matches. Three process criteria were not performed (R12, R13, R14). See work/JUDGE_ESTIMATE.md.

## Lessons for the master
- I fitted one clock offset per handset by majority vote; the rubric fits offsets per day, so 7 of 8 what-ifs drift after a reset.
- The instruction line "each handset differs by one whole number of minutes" pulls toward a single offset; that is the trap, and a self-check on shipped data cannot catch it.
- Ambiguous or empty offset fits should raise, not tie-break or default to 0.
- Process credit was lost cheaply: also run on one extra hand-made extract and log the files the program opens.
- Matching totals on shipped data proved nothing about the what-ifs; build a what-if that shifts one handset mid-cycle.
