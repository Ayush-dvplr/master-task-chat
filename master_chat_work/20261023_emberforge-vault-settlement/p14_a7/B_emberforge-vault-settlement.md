# Phase B: emberforge-vault-settlement, attempt 7: how it is built and where points were lost

Evidence paths: TASK = `master_chat_work/bundles/emberforge-vault-settlement`; RUN = `.../traj_a7/job/trajectory/claude-opus-5/Run 1`; local runs under `OUT/work/`. Trajectory step numbers are 1-based (step N = `steps[N-1]` in `agent/trajectory.json`).

## 1. Inventory

**Task.** The domain is a fantasy crafting-guild season settlement. The archetype is a rulebook-driven batch settlement program with a hidden parameter draw and an exact-optimum allocation. The agent sees `/app/data` (`environment/data`, 24 files).

**Rulebooks** (bytes):
| File | Bytes |
|---|---|
| rulebook_admission.md | 2348 |
| rulebook_identity.md | 2228 |
| rulebook_editions.md | 1484 |
| rulebook_charge.md | 2018 |
| rulebook_scarcity.md | 2647 |
| rulebook_salvage.md | 2675 |
| rulebook_requisitions.md | 2544 |

**Other notes** (bytes):
| File | Bytes |
|---|---|
| invariants.md | 3100 |
| record_shapes.md | 5134 |
| convention_register.md | 4074 |
| finding_codes.md | 2406 |
| clerks_digest.md | 755 |

**CSV data** (data rows):
| File | Rows |
|---|---|
| crafting_ledger.csv | 310 |
| recipe_editions.csv | 97 |
| reagent_acquisitions.csv | 55 |
| artifact_catalogue.csv | 20 |
| reagent_registry.csv | 14 |
| smith_identity_events.csv | 14 |
| vault_opening.csv | 14 |
| patch_calendar.csv | 7 |
| workshop_registry.csv | 6 |

**JSON inputs** (bytes): season_charter.json 392, council_rulings.json 933, requisitions.json 705.

**Instruction.** `instruction.md` has 429 words over 13 lines:
- :3 the rulebooks and invariants govern.
- :7 the deliverable `/app/out/settle_vault.py`, which must finish within 38 s on 2 CPUs, rerun byte-identically, and exit non-zero naming a missing file.
- :11 "Each output document is graded whole on fresh inputs."
- :13 no online solution; 7200 s.

**Tests** (`tests/test_output.py`, 3548 lines, rewardkit 0.2.1, weights at 3518-3539). There are 22 checks with 54 positive points:
- 4 structure checks, weight 1 each.
- 7 `whole_*` checks, weight 5 each, all-or-nothing over forge_a..d (`_whole_share` 3306-3323).
- 3 isolated checks, weight 3 each: unit_charge_season_total (iso_unit_charge), cap_release_closures (iso_cap_release), live_window_refusals (iso_live_window).
- 2 mutation checks, weight 3 each, on mut_base, mut_family and mut_grade.
- 6 negatives totalling -10.

**Hidden seasons.** `_build_corpus_dir` (2185) builds every hidden season from a seed and a `Params` draw: ruling set, quantiser, operator order and scarcity basis. Its outputs are the corpus, the embedded rulebooks (with the "not reinstated" and "no apprentice" sentences removed outside the visible season) and the council rulings. Expected values come from `settle()` (636). SEASONS are defined at 2932-2943:
- forge_a..d use `_mix_plan(... live=True)`.
- iso_unit_charge uses `_open_books`.
- iso_cap_release uses `_release_on_the_line`.
- iso_live_window uses `_open_live_window`.
- The mut_* seasons are charter mutations.

**Judge.** `tests/judge.toml` (gpt-5.6-sol, batched, reads the trajectory) has 8 criteria: R1-R4 at +3 each and R5-R8 at -1/-3/-3/-3.

**Reward.** `tests/reward.toml` splits it as tests 0.5/54 per point and judge 0.5/12 per point.

## 2. Rule map (graded rules)

Column key: "Trap stated" means the trap is explained in the text. "Shipped separates" means the shipped data tells the readings apart.

