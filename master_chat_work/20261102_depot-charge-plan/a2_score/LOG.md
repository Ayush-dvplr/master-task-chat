# LOG af2d811
- 2026-11-02 00:28:55 rename ok (opencode ses listed); tree 205cb85281c7 matches; a2 out copied (sha in a2_out_sha256.txt); scratch /Users/mac/Desktop/Terminal Bench/_runs/20261102/depot-charge-plan/a2score-20261102T0028

- 00:33 1c: a2 and solve.py on shipped data identical on all 9 docs; a2 delivered reports identical too. Local fuzz copy scratch/fuzz_local.py (paths rewritten, uplift branch = uplift2 = gen_core.uplift shipped test generator). 3a launched: 5 branches x300 seeds, 6 jobs, sequential, logs/fuzz_<branch>.jsonl.
- 00:50 3a shipped 300/300 done (rc 0, 285 s); hidden running. Wrote scratch/targeted.py (13 doc-allowed mutators on hidden renders + blank_lines ref-bug probe). Smoke 2 seeds each: 26 MATCH; blank_lines DIFF data_quality line (ref DictReader skips blank lines -> line off by one; a2 physical line = R21 :44 correct) -> reference bug, not lever. Launched 3b run3b.sh (pid 87309).
- 00:43 step 2 A2_RULES.md written (22 rules + notice format; only divergence by reading: R21 blank-line ref bug).

- 00:45 3a: shipped 300 MATCH, hidden 300 MATCH, hidden_reorder running (50 MATCH so far); 3b targeted 64 MATCH so far. TIMELINE.md written (judge earned R9,R10,R11,R17; lost R12,R14; zeros all process probes).
- 01:03 3a: hidden_reorder 300 MATCH (373 s), uplift2 300 MATCH (534 s); large running (30 MATCH). 3b targeted_all 694/780 MATCH so far.
- 01:20 3b DONE: targeted_all 13 mutators x 60 = 780 MATCH (1649 s, max ref 57.8 s on combo/large); blank_lines 20/20 DIFF data_quality line only (ref DictReader skips blank lines -> line off by n; a2 = physical line; docs silent on blank lines -> not determinate, logged as ref robustness gap, not a lever). Extra probe offgrid_first (first_slot 12:01-12:14, settlements + published moved with it): 12/12 MATCH (ref's one-slot band rotation is absorbed by the fitted k; no report shows k). slot_minutes != 15 not probed: R12 :27 'k from 0 to 95' fits exactly one k only with 96 slots per day -> docs fix slot_minutes 15.
- 01:40 3a large 300 MATCH (2546 s, ALL_DONE). Total 2312 folders, 0 determinate DIFF, 20 blank-line DIFF = ref bug. A2_SCORE.md + result_af2d811.json written (off_route1, pred final 61.4). Steps 4,6 done.
- 01:40 no child processes left; rename re-run; DONE.
