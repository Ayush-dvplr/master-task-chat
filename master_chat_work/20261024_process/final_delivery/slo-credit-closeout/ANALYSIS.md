# f272f70 slo-credit-closeout (masked 80202e15-2d10-5eef-b823-ce74567dee0f): why it passed QC and beat Opus

Scratch: `/tmp/fd-slo-credit-closeout-20261024T1156` (S). Delivered folder: D. Run: `D/trajectories/claude-opus-5/run_1` (RUN). Docker was not used: `docker ps` showed containers I did not start (`fdsent-verifier:d930be0 ... fdsent-rg-agent`, later `fdsent-rg-oracle`). All grading ran on host Python 3.12.15 in `S/venv`, with the tests/Dockerfile pins (regrade.txt §0).

## Verdict
**PARTLY.** The 2.38 on tests is a real failure by Opus, but most of it is billed through amplification and about half rests on gaps in the spec. Opus made five value mistakes, on about 5,600 of 21,021 records. Every concept, trap slice and decoy check compares whole records, or the whole population, against a digest. So those five mistakes cost 205 of 210 test points, and fixing them one at a time is super-additive: B alone returns +5, while A+B+C+D returns 195 (regrade.txt §5, §7). Split by cause:
- **GENUINE, 105 points.** These are rules the documents settle: B, an internal flag on an alias id (45), and D, a lower-case wave id (60).
- **Spec gaps, 100 points.** A, fx_rate on MET records, which nothing in the spec conditions (55, AMBIGUITY). C, which calendar row wins after an account merge, which no document states (35, HIDDEN RULE). E, quarantine "at the window start" (10, AMBIGUITY).
- **Judge, 6 points.** Two genuine conduct losses: a false harness claim (R6) and swallowed exceptions (R9).

The recorded run itself is not an artefact: re-grading the agent's outputs reproduces 5/210 = 2.38% exactly. **The delivered bundle is defective, though.** Masking rewrote the slug inside the SHA-256-pinned generator sources, so the hidden tier can no longer run. On the delivered bundle the oracle scores 197/210 = 93.81%, not 100% (regrade.txt §1).

## Phase 1: identity, provenance, integrity
1. **Mapping.** `Final_Delivery_Internal/mask_map.json` maps slug slo-credit-closeout to 80202e15-2d10-5eef-b823-ce74567dee0f. Its source is the Poonam_Chourey QL folder under Perfect_for_Delivery. That folder is not on disk; only the QC report is.
   - Author: `task.toml:9` `authors = [{ name = "Bhavik Jain", email = "bhavik.jain86@ethara.ai" }]`.
   - Category: `task.toml:12` "Software Engineering".
   - The team QC report gives the bundle's path as `Pass@1_New/Poonam_Chourey/Bhavik Jain/slo-credit-closeout` (QC report header). That path does not exist either.
   - **Older copies:** I searched by slug (find, maxdepth 6, across Terminal Bench and /) and found none. No `diff -rq` was possible.
   - **Masking changes:** 6 files rewritten with 33 replacements. tests/test_output.py had 5 slug replacements, all inside embedded generator docstrings (:59, :206, :546, :4115, :4458). TRUTH.md had 3, plus the provenance fields. task.toml had 1. config.json, result.json and trajectory_usage.json were also rewritten. On top of that: 7 host-path rewrites, binary_leaks [], and three synthesized files (trajectory_usage.json, reward-details.json, reward_raw.json).
   - **Why it matters:** `_generator_ok()` (test_output.py:5842-5846) hashes GENERATOR_SOURCES against `GENERATOR_SHA256`.
     - Delivered file: `pin 8b5cf995a11eba15 masked 5b551b5ff3cb7160`.
     - After putting the slug back: `unmasked 8b5cf995a11eba15 True`.
     - Consequence: `_regenerate_locked` (:5870-5900) writes `eval.FAILED`. The three eval tests (13 points) can never pass, and the four negatives can never fire.
2. **Masking residue.**
   - Text grep for slug, Bhavik, Poonam, `/Users/`, `.kiro-staged` and `macbookpro`: the only hit is `task.toml:9` (author, kept by design).
   - Binaries (unzipped xlsx/docx, pdf/sqlite/parquet strings): no hits. docx `dc:creator` and PDF `/Author` both read "Corvid Cloud Platform - Service Reliability Office".
   - Soft residue in tests/ (agent cannot see it): `test_output.py:1` "Verifier for the SLO credit closeout task.", `:35` `/tmp/slocc-verifier-cache`, `:5087` "World model for the SLO credit closeout corpus". These are descriptive names; the slug string itself does not appear.
