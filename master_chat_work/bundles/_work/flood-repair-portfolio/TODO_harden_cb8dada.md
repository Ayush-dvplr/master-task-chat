# TODO harden r2 cb8dada (prompt 20261101T1127_harden.md)
R=/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/harden2-20261101T1130

## P0
- [x] rename session (opencode match ses_e6a4ec0a6ffedV8woIzac138g8, codex no match)
- [x] read rule files; fingerprints; kit HEAD 5574d77e
- [x] BUNDLE tree cd11476e6e14; WORK/h2_a1, OUT, R dirs
- [x] OUT/TRIP.md (R3 items: files never opened, shipped-fitted literals, where checking stopped)
## P1
- [x] read test_output.py hidden-tier structure (generator, seeds, weights, per-book call)
- [x] prototype hidden books: h2_a1/proto_gen2.py (H base list x20 = 40 large rounds), drive2.sh; firstwrite_program.py (a1 step 11), allbutone_program.py (ref, single BFS start)
- [x] kill1 running (logs/kill1.log, container cb8dada_k1, seeds 815301/822402/833503, CAP 40)
- [x] Docker kill table: a1, dae9563, elim, vebest, strong, first-write, all-but-one; ref busy/unbusy
- [x] Lever 2 search (quiet branch / LC1) or "none found" evidence
- [x] OUT/DESIGN.md; stop DESIGN READY / NO CORE; WAIT for go (DESIGN READY sent 11:55, waiting for go; design rep30 seeds 815301/822402/833503)
## P2 (go 11:56, master corrections 1-3)
- [x] assemble_tests.py roundtrip == current test_output.py (before edit); check-body digest before
- [x] hidden_meta.json H1-H3 rep30 seeds 815301/822402/833503 -> assemble -> test_output.py; digest after (only _BOOKS diff)
- [x] generator shape asserts over 300 seeds (rep30 spec) in Docker
- [x] corr2: fork1 SURVIVORS 4 before fix; fix in tests_template _launch (Popen start_new_session, killpg + sweep uid nobody, _stop_untrusted); fork2 SURVIVORS 0 (incl setsid escapee); digest_checks2 (no _BOOKS/_launch/_stop_untrusted/2 imports) b1d31eb4 == before
- [x] corr1 DONE: oracle 1.0 VERIFIER_SECONDS 40.85; a1 0.2778 (30/108) VERIFIER_SECONDS 146.65 (<=2430); logs/v_oracle.log v_a1.log. Was: verifier tests-only in Docker with oracle and with a1 (a1 <= 2430 s) else rep20
- [x] LEVERS.md r2 (12:08), QC_DEFENCE r2 rows, EVIDENCE_MAP r2 rows (12:14)
- [x] COST_TABLE r2 section (after costrun: R/logs/ct_*.log, costrun.done)
- [x] (12:38 TRUTH updated 043e5b280055, precheck CLEAN after) truth_facts.py in Docker (R/logs/truth_facts.log) then h2_a1/truth_update.py on TRUTH.md (run last, after gates for provenance)
- [x] xref_check 0 (36 entries, 0 findings 12:38)
## P3
- [x] stacking_check -> OUT/STACKING_CHECK.md (hand TS-26 PASS)
- [x] cost table run (COST_ALL_DONE) (costrun.sh started 12:12; ct_a1 done 30/108 167.18 s)
- [x] precheck CLEAN 12:19 (rerun after TRUTH update)
- [x] exe_copy lanes (oracle x3, owner, nop/stub/forgery): G=_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818; lane1 started 12:21; lane1/lane2 done (1.0 x3 124-151 s, owner 1.0 125 s), nop 0.0, stub done, forgery running
- [x] sync Tasks_INPUT
- [x] HARDEN_REPORT.md, result_cb8dada.json; rename again
