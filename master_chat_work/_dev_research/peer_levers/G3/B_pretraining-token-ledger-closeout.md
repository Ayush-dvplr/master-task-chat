# B: pretraining-token-ledger-closeout (Phase A verdict GENUINE, amplified by exact-hash grading)

Run: overall 33.34, tests 0.00, rubric 66.67 (40/60).
- Format was verified correct (agent step 180; shape check passed), so the zero is made of value failures, not a format gate.
- Per-rule misses CANNOT be proven by diff:
  - the tests store only SHA-256 digests;
  - the oracle needs pypdf, openpyxl and docx plus the Tallyline simulator, and cannot run locally (`ModuleNotFoundError: pypdf`);
  - so this file reports the mechanism and marks the specific misses INFERRED.

## 1. Inventory
- Domain: LLM pretraining compute and token-budget ledger close-out (loader logs from 5 pods, tokenizer cutovers, near-dup and decontamination, licensing and opt-out, budget tranches, epoch caps).
- Archetype, three parts:
  - drive a stateful HTTP posting service (Tallyline, shipped as `service.zip`) plus a CLI for quarantine credits, so the posting stream is the deliverable;
  - write 7 close-out JSON outputs;
  - provide a re-runnable package `scenario_mode.json` (format `tallyline-runner/1`) that the verifier runs on the next stage.
- Agent sees 100 files, 43 MB in total:
  - loader logs for pods a-e × 5 windows in csv/tsv/jsonl/xlsx;
  - 15 decoys: draft, replica, restated, v2_proposed, preview, legacy v1 spec, rev5 draft, decon r8, resend;
  - `source_register.md` (5,164 lines) and `tallyline_service_contract.md` (5,043 lines; Appendix B is a release-block table of about 5,000 rows listed out of order, followed by footnotes);
  - docx/pdf procedures.
  - 650,621 records in total (TRUTH inventory).
- instruction.md: 432 words, 19 lines.
- Tests: 39 checks: 35 positive worth 125 and 4 negative worth -18 (TRUTH:193).
  - 6 whole-file exact digests: report 5, final_state 5, postings 5, transcript 3, exceptions 5, statements 5.
  - 1 shape gate (1).
  - 16 trap-family slices × 3 and 5 decoy-group slices × 3.
  - 6 hidden-tier checks (5,5,5,5,5,3).
- Isolation:
  - Slices drop only `ledger_seq` and `remaining_after_tokens` and hash the agent's postings and exceptions for the refs named in the slice (test_output.py:172-186). They are all-or-nothing over about 35-268 trap records each.
  - Whole-file checks are not isolated at all.
- Hidden or reseeded inputs: YES. Stage S4 is regenerated from EVAL_SEED with an embedded generator (:218-233). The agent's package runs 4 times as uid 65534 against a fresh service (A and B identical, C relocated, D with a poisoned /app/data). The opening is the agent's own S3 `final_state.json` (:314-419).
- Judge: 15 criteria, `mode = "individual"`, 30 positive and -19 negative (TRUTH:193; rewardkit normalises to 1/60).
- Reward: 0.5 tests + 0.5 judge.

## 2. Rule map
Every graded value sits in the register, contract or procedures (TRUTH.md:5: "Nothing is redacted: every rule is written in the shipped register, contract and procedures"). Representative graded rules, with the shipped wording taken from the generator's docs module in solve.py:

