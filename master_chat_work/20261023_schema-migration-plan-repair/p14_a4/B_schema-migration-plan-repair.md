# Phase B: trajectory autopsy, schema-migration-plan-repair attempt 4 (41af690)

Step indices are trajectory list indices; step_id is the index plus 1. Times are UTC on 23 Oct 2026, and the agent started at 15:47:25.

## 1 Inventory

- **Domain and archetype.** The domain is Software Engineering (task.toml): a repo-repair task. The agent fixes a stdlib Python package `migrakit` (src layout, under `/app/repo`) that has 17 seeded defects. F1 to F15 are in DESIGN.md:57-79; F16 (token trim) and F17 (receipt) were added at harden P9 v2 r1. The defects sit across planner, executor, identity, feed, pipeline, report and CLI.
- **Instruction.** instruction.md is 13 lines and 247 words, and delegates to `/app/ci/repository_contract.md` (K1 to K19).
- **Files the agent sees** (`/app/ci`):

| File | Size | Rows | Contents |
|---|---|---|---|
| repository_contract.md | 8708 B | 153 lines | |
| migration_semantics.md | 3482 B | 64 lines | M rules |
| null_semantics.ini | 2750 B | 93 lines | N1-N8 header |
| correction_log.txt | 78925 B | 1389 lines | C1-C8 header |
| partner_aliases.xml | 153245 B | 2265 lines | P1-P4 comment |
| report_taxonomy.json | 1297 B | 56 lines | T1-T3 |
| field_policy.tsv | 38172 B | 1105 lines | |
| migration_edges.csv | 95071 B | 1401 lines | |
| partner_batches.jsonl | 1794541 B | 8000 lines | |
| partner_order.tsv | 28716 B | 2051 lines | |
| replay_manifest.csv | 55042 B | 2201 lines | |
| schema_versions.json | 102042 B | | |

  The repo also ships `tests/test_visible.py` (5701 B, 9 tests: one_edge_plan, rename_then_cast_execution, signature_without_nulls, single_hop_alias, unknown_schema_code, empty_plan_at_target, fingerprint_stable, module_entry_help, cli_runs_from_other_folder).
- **Tests.** `tests/test_output.py` is 939641 B and holds 63 checks.
  - 57 positives worth 201 points:
    - thirteen w1, of which six are structural/shipped-input (3.0%) and the rest isolated rule checks;
    - twelve w3, all isolated;
    - thirty w5: worlds 01 to 28 plus 2 mutation tests, 150 points (74.6%).
  - Isolated checks total 41 points (20.4%).
  - 6 negatives worth -14:
    - unsafe_archive_members -1
    - hardcoded_sample_answers -5
    - filename_dependent_behaviour -3
    - deleted_visible_tests -3
    - nondeterministic_output -1
    - entry_points_mutate_arguments -1
- **Hidden worlds.** Each world is built inside test_output.py from `EVAL_SEED = 33461789` (line 28) with `random.Random(EVAL_SEED*1000+salt)` (line 8260). Gadget mixes are named in the world names (state, tie, null, policy, tokens, corrections, replay, feed, summary, cli, scale, plus the P9 gadgets REJECT, SCOPE, PAD and DAMAGE). Expected values come from an independent reference pipeline in the tests, which was cross-checked against repo_fixed on 304 worlds (DESIGN.md:213). Outputs are compared as whole JSON text.
- **Judge.** 9 criteria, mode batched, model openai/gpt-5.6-sol, reading the ATIF trajectory. Positives: R1 3, R2 3, R3 3, R4 3, R9 1 (total 13). Negatives: R5 -3, R6 -5, R7 -1, R8 -3.
- **Reward split.** 0.5 tests / 0.5 judge (reward.toml 0.5/201 and 0.5/13).

## 2 Rule map (graded rules)

Sentence forms used in the table: plain = one plain sentence; split = split across files; def = implied by a definition; default+exc = default plus exception; scope-omit = scope by omission.

