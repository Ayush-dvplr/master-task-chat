# Blind report: e32d5b7 flood-repair-portfolio (P13)

## Files read, in order
1. RUN folder listing
2. instruction.md
3. environment/data/contract.md
4. work/TODO.md
5. environment/Dockerfile
6. Heads and stats of the data files: manifest.json, benefits.ini, proposals.csv, segment_codes.tsv, permits.csv, region_codes.csv, crews.tsv, audit_queries.txt, sites.jsonl, exclusions.json

## Timing
- Start 00:14:58 IST. The program was first written in full at about 00:18, which is about 4 minutes in.
- name_session.py printed `codex: no match` / `opencode: ['ses_e67923b1dffeE2givMc6rnDPnY']`. I cannot confirm that this ID belongs to this session.

## Self-check (shipped data only): PASS
- All 9 output files exist. Totals agree across summary, region and segment files: 192 rounds = 173 planned + 19 rejected, 1165 selected, total benefit 2685141.
- Rounds are listed in order and every selected list is sorted. No selected portfolio contains a conflicting pair, and the crew cap holds. The audit file has 2400 rows, matching the non-blank query lines.
- For all 171 rounds with n <= 26, the DP result matches brute force. The two large rounds (n = 160 and n = 150) were checked for feasibility only.
- Wall time was 0.49–0.56 s against the 20 s limit.

## Crash fixed: yes (once)
- The first run did not finish (it was killed after more than 120 s, with no outputs) because branch and bound stalled on round R57468 (n = 160).
- The fix adds a min-fill elimination order and an exact variable-elimination DP, used when the width is 24 or less (it is 18 here). The old branch and bound is kept as a fallback for wider cases.
- The self-check later showed that this fallback is wrong on 8 small rounds. I did not rework it, because the rules forbid logic changes after the self-check. It is never used on the shipped data, but wider inputs would reach it.

## Lessons for the master
- Exact max-weight portfolio search with n = 160 needs a structural method (tree decomposition / DP); plain branch and bound stalls.
- Check the solver against brute force on small rounds before the first full run. That catches wrong pruning early.
- Big-int weights (benefit << n plus a rank bit) make the lexicographic tie-break exact for any solver.
