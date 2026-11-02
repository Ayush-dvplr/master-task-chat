# Leak audit ed0bc62 (25 Oct 2026, audit only, no bundle edited)

Scope: 8 Harbor 0.24 bundles. Per-task evidence tables are in `OUT/<slug>.md`. Severity scale and checklist A-J are as in the issued prompt `prompts/issued/_adhoc/20261025T1045_leak-audit_ed0bc62.md`.
Base checks I ran myself: every `environment/Dockerfile` COPYs only `data` (or `repo` + `ci` for tariff), so `tests/`, `solution/`, `TRUTH.md`, generators and `_work/` never reach the image. `find` turned up no `__pycache__`, `.DS_Store`, `.git`, `*.bak` or `*~` under any of the 8 `environment/` trees. The 7 probed bundles have not changed since their probe, and each trajectory `instruction.txt` matches the bundle's `instruction.md`. Match-replay's only trajectory (20 Oct) ran on an older instruction, so J is N/A for it.

## 1. Per task

| task | tests (probe) | C | H | M | L | top leak |
|---|---|---|---|---|---|---|
| sentinel-policy-recompute | 100 | 0 | 5 | 3 | 2 | F1 `override_precedence.conf:7` spells out the whole timeout_pool algorithm: floor, the below-100 drop, and the re-share across survivors. Read at step 10 and implemented as written. F4: the shipped per-tenant `controls` reconcile only under the right `ef<cut` reading (step 27). |
| sensor-network-lsq-correlated-adjustment | 100 | 0 | 3 | 4 | 3 | F1 `schema.md:123-127` gives the amount, method and population of the second closure share. Step 24 implements it as an unconditional pass 2. F2 (recursive centring) and F3 (district of the kept shard) are also transliterated. |
| district-heat-flex-procurement | 100 | 0 | 7 | 6 | 3 | L01 `schema.md` is a complete literal recipe for all seven levers. The first write at step 15 already implements every one, and L02 `:235-241` re-share is confirmed at step 56. |
| tariff-engine-audit-repair | 100 | 0 | 4 | 4 | 3 | F01 `ci/api_contract.md:125-128` (+ `:46-48`) gives N1's amount, equal-part method and repetition. That is the `share_allowance` loop at step 18. N2 (month spans `:115-117`) and N3 (account position `:38-40`) are written the same way. |
| caldermoor-commitment-closure | 98.45 | 0 | 5 | 5 | 4 | F1 `cadence-register.md:49-53` puts the allowance key, order and tie in one sentence. F2 is the H7 re-share in `commitment-protocol.md:204-210`. All of F1-F5 appear in the step-26 first draft, which lost 0 lever points. |
| metered-usage-rating-pipeline | 100 | 0 | 5 | 1 | 4 | F1 `rating_contract.md:171-177` names the credit re-share amount, method and set. Step 15 `allocate()` is that sentence (I checked step 15 myself: `kept = [... if value >= 50]`), and step 22 re-derives it by hand. |
| data-product-config-compiler | 100 | 0 | 5 | 4 | 1 | F1 `config_contract.md:140-145` gives the cap re-share procedure: amount, keeper, recipients, Q/W, and repeat until a round gives nothing back. Transliterated at steps 19, 28 and 37. F4: the instruction's self-check paragraph led to an independent `verify.py` plus synthetic extracts (steps 26-42). |
| match-replay-desync-audit | n/a (parked) | 0 | 0 | 11 | 4 | M1 `engine-rules.md:87-88` names the rival cancellation reading ("not the latest one"). M11: the L3 allowance rule is stated four times as an algorithm. All MEDIUM because there is no current-bundle trajectory. |
| **total** | | **0** | **34** | **38** | **24** | |

**CRITICAL: none.** No bundle lets the agent reach tests, the oracle, TRUTH, generators or `_work/`. See the Dockerfile COPY lines above.

**The one leak that best explains tests at 100: the contract sentence that states the whole graded procedure.** For the shared second-pass re-share lever that means amount, method, recipient set and repetition. 7 of 8 bundles carry this lever in this form: sentinel F1, sensor F1, district L02, tariff F01, caldermoor F2, metered F1 and data-product F1. Match-replay M11 is the same shape for its allowance. In every probed trajectory the first program write is a line-by-line copy of that sentence, and no hidden test separates a copy from understanding. The same "one literal sentence per lever" form covers every other lever too (keys, chains, positions, date cut-offs). So the contract file is the hidden test plan: each sentence maps to one test (G11).

## 2. Recurring patterns, ranked by trajectory use

