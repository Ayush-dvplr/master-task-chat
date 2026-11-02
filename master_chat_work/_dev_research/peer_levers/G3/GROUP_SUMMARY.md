# G3 peer lever mining: group summary (board 118ec8a)

Anubis HEAD 19cdf6989906385943b9ca00acaadcae204b29e8. Session renamed to 118ec8a (ses_e9970c2aeffeYgB2VZbbs90Q7j, shown by `opencode session list`). One run per task, claude-opus-5 via openhands-sdk 1.55.1, judge gpt-5.6-sol. Evidence for each claim is in the `A_*.md` and `B_*.md` files next to this one.

## 1. Scores and verdicts

Points are raw positive points from TRUTH.md/reward.toml. "Lost" means positive points not earned plus any negatives that fired.

| task | verdict A | overall / tests / rubric | tests points lost (genuine) | judge points lost (genuine) |
|---|---|---|---|---|
| pretraining-token-ledger-closeout | GENUINE (amplified by exact hashes) | 33.34 / 0.00 / 66.67 | 124 of 125 lost, plus the -3 nondeterminism negative fired (score clamped at 0) | 10 of 30 (R12 1, R13 3, R15 3, R8 -3 fired) |
| sentinel-fraud-training-release | GENUINE (amplified) | 19.76 / 2.68 / 36.84 | 145 of 149 | 12 of 19 (R3 3, R4 3, R11 3, R9 -3 fired) |
| slo-credit-closeout | GENUINE (amplified) | 38.69 / 2.38 / 75.00 | 205 of 210 | 6 of 24 (R7 3, R10 3) |
| survey-raking-disclosure-audit | GENUINE (one rule, PROVEN). The lever itself fails IN-16 | 36.88 / 41.41 / 32.35 | 75 of 128 | 23 of 34 (R1, R4-R8 what-ifs = 22, R10 1) |

Phase A found no harness artefacts:
- `exception_info` is None for all four runs.
- `test-stdout.txt` holds only the reward line.
- The verifier executed every agent program on hidden data. The proof is a passing hidden-run check in each task:
  - sentinel: `held_release_when_catalog_file_missing`
  - slo: `eval_held_close_exact`
  - survey: `unseen_run_writes_complete_report_set` plus 9 hidden upstream groups
  - pretraining: the nondeterminism negative fired, which requires two completed runs.
- There was no permission trap. Each test.sh does `chown root` and chmod on /logs/verifier, and runs `chmod -R go-rwx /tests`. Agent code runs as uid 65534 in private dirs.

The near-zero test scores are genuine value errors. The grading design turns a few slips into almost total loss (see section 5).

## 2. Lever patterns (SAFE or RISKY only), ranked by genuine points cost

Per-pattern points in the three digest-only tasks are INFERRED: the tests give hash verdicts only and their oracles could not run locally (they need pypdf/openpyxl). Survey is the only exact attribution.

### P1. Stateful stream: one wrong disposition moves later outcomes (family C + B), SAFE
- **Mechanism:** an ordered ledger with caps or budgets, such as BUDGET_EXHAUSTED/OVER_EPOCH, quarter-to-date caps in subscription order, or "prior split outranks pins". A wrong early decision shifts the outcome of later, unrelated records, so the error lands in every per-family slice.
- **How it is written:** the order and cap rules are stated plainly in one section. Contract s3 gives the stream order, and a quarantine credit ends the batch. The cascade itself is never mentioned.
- **Why self-tests miss it:** the agent checks totals such as "no chunk over cap" and "each record disposed once". These invariants hold even when the order or the dispositions are wrong (pretraining step 196).
- **Tasks:**
  - pretraining (TRUTH:195 "A wrong disposition that changes later budget decisions ... still moves the slices of those later records")
  - slo (caps carried quarter-to-date via --prior)
  - sentinel (delta prior split outranks pins)
  - Evidence: B_pretraining §3, B_slo §3, B_sentinel §3.
- **Our use:** a retention cohort where a churn or reactivation decision consumes a per-account allowance that later months read, so one wrong month changes later cohort cells.

