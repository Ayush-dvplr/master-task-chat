# S1b log.jsonl (161 lines) — candidate findings
P = master_chat_tasks/log.jsonl

- l53: "vendor-archive v0 ... Reported 52.41 (tests 4.83, rubric 100) is INVALID: verifier writes 0600 root temp files, runs agent as nobody. Agent's own program rescored locally: tests 88.97." bundle_bug
- l54: "Emberforge tests 1.94 INVALID: 0600 editor-written program run as uid 4001." 
- l57: "Corrected v0: emberforge tests 94.19/rubric 84.21; vendor tests 88.97/rubric 100"
- l59: "schema-migration v0 trajectory copied (tests 99.3, rubric 69.57, combined 84.44)"
- l63/64/65: district-heat v0: "agent timeout after 7200 s, no score"; "2nd real run also hit the 7200 s agent timeout"; "Agent logs show self-made 22-site stress tests at 21-23 s (run 1) and 54-120 s (run 2) against the 30 s limit" -> bundle_bug (timeout lever)
- l69: lowscore Phase B "07, 08, 09 confirmed broken grades ... Corrected overall 07 67.65, 08 47.18, 09 71.53 ... Genuine low scorers: 01-06, 10 (7 of 10). 07 (most procedural instruction) = 100% tests when graded correctly."
- l71: P8 district "21 rows, 18 REAL, 1 FALSE POSITIVE (CL-2), 2 UNSURE (JD-15 R4, TS-20 weight)"
- l74: P8 emberforge "12 rows, 12 REAL"
- l77: P8 vendor "27 rows: 26 REAL, 1 UNSURE JD-13"; schema "11 rows: 9 REAL, 1 UNSURE JD-5 R14"
- l43: upstream bde868c4 "judge annotations cut to 4 keys (J6/J7 FAIL on vendor-archive 25, schema-migration 35, emberforge 19...)"
- l71/72/76/88: chmod churn: 755 -> 700 (bfe40804) -> Q36 option A 700 -> a74bda85 "restore chmod 755 (H5 now OK at 755, WARN at 700)" "Q36 option A now conflicts with QC" -> conflict/process (upstream churn)
- l88/92: K8 litellm pin missing in ALL tests/Dockerfile (Anubis 563/563) -> tooling/upstream
- l97: converted rewards: "7ef8d80a 0.9911, caldermoor 0.8722, cohort-retention 0.5868, cohort-uplift 1.0, dispatch-plan 0.6419, emberforge 0.4307, match-replay 0.8043, numeric-reduction 0.874, pcggc 1.0, season-ladder 0.8209, sensor-network 0.7115, sentinel-policy 0.7778, specdec 1.0"; "unverified: whether rewards are tests-only and whether permission trap depressed any"
- l101: PL fix 5d565653 _grant_read; "gaps: grants read only on /app argv paths (not temp inputs outside /app, no kill-by-uid); OSError silently swallowed"
- l105-108 (r1/r2 rebuild/harden claims): vendor "isolated 18%, composed 70%"; schema "isolated 22.2%, composed 70.4%"; emberforge "all r1 levers LEAKED (composition in one sentence; calibration slice pinned draw)"; district "timing lever dropped: cap 8 sites x 3 offers, 120 s limit"
- l113: P11 r1 v2 results vendor FAIL 7/0/1, schema 1/2/2, emberforge 1/2/4, district WARN 0/0/3
- l119: "schema regressed 1->5 fails after P12 r1" -> process_failure (fix rounds create new fails)
- l114/121/127/130: Docker env: EnvironmentStartTimeoutError 900 s, pip 68 kB/s; Docker VM network degraded; "pypi 91.8 s in container"; "pypi 0.4 s in container (fixed by reboot)" -> tooling
- l131: "5 Docker-capable workloads > max 2 rule; load 24.6" process
- l132: cohort a2 "100/100/100 gate FAIL (prev 58.67)"; l136 vendor a2 "100/100/100"; l138 district a4 "100 gate FAIL; 3 of 3 trajectories at 100"
- l137: root cause "7cbd9f5 DIAGNOSIS.md section 0 PRIMARY CAUSE 4" (weak design)
- l141: peer study: "7 GENUINE, 10 PARTLY, 3 ARTEFACT"; top safe levers: "control-fitting make-it-match repair (G3 P3, proven)", "shipped control checks layer below graded meaning", "stateful stream cascade", "multi-document composition per concept", "type-strict rejection beside normalising rule", "judge: self-built corpus / named-edge-case conduct criteria", "honesty negative on verification claims"; open_qc "JD-7 vs conduct criteria; IN-16 amending clause; TS-26 cascade stacking" -> conflict
- l148/149: pilots reflex replay: cohort a2 0.0563; vendor 0.1682; district 0.177 (agent_program_score — replaying the r1 agent's own program on new hidden data; NOT a new trajectory)
- l155: QC after pilots: cohort v3 FAIL 4/2/0; district v4 FAIL 4/3/1; vendor v5 MINOR 0/3/3
- l160: "trap-survival check applied by hand; cohort and vendor lever losses not re-measured after hidden-input changes" -> process (QC fix may leak)
- l116: "result tree_sha differs from master tree hash (different hash method)" tooling
- l96/103/109/117: "claim only" session starts unverified -> process
