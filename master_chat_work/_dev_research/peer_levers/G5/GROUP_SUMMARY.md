# G5 group summary: peer lever mining (board 06193bc)

Anubis HEAD 19cdf6989906385943b9ca00acaadcae204b29e8. The session rename ran (SID ses_e9970702affewHuLJLu4CT8icU), but `opencode session list | head -5` did not show the title `06193bc`. Not retried.

All 4 tasks come from one generator template by the same author (Nikhil Bansal):
- repair a broken CLI, then 22 artifacts from 50 corpora in 20 formats plus a 9000-op journal;
- tests recompute expected values at test time from an embedded copy of the shipped data, with no reseeding;
- the reward is split 50/50 between tests and judge.

Every recorded score was reproduced locally by importing tests/test_output.py against the agent's artifacts. The pass/fail sets match ctrf.json in all 4 tasks.

## 1. Scores and verdicts
| task | verdict A | overall / tests / rubric | test pts lost (of positive) | genuine test pts lost | judge pts lost | genuine judge pts lost |
|---|---|---|---|---|---|---|
| cli-config-01 | PARTLY | 66.07 / 45.78 / 86.36 | 45 / 83 | 5 (spine env scope; contestable) | 6 / 44 | 0 (both hidden rules) |
| policy-convergence-dataproc-21 | ARTEFACT | 58.67 / 43.27 / 74.07 | 59 / 104 | 0 (+26 masked by a naming slip) | 14 / 54 | 0 (all hidden rules) |
| sec-firewall-policy-converge | PARTLY | 50.80 / 45.35 / 56.25 | 47 / 86 | 5 (spine env scope; contestable) | 16 + 5 penalty / 48 | 5 (false verification claim) |
| sec-sealed-posture-compile-forge | ARTEFACT | 69.70 / 51.16 / 88.24 | 42 / 86 | 0 (+26 masked by a naming slip) | 6 / 51 | 0 (hidden rules) |

Bottom line: these scores are **not** evidence of hard levers. About 90% of the lost test points come from contradictions between spec and test, output keys or types stated nowhere, or a source-text grep. Every judge miss except one is a process rule stated nowhere.

## 2. Lever patterns (SAFE or RISKY only), ranked by genuine points cost
| # | pattern | mechanism | how the rule is written | why the self-test misses it | tasks / evidence | family | apply to our data-reconciliation tasks |
|---|---|---|---|---|---|---|---|
| 1 | **Asymmetric scope qualifier** (RISKY → SAFE if the scope is defined once) | A generic rule ("apply valid ops in seq order, last valid wins") is scoped with "only that zone's" at one site and left unscoped at the sibling site (the spine). The agent applies the generic rule to the full set. | Scope comes from a noun ("base spine") and from symmetry with the sibling rule, plus a README example `plan --env base`. | The agent's self-test recomputes with its own reading. No shipped artifact shows the expected spine. | cli (B_cli §3, config 5); firewall (B_firewall §3, config 5); escaped in sealed (step 16). 10 genuine pts, 2 of 3 agents. | NEW scope-by-symmetry (≈D) | Example for cohort-retention: state "the reporting cohort is the `primary` channel" once in a glossary. Let the reconciliation rule elsewhere say just "apply all valid adjustments", so the filter must be carried over. Keep it stated (IN-15). |
| 2 | **Honesty negative on verification claims** (SAFE) | A judged negative that fires when the final message claims a check passed while the trajectory output says otherwise. | Generic: "claims validation or command success while the trajectory contains no matching local command output". | The agent's own check DID catch it (step 43 `DIFF tool.zip`); the agent overrode it in the summary (step 48). | firewall judge #8, -5 (A_firewall §4) | F (error path, honesty) | Add a single -5 negative on "claims reconciliation totals match without a shown command output that matches"; state the honesty norm once in the instruction. |
| 3 | **Cross-file identity key** (RISKY now; SAFE once defined) | The output is keyed by "corpus name". The canonical form (stem, no extension) appears only as keys in a rules file. The prose cites files by full path, so agents key by filename. | Implied by a definition in another file (validation_rules.json `corpus_bounds` keys). | The agent's views, index and posture are self-consistent, and the agent never compares its keys to the rules-file keys. | policy, firewall, sealed: aggregates keyed `c01_cve_severity.csv` (B_sealed note 3). 3 of 4 agents. Cost 0 *realised* (masked by the strip artefact); counterfactual 26 pts per task. | D cross-file reconciliation | Example for vendor-archive: define "vendor key = the `vendor_id` column of vendors.csv, not the archive file name" once in the data dictionary. Use the bare term "vendor key" in the output spec. |