| rank | pattern (category) | tasks with trajectory use (finding ids) | how the agent used it |
|---|---|---|---|
| 1 | **Full-procedure rule sentence** for the scoring lever: amount + method + set + repetition, or key + order + tie (C) | all 7 probed (sentinel F1-F3, sensor F1-F3, district L01-L07, tariff F01-F04, caldermoor F1-F5/F11, metered F1-F4, data-product F1-F3/F5); match-replay M3-M8/M11 INFERRED | Transliterated in the first program write, 3-10 minutes in. 0 lever points lost on any of these levers. |
| 2 | **Self-check invitation in the instruction plus the G5 "fresh inputs" sentence** (B/I) | data-product F4 (HIGH), sentinel F6 (HIGH), metered F5, district L12, sensor F8, tariff F06 | The agent builds an independent recompute and edits single fields of `/app/data` to make mutated copies. That reproduces the hidden tier's mutations (sentinel steps 48-52, data-product steps 26-42, district steps 23-47). |
| 3 | **Shipped controls, receipts and solved examples that reconcile only under the right reading** (D/E) | sentinel F4 `controls` + F5 `effective_instant_examples.xml` (200 solved in/out-of-window cases), district L08 `export_manifest.tsv`, tariff F05 `customer_claim` + `failing_tests.log`, data-product F8 `team_overrides.json`, metered F6 type mix, sensor F4/F5, caldermoor F5 | Used as a test oracle: "tenants 14 mismatch []" (sentinel step 27), "half-open consistent True 200" (sentinel step 28), 1286 matches measured (tariff steps 22-24). |
| 4 | **All-zero counters / cold branches** that point at what the shipped data does not exercise (D) | district L10, caldermoor F7, metered F7 | The agent builds synthetic extracts for exactly those branches, e.g. district "exercising every branch the shipped data leaves cold" with about 70 assertions. |
| 5 | **Redundant restatement or decoys refuted in words** (H/A) | tariff F08, data-product F10, district L06 `[export]`, caldermoor F9, sensor F6/F7, sentinel F9 | Decoys dismissed with a quoted reason (district step 56, caldermoor step 79). Restated rules cross-confirm each other. |
| 6 | **Meaningful ids and name suffixes** (A) | sentinel F7 (`WIN-AUTH` vs `-V099`/`-prev`), district L14 (`-X`, `-Q` suffixes), data-product F7 (planted rows at top of `seq`) | INFERRED mostly. Sentinel step 17 filters on the right ids directly. |

## 3. Where the templates and tools produce these patterns (quoted; proposed changes NOT applied)

| pattern | template line (quoted) | proposed template change |
|---|---|---|
| 1 | `P2_build_v3.md:43` "Every graded rule is fully stated in a visible file (IN-15) with one reading (IN-16)"; `LEVER_RULES_v1.md:56` W9 literal-reading self-test | Keep IN-15 for the rule. Add: "the graded case must need a combination of two or more stated facts from different files. No single sentence may contain amount, method and recipient set together (H7)." Change W9 so it checks one reading across sentences, not inside one sentence. |
| 1 | `P2_build_v3.md:88` G11 "one row per rule in the contract file, each mutant dropping that rule alone; every row fails at least 1 test" | G11 makes sentence-to-test a 1:1 map. Add a reverse check: "for each scoring test, a program written by transliterating its sentence alone must fail it". This is the existing G10 differential fuzz, run on a transliteration program instead of the old probe program. |
| 1 | caldermoor issued harden `20261025T0113_harden.md:22` "rewritten in 5f2e150 to name the amount and method" and `:33` "Never weaken ... the H7 wording fix" | Master notes: never ask for a rewrite that names the amount and method. Resolve IN-16 ambiguity by keying the rule from another file (`LEVER_RULES_v1.md:43`), not by spelling it out. |
| 2 | `P2_build_v3.md:105` "State whole-document exactness up front (G5) ... on these files and on fresh extracts at other scales"; `P9_harden_from_results_v2.md:53` mandates "the G5 sentence" | Keep one exactness sentence and drop "fresh extracts at other scales". It tells the agent that hidden mutated inputs exist and invites it to rebuild them. No template line asks for an instruction-level "recompute a second way" paragraph (that wording appears only in J2, `P2_build_v3.md:97` / `LEVER_RULES_v1.md:77`). Add: "J2 conduct wording stays in judge.toml and is never echoed in instruction.md". |
| 3 | `LEVER_RULES_v1.md:13` L1 control "described truthfully"; `:54` W7; `_COMMON_RULES_v3.md:30` Never 11 forbids only an answer key that *contradicts* the contract | Add to L1/W7 what `LEVER_RULES_v1.md:43` already says: "the shipped control reconciles under both readings". Never 11 becomes "Ship no answer key, golden output, solved example list or claimed figure for a graded field, consistent or not". That covers sentinel `effective_instant_examples.xml` and tariff `customer_claim`. |
| 3/5 | `LEVER_RULES_v1.md:17` L5 "State the strict rule twice: in the field block and in the malformed-value list" | Conflicts with H1 LV-ENUM and creates pattern 5 redundancy (tariff F08). State it once. |
| 4 | no template line; `P2_build_v3.md:52` reflex pre-mortem lists self-tests on shipped data | Add to DS rules: "no counter in shipped data or controls that is 0 for a branch the hidden tier plants". |
| all | `P9_harden_from_results_v2.md:42` Cause 4 "what gave it away (rule next to its use, trap explained, shipped separating example, self-test)" | Widen the list: full-procedure sentence, self-check paragraph and G5 sentence, reconciling control, solved example list, zero counter, meaningful id/suffix. `:19`/`:22` still point to `_COMMON_RULES_v2` and `QC_FIX_PLAYBOOK.md`; repoint them to v3 and v2. |
| all | `tools/issue.py:110-113` checks only `<SHA>` and `name_session.py` | Add a draft lint that flags master notes containing "name the amount", "name the method" or "Never weaken ... wording", and that greps instruction drafts for "second way" and "fresh extracts". |

