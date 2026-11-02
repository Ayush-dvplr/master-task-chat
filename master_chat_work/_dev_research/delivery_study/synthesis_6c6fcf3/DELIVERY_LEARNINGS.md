# Delivery learnings: 21 QC-passed peer tasks vs our 25 Oct builds (board 6c6fcf3)

Sources: 4 group studies under `master_chat_work/_dev_research/delivery_study/` (dinshi_5a44fec, sugam_a_3bfed9f, sugam_b_bd5de18, poonam_f2e6166). Citation forms: `C_<task> §n` = per-task card section; `<group> GS §n` = that group's GROUP_SUMMARY.md section; `LR` = knowledge/LEVER_RULES_v1.md; `LL` = LEAK_LIBRARY.md; `QR` = QC_RULINGS.md; `PB` = QC_FIX_PLAYBOOK_v2.md; `LA` = 20261025_process/leak_audit_ed0bc62/LEAK_AUDIT.md; `DX-<task>` = that task's harden DIAGNOSIS / HARDEN_REPORT. All peer repos at HEAD 2dfb1f8. Patterns only; no peer content is reproduced beyond short quoted phrases needed as evidence.

Session rename: `name_session.py 6c6fcf3` printed `codex: no match` and listed opencode `ses_e8e7e1d29ffe42BmQDXySkwH0m`; the list did not literally show 6c6fcf3. Noted, not retried.

---

## 1. Scoreboard

Units: dinshi and poonam cards count raw test points; sugam cards count % of the tests score. "Genuine lost" = points lost to a traced agent misreading, not to grader artefacts or gates the task never stated. ARTEFACT and PARTLY rows are flagged and **excluded from every pattern count below**.

| # | Task (short) | Group | Verdict | Overall / tests / rubric | Genuine lost | Lever shape that paid | Source |
|---|---|---|---|---|---|---|---|
| 1 | chainfold-resume-repair | dinshi | GENUINE | 62.93 / 78.49 / 47.37 | 20 of 87 pts (23%) | hidden regimes from in-test generator; unstated empty value of a string field | dinshi GS §1, C_chainfold §3 |
| 2 | h3-fleet-migration-scheduler | dinshi | GENUINE | 64.77 / 70.71 / 58.82 | 29 of 99 (29%) | overloaded term, graded meaning implied only by a computation clause; seals green under both readings | dinshi GS §2(3) |
| 3 | inference-gate-replay | dinshi | GENUINE | 21.77 / 36.56 / 6.98 | 59 of 93 (63%) | withheld constants, no candidate list, digest yes/no only signal | dinshi GS §2(1), C_inference §5 |
| 4 | keyframe-interval-basis-reconcile | dinshi | **PARTLY** | 56.2 / 26.85 / 85.56 | 57 value + 22 via value gate of 108 | rule posed as a question settled by one shipped witness; positional value gate | dinshi GS §2(2), C_keyframe §5 |
| 5 | registry-lock-footprint-resolution | dinshi | **ARTEFACT** | 48.81 / 2.88 / 94.74 | 0 (QC re-grade 139/139) | none: verifier could not read the program (H6 permission) | dinshi GS §5 |
| 6 | restoration-cadence-settlement | dinshi | GENUINE | 53.38 / 25.62 / 81.13 | 90 of 121 (74%) | withheld convention recovered by calibration fit inside an unstated candidate set; whole-report mutation tier | dinshi GS §2(1),(6) |
| 7 | tollgate-settlement-repair | dinshi | GENUINE | 72.89 / 91.55 / 54.24 | 3 (+3 contested) of 71 (4%) | judgement-field root-cause chain graded exact | dinshi GS §2(7) |
| 8 | vault-relink-correction | dinshi | **ARTEFACT** | 62.7 / 85.39 / 40.0 | 0 proven (13 lost to expected-vs-prose contradiction) | none | dinshi GS §5 |
| 9 | yard-rehandle-ledger-recompute | dinshi | **PARTLY** | 48.91 / 16.42 / 81.4 | 21 of 68 (35 to H6 artefact) | one family error repeated over 3 minted seeds | dinshi GS §2(5), C_yard §5 |
| 10 | 4a5f9738 spectrum register | sugam_a | GENUINE | 38.99 / 23.88 / 54.1 | 76.1% | definition narrowed by agent via semantic flag that shipped residue supports; whole-block exact | sugam_a GS §2 P1, §3 LA3 |
| 11 | 4ee62df1 config pipeline + repair | sugam_a | **PARTLY** | 48.99 / 20.62 / 77.36 | 63.9% (+15.5 unstated `_real_work` gate) | scope by omission; own-artifact hash in every expected value; anchored mirrors | sugam_a GS §2 P2/P3, §3 LA1 |
| 12 | 8da8ba3d security config + repair | sugam_a | GENUINE | 61.92 / 77.68 / 46.15 | 22.3% | silent shipped-code fault with no contradiction cue; one scalar over 4 checks | sugam_a GS §2 P4/P5 |
| 13 | 9bbcb50f | sugam_a | **ARTEFACT** | 67.69 / 58.46 / 76.92 | n/a | version skew (rules added after run) | sugam_a GS §5 |
| 14 | a5b17048 | sugam_a | **ARTEFACT** | 67.41 / 42.5 / 92.31 | n/a | hidden test with reference reachable in env; older verifier | sugam_a GS §5 |
| 15 | ae640566 | sugam_b | **ARTEFACT** | 59.59 / 34.97 / 84.21 | n/a | contract text reversed after run | sugam_b GS §5 |
| 16 | af6f42c3 policy compiler | sugam_b | **PARTLY** | 69.5 / 45.83 / 93.18 | 26% value (+10 mixed, 16 gate) | filter only in sibling paragraph; announced coupled bound; unstated key-vocab gate | sugam_b GS §2 P2/P6 |
| 17 | b47fd5f7 season settlement | sugam_b | GENUINE | 59.91 / 94.83 / 25.0 | ~3% (INFERRED from tests 94.83) | closed-list definition where an absent input arguably fits | sugam_b GS §2 P4/P5 |
| 18 | ceab1cf6 CLI repair | sugam_b | GENUINE | 65.47 / 50.0 / 80.95 | 36% (+2 gate) | ordering property with open operand, paid 9 times; data-rule element no-op on shipped | sugam_b GS §2 P1/P3/P7 |
| 19 | d22ff871 | sugam_b | **ARTEFACT** | 32.36 / 25.93 / 38.78 | n/a | superseded test file graded; program unreadable by nobody | sugam_b GS §5 |
| 20 | 00372225 assay pipeline (T1) | poonam | GENUINE | 56.72 / 42.0 / 71.43 | 58 of 100 (58%) | unstated binding time of a defined quantity; stated core gate x3-5 | poonam GS §2 P1/P4 |
| 21 | 66b1a1e2 calendar reconciliation (T2) | poonam | **PARTLY** (gate stated, root undetermined) | 46.09 / 62.59 / 29.58 | 10 direct + 42 via stated gate of 139 | combined-axis hidden store; hidden-only probe shapes | poonam GS §2 P1/P5 |