### P2. The shipped control checks the layer below the graded meaning (family D), SAFE
- **Mechanism:** the data ships with a verifiable control: a lineage DB with partition counts and hash sums, 100-record control-sum blocks, or embedded control totals. These controls check parsing and record counts only. The graded values come from semantic rules above that layer: labels, point-in-time joins, splits, authority.
- **How it is written:** the control is described honestly as a parse/count control.
- **Why self-tests miss it:** the agent treats "all controls ok" as its acceptance test, and the controls are green while the graded values are wrong.
  - sentinel step 118: "all ok True" with splits still wrong (train 23,240 vs 23,746).
  - pretraining: every embedded control total matched, yet 0/21 slices passed.
- **Tasks:** sentinel, pretraining, slo.
- **Our use:** ship a vendor-archive manifest with row counts and amount sums per file. It validates ingestion, while the graded retention or reconciliation values depend on rules the manifest cannot see.

### P3. A "make it match" repair that is plausible and wrong (NEW: control-fitting), SAFE
- **Mechanism:** when the honest reading fails a control, there is a tempting repair that makes the control pass but contradicts a stated reading rule.
- **Evidence (PROVEN, slo):**
  - The agent's harness printed `cdn_attestations.xlsx ... bad=101` (steps 49 and 113).
  - The agent then permuted sheets until the sums matched (transform.py:1021-1035).
  - source_register.md:93 says "sheets in catalog order".
  - The file carries 20 traps (TRUTH:60). The close was PUBLISHED with a false claim, and judge R7 caught it.
- **How it is written:** the reading rule is a plain clause in the register's per-file conventions, far from the control definition.
- **Why self-tests miss it:** the repair turns the self-test green by construction.
- **Our use:** a district-heat meter export whose control block only matches if a stated column-offset rule is applied. A tempting alternative fix (reordering, or a rescale) also matches the counts but not the per-row values.

### P4. Multi-document composition per concept (family A + E), SAFE
- **Mechanism:** one graded value needs 3-5 files. Sentinel splits need the policy docx, the device registry kinds, the exemption table, the revocation latest action, the link log vs the fingerprint first_seen, merge chains, and pins and prior state.
- **How it is written:** each piece is a plain sentence, but in a different file from the data it governs (sentinel TRUTH:5 "usually in a different file from the data it governs"). Pretraining also uses footnotes in docx/pdf that override table cells far from the table.
- **Why self-tests miss it:** the agent implements each clause it finds (sentinel transform.py:2410-2554). An interaction that is missing or approximated (re-link after UNLINK at :2450; non-test/val pin at :2510, both INFERRED) leaves no visible symptom.
- **Tasks:** sentinel, pretraining.
- **Our use:** cohort membership composed from the signup log, a merge-chain register, an exemption list and a revocation file, each in its own document.

### P5. Upstream derivation feeding a long chain of graded stages (family B), RISKY (AL-28/TS-26 stacking)
- **Mechanism:** one input-derivation rule (the reference-wave band) feeds raking, then trimming, replicates, estimates and disclosure. Stage groups are graded on 4 extracts, so one misread costs 75 test points and 22 judge points.
- **How it is written:** in survey the rule was a fallback chain whose scope was ambiguous (HAS-7-standard.md:237-243). That wording is NOT ALLOWED (IN-16). The allowed variant states the chain unambiguously and keeps the cascade.
- **Why self-tests miss it:** the pilot record supplies unit levels directly, so the agent's pilot check (step 13) never exercised band derivation. The shipped data publishes no raking figure for the round.
- **Proof:** a one-branch patch makes all 22 files byte-identical (A_survey).
- **QC risk:** grade each stage once, or TS-26 double payment applies.
- **Our use:** a cohort assignment rule that feeds retention curves, then the reconciliation, then the disclosure table.

### P6. Hidden period seeded from the agent's own closing (family B + C), RISKY
- **Mechanism:** the next period starts from the agent's prior output. pretraining starts from final_state.json; slo and sentinel use --prior. A visible error repeats in the hidden tier even when the code is right (pretraining TRUTH Root cause).
- **Why self-tests miss it:** the agent cannot see the next period.
- **QC risk:** it pays the visible error twice (TS-26). Seeding the hidden run from an oracle prior isolates the code.
- **Our use:** a next-month cohort run from the agent's retention state.

