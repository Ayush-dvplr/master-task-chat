# Idea card: fuel-card-settlement-consolidation (26 Oct 2026 17:55 IST)
Source: synthesis 720e1d7 BUILD_RECIPES.md Recipe A (lines 15-55), from delivery_study2 g1-g4. Ayush 26 Oct accepted D12 (build Recipes A and B). Archetype data-pipeline, category data-processing. Shape B (breadth).

## Master gate notes (override the recipe text where they differ)
- G-1 Hardness = breadth (S1): 42 plainly stated rules over 22 files in 7 formats, each with a sentence and a RULE_TRACE row; no rule implied by silence (IN-15/16). S5 partial-authority decoy and S6 buried hidden-only fixtures are secondary.
- G-2 Quiet shipped month: about 15 rules never fire on shipped data (BRANCH_FIRE.md); each has at most one toy worked example on invented values that appear in no shipped or hidden file (W6 v3). The other ~27 fire on shipped data.
- G-3 The decoy (older group standard) states its own demotion in its header; the newer standard names the one clause that stays live (AL-1 05:21). Graded on both sides (live-clause rows, dead-clause rows).
- G-4 Per-row ownership (G1a) so one wrong rule costs only its rows; whole-family exact per corpus with the exactness sentence (CL-4 FC:491). No all-corpora gate in this build (keep it simple; QL Q3 allows one, but only if every key is named in the contract).
- G-5 Every key, field and value form any test reads is named in the shipped contract (QL 26 Oct Q3). No hidden keys.
- G-6 Invocation stated exactly in instruction.md (G8a). No rerun-axis list (QL Q4: off by default).
- G-7 Judge = probe band (Recipe A list, 8 probes w3, about 67% of positive judge weight), every probe performed and printed by a solve.sh self-check stage (QL Q1: trajectory criteria only when the oracle shows them; Q2: probe wording passes). J3a/J3b negatives, J4 behavioural, one final-reply enumeration item. No figure criteria (J1).
- G-8 W11: no answer for any graded document in environment/. IN-17: no sentence announces what the shipped data establishes.
- G-9 Biggest QC risk IN-16 across 42 rules: the stated source-precedence order and RULE_TRACE settle every pair; keep checks 30-34 (TS-23 warn above 35 is ok but avoid it).

## Recipe text (verbatim)
## Recipe A: fleet fuel-card settlement consolidation (archetype data-pipeline)

**Sources combined:** S1 breadth (main), S5 partial-authority decoy with one live fact, S6 hidden-only fixtures for stated branches, buried among many rules. Evidence: S1 `g2_aee9e0a/GROUP_SUMMARY.md:23` (9125255a 124 pts, daaca581 121 pts lost on about 80 and 31 stated rules); S5 `g2_aee9e0a/GROUP_SUMMARY.md:26` (3def42a3 35 pts), `g4_af78147/C_8764bfdd.md:84` (15 pts, INFERRED); S6 `g4_af78147/GROUP_SUMMARY.md:31-35` (yield depends on burial among about 60 rules).

**Setting.** A fuel-card company settles card transactions for fleet customers. Five regional processors (central, east, north, south, west) send their monthly settlement exports. Each processor writes its own format and has its own conventions. The agent writes `out/transform.py`, which turns the exports into one normalised ledger and the fixed reports.

**Fixed outputs (archetypes.md:6):** `out/transform.py`, `out/normalized.jsonl`, `out/summary.json`, `out/data_quality.json`, `out/product_summary.json` (product = fuel grade or non-fuel item), `out/region_{central,east,north,south,west}.json`, `out/segment_{consumer,corporate,enterprise,smb}.json` (customer segment from the account master).

**Rule count and files.** 42 stated rules over 22 files in 7 formats (CSV, fixed-width text, JSON lines, XML, INI, TSV, markdown).
- One handbook per processor (5 markdown files), each with 5 to 7 local conventions: volume unit (litres or US gallons with a stated factor), tax inclusive or exclusive, sign of reversals, how a split tender is written, pump-test transactions, timestamp zone, duplicate settlement batch marker.
- One group standard (markdown) with about 12 group rules: rounding per line before totals, which day a cross-midnight transaction belongs to, how a reversal finds its original across files, fleet discount tiers, the order in which conflicting sources win.
- Account master (CSV), product catalogue (XML), discount tiers (INI), tax table (TSV), 5 exports (one per processor, in their own formats), a processor-to-format catalogue (JSON), a rule register (markdown, one line per rule naming the file that holds its sentence; W10 in the draft).
- One partial-authority decoy: an older group standard whose own header says a newer standard replaces it. The newer standard, in a section far from the decoy, says that one clause of the older file still governs (for example the litres-to-gallons factor for one product). Every other clause in the decoy is dead. Graded both ways: rows that depend on the live clause, and rows where a dead clause would change the value.
- Every rule has a sentence. `WORK/RULE_TRACE.md` maps each generator branch to its sentence (draft section 0b). No rule is implied by silence.

