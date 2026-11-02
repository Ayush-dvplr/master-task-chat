# Lever table

Families follow the labels in `master_chat_tasks/registry/levers.json` and its LEVER_PLAN entries: A = hidden composition / scope, B = dependent chain, C = stateful stream, D = green control / wrong answer, E = multi-document or per-item rounding, F = strict vs normalising format, and NEW = control-fitting ("make-it-match"). The registry applies these labels inconsistently (F-19), so family is marked "?" where the source gives none.

Columns:
- **Held/leaked** counts only *real* trajectory evidence: claude-opus-5 runs in `jobs/` or the corrected v0/a2/a4 runs.
- **Replay** marks figures that were measured by re-running an old agent program, or a mutant, against new tests. Those figures are not trajectory evidence (F-31).

## 1. Levers with real-run evidence
| Lever | Fam | Task | Held / leaked (real) | Why | Verdict |
|---|---|---|---|---|---|
| LV-EF-L7: cap and floor both refuse one forge (rule in invariants.md, away from A4/V4), hidden-only | A (+B) | emberforge v0 | **1 held** (lost 10 of 11 points) | if/elif early return; composition never written as a sentence, separating case not shipped (EF1:19,47) | **keep** the mechanism; do not restate it (r1 stated it, see LV-EF-1) |
| K13 tie: "earlier in fiscal order wins" | ?(D-like reflex) + B | dispatch v0 | **1 held** (14 chained checks) | backward DP keeps the later period against a stated rule and its own docstring (D1:21) | **keep** pattern: stated rule vs algorithm reflex, rare exact tie, chained |
| gen_*/generalisation_*/unseen_*/trap_*_inverse hidden worlds | A/B | season-ladder, caldermoor, match-replay, old emberforge | **4 runs held** (8-12 checks each) | the hidden worlds contain situation classes the shipped data never shows | **keep**; mechanism per check UNVERIFIED for season-ladder |
| LV-H01..H05 district v1 | A,B | district v1 | 5 leaked (reviewer 3/10; v1 solved) | "every rule documented and isolated ... Composition and chaining absent" | **retire** |
| LV-DH-1 size/exact-search 20-22 sites | D | district r1 | leaked as a lever; caused two 7200 s timeouts | the agent "strengthened the bound" promised in the instruction (DH2:17,20) | **retire**: process failure, not hardness |
| LV-DH-2..5 (per-value ticks, funded pool, rejected/dup rows, waived weight) | A,B,F,A | district r1/r2 | leaked (a4 100/100) | one explicit sentence each; several state their own trap (DHL:43-49) | **retire** as worded; DH-3 funded pool was DERIVABLE |
| district r2 72% whole-doc + `program.ini [export]` SIGNEDY decoy + omission | B,D,A | district a4 | leaked (100) | decoy "refuted in plain words in the same file description" (DHL) | **fix**: the decoy only works if it is unrefuted near its use (UNVERIFIED) |
| CR-1..CR-5 cohort r1 | A,D,B,A | cohort a2 | 5 leaked (100/100/100) | CR-1 "trap spelled out in the rule"; CR-2 decoy refuted on the same page; CR-5 split across 2 files, each explicit (C3:43-47) | **retire** |
| V0-1..V0-8 cohort v0 | ? | cohort v0 | 8 leaked | rules beside use; instruction listed topics; schema counted "three residuals" (C1:22-33) | **retire** |
| LV-VA-1..6 vendor v0 / REBUILD RUN, REV decoy, STATE omission, W1 | A,D,A,? | vendor a2 | 6+4 leaked (88.97 → 100) | VA-1/4/6 HIDDEN-ONLY on data but stated plainly; W-VA2 derivable via self-roundtrip (VH:73); RUN shown separately in shipped stream 3 (VD:25); REV refuted on its line (VD:26); STATE exception had its own sentence (VD:28) | **retire**; registry still shows them as "candidate" |
| LV-MR-1..7 schema | ? | schema v0 | 7 leaked (tests 99.3) | all DERIVABLE; visible anomaly 264 E_PREREQ_FAILED contradicts M7 (HARDNESS_REPORT:66-77) | **retire**; registry still shows "candidate" |
| LV-EF-1..4 emberforge r1 (incl. L7 restated) | A,B,D,E | emberforge (v0-era) | leaked except L7 (94.19) | "Round 1 stated the composition in one sentence" (EF2:18) | **retire** EF-1 (it restates L7); EF-2..4 as worded |

