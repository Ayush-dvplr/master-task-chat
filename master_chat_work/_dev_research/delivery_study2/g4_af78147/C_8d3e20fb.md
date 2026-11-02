# C_8d3e20fb: security policy compiler v3 (NEW only)

This card lists only what differs from the two earlier versions: `delivery_study/sugam_a_3bfed9f/C_4ee62df1.md` (4ee62df1, PARTLY 48.99/20.62/77.36) and `delivery_study/sugam_b_bd5de18/C_af6f42c3.md` (af6f42c3, PARTLY 69.5/45.83/93.18). Anything not listed here is the same as those cards, including the persona, the 50 odd-extension corpora, the journal + defaults + overrides spine, the zone profiles, the canonical-integer token rule, the mirrors, and the manifest.
T = `Final_Delivery/8d3e20fb-2aab-5efb-be67-7ad3dbeabc8f`.

## 1. Scores and verdict

The final score is 63.64, with tests at 41.24 and rubric at 86.05. **Verdict: PARTLY** (details in `A_8d3e20fb.md`).
- Test points lost: 57 of 97.
  - 38 come from the spine-scope value cascade (HIDDEN RULE: the reference contradicts the literal contract).
  - 16, plus a fired -3 negative, come from the `python -I` tool-run artefact.
  - Strictly genuine test loss is 0 points.
- Judge points lost: 6 of 43, both genuine (13.95 rubric points).

## 2. Inventory (what changed)

- The category is now **Debugging**; earlier versions were data-pipeline or cli-config. The archetype is build-repair + data-pipeline.
- Timeouts: agent 7200 s, verifier 2700 s. Resources: 2 cpu / 4 GB. Expert estimate 480 min.
- `instruction.md` now has **21 numbered requirements** and states several rules outright:
  - req 3 forbids digit strings on integer keys;
  - req 4 makes `unset` restore defaults and warns that "last-set-wins while ignoring unset is wrong";
  - req 5 requires the base spine to be produced "by driving the repaired CLI (init / set / validate)";
  - req 8 enumerates the rejected digit scripts.
- **New computational term.** The bound is `hi + (R mod 97) + (J mod 31) + (E_i mod 7)`, solved as a per-corpus fixpoint. E_i is the eligible-row count under that same bound (instruction req 7; `config_contract.md:54-72`).
- Tests: 33 checks, +97 / -16. `tests/test_output.py` has 1071 lines, much smaller than before. The docstring calls it an "Independent re-derivation" from the embedded `_BLOBS` (:1-7).
- Judge: 13 criteria, +43, batched. Reward split 50/50 (`reward.toml` 0.5/97 and 0.5/43).

## 3. Core difficulty (what is new)

- The fixpoint term is a real computational core, but the contract spells it out, including the trap ("A one-pass solver that uses only hi + (R mod 97) + (J mod 31) will misclassify the rows planted at the fixpoint boundary", `config_contract.md:71-72`). The agent solved it, and judge R10 passed.
- **Classification: unstated or implied rule** (spine scope) **+ an artefact**. The only lever that cost points is still the spine scope, which has now cost points in all three versions.
- This time the agent's literal reading is the documented one. Step 37 compares `all-env spine R 17554` with `base-only R 33796`. The agent's `/app/AGENTS.md` says "not only `env == "base"`; the profiles are the only env-filtered replay".
- A blind Opus does not "fail to transliterate" here. It transliterates the contract, and the reference disagrees with the contract.

## 4. Test architecture (differences)

- **Expected values.** They come from a compact reference inside the test file (`replay` :414-424, `hi_fixpoint` :435-445, `wanted_config` :447-452). There is no generator and no hidden corpus.
- **Coverage.** Shipped-only grading is 100%; stacking_check classifies `trailer_once` as hidden_rows, which is a false positive.
- **Mirrors.** These are now graded against the **reference** aggregates (`_expected_view` :573). The earlier own-aggregate anchor (`_agent_agg`) and the `_real_work` gate are gone.
- **New tier: re-execution of the delivered tool.** `run_tool` (:513-533) runs `python -I cli.py` from /tmp under setpriv uid 65534 with a minimal env and a 120 s limit. Four checks use it:
  - `report_transcript_real` 5 replays every recorded validate and needs the same rc and stdout (:674-708);
  - `tool_round_trips` 3;
  - `cli_repaired` 5 does init, then `set --value 321` must give an int, then `plan --env base == wanted_config` (:736-759);
  - `compile_reproducible` 3 runs compile twice and needs byte-equal output (:972-987).

  Together these are 16 points, all of which depend on the tool running at all.
