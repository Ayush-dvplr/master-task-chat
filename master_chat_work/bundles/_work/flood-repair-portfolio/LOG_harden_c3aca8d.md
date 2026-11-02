# LOG c3aca8d harden-a1 (time | step | rc | result)
14:21 IST | setup WORK/h1_a1, tree cd11476e6e14, copied a1 + dae9563 programs | 0 | ok
14:29 IST | bench1 ref/elim/a1/dae per-round 160-node lattices | 0 | ref 0.05-0.17s elim 0.22-0.55s a1 1.2-4.1s dae 8.8-34s/TIMEOUT
14:29 IST | bench2 started without START=yes (dockfree said no) | killed | rule slip, rerun after START=yes
14:41 | 0d prep | 0 | wrote h1_a1/proto_gen.py, timer.py, book_drive.sh, elim_program.py (a1 I/O + verifier min-fill DP); host gen check K=30 ok (70 rounds, 5309 rows); waiting dockfree START=no
14:51 | bench3 book-level K=30 (ref/elim/a1/dae, busy core) | partial | ref 1.1-1.5 s, elim 7-11 s EXACT, a1 57-90 s, dae TIMEOUT 90
14:51 | bench4 strong sweep solvers per round (strong.py: sweep over min-fill/rev/min-degree order) | started | R/bench4.log
14:58 | bench4 sweep over elimination orders | killed early | sweep_mf/mfrev/md TIMEOUT 60 s per round (linear sweep over elim order is useless); bench3 broke after my book_drive.sh edit (b14a dae, b13b missing)
14:58 | bench5 VE strong solvers 8 cfgs | ALL_DONE | totals ref 0.45 s, elim 2.18 (4.9x), ve_mf 1.59 (3.6x), ve_md 1.18 (2.6x); all EXACT
15:01 | bench6 pdiag/rows sweep 12 cfgs | ALL_DONE | best VE (md or mf) 0.6-3.4x ref per round, never > 3.5x; all EXACT
15:01 | book7a (ref, busy core) + book7b (vebest elim a1 dae, quiet) on H1 H2 H3 M + K=100 books | started | R/book7a.log, book7b.log
15:12 | book7a/7b ALL_DONE | 0 | hidden H1-M: ref 0.08-0.36 s, vebest/elim 0.2-0.7 EXACT, a1 1.6-10.4 EXACT, dae 5-54 EXACT; K=100 books: ref 2.5-4.7 (busy 4.2-4.5), vebest 19.2-21.1 EXACT, elim 14.0-26.4 EXACT, a1/dae TIMEOUT 60
15:12 | wrote h1_a1/fuzz.py (a1 vs verifier _Ledger on random small specs) | - | waiting dockfree START=no (2 foreign containers)
15:17 | fuzz1 a1 vs verifier 150 random specs | 0 | 150 MATCH, no WRONG: lever is speed only
15:27 | book8a/8b ALL_DONE (K=105/110 t1-t6) | 0 | ref busy 2.73-4.65; vebest 9.8-24.6 EXACT (passes 20 s on 5/6); elim 10.9-30.6 EXACT (passes 3/6... t2 19.26,t3,t4 pass); a1 TIMEOUT 40 all -> NO CORE
15:29 | OUT TRIP.md DESIGN.md result_c3aca8d.json, h1_a1/KILL_TEST.md written | 0 | NO CORE; BUNDLE tree cd11476e6e14 unchanged; no containers of mine running
