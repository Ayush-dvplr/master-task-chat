# B: reminder-store-reconciliation

Paths: `T = .../Abdus Samad Ali/reminder-store-reconciliation/`, run `T/trajectories/claude-opus-5/run_1/`. Score 62.25 / 83.33 / 41.18.

## 1. Inventory
- **Domain**: binary container decoding + parameter recovery + business settlement (reminder/commitment store, revision supersession, escalation, desk routing).
- **Archetype**: a reusable program `/app/out/transform.py <DATA_DIR> <OUT_DIR>` that decodes captures, recovers 12 hidden parameters from a calibration slice, settles them, and writes 13 JSON/JSONL documents. It is rerun on hidden corpora.
- **Files the agent sees** (`environment/data/`, 28 files): specs `container-format.md` 9632 B, `report-schema.md` 8905 B, `assistant-charter.md` 3440 B, `reading-order.md` 2933 B, `calibration.md` 2755 B (12 control figures), `desk-routing.md` 1525 B, `escalation-policy.md` 1228 B, `supersession-policy.md` 1193 B; tables `requester-directory.csv` 2706 B, `tag-table.csv` 710 B, `identity-events.csv` 570 B, `desk-roster.csv` 153 B; captures `cycle_01-06.rmx` (1.3–2.5 KB), `calib_store_01-03.rmx`, `sample_store_01-03.rmx` with `.decoded.json` (~10 KB each); `example_desk_report.json` 274 B.
- **Instruction**: 771 words, 23 lines.
- **Tests**: 35 (32 positive, weight 78; 3 negatives: -5 hardcoded, -5 reads supplied answer data, -3 nondeterministic). Each test compares one corpus/field slice (`_same_rows(corpus, [field])`), so they are isolated with partial credit. Shipped-data checks: format 1, shipped ledger 5, summary 3, desk 5, class 5, record_adopts 3, record_reconciles 3 = **25/78**. The rest (≈53/78) run the program on hidden corpora.
- **Hidden inputs**: yes. They are produced at test time by an in-file deterministic generator (`test_output.py` header L1-11; seeds `SAMPLE_SEED` L23, `CHALLENGE_SEED` L26, `EVAL_SEED` L29; `EVAL_PARAMS` L122-135; `TIE_CORPORA` L149-168; trap corpora with one flag on, L1466-1467; mutations L1573-1579). Expected values come from the verifier's own reference settlement, computed before the agent's program runs (`_pristine` L2213-2251).
- **Judge**: 29 criteria, `mode = "batched"`, positive weight 51 (R1 w5; 10 × w1; 12 × w3; 6 negatives). **Split**: reward.toml test 1/156, judge 1/102, so 50/50.

## 2. Rule map (graded rules that matter for the levers)
| Rule | Where stated | Form | Trap explained? | Shipped data separates? |
|---|---|---|---|---|
| Parameters recovered from calibration; ties are allowed and either tied value is fine | `calibration.md` L3-8 "A wrong value moves at least one of them unless that value reads and settles every calibration capture exactly as the right one does, and such a value settles the cycle captures ... the same way" + instruction L3 "in the calibration slice shipped here exactly one candidate of each reproduces every control figure" + L3 "Adopt the candidate a control supports and no other" | **default + exception split across 2 files**; uniqueness is scoped to the shipped slice by the phrase "shipped here" (scope by omission for other slices) | No. The tie clause is written as a property of wrong values, not as "your search must tolerate ties" | **No.** In the shipped slice each parameter is unique by construction (instruction L3), so a uniqueness assertion never fires on shipped data |
| Program reruns on other params and bigger slices within 200 s | instruction L13 | one sentence | Partly (names the rerun and the time limit) | No |
| Transforms are undone in an order the contract implies | instruction L5 "in an order the container contract implies rather than states"; container-format.md L72-79 flag list | implied by definition | Says an order exists, not which | Yes (cycle/calib captures carry all or almost all flags) |
| Supersession: second-newest governs; newest governs if raised ≥ grace after predecessor | supersession-policy.md L11-18 | default + exception, explicit, trap named ("opposite of the reading most stores use", L13) | Yes | Yes |
| Torn records dropped from cycle only; damaged calibration capture still counts for alias seed | calibration.md L25-29 | one sentence each | Yes | Yes (hidden mutants also) |
| Falsifier = first control in print order | instruction L3, calibration.md L10 | one sentence, said twice | Yes | Yes |
| Decimal facility, fresh clean pass, closing-message facts | instruction L19 | one sentence | n/a | n/a |

