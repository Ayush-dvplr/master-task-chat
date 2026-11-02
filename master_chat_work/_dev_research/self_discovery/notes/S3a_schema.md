# S3a schema-migration-plan-repair round outputs (read 23 Oct ~11:55 IST)
Base: master_chat_work/20261021_schema-migration-plan-repair/ (S1) and 20261022_schema-migration-plan-repair/ (S2)

## build/BUILD_REPORT.md
- :3 tests-only, judge not run (no OPENAI_API_KEY).
- :37 shipped feed 8,000 lines incl. 15 malformed lines (=> F lever visible).
- :173 OPEN CONFLICT Q18: TRUTH provenance block (generator) — VB §15.5 passes with it, QC DS-27 fails generator provenance.
- :186 "Careful-agent difficulty is UNVERIFIED."

## hardness_r1/HARDNESS_REPORT.md (21 Oct 17:30-18:45)
- :3 Verdict REBUILD.
- :9 "macOS arm64 with other sessions running (load average 160 to 230), not Docker with 2 CPUs" — solver timing on loaded host.
- :30 S4 careful 0.6268; :31 S4b (right on singles, wrong where two rules meet) 0.7746; SC1 best shortcut 0.1761 (docstring-only edits paid module_claims :91).
- :37-43 S4 definition = "Dijkstra on schema ids ... This is the reflex on LV-MR-1 and LV-MR-2" (auditor's guess at reflex, never measured on a real agent).
- :66-77 underivability: every lever DERIVABLE from shipped data: "The shipped data carries no expected outputs. So 'differs' means the visible inputs exercise every separating pattern, and an agent can confirm each rule by self-checks ... No lever is HIDDEN-ONLY." LV-MR-1: "264 records fail with E_PREREQ_FAILED although no correction belongs to them (oracle: 0), which contradicts M7" (visible anomaly signals bug).
- :80 enumeration planner 1,855 s on 16x4 ladder (185x limit) — D size lever only binds an enumerating agent.
- :105 composition share 32.4% measured vs DESIGN counted 39%.
- :125-127 "Each lever's checks are isolated on supplied inputs ... no lever holds more than 22.5%. So a solver that falls for every NEW-lever reflex still keeps about 63%. ... For S4 to reach 0.20, about 80% of the weight must sit in checks that S4's misses break. Adding checks cannot get there".
- :130 "X5 also passes when two wrongs cancel: FieldView dropping nulls plus ini-only presence give the right answer" (composition can cancel).
- :131 shipped (unrepaired) code earns 14 points (CL-2).
- :166 upstream HEAD moved bde868c4 vs knowledge 9b8229f6; repo-patch archetype moved to repo/ + ci/ layout => bundle fails validator §1.4/§5.5 (process churn).

## baseline_v0 (S1/baseline_v0/TRAJECTORY_RESULT.md, QC_RESULT.md)
- Real run tests 99.30% (lost only module_core_claims_match_archive), rubric 69.57%, combined 84.44. "P3 predicted careful S4 0.627; real run 0.993."
- QC v1 FAIL 8/2/5: CL-2 (unrepaired code earns 13.4%), JD-8 (judge R7-R13 restate rules the tests grade, copyable from contract), AL-27 (three stated rules never triggered), Step 11 (K7,K11,K12,K15,K17,K18,N7 no checker), TS-17 loose ==, TS-24 no process-group kill, DS-27 TRUTH lever taxonomy, IN-12 category.

## rebuild_r1/REBUILD_REPORT.md (22 Oct)
- :7 re-layout environment/repo + environment/ci; `_grant_read` inside `_untrusted_command`; kill-by-uid + flock.
- :19 visible graph/feed regenerated so right and reflex readings agree on shipped inputs (verify_visible.py) — derivability fix.
- :21 instruction no rule count, no trap list, six computed figures.
- :22 70.4% hidden composed worlds (19 worlds, 4-6 levers each), isolated 22.2%, shipped-only 4.4%.
- :23 rule by omission N7; :24 decoy default in shipped core/records.py + README ("treats an empty null_counts_as column as absent"), contract sends it elsewhere; shipped feed shows the boundary on 16 records.
- :56 measured weight lost per single wrong reading: planner 73%, null 49%, decoy 26%, others 26-36%; shipped repo 0.0296.
- :74 "The first two Docker oracle runs scored 0.207 and 0.281: rewardkit runs checks concurrently, and the new kill-by-uid in `_stop` killed other checks' children; an flock around each untrusted run fixed it".
- :74 validator §6.3 failed because solve.py README literal named field_policy.tsv.
- :87 not run: judge, hardness solvers (round notes D), real trajectory.

## P12 r1-r3 PL_NOTEs (S2/p12_r*/PL_NOTE.md)
- r1: 5 REAL 0 FP. TS-13 split three-part check into three: "Effect: the tests channel gets marginally easier (+2/137 for any build that ships a working archive)." => QC rule (TS-13 single-property checks) pushes toward isolated checks, against composition rule 6. TS-23 >35 check warn kept.
- r2: 9 REAL 0 FP (QC v3 after r1 — log l119 regressed 1 -> 5 fails). IN-16 float spaces, CL-5, TS-25 argument guard -> negative, JD-2/15/5 code-quality criterion -> negative (-3), AL-2, AL-27, DS-15.
- r3: 5 REAL 0 FP. AL-27: seven stated rules given triggers inside hidden worlds: "Each one-rule-broken variant now scores 0.66 to 0.74 (before: 0.97 to 1.00)." TS-13 again; DS-18 idempotent solve.sh. Positive total 136->137 "because the kit allows weights 1, 3 and 5 only".
- No real trajectory after rebuild_r1 recorded (scores.jsonl) => rebuild levers UNMEASURED.

## Derived points
- SC-a process_failure: careful-solver prediction 0.627 vs real 0.993 (second task where build-time S4 under-predicts).
- SC-b agent_behaviour/lever_leaked: when shipped data exercises every separating pattern, careful agent self-checks (anomaly like E_PREREQ_FAILED with no correction) find the rule — visible anomalies are tells.
- SC-c qc_rule_trap: TS-13 (one property per check) and TS-23 (>35 warn) both push weight toward isolated checks, contradicting study rule 6 / D6 composition design; AL-27 (every stated rule must be triggered) is actually useful: raised per-rule loss from ~0 to 0.26-0.34.
- SC-d tooling: kill-by-uid under concurrent rewardkit checks broke oracle (0.207/0.281); fix flock.
- SC-e lever_leaked: composition can cancel (two wrongs right).
- SC-f process_failure: upstream archetype layout change mid-build forced re-layout.