3. **Leaks in environment/.**
   - The grep for TRAP, LEVER, grader, hidden test, answer key, expected and oracle hits only two things. One is PDF metadata `/Trapped /False` (7 PDFs). The other is the by-design sentence "The audit control register lists the expected record count and control sum of every block of every file" (source_register.md:80).
   - environment/ holds only the Dockerfile and data/. No figures from solution/ or tests/ appear in it.

## Phase 2: kit verdict
Precheck (kit 71a653b2) on a copy without trajectories/; full output in `precheck.txt`.

| fails | minors | warns | extra-check hits | tests | criteria |
|---|---|---|---|---|---|
| 0 | 0 | 1 (`WARN [A3] 48 checks; cap is 35 (warn)`); X1 informational (32 binaries) | `FINDING: tests 48 > 35` (`PRECHECK: 2 finding(s)`, exit 1) | 48 | 9 |

Team QC report, finding by finding (Poonam_Chourey QC report, verdict line 3 "WARN 0/0/5", all accepted at lines 44-46):

| team finding | report line | accepted by tasker | live kit today |
|---|---|---|---|
| TS-20: hidden tier is 13/210 = 6.2%; oracle outputs plus a broken transform keep 197/210 | :36 | yes | not emitted (manual gate check) |
| X1: 32 binaries, 7 Latin-1 CSVs | :39 | yes | informational, same |
| A3/TS-23: 48 checks > 35 | :40 | yes | **agrees** (WARN A3) |
| JD-16: R4 no-arg default is judged, not tested | :41 | yes | not emitted (manual) |
| AL-8: expert 2400 min against a 4 h agent timeout | :42 | yes | not emitted (manual) |
| DS-22: TRUTH sha/judge counts (fixed) | :50-52 | fixed | n/a |

Where the delivered task breaks OUR rules:

| # | our rule (quoted) | file:line | this task |
|---|---|---|---|
| 1 | "Caps: at most 35 tests ... The PL accepts zero findings, warns included (dec 101): a WARN is a finding to fix, not to record." | _COMMON_RULES_v3.md:56; KNOWLEDGE.md:38 | 48 tests; 5 warns accepted |
| 2 | "Gate for real model runs ...: tests < 100, rubric < 100, overall < 70, on 2 runs before PL." | _COMMON_RULES_v3.md:55 | 1 run only (pass_summary.json); the scores themselves pass the gate (2.38 / 66.67 / 34.52) |
| 3 | "G3 shares: isolated <= 30%, whole-document on hidden inputs >= 50%, shipped-only <= 5%." | P2_build_v3.md:82 | hidden 13/210 = 6.2%; shipped-only 197/210 = 93.8% |
| 4 | "isolated rule checks on supplied correct upstream inputs, no whole-set asserts." | P2_build_v3.md:81 | 8 concept checks digest the whole population (test_output.py:5747-5770) |
| 5 | "no two checks may read the same observable with the same logic (TS-26)." | P2_build_v3.md:86; COMMON:43 | one wrong record is billed in a concept, a slice and a decoy check (A touches 33 visible tests) |
| 6 | "Leave a rule of engagement unstated. Every rule about HOW the program must work or what it must write (... precedence, ...) is stated in a visible file" | _COMMON_RULES_v3.md:25 | C (calendar row tie after a merge), A (when fx_rate is null) |
| 7 | "Do not make it hard by ... hidden or ambiguous rules." | P2_build_v3.md:43 | A, C, E (100 points) |
| 8 | "test.sh: `chmod 700 /logs/verifier` in every template; QC H5 warns on anything else (755 now warns)." | KNOWLEDGE.md:76 | tests/test.sh uses `chmod 755` (precheck did not flag it) |
| 9 | "State whole-document grading (G5)" | P2_build_v3.md:98 | instruction.md never says how outputs are graded |