| Rule | Locations (file:line, quote) | Sentence form | Trap stated | Shipped separates |
|---|---|---|---|---|
| Draw recovery (ruling set, quantiser, operator order, scarcity basis) | convention_register.md:10-68 (return schedules, reduction conventions, operator orders, scarcity references, "The council's rulings"); council_rulings.json; rulebook_charge.md:7-10 "the convention ... is not recorded in this rulebook"; :40-41; rulebook_scarcity.md:25-27 | split across files | Y | Y (agent recovered the shipped draw, step 10-12) |
| **L7** per-unit charge (H1-H5) | rulebook_charge.md:14-15 "The base value of a forge entry is the base charge of the artifact it forges"; :39-43 "each yields a whole number before the next applies ... The charge of the entry is the value the last operator yields, multiplied by the number of units the entry forges." | one plain sentence | N | Y (LEVERS.md:42) |
| H3/H4 grade and scarcity operators | rulebook_charge.md:24-35 | one plain sentence each | N | Y |
| H7 apprentice relief | rulebook_charge.md:51-54 (sentence "No entry ... registration patch." removed in hidden seasons) | default + exception | N | N (does not fire on shipped) |
| **L3** cap ledger | rulebook_admission.md:34-41 A4 "A workshop accrues settled charge across the season ... closed for the remainder of the season"; rulebook_salvage.md:42-46 S5 "the charge of its source forge entry leaves the accrued settled charge of the workshop that filed that forge, for every forge entry settled after the salvage" | default + exception in another file | N | Y (LEVERS.md:42) |
| **L6** live window | rulebook_salvage.md:14-16 S2 "among the last three live forge entries ..."; invariants.md:10-11 "**Live forge entry.** A settled forge entry that no salvage has yet been credited against." | implied by a definition | N | N (LEVERS.md:42 "L6 does not fire") |
| **Window identity day** (the actual loss) | rulebook_salvage.md:16-19 "The canonical smith is the one the salvage's own handle resolves to on the salvage day, and the forge entries are read against that canonical smith whatever handles they were filed under."; rulebook_identity.md:14-17 I1; :22-25 I2; :32-34 I3 "A handle filed before a rename or a merge takes effect resolves to whatever it resolved to on that earlier day"; clerks_digest.md:10-12 "for the salvage's smith" | split across files; the two passages pull opposite ways | N (the settling sentence was removed in lp1 r1) | **Y**: shipped credited 37 vs 40, 4 salvages differ (OUT/work sh_o vs sh_a) |
| S6 one salvage per forge | rulebook_salvage.md:50-59 | one plain sentence + order rule | Y | Y |
| S3/S4 returns | rulebook_salvage.md:24-38; rulebook_scarcity.md:32-34 V7 | plain | N | Y |
| V1-V9 vault, floor, index fixed point, retirement | rulebook_scarcity.md:3-47 | plain; V8 fixed point | N | Y |
| A1-A7 admission | rulebook_admission.md:7-57 | plain; A6 extension | N | Y |
| E1-E5 editions | rulebook_editions.md:8-36 | plain | N | Y |
| I1-I6 identity and reporting | rulebook_identity.md:8-53 (I6 "No identity ... reinstated." removed in hidden seasons) | plain + default/exception | N | Y |
| **Q1-Q9 allocation** (exact optimum) | rulebook_requisitions.md:8-49; Q5 :26-30 "For each reagent the reagent registry marks scarce, the units granted for that reagent across every requisition may not exceed the vault's closing balance"; Q7 :36-37; Q8 :39-44 | one plain sentence each | N | N for the Q5 leak (shipped scarce balances are large; agent allocation matched the oracle at 54) |
| N1-N9 invariants | invariants.md:15-62 | plain | N | Y |
| Record shapes | record_shapes.md:17-101 | data contract | n/a | Y |

## 3. Lever table

The "First coded" column gives the step and timestamp where the logic first appeared.

