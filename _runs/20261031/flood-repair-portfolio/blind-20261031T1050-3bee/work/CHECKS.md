# CHECKS dae9563 (BLIND_DIR = _runs/20261031/flood-repair-portfolio/blind-20261031T1050-3bee; paths relative to it)

| # | command | input | what it showed |
|---|---|---|---|
| 1 | `python3 .../name_session.py dae9563` | - | opencode match `ses_e6f92aa92ffezqdyxHtz2J4h6c`; codex no match |
| 2 | `ls -laR BLIND_DIR`, `head`/`wc -l`/`file` on data files, Counter probe of proposals/permits/crews | environment/data | 192 rounds (10..160 rows), 1 lowercase `a` risk_override, `4.5` households, 3 `revoked` permit rows, 24 blank lines in audit_queries.txt |
| 3 | graph-stats probe (python heredoc) | environment/data | two big rounds: 160 proposals/394 conflict pairs and 150/366, each one connected component |
| 4 | `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py environment/data out` (first version, lb-pruned clique-cover B&B) | environment/data -> out | **did not finish**: killed by the 120 s tool timeout, no documents written (>120 s, over the 20 s limit). Counted as the one allowed crash |
| 5 | `perl -e 'alarm 60' python3 work/diag/probe.py` | environment/data | stuck in the 160-proposal round: 400k solve calls in 43 s and still going |
| 6 | `python3 work/diag/dump.py` + `work/diag/tw.py` | big-round conflict graphs | degree 2..6; min-degree elimination width <= 16 (both rounds) |
| 7 | `perl -e 'alarm 120' python3 work/diag/proto.py` (memo + reverse min-degree elimination branching) | both big graphs | 160 round: optimum 60229 (55 picks) in 4.82 s; 150 round: 61608 (53 picks) in 2.54 s |
| 8 | `python3 work/diag/proto_fill.py` (same with min-fill order) | both big graphs | same optima 60229 / 61608 (cross-check), slower 5.58 / 5.24 s |
| 9 | crash fix: replaced the MWIS class in app/derive_report.py with the proto version (one time) | - | `grep` shows the one solve call updated |
| 10 | `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py environment/data out` | environment/data -> out | **real 7.64 s** (user 7.42), exit 0; all 9 documents written. 7.64 s is 38% of the 20 s limit (local Python 3.14; container has 3.12 and 2 CPUs) |
| 11 | `python3 work/diag/check.py` | out/*.json | summary: 192 rounds, 173 planned, 19 rejected, 1165 selected, total_benefit 2685141; counts and sums add up; id lists sorted; rejected rounds have [] and 0 |
| 12 | same check.py | out/data_quality.json | 19 rejected rows (codes: UNKNOWN_PROPOSAL x8, INVALID_INPUT x8, DUPLICATE_PROPOSAL x2, NONPOSITIVE_BENEFIT x1); conflict_pairs 3825; by source crew 913 / permit 1511 / exclusion 1955; withdrawn_permit_rows 589 |
| 13 | same check.py | out/policy_audit.json vs audit_queries.txt | 2400 rows = 2400 non-empty lines; key counts: rejected rows 4 keys, VALUE 13, PAIR 10; 0 conflicting PAIRs with both selected; every VALUE `selected` matches summary; every benefit = households*(rate+uplift)+premium |
| 14 | same check.py | out/region_*.json, out/segment_*.json | key order as contract; per-doc sums add up; 4 regions sum to 2685141 / 1165 = summary; commercial 420 / 1040381, public 468 / 1330852; book B3790 everywhere |
| 15 | `cmp app/derive_report.py out/derive_report.py`; `grep -n "_runs\|/Users"` | program | identical copies; no hard-coded paths |
| 16 | `ps -axo pid,rss,command \| grep python` | - | only pids 1033/1036 (`parked_scan/clean/solve_raw.py`, another session's job, not mine); none of mine |