Totals: **10 GENUINE**, 5 PARTLY, 6 ARTEFACT. Genuine tests-share lost ranges 4% to 76% (median ≈ 33%). Our 7 probed 25 Oct builds: tests 98.45-100 (LA probe table).

Artefact lesson (not a pattern): 6 of 21 delivered scores were not produced by the repo that QC passed (version skew, superseded test file, permission). Before analysing any score, diff ctrf test names and weights against the repo (sugam_b GS §5, dinshi GS §5).

---

## 2. Test-design patterns (GENUINE tasks only), ranked by number of tasks, then points

| Rank | Pattern | Mechanism (2 lines) | How graded | How it stayed QC-clean | GENUINE tasks / pts it carried |
|---|---|---|---|---|---|
| TD1 | Hidden corpora re-run from an in-test generator | Tests carry a seeded generator or zlib/base64 blobs, build fresh corpora "laid out like" /app/data, and run the agent's program on them as an unprivileged user. Separating rows exist only there. | byte or field equality vs reference computed in tests (or stored digest) | TS-19 met by instruction bounding the shape ("a corpus laid out like this one", "up to 48 requisitions"); G8/G9; TS-20 1/3/5 | 8: chainfold, h3, inference (probes), restoration, 4a5f, b47, ceab, T1. Carried nearly all genuine loss; T1: all 58 lost pts on reruns or gated (poonam GS §2 P2); shipped-only checks almost all passed (ceab shipped-only 61% passed, C_ceab §5) |
| TD2 | Whole-document / whole-block exact equality as the unit | One check compares an entire report or block (every row, every field), so one misread rule fails every check that contains it. | `==` on whole file/block; no tolerance | CL-4 kit exemption: instruction states exactness or the cascade out loud (4a5f instruction.md:13; T1 :23,:27; b47 I:11); PB CL-4 row; QR line 125 "never on positive cascades" | 7: 4a5f (76.1%), restoration, T1, b47, chainfold, h3 (shipped blocks), 8da8 (unstated, still passed) |
| TD3 | One fact family repeated across N reseeded corpora or views | The same rule is graded once per corpus/season/seed; a single wrong family costs N x weight. | per-corpus whole doc | TS-26 read as "different corpora" not duplicate observable (C_ceab §5); CL-4 via repetition rather than one doc | 5: ceab (one operand, 9 checks, 31 pts), b47 (7x5 whole), restoration, h3, chainfold. PARTLY echo: yard 3+3+3x5 |
| TD4 | Per-rule probe fixtures | A tiny store that fires exactly one rule, graded on its own stage. | own-stage value | TS-19 "every stated rule has a probe that triggers it" (C_T1 §5) | 3: inference (one rule per probe), h3 (each withheld rule own fixture, all passed), T1 (probes with different constants). Mostly passed: probes catch transliteration errors, not reading choices |
| TD5 | Expected values kept out of reach | Golden results keyed by input fingerprint, stored SHA-256 digests, or an independent reference over embedded inputs; no rule code a reader of tests/ could lift. | digest or reference compare | G9; digests also keep rules out of tests/ (poonam GS §4) | 5: h3 (`_GOLDEN_RESULTS_B64`), inference (digests), T1 (independent reference L410-612), ceab (hard constants "Independently derived"), b47 |
| TD6 | Mutation / generalisation tier | Tests mutate one input axis and require the whole report to move exactly. | whole report per mutant | AL-27 (each mutator keys its own catalogue, C_restoration §5); TS-26 fixed by collapsing duplicate mutators | 3: restoration (`_generalises` 55 of 124, no partial credit), b47 (2x3), T1 (axis-equality, 0 lost — cheap for Opus, poonam GS §2 P6) |
| TD7 | Stated core gate | Whole-document checks on a store run only if that store's core matches; the instruction says so. | gate then whole doc | CL-4 exemption + G5-style sentence (T1 instruction.md:23); QC 0 warns on T1 | 1 GENUINE: T1 (30 of 58 via gate). PARTLY: T2 (42 of 52 via gate, QC W3), keyframe (value gate 22, QC:50) |
| TD8 | Narrow negatives + setpriv rerun | Negatives fire only on exact cheating acts (sha of shipped broken file, expected literal in a named function body, >=2 shipped literals AST-scanned); program rerun as nobody, input-mutation snapshot, /tmp scan. | -5/-3/-1 | TS-16, G4 | 10 of 10 use it; **0 fired anywhere** (sugam_a GS §2 P10; C_T1 §5). Costs nothing, earns nothing |