## Phase 3: scores, re-graded
1. **Recompute.** reward.toml weights are test_output 1/420 and judge 1/36. So the combined score is 5/420 + 12/36 = 0.3452. That matches `test-stdout.txt` ("reward: 0.3452"), `reward.json` 34.52 and `pass_summary.json` (tests 2.38, rubric 66.67, combined 34.52).
   - **The 0.3869 mismatch.** result.json `verifier_result` and reward_raw.json say 0.3869, and reward-details.json is synthesized from result.json (`"source_files":["result.json"]`). 0.3869 equals 0.5·5/210 + 0.5·0.75 = 0.386905, which means the same 5 test points with rubric **75.00**.
   - The earlier peer mining of this run recorded exactly that: "overall 38.69 / tests 2.38 / rubric 75.00" with a 10-criterion judge (peer_levers/G3/A_slo-credit-closeout.md:3, B:28). The delivered score.json is a re-judge with today's 9 criteria (12/18). result.json was never updated, so the synthesized details inherit the stale value.
2. **Loss table:** `loss_table.md`, covering all 48 tests and 9 criteria. Tests kept 5/210. No negative fired (ctrf status "fail" on a negative means its condition was false). Judge 15−3 = 12/18.
3. **Re-grade** (`regrade.txt`):
   - Host driver: a copy of test_output.py with only paths and setpriv patched; the judge is never called.
   - Agent outputs: 5/210 = 2.38%, passing shape, encoding and eval_held_close_exact. **This matches** ctrf (3/48, 2.381).
   - Oracle (solve.py, 60.13 s visible): **210/210 with the pin restored**. On the delivered masked file it gets 197/210.
   - nop: 0/210, and no negative fires.
   - Host caveats: no uid 65534 isolation. negative_reads_training_corpus_at_runtime cannot fire on macOS, because its poisoned run must create /app/data.

## Phase 4: where Opus lost
**Timeline** (trajectory.json, 137 steps; result.json):
- Agent ran 18:43:40 to 19:47:02, i.e. 63 min of the 240 min budget and 137 of MAX_ITERATIONS 350.
- Tokens: 27.70 M input (27.35 M cached), 189 k output, $20.62.
- Steps 3-7: listing, then `head -200 source_register.md` (step 5; no observation is stored) and a heading grep (step 7).
- Steps 8-14: dumped all 7 docx files (charter first).
- Steps 15-39: inspected every format family (csv/tsv 15, json 16, jsonl 17, xml 18, the control-register PDF 19, xlsx 20, sqlite 21-22, logs 23-25, html 26-27, md, toml, yaml, fixed-width 28-34, PDFs 35-36, ics/mbox 37, ini 38).
- **First output** at step 40 (18:51:14, about 7.5 min in): transform.py.
- Steps 46-50: control harness check.py. Steps 58-70: split into part files.
- Steps 71-98: first full run (28.5 s), then about 30 probes.
- **Self-tests:**
  - HELD simulation (99, 131);
  - --prior and determinism (101-103);
  - no-arg run (123);
  - simulated next month with the period edited and --prior (134-135).
- **Never touched** /tests, /logs/verifier, solution/ or /logs/agent, and no curl/wget/pip install. I grepped every tool call and found 0 hits.

**Losses.** Class per COMMON taxonomy. Points use sequential patch attribution (A→B→C→D→E), test points out of 210.