## 3. Lever table (failed checks and criteria)
| id | w | rule graded | agent's reading | correct reading | mechanism | self-test on shipped data catches? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| test_trap_* ×12 (due_chain, lead_delta, priority_drift, block_shuffle, backref_window, count_bias, endian_island, span_shadow, note_rotate, tag_alias, sentinel_escape, crc_span) | 1 each | per test docstring, the inverse of one transform on a corpus where only that flag is on | step 12 `recover()`: keep every survivor, multiply across stages, then `if len(survivors) != 1: raise SystemExit('parameters underdetermined ...')` (out/transform.py L742-770) | with a transform off, its parameters are unconstrained; any surviving value is acceptable (calibration.md L5-8) | **identifiability collapse on a degenerate hidden corpus**: valid input makes the calibration unable to separate candidates, so a uniqueness assertion, or a search that multiplies unpruned survivors, crashes or times out (INFERRED timeout: verifier 40 m 41 s ≈ 12 × 200 s) | **N**: the shipped slice is unique by design and the agent never built a corpus with flags off (trajectory search: no step mentions ties or underdetermination apart from the step-12 code) | YES (calibration.md L3-8 + instruction L3 "shipped here" + L13) | NEW "promise scoped to shipped data" + E (stacked: time limit × tie tolerance) |
| test_generalisation_shifted_grace_boundary | 1 | governing revision when every gap equals 45 | same SystemExit: grace 15/30/45 tie on every control | any tied grace gives identical cycle settlement (calibration.md L7-8) | same mechanism; the settlement comparison `>= grace` (L505) is correct | N | YES | same |
| Judge R17 | 3 | run on captures written under other params and check adoption | never did | conduct probe | process: no self-made corpus | — | conduct (no sentence needed) | judge-process |
| R20, R21, R22, R23, R25, R26, R27, R28, R29 | 3 each | print a specific edge-case probe (torn record before another; own encoder byte-compare; timing on larger slice; damaged smallest-store alias seed; escalation cascade pass count; group exactly at grace; v3 heartbeat; all-desks-full fallback; same-minute tie-break) | none of these printed | — | process criteria naming a specific probe | — | conduct | judge-process |

Test points lost genuinely: **13/78** (one root cause). Judge: 30/51, all on process-probe criteria.

## 4. Contrast: what the agent passed and why
- **Stated rules with shipped instances** (shipped ledger/summary/desk/class, torn records, frozen merges, damaged companion, older capture, retired requesters, public sector): each rule is one sentence, often with the trap named ("opposite of the reading most stores use"). The agent coded them right on the first write. This matches our DIAGNOSIS cause 4 (leaked levers CR-1..CR-5).
- **Hidden corpora that only change values** (fresh cycle under EVAL_PARAMS, tie_a/tie_b, wide calibration): passed, because a later control separated the tie and the staged search pruned early, so it stayed fast. The peer's own anti-brute-force corpus (comment L143-148) cost nothing.
- Lesson: as in T1, hidden reseeded inputs cost points only when they produce a **structurally different** but legal situation (here: unidentifiable parameters). New values for the same structure cost nothing.

