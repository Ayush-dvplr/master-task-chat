# sentinel-policy-recompute: harden r3 Phase 1 diagnosis (9aaa7c6)

Probe 2 (harness attempt 3, bundle after r2 0074a64): tests 44/44 = 100 (12/12 positive checks; the 3 negatives did not fire), judge 14/37 = 37.84, overall 68.92. Only the tests gate fails.

## 1. Phase A: GENUINE
- `Run 1/result.json`: `exception_info: null`, run 17:03:01Z to 17:14:57Z (about 12 min, no timeout).
- `verifier/test-stdout.txt`: the only failures are the 3 negatives ("AssertionError: honest baseline ..."); reward 0.6892. ctrf: 15 tests, 12 passed, 3 failed (negatives), weighted 100.0. No Permission denied, Errno 13, Traceback or missing artifact; all 7 artifacts in the manifest have status ok.
- The staged copy `.kiro-staged-tasks/sentinel-policy-recompute` vs BUNDLE (`diff -rq`): only `.kiro-staged-from` and the harness-added `host.docker.internal` in task.toml allowed_hosts. Same bundle.
- The judge (gpt-5.6-sol) read the response and quoted step 45 for R9 ("claims exhausted-allowance mutation verified, but step 45 command has no displayed result").

## 2. Causes
| Cause | Verdict | Evidence |
|---|---|---|
| 1 Run error or wrong copy | NO | See Phase A. |
| 2 Harness or rescoring change | NO | Same scoring path as probe 1 (tests 100 in both probes). pass_summary: combined 68.92 = mean of 100 and 37.84. |
| 3 Our QC or fix rounds made it easier | NO (minor) | Tests were already 100 at probe 1 (71.62, test-depth 840adf9) before r2. r2 replaced L2/L3 with N1-N3 and touched quota_limits.cfg, units_reference.txt, effective_windows.xml, override_precedence.conf, override_deltas.json conventions, tests and solution. None of these edits removed difficulty; they added more rules of the same kind. |
| 4 Levers weak by design | **YES: PRIMARY** | Every lever traces to a contract sentence that names its key, its source file and its separating case. Fuzz on the probe-2 program: 0 of 307 corpora differ (table below). |

**PRIMARY CAUSE: Cause 4.** Each N lever is a lookup. The sentence that states it also names the case that separates right from wrong, so a careful reader gets the rule on the first try. In probe 2 the agent wrote the final `cli.py` once (step 32) with every lever right.

## 3. Lever table (probe 2 reward-details and trajectory)
| Lever | Rule text and location | Tests that carry it | Probe 2 | Step it was got right | What gave it away | Fuzz differing (probe-2 program) |
|---|---|---|---|---|---|---|
| N1 region allowance | quota_limits.cfg:7 "override_allowance is keyed by region; the region of a tenant is its region in tenant_catalog.xml" | hidden_region_allowance_hard n1-a/b w5, coupling | pass | steps 9, 19-20 (read catalog regions); cli.py L292-307 | Names the key (region) and the file to read it from | 0/20 (N1-region-exhaust), 0/149 random |
| N2 unit by version cutover | units_reference.txt:6-7 cutover 1650000000, "whole seconds on an override row whose version has an effective_from ... before the cutover" | hidden_unit_cutover_hard n2-a/b w5, coupling | pass | steps 9, 13-14, 28 (`cut=1650...` computed per row); cli.py L251-255 | Names the per-row test, field and file outright | 0/19 (N2-cutover-edge) |
| N3 window admit + draw_order | effective_windows.xml admit attr; override_precedence.conf:5-6 "... a row refused by either draws neither" | hidden_window_admit_hard n3-a/b w5, coupling | pass | step 17 (admit attr), 29; cli.py L276-307 | A carve-out sentence states the separating case (refused rows use no unit) | 0/20 (N3-admit-exhaust) |
| L7 summed rounding | risk_weight_rounding.txt:2-3 per-term round_half_up | curve docs | pass | step 9; cli.py L327-328 | Worked rule per term | 0/20 |
| L1 trusted controls | override_deltas.json conventions (controls are a parse and count check only) | trace ledger_controls | pass | steps 15-16 | Says outright what controls are for | 0/19 |
| struct (keyshuffle/reindent/space dir) | n/a | n/a | n/a | n/a | n/a | 0/60 |

Fuzz: `OUT/fuzz/fz_r3.py`, an adaptation of kit fz_sp.py/mk_sp_cases.py to the r2 test API. It ran locally (the agent cli is stdlib plus pyarrow), with no Docker. Corpora: 307 (310 generated; 3 skipped because the spec was impossible for the head). 243 had applied rows and 126 had more than one. **0 differing in every kind.** Raw output: `OUT/fuzz/probe2_fuzz.jsonl` and `probe2_fuzz_summary.json`. A first attempt without pyarrow failed every case with ModuleNotFoundError; that was an artefact, and the rerun was clean.

## 4. Trajectory autopsy (52 steps, about 12 min)
3-8 unzip and read the tool (8: `cat -n cli.py`); 9 config files including units_reference.txt and quota_limits.cfg; 13-14 policy_version_map; 15-16 override_deltas conventions; 17 effective_windows.xml; 19-20 tenant_catalog regions; 21-27 xlsx, base params, other files; 28 per-row cutover; 29 window and instant selection; 30-32 writes cli.py (final at 32, all levers right); 33-36 resolve and small edits; 37-43 build.py and a determinism check; 44-46 mutation checks (45: an r-north=1 allowance mutation run with no shown output, which is what fired R9); 47-51 cleanup and AGENTS.md; 52 final message. The agent read each rule straight off the contract and never had to infer anything.