| mistake | what the agent did (step / code) | right answer and the line that settles it | tests touched | points | class |
|---|---|---|---|---|---|
| A: fx_rate on MET records | emits a rate whenever a filing hour exists (agent transform.py:2930 area, :2965); written step 40 onward | oracle sets fx only on converted credits (solve.py:2150-2160; MET 10441 / UNCLAIMED 4809 all null). instruction.md:13 says only "`fx_rate` (string, 6 decimals, or null)"; credit_operations_manual says credits are converted at the fixing of the claim-filing hour. **No line says null when there is no credit.** | 33 visible + 2 eval; sole cause of 11 | 55 (alone on the oracle: −165/197) | AMBIGUITY |
| B: internal_flag not alias-resolved | `self.internal.add(norm_ident(account_id))` raw (transform.py:1241-1248, :1272) | charter para 4 "internal_flag is the system of record for internal accounts" + para 6 "References are followed until they reach an account that is not mapped further"; 41 subs (37 published that should be excluded INTERNAL_ACCOUNT) | 19 visible + 2 eval | 45 (alone −95) | GENUINE |
| C: calendar site after merge | `account_site.setdefault(norm_ident(id), site)` keeps the surviving account's own row (transform.py:1734-1739) | oracle keeps the merged-away account's row (solve.py:1473-1477, dict overwrite). Example: ACC-03091 SE-AB and ACC-06052 IE-D, merged by GD-04437. **No document states which row wins.** Effects: SUB-002542 claim lost (−332 cents and qtd cascade on 6 records); SUB-012475 spurious claim | 12 visible | 35 (M3 alone −60, M4 alone −30) | HIDDEN RULE |
| D: lower-case wave id | `wave = clean_text(rget(r,"wave"))`, case-sensitive (transform.py:2491, :2517). So the ROLLBACK `wave=wv-0185` (deploy_events.log:2562) never matches `WV-0185`, schema stays v2 and 429s are not subtracted from 5xx: 2 extra bad windows (SUB-011237, SUB-012006) | source_register.md:66 "Exports also write them in lower case ... these are the same identifier"; telemetry_collection_standard para 6 (schema by highest-seq event) | 11 visible | 60 (alone −55) | GENUINE |
| E: quarantine at bucket start | `quarantined(host, self.window_start(win))` (transform.py:2580-2598). The 14:30 bucket start falls inside QR-01267, so SV-00022999 (14:34:34) is dropped (hidden month, SUB-025753) | telemetry std para 4 "not under an ACTIVE quarantine at the window start". The oracle uses the record's own `window_start` (solve.py:1752-1766). The phrase reads both ways | 2 eval | 10 | AMBIGUITY |
| R6: false claim | final message (step 137) claims every file showed bad=0; check.py ran at steps 50 and 114 ("FAIL: cdn_attestations.xlsx ... bad=101") and never again after the fix at 127-129 | score.json R6 justification, verified | judge | −3 | CONDUCT |
| R9: swallowed exceptions | `except Exception: pass` at transform.py:961-962 and :971-972, `return` at :2006-2007, `continue` at :2024-2025 | judge.toml:115-126; the oracle has 2 handled broad excepts (solve.py:1032, :2274) | judge | 3 | CONDUCT |

- **No JUDGE ERROR and no ARTEFACT** in the recorded run. **AMPLIFICATION is the mechanism behind every row,** not a separate cause: 5 value mistakes produce 44 failed positive tests.
- **Patch proof** (regrade.txt §5-8; each patch is the minimal hunk only):

  | step | visible score (of 197) | full score (of 210) |
  |---|---|---|
  | agent as recorded | 2 | 5 |
  | +A | 57 | |
  | +B | 102 | |
  | +C | 137 | 140 |
  | +D | **197/197** | 200 |

  After +D, the only September difference is SUB-025753, which is mistake E.
- **Distinct mistakes:** 7 in all, 5 computation and 2 conduct.

**Did it read the saving line?**
- **A:** the manual's fixing sentence was read at steps 8-14. There is no line that would have saved it.
- **B:** charter para 4 was read at steps 8 and 12. The agent read it, then applied the flag to raw ids.
- **C:** the calendar table was read at steps 9, 12 and 14 (the observation shows `acc-00001|NO-03`, rows=9601). No tie rule exists to read.
- **D:** step 5 has no stored observation and the "same identifier" text appears in no step, so reading source_register.md:66 is **UNVERIFIED**. The agent applied norm_ident everywhere else, so it knew the rule. It never saw a lower-case wave: step 25's grep showed only `wave=WV-0101`, and `wave=wv-` occurs in no observation.
- **E:** telemetry std para 4 was read at steps 9 and 14.

## Phase 5: design anatomy
1. **Instruction.** 22 lines (15 non-empty), 633 words, 5454 B.
   - Structure: line 1 is context (100 files; "start with source_register.md and governance_charter.docx"; "only the sections the charter designates are authoritative"). Lines 3-9 are the program contract (`transform.py <DATA_DIR> <OUT_DIR> [--prior]`, deterministic, ≤25 min, no-arg defaults at line 9). Lines 11-18 are the exact output schema (32 fields; the bad_window_digest definition). Line 20 covers status_counts and HELD outputs. Line 22 covers time and no online lookup.
   - Every business rule is stated **by reference** to the register, charter and policies. None is stated in the instruction.
   - Deliberately left out: any trap hint, how outputs are graded, and the next-month tier.