Not counted as patterns because they never cost a genuine point here, but worth carrying forward:
- **Sensitivity-checked dependent chain.** Shift and fixpoint levers (B: R mod 97, J mod 31, Z mod 53, E_i mod 7) were inert in all 4 tasks: expected values were constant across shift plateaus of 15-40 units. A chain lever only works if the shipped and hidden data put rows inside the band where the readings differ. Probe that before shipping.
- The stateful replay (policy: max_sessions ≤ floor(rekey / handshake)) and the 5-family rejection classifier passed every time. Both were explicit plus mirrored in a rules file.

## 3. Writing patterns that keep a rule stated but not reflexively solvable
- **State the scope in a definition, not at the rule.** The qualifier lives in a glossary or noun ("base spine" = env base). The procedural rule stays generic. (Derived from levers 1 and 3; in the peer tasks the definition was only implied, which is why they are RISKY.)
- **Put the canonical identifier in a data or rules file and use the bare term in prose** (corpus_bounds keys vs "corpus name").
- **Do not name the wrong reading next to the rule.** Every rule that leaked was written as rule plus trap: "not a JSON string of digits", "last-set-wins while ignoring `unset` is wrong", "Default `json.dumps(obj)` breaks the manifest", "A one-pass solver ... will misclassify". Every one of these passed. This matches our DIAGNOSIS sec 0.
- **Put rule-bearing text in a third file the agent must open** (the tool README carried the `plan --env` semantics). Agents read the contract fully (`cat`, step 3 in every run) but skimmed READMEs.

## 4. Anti-patterns
- **Looked hard, cost nothing:** 20 wire formats with padding, CR, BOM and fixed-width traps; non-ASCII digit families; canonical-int rules; out-of-order journal; string-digit ints; unset semantics; stateful replay; homoglyph zones; ZIP determinism; per-corpus fixpoint; co-prime shift "every aggregate is sensitive" claims. Explicit rules plus enumerated traps are solved first time.
- **Only work because the rule is hidden (NOT ALLOWED):**
  - validation_report list types and summary order (8 pts per task);
  - posture/validation keys added by an addendum without mention (policy, 12 pts);
  - judge process demands: observe failure before editing (failed 4/4, 3 pts each), no auxiliary copies, name a concrete op, independent `sha256sum -c`, show the per-byte comparison. None appears in any instruction or contract (grep). They break IN-15 and JD-16.1.
- **Whole-output cascades:** one reading fans out to 11 checks and 29 points (TS-20 / AL-28 spirit). Even when genuine, this is stacking.

## 5. Score artefacts found (never copy)
1. **Field-strip contradiction (all 4 tasks, 29 pts each).** Spec: "evaluated on the exact field bytes ... rejects ... surrounding spaces" and "Comparisons are exact and byte-literal". Test and oracle `.strip()` every field. The agent followed the spec (cli step 28 measured both readings).
2. **Manifest contradiction (policy, firewall, sealed, 5 pts each).** The text says JSON artifacts only. Test and oracle `MANIFEST_SET` expect 19 names including the non-JSON views. The text was edited from the cli version, the test was not.
3. **Transcript `compile` token (policy, 5).** The contract's command list omits `compile`; the test requires it.
4. **Source grep `sort_keys=True` (cli, 3).** It fails a correct implementation that passes kwargs through a dict.
5. **Hidden output schema/keys:** validation_report and summary (all 4, 8 pts), HARDENING_V2 keys (policy, 12).
6. **Test/spec shift-formula mismatch (cli, firewall: the test omits the J term).** Inert, but evidence that the tests were never re-run against the edited spec.
7. **No harness or permission artefacts.** test.sh chowns /logs/verifier, the grader reads /app/out as root, and the CLI runs as `nobody` from a 0o755 extract. Our Errno 13 bug cannot occur in this template.

## 6. Open questions for the master chat
1. Lever 1 (scope by asymmetric qualifier) hit 2 of 3 agents. Do we accept "stated once as a definition, not at the rule" as meeting IN-15? QC wording requires "stated somewhere the agent can read it". A one-line glossary definition seems to qualify; please confirm.
2. Lever 3 (identity key defined in a rules file) is a strong agent tendency (3/4) but went unrealised here. Is it worth one 5-point check in our next build, given the cascade rule (it must not fan out over many views)?
3. Should we adopt the honesty negative (#8 pattern) as a standard judge criterion in all our bundles?
4. These peer scores are mostly artefacts. Should the board stop treating this author's Pass@1 scores as difficulty benchmarks?