| id | Weight | Rule graded | First coded | Right first? | Self-test touched it? | Why held or leaked | Fully stated? | Family | Nearest LEVER_RULES |
|---|---|---|---|---|---|---|---|---|---|
| L7 per-unit charge | unit_charge 3, mutations 6, plus a share of the whole docs | H5 :42-43 | step 15 (15:11:14) `charge = value * info["units"]` after per-operator `reduce_fraction` (agent_settle.py:592-594) | Y | N for the targeted check (judge R1: no fractional multi-unit season built); step 84 mutation corpora did not target it | Held: the agent read H5 literally | Y | E | L7 |
| L3 cap ledger | cap_release 3, plus a share of the whole docs | A4 + S5 | step 15, `accrued[src_wid] -= charge_of.get(ref, 0)` (line 755) | Y | N (judge R2: "did not build a targeted season where a credited salvage precedes a later cap-tested forge") | Held | Y | C+B | L3 |
| L6 live window | live_window 3 (fails, but not because of L6), plus a share of the whole docs | invariants.md:10-11 + S2 | step 15, `live = [cand for cand in live if cand["entry_id"] != ref]` (line 752) | Y | N (judge R3) | Held: the variant with only the identity-day change passes live_window_refusals | Y | A | L6 |
| Window identity day (no designed lever) | live_window_refusals 3 + whole_vault_audit, whole_reconciliation, whole_data_quality 15 = **18** (it also fails summary, workshop and guild docs on forge_b..d, masked by the allocator on forge_a) | S2 :16-19 vs I3 :32-34 | step 15, line 735 `identity.canonical(cand["smith_ref"], day) == canon` | N (grader reading) | **Y**: step 22 "candidate pairs where the two readings disagree: 38"; step 24 alt_sv.py "own-day reading: credited 37" (the oracle figure); the agent chose salvage-day, step 91 AGENTS.md and step 93 "Judgments the texts forced" | Leaked: two defensible readings and no visible tiebreak; the tiebreak sentence in I3 was removed in lp1 r1 (LEVERS.md 'Harden lp1 r1' "I3 closing sentence"; DESIGN.md:66; QC_DEFENCE.md:100) | **N, not settled** (IN-16, not a hidden rule) | NEW: "identity time-of-resolution inside a window" | nearest L4 identity (LEVERS.md:13); not in WORK/wrong (wrong/README.md L4 is "applies renames and merges whatever their effective day", a different misreading) |
| Allocator Q5 leak (no designed lever) | whole_summary, whole_allocation, whole_workshop_reports, whole_guild_reports on forge_a = **20** | Q5 :26-30 | step 15, `_capacity` max-flow; rewritten steps 57-61 (15:32) | N | Y: steps 30 and 63 brute force on 6-requisition corpora ("checked 60 fails 0"); INFERRED the shipped scarce balances (~50,000) never let the scarce cap bind | Leaked: scarce flow escapes through the shared guild-out-to-sink edge (`_capacity({'RQ05':(6,17),'RQ11':(9,16),'RQ01':(8,18)},[])` = 51 vs true 48); `solve()` never checks final total == target, so forge_a collapses 160 to 92 | Y | D (exact optimisation) | L3 (fund) in WORK/wrong/README.md:9; no LEVER_RULES lever |
| Judge R1 / R2 / R3 | 3 + 3 + 3 = 9 | conduct: build and run a targeted season per lever | never | n/a | N | No targeted season built; the testing effort went to allocation stress (steps 27-63) and edge cases (84) | Y (criteria plain, meetable: solve.sh:102-132) | J2 conduct | J2 |

## 4. Contrast with the blind solves

**Records.** scores.jsonl rows 1cd546e (Opus, 23 Oct 15:10) and 0c22dae (Codex, 15:30) both show tests 34.7, earned 18.75/54. Their notes say "whole records fail on 4 unseen seasons, L6 live window lever caught". blind_r1/SCORE.md and blind_r2_codex/SCORE.md fail check for check alike.

**Why the numbers differ from a7.** Their 18.75 used the old fractional whole share. P12 r4 (TS-29) changed it to all-or-nothing. Rescored with the current grader (OUT/work/score_prog.py), both blinds get **16/54**, the same as a7, with the same pass/fail set.

**Same root cause.**
- blind_r1_settle.py:449-450 `self.canon(f[3], day) == cn`
- blind_r2_settle.py:362-364 `canonical(f['entry']['smith_ref'], day) == smith`

Both resolve forge handles on the salvage day, and both drop credited forges, so L6 held. iso_live_window gives an identical signature: credited 64 vs 71, SALVAGE_ALREADY_CREDITED 14 vs 16.