- **Negatives.** `negative_fake_report` -3 reruns export-report and fires if the output differs **or rc != 0** (:801-824). That makes it a crash detector as well as a cheat detector.
- **Tool archive.** `tool_zip_deterministic` (:957-969) requires stored members, the 1980 epoch, mode 0o100644, and a `cli.py` that differs from the shipped one.
- **Shares.** Value checks that depend on the spine: 38/97 = 39%. Tool re-execution: 16/97 = 16.5%. Format and determinism checks that pass on any honest run: 43/97.
- **stacking_check output.** AL-28 flags "UNMATCHED act negative_fake_report -3 + R7 -5 = 8 FAIL"; this is a heuristic pairing and the two penalise different acts. The TS-26 hint lists 20 checks as duplicates; that is a false positive because they share the `_holds` helper.

## 5. Lever table (failed checks)

| id | w | rule graded | locations (quote) | sentence form | agent reading | correct (reference) reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| config_matches_policy + 7 mirrors + zone/index/posture/aggregates | 38 | spine replays only `env == "base"` ops | `config_contract.md:17-18` "its `env` is listed in `journal_envs`"; `:31-35` zone filter "whose `env` is that zone"; `instruction.md:9` "the base spine"; reference `:447-452` `replay(seed_doc, "base")` | scope by omission, with the literal text pointing the other way | all valid ops of every listed env (step 37; AGENTS.md) | base-only | no control value is shipped and no visible spine; both readings are self-consistent | **No: HIDDEN RULE.** The contract states the opposite literally. QC passed because the reference and TRUTH.md (:111-112 "matching the journal-replayed baseline") restate the reference without citing text | LV8 / R4 scope by omission; prior E1; N2/N3 class |
| report_transcript_real, tool_round_trips, compile_reproducible, cli_repaired; negative_fake_report fired | 16 + 3 | delivered tool must run as `python -I cli.py` from another cwd | `tests/test_output.py:513-533` only | test-only (no sentence) | multi-module package driven by `run.py`, verified with plain `python3` in a fresh dir | single-file or self-locating imports | the agent's own fresh-dir rerun did not use `-I` | **No: ARTEFACT** (N5 format only in test code; TS-19 not learnable) | NEW artefact class |

## 6. Judge architecture and losses (differences)

There are 13 criteria. By target: 10 are `trajectory`, 2 are `user_facing_message` (R8 negative, R9), and 1 is `state_change` (R13 code quality). Negatives are R7 -5 (external CLI) and R8 -5 (false success claim).

| crit | w | wording | agent | why JD-* accepted | class |
|---|---|---|---|---|---|
| R1 (`tests/judge.toml:11`) | +3 important | "The agent inspects the local CLI source, schema file, and failing command behaviour before editing." | read source and README at steps 5-7; never ran the broken CLI; first edit at step 18 | the oracle trajectory can show a run of the broken tool, so JD-7 is OK; the criterion is behavioural and checkable in the trajectory | process step with a "before" anchor |
| R12 (`:154`) | +3 important | "The agent names at least one concrete journal operation whose misclassification would change the effective upper bound of every one of the fifty corpora." | explained the shifts generally; named no op | the oracle can name one; the chained-coupling claim in req 7 makes it a fact the agent must surface | final-answer fact: per-item enumeration of a counterfactual instance |

**What is new vs prior versions.**
- R1 rewards **observing the fault before repair** (debugging hygiene). It cost Opus 3 points because Opus reads code and rewrites rather than running the broken tool.
- R12 asks for **one named instance**, not a count.
- Both are fair, and both are shapes Opus skips when its final message is a summary.

## 7. How it passes QC (deltas)

- **IN-15, TS-19, AL-1.** The spine scope is graded but not stated, and the literal text contradicts it. It passed QC as in both earlier versions; nobody flagged it across three reviews.
  - The `python -I` execution mode is not stated anywhere: `instruction.md` has no isolated-mode or single-file sentence, while `tests/test_output.py:521` has `"-I"`. This is an unlearnable gate, contrary to QC_RULINGS TS-19 "stricter than contract FAIL", yet it passed.
