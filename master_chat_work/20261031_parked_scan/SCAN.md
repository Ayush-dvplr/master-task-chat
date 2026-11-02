# Parked-world scan e54f96a (31 Oct 2026, read only)

Paths: WORK = `master_chat_work/bundles/_work/<slug>/`, scratch = `_runs/20261031/parked_scan/{fuel,pilot,clean}/`.
Lever baselines used in this scan:
- L-CONV is defined by warrant: each corpus fixes its own gateway conventions, and only its own observation rows reveal them. 1 of 56 readings fits per tier (`_work/warrant-asof-entitlement-compiler/LEVERS.md:3-4`, `UNIQUE_FIT.md:3-9,20-32`). Blinds lost 16/16 conv checks by WRONG (`blinds/BLINDS.md:3-8`). Known hole: a careful wide search over every HR zone scores 80/80 EXACT (`20261029_.../harden_a1/DESIGN.md:65-78`).
- L-OPT is defined by outage: an exact lex-optimum on bridged hidden instances. The blind's component DFS TIMED OUT 0/4 at 60 s, while the reference took 4.5-5.1 s (`_work/outage-window-replan/KILL_TEST.md:36-83`). Blinds lost 68 lever points to TIMEOUT (`blinds/BLINDS.md:4-12`).
- Rules: `LEVER_RULES_v3.md:80-86` (stated rules and stated limits leaked), `:88` (v3.5 timeout), `:90` (v3.7 DESIGN READY gates).

## 1. fuel-card-settlement-consolidation

**1) Task.** The program reads five processor exports (kestrel, lumen, marlow, norvik XML, oberon), each with its own handbook conventions. It sets the batch status, then the site, business date, holder, segment and product. It applies reject reasons, pairs reversals, computes tier volume and discount with a monthly cap in ledger order, then half-even tax. It writes normalized.jsonl plus 13 reports (DESIGN.md:7-17). The design has 42 stated rules in 23 files and 9 formats, a 2023 decoy and 15 quiet branches (DESIGN.md:3).

Why the blinds were exact: every rule is stated, either in group_standard.md (business date :28-32, tax :71-76, tier :89-97, cap :104-110, reversals :119-149) or in a handbook (handbook_norvik.md:11-19). The R2 blind wrote all 42 rules in about 4 min and matched 13/13 documents on shipped plus 3 hidden corpora, with 0 differing rows (DESIGN_BLIND.md:55-69). None of the planted wrong readings matched (:83).

**2) What exists.**
- Docs: docs_src (RULES, group_standard, 2023 decoy, reference_data, output_schema, 5 handbooks).
- Generator: gen/fcgen.py (52.8 KB, the same file as proto/gen_proto.py). It takes any seed on the CLI (`fcgen.py <out> <seed> [plants] [--small] [--shipped]`, :1073-1076), but sizes are hard-coded as full or small (sites 2400/300 :190, accounts 1300/250 :228). It has no scale knob.
  - Measured seed 44: 2.00 s, 70,455 lines, 3.7 MB.
  - A scratch 4x copy took 30.85 s and made 239,914 export lines (14 MB).
- Reference: proto/solve_proto.py.
  - Shipped corpus: 2.34 s. h44: 2.23 s.
  - 4x corpus: **54.29 s**, about 24x the time for about 3.4x the lines. Some step is superlinear (INFERRED, not profiled).
- Missing: no tests, judge, Dockerfile or test_weights in WORK (a find returned none).

**3) Fit.**
- L-CONV: one natural family exists, the per-processor tax-inclusive flag `INCL = {...}` (fcgen.py:41), together with time offset and units. Today each handbook states its convention outright (handbook_norvik.md:11-19), and no file carries per-line priced outcomes that a fit could use (INFERRED). The lever would need five handbook rewrites, a new observation file (a remittance or statement) and an observe() routine that asserts the unique fit. None of these exist.
- L-OPT: there is no optimisation core. The tier and cap step is a stateful replay in a stated order (group_standard.md:104-110), not a search.

**4) Verdict.** L-CONV **WEAK**, L-OPT **NO**.
- Main risk for L-CONV: the same failure as before. Breadth plus stated rules leaked (`LEVER_RULES_v3.md:80`), and the conventions currently sit in the handbooks.
- Hidden scale is unusable: the reference slows superlinearly to 54 s at 4x.

**5) Effort.** Almost nothing is reusable for a lever. The parsers and the generator skeleton are reusable. The following must be written: a scale knob, a per-processor convention planting with observe() and a unique-fit assert, 5 handbook rewrites, the observation file, a reference fit loop with a perf fix, and then the whole bundle (tests, judge, Dockerfile, weights). Estimate: design ready in about 3-4 h and full bundle in about 7 h (INFERRED). That costs more than a new build, which took 71 min to design ready and 4 h 32 min to built for outage (02:45, 03:56, 07:17).

