# BUILD_RECIPES (draft, board 720e1d7)

Two recipes for our next two builds, plus the parked tasks that a judge-only rebuild could bring under 70.
Rule ids point to `LEVER_RULES_v3_DRAFT.md` in this folder: S1-S11 are the hardness sources (section 1A), P-a to P-h are the probe templates (J2a), J3a-c are the honesty negatives, G1a is per-row ownership grading.
Final reward = tests share x 0.5 + judge share x 0.5. The kill rule parks a task when the probe's final reward is above 70 (`_COMMON_RULES_v3.md:62`).
Domains were checked against every slug in `registry/tasks.json`. Neither domain is used there.

Peer numbers used as anchors (tests share, judge share):
- Breadth tasks: 9125255a 32.61 / 82.35; 3def42a3 37.93 / 83.33 and daaca581 17.12 / 83.33 (same task, run variance); 8764bfdd 51.46 / 83.33; 4e2f6925 51.35 / 87.18 (`g2_aee9e0a/GROUP_SUMMARY.md:10-14`, `g4_af78147/GROUP_SUMMARY.md:10-13`). None of these had a probe band.
- Degenerate shipped instance tasks: 18b5d99f tests 7.77, 3f39299a 5.17, b42c61b9 8.96 (`g1_be971df/GROUP_SUMMARY.md:15-19`). Those numbers include a stated gate (b42c61b9) or a hidden rule (3f39299a), so we do NOT expect them. We plan on a far milder drop.
- Probe-band judges: 0b27b9dc 26.32, 7e0d8feb 33.01, e13fd332 25.0 (`g3_bffecb6/GROUP_SUMMARY.md:7-11`). Opus passed 3 of 16 probes in 0b27b9dc (`g3_bffecb6/C_0b27b9dc.md:65`).

---

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

---

## Recipe B: harbour pilotage dues reconstruction (archetype domain-calculation)

**Sources combined:** S2 degenerate shipped instance with the rule space stated (main), S3 unique fit instead of first fit, S8 rare-branch hidden seed. Evidence: S2 `g1_be971df/GROUP_SUMMARY.md:23` (266 pts across 3 tasks); S3 `g1_be971df/GROUP_SUMMARY.md:24` and `g1_be971df/C_18b5d99f.md:32` (Opus took the first consistent fit; the reference required exactly one); S8 `g3_bffecb6/C_7e0d8feb.md:16`.

**Setting.** A port authority audits pilotage invoices from four pilot stations (North, South, West, East). Each station bills ships by a tariff formula, but the stations never published their coefficients; only a circular lists the allowed values for each coefficient. The agent must recover each station's tariff from its paid invoices, then recompute a batch of disputed invoices and audit them. Customers are commercial shipping lines or public vessels (research, coast guard), which pay under different exemptions.

**Fixed outputs (archetypes.md:7):** `out/derive_report.py`, `out/summary.json`, `out/policy_audit.json` (per disputed invoice: recomputed due, verdict), `out/data_quality.json`, `out/region_{North,South,West,East}.json` (recovered tariff, fit status, invoices used), `out/segment_{commercial,public}.json`.

**Rule count and files.** 24 stated rules over 13 files in 5 formats.
- Tariff circular (markdown): the formula shape (base by tonnage band + draft charge + night factor + towage-linked surcharge), the closed list of allowed values for each coefficient, and the fit rule: a station's tariff is the one combination from the list that reproduces every paid invoice to the cent; if no combination does, or more than one does, the station is "unresolved" and its disputed invoices get the verdict `cannot_recompute` with the reason. This is the unique-fit rule, stated in full (no hidden rule; compare the hole in `g1_be971df/C_3f39299a.md:34`).
- Paid invoices per station (4 files: CSV, JSON lines, fixed-width, XML), disputed batch (CSV), vessel register (TSV), exemption policy for public vessels (markdown), station notices (markdown: tariff change effective dates; a station may change tariff once, and invoices before and after the date are fitted separately), a holiday calendar (JSON) for the night/holiday factor, rounding rule (cents per line, half-even, stated with exactness).