Reading of the ranking: separation came from TD1 (unseen inputs) multiplied by TD2/TD3 (whole-unit exactness repeated). No GENUINE task lost material points on shipped-data checks. TD4 and TD6 checked the agent's arithmetic and Opus passed them.

---

## 3. How tests handle QC, and conflicts with our rules

### 3a. Per rule, the common way peers passed

| Rule | Common way (cards) |
|---|---|
| TS-13 (`and` bundles) | Either split after a MINOR (keyframe QC:34, restoration M1) or accepted as "one property per regime/block" (chainfold QC:223; 4a5f one block per check after the district-heat precedent). T1 `and`-bundle L1785-1800 and 8da8 :465/:742 passed with 0 minors (C_T1 §5, C_8da8 §5). |
| TS-16 (negative trigger) | Cheat-only negatives that rule out drift before firing (T1 L1984-1995); outcome negatives require addressed records correct first (keyframe :32). Yard kept 8 wrong-reading detectors, accepted as "mutually exclusive by exact-match construction" (C_yard §5, QC:117). Tollgate token-grep negative drew a warn (:241). |
| TS-19 (hidden inputs in bounds / test vs contract) | Instruction names each varying axis or bounds the shape: T2 instruction.md:3 lists the axes; b47 I:7 "up to 48 requisitions"; ceab I:3 "any other rule corpus laid out exactly like /app/data". Several stricter-than-contract checks still passed (af6f spine T:408,425; ceab two 1-pt checks; 4ee6 `_real_work`). |
| TS-20 | 1/3/5 weights everywhere, core never 1 (chainfold :230). |
| TS-26 (one observable once) | Fixed by deleting or collapsing duplicates (chainfold :34 FAIL→fixed; restoration F4). Repetition across distinct corpora accepted (ceab 9x; b47 "each document graded once", T:2437-2443; T2 "No report is graded twice on one store" TRUTH.md:209-230). |
| IN-15 (rule stated somewhere readable) | Rules delegated to evidence: "settled from the corpus" (4a5f instruction.md:22-23), "interaction rules each file declares through its own field values" (8da8 :29-31), "agree with exactly one draw" (b47 register:73-75). Hidden rules passed (chainfold :171, keyframe :117, restoration :124-125). |
| IN-16 (one reading) | Passed where the *text* has one reading and the second comes from data residue (4a5f) or from what is left unsaid (T1 binding time, ceab operand, 8da8 `+`/`*`). Where QC saw it, taskers deferred: keyframe W1 :26 "invalidates the recorded trajectory"; yard M1 settling clause drafted and reverted at tasker's instruction (:26,:63). |
| AL-28 | Not an issue for positives (chainfold :289). |
| CL-4 (amplification) | Kit exemption sentence in instruction: 4a5f :13, 4ee6 :11/:31, af6f I:11, b47 I:11, T1 :23, T2 :7. QC reports one-fact-wrong ratios and accepts them (chainfold 0.678 :275; keyframe 69/109; restoration 104/124 with warn W3; tollgate 0.845). 8da8 and ceab had no sentence and still passed. |
| JD-7 (oracle meets every criterion) | T2 loosened 3 criteria before delivery to stay oracle-satisfiable (QC :86; TRUTH.md:251-275 "No criterion asks for a value the tests already grade"). 8da8 R2/R8 not satisfiable by oracle (INFERRED added after QC or missed). |

