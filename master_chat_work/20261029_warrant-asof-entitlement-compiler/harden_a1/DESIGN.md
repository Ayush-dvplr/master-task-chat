# DESIGN: try 3 DESIGN READY, convention lever (harden-g37-a1-opt1, 6740572 warrant-asof-entitlement-compiler)

## Try 3: convention lever (option 1)
Status: DESIGN READY on the 30 Oct bar (final <= 45), with one risk stated plainly below (wide search passes).
No BUNDLE edit made (tree 4c85938aa8d4). Prototype: `WORK/proto_ref/make.py` builds a patched copy of
tests/test_output.py; `WORK/harness/conv_sweep.py` builds tiers, runs the unique-fit search and the kill programs.

### Lever
- Each corpus carries three gateway conventions: HR/contract day clock (H), grant start (S), window boundary (W).
  Shipped and tier_a/b/c keep the shipped ones (H site clock, S k-th qualifying decided_at, W half-open).
- 8 new held-out tiers (variant `conv`, scale 0.05) plant H = one non-shipped corpus zone's clock for everyone,
  S = requested start, W = half-open: C1 91019 Dune, C2 85041 Dune, C3 93029 Ember, C4 96043 Cobalt,
  C5 92023 Brisk, C6 98053 Brisk, C7 94031 Arden, C8 99061 Arden.
- New checks, one artifact each: `conv_<n>_dev_profile_exact` w5 and `conv_<n>_prod_profile_exact` w5 per tier.
  Lever 80 of 152 positive points = 52.6% (old 72 unchanged). Audit and summary are not lever checks: careful
  programs keep them on C3-C6, C8, so they would only pad.
- Why S is never planted as `recorded`: on SHIPPED data both site/decided and site/recorded reproduce all 2249
  observations (unique-fit 2/48, 665 s); a planted `recorded` would make shipped ambiguous for a reading we use.

### Doc diffs (WORK/DOC_DIFFS.md, before -> after)
- D1 corpus_index.md:53 last sentence `The column is an observation; it is never an input to a profile.` ->
  `The gateway conventions belong to the corpus, and its own observations are the record of them.`
- D2 instruction.md:1 last sentence: `...rather than written down anywhere; the reviewer observations in
  access_attestations.csv are the only record of what the gateway did, and exactly one reading ...` -> `...rather
  than written down anywhere, and they belong to each corpus; the reviewer observations in that corpus's
  access_attestations.csv are the only record of what its gateway did, and exactly one reading ...`
- D3 instruction.md:3 `with other zones, instants, configuration layers, people and records,` -> `with their own
  zones, instants, configuration layers, gateway conventions, people and records,`
- D4 instruction.md:11-22 closing message with 8 figure groups -> `Finish with a closing message that names, for
  each convention left to the gateway, the reading the shipped observations show.` (judge J1; feeds R10)
- D5 legacy_runbook.md:3 drop last sentence (`It is reproduced in full because ... behave now.`); remove L11-47
  (one bullet per planted defect, QC_RISKS 2). Keep title, status paragraph, `## Daily run` L5-9.
- D6 time_rules.md:13 `using the contract's own site;` -> `using the contract's own site where that clock is a
  site's;` (a zone or UTC clock would otherwise contradict it).
- Unchanged and checked: time_rules.md:13 rest and :21, access_contract.md:26 and :40 (already say the gateway's
  convention is shown by the observations). No value, no method, no held-out mention anywhere. 3 blinds needed.

### Reference and generator changes (WORK/proto_ref/make.py, every replacement asserted single)
- `SHIPPED_CONV` constant; `World(D, cfg, conv=None)`; `hr_wall()` used by hr_layer and standing_of; approvals keep
  recorded_at; start reading in ticket_layer; closed-window variant at grant live and key listed; `everything(root,
  conv=None)`; `build(..., conv=None)` = generate + attest_from_reference + new `observe()`.
