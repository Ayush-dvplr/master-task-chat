# S3a district-heat-flex-procurement round outputs
Base: master_chat_work/

## harden_r1 (20261021_district-heat-flex-procurement/harden_r1/)
- DIAGNOSIS.md:3 "Verdict: REBUILD. Every lever is HIDDEN-ONLY on the data, yet a solver right on each documented rule scores 1.0. Of the 98 weight, 58 sits on checks every lazy reading passes."
- DIAGNOSIS.md:30-36 why each lever leaked: LV-H01 "a spec sentence next to its use" (L130); LV-H02 "a spec pointer at its use ... and a self-test the agent can run, prompted by instruction L15 'ties and zero denominators all have defined outcomes'"; LV-H03 "the applying sentence already orders the steps"; LV-H04 "a verbatim bridge" L185 vs L101-102; LV-H05 "a spec sentence at its use ... self-test is trivial". Common cause: "Each rule has its own 1-rule case and no case combines rules, so isolated correctness gives 1.0."
- DIAGNOSIS.md:48 introduced LV-DH-1 family D "each run must finish within N s ... times out at scale" (size lever).
- DIAGNOSIS.md:65 OPEN CONFLICT Q18 TRUTH `authored_by: null`/`status: reference` (VB 15.5 requires, QC DS-27 fails).
- HARDEN_REPORT.md:14-16 S2 0.086, S4 0.194, S4b 0.381 (arithmetic+measured solver baselines). :24 "S4b is an honest warning: DH-3 is plainly stated, so a careful run probably gets it right."
- HARDEN_REPORT.md:49-51 pre-existing: judge.toml used retired annotation keys, live judge_qc failed ORIGINAL with 24 FAILs.
- HARDEN_REPORT.md:94-103 new judge R5,R13,R14,R15,R17: "the response states that the shared cents are the pool minus the event-region credit"; "The instruction asks for each of these facts in plain words." -> trap topics in reply ask (study rule 2 violation) and echo criteria (later flagged CL-3 in recheck row 11).
- HARDEN_REPORT.md:123-137 UPSTREAM CHANGED mid-session (pulls 15:18, 16:08: 9b8229f6 -> 95401d0e -> bde868c4); tests_qc H5 now prefers chmod 755 over bundle's 700.
- HARDEN_REPORT.md:145-150 not run: Harbor oracle x5, real model, judge (no OPENAI_API_KEY).

## harden_r2 (20261022_district-heat-flex-procurement/harden_r2/)
- DIAGNOSIS.md:15 both real runs "AgentTimeoutError: Agent execution timed out after 7200.0 seconds"; no ctrf.
- DIAGNOSIS.md:17 agent built own 20-22 site stress cases: "the schema explicitly promises 10^15-portfolio groups within 30s, so I'll strengthen the bound rather than hope the hidden extract is tight" (run1 l.6290-6305).
- DIAGNOSIS.md:19 "Both agents had a correct program on the shipped data long before".
- DIAGNOSIS.md:20 root cause = instruction line 3 size+limit sentence + closing-reply ask "the largest event and region your program was run on and how many seconds that run took".
- DIAGNOSIS.md:27-28 both delivered derive_report.py mode 0600 -> r1 verifier would score ~4/139.
- DIAGNOSIS.md:39-47 programs read vs rules: every documented rule CORRECT in both runs, only miss = waiver_signed_missing count, an IN-16 wording ambiguity ("Both agents chose the other reading, which shows the wording gap was real", :50-52).
- HARDEN_REPORT.md:10 LV-DH-1 removed; max 8 sites/3 offers, 120 s.
- HARDEN_REPORT.md:11 run_agent copies as root, chmod 0644, setpriv nobody, kills uid 65534 processes via /proc scan.
- HARDEN_REPORT.md:39-44 hardness redesign: no rule count/trap topic/sizes; closing reply asks six computed figures; composed whole docs 72/100, isolated 24, shipped 4; decoy program.ini `[export] waiver_signed = Y` ("schema.md says any other section of program.ini carries no rule"); omission "for every other event-region". "Every rule stays documented in schema.md ... no hidden rule."
- HARDEN_REPORT.md:74-75 judge R1-R6 "the response states ... global credit_cents 1959002" etc.; R10 honesty -5.
- LEVERS.md:32-53 arithmetic weight lost per wrong reading 23-63 of 100 ("arithmetic, not a solver run").

## harden_lp1_r1 (20261023_district-heat-flex-procurement/harden_lp1_r1/)
- DIAGNOSIS.md:4 a4 run claude-opus-5: tests 100.0, rubric 100.0, combined 100.0. :10 12m51s, 29 steps.
- DIAGNOSIS.md:14-21 agent sequence: step 3 `cat schema.md` (whole file); steps 4-7 read every data file, checked neutrality "relief mod10 [(0, 108036)]"; step 10 wrote program; 13-14 brute-force cross-check all 2000 groups ("bad 0"); 15-16 one fix triggered by schema L56-58; step 19 identities "ALL CHECKS PASS"; 22-24 synthetic extract covering wh_per_tick 4, `[export]` default, unknown region ZZ, duplicate, out-of-range, orphan, cooldown.
- DIAGNOSIS.md:28 decoy SIGNEDY leaked: "The decoy is refuted in plain words in the same file description. The closing reply calls it 'export-tool noise'".
- DIAGNOSIS.md:32 H5 "The rule states its trap ('as soon as it is read, before it is added to anything')".
- DIAGNOSIS.md:43-49 cause: "Every rule is one explicit sentence in schema.md, read in one `cat` at step 3, and several of them state their own trap ... The hidden composed extracts only repeat rules the agent coded correctly the first time. The 72-point whole-document design had nothing to separate. The judge 'states figure X' criteria pay any correct program."
- DIAGNOSIS.md:55-58 new levers L1 green receipt export_manifest.tsv, L2 register_multiplier make-it-match, L4 rate from 4 docs, L7 per-interval half-to-even in rate_cards.xml header comment.
- HARDEN_REPORT.md:13,53 "The real a4 agent program scores 0.177 on the new tests" (reflex replay of OLD program, not a fresh agent).
- HARDEN_REPORT.md:38 isolated 0.292, whole-doc hidden 0.673, shipped-only 0.035.
- HARDEN_REPORT.md:40-44 judge R1-R4 conduct "constructs its own extract in which ... and checks ..." (accepted under JD-7 per LEVER_PLAN_v1, :86).
- HARDEN_REPORT.md:50 G7 deviation: [check] lines in test-stdout.txt not ctrf ("rewardkit 0.2.1 Score has no message field ... tests_qc B4 forbids writing under /logs/verifier").
- HARDEN_REPORT.md:63 playground.py absent at HEAD (removed in a72c20a4).
- HARDEN_REPORT.md:77 "The kit asks for oracle x5; Ayush set x3".
- HARDEN_REPORT.md:87 "Whether a fresh agent falls for L1/L2 (the receipt) is UNVERIFIED".

## Derived findings
- Composition/whole-doc grading (study rule 6) does not CREATE a miss; it only amplifies one. a4 = 100 with 72% composed weight. -> rule 6 WEAKENED (necessary multiplier, not sufficient).
- Decoy (rule 5) leaked when the authority sentence refutes the decoy in plain words beside it.
- Size/time lever (family D) caused 2x 7200 s timeouts, not low scores -> process failure; retire.
- Stating trap topics in judge "response states" criteria (r1) = rule 2 violation introduced by our own hardener.
- The agent's habits: reads whole spec in one cat; checks neutrality properties of data; brute-force cross-check; builds synthetic extract covering every documented edge class; stops after identities pass.