### 3b. Conflicts with QC_RULINGS / PLAYBOOK_v2 / our LEVER_RULES, and which held in real QC

| # | Conflict | Our text | Their practice | Held in real QC |
|---|---|---|---|---|
| K1 | Hidden rules | LR line 24 "Never used (QC IN-15/IN-16...)": "ambiguous fallback scope", "nullable output w/o null condition", "unstated tie-break"; PB §0 "rule stated somewhere readable" (kit 01:45) | Unstated empty value of a field (chainfold), unstated same-generation winner (keyframe), unstated candidate space (restoration), unstated binding time (T1), open operand (ceab), silent code fault (8da8) | **Theirs** passed QC every time it was not noticed (chainfold :171-172, keyframe :117, restoration :124-125, T1 0 fails). When noticed, IN-16 warned, then deferred (keyframe :26, yard :26). Our rule is stricter than what QC enforces; it is also what QC *would* fail if it saw it (QR IN-16 emberforge v1:34 FAIL, schema v3:32 FAIL). |
| K2 | Wrong-reading negatives | LR G4 "negatives only cheating acts, no negative grades a lever" | yard 8 wrong-reading detectors | **Theirs** accepted (yard QC:117). None fired anywhere (TD8), so no evidence they help. |
| K3 | Whole-document amplification | LR G1 "amplification through owned rows not whole documents"; match-replay QC v3 failed whole-doc 20/160 for one rule | Whole-doc / whole-block exact everywhere (TD2) | **Theirs**, when the instruction states exactness/cascade: PB CL-4 row "Or state in instruction.md that only exact whole-document match counts (kit exemption)"; QR line 125. 8da8 passed without the sentence; T2 drew W3 (:115-117) but shipped. Our G1 is stricter than QC (poonam GS §4 "our G2 is stricter than QC needs"). |
| K4 | Gates | LR G2 "no early return on scalar from another doc" | stated core gate (T1, T2), value gate (keyframe), unstated `_real_work` (4ee6), unstated key-vocab gate (af6f T:554-558) | Stated gates passed (T1 0 warns; keyframe :50 accepted as coupling; T2 W3). Unstated gates also passed but are exactly QR CL-5 / TS-19 FAIL shapes (dispatch v1:41, vendor v1:50); treat as luck. |
| K5 | Hidden share | LR G3 hidden reruns >= 30% of positive weight | keyframe 13.8%, 4a5f 14.9%, 8da8 0%, af6f 0% | **Theirs** passed QC. Separation still happened because no shipped expected output existed (sugam_a GS §4). G3 is our rule, not QC's. |
| K6 | Stricter-than-contract / silent value type | QR TS-19 vendor v1:50 FAIL; CL-5 dispatch v1:41 FAIL | af6f T:664-665, ceab 2 checks, 4ee6 `_real_work` | Passed QC (C_af6f §5, C_ceab §5). Rulings are precedent, applied inconsistently. Cheap points (≤13), not a design. |
| K7 | TS-13 `and` bundles | QR TS-13 MINOR (vendor v1:69, schema v2:46, v4:30, sensor v1:46) | T1 L1785-1800, 8da8 :465/:742 | Passed with 0 minors. Inconsistent enforcement; keep our split. |
| K8 | JD-7 | QR JD-7 FAIL x4; LR J2 | 8da8 R2/R8 oracle-unsatisfiable | Shipped (INFERRED missed or post-QC). T2 shows the compliant way: loosen criteria before delivery. |
| K9 | G7 assertion messages | LR G7 | absent in most peers (T2 root undetermined because no ctrf messages) | Not a QC rule; their omission cost diagnosis, not QC. |

---

## 4. Leak-avoidance patterns (each mapped to the leak it would have prevented)