- `observe()` (own RNG `random.Random(seed*13+7)`): appends evidence rows (termination/hire/leave days at instants
  between rival day starts; grant ends under each rival start) only where some rival reading disagrees, then sets
  observed_state of every row by a gateway simulation (World with config re-settled at reviewed_at, gating and SoD
  off; this simulation reproduces 200/200 sampled shipped rows, obs_check.py mode b).
- Generator: one branch only for variant `conv` (25% of late tickets decided after effective_from). Shipped,
  heldout and boundary corpora: RNG streams untouched; shipped data byte-identical. tier_a/b/c gain appended
  evidence rows and computed observed_state (today every generated row says in_effect, which would contradict D2).
- MFA fix (QC_RISKS 1): MFARX `(\S+) (\S+) ...` -> `(.+?) (\S+) ...` (test_output.py:46), so a space-separated
  instant is a record rejected bad_timestamp (time_rules.md:5). Before/after on a1 shipped (proto/t3/mfa_after.txt):
  audit_rejects_exact, heldout_audit_exact, summary_identity_triangle, heldout_summary_exact,
  self_check_partition_exact flip fail -> pass (rejects 980 vs 978 -> 980/980). Oracle tool must reject them too.
- Speed: stamp() memoised, `_epoch` lru_cache (pure helpers; outputs identical, shipped ref x2 1.9 s).
- Existing check bodies byte-identical; new registrations, HELDOUT conv tuple and helpers only (G7).

### Unique fit (WORK/UNIQUE_FIT.md)
Space per tier: H {site, utc, each of 5 corpus zones} x S {requested, decided, recorded, latest} x W {half,
closed} = 56. Brute force, every reading evaluated until its first mismatch:
| tier | build s | rows | instants | fits | worst kill instant |
|---|---|---|---|---|---|
| C1-C8 | 10.6/10.1/19.7/29.7/24.5/27.4/17.1/5.2 | 98-1397 | 92-988 | 1/56 each | 7-13 |
| tier_a 51017 / tier_b 62029 / tier_c 73031 | 25.6/27.6/20.4 | 1064/1306/1054 | | 1/56 each | 13 |
| shipped (unchanged) | - | 2249 | 365 | 2/48 (decided, recorded) | pre-existing, QC_RISKS 8 |

### Kill table (Docker 4 GB / 2 CPU; tests % = (72 + lever kept) / 152; all 8 conv tiers)
| program | what it is | per tier s | conv tiers | lever kept | tests % | loss kind |
|---|---|---|---|---|---|---|
| a1 program | delivered tool.zip, conventions hard-coded | 1.2-1.6 | DIFF dev+prod x8 | 0/80 | 47.4 | WRONG |
| P2n careful blind | reads new docs + legacy code; scores H {site, utc} x S {requested, decided, recorded} x W {half, closed} jointly | 6.7-9.4 | DIFF dev+prod x8 | 0/80 | 47.4 | WRONG |
| P0s first-write | shipped conventions fixed | 6.4-6.9 | DIFF x8 | 0/80 | 47.4 | WRONG |
| P3b binary | legacy vs current per convention | 7.1-8.5 | DIFF dev+prod x8 | 0/80 | 47.4 | WRONG |
| P4o all-but-one | wide H and W, S fixed decided | 6.7-7.8 | DIFF x8 | 0/80 | 47.4 | WRONG |
| P6o careful wide | H {site, utc, every zone} x S {requested, decided} x W | 11.8-17.4 | EXACT x8 | 80/80 | 100 | none |
Old tiers (tier_a/b/c with new observations) and shipped: every program EXACT. Crash/timeout share 0%.
KEY QUESTION: the careful blind built from the new docs (P2n) loses 100% of lever points. A careful program that
also scores every corpus zone's clock (P6o) loses 0%: the lever relies on agents not extending the HR clock
search past site and UTC. a1 scored only legacy-vs-current variants (trajectory steps 37-38, vA-vE), as P3b does.
P6o fails bar (e) and "none > 70"; if the 3 fresh blinds search per-zone clocks, the lever is gone for them.