- **TS-16.** `negative_fake_report` fires on rc != 0 (:801-824), so an honest tool that cannot be imported is penalised as a fake. QC_RULINGS TS-26/TS-16 expect negatives to fire only on the cheat. It passed.
- **CL-4.** The cascade is announced in req 7 ("a single misclassified journal op is observable in every one of the fifty aggregates") and in `config_contract.md:64-65` ("depends on BOTH a correct spine replay AND ..."). This is the KNOWN CL-4 exemption by stated coupling.
- **IN-17.** The contract spells the fixpoint trap at :71-72; QC allowed it because it explains a computation, not a hidden reading. This is consistent with prior cards.
- **AL-28.** Negatives total -16 across 4 acts, each ≤5. PASS.
- **JD-7.** R1 and R12 are satisfiable by the oracle trajectory. **JD-15.** Process criteria with "before" anchors are accepted.

## 8. Leak avoidance (new points)

- **W1 / IN-17 violated, but harmless.** The fixpoint trap is spelled out; the agent solved it, and solving it gained the agent nothing it could not already do.
- **W10 partly reversed.** `instruction.md` now carries rules (reqs 3, 4, 7, 8). The rules it states are exactly the ones Opus got right.
- **LEAK_LIBRARY row.** "every rule one explicit sentence" fits V0-8. The only point-costing rule is the one *without* a sentence.

## 9. Agent behaviour

- **Reading.** Steps 2-17 (15:24-15:31) read the contract, JSON inputs, tool source and all corpora.
- **First program.** Modules were created at steps 18-27. The first full pipeline run was step 28 at 15:36:26, **about 12 min** after start.
- **Graded logic.** The graded logic was not changed after that. Step 37 was a deliberate both-readings check that kept the all-env spine.
- **Self-tests.**
  - determinism reruns (38, 46, 52);
  - manifest verification (39);
  - independent hand-rolled parsers for 14 aggregates across 10 formats (42-43);
  - fresh-dir rerun of the extracted zip with plain `python3`.
- **Final claim.** "All requirements are satisfied and verified." The values are wrong under the reference, and the tool fails under `-I`.
- **Cost.** About 20 min, $5.03, 76k output tokens.

## 10. Passed checks (why easy)

Profiles (zone replay overwrites the differing keys), rejected_ops, validation_report, summary, manifest, json_canonical, zip determinism, trailer and counts all passed. Each is either a plain stated rule or format, or does not depend on the spine scope. Judge: 9 of 11 positives passed, including the fixpoint and token-rule explanations (R10, R11), which are restatements of stated rules.

## 11. Take-aways (new only)

- **AVOID (artefact): re-executing the delivered program under an interpreter mode the instruction never states.** Examples are `-I` or `-P`, a different cwd, or setpriv. If we re-run the delivered tool, we must state the exact invocation (for example "run as `python3 -I cli.py` from another directory; it must be one file or locate its own modules"). Otherwise this repeats N5/TS-19.
- **AVOID: rc-sensitive negatives.** A cheat detector that fires on rc != 0 turns a crash into a penalty (TS-16). Gate the negative on a successful rerun.
- **AVOID: a reference that contradicts the literal contract.** Three versions show it is not a lever. Opus saw both readings and chose the text. This is not a hardness pattern; it is N2/N3.
- **ADOPT SAFE NEW (judge): "observes the fault before repair" process criterion** for repair tasks. Wording template in our own words: the agent runs the shipped tool, or reproduces its failure, before its first edit. It cost Opus 3 of 43.
- **ADOPT SAFE KNOWN (J6): per-item counterfactual enumeration.** The pattern is "names one concrete X whose change would alter Y". Opus answers with aggregates and misses it.
- **Build technique (SAFE, if stated): a re-execution tier.** Re-running the delivered tool on the shipped inputs and comparing it with its recorded transcript is a strong anti-hand-writing check. It just needs the invocation contract written down.
- **Lesson on computational terms.** Adding a stated computational term (the E_i fixpoint) did not create loss. A spelled-out computation is transliterated.
