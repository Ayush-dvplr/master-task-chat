# BLIND REPORT dae9563 flood-repair-portfolio (P13)

Session rename: `name_session.py dae9563` printed opencode match `ses_e6f92aa92ffezqdyxHtz2J4h6c` (codex: no match). Started 10:57:33 IST, finished about 11:08 IST.

## Files read, in order
1. instruction.md
2. environment/data/contract.md
3. environment/Dockerfile
4. Heads, `wc` and Counter probes of environment/data/: manifest.json, benefits.ini, proposals.csv, segment_codes.tsv, permits.csv, region_codes.csv, crews.tsv, audit_queries.txt, sites.jsonl, exclusions.json
5. blind-20261031T1050-3bee.judge.md (only at step 5, after FINAL_REPLY.md was frozen)

## Minutes to first full write
About 3 minutes (app/derive_report.py fully written about 11:00).

## Self-check (work/CHECKS.md, 16 lines)
- Timed run on the shipped book: real 7.64 s, exit 0, 9 documents (38% of the 20 s limit; local Python 3.14, container has 3.12 and 2 CPUs, so expect it to take longer there).
- check.py on out/: totals and counts add up across summary, data_quality, policy_audit, regions and segments; 2400 audit rows = 2400 non-empty query lines; no conflicting pair has both proposals selected; id lists sorted; app and out copies identical; no hard-coded paths.
- Big-round optima cross-checked between two elimination orders (60229 / 61608).
- Result: PASS on these internal-consistency checks. It did NOT recompute anything independently from the input tables, did not enumerate small rounds and did not rerun on altered data.

## Crash fixed
Yes, once: the first solver (clique-cover branch and bound) ran for more than 120 s on the 160-proposal round. I replaced it with memoised branch-and-reduce and the run then took 7.64 s.

## Judge estimate
lower 6/30 = 0.20, upper 9/30 = 0.30; 7 process criteria not performed (R1-R7: independent recomputations and altered-copy rerun).

## Lessons for the master
- The rubric is 70% independent recomputation outside the program (benefits, PAIR sources, rejections, regions, segments, small-round brute force) plus an altered-copy rerun; consistency checks score nothing.
- Write one separate checker that rebuilds each figure straight from the raw tables, not from fields the program emits.
- MWIS on 160-node sparse graphs: plain B&B blows up; memo + reduction + min-degree branching finishes in under 5 s.
- Log the timing compared with the 20 s limit as a percentage (R8 PASS came from this).
- Keep `main` split into named functions for R9.