2. **Data.** 100 files, 55 MB, 19 extensions (csv14 docx7 html3 ics1 ini3 json6 jsonl8 log5 mbox1 md3 parquet6 pdf7 sqlite4 toml3 tsv8 txt3 xlsx8 xml6 yaml4; TRUTH.md inventory). That is 685,728 records, 7 Latin-1 CSVs (QC :39), and 15 decoys with plausible names (`*_replay`, `*_compacted`, `*_draft`, `*_legacy`, `*_unofficial`, `*_mirror`, `*_proposed`, `region_groups_2025`).
   - Traps sit in ordinary columns. Examples: the alias id in the internal flag (account_snapshot_legacy.sqlite, a decoy that is authoritative for one column), the lower-case wave in deploy_events.log:2562, a drifted header mid-file (lb_errors_south.csv:4503), and merged accounts in the charter decisions table.
   - Next period: September is regenerated by the embedded generator (EVAL_SEED 20261147), plus a held variant with support_tickets.jsonl removed.
3. **Tests.** 48 checks: 44 positive worth 210 (shape 1, encoding 1, 8 concepts × 5, 15 decoys × 5, 16 slices × 5, 2 eval × 5, held × 3) and 4 negatives (−5, −5, −5, −3).
   - Tier split: visible 197 (93.8%), hidden 13.
   - All value checks are SHA-256 digest comparisons. A concept check digests the whole population (:5747-5770). A slice digests whole 32-field records (:5811).
   - Fan-out: one concept spans up to 35 tests (mistake A). The negatives are anti-hardcode (more than half the records replayed), filename dependence (moved copy), corpus read at runtime (poisoned /app/data) and nondeterminism.
   - Hidden runs as uid 65534 with the generator deleted first. RUN_TIMEOUT 1500 s, which is 25× the oracle's 60 s. No failure messages.
4. **Judge.** 9 criteria: positive 18 (R1-R5 and R9 at 3 each), negative −13 (R6 −3, R7 −5, R8 −5).
   - Targets: R1-R5 read the trajectory, R6 reads the final answer, R7/R8 conduct, R9 the code.
   - The oracle meets R9 (two handled excepts). R1-R6 are process criteria that a competent run meets; this run met 5 of them.
5. **Solution.** solve.py, 102,907 B / 2,300 lines: a single-pass `Repo` that reads the catalog, then concepts in order, with --prior carry for quarter caps. Visible run 60.13 s on host. TRUTH.md is 57,726 B.
6. **Robustness.** Each of A, B, C and D is one yes/no decision, and any one of them left wrong costs 30-165 of the 197 visible points (single-injection costs). A run that makes all four decisions correct scores about 197-210; one that misses any of them lands near 2-67%.
   - A second Opus run very likely misses at least one of A and C, because the spec does not settle them. So tests would probably land between 2 and 35, but ±30 is possible if fx_rate happens to be nulled.
   - Rubric: R6 and R9 are single decisions worth 16.7 rubric points each, so the rubric could land anywhere from 50 to 100.
   - Estimated combined spread: 30 to 60 (UNVERIFIED; only 1 run exists).

## Phase 6: what we take from it