**The blind note is a misattribution.** Correcting blind_r1 to the forge's day makes live_window_refusals pass. Its whole docs still fail from a separate charge defect: forge_a guild charge_ember 67899 vs 67753. blind_r1 has no allocator leak (its allocation share was 0.75), so the a7 allocator bug is a7's own.

**Conclusion.** All three strong solvers took Reading A. The real agent failed for the same reason as both blinds on the identity day, plus its own allocator defect.

## 5. Agent behaviour (trajectory autopsy, 93 steps, 40 min)

**Reading (15:00:56-15:01:40, steps 3-7).**
- Step 3: `find /app`.
- Steps 4-6: `cat` of the charter, convention_register, invariants, record_shapes, then all 7 rulebooks, finding_codes and clerks_digest.
- Step 7: all CSVs.

Every rulebook was printed whole. INFERRED: the observations were not truncated (files are 2-5 KB).

**Planning and drafting (steps 8-15).**
- Steps 8-9: ledger statistics.
- Steps 10-12: draw recovery prototypes (/tmp/solve.py, /tmp/solve2.py).
- Step 13 (15:08:53): first create of `/app/out/settle_vault.py`.
- Step 15 (15:11:14): full program, about 10.5 min in. All graded settlement logic (charge, cap ledger, window, identity) is in this write and never changed later. Later edits touched only allocation (32-33, 51, 57-61), salvage returns of unknown reagents (76), and the draw for unknown reagents (77, 85).

**Run and readings check (steps 16-26, 15:11-15:14).**
- Steps 16-17: first run, then chmod 644.
- Steps 18-23: introspection on /app/data.
- **Steps 22-24 are the near miss.** The agent counted 38 disagreeing pairs, built the own-day variant, saw "credited 37" (exactly the oracle), and kept the salvage-day reading.

**Allocation correctness and performance (steps 27-63, 15:14-15:33, about 19 min, the biggest phase).**
- Stress generator, then brute-force comparisons at steps 30 and 63, all matching.
- Timeouts on /tmp/adv (step 50, "rc=124"), then a rewrite of the bound.

**Robustness (steps 64-90, 15:33-15:40).**
- Steps 67-69: determinism.
- Step 70: missing-input test (this earned R4).
- Steps 79-80: an 840-draw recovery experiment.
- Steps 83-84: mutation corpora (outside-calendar acquisitions, missing refs, provisional workshop).

No season targeted L7, L3 or L6.

**Close (steps 91-93, 15:40:44-15:41:03).** AGENTS.md, a final run, then the final answer.

**Final claim vs reality.** The final message states the S2 identity-day choice openly as a judgment and makes no claim of passing hidden checks. R7 did not fire.

## 6. Test design

**Expected values.** The grader's own `settle()` produces them; the oracle `solve.py` matches it on all 10 seasons (0 differing docs). There is no partial credit inside a document. Whole docs are all-or-nothing across 4 seasons. The isolated checks read one field or one finding set.

**Cascade (TS-26 vs G1).**
- One upstream line (agent_settle.py:735) fails whole_vault_audit, whole_reconciliation and whole_data_quality on all four forge seasons. On forge_b..d it also fails summary, workshop and guild reports, plus live_window_refusals.
- This is the natural cascade LEVER_RULES G1 allows: each whole doc grades a different document, and live_window_refusals uses its own isolated season.
- live_window_refusals and whole_data_quality both pay for UNCREDITED_SALVAGE, but on different seasons and through different checks. That is allowed per QC_RULINGS TS-26 (emberforge v5:170 PASS, district v3:185).
- The real problem is not double payment. It is that **a single unsettled reading costs 18/54 (33%) of the tests channel**. The variants also show that one allocator slip costs 20/54 through four whole docs on one season (forge_a).