## 4. New LEAK_LIBRARY rows (proposed, not applied)

| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| SN-1 timeout_pool re-share | `override_precedence.conf:7` floor, below-100 drop, re-share across survivors in one sentence | step 10 read, step 33 code | H7, new "no single-sentence procedure" |
| SN-4 window cut | per-tenant `controls` reconcile only under `ef<cut`; 200 solved cases in `effective_instant_examples.xml` | steps 27-28 | W7 both-readings control; Never 11 widened |
| SL-1 closure second share | `schema.md:123-127` amount + method + population | step 24 | H7 |
| DH-1 grant re-share | `schema.md:235-241` "every cent of F is shared again ... across only" | step 15, step 56 | H7 |
| TA-N1 allowance re-share | `api_contract.md:125-128` + `:46-48` equal parts, repetition | step 18 | H7; state once (L5 conflict) |
| CA-H7 second-pass allocation | `commitment-protocol.md:204-210`, rewritten in 5f2e150 to name amount and method | step 26 | H7; master-note lint |
| MU-1 credit re-share | `rating_contract.md:171-177` | step 15 `allocate()` | H7 |
| DP-1 cap re-share | `config_contract.md:140-145` Q/W and repeat-until-zero | steps 19, 28, 37 | H7 |
| DP-self-check | instruction para 4 "Work out the expected figures ... from the contract" | steps 26-42 `verify.py` + mutated copies | J2 stays in judge only |
| DH-zero | all-zero counters in shipped quality data | step 56, about 70 synthetic assertions | new DS zero-counter rule |

## 5. Open questions for Ayush

1. All 7 probed bundles carry the same second-pass re-share lever, and all 7 lost 0 points on it. Do we retire that lever family rather than reword it for the eighth time?
2. If IN-15 ("every graded rule fully stated") stays, is there any wording of a single rule that Opus cannot transliterate? Or must difficulty move to rule interaction across files, which `P2_build_v3.md:43` already names ("how they interact")?
3. Should the G5 "fresh inputs" sentence and any instruction self-check paragraph be dropped, given they led the agent to rebuild the hidden mutations (sentinel F6, data-product F4)?
4. Widen Never 11 to forbid consistent answer keys and solved example lists too? Several negative checks named `hardcoded_sample_answers` did not fire on 25 Oct, per tariff/metered/data-product harden notes `:21`.
5. Match-replay has no trajectory on the current bundle. Probe once before deciding its 11 MEDIUMs, or fix M1/M11 blind?

## Lessons for the master
single-sentence full procedure (amount+method+set+repeat) is transliterated 7/7 | template_change: P2_build_v3.md:43 add "graded case needs facts from two files; no sentence holds amount+method+set"
G11 sentence-to-test map makes the contract the test plan | template_change: P2_build_v3.md:88 add reverse check: a transliteration program must fail each scoring test
"fresh extracts" and self-check wording invite agents to rebuild hidden mutations | template_change: P2_build_v3.md:105 drop "fresh extracts at other scales"; J2 wording never in instruction
honest controls and consistent answer keys act as an oracle | template_change: _COMMON_RULES_v3.md:30 Never 11 forbids any answer key/solved list; LEVER_RULES_v1.md:13 control reconciles under both readings
master notes pushed "name the amount and method" as the IN-16 fix | template_change: tools/issue.py:110 lint drafts for "name the amount/method" and "Never weaken ... wording"