**What the shipped instance hides.** On the shipped data every station's invoices pin down exactly one combination, and the first combination that fits is also the only one. So a first-fit program is exact on shipped data. No station changes tariff mid-period. No station's invoices miss a coefficient (for example no night invoice at West). Each of these branches has one toy worked example in the circular on invented numbers (draft W6).

**Hidden-corpus generator.** Seeded, in tests. Per corpus it draws a tariff per station from the stated lists and invoice mixes so that, across the 6 hidden corpora, each of these happens at least twice: (1) two combinations fit (a coefficient never exercised by the invoices), (2) no combination fits (one invoice billed under an exemption), (3) a tariff change on a notice date, (4) a rare branch: a public vessel that is exempt only for part of a visit (exemption ends at midnight). The generator draws the four rare cases on its own RNG stream so the plain cases never move when a rare one is added (draft G8). Seeds are chosen so that first-fit and unique-fit give different outputs on every hidden corpus (peer pattern `g3_bffecb6/C_7e0d8feb.md:19`).

**Test plan.** About 26 positive checks. Per corpus: region files (fit status and tariff) exact, policy_audit exact with per-row ownership (one wrong station costs that station's rows, not the whole file; draft G1a), segment files exact. Hidden share about 75% of positive weight (draft G3 for this shape: at least 70%). No all-corpora gate (C3 in CONFLICTS is pending QL). 2 mutation checks graded only where the plain hidden run is exact. Invocation stated exactly.

**Judge probe band (10 criteria, our own wording).** Positive weight 33; band = 8 x w3 = 24 (73%).
1. (P-g, w3, trajectory) For at least one station the agent shows that exactly one combination fits, by counting all fitting combinations rather than stopping at the first.
2. (P-a, w3, trajectory) The agent runs its program on invoices it built so that two combinations fit, and shows the station reported as unresolved.
3. (P-a, w3, trajectory) The agent runs its program on invoices it built so that no combination fits, and shows the verdict and reason.
4. (P-b, w3, trajectory) The agent shows one disputed invoice line by line: tonnage band, draft charge, night factor, rounding, and the final figure.
5. (P-c, w3, trajectory) The agent recomputes one disputed invoice's due by hand or by a separate command, outside its program, and compares it with policy_audit.json.
6. (P-d, w3, trajectory) The agent changes one paid invoice amount in a copy of the data, reruns, and shows how the fit status or tariff changed.
7. (P-a, w3, trajectory) The agent runs its program on a station with a tariff change date and shows the two fitted periods.
8. (P-f, w3, trajectory) Before its first edit the agent runs any shipped helper or check command and reads its output. (Only if the bundle ships one; else replace with P-e relocated run.)
9. (J4, w3, code) Every exception handler in the program acts on the error it catches; none passes silently.
10. (final reply, w3) The response names each unresolved station and the reason it could not be resolved.
Negatives: J3a (-3), J3b (-5), J3c (-3) misstates how many combinations or invoices its own check covered (`g1_be971df/GROUP_SUMMARY.md:30-33`, 18b5d99f).

**Expected final reward.**
- Tests: shipped tier 25% of weight, Opus exact there. Hidden tier 75%: with first fit, Opus misses the two-fit and no-fit corpora rows and the tariff-change rows; it likely gets plain stations right in other corpora. Per-row ownership leaves it roughly 40% of the hidden weight. Tests = 25 + 75 x 0.4 = **55** (range 35-70). Peer degenerate-instance tasks lost far more (tests 5-11) but with gates or hidden rules we will not use.
- Judge: probes 24 x 0.25 = 6; J4 1.5; final reply 3 (it will report no unresolved station on shipped data, so likely FAIL on hidden truth; count it as 3 only in the upper case). Lower 7.5 / 33 = 23; upper with probes at 50%: 12 + 1.5 + 3 = 16.5 / 33 = 50.
- Final = 55 x 0.5 + 30 x 0.5 = **42.5**. Upper 70 x 0.5 + 50 x 0.5 = **60**.

**Biggest QC risk.** IN-15 / IN-16 on the unresolved outcome (01:45-46): the "no fit or more than one fit" verdict and its reason string must be stated word for word, or it is the 3f39299a hole (hidden rule passed only as WARN, `g1_be971df/C_3f39299a.md:34`). Second risk: our own cold-chain lesson, a stated bound that hands over the method (`registry/tasks.json` cold-chain note). The coefficient lists are small enough to enumerate, which is intended: the difficulty is counting all fits, not search speed. State no runtime bound that hints at a method. Third: CL-4 (FC:491) if one wrong station shifts every downstream row; per-row ownership plus the exactness sentence covers it.

---

## Parked tasks: can a judge-only rebuild bring the final under 70?

Rule: final < 70 needs judge share < 140 - tests share. With tests at 100 the judge must score below 40. Scores from `master_chat_tasks/registry/tasks.json` `pipeline.traj_*` and `pipeline.next`.
Target judge after a probe-band rebuild: 30 (peer probe-band judges 25-33, `g3_bffecb6/GROUP_SUMMARY.md:7-11`). Final shown at judge 30 and at judge 40 (bad case).

| task | recorded tests / judge / final | judge needed | final at judge 30 / 40 | candidate? |
|---|---|---|---|---|
| caldermoor-commitment-closure | 98.45 / 48 / 73.22 (probe 5) | < 41.55 | 64.2 / 69.2 | YES, best margin of the probed ones |
| sentinel-policy-recompute | 100 / 40 / 70.0 (probe 4) | < 40 | 65.0 / 70.0 | YES. Note: 70.0 is not "above 70", so under the new kill rule as written it was not a park. Ask Ayush (D-list). |
| metered-usage-rating-pipeline | 100 / 64.71 / 82.35 | < 40 | 65.0 / 70.0 | YES, tight |
| cold-chain-backbone-quote | 100 / 70 / 85.0 (probe 2) | < 40 | 65.0 / 70.0 | YES, tight |
| sensor-network-lsq-correlated-adjustment | 100 / 75 / 87.5 (probe 3) | < 40 | 65.0 / 70.0 | YES, tight |
| tariff-engine-audit-repair | 100 / 3.33 / 51.66 (recorded), blind 157/157 | already < 40 | already under 70 | ALREADY UNDER on record (source run INFERRED older). Needs only a probe, no rebuild. |
| cleanroom-window-schedule | blind 100, judge not measured | < 40 | 65.0 / 70.0 | MAYBE: no judge ever measured |
| counter-page-crash-recovery | blind 100, judge not measured | < 40 | 65.0 / 70.0 | MAYBE |
| batch-lease-scheduler-replay | blind 100, judge not measured | < 40 | 65.0 / 70.0 | MAYBE |
| flood-repair-portfolio | blind 1/3 miss, judge not measured | < 40 if tests 100 | 65.0 / 70.0 | MAYBE |
| data-product-config-compiler | 100 / 100 / 100 | < 40 | 65.0 / 70.0 | MAYBE (judge 100 today, needs the most change) |
| cohort-retention-reconciliation | 100 / 100 / 100, parked on AL-27 loop | < 40 | - | NO: parked for a QC loop, not hardness |

Honest caveats:
- With tests at 100 the margin is 5 points at judge 30 and zero at judge 40. Run variance on the final is about ±10 (draft G13, from `g2_aee9e0a/C_daaca581_DIFF.md`). One probe can land on either side. Only caldermoor has a margin that survives a bad judge run.
- `_COMMON_RULES_v3.md:59` still requires tests < 100 before PL. Every candidate with tests 100 fails that line as written. This is decision D2 in SUMMARY.md.
- A probe band that the oracle must show (JD-7, 04:76) means a `solve.sh` self-check stage per probe in each rebuilt bundle. That is a solution change, not only a judge.toml change. Test files stay the same.
- Rebuilding only the judge to get under 70 makes the task hard on process, not on the result. QC accepts that (g3: tests 90-96, finals 57-63, all delivered; `g3_bffecb6/GROUP_SUMMARY.md:13`), but it is Ayush's call whether such tasks are worth delivering.