**stacking_check (OUT/work/stacking_raw.txt, rc 0), hints corrected.**
- Totals: 22 checks, positive 54, negatives -10; judge 8 criteria, 12 positive, batched.
- whole_doc 35/54 = 64.8%: PASS against the >=50% rule.
- format_hidden 2 (3.7%); shipped_only 0.
- The tool's "isolated+mutation 31.5% FAIL" counts the two w1 structure checks as isolated. The real rule checks are 9 isolated + 6 mutation = 15/54 = 27.8%, which PASSES the <=30% rule (the same correction appears in p12_r5/PL_NOTE.md).
- TS-26 duplicates: none.
- AL-28 penalty groups are all <=5.
- Weight-1 checks are the four structure checks only.
- The tool's "J2 conduct criteria: none" is a false negative: R1-R3 are the J2 conduct criteria.

## 7. Judge design
- **JD-7** (run the oracle against the criteria): R1-R3 are met by `solution/solve.sh:102-132` probe seasons, and R4 by the oracle's missing-input path. PASS.
- **JD-8** (behaviour, not figures): R1-R3 check that a season was built, run and inspected. No criterion carries a numeric answer. PASS.
- **JD-15** (conduct criteria): the instruction never asks the agent to build test seasons, so R1-R3 grade unprompted conduct worth 9/12 of the judge channel. They name the exact trap shape: "a forge entry of more than one unit has an operator step that yields a fractional ember value", "a credited salvage ... earlier forge of the same workshop", "already credited ... among that smith's last three settled forges". QC_RULINGS JD-15 has no ruling on J2 conduct criteria yet (PL Q46). district-heat v4:37 FAILed a conduct label that hid a constraint. Here the criteria are hidden from the agent and do not leak rules, but they grade conduct the instruction never requested. RISKY, pending Q46.
- **JD-18** (one code-quality criterion): there is no code-quality criterion. R4 grades the missing-input path, which is behaviour, not code shape. Open per the P12 r5 note (R4 rewritten under JD-18). RISKY unless R4 is accepted as the J4 item.

## 8. QC safety, for each point-losing item

| QC rule | Window identity day (18 pts) | Allocator Q5 (20 pts) | Judge R1-R3 (9 pts) |
|---|---|---|---|
| IN-15 (instruction says what is graded) | SAFE: instruction:11 "graded whole on fresh inputs" | SAFE | RISKY: the instruction does not mention self-built seasons (see JD-15) |
| IN-16 (no significant graded ambiguity) | **NOT ALLOWED**: all three parts shown (graded 18 pts; Reading A from S2:16-19 + I1:14-17, Reading B from I3:32-34; no tiebreak in the 12 note files after the I3 closing sentence was removed). Same class as QC_RULINGS IN-16 emberforge v1:34/v1:228 FAIL, fixed in v2:604 by one settling sentence | SAFE: Q5 one sentence | n/a |
| TS-13 (assert on values, not format) | SAFE (TS-13 emberforge v5:161 PASS) | SAFE | n/a |
| TS-16 (hidden seasons exercise the stated rule) | RISKY: the hidden generator plants rename/merge-straddling windows (forge_a..d, iso_live_window), so the open case is graded (cohort v2:120: "hidden generator must never produce the open case") | SAFE | n/a |
| TS-19 (no environment artefact) | SAFE: `_stage_program` 0644 copy, setpriv uid 4001; no 0600 effect in a7 | SAFE | n/a |
| TS-20 (weights proportional) | SAFE: weights in {1,3,5}; structure w1 only | SAFE | n/a |
| TS-26 (no double payment) | SAFE as G1 cascade (TS-26 emberforge v5:170 PASS); note the concentration (18/54) | SAFE (natural cascade across 4 docs) | n/a |
| AL-27 (graded rules all visible) | RISKY: both readings visible, the grader's choice not uniquely implied | SAFE | SAFE |
| AL-28 (penalty groups <=5) | SAFE (all groups <=5, AL-28 emberforge v5:229 PASS) | SAFE | SAFE |

## Lessons for the master
- The lp1 r1 "giveaway removal" deleted the I3 sentence that was the only tiebreak for a graded fork. Every harden pass needs an IN-16 diff of removed sentences against the graded readings.
- Measure the identity-day reading as a WORK/wrong single-reading solver. It moves 18 points and was never in the wrong set.
- Blind-solve notes attributed the loss to L6. Attribute only after a one-line variant passes the check.
- The agent's brute-force allocator tests used shipped balances, which never bind Q5. Hidden seasons with tight scarce caps are what separate a correct allocator.
