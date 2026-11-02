# Idea card: pilotage-dues-reconstruction (26 Oct 2026 17:55 IST)
Source: synthesis 720e1d7 BUILD_RECIPES.md Recipe B (lines 59-95), from delivery_study2 g1-g4. Ayush 26 Oct accepted D12. Archetype domain-calculation, category data-science. Shape D (degenerate shipped instance).

## Master gate notes (override the recipe text where they differ)
- G-1 Hardness = S2 quiet shipped instance (rule space stated, hard branch never fires on shipped data) + S3 unique fit (the station tariff is the one combination that reproduces every paid invoice; zero or two or more -> unresolved, verdict `cannot_recompute` with the stated reason string) + S8 rare branch (partial-visit exemption ending at midnight) on its own RNG stream.
- G-2 The unique-fit rule, the unresolved verdict and its reason strings are stated word for word in the circular (IN-15/IN-16; the 3f39299a hole must not repeat).
- G-3 Cold-chain lesson: state no size or runtime limit that hints at a method. Coefficient lists are small enough to enumerate on purpose; the difficulty is counting all fits, not speed.
- G-4 Hidden share >= 70% of positive test weight (G3 Shape D); seeds chosen so first-fit and unique-fit differ on every hidden corpus; per-row ownership (G1a). No all-corpora gate.
- G-5 Every key, field and value form any test reads is named in the shipped contract (QL 26 Oct Q3). No hidden keys.
- G-6 Toy worked example per quiet branch on invented values only (W6 v3). No rerun-axis list (QL Q4 off by default). Invocation stated exactly (G8a).
- G-7 Judge = probe band (Recipe B list, 8 probes w3, about 73%), each performed and printed by solve.sh self-check (QL Q1/Q2). If the bundle ships no helper, probe 8 becomes P-e relocated run. J3a/J3b/J3c, J4 behavioural, final-reply enumeration. No figure criteria.
- G-8 W11 no answers in environment/; IN-17.
- G-9 PREMORTEM must run the first-fit program Opus writes on the sample and every hidden seed: exact on sample, wrong on every hidden corpus, else redesign.

## Recipe text (verbatim)
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