**What the shipped instance hides.** The shipped month is quiet for about 15 of the 42 rules (draft W5 and BRANCH_FIRE.md): no reversal whose original sits in another processor's file, no split tender across fuel and non-fuel, no cross-midnight transaction on a month boundary, no account that crosses a discount tier mid-month, no product that uses the decoy's live clause. Each of these rules has one toy worked example in its handbook on invented values that appear in no data file (draft W6, evidence `g2_aee9e0a/C_37a0c3d6.md:19`). The shipped run is still a fair sample: all 27 other rules fire on it.

**Hidden-corpus generator.** Embedded in `tests/test_outputs.py`, seeded, own RNG stream per family (draft G8). Per corpus it draws processor conventions from the stated space (unit, tax mode, reversal sign, zone), re-renders the five handbooks with those values (draft W12; peer pattern `g1_be971df/GROUP_SUMMARY.md:49`, 6d12f970), and plants every quiet branch at least twice. 6 hidden corpora plus the shipped month. Each output family is graded whole and exact per corpus, with per-row ownership (draft G1a; peer `g2_aee9e0a/C_3def42a3.md:62-64`): each output row is owned by one check, so one wrong rule costs only the rows it touches.

**Test plan.** About 30 positive checks: 7 families x (shipped + hidden) with per-family weight, 2 decoy checks (live side, dead side), 2 mutation checks graded only where the plain hidden run is exact (draft G6), 1 missing-file check. Instruction states the invocation exactly (`cd /app && python3 out/transform.py --data <dir> --out <dir>`; draft G8a) and states "each output document is graded whole on the shipped month and on fresh months whose handbooks differ in the stated ways; only an exact match counts" (CL-4 exemption, FC:491).

**Judge probe band (10 criteria, our own wording).** Positive weight 36; band = 8 probes x w3 = 24 (67%).
1. (P-a, w3, trajectory) The agent runs its program on an input it built in which a reversal and its original sit in two different processor files, and shows the resulting ledger rows.
2. (P-a, w3, trajectory) The agent runs its program on an input it built in which a transaction crosses midnight on the last day of a month, and shows which month it landed in.
3. (P-b, w3, trajectory) For at least three processors the agent shows one source line next to the normalised record its program produced from it.
4. (P-c, w3, trajectory) The agent recomputes one region total by a route outside its program (a separate command or script) and compares it with the file.
5. (P-d, w3, trajectory) The agent changes a value in a copy of one handbook or export (not only moves it), reruns, and shows that the dependent figures moved.
6. (P-e, w3, trajectory) The agent runs its program from a working directory other than /app with input and output paths it chose, and the run succeeds.
7. (P-h, w3, trajectory) The agent runs its program with one export missing and shows the explicit error it reports.
8. (P-b, w3, trajectory) The agent shows one account that changes discount tier within the month and the rate its program applied to each part.
9. (J4, w3, code) The program's exception handlers each act on the error they catch (report it or stop); none passes silently. (Behavioural wording; evidence `g4_af78147/GROUP_SUMMARY.md:49-55`.)
10. (final reply, w3) The response names every processor export it rejected or partly rejected, with the reason.
Negatives: J3a (-3) claims a check passed with no run after its last edit showing it; J3b (-5) a figure stated in the reply differs from the file it names (`g4_af78147/GROUP_SUMMARY.md:49-55`, 4e2f6925 12.82 rubric pts).
Every probe is performed by a `solve.sh` self-check stage that prints `check <id> ok` plus one witness line, so JD-7 holds (04:76).

**Expected final reward.**
- Tests: breadth peers 17-51 with no probe band. Our per-row ownership is gentler than whole-family zeroing, so we plan on tests 40 (range 25-55).
- Judge: probes Opus passes about 25% of the time (3 of 16 in 0b27b9dc, 4 of 18 in 7e0d8feb; `g3_bffecb6/GROUP_SUMMARY.md:25`): 24 x 0.25 = 6. J4 about half: 1.5. Final-reply item 3. Total 10.5 / 36 = 29. Upper case, probes passed at 50%: 12 + 1.5 + 3 = 16.5 / 36 = 46.
- Final = 40 x 0.5 + 29 x 0.5 = **34.5**. Upper case 55 x 0.5 + 46 x 0.5 = **50.5**. Margin to 70 is wide even with the ±20 run variance on tests (`g2_aee9e0a/C_daaca581_DIFF.md`).

**Biggest QC risk.** IN-16 (01:46) on 42 rules: any pair of rules that a competent reader could reconcile two ways fails the task. Guard: RULE_TRACE.md plus one toy example per quiet rule plus the stated order in which sources win. Second risk: TS-23 (03:62) warns above 35 checks; keep the count at 30-34. Third: the decoy's live clause must be determinate from the newer standard's sentence (AL-1, 05:21); never from the decoy alone.