| Rule | Where (file:line, quote) | Form | Trap explained? | Shipped data separates? |
|---|---|---|---|---|
| L1 receipt control | contract:79-86 "`lines` is the number of records whose `batch` is that batch ... The run lists in `receipt_mismatches` the sorted ids of the batches whose count or XOR differs"; K18 contract:127-128 | plain | N | N (shipped receipts all honest, `[]`) |
| L2 receipt XOR over lines as received | contract:81-84 "XOR of the first eight hex digits of `record_fingerprint(schema, payload)` over those records' lines as received"; K17 contract:120-121 "`fingerprint` (null before the partner stage passes)" | split (contract K13 and K17) | N | Y for F17 (25 shipped batches mismatch under the shipped code) |
| L6 receipt scope | contract:81 "records whose `batch` is that batch" + K15 contract:97-98 "Such a record has `batch`, `partner`, `key` and `schema` null." | def + split | N | N (bad lines renamed to B99902-B99905; W5) |
| L5 tokens exact | null_semantics.ini:20-21 N6 "a string exactly equal to one of the partner's null tokens"; normalising neighbours ini:24 N8 "surrounding spaces are trimmed" (token text) and migration_semantics.md:25,27 M5 "surrounding spaces ignored" (casts) | plain, beside normalising | N | Y (40 values; agent measured at idx40) |
| M6/M7 state planning | migration_semantics.md:31-39 "A plan may pass through a schema more than once." | plain | N | partly |
| M8 tie | migration_semantics.md:41-44 smallest cost, then lexicographic edge-id list | plain | N | Y |
| N1-N4 null/absent/fill | null_semantics.ini:3-18 | split | N | Y (16 decoy records, DESIGN.md:211) |
| C4 first arrival | correction_log.txt:14-19 "A later arrival at the same schema applies nothing." | plain | N | N (agent idx40: "applied at the final schema arrival 0") |
| K15 bad lines continue | contract:95-99 | plain | N | Y (12 E_PARSE) |
| K16 replay identity | contract:101-110 | plain | N | Y (383 replayed, 44 superseded) |
| P1-P4 identity | partner_aliases.xml:2-13 | plain | N | Y |
| T1-T3 summary | report_taxonomy.json `rules` | plain | N | Y |
| K10 CLI cwd | contract:54-58 | plain | N | Y (visible test) |
| K14 scale 10 s | contract:88-93 | plain | N | n/a (oracle fails op-heavy wide graphs; see A §3) |

None of the rules explains its trap; the W1 rule is respected.

## 3 Lever table (L1, L2, L5, L6 and the other world-exercised rules)

| Id | Weight in tests | Rule | Step first coded (quote) | Right first write | Self-test touched (step) | Why held | Family | Nearest LEVER id |
|---|---|---|---|---|---|---|---|---|
| L1 RECEIPT green control | 14 DAMAGE worlds + mutation_receipt_moves_only_mismatches (w5) | contract:79-86 | idx23 15:52:46, `_receipt_mismatches` recomputes count and XOR | Y | Y: idx72 scenario B2 wrong count, `receipt_mismatches` only B2 (R1 met) | Agent recomputed from the definition and never trusted shipped `[]` | D | L1 |
| L2 RECEIPT make-it-match | 15 REJECT worlds + receipt_counts_partner_rejected_lines (w3) | contract:81-84 + 120-121 | idx23: `fingerprint = record_fingerprint(document["schema"], document["payload"])` in place of the F17 `records[...]["fingerprint"]; if fingerprint is not None` | Y | Y: idx72 partner-rejected lines (R2 and R9 met) | "lines as received" read literally; agent never treated the record field as the source | NEW | L2 |
| L6 RECEIPT scope by definition | 14 SCOPE worlds + receipt_skips_lines_rejected_at_parse (w3) | contract:81 + 97-98 | idx23: `batch = records[item.line]["batch"]` with E_PARSE `_blank_record(item.line, None)` | Y | Fork named on shipped data only, idx36 ("interpretation c ... (a) ... 7988/7988, mismatch 0/0"); no separating probe (R3 missed) | Agent took "records whose `batch`" as the record field, which K15 nulls | A | L6 |
| L5 TOKENS strict beside normalising | 15 PAD worlds + tokens_match_exactly (w3) + pipe_bad_lines_run_continues + mutation_tokens (w5) | ini:20-21 vs ini:24, M5 | idx23: docstring "a value matches a token exactly", `value in tokens` (F16 `.strip()` removed) | Y | Measured on shipped, idx40 ("trim-vs-exact differs 40"); never ran the package (R4 missed) | "exactly equal" read literally; F16's docstring "compared trimmed, as the tokens are" did not persuade it | F | L5 |
| STATE M6/M7 (F1, F2) | worlds state* + plan_revisits_schema_with_new_state, ladder_large_state | migration_semantics.md:31-39 | idx17 15:51:58 planner rewrite | Y (later rewritten for speed only; fuzz bad 0 at idx41-43, idx63) | Y: idx41-43 fuzz_planner | Stated plainly; the agent re-derived planning state as (schema, field states) | B | L3 |
| TIE M8 (F3) | tie* worlds + plan_tie_first_edge_decides | :41-44 | idx17 | Y | Y (fuzz) | plain | E | none |
| NULL/POLICY N1-N4 (F5, F6, F7) | null*/policy* worlds + signature_keeps_explicit_null, exec_add_fill_absent_vs_null | ini:3-18 | idx14 records.py, idx20-21 contracts.py | Y | Y: idx72 policy/ini variants | plain sentences per state | A | L4 |
| CORRECTIONS C4 (F8) | corrections* worlds + exec_correction_first_arrival_only | correction_log.txt:14-19 | idx14-17 executor | Y | Y: idx40 measured | plain | C | L3 |
| FEED K15 (F13) | feed* worlds + pipe_bad_lines_run_continues, pipe_rejection_codes | contract:95-99 | idx19 15:52:2x feed.py | Y | Y: idx36 problem counter | plain | A | none |
| REPLAY K16 (F10) | replay* worlds | contract:101-110 | idx23 | Y | Y: idx72 replay/REISSUE | plain | C | L3 |
| IDENTITY P1-P4 (F12) | identity_* checks (w1) | aliases.xml:2-13 | idx18 identity.py | Y | Y: idx38 cycle partners, idx72 loop | plain | C | none |
| SUMMARY T1-T3 (F14) | summary* worlds + summary_categories_code_first, summary_partner_order_by_rank | taxonomy rules | idx22 classify.py | Y | Y: idx28 full run | plain | E | none |
| CLI K10 (F15) | cli* worlds | contract:54-58 | idx25-26 | Y | Y: idx27 visible tests | plain | none | none |
| SCALE K14 (F4) | scale worlds 04, 08, 12, 15, 18, 28 | contract:88-93 | idx17, then idx51/58/61 | Y on graded ladders | Y: stress idx44-63 | graded ladders easy for any state-aware planner | D-like perf | NOT ALLOWED (oracle fails, A §3) |