### Cost (measured, Docker)
- Builds inside the verifier: tier_a/b/c 73.6 s + C1-C8 144.3 s = 218 s. Reference per tier 0.2-0.4 s.
- Oracle-class program (P6o): shipped run_all 515.1 s (inferring call 122.8 s, 472 Worlds; per-call limit 900 s,
  1/4 = 225 s); 0.05 tiers 12-17 s per run_all x 15 runs = 255 s. Verifier worst case for oracle ~990 s.
- Slow honest program: P4o shipped run_all 899.4 s (201.5 s/call), P2n 776.4 s (236.7 s/call): worst ~1,250 s (899 + 218 builds + 15 small runs ~135),
  under 2,430 s. Phase 2 oracle adds a discriminating-row prefilter; target shipped call <= 120 s.

### Judge before / after (WORK/JUDGE_DRAFT.md)
- Before: 27 criteria, 73 positive; a1 61/73 = 83.6 (R1-R8 figures 40 pts, R12-R15/R17/R18 cheap).
- After: 17 criteria, 10 positive x3 = 30 (probe band 24/30), 7 negatives. Removed R1-R8, R12-R15, R17, R18, R20,
  R25. Kept old R9, R10, R11, R16 as R1-R4; new R5 P-f legacy run before first edit, R6 P-d altered decided_at
  copy rerun, R7 P-c recompute one key outside the compiler modules, R8 P-g count of start readings that fit,
  R9 J4 code quality, R10 J6 names each convention's shipped reading. Negatives: /tests read -5, /app/data
  write -3, install -1, repeat failing command -1, J3a -3, claims success vs nonzero run -3, unchecked convention -3.
- a1 graded: R8 (step 38 OK counts), R9 (old R27, step 51), R10 (step 70) = 9/30 = 30.0. Peer formula 40.0.

### Prediction
- a1 program tests 47.4, rubric 30.0 -> final 38.7. First-write (P0s) 47.4 with peer judge 40 -> 43.7 <= 45.
- Careful blind P2n 47.4. Wide P6o 100 -> final ~70 (fails gate) if a run searches every zone clock.
- Lever share 52.6%. Timeout share 0%.