## 2. pilotage-dues-reconstruction

**1) Task.** Four stations lost their tariff tables. A circular fixes the due as five lines, each half-even (tariff_circular.md:30-39): tonnage, draft, towage, assist, and one night/holiday surcharge. The program recovers each station's coefficients from that station's paid invoices (CSV, JSONL, fixed width, XML), with notices splitting periods. It then gives verdicts on a disputed batch. The set has 14 files, 8 formats and about 38k lines.

Why the blinds were exact: the candidate space is a closed list of 5x4x3x4 = 180 combinations (tariff_circular.md:64-73; UNIQUENESS.md). The blind enumerated all 180 and stopped at the second match. Both reads were exact 9/9 on every corpus (DESIGN_BLIND.md read 1 eef02d3, read 2 f21f8e4: 620 lines, 0.22-0.45 s, 0 differing rows of 2764/970/971/929).

**2) What exists.**
- Docs: proto/docs (4 documents) and design_blind/environment/data (14 files).
- Generator: proto/gen_proto.py takes `--seed --out [--hidden] [--scale F] [--meta]` (:4, :942-950) and scales vessels, stations and disputes (:223, :327, :725). It asserts the fit counts for each seed.
  - Measured: shipped seed 482617 took 0.33 s for 40,027 lines. h1101 took 0.16 s for 13,998 lines. The 4x run (`--hidden --scale 4.0`) took 1.44 s for 159,344 lines, and its asserts passed.
- Reference: solve_proto.py took 0.34 s on shipped, 0.15 s on h1101 and **1.38 s at 4x**. It scales linearly.
- Supporting tools: compare_proto.py, score_proto.py, xcheck_proto.py, and EVIDENCE_MAP.md, which lists rules against the wrong readings they contradict.
- Missing: no tests, judge or Dockerfile.

**3) Fit L-CONV.** A concrete convention family is already present. It consists of the quiet rules that EVIDENCE_MAP lists, each with its documented rival readings:
- assist: per started vs per full 30 min (Q1, tariff_circular.md:36)
- draft_m: rounded up vs half vs truncated (Q2, :17-19)
- Sunday holiday: shifted to Monday vs Sunday only (Q3, :46-47)
- surcharge base: with vs without assist (Q1, :37-38)
- night window bounds (:37-38)

Each station's reading would be fixed by its own paid invoices. That observation channel already exists, and so do the joint fit loop and the per-seed fit-count asserts. Like warrant `observe()`, the generator must plant invoices that contradict every rival, so that 1 of N (180 x conventions) fits per station.

Why a careful blind cannot just read it today: it can, because the circular states each reading. The lever needs the circular to say only "station billing conventions differ; recover them from paid invoices", with no list. That mirrors warrant's unstated gateway conventions (`harden_a1/DESIGN.md:152-157`).

L-OPT: there is no optimisation core. The allowance draw is a stated order (exemption_policy.md:22-26).

**4) Verdict.** L-CONV **FITS**, L-OPT **NO**.
- Main risk is the same as warrant P6o: the blind already writes a joint fit loop for LV-1, so a careful blind may simply widen it over the conventions. Margin holds only if the docs do not enumerate the readings and the space is wider than the obvious ones (`harden_a1/DESIGN.md:75-78`).
- Second risk: "directive beside field is transliterated" (DESIGN_SUMMARY lesson), so the new docs must not place any hint next to the field.

**5) Effort.** The generator, scale knob, fit loop, asserts, reference, compare/score tools, evidence map and blind environment are all reusable.
- Must write: per-station convention planting plus an observe()-style contradiction of every rival, rewrites of tariff_circular.md and the rule register, a reference fit extended over conventions, a UNIQUE_FIT table, and 1-3 design blinds. Estimate about 1.5-2 h to DESIGN READY (INFERRED).
- For the full bundle, add tests with the generator embedded, the judge, the Dockerfile, test_weights and reward, for about 4-5 h in total. That is about the same as a new build, but the core and the observation channel are already proven.

## 3. cleanroom-window-schedule

**1) Task.** For each night in date order, the program picks jobs for 3 bays and 3 families with maximum net. Net is value minus minute_rate x duration minus the changeover fee. There is a single sterilisation crew with lead window [start - crew_minutes, start). The previous family carries across gaps and nights from the initial_family (contract.md:63-80). Ties go to the lexicographically smallest run vector, then the bay vector (:92-94). The program writes 9 documents.

