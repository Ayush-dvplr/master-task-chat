# LOG 1e969db
01:46 start; TODO in WORK/TODO.md
01:48 0b done: a4 transform.py copied; stdout shows lever fails = 'no result within 15 seconds' (TIMEOUT not WRONG)
01:52 0c launched g37-meas-a4 / g37-meas-ref (measure.py, cap 300s)
01:53 a4 meas relaunched cap 60s (first try cap 300 killed: long-1 > ~4 min). ref solve.py: hidden .27s long 3.1-3.7s ladder 4.5-4.7s (limit 15 => ratio up to 0.31 > 1/4)
- 02:00 fuzz_a4: 11 seeds x 11 doc-valid perturbations (none,shuffle_pc,shuffle_acc,noncanon,pad,reverse_tiers,ini_shuffle,west_order,north_keys,xml_order,all) = 121 runs ALL EXACT (seed 11 gen assert 'reseller depth' on small world, harmless). Launched meas_a4_flat (flat-1,2: ladder tiers, LADDER_SHAPES sizes, resellers=0) to test a4 at scale without deep chain.
- 02:03 meas_a4 ALL_DONE: long-1..3 & ladder-1..4 all TIMEOUT at 60 s cap (ref 3.1-4.7 s). flat relaunched with resellers=2 (resellers=0 fails sample range).
- 02:09 flat-1/2 a4 EXACT 32.1/50.6 s. Wrote OUT TRIP, DESIGN (NO CORE), HARDEN_REPORT, result json. Tree bbc865f36130 unchanged. No containers of mine running.