## 4 Near misses (natural-trap candidates)

1. **idx36, L6 scope.** The two readings were (a) count only admitted lines, i.e. records whose `batch` is set, or (c) count every line whose document names a receipt batch. The agent computed both; shipped data could not separate them ("mismatch count a 0 / c 0"). Its code was already (a) from idx23, so the definition in K15:97-98 decided it. No miss.
2. **idx40, L5 tokens.** The readings were trim versus exact. The agent counted 40 separating shipped values and kept exact, citing N6 "exactly". No miss.
3. **idx67, M5 decimal forms** (`.5`, `5.`). The agent scanned and found `0 []` shipped cases. The shipped `_DECIMAL` regex was already right and was never changed. Not a repair. IN-16 ruling (schema v3:32) forbids building on the ambiguity of decimal-string casts.
4. **idx53-63, K14 performance.** The agent spent about 94 min (15:57 to 17:31) making the planner fast and ended with 78 s on its own wide graphs. This is the only place real difficulty showed. Our oracle is slower still (43 s / more than 400 s in-limits), so it cannot be graded (see §8).

No other forks appear in the trajectory. The `message` fields at idx12-23 are empty, so the repair burst carries no visible reasoning.

## 5 Agent behaviour

- **Read order.**
  - idx2 `find /app`, then idx3 `cat repository_contract.md` (full), then idx4 `cat migration_semantics.md` (full).
  - idx5: `head -60 null_semantics.ini` (N header lines 3-25 covered), `head -60 correction_log.txt` (C header 3-30 covered), `head -40 partner_aliases.xml` (P header 2-13 covered), `cat report_taxonomy.json`.
  - idx6 data heads; idx7-10 all repo source and `tests/test_visible.py`.
  - Every rule text was read in full by 15:48:03, about 0.6 min in.
- **Plan.** No written plan; the message fields are empty. It copied the repo to /app/orig-repo and ran the visible tests (idx12), then rewrote module by module (idx14-26).
- **First full repair.** 15:51:23 to 15:52:57 (4.0 to 5.5 min). The visible 9 OK at idx27 (15:53:00), and the full shipped run at idx28.
- **Graded logic changed afterwards?** Only planner.py (idx51, idx58, idx59, idx61, idx62), for speed. Equivalence was checked by its own fuzz and by our 1600-case differential (0 differ).
- **Self-tests.** Shipped-data measurements (idx29-40, idx65-70), planner fuzz (idx41-43, idx63), stress (idx44-63), one scenario folder (idx72-73), and a zip re-test (idx89).
- **Size.** 96 steps, 112.4 min.
- **Time per phase:**

| Phase | Minutes |
|---|---|
| Reading | 0.6 |
| Repair | about 5 |
| Shipped probes | about 4 |
| Planner performance | about 94 |
| Scenario and deliverables | about 8 |

- **Final claim vs reality.** The tests claims all held (100). The K14 claim was false; R8 fired (A §3).

This matches LEVER_RULES section 0: it read everything first, wrote the program once 3 to 10 min in, never changed graded non-perf logic, and self-tested on shipped data and its own tiny examples.

## 6 Test design

