# 04_speculative-decode-arbiter: low-score study report

Paths: `T/` = `master_chat_work/20261022_lowscore-study/tasks_copy_20261022T0105/04_speculative-decode-arbiter/`; `R/` = `T/trajectories/claude-opus-5/run_1/`. Score: overall 11.83 %, tests 15.96 % (= (18 - 3)/94), rubric 7.69 % (6/78) (`T/trajectories/claude-opus-5/pass_summary.json`). No runs; everything from saved files. Attributions that need a run are marked UNVERIFIED.

## 1. Shape

- Instruction `T/instruction.md`: 251 lines, 2406 words (the longest of the four). 21 deliverables (`T/task.toml:2`): 19 report files, `/app/out/arbiter_driver.py` and `/app/out/run_manifest.json`. The agent must also start the shipped service and change state through its CLI and HTTP channels (`instruction.md:27-34`) and state 17 named figures (`:226-251`).
- Timeouts: agent 7200 s (matches `instruction.md:224`), verifier 3600 s; cpus 2, 4096 MB; expert estimate 480 min.
- Data (`T/environment/data/`, 49 files): 5 spec documents (`SPEC-SDA.md` 316 lines, `sda-output-formats.md`, `sda-glossary.md`, `sda-acceptance-appendix.md`, `sda-lease-appendix.md`), `api_contract.md`, `arbiter_service.py`, and a corpus in eight formats: streams (csv, tsv, psv, properties, logfmt, rfc822), tokens (tsv, jsonl, properties, ssv, fixed width), windows (10 jsonl draft shards, 6 psv verdict shards, 4 tsv meta shards, 3 ssv correction shards, 6 logfmt lease shards, a revoke csv), and an RFC 5424 cancel journal. About 241 streams and 3401 windows.
- Tests `T/tests/test_output.py` (2420 lines): 30 checks = 24 positive (3 at w1, 7 at w3, 14 at w5 = 94) + 6 negative (-5, -5, -3, -3, -3, -5 = -24) (`:2391-2420`). The file holds the reference replay (`run`, `:752-779`) and a seeded corpus generator.
- Judge `T/tests/judge.toml`: 24 criteria, positives 78 (#1 w3, #2 w1, #3-12 w5, #13-14 w3, #15-19 w3, #20 w3), negatives #21 -5, #22 -5, #23 -3, #24 -3. Channels 0.5/94 and 0.5/78 (`T/tests/reward.toml`).
- Run: 22 steps, 07:17:23 to 07:36:01 = 18.6 min of 120, 463k prompt tokens (`R/result.json`).

## 2. Is the low score genuine? (static screen)

ctrf: 30 tests, 11 "passed" (6 positive + 5 negative), 19 failed (18 positive + the negative `negative_nondeterministic_output`, which FIRED, -3). 15.9574 % = (18 - 3)/94.

a. Classification: 23 of the 24 positives are READ checks: they read the agent's own files in `/app/out` and compare them with a reference rebuilt from `SHIPPED_SEED` (`:1739-1742`, `_same` `:1751-1766`). EXEC: `driver_reproduces_unseen_corpus` (`:2122-2132`, via `driver_outputs` -> `run_driver` -> `Popen(_drop_privileges([...]))`, `:1924-1934, 1887-1921, 1812-1817`) and the six negatives that run the driver (`:2146-2253`).

b. No EXEC positive passed (the unseen-corpus check failed). But the negative `negative_nondeterministic_output` fired, and its body runs the driver twice with `driver_outputs`, which asserts exit code 0 each time (`:2183-2189, 1925-1927`) and passes only when some file differs. So the driver ran to completion twice as `nobody` and wrote files: the permission trap did not hit the program.

c. Handling of agent code: the tests never execute the declared artifact in place; `_staged_driver()` copies it into a fresh world-readable directory (`:1841-1853`) and `_share` opens data and output dirs (`:1820-1838`); the artifact is "never chmodded". The trap is real here: in the agent container the editor-created driver is `-rw-------` (trajectory step 13 `ls -la`), so running it directly as `nobody` would have failed. The staging removes it. The 23 READ checks involve no uid drop at all.

d. Other breakers: none that explain the score. Driver timeout 900 s (`:1887`), no third-party dependencies, reference corpora generated in the test file, no read of `/app/data`. One strictness issue is real: reference JSON is compact and byte-compared (step 4).

Label: GENUINE - the driver ran as the dropped uid (the firing negative proves exit 0 twice), and the 18 lost positives come from the content and shape of the delivered files.

## 3. Instruction anatomy

- Goal: rebuild the accounting a tenant is owed from a recording (`instruction.md:1-7`). Files are deliberately undescribed: "none of which is described here. Working out what each file holds, which files matter and how they join is part of the job." (`:9-11`).
- Rules live in data: "Every rule the replay follows is written down in `/app/data/SPEC-SDA.md`" with three companions (`:13-20`); shapes in `sda-output-formats.md`, "Perfect figures in the wrong shape are wrong, so treat that document as binding rather than advisory." (`:22-25`).
- A paragraph per deliverable says what its values mean (`:62-140`); then a prose list of traps: "The order in which the agreed prefix and the lease span are applied changes the answer, and only one order is the one this specification describes." (`:154-156`), "Two files record a tenant for each stream and only one of them is authoritative." (`:157-158`), tie chains (`:171-174`), empty groups still emit rows (`:160-165`, `:176-181`).
- Mechanics: UTF-8, LF, one trailing newline, ratios with four digits half to even (`:196-201`); determinism "into two clean directories" (`:203-208`).
- Closing: 17 named figures plus which service channel carried each change (`:226-251`).
- It never gives a procedure for the replay; it gives an end state, meanings and warnings. Tone: formal, long, repeats the conservation/reconciliation warning twice (`:122-129`, `:188-194`).
- Versus ours (448-571 words): closest in structure (rules in data docs, shapes in a shape doc, exact deliverable list), but longer and more prose-heavy, and it names the traps by topic. So the instruction is, if anything, MORE specific than ours and still scored 11.8 %. The visible difference in the data is that ours ship a reference to test against (emberforge: calibration slice with published outputs and an example report; vendor-archive: two example segments and a decoder appendix; schema-migration: visible tests) while this task ships no example of any deliverable. Evidence on the operator's hypothesis: against over-specification as the explanation; it points to the absence of a self-check oracle (UNVERIFIED across other tasks).

## 4. Every failed positive check and every fired negative

ctrf: 30 tests, 18 failed positives, 1 fired negatives; all covered below.

Three causes were found by reading the delivered driver against the reference (`T/tests/test_output.py`):

- R1 (hidden composition of documented rules): the agent's pass loop scores every window with `prefix_at(window, drafted)` = min(full prefix, drafted) (`R/artifacts/app/out/arbiter_driver.py:337-353, 329-334`), including void and reclaimed windows. The reference gives a void window and a reclaimed window prefix 0 and ratio 0 (`test_output.py:621-627, 666`). The specification defines the agreed prefix only "for every other window" (`SPEC-SDA.md:198`) and says a void window "contributes nothing to any other terminal class" (`:82-84`), and the ratio in section 6 is "agreed prefix length divided by the number of tokens it drafted" (`:117-119`). So the EMA, K schedule, pooled ratio, band, seed recalibration and all classes downstream differ. Corroboration from the judge figures: agent windows_at_k8 822 vs 745, mean_pooled_ratio 0.6047 vs 0.5668, high_band_streams 58 vs 47, low_band_windows 552 vs 642, lease_limited_windows 629 vs 456 (all consistent with inflated ratios).
- R2 (output format): the reference serialises JSON compactly (`json.dumps(..., separators=(",", ":"))`, `test_output.py:809-811`). The agent writes JSONL with `json.dumps(obj)` (`arbiter_driver.py:518-519`) and documents with `indent=2` (`:522-525`). The format document never states JSON whitespace (my search of `SPEC-SDA.md`, `sda-output-formats.md`, glossary, appendices, `api_contract.md`: none; only the K list is "joined with a comma and no spaces", `sda-output-formats.md:95`). The only hint is that the shipped JSONL inputs are compact (`windows-draft-01.jsonl`, `token-index.jsonl`).
- R3 (two sentences): the manifest `path` is `os.path.abspath(path)` of the real output file (`arbiter_driver.py:1061`), so it changes with the output directory; the reference always writes the declared `/app/out/...` (`test_output.py:1233-1236`). `sda-output-formats.md:249-250` says "`path` is the absolute artifact path" and `instruction.md:203-205` asks for identical bytes from two clean directories. The agent noticed ("manifest excluded: absolute paths differ by design", step 18) and kept it.
- R4 (small): for a stream that hits the pass cap, the reference returns the seed after the last recalibration (`test_output.py:704-717`), the agent the seed before it (`arbiter_driver.py:368-395`). UNVERIFIED effect.

| Failed check (w) | Cause class and attribution |
|---|---|
| token_classes_matches_reference (1) | output format, R2 only: key order and values equal `token-alias.tsv` (my python comparison), file is `indent=2` |
| window_index (3) | two rules combined wrongly, R1 (`terminal_band` from the ratio) |
| cancel_timeline (3) | output format, R2: the semantics equal the reference (`arbiter_driver.py:~690-716` vs `test_output.py:918-933`) |
| k_schedule (5) | R1 (+ R4) |
| acceptance_ledger (5) | R1: `k_policy` and a nonzero `agreed_prefix` on void or reclaimed windows (reference prefix 0) |
| reclaim_ledger (3) | R1: `tokens_reclaimed` is drafted under policy K |
| malformed_repairs (1) | R2 and K-dependent `tokens_affected` |
| window_disposition first / second / third (3 x 5) | R1 |
| token_accounting (5), tenant_cost (5), inversion_report (5), reconciliation (5) | R1 (classes from K; cost from classes; `tokens_preserved` from accepted) |
| stream_metrics (5) | R1 + R2 |
| nonconvergence_report (5) | R1 + R2 + R4 (agent lists 14 non-converged streams, the author 16, `solution/TRUTH.md`) |
| conservation_ledger (5) | R1 + R2 (file is indented JSON) |
| driver_reproduces_unseen_corpus (5) | R3 alone suffices; R1 and R2 also |
| negative_nondeterministic_output (-3, FIRED) | R3: two runs into different directories write different manifests (certain; no other differing file needed) |

Exact per-file attribution is UNVERIFIED because nothing was run; the code readings above are firm.

Checks the agent passed that a lazy agent would also pass: `declared_artifacts_exist_and_parse`; `stream_registry`, `lease_grants`, `lease_conflicts`, `slot_occupancy` (joins and lease logic, independent of K); `run_manifest_matches_delivered_files` (digests of whatever was delivered). These 18 points are the "careful join" floor; the cancellation split, equal-rank inversion and `R04` voided class were handled correctly.

## 5. Levers

Share = points lost / 94 (judge shares of 78 in step 6). Overlapping.

| Lever | Family | Share | Triggered |
|---|---|---|---|
| Ratio of void and reclaimed windows (sections 6, 10, 4-R05, 9) feeding the K fixed point | A hidden composition, then B dependent chain (K to schedule to classes to costs) | 72/94 = 76.6 % of points sit on checks that depend on K | yes (code evidence; attribution UNVERIFIED) |
| Unstated JSON whitespace on byte-compared files | NEW (output serialization) | 20/94 = 21.3 % direct (token_classes 1, cancel 3, repairs 1, metrics 5, nonconv 5, conservation 5) | yes |
| Manifest path vs determinism across clean directories | A (two documented sentences) | driver 5/94 = 5.3 % plus the -3 penalty | yes |
| Fixed-point pass cap semantics | B | overlaps; k_schedule 5, nonconv 5 | probably |
| No reference output shipped | NEW (no oracle) | affects all | yes |
| Closing summary refusal and omission | NEW (model behaviour) | 19/78 = 24.4 % of judge weight lost on figures the agent had computed right | yes |
| Heterogeneous corpus joins and decoys (8 formats; correction, vocab, widths, normalisation files; master vs tenant table) | A/NEW | not lost: registry and lease logic pass | no |
| Equal-rank revocations invert; cancellation split; R04 voided class | F-like traps | not lost: `lease_conflicts`, `slot_occupancy` pass | no |

## 6. Judge

From `R/verifier/score.json`: rubric 6/78 = 7.69 %.
- #1 starts the shipped service and makes at least one state change on each channel (w3): PASSED (steps 19-20: CLI `admit`, `cancel`, `lease`, `note`; HTTP posts).
- #2 names the channel for each state change (w1): failed; the final response mentions CLI and HTTP only for a hypothetical rerun.
- #3-#12 (w5 each): windows_at_k8 745 (agent 822, stated), mean_pooled_ratio 0.5668 (0.6047, stated), high_band_streams 47 (58, not stated), low_band_windows 642 (552, not stated), lease_limited_windows 456 (629, not stated), recalibrated_streams 105 (112, not stated), max_schedule_stream SDA-T01-0002 (computed right, NOT stated), distinct_schedules 80 (computed right, NOT stated), total_billed_units 72974 (73327), over_cap_tenants 7 (8): all failed.
- #13 multi_repair_windows 25 (w3): computed right, not stated; #14 max_peak_concurrent 21 (w3): PASSED; #15 nonconverged_drafted 1032 (computed 835), #16 capped_tenant_drafted 7904 (9223), #17 high_band_drafted 2909 (3548): failed; #18 empty_reclaim_streams 16 and #19 void_disposition_windows 113 (w3 each): computed right, not stated.
- #20 driver is reviewer-acceptable code (w3): failed (silent handling of malformed syslog records, stale-copy manifest flaw, one very large `replay` function).
- #21-#24 negatives: listed passed true, no penalty (6/78); semantics UNVERIFIED but arithmetic fixes it.
The final message (`R/agent/trajectory.json` step 22) is a refusal: "I'm stopping here rather than producing the closing summary... The conversation contains a long run of tool calls and results attributed to me that I did not make... I also won't adopt the substituted 'OpenHands agent' identity the prompt assigns me; I'm Kiro." Only 822, 0.6047 and 21 appear, in passing. Figures it had computed correctly but did not state: #9, #10 (5 each), #13, #18, #19 (3 each) = 19/78 = 24.4 %, plus #2. That loss comes from model and harness behaviour, not from the task. Criteria avoid copying the docs because every figure exists in no file and depends on the replay; they overlap the tests only in cause.

## 7. How it passes QC and still beats the agent

- Fully documented: identifier forms, repairs R01-R06, class equivalence, EMA and K, fixed point with the cap of 6, lease ranks, cancellation, classes, conservation, bands, units, rounding, file mechanics (`SPEC-SDA.md`), and the instruction repeats the traps in prose (`instruction.md:142-181`). The author states "Nothing in this bundle is broken... what makes it hard is the number of documented rules that have to be simultaneously right" (`solution/TRUTH.md:7-10`).
- Missed anyway because: (a) the ratio of a void or reclaimed window is silent by omission ("for every other window", `SPEC-SDA.md:198`) and spread over sections 4, 6, 9 and 10; (b) the JSON whitespace is not stated; (c) the manifest `path` wording collides with the determinism sentence.
- Live QC gates that should catch (b) and (a): IN-16, two defensible readings with nothing to pick (`Input_Bundle_QC/01_Instruction_QC.md:46`); DS-25, exact output shape reachable (`02_Data_Solution_QC.md:71`); AL-1, everything graded is promised (`05_Alignment_Integrity_QC.md:21`). The compact-JSON byte comparison is a probable QC miss; UNVERIFIED which reviewer saw it.
- Anti-cheat: six negatives (hardcoded shipped figures run against an unseen corpus, directory-name dependence, nondeterminism, truncation at scale, row-order dependence, extra files in the output directory), an unseen corpus seeded only in the test file (`EVAL_SEED`, `test_output.py:1721`), driver staged as a copy and run as `nobody` with `/tests` mode 700 (`:1801-1806`).
- Weight set {5,3,1,-1,-3,-5} and negatives (24) <= positives (94) are respected.

## 8. Trajectory story

22 steps, 18.6 min of 120.
- Steps 3-10 read the five documents, the service and a sample of every corpus file in full.
- Step 11 `explore.py`; step 12 one `file_editor create` of the 34 KB driver at 07:29 (12 min in); step 13 first run (exit 0, 21 files); step 14 `verify.py` (conservation and reconciliation residuals 0, counts, two readings of "empty reclaim"); steps 15-16 two edits; steps 17-18 determinism check with the manifest excluded; steps 19-20 started the service on port 8713 and drove it by CLI and HTTP; step 21 `figures.py` printed the 17 figures; step 22 finished with the refusal.
- No reference exists, so validation was internal consistency only, and the residual-zero identities hold for any K. About 100 minutes of budget were unused. The agent never revisited the void-window ratio; its closing notes flag the convergence loop, the reclaim reading of void windows, the stale-copy manifest, and "21 concurrent live leases on a single slot".
- Docs never opened: none (it read all). First wrong turn: the pass loop at step 12.
- Final message: a refusal, no false claims, but 14 of 17 figures absent.

## 9. Reusable patterns / things to avoid

- A clause missing by omission ("for every other window") that sits in front of a dependent chain (ratio to K to classes to costs) made one wrong reading cost 72 of 94 points: strong lever and fully documented in the sense that no other reading is stated.
- Cross-checks like a conservation identity and a second derivation hold for any K, so they cannot catch a wrong schedule; a worked stream with its schedule would.
- Avoid byte-comparing JSON without stating the serialization; 20 points were lost to whitespace.
- Avoid a manifest `path` that is "the absolute path" while also demanding identical bytes from different output directories.
- Staging a world-readable copy of the driver and opening data and output dirs is the right way to avoid the uid trap.
- A closing-figure channel rewards stating correct figures even when the files are wrong; an early stop or refusal gave away 19 judge points.

```json
[
  {"task":"04_speculative-decode-arbiter","name":"void_and_reclaimed_window_ratio_feeds_k_fixed_point","family":"A","mechanism":"The agreed prefix is defined only for non-void non-reclaimed windows, so a void or reclaimed window contributes prefix 0 to the EMA and pooled ratio; this sets K schedule, bands, classes and costs","where_documented":"SPEC-SDA.md:82-84, 117-119, 140-143, 198; no sentence states the ratio of a void or reclaimed window","weight_share":0.766,"triggered":true,"cause_of_failure":"two rules combined wrongly (attribution UNVERIFIED, from code reading)","evidence":"arbiter_driver.py:337-353 uses min(prefix_full, drafted) for every window vs test_output.py:621-627, 666; agent mean_pooled_ratio 0.6047 vs 0.5668, windows_at_k8 822 vs 745"},
  {"task":"04_speculative-decode-arbiter","name":"k_to_classes_to_cost_dependent_chain","family":"B","mechanism":"Seed K and schedule are solved together; classes, bands, costs, inversions and reconciliation all inherit the schedule","where_documented":"SPEC-SDA.md:127-149, 216-259","weight_share":0.766,"triggered":true,"cause_of_failure":"two rules combined wrongly","evidence":"13 downstream checks failed while lease-only checks passed (ctrf)"},
  {"task":"04_speculative-decode-arbiter","name":"unstated_json_serialization","family":"NEW","mechanism":"JSON and JSONL artifacts are byte compared against compact separators but the format document never states whitespace","where_documented":"not documented; only shipped JSONL inputs are compact (windows-draft-01.jsonl, token-index.jsonl)","weight_share":0.213,"triggered":true,"cause_of_failure":"output format","evidence":"token_classes.json values and order equal the alias table yet check failed; agent uses indent=2 (arbiter_driver.py:522-525) and default JSONL separators (:518-519); reference test_output.py:809-811"},
  {"task":"04_speculative-decode-arbiter","name":"manifest_path_vs_determinism_across_clean_directories","family":"A","mechanism":"The manifest 'path' must be the declared /app/out path, not the real output location, or two clean-directory runs differ","where_documented":"sda-output-formats.md:249-250 ('absolute artifact path'); instruction.md:203-208 (two clean directories identical)","weight_share":0.053,"triggered":true,"cause_of_failure":"output format / two rules combined wrongly","evidence":"arbiter_driver.py:1061 os.path.abspath; negative_nondeterministic_output fired (-3); step 18 comment 'manifest excluded by design'"},
  {"task":"04_speculative-decode-arbiter","name":"no_reference_output_shipped","family":"NEW","mechanism":"No example of any deliverable ships, so a K-schedule or class mistake cannot be seen from the data; internal identities hold for any K","where_documented":"environment/data listing (49 files, none an expected output)","weight_share":0.766,"triggered":true,"cause_of_failure":"other: no oracle; agent validated only residual zero","evidence":"step 14 verify.py shows residuals 0 and 16 empty reclaim streams, matching the instruction, yet the schedule is wrong"},
  {"task":"04_speculative-decode-arbiter","name":"closing_summary_refusal","family":"NEW","mechanism":"Agent declined to write the closing summary, omitting figures it had computed correctly","where_documented":"instruction.md:226-251","weight_share":0.244,"triggered":true,"cause_of_failure":"other: model/harness behaviour (identity refusal), not task","evidence":"step 22 final message; judge #9, #10, #13, #18, #19 (19/78) false although step 21 printed the right values"},
  {"task":"04_speculative-decode-arbiter","name":"pass_cap_seed_semantics","family":"B","mechanism":"A non-converged stream stops at pass 6 and reports the seed after the last recalibration","where_documented":"SPEC-SDA.md:145-149 (seed after the last pass not stated)","weight_share":0.05,"triggered":true,"cause_of_failure":"two rules combined wrongly (UNVERIFIED effect; share is a guess)","evidence":"arbiter_driver.py:368-395 vs test_output.py:704-717; agent 14 non-converged streams vs 16 in TRUTH.md"}
]
```