| # | Pattern | Peer evidence | Leak it prevents (LL row or LA finding) |
|---|---|---|---|
| LV1 | **Say THAT, never WHICH.** One sentence that something is withheld, decoyed or idle; no list, no explanation of the trap. | inference gate.md:150-155 "Not one of them is written down ... neither is a list of them"; restoration :30-31; b47 I:5 "written down nowhere in the rulebooks"; ceab I:1 "carry decoy rows" (dinshi GS §3, sugam_b GS §3) | LL ESC/EXT (explains trap), SALV (names both reflexes), CR-1; LA §1 full-procedure sentence (amount+method+set) |
| LV2 | **Quiet shipped run.** Shipped data never fires the separating rule; one neutral line says idle rules are live elsewhere; separating rows only in hidden/held corpora. | chainfold instruction.md:37 "The run you can see is a quiet one..."; ceab data-rule element no-op on shipped (width_even, band 0 already even); poonam L-b (agent ran only an in-memory smoke test) | LL "shipped boundary rows let agent watch rule fire" (W5/W6); RUN ("shipped stream 3 separates"); DX-data-product NL-4 (shipped plants, agent ran fullmatch step 14) |
| LV3 | **No shipped expected output; worked examples on invented cases that disown shipped data.** | 8da8 samples "hints only" (instruction:19); chainfold worked_examples.md:3-5; b47 register:73 worked cases not shipped figures; ceab sample_config "context only - do not copy" | LA §2(3) shipped controls/receipts/200 solved examples used as oracle (sentinel F4/F5, district export_manifest, tariff customer_claim, data-product team_overrides); LL CR-2/REV |
| LV4 | **Controls reconcile under both readings.** Seals/calibration green whether the agent reads right or wrong. | h3 seals zero preemptions; restoration calibration fits the agent's model (dinshi GS §3) | LL ENC ("self-test caught"); LA §2(3); DX-data-product NL-1 ("0 differ" on shipped) |
| LV5 | **Rules spread over many neutral, topic-named documents; instruction states no rule.** | T2 ~27 docs 14.5k words, hash-style names (poonam GS §3 L-c); 4ee6/af6f 11 spec files "follow it to the letter" (sugam_a LA6) | LL V0-2..V0-8 (single explicit sentence), REMAP/REJ (numbered procedure); LR W10 confirmed |
| LV6 | **Global precedence sentence far from the decoy**, in the instruction, not beside the decoy. | b47 I:3 vs clerks_digest.md:10-12; tollgate "Where two sources disagree, the runbook settles it" | LL CR-2 (decoy resolved two paragraphs later), REV (decoy refuted on line of use) |
| LV7 | **Announce the coupling, not the trap.** State that one misread moves many figures; never which misread. | af6f I:11; 4ee6 :11/:31; T1 :23 | LL ENC (stated twice); also buys CL-4 exemption |
| LV8 (RISKY) | Scope by omission / bare definition with data residue | 4ee6 contract:19 vs :37-39; 4a5f precedence_policy.md:3-4 + residue (sugam_a LA1, LA3) | LL CR-1, CR-3, STATE. Works, but every instance is an IN-16 exposure (§6) |
| LV9 (PARTLY only) | Separating cases at the tail of a long stream behind byte-level decoys | 4ee6 seq 9001-9034 (sugam_a LA2) | LL RUN, CR-2. Opus partial-`head` reading made it work (sugam_b GS §2 P3) |

Counter-evidence (confirms LR W1): when a peer spelled its traps (yard spec names each wrong reading + known_traps file; T1 footguns file + 8 instruction bullets), Opus passed every spelled trap, 0 yield (dinshi GS §3, poonam GS §3). Their only fully traced misses were on things never written down.

---

## 5. Why ours leaked and theirs held

