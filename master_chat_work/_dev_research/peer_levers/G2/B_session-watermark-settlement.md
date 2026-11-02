# B: session-watermark-settlement

Path: `T = .../Abdus Samad Ali/session-watermark-settlement/`. Score: 60.57 / 96.70 / 24.44. Phase A verdict: PARTLY. There is **no genuine test lever** (all 31 positive checks passed). This file records how the task is built, why a heavily hidden-input design still cost nothing, and how the judge produced the low score.

## 1. Inventory
- **Domain**: stream processing. Event-time watermarks, session windows, late events, replay ordering, money in decimal.
- **Archetype**: a reusable program `/app/out/settle_sessions.py <data> <out>` that writes 13 JSON artifacts, including digest chains (integrity manifest, audit seal, final state).
- **Files the agent sees**: `spec.md` (27 331 B, 460 lines, the binding contract), `numeric_contract.md`, `tolerances.md`, and ~28 data files in many formats (YAML policies: 1 active + superseded + draft; events in CSV + NDJSON shards; xlsx user keys; sqlite offsets; XML amendments; fixed-width partitions; manifest JSON). There are 8 named decoys (instruction L3) and a `calibration/control_1/` copy set with `published_manifest.json`.
- **Instruction**: 873 words in 11 lines.
- **Tests**: 35 in total. 31 positive (weight 91: weights 1/3/5) and 4 negative (-5 hardcoded, -3 reads verifier files, -3 non-stdlib/network import, -3 nondeterminism). Each check is isolated (one artifact or field family per test).
- **Hidden inputs**: yes, and they cover almost all the weight. The verifier never reads `/app/data` (header L1-8). It builds `sample` (= the shipped data, L716-719), `alpha`, `beta` and `gamma` (other seeds, gaps, bounds, lateness, ordering, idle partition, swap and decoy settings, L720-730), plus three legal format variants: BOM, default XML namespace, xlsx cells without the `r` attribute (L706-715, `_apply_variant` L732-759). Expected values come from the verifier's own reference implementation, computed before the program runs. The sample corpus is used by only 2 tests (L1629, L1636). Most checks loop over alpha/beta/gamma (`_all` L1580).
- **Judge**: 25 criteria in `batched` mode. Positive weight 45 (w1/w3); negatives R3 -3, R5 -1, R11 -5, R12 -3. **Split**: reward.toml test 0.005494 (=1/182) and judge 0.01111 (=1/90), which is 50/50.

## 2. Rule map (abridged; every graded rule is stated)
| Rule | Where | Form | Trap explained? | Shipped data separates? |
|---|---|---|---|---|
| Only authoritative source applies; decoys never | spec.md L28-34 + table; instruction L3 | one bold sentence + table | yes ("even when it is newer, larger, or easier to read") | yes |
| BOM is not content | spec.md L24 | one sentence | yes | not in shipped files (variant hidden) |
| XML default namespace, match local names | spec.md L160-161 | parenthetical | yes | hidden variant |
| Gap comparison at exactly session_gap opens/extends | spec.md (instruction L9 lists it as "which comparison at the session gap opens a new window") | one sentence in spec; instruction flags the topic | instruction names the topic | yes (test passed) |
| Program must not open the three contract docs | spec.md L20-23; instruction L5 | one sentence, said twice | yes | n/a |
| Stage order and digest folding | instruction L9 + spec | explicit | yes | yes |

Instruction L9 is a **checklist of every trap topic** ("which comparison at the session gap opens a new window and which extends the current one, where the finite lateness bound applies ..., how the per partition watermark leaves idle partitions out and never moves back, which offset row is in force..."). It points the agent at every subtle rule. This is the opposite of a lever.

## 3. Lever table (failed items)
| id | w | rule | agent | mechanism | self-test would catch? | fully stated? | family |
|---|---|---|---|---|---|---|---|
| negative_weight_non_stdlib_or_network_import | -3 | no non-stdlib/network imports | `import urllib.request` used only for `pathname2url` to open SQLite read-only (out/settle_sessions.py L19, L187) | **false positive**: the check matches the module name, not the network use | n/a | instruction asks for stdlib only, and urllib is stdlib | ARTEFACT |
| Judge R8, R13, R14, R15, R18, R19, R20, R21, R22 | 3/3/3/3/3/1/3/3/3 | "locates or constructs <boundary case> and reports what its program did" | no edge probes; self-tests were control digest (st 19, 31), determinism rerun (st 22), digest chain (st 25) | process criteria; the program handled these edges correctly (matching tests passed) | — | conduct | judge-process |
| R16 (1), R17 (1) | | run on a copy without the three docs / with `replay_ordering=event_major` | not done | conduct (odds-raising, tied to instruction L5 and the manifest field) | — | conduct | judge-process |
| R24 (3), R25 (3) | | count segment-gap candidates fitting the control; build own control and check recovery | not done | conduct | — | conduct | judge-process |
| R9 (1) | | look for repeated event_id in `raw_events.csv` before writing dedup | not done | rewards inspecting a file the spec calls a decoy (spec.md table: "`raw_events.csv` (a stale preview export)") | — | preference | judge-process (questionable) |

