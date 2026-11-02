# CHECKS (one line per command: command | input | result)
- `python3 master_chat_tasks/tools/name_session.py e32d5b7` (00:14:58) | - | `codex: no match`, `opencode: ['ses_e67923b1dffeE2givMc6rnDPnY']`
- `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py environment/data out` (00:18:20) | environment/data | did not finish inside the 120 s tool window (B&B stalled on round R57468, n=160); killed, no outputs, no time printed
- `python3 work/probe.py` / `probe2.py` / `probe3.py` | environment/data | B&B made 92k solve calls in 25 s on R57468; min-fill treewidth 18 -> run-failure fix: tree-decomposition DP (solve_dp)
- `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py environment/data out` | environment/data | real 0.49 user 0.27 sys 0.02, exit 0, 9 JSON outputs
- `perl -e 'alarm 300; exec @ARGV' python3 work/check.py` | out/ + environment/data | book B3790, 192 rounds = 173 planned + 19 rejected, 1165 selected, total 2685141; round order sorted, selected lists sorted; region sums = summary (1165/2685141); 2400 audit rows = non-blank query lines; 0 conflicting selected PAIRs; DP vs old B&B mismatch on 8 of 171 rounds, max width 18
- `perl -e 'alarm 300; exec @ARGV' python3 work/check2.py` | environment/data | all 8 mismatches: DP == brute force, B&B != brute force (B&B is only a fallback for width > 24, never used on shipped data)
- `/usr/bin/time -p perl -e 'alarm 300; exec @ARGV' python3 work/check3.py` | environment/data | real 0.62; 171 rounds with n<=26 brute-forced, 0 mismatches vs DP; 2 large rounds feasible (no conflicts, crew cap held); output == out/summary.json
- `ps -axo pid,rss,command | grep python` | - | only harness/other-agent processes, none of mine
- `cp app/derive_report.py out/derive_report.py; /usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py environment/data work/final_out` | environment/data | real 0.56, exit 0, all 9 JSONs byte-identical to out/