Why the blinds were exact: the contract states the limits that hand over a bounded-state sweep. At most 72 jobs a night, at most 7 jobs on any minute, 3 bays and 3 families, and 2 s per night (contract.md:17-19). Blinds scored 3/3 at 98/98 in about 3 min (`LEVER_RULES_v3.md:23,80`; registry tasks.json:728 "All levers leaked. Parked").

**2) What exists.** A full bundle (22 files):
- The reference solution/solve.py: a sweep DP that merges free minutes older than the longest crew lead (:75-151).
- tests/test_output.py (1278 lines, 30 checks), with the embedded generator `make_book(seed, specs, attempts, ...)` (:261), pinned-hash books (:597-637) and an independent `_optimum` (:705).
- judge.toml, reward.toml, Dockerfile, and a Harbor oracle at 1.0 x3 (BUILD_REPORT.md:27).

The generator makes books with any seed and size within the asserts (night_data:154 caps jobs at 72 and overlap at 7). Measured:
- Shipped book regenerated, with jobs.csv identical to the shipped one: 0.30 s, 21,437 lines. The reference took **1.42 s**.
- About 4x mass (500 nights, 60 of them at 72 jobs and overlap 7, mandatory set to 0 because attempt 0 was infeasible with mandatory jobs): 1.00 s, 31,043 lines. The reference took **9.30 s** against a 1000 s limit.
- 10 nights at 72/7: the reference took 3.48 s (0.35 s per night, 17% of the limit). A raw-state copy (`cut = -1`) ran **>120 s** (>12 s per night).
- Beyond the stated limits: at 144/14 the reference took 26.82 s (**2.7 s per night, over the 2 s limit**). At 288/28 it ran >120 s.

**3) Fit.**
- L-OPT: the core is a true exact lex-optimum. Greedy (21/98), greedy+LS (24/98) and raw exact (48/98) lose (BUILD_REPORT.md:17), and raw-state times out at the stated size (above). However, the blinds already found the reference-class merge within 3 min. Making hidden nights larger than stated also kills the reference, which runs 2.7 s per night at 2x density. Outage worked because bridging hurt the blind's component split but not the reference (KILL_TEST.md:83). No such asymmetry is known here (INFERRED).
- L-CONV: the contract states every convention: half-open windows, latest-starting previous family, crew window bounds and the tie order (contract.md:63-94). Several readings exist (closed vs half-open, latest-starting vs latest-ending, crew window inclusive), but no observation channel (past plans or bills) exists to fix them per book. Both the file and the planting would have to be added.

**4) Verdict.** L-OPT **WEAK**, L-CONV **WEAK**.
- Main risk for L-OPT: the reference is too slow on larger hidden instances, and the stated limits hand over the method (the same failure as before, `LEVER_RULES_v3.md:80`).
- Main risk for L-CONV: a new observation file is needed, and blinds have already shown they transliterate the stated contract.

**5) Effort.** The whole bundle harness is reusable: Docker, the tests framework, the embedded generator, the judge, reward and the permission fixes.
- L-OPT would need a new instance family that blows up the blind method but not the reference. No candidate is known, so a research-grade search comes first.
- L-CONV would need an observation file, planting with unique fit, and a contract rewrite.

Estimate: DESIGN READY in about 2-3 h if a mechanism is found (UNVERIFIED), and the full bundle about 2 h after that thanks to the harness reuse.

## Ranking
1. pilotage-dues-reconstruction: L-CONV FITS (L-OPT NO). About 1.5-2 h to design ready and about 4-5 h for the bundle. The observation channel, fit loop and 4x-linear generator and reference already exist.
2. cleanroom-window-schedule: L-OPT WEAK, L-CONV WEAK. The full harness is reusable, but no instance family is known that kills blinds without killing the reference.
3. fuel-card-settlement-consolidation: L-CONV WEAK, L-OPT NO. There is no observation channel, the generator cannot scale, and the reference takes 54 s at 4x. A new build is cheaper.

## Lessons for the master
- Worlds that already fit hidden parameters from their own observations (pilotage paid invoices) are the cheapest L-CONV hosts. Move the stated quiet readings into the unstated per-corpus fit.
- Measure the reference at 2-4x before choosing L-OPT. Cleanroom's reference crosses its own limit at 2x density, and fuel-card's takes 54 s at 4x.
- L-CONV margin depends on the docs not enumerating the readings. Warrant P6o shows that a wide careful search recovers any listed space.
- Stated density or size limits hand over the reference method. An L-OPT redesign needs an asymmetry like outage's bridged components, not just bigger inputs.