Genuine test points lost: **0**. Judge: 34/45, all on conduct.

## 4. Contrast: why everything passed
- **Format variants that the spec states** (BOM spec.md L24; default namespace L160) passed. In T1 the three format variants that failed were exactly the ones the spec did *not* state (xlsx phonetic runs, absolute part names, title-case SQL columns). Together the two tasks show that **a hidden variant of a stated rule costs nothing; only a legal-but-unstated property costs points.**
- **Hidden corpora with other seeds/parameters** (alpha/beta/gamma: other gaps, bounds, orderings, swaps, extra decoys): passed. They change values, not structure, and the agent's program derived everything from inputs.
- Instruction L9's topic checklist + spec's bold rules are like our DIAGNOSIS cause 4: every rule is a plain sentence with its trap named, so it was coded right on the first write (step 15 created the full 860-line program; later steps only refactored).

## 5. Agent behaviour
- Steps 1-7: read spec.md in chunks (all 460 lines), then numeric_contract.md and tolerances.md. Steps 8-14: inspected every source and decoy, including xlsx internals and sqlite tables. Step 15: wrote the whole program in one create. Steps 16-21: a small import edit and calibration run. Step 22: determinism rerun on a copy (chmod 644). Steps 23-26: eyeballed artifacts and the digest chain. Steps 28-31: a refactor with an identical-output check. Step 32: data-untouched check. Step 33: finish.
- Total: 33 steps, ~7.5 min. It made no constructed boundary inputs and ran no other-parameter runs. The final claim ("Done ... thirteen artifacts") was true, and the hidden tests confirm it.

## 6. Test design
- Expected values come from a reference implementation inside the test file over verifier-built corpora (not a fixed file). Type-strict comparison (header L7-8: "true never equals 1 and 5000 never equals 5000.0").
- Consistency checks grade each downstream document against the program's *own* upstream output (`test_closure_consistent_with_own_watermark`, `test_rollup_consistent_with_own_windows`, `test_audit_consistent_with_own_trace`). This is a good pattern that stops one upstream error cascading into many failures.
- Runtime budget: header L55-57 "Eight program runs at most ... 8 x 120 s".
- Share of weight on shipped-data-only checks: ≈ 2 tests. Hidden corpora carry nearly all the weight, yet the task did not discriminate.
- Anti-cheat issue: the network-import negative matches module names (`NETWORK_MODULES` L2103), so it fires on harmless stdlib use. This breaks TS-16 (03_Tests_QC.md L47, negatives fire on cheat only).

## 7. Judge design
- All 14 failed criteria are conduct. JD-15 (04_Judge_QC.md L92-96): conduct needs no contract sentence. Criteria that raise the odds of success (R16 run without docs, R17 alternative ordering, R25 self-built control) are fine at w1/w3. "Locates or constructs a case exactly at boundary X" is odds-raising at w3: it passes QC, but it is graded diligence, not correctness. R9 is a preference that rewards inspecting a decoy file, which is a minor finding.
- **This judge is where the overall score was lost** (34/45). The program itself was right. For our purposes it is an anti-pattern: a low score that does not mean the agent misread any rule.
- JD-18 is met by R10 (reviewable code, passed).
- Reusable pattern: "runs the program on a copy whose declared ordering field is flipped and reports which copy it kept under each" (R17). This is an odds-raising probe of an explicit switch, safe at w1-3.

## 8. QC safety
| Item | Verdict |
|---|---|
| Network-import negative by module name | NOT ALLOWED (TS-16 false positive; also stacks with judge R5 network-fetch negative only on a different act, so AL-28 is fine) |
| Exact-boundary conduct criteria | SAFE at w1-3 (odds-raising), but do not count them as a lever: they measure diligence |
| Own-output consistency tests | SAFE (good pattern) |

## 9. Writing style
1. "Every text input is UTF-8 and can begin with a byte order mark, which is not part of its content." (spec.md L23-24). **Modal "can" plus a general reading principle.** This is the stated form of a format variant; compare T1, where the variant was unstated and failed.
2. "the document can declare a default XML namespace; elements are identified by their local names" (spec.md L160-161). **Reading principle instead of a list of quirks.**
3. "every other copy of that dataset is a decoy and never applies, even when it is newer, larger, or easier to read" (spec.md L31-33). **The trap is explained outright**, which leaks (as in our CR-2).
4. Instruction L9: a long "The contract states which ... which ... where ... how ..." sentence. **Topic checklist**: it guarantees the agent looks at each rule. Avoid this if the goal is difficulty.