| design choice | evidence (file:line, points) | kit check | our v3 templates | verdict |
|---|---|---|---|---|
| Reusable program re-run on a regenerated next month with --prior, as uid 65534 | test_output.py:5828-6060; 13 pts; mistake E only shows here | TS-12, TS-9 | required, P2_build_v3.md:80 | adopt |
| Concept projection = one concept's fields over every record, digest-compared | :5747-5770; A alone −165/197 | TS-26/TS-13 risky (peer B §8) | visible whole-set forbidden, P2_build_v3.md:81 | adapt: run it on hidden inputs, where it counts as whole-document (P2:82) |
| Trap and decoy slices comparing whole 32-field records | :5811; A is the sole cause of 11 slices (55 pts) | TS-26 | P2_build_v3.md:86, COMMON:43 | adapt: a slice digests only its own trap's fields |
| 48 checks | precheck "WARN [A3] 48 checks" | TS-23 warn | forbidden, COMMON:56 | avoid |
| 93.8% of weight on shipped data | QC report :36 | TS-20 warn | forbidden, P2_build_v3.md:82 | avoid |
| Rules by reference into a 100-file, 19-format corpus with per-section authority and 15 decoys | instruction.md:1; B 45 and D 60 GENUINE | IN-15 ok | allowed, P2_build_v3.md:41-42 | adopt |
| A general identifier-variant rule stated once, exercised in a low-traffic join (event-log wave) | source_register.md:66, deploy_events.log:2562; D 60 | IN-15, IN-16 | allowed, COMMON:25 | adopt |
| A nullable field with no stated null condition | instruction.md:13 fx_rate; A 55 | IN-15/IN-16 (team QC missed it) | forbidden, COMMON:25 | avoid |
| An unstated tie (merged account owns two calendar rows) | solve.py:1473-1477; C 35 | IN-15 | forbidden, COMMON:25, P2:43 | avoid |
| Shipped audit control register as an honest self-check | source_register.md:80; agent's 100 sources = oracle's | TS-19 | allowed | adopt |
| Exact HELD gate (small weight) | :6311; 3 pts, passed | TS-20 | allowed | adopt |
| Judge R6 false-claim negative and R9 named-shape code quality | score.json R6 −3 and R9 0; judge.toml:76-87, :115-126 | JD-11, JD-18 | P2_build_v3.md:91 J3/J4 | adopt (make R6 specific) |
| No-arg default judged, not tested | judge.toml:50-61 (R4) | JD-16 warn | P2:85 G4 | avoid |
| Full output schema in the instruction (format worth 2 pts) | instruction.md:11-18 | TS-20 | P2_build_v3.md:96 | adopt |
| SHA-pinned generator whose text contains the slug | test_output.py:5842; masked oracle 197/210 | none (DS-22-like) | not covered | avoid |
| `chmod 755 /logs/verifier` | tests/test.sh | H5 | KNOWLEDGE.md:76 | avoid |

**Template and playbook edits** (not made; at most 6):
1. `knowledge/LEVER_RULES_v1.md:43` still says "Caps: 70 tests and 70 criteria (QC WARN above 35 is recorded, not a failure)". Replace it with the 35/35 zero-warn rule of COMMON v3:56 and KNOWLEDGE.md:38. Rows: 48 checks, A3.
2. `prompts/templates/P2_build_v3.md:81`: add "A concept projection (one concept's fields across every output record, digest-compared) run on hidden reseeded inputs counts as a whole-document check under G3; never run it on shipped data alone." Row: concept projection.
3. `P2_build_v3.md:86`: add "A record slice digests only the fields of its own trap; whole-record slices bill one bug many times (TS-26)." Row: whole-record slices (A billed in 33 tests).
4. `_COMMON_RULES_v3.md:25` (Never 6): add two audit lines. Every nullable output field names its null condition. Every entity-keyed table that a merge or alias can collapse states which row wins. Rows: A (55) and C (35).
5. `P2_build_v3.md:41`: add a lever pattern. State a general normalisation rule once (identifier variants, case, blanks) and exercise it in a rarely-joined field of an event log, never in the main key. Row: D (60, GENUINE).
6. `P2_build_v3.md:113` (Phase 8 gates): add two gates. Keep the slug, author and task-specific strings out of any SHA-pinned text in tests/. Re-run the oracle on the masked delivery copy and require 100%. Row: masked oracle 197/210.

**Earlier peer mining** (peer_levers/G3/A and B, on the earlier 10-criterion judging):
- **Agree:**
  - the run is not a harness artefact (A §1-2);
  - the visible failures are value failures, amplified by whole-population digests (A §4, B §1);
  - R6/R7 false claim and code quality are genuine (A §6);
  - the concept-plus-slice-plus-decoy stack is TS-26 RISKY (B §8).
- **Disagree:**
  - B §3 calls the agent's sheet reordering of cdn_attestations.xlsx a PROVEN "control-fit trap" defect. It is not a loss: the agent's 100 data_quality sources equal the oracle's, and the patched transform with the reorder kept scores 197/197 (regrade.txt §7).
  - A §3 and B §6 say the specific misses cannot be named. They can: the five mistakes are named and patch-proved above.
  - A §1 says there are "No ... timeout anywhere". That is true for the run, but the delivered masked bundle's hidden tier now always fails.
  - Their "rubric 75.00 / overall 38.69" is the stale result.json value. The delivered score is 66.67 / 34.52.