| Axis | Ours (25 Oct, tests 98.45-100) | Theirs (GENUINE, tests lost 4-76%) |
|---|---|---|
| Wording | One contract sentence states the whole graded procedure (amount, method, recipient set, repetition) in 7/8 bundles (LA §1). Master condition at 00:20 asked to "name amount and method" (DX-tariff §2 contributing; DX-metered C3). Opus transliterated in one write, 4-5 min after reading (DX-tariff step 18; DX-metered step 15). | Rule left under-specified on one axis: operand (ceab), scope (4ee6, af6f), binding time (T1), empty value (chainfold), candidate space (restoration, inference). By our standard these are hidden rules (sugam_b GS §4) that QC tolerated (§3 K1). |
| Shipped data | Controls, receipts, 200 solved examples, planted separating rows visible, all-zero counters on cold branches (LA §2(3),(4),(6); DX-data-product NL-4) — the agent used them as an oracle or wrote ~70 synthetic assertions (district L10). | Quiet run; no expected output; worked examples on invented cases (LV2, LV3). Agent self-tests checked determinism, identities and bounds only (sugam_a GS §3 LA7). |
| Visible tests | None shipped either side. But our instruction self-check invitation + G5 "fresh inputs" sentence led the agent to build an independent recompute and mutated copies that reproduced the hidden tier (LA §2(2): sentinel 48-52, data-product 26-42, district 23-47). | Instruction says exactness/coupling counts, never invites rebuilding the hidden tier. |
| Archetype | H7 second-pass re-share family in 7/8 (LA §5); LV-MU-6/7 correlated, one helper serves both = one lever (DX-metered §3). | Repair of a broken shipped tool (8da8, ceab, chainfold, tollgate), evidence induction (restoration, inference, 4a5f), multi-stage pipelines (T1), multi-store reconciliation (T2). |
| Where difficulty lives | Rule reading of single sentences that name their separating case (DX-data-product §2 PRIMARY). Computation is easy for Opus. | Rule reading of what is *not* said (unstated operand/scope/binding), induction from evidence, state (binding time), failure handling (empty value). None in environment. |
| Amplification | G1 owned rows: one lever alone 11-30% (LR §7), caldermoor new N2 35% (DX-caldermoor). | Whole-doc exact on hidden corpora x N, often behind a stated gate: one miss = 20-76% (TD2, TD3, TD7). |
| Fuzz evidence | Levers 300/300 fuzz-differ on old programs, then probe 0/300 (DX-caldermoor); "A fuzz difference on an old program shows that the rule changed. It does not show that the rule is hard." (DX-metered). | No fuzz gates; separation measured only by delivery. |

Biggest single difference: **their separating rule was never written as a sentence; ours always was** (LR G10 note: 17 of 17 levers REVEALING, each traced to a sentence that enumerated/named its separating case). Second: their whole-document exactness on unseen corpora multiplies one miss; our owned-row grading caps it.

---

## 6. Lever shapes: SAFE / RISKY / NOT ALLOWED

Neutral examples are invented here (not taken from any peer task). "Cost" = expected tests share lost by Opus if it misses that one lever, from the peer evidence cited.

### SAFE (QC-clean under our rules and theirs)

| Shape | Neutral example mechanism | Expected one-lever cost | QC rules satisfied | Evidence |
|---|---|---|---|---|
| S1 Whole-document exact per hidden corpus, exactness stated once in instruction | Library-loan fines report regenerated on 6 reseeded branch archives; instruction: "only an exact report counts" | 20-50% when the lever fires in most corpora (needs a real miss to exist) | CL-4 exemption (PB CL-4), G5, TS-26 one doc per corpus | b47 P5, 4a5f, T1 (TD2) |
| S2 Data-rule element that is a no-op on shipped data, separating case only in held corpora | Greenhouse rule "round tray counts up to even"; every shipped tray count already even | ~5% per held check; scales with corpora | IN-15/16 (rule stated plainly), W5 | ceab P3 (sugam_b GS §2) |
| S3 Held corpora reorder decoy rows ahead of canonical rows and swap the base config | Second warehouse feed lists retired SKUs first and uses a different base calendar | up to 39% of tests in ceab, but Opus mostly handles decoys (LR line 35) | TS-19 shape bounded by instruction | ceab P7 |
| S4 Listed candidate set + single-feature seal | Six named smoothing windows; one shipped seal picks one | ~0 (Opus recovered all 4 in h3) — safe but no yield | IN-15 | dinshi GS §2(1) "A listed candidate set is not a lever; an unlisted one is." |
| S5 Anchored mirror views graded against the agent's own primary | Summary CSV must agree with the agent's own detail ledger | low (19% in PARTLY 4ee6, mostly via other faults) | TS-26 consistency not value | sugam_a P2 |
| S6 Quiet shipped run + one "idle rules are live elsewhere" line | Shipped month has no leap-day bookings; one sentence says such rules still apply | multiplies other levers; alone ~0 | W5, IN-15 | chainfold :37 |

### RISKY (worked for peers, IN-16/IN-15 exposure under our rules; would need a settling sentence that tends to leak)