## 5. Agent program
`OUT/agent_program/out/` (7 artifacts including tool.zip) and `OUT/agent_program/src/` (cli.py 515 lines, README.md, schema.json). resolve_policy at cli.py L193-386 is the oracle line for line.

## 6. LEAK_LIBRARY rows (new)
| Leak | Where | Class | Fix |
|---|---|---|---|
| Keyed-scope sentence names key and source file | quota_limits.cfg:7 | names the separating case (keyed scope from another file) | Do not count it as a lever. Keep it only as a coupling feeder. |
| Per-row cutover sentence names the test field | units_reference.txt:7 | names the separating case | Same: amplifier only. |
| "a row refused by either draws neither" | override_precedence.conf:6 | carve-out sentence states the separating case (LV-ENUM class) | Same: feeder only. A rewrite that drops it would leave the rule ambiguous. |

## 7. Proposal for Phase 2: one new H7 re-entry lever (N4); keep N1-N3 unchanged as feeders
Following the master note, I add one H7 branch rather than rewriting N1-N3, which are already proven 0%.

**N4 window timeout pool with re-entry.** New data: attribute `timeout_pool` (whole ms) on every `<window>` in effective_windows.xml; the shipped default is 1200. New rule line override_precedence.conf:7 (the file that already holds admit/draw for this XML):

> `timeout_pool = the applied rows of one window whose timeout delta in milliseconds is above zero share that window's timeout_pool from effective_windows.xml: when their summed delta is at or below the pool, each adds its own delta; otherwise each adds floor(pool × its delta ÷ summed delta). A row whose added delta then falls below 100 adds none, and the whole of the pool is shared again by the same rule across only the rows that held 100 or more.`

There is a one-clause edit to the override_deltas.json conventions: "Every applied row adds its deltas ... ; its timeout delta as set by timeout_pool in override_precedence.conf".

- **Separating case, not named in the text:** pass 2 re-evaluates the fits branch. After the drop, the survivors may sum at or below the pool, so each adds its own delta and the pool is not split proportionally again. If they still exceed the pool, they split the whole pool, not only the freed part. Pass 2 shares can only grow, so there is no third pass and no ambiguity. Nothing is enumerated and there is no worked example (precheck LV-ENUM should stay clean).
- **COUPLING:** the pool is shared across every applied row of the window, including other tenants and other params. So the N1/N3 draw decides who takes part, and N2 decides the ms value fed into the sum. Only K042 rows reach timeout_ms.
- **Shipped answers unchanged (Never 11):** shipped timeout is 2250 under truth and under every mutant (WIN-AUTH applied sum is below 1200). 285/3/2250/51 hold.
- **Prototype:** `OUT/proto/proto_pool.py` (scratch, not shipped). It uses the r2 draw for the applied set and runs the probe-2 program for real on 300 planted corpora. Result `proto_pool_result.json`:

| Reading | Differs from truth |
|---|---|
| probe-2 agent program (no pool) | **78/300 (26%)** |
| no re-entry (dropped share lost) | 111/300 |
| pass 2 always proportional (misses the fits branch) | 33/300 |
| pass 2 shares only the freed amount | 93/300 |
| no drop rule | 111/300 |
| pool shared among K042 rows only | 55/300 |

- **Shrunk corpora (WIN-AUTH, all v100, t-atlas unless noted):**
  - **pool-a** (pass 2 fits), pool 1000. Rows: K003 t-f003 66 ms; K042 231; K042 516; K118 220. Sum 1033 > 1000. Pass 1 gives 63 to the K003 row, which falls below 100 and is dropped. The survivors sum to 967, at or below 1000, so each adds its own delta. Truth 2747. No re-entry gives 2722 and always proportional gives 2771.
  - **pool-b** (pass 2 over), pool 1200. Rows: K003 t-cinder 39; K042 485; K042 392; K118 541. Truth 2741. The probe-2 program gives 2877, and the "K042 only" reading also gives 2877.
- **Hidden cases:** new family `hidden_timeout_pool_hard` with pool-a and pool-b at w5. Plant one over-pool case in hidden-b, so the policy check (w5) also carries it, plus `mutation-pool` (pool edited, w3). The generator plants both pass-2 branches (G12).
- **Predicted alone cost:** 13 of P = 52, which is 25.0% (meets G10 at the floor). One fact wrong, honest: a reader who misses only the fits re-check fails pool-a (5) and, depending on corpus, hidden-b policy, so tests land at about 81-90. A reader who gets it right loses nothing.
- **Why a fresh Opus may miss it:** H7 is the only habit that measured as missed (caldermoor CM-B, 2/314 corpora overall, 9% of P2 edges, test-depth 840adf9). The fits branch in pass 2 is what an implementation that loops only the proportional step skips. I can't claim more than that.
- **Judge:** keep R1-R15. Add R16 at w3: the agent checked the pool re-share on a corpus where a row drops below 100 and showed the result.
- **Fallback if the master rejects N4:** an H3 defined term (for example "the effective window of a row", the window holding the instant under the row's own region allowance) that differs from the per-row `window_id`. This has not been prototyped.

Files Phase 2 would touch: environment/data/effective_windows.xml, override_precedence.conf, override_deltas.json (conventions), WORK gen_data.py, test_body.py, build_tests.py → tests/test_output.py, solution (oracle cli + solve.py self-check), judge rubric R16, _SHIPPED_DATA / reward.toml / TRUTH sha regeneration (Always 6), and WORK docs.