### P7. Per-table authority inside a demoted file (family D), SAFE
- **Mechanism:** a draft, preview or mirror file is wrong for values but binding for exactly one table or section. Example: the pretraining preview export is the only ledger_code→account crosswalk. In slo, "only the sections the charter designates" count.
- **How it is written:** one per-role sentence in the register/charter, next to a general "drafts are never a source of values, except the tables this section names".
- **Why self-tests miss it:** decoy rows agree on almost every key, so using the wrong source changes only a few values.
- **Tasks:** pretraining, slo, sentinel. These are 15-20 decoy-group checks; all failed in the three digest tasks, and the share per pattern is INFERRED.
- **Our use:** a vendor-archive "restated" file that is wrong for amounts but is the only source of a vendor-id crosswalk.

## 3. Writing patterns (rule fully stated, not reflexively solvable)
- **General rule with a named exception list in another section.** Example: "never a source of values, except for the tables this section names". The exception's table lives in a per-role list, not beside the rule.
- **The rule lives in a reading convention for the file, not in the logic section.** Examples: "one data row below the header row of each sheet, sheets in catalog order" (slo register:93) and "belongs to the stage by its step and never by the window named in its file name".
- **Plan vs fact distinction stated once.** Example: "The planned_switch_step ... is a plan, not a cutover". The obvious field exists, and the fact must be derived from event rows.
- **Bait carried by a low-authority document that also holds one binding table.** Example: a runbook "Suggested practice: keep the first one logged", in the same file as a binding hot-swap table.
- **Field disclaimers.** Example: "The epoch ... fields of the loaders are logger bookkeeping and are not counters". The convenient column is disclaimed, and the counter must be built from postings across stages.

## 4. Anti-patterns
- Things that looked hard but cost nothing:
  - Binary HELD/publish gates: passed in sentinel and slo.
  - Output format and key order: passed everywhere, and the agent self-verified it (pretraining step 180).
  - Authority-model understanding: judge R1-R6 passed in pretraining and slo.
  - Withheld settings recoverable from published figures: the survey agent brute-forced the 12 combos on the pilot at step 13 and found the unique match. This is our DIAGNOSIS leak again: a published target makes the rule self-checkable.
  - Determinism and row-order independence: passed, except pretraining's negative.
- Allowed only because the rule is ambiguous or hidden (NOT ALLOWED for us):
  - Survey reference-wave band chain: the scope of "Where hours are absent" is ambiguous (IN-16).
  - Survey judge what-if numerics R1, R4-R8: they re-charge the same raking error through the judge. RISKY under JD-8 (same observable) and AL-28 stacking.
- Volume of traps is not itself a lever. Pretraining has 1,881 traps and its agent implemented nearly every named rule. Points were lost through all-or-nothing hashing × stateful cascade, not through rule cleverness.

## 5. Score artefacts and amplifiers (do not copy as levers)
- No ARTEFACT verdicts.
- Amplifiers inflate how strong a lever looks:
  - **Whole-population concept projections:** sentinel and slo hash every record per concept, so one wrong record fails the concept. Concepts, slices and decoys also overlap on the same records, a TS-26 risk. Partial credit is near zero, so the 2-3% test scores overstate how far off the agents were.
  - **Pretraining clamp:** the tests channel is floored at 0 after the -3 negative. verifier/reward.json reads 32.53 while the pass summary reads 33.34 (unexplained gap, noted).
  - **Pretraining nondeterminism negative fired:** runs A ≠ B on S4 against a fresh service, yet no nondeterminism source was found in runner.py. A negative an honest solution might trip is a TS-16 risk; treat it as unproven.
- Local oracle runs for sentinel and slo were impossible (missing pypdf/openpyxl). The slo local HELD result is a local artefact, not a task property.

## 6. Open questions for the master chat
1. Should we adopt P3 (control-fitting trap) as our first lever? It is the only one proven to defeat a self-check. It needs a control that a wrong repair can satisfy at block level but not at row level.
2. P1, P2 and P4 are SAFE but their per-rule effects are INFERRED here. Do we want a group that can run the peer oracles in Docker to attribute the losses exactly?
3. For P5 and P6, do we accept the cascade and grade each stage once (lower stacking risk, smaller loss), or keep per-stage grading and argue that each stage is a distinct observable?
4. Should our hidden tier seed from the oracle's prior (isolates the code) or from the agent's own prior (P6, stronger but RISKY)?