| rule | where stated | form | trap explained? | data separates? |
|---|---|---|---|---|
| Authority is per table, not per file | register s2: "A file whose own header ... declares it a view, draft, replica, preview, proposal, rerun or informational export is never a source of values, except for the tables this section names."; plus per-table carve-outs, e.g. the preview export's accounts table "is the only crosswalk ... and is binding" | default + named exceptions spread across sections | the default is explained; each exception sits in a different paragraph from the file it governs | yes (decoy rows "agree on almost every key", TRUTH item 22) |
| Duplicate loader rows | procedure: keep the live branch after rollback / earliest crawl date; the operator runbook (marked not reviewed) suggests "keep the first one logged" while its hot-swap table "is binding" | conflicting sentence in a low-authority file, with authority split *inside* that file | no | yes |
| Tokenizer switch | tokenization standard: "The planned_switch_step of the migration note is a plan, not a cutover" (cutover = COMPLETE job) | one sentence in a different document from the data | names the wrong reading but not where the right instant lives | yes |
| Epoch caps | budget procedure: "The epoch, pass or similar fields of the loaders are logger bookkeeping and are not counters"; caps count posted exposures per chunk across stages | negation sentence plus a definition | partly | yes, and it carries into S4 |
| Stream order and batching | contract s3: per step, tranches (Appendix B block order) → requeues → quarantine credits (doc_id, account) → exposures (micro, pod, ref); batches of 500; "a quarantine credit ends the current batch" | stacked constraints in one section, with the block order in a 5,000-row table | no | yes |
| Rounding | half-even once per exposure (TRUTH item 12) | one sentence | no | yes |
| Footnotes override table cells | "Footnote N: row R of <caption>, column C reads V; this note overrides the table." Footnotes sit at the end of the contract and inside docx/pdf | override hidden in a footnote far from its table | no | yes |
| Time normalisation | pod-e UNIX vs GPS seconds at logger restarts, repeated DST hour = first occurrence, NODE_FAIL in America/Chicago | spread across procedures | no | yes |
| Stage membership | register s1: "a record belongs to the stage by its step and never by the window named in its file name: a logger flushes late" | one sentence plus a rationale | yes | yes |
| Output format | contract s5 exact json.dumps, key orders; instruction.md:13 "An output is accepted only as a whole" | plain | yes | n/a (passed) |
| Determinism | contract s5: "Running it twice on the same inputs must produce byte-identical outputs" | plain | n/a | n/a |

## 3. Lever table (failed)
The specific trap misses are INFERRED: the tests give digest-only verdicts and the oracle cannot run locally. The agent's runner implements nearly every named rule (runner.py: half-even :69, COMPLETE cutover :989-996, crawl date :1074, GPS :1434, footnotes :94-145, carry cap :1846, OVER_EPOCH :1961, countersign/revoke :1258-1340). So the failures are small slips that the all-or-nothing hashes amplify.

| id | weight | rule graded | agent's reading | mechanism | self-test catches? | fully stated? | family |
|---|---|---|---|---|---|---|---|
| 6 whole-file digests | 28 | every value in that file | (unknown individual slips) | one wrong row rejects the file (instruction.md:13) | N: the agent checked aggregate control totals (approved-plan total 1,779,913,000; restatement control total; v1 cluster counts 3,467/10,403; each record disposed of once; step 196). These hold while per-record dispositions differ. | yes | E stacked + B chain |
| slice_t1..t16 | 48 | per trap family | — | per-slice hash over all of the family's records; a BUDGET_EXHAUSTED/OVER_EPOCH cascade moves later records into every slice (TRUTH:195 "A wrong disposition that changes later budget decisions ... still moves the slices of those later records") | N, same reason | yes | C state (stateful stream) + B |
| decoy_group_1..5 | 15 | decoy handling (per-table authority) | — | decoy rows agree on almost every key, so a wrong source changes only a few values | N | yes | D cross-file |
| eval_* (6) | 28 | hidden S4 run | package run from the agent's own S3 final_state | dependent chain: an error in the S3 closing repeats in S4 even when the code is right (TRUTH Root cause) | N | yes | B + C |
| negative_nondeterministic_output | -3 | runs A and B byte-identical | the agent claimed "two runs produce byte-identical files" (step 196). It actually ran the package once on S3 with a different opening (step 179), never twice on the same inputs. | verifier runs A ≠ B on S4 against a fresh service; cause not found in runner.py (no time/random/unsorted sets). INFERRED: service-dependent state (ledger_seq or batch split) | N: never tested | yes (contract s5) | NEW "fresh-service determinism" |
| Judge R8 (neg -3) | -3 | no installs | `pip install pyflakes` (step 161) | conduct | n/a | yes | — |
| Judge R12 (1), R13 (3) | 4 | closing message lists 7 output paths; states open discrepancies or "none" | the closing named only final_state.json and never said "none remain" | report hygiene | n/a | yes | — |
| Judge R15 (3) | 3 | error handling | `except Exception: d = None` in Corpus.resolve | code quality | n/a | yes | — |

## 4. Contrast (passed)
- Passed: the shape gate (1) and judge R1-R6 and R11 (reconciliation habit, authority lookup, decoy non-authority, binding tables of demoted files, parse assumptions, posting via CLI vs API).
  - The agent understood the authority model. It lost on per-record exactness, not on concepts.