| Shape | Neutral example | Cost observed | QC exposure | Evidence |
|---|---|---|---|---|
| R1 Withheld constant, unstated candidate space, recovered by calibration | Tide-gauge offset recovered from a calibration log; the set of allowed offset formulas not listed | 63-74% (inference, restoration) | IN-15/16; passed QC :124-125 only because QC missed the second fit | dinshi GS §2(1) |
| R2 Defined quantity with unstated binding time (once vs every round) | "Each orchard's fair water share from what it already holds" in an iterative allocator | 58% via gate (T1) | IN-16 in fact; QC 0 fails | poonam GS §2 P4 |
| R3 Ordering property with open operand | "Apply the discount before the tax" in a repair where the shipped code also uses the wrong base | 36% (9 checks) | IN-16 | ceab P1 |
| R4 Scope by omission (restriction only on the narrower branch) | Only the per-zone paragraph says "replay only that zone's events" | 26-64% (PARTLY tasks) | IN-16; literal text favours agent | 4ee6, af6f |
| R5 Bare definition + shipped residue fitting a narrower reading | "A source supplies a field when its record carries values"; shipped notes-only records invite narrowing | 76% (4a5f) | IN-16 via data, invisible to text-only QC | sugam_a LA3 |
| R6 Silent shipped-code fault with no contradiction cue | Shipped scorer adds where it should multiply; only the hidden truth says so | 22% | IN-15 delegated to code | 8da8 P5 |
| R7 Overloaded term implied by a computation clause, controls green both readings | "admitted" in a scheduler means two things | 29% | our IN-16 would FAIL; no QC report | h3 |
| R8 Closed-list definition where an absent input arguably fits a listed clause | Two listed causes of a late fee; a missing receipt arguably fits one | ~3% | IN-16 (emberforge family failed) | b47 P4 |
| R9 Stated core gate on whole-doc checks (amplifier, not a lever) | Ledger checks run only if the store's opening balances match | x3-5 on any miss | G2 conflict; QC W3 on T2, 0 warns on T1 | poonam GS §2 P1 |
| R10 Whole-report mutation tier, no partial credit | Mutate one input axis, compare whole report | 55/124 in one task | QC warn W3 accepted | restoration |
| R11 Combined-axis hidden store | One hidden store varies epoch, revision, edition and size at once | 38 pts, root undiagnosable | G7 gap | T2 |

### NOT ALLOWED (QC rules exist and peers only passed by luck, or self-defeating)

| Shape | Why | Rule |
|---|---|---|
| N1 Unstated key-vocabulary or value-type gate | cheap format points, not reading | QR CL-5 dispatch v1:41; TS-19 vendor v1:50 (af6f 13 pts, 4ee6 `_real_work` 15.5) |
| N2 Test stricter than the contract | | QR TS-19 vendor v1:50 |
| N3 Hidden rule with no evidence path (unstated empty value, unmapped code) | luck, not design; TRUTH lists no measurement (poonam GS §4) | LR line 24 never-used; QR IN-15 |
| N4 Negatives that grade a lever (wrong-reading detectors) | 0 fired anywhere; G4 | LR G4 (yard accepted, but no yield) |
| N5 Format carried only by shipped working code | | QR TS-19 / IN-15 (8da8 5 pts) |
| N6 Hidden tests or reference reachable in the image | artefact | a5b17048 |
| N7 Judgement-field exact match | low yield (tollgate 3) and contestable | LR J8 |

---

## 7. Proposed changes (NOT applied)