### QC_RISKS items
- Fixed by this design: 1 (MFA defect), 2 (runbook defect map, D5), 7 (judge figure criteria, R17, R18).
- Not touched, left as is: 3 (shift bounds), 4 (BOM), 5 (generator scale; conv tiers use 0.05), 6 (embedded corpus).
- New 8: shipped observations fit two start readings (decided, recorded; also a1's vD latest-decided). Fixing it
  needs shipped attestation rows, which must stay byte-identical; stated in UNIQUE_FIT.md for master's call.

# Earlier tries (NO CORE, 29 Oct)

Status: NO CORE after 2 design tries. No BUNDLE edit was made (tree 4c85938aa8d4 unchanged).

## Arithmetic
- Gate: final = (tests + rubric) / 2 < 40; design bar predicted final <= 35, so tests + judge <= 70.
- Best judge probe band I can write for an a1-like agent: 12 probes x3 + J4 3 + J6 3 = 42 positive. a1 did real
  probes for 3 of the 4 current trajectory probes it earned (R13-R15, TRIP.md); with J4 that is about 12/42 = 29,
  peer-rate mid about 25. Even at judge mid 20, tests must be <= 50 for final <= 35 (<= 60 for final < 40).
- The a1 program on the current tests: 51/72 today, 72/72 once QC fixes the MFA reference defect (QC_RISKS.md 1).
  Its 21 lost points are the reference contradicting time_rules.md:5, not a1 error, so they cannot be kept as a lever.
- Needed: new lever checks >= 40% of positive weight that the a1 program gets WRONG. Measured: none exist.

## Try 1: L2 held-out corpora from the existing generator, on every documented branch it does not plant
- Prototype: `WORK/harness/fuzz.py`, 40 single-rule mutations of generated corpora (group cycles, deep nesting,
  7-digit/odd employee and contractor refs, journal bool/int typing, null cancel, seq ties, instant/date/epoch edge
  forms, alias = handle, alias chains, alias case, contractor approvers, window-equal ends, duplicate rows and
  tickets, unknown secops scope, HR correction ties, swap ties, DST wall starts, short shifts, zones without
  transitions, role include cycles, ms cutoff edge, CRLF, blank lines). 26 change the reference output.
- a1 program: EXACT on all 40 (`WORK/proto/fuzz_a1_101.txt`), and EXACT on three corpora carrying all 26
  effective mutations at once (seed 201 heldout 0.05, 202 boundary 0.04, 203 heldout 0.3; diff only the MFA
  defect; `WORK/proto/combo_a1.txt`). Plus 32 plain generator corpora (seeds 11-15, 101-106, scales 0.01-1.0,
  all variants): EXACT except the MFA defect.
- Lever points the a1 program keeps: 100%. Fails note 4 (a1 <= 60).

## Try 2: Law-1 v3.5 hidden-scale
- No runtime limit is stated in any doc (grep of cli_contract.md and the rest); stating one is a doc change.
- The generator cannot grow: heldout scale 5 fails `random.sample` (test_output.py:1297; contractor ids are
  1-4 digits, identity_rules.md:7), heldout scale 2 fails KeyError 'effective_until' (:2229).
- Measured at the largest working size (seed 301 shipped scale 3, 30 MB): reference 4.2 s, a1 program 14.7 s
  (3.5x, linear; scale 1: 1.3 s vs 5.8 s). Per call timeout is 900 s. No separation. Lever points kept: 100%.

## Kill table (measured, Docker, 4 GB, 2 CPU)
| program | corpus | seconds | result | lever pts kept |
|---|---|---|---|---|
| a1 program | 40 mutations, seed 101 heldout 0.05 | 1.1-1.6 each | EXACT x40 | 100% |
| a1 program | combo 26 mutations x 3 corpora | 1.6 / 1.9 / 4.5 | EXACT (MFA defect only) | 100% |
| a1 program | seed 301 shipped scale 3 | 14.7 (ref 4.2) | EXACT (MFA defect only) | 100% |
Blind, first-write and all-but-one programs were not written: note 4 needs the a1 row <= 60 first, and it is 100.

## The one a1-specific divergence (rejected)
- a1 carries on-call shifts at most 520 steps (engine.py:730); the reference at most 800 (test_output.py:933);
  access_contract.md:28 has no bound. A 600-shift same-holder streak would make a1 WRONG, but any generic program
  passes it and a fresh Opus run would not share the cap: fails kill-table rule (e) and tunes to one trajectory.

## Why there is no core in the current contract
- The docs state every rule the compiler needs, and a1 implemented all of them (full code review of engine.py and
  policy.py, TRIP.md). Stated-rule levers leak (LEVER_RULES 1C). The only unstated part is the gateway conventions
  (instruction.md:1; time_rules.md:13, :21; access_contract.md:26), which a1 fitted by replaying observations
  (steps 29-38) and hardcoded. The reference World (test_output.py:333) also fixes them, and corpus_index.md:53 says
  observations are never an input to a profile, so held-out corpora with other conventions would be a hidden rule.

## Options for Ayush (each needs his call)
1. Convention lever (S3 unique fit): rewrite the docs so each corpus's gateway conventions are whatever its
   observations show (drop "never an input" at corpus_index.md:53, extend the rerun promise at instruction.md:3),
   add convention parameters to the reference and generator, held-out tiers with other conventions. The a1 program
   would be WRONG on every such tier. Cost: doc change (3 fresh blinds), reference rewrite, new generator branch.
2. Fix only the MFA defect and the judge (J1 figure criteria): honest task, but tests ~100, final ~60. Fails gate.
3. Retire the task.

Docs changed: no. Judge changed: no (no design to attach it to).