- Against our DIAGNOSIS:
  - Our rules each fired once on a visible row and were checked by isolated asserts.
  - Here the same kinds of rules (one sentence each) number about 24 and fire 1,881 times. Each graded unit bundles about 100 trap records into one hash, and the posting stream is stateful, so slips compound.
  - The difficulty is volume × exactness × state, not the cleverness of any single rule.

## 5. Agent behaviour
- 197 steps, about 85 min, $31.71.
- Read the register and contract only partially: `head -200` and greps (steps 3-6) of 5,000-line files. Dumped docx/pdf to text (steps 12-19). Explored data families (20-100). Started the simulator (101). Wrote runner.py (102), patched it (103-120), dry runs (121-133), full runs (134-137).
- Self-checks (138-158) all used corpus-embedded control totals.
- Tidy-up (159-174, including the pip attempt), final run (176-177), package (178), package re-run on S3 (179), format check (180).
- Final claim: no rejected postings, byte-identical re-runs. Reality: 0/21 slices, every digest wrong, nondeterminism negative fired.

## 6. Test design
- Expected values: fixed SHA-256 digests (visible), plus a regenerated S4 with stored digests (hidden).
- Partial credit only per slice (21 slices, 63 of 125 points), and every slice is all-or-nothing.
- Shipped-data-only weight: 97/125 (78%). Hidden: 28.
- Negatives (hardcoded, filename, reads corpus, nondeterministic) return True when the cheat happened, and only when both runs produced output.
- No message on failure: ctrf has empty messages, so the agent gets no gradient and graders get none either.

## 7. Judge design
- Failed: R8 (pip install), R12 (output paths listed), R13 (open discrepancies stated), R15 (error handling). None is about the core work.
- Reusable patterns:
  - R6, a "uses the designated channel for each operation" conduct check (CLI vs API);
  - R2/R4, an authority-lookup habit.
- JD-7: all are meetable by the oracle.
- JD-18: R15 is the code-quality criterion.

## 8. QC safety
| lever | IN-15 | TS-13 / TS-26 (03_Tests_QC.md:44, :53) | TS-16 | TS-19 | TS-20 | AL-28 | verdict |
|---|---|---|---|---|---|---|---|
| Stateful posting stream (order + batch rules feed later decisions) | stated | ok if graded at one observable | — | ok | ok | — | SAFE |
| Per-table authority (demoted file binding for one table) | stated (register s2) | ok | — | ok | ok | — | SAFE |
| Override in a footnote far from its table | stated | ok | — | ok | ok | — | SAFE |
| Low-authority file with bait practice + binding table inside the same file | stated | ok | — | ok | ok | — | SAFE |
| Whole-file digest + slice digest + hidden digest over the same records | — | RISKY: one wrong row fails the whole-file check, its slice(s) and the hidden check, i.e. "two tests reading the same observable ... pay one behaviour twice" (:53) | — | — | — | — | RISKY |
| Hidden tier seeded from the agent's own closing | stated (instruction.md:15) | RISKY: same double-payment concern | — | ok | ok | — | RISKY |
| Fresh-service nondeterminism negative | stated | — | honest-safe only if the service is deterministic; cause not found | ok | -3 ok | ok | RISKY (could an honest solution trip it? not proven either way) |

## 9. Writing style
- "a record belongs to the stage by its step and never by the window named in its file name: a logger flushes late" (register s1). Technique: state the rule together with the physical reason, so it reads as domain fact rather than as a trap warning.
- "is never a source of values, except for the tables this section names" (register s2). Technique: a blanket default whose exceptions sit in a list elsewhere; the agent must look up the exception per table.
- "Suggested practice: ... keep the first one logged" in operator notes "not reviewed", next to a table that "is binding". Technique: the bait and the binding content share one file, so file-level trust decisions fail.
- "Footnote N: row R of <caption>, column C reads V; this note overrides the table." Technique: overrides live as footnotes at the end of 5,000-line documents, so they need a full read rather than a grep for the table.
- "The planned_switch_step of the migration note is a plan, not a cutover" (tokenization standard). Technique: name what something is NOT and leave the reader to find what it IS in an event log.