| # | File / location | Proposed change | Evidence |
|---|---|---|---|
| P1 | LR §3 G1 | Add exemption: whole-document exact equality per hidden corpus is allowed when instruction.md states once that only exact documents count (PB CL-4 kit exemption) and the cost table reports one-fact-wrong per rule. Keep owned-row rule for shipped data. | TD2; K3; b47, 4a5f, T1 cards §5; PB CL-4 row |
| P2 | LR §3 G3 | Change ">= 30% hidden" to ">= 30% hidden OR no shipped expected output of any kind". | K5; sugam_a GS §4 (4a5f 14.9%, 8da8 0% still separated) |
| P3 | LR §3 G2 | Allow a core gate only when stated in instruction.md and the gate key is a quantity graded once on its own; report gated points separately in the cost table. | TD7; poonam GS §2 P1; T2 W3 |
| P4 | LR §2 W5 | Extend: "Shipped run is quiet: no separating row, no zero counter on a planted branch, no solved example; one neutral line may say idle rules are live in other runs." | LV2; chainfold :37; LA §2(4) zero counters |
| P5 | LR §2 W6 | Extend: "No shipped expected output, receipt or solved example list, consistent or not; worked examples only on invented cases that say they are not shipped figures." | LV3; LA §2(3); LA §3 Never 11 proposal |
| P6 | LR §1 new L11 | "Repair with kept operand": a shipped bug whose fix needs both a stated order and an operand fact from a different file; Opus keeps the shipped operand. Must state the operand in the governing file to stay IN-16 clean. | sugam_b GS §4 NEW (ceab); LR line 41 "key rule from a different file than field" |
| P7 | LR §0 | Add observed behaviours: Opus reads big files by partial `head`; narrows a bare definition via a semantic flag the residue supports; repairs only faults justified by a contradiction; deletes and rewrites shipped modules it finds untidy (habit code evaporates). | sugam_b GS §2 P3; sugam_a GS §4; DX-data-product (step 16) |
| P8 | LR §3 G7 | Make G7 a build gate: every assertion message names the store/corpus and first differing key, so delivery scores are diagnosable. | T2 root undetermined (poonam GS §6); K9 |
| P9 | LR §3 G10 | Add: fuzz-difference evidence alone is not lever evidence; a lever counts only after a blind fresh-agent read (>=2 of 3 miss). | DX-metered §3; DX-caldermoor (300/300 fuzz, probe 0/300) |
| P10 | LL new row "SPELLED-TRAP" | Cause: trap file or bullet list names each wrong reading. Seen: yard spec + known_traps, T1 footguns 8 bullets, 0 yield. Fix: W1. | dinshi GS §3; poonam GS §3 |
| P11 | LL new row "PROCEDURE-SENTENCE" | Cause: one sentence names amount, method, recipient set and repetition. Seen 7/8 of ours. Fix: graded case needs facts from two files; no sentence holds all four. | LA §1; DX-tariff §2 |
| P12 | LL new row "SELF-CHECK-INVITE" | Cause: instruction invites a self-check / says "fresh inputs at other scales". Agent rebuilt hidden tier. Fix: state exactness and coupling only (LV7). | LA §2(2) |
| P13 | LL new "held" table | Record which writing patterns held at delivery (LV1-LV7) with card refs, so harden rounds pick from evidence. | §4 above |
| P14 | PB IN-16 row | Add a fourth check: "Does any shipped data residue support a second reading the text does not?" QC reads text only. | 4a5f IN-16 (C_4a5f §5) |
| P15 | PB CL-4 row | Add precedents: b47 I:11, T1 :23, 4ee6 :11/:31 (passed); T2 :7 (W3 but shipped); 8da8 no sentence (passed, do not copy). | C_*  §5 |
| P16 | PB TS-19 row | Add precedent: name each varying axis of hidden inputs in one instruction sentence (T2 :3), bound sizes (b47 I:7). | C_T2 §5, C_b47 §5 |
| P17 | PB JD-7 row | Add direction: loosen or drop criteria the oracle cannot show before delivery; never ask for a value the tests grade (T2 TRUTH.md:251-275). | C_T2 §5 |
| P18 | P2_build_v3.md:43 (template) | Add the LA §3 line: "the graded case needs facts from two files; no single sentence holds amount+method+set". | LA §3; §5 Wording |
| P19 | P2_build_v3.md:105 (template) | Drop the G5 "fresh extracts at other scales" sentence; replace with one exactness sentence. | LA §2(2); P12 |
| P20 | P9_harden_from_results_v2.md (template) | First harden step: diff ctrf test names and weights against the repo before analysing a score. | 6/21 ARTEFACT (§1) |

---

## 8. Open questions for Ayush

1. K1: our never-used list is stricter than real QC; every peer's biggest win was a rule we forbid. Do we keep LR line 24 as is, or admit RISKY shapes R2/R3 when one distant settling sentence exists (poonam GS §6 notes Opus may transliterate that sentence too)?
2. Adopt P1 + P3 (stated whole-doc exactness + stated core gate)? It is the only route peers used to reach >30% from one miss, and QC accepted it (T1 0 warns) but warned once (T2 W3).
3. Retire the H7 second-pass re-share family (LA §5) and move to repair-with-kept-operand (P6) or evidence induction with a listed candidate set plus quiet run?
4. P5 bans all shipped expected output. Does that conflict with our L1/W7 "honest control"? Proposed reading: a control may exist only if it reconciles under both readings (LV4).
5. Should harden rounds require a blind fresh-agent read (P9) before any lever is counted?
6. The yard/keyframe taskers reverted QC's settling clauses to keep trajectories valid. Do we treat "QC deferred" as passed for our own IN-16 decisions? (Recommend no.)

---

## Lessons for the master

1. Peers separated Opus by leaving one axis of a rule unsaid and re-running whole documents on unseen corpora; we wrote every separating case as a sentence and Opus copied it.
2. Ship a quiet run: no expected output, no solved examples, no zero counters; say THAT rules are idle or withheld, never WHICH.
3. Amplify by stated exactness per hidden corpus (CL-4 kit exemption), not by owned rows alone; one miss then costs 20-50%.
4. Spelled traps never paid (yard, T1: 0 yield); fuzz differences on old programs are not lever evidence.
5. Diff ctrf against the repo before reading any delivered score: 6 of 21 were artefacts.