## 2. Levers built but never run on a real trajectory (open, n=0)
| Lever | Fam | Task | Evidence available | Verdict |
|---|---|---|---|---|
| CR2-L1 green control, wrong answer | D | cohort r2 | replay single misread 0.85-0.89 (C4:66) | **fix**: weak even in replay |
| CR2-L2 identifiers vs strict fields (make-it-match; shipped e035 ' 4500') | NEW+F | cohort r2 | replay 0.24-0.46, the only strong one (C4:66) | **keep, measure** |
| CR2-L3 refundable balance ledger | C+B | cohort r2 | replay 0.75 | **fix** |
| CR2-L4 weight override across files | A+E | cohort r2 | replay 0.70-0.77 | **fix**: an explicit cross-file override is read, per H1 |
| vendor lp1 L2 unsigned count behind value_sum control | D/NEW | vendor lp1 | replay L2s 0.6636 (STACKING:92) | **measure** |
| vendor lp1 L3 run-ledger resends, L5 JSON bool override beside trim, L6 cumulator per field name | C,F,A | vendor lp1 | "A careful agent that reads Field names, Terms and Runs can code all four rules" (VL:55) | **fix** before a trajectory |
| district lp1 L1 receipt, L2 multiplier, L4 4-doc rate, L7 half-even interval | ?,NEW,A+E,E | district lp1 | reflex 0.177 (old a4 program) | **measure** |
| LV-EF-5 clerks_digest.md decoy (5th note counts same-day forge) + N3 omission + 5 mixed seasons | D,A,B | emberforge r2 | engine following the decoy loses 78/101 (mutant only) | **measure**; "how often a frontier agent misses is unmeasured" (EF2H:101) |
| schema rebuild levers (decoy in shipped code+README, omission N7, AL-27 triggered precedences) | D,A | schema rebuild + p12_r3 | single wrong reading loses 26-73%; one-rule-broken 0.66-0.74 | **keep AL-27 triggers, measure** |
| LV-DPR-01 tie / -02 fallback-decoy-omission / -03 amendment / -04 rejection | D,D+A,?,? | dispatch r1 | v0 replay: 01/02 held, 03/04 leaked; v0 solver 0.168 | **keep 01** (real-run support from K13), measure 02 |
| sensor H1-H4 (irregular acceptance rows, negatives stand down unless clean) | ? | sensor r1 | mutants 0.129/0.081 | **measure** |
| LEVER_PLAN L5 strict beside normalising, L6 scope by definition | F, A | none | none | **open** |
| LV-001..LV-020 web candidates | mixed | none | never used | **retire** from active use; keep as an idea list |

## 3. Peer low-score study levers (`levers_found.json`, n=1 per task)
| Group | Ids | Result | Verdict |
|---|---|---|---|
| Held, costly | #20, #21, #24 (04); #27, #28 (05 decoy + chain, "boundary unexercised"); #53, #54 (08 inverted cross-file field, ordered write-ups); #64, #65 (10 staged cascade) | held in a real peer run | **keep as patterns**; each relies on a rare boundary or downstream chain the shipped data does not exercise |
| Beaten | #33, #35, #36, #42, #55-57, #61-63 | leaked | **retire** |
| Withheld-constant + digest template (01/02/03/06) | rank-1, 300.4 pp | not QC-usable (IN-9); agent brute-forces it (match-replay steps 9-93) | **retire** |
| Families D/E/F as standalone, time levers | — | ~0 pp (SYN:69, :86) | **retire** as standalone; usable only as composition partners |

## Totals (real evidence)
- **Held:** 4 mechanisms (EF L7; dispatch K13; converted hidden-world situation classes, 4 runs; peer held set).
- **Leaked:** about 46 registry levers (18 recorded plus 22 de facto plus district r2/vendor REBUILD extras).
- **Untested:** all r2/lp1 levers, about 20, n=0 (F-34).
- **Pattern across held levers:** each needs (a) plainly stated rules, (b) a natural code shape that is wrong only in their interaction, a tie or a boundary, (c) no shipped file that contains the separating case or confirms the full answer, and (d) a chain that multiplies the miss.