- **Expected values.** They come from the tests' own reference pipeline and gadgets by construction. Ladders use the tests' own planner, written apart from solve.py (DESIGN.md:100, 213).
- **Partial credit.** Per check only; each world is all-or-nothing on whole-file JSON text.
- **Cascades.** A single wrong lever reading fails every world carrying that gadget, about 14 to 15 worlds × 5. Examples: W_receipt_always_empty 0.5672, W_receipt_make_it_match 0.4876, W_receipt_counts_parse_rejects 0.5124, F16 0.5672 (LEVERS.md). This is intended G-cascade, not stacking: one property per world mix.
- **stacking_check.py** reported "63 checks, positive total 201, negatives -14; judge: 9 criteria, positive 13". Corrections to its hints:
  - It puts `api_entry_points_importable` in whole_doc; it is an isolated w1 import check.
  - It puts archive_src_layout, visible_repo_tests_pass_from_archive, test_fixes_matches_visible_test_runs and repair_report_well_formed in isolated; they are structural (shipped-input-only) checks.
  - Corrected shares: shipped-only 3.0% (≤5% OK), isolated 20.4% (≤30% OK), whole-doc hidden 74.6% (≥50% OK).
  - Its TS-26 duplicate hint over worlds is a false positive. The same literal "condition not met" comes from a shared wrapper, and each world uses a different seeded gadget mix.
  - TS-13 multi-assert hints: none.

## 7 Judge design beyond R6

- **JD-7.** The oracle `self_checks` (solve.py:575-626) meets R1, R2, R3, R4 and R9 and avoids R5, R7 and R8. R6 as written is tripped by the oracle (A §3); this is the only JD-7 break.
- **JD-8.** R1-R4 and R9 grade the agent's probing conduct, not the package output the tests grade. Different observable: no overlap.
- **JD-14 / JD-15.**
  - R2 (w3, fingerprint field) and R9 (w1, receipt result) share one constructed feed: "a batch holds a line rejected at the partner stage". They read different observables, and a4 met both from one scenario. MINOR risk of double payment for one probe; acceptable at w1.
  - Conduct positives are odds-raising at w3, not w5: JD-15 OK.
- **JD-18.** R5 (debug print or commented-out code under src/migrakit, -3, state_change) is the named-shape code-quality criterion. OK.
- **R8.** Honesty negative (JD-11 "fabricating success claims"), final_answer target. Correct as written.

## 8 QC safety per candidate

| Candidate | IN-15 | IN-16 | TS-13 | TS-16 | TS-19 | TS-20 | TS-26 | AL-27 | AL-28 | Ruling |
|---|---|---|---|---|---|---|---|---|---|---|
| M5 decimal-string forms (`.5`, `5.`) as a graded case | n/a | FAIL (QC_RULINGS IN-16 schema v3:32: float cast of decimal strings ruled ambiguous) | ok | n/a | ok | ok | ok | ok | ok | NOT ALLOWED |
| K14 op-heavy wide graph within 10 s | ok (stated) | ok | ok | n/a | FAIL: oracle cannot meet it (in-limits wide more than 400 s), so a graded world would rob an honest agent (TS-17/19 honest-agent-loses) | ok | ok | ok | ok | NOT ALLOWED until the oracle planner is fast |
| L6 separation in shipped data | ok | ok | ok | n/a | ok | ok | ok | ok | ok | NOT ALLOWED by W5 (separating case must stay hidden-only; LEAK_LIBRARY shipped-boundary leak) |
| L5/L1/L2/L6 as they stand | ok | ok (N6 "exactly"; matches IN-16 ruling, case stated for strings) | ok (TS-13 schema v2/v4 MINOR history only) | ok (negatives fire only on cheats; none fired on a4) | ok (TS-19 v3:35 changed_functions ungraded, unchanged) | ok | ok (worlds differ by gadget) | ok (each gadget present in 14-15 worlds; AL-27 rulings cohort v3:44 / district v4:39 do not apply) | ok (largest act group: hardcoding -5 tests only; R6 -5 judge only, no test reads history) | SAFE, but already beaten |

**Result: no SAFE candidate the agent can plausibly misread.**

Bundle defect to record: K14 (contract:88-93) promises something our oracle cannot do on in-limits op-heavy graphs. It is ungraded, so it is harmless to the score, but it is an untrue contract sentence. It also makes R8-style claims about K14 a trap for honest agents who trust the contract. Fix by narrowing K14 or by speeding up the oracle.

## Lessons for the master
- Opus read every rule file within 1 min and wrote all four levers right in one script at 5 min. It explicitly measured both forks (idx36, idx40) on shipped data. Forks it can name and test do not trap it.
- Its only real struggle was performance (94 min). A performance lever is only usable if the oracle is several times faster than the stated limit on worst in-limits inputs; measure that first.
- stacking_check misclassifies structural w1 checks and flags shared-wrapper strings as TS-26 duplicates. Correct those hints by hand, as done here.