## 5. Agent behaviour
- 72 steps, ~17.5 min. Steps 2-8 read every spec file fully (container-format, charter, reading-order, calibration, supersession, escalation, routing, report-schema, CSVs, example). Steps 9-11 probed captures. Step 12 wrote the whole `transform.py` in one create, uniqueness assert included. Steps 13-35: fixes plus per-parameter control sweeps on shipped data. Step 36: first full run. Steps 47-48: logging/falsify. Step 59: read-only copy run as user `agent`. Step 62: frozen-merge probe. Steps 63-71: clean pass, chmod 755, standalone copy test. Step 72: closing claim "All twelve parameters were recovered..." (~0.5 s run).
- Self-tests: all on shipped data. It did test permissions and standalone use (the "how it is run" constraints) but never the "other parameter values" clause. No sign it noticed the tie risk. The final claim is true for shipped data and false for the generalisation the instruction promised.

## 6. Test design
- Expected values: the verifier's independent reference settlement on generated corpora (header L1-11), computed before the agent runs. Not a fixed file.
- Partial credit: per corpus × field. **Concern:** 12 trap tests named after distinct transforms all failed for one recovery bug. Their docstrings describe a transform inverse, so the test names misstate what was actually separated. A weaker program that crashes on any degenerate slice loses 12 points for one mistake (TS-20 double-billing risk, INFERRED).
- Anti-cheat: altered/0-mode `.decoded.json` answers (L2428-2443), hardcode check via EVAL_PARAMS corpus, nondeterminism rerun. None fired.
- Share on shipped-data-only checks: 25/78 ≈ 32%.

## 7. Judge design
- Failed: 10 × w3 conduct probes (listed above). JD-15 (04_Judge_QC.md L92-96): conduct criteria need no contract sentence, but each must be satisfied by every competent route or be odds-raising. Criteria that demand one exact probe (R21 "writes an encoder ... byte-compare", R27 "constructs a version 3 capture with heartbeat") are **preference** (another competent route exists), so at w3 they are a *minor* finding. R17 and R22 (test on other params; time a larger slice) are **odds-raising** and directly tied to instruction L13, so they pass at w3.
- JD-7: the oracle can meet all of them (they are actions). JD-8: R17/R22 overlap in spirit with the generalisation tests but observe different things (trajectory vs output), so OK.
- JD-18 met (R9 code quality, passed).
- **Reusable pattern**: "probe the instruction's own generalisation clause" (R17: build an input under other parameters and confirm recovery). It is safe at w1-3 and it rewards exactly the self-test our agents skip.

## 8. QC safety of the lever
| Lever | IN-15 | TS-16 | TS-19 | TS-20 | AL-28 | Verdict |
|---|---|---|---|---|---|---|
| Promise scoped to shipped data + degenerate hidden corpus (ties legal, uniqueness only "here") | stated (calibration.md L3-8, instruction L3/L13) | n/a | learnable from text; no shipped instance (flag as "undocumented edge" risk if QC wants one) | 12 tests for one behaviour → should collapse to 1 test of weight 3-5 | n/a (positives) | **RISKY**: legal but needs one test, not 12, and the generalisation sentence must stay explicit |
| Judge "probe-specific" criteria | conduct | — | — | — | — | RISKY at w3 (preference); SAFE when phrased as odds-raising (any self-made input under other params) |

## 9. Writing style (technique, short evidence quotes)
1. "in the calibration slice shipped here exactly one candidate of each reproduces every control figure" (instruction L3). **Scope-limited promise**: the true fact is stated for the shipped data only; the agent generalises it.
2. "A wrong value moves at least one of them unless that value reads and settles every calibration capture exactly as the right one does" (calibration.md L5-7). **Exception phrased as a property of the data, not as an instruction to the solver**, so it reads as reassurance, not as a requirement for the search.
3. "in an order the container contract implies rather than states" (instruction L5). **Announce that a derivation exists without giving it.** The rule is fully determined by the contract, but the agent must derive it.
4. "may hold more captures and more records than the one shipped here ... each run must finish within 200 seconds" (instruction L13). **A stacked constraint (scale × time) attached to the generalisation clause**, which turns a correct but naive search into a failure.
