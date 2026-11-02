# B: cli-config-01. How it is built and why the agent lost points

## 1. Inventory
- **Domain**: offline security-policy compiler (config convergence plus evidence aggregation). **Archetype**: repair a broken stdlib CLI from tool.zip, then drive it to produce 22 artifacts in /app/out: config.json, 4 zone profiles, aggregates.json plus 7 text views, zone_totals, corpus_index, posture, rejected_ops, validation_report, summary, report.json (CLI transcript), a deterministic tool.zip, and manifest.sha256.
- **Files the agent sees** (/app/data):
  - 50 corpora c01..c50 in 20 wire formats (csv, tsv, psv, scsv, colon, ssv, caret, at, dcolon, bang, tilde, json, jsonl, xml, nested xml, ini, fixed, md, kv, properties), ~4-15 KB each;
  - change_journal.jsonl, 9000 ops (env counts mgmt 1871, edge 1817, dmz 1811, base 1776, core 1725), ~650-717 KB;
  - config_contract.md (198 lines, 1797 words);
  - config_schema.json 352 B, defaults.json 314 B, env_overrides.json 584 B, validation_rules.json 3274 B;
  - tool.zip 4168 B.
- **Instruction**: 647 words, 27 lines, 21 numbered requirements.
- **Tests**: 32 in tests/test_output.py, 27 positive (total 83) and 5 negatives (-3 credentials, -5 hardcoded, -5 nested, -3 fake transcript, -3 network).
  - Weights: 5 = config, profiles, aggregates, corpus_index, rejected_ops, validation_report, transcript, manifest, round-trip; 3 = views, zone_totals, posture, summary, cli_repaired, digest, flat, corpus_count; 1 = existence, minor views, world-readable, trailer_once.
  - Almost every check is a whole-file exact-equality compare against an expected value recomputed at test time.
- **Hidden or reseeded inputs**: no. The test embeds the shipped data as zlib+base64 `_BLOBS` and recomputes expected values from that copy. `EVAL_SEED` (L60) is used only for the anti-hardcode negative (L683). So 100% of positive weight is on shipped data.
- **Judge**: 14 criteria, `mode = "individual"`, reads the ATIF trajectory, gpt-5.6-sol.
- **Reward split**: reward.toml weighted sum, test 1/166 per point and judge 1/88, i.e. 50/50.

## 2. Rule map (graded rules)
| rule | where stated (all) | sentence form | trap explained? | shipped data separates readings? |
|---|---|---|---|---|
| Replay in seq order | instr L6; contract L14-27 | one plain sentence | yes ("intentionally out of order") | yes |
| Integer set must be a JSON int within bounds | instr L7; contract replay section; validation_rules.json | plain sentence + rules file | yes ("not a JSON string of digits") | yes |
| unset restores defaults.json value | instr L8; contract | plain sentence | yes ("last-set-wins while ignoring `unset` is wrong") | yes |
| **Spine replays only `env == base` ops** | NOWHERE explicitly. Instr L9 "Generate the base spine"; L10 says profiles replay "only that zone's valid journal operations"; contract L14-27 "Apply valid operations as events in seq order, last valid wins per key" (no env filter); tool.zip README "`plan` prints the fully resolved policy document for one environment", example `plan --env base` | scope by omission + implied by symmetry with the profile rule + example in a README | no | yes (all-env and base-only replays differ in 5 keys) |
| Profile = spine + overrides + that zone's ops | instr L10; contract L31-35 | plain sentence | n/a | yes |
| Effective hi = hi + R%97 + J%31 | instr L11; contract L54-65 | formula + motivation claim | yes (the claim is spelled out) | **no**: aggregates are invariant for shifts 17-31 |
| Row eligibility (zone, flag, canonical int) | instr L12; contract L43-51, L67 | long enumerated list | yes, every rejected form is listed | yes, but the TEST grades the opposite of the text (strips fields) |
| Views format | instr L13; contract | plain sentence | n/a | n/a |
| zone_totals, corpus_index, posture, rejected_ops | instr L14-17; contract L168-187 | key lists | tie-break stated | yes |
| validation_report / summary types and order | instr L18-19 give key names only | **types and order not stated** (validation_rules.json profiles order implies the zone order) | no | n/a |
| report.json via export-report, transcript | instr L20 | key list | n/a | n/a |
| Deterministic tool.zip | instr L21 | parameter list | yes | n/a |
| Manifest set | instr L22; contract L192-196 ("nineteen lines total") | explicit list | yes | n/a |
| JSON serialization | instr L23 | exact call | yes ("Default `json.dumps(obj)` breaks the manifest") | n/a |
| cli_repaired | instr L5 "repair the broken CLI" | **the test greps for the literal text `sort_keys=True`** | no | n/a |

## 3. Lever table (failed checks and criteria)
| id | wt | rule graded | agent reading (evidence) | correct reading | mechanism | self-test on shipped data catches it? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| config_matches_policy | 5 | the spine is the base env only | Replayed every env's valid ops into the spine. Step 21 `plan --env base` output shows hs 13336 / max 422 (all-env values). At step 33 its own README says "`base` is the spine, a zone name is that zone's profile", but the code does not apply that. | replay env==base only (test L410-415) | Scope by omission: the env filter is stated for profiles and not for the spine. The word "base" is the only cue. | N: no oracle; any self-test checks its own reading | NO, implied only → **RISKY under IN-15** (borderline HIDDEN) | NEW: scope-by-symmetry (close to D) |
| aggregate family (11 checks) | 29 | count rows by canonical value on raw bytes | Byte-exact: rejects ` 12`, `active ` (agent cli.py L181, L199; step 28 measured both readings) | test/oracle strip fields first | spec-test contradiction | n/a | test contradicts the text | **ARTEFACT, do not copy** |
| validation_report_correct | 5 | command_failures list, rejected_ops seq list | wrote counts 0 / 2113 | lists | type never stated, plus cascade | N | NO → **HIDDEN RULE** | (hidden schema) |
| summary_correct | 3 | profiles in zone order | sorted list | [core, edge, dmz, mgmt] | order not stated, plus cascade | N | NO (implied by validation_rules profiles order) → HIDDEN | (hidden schema) |
| cli_repaired | 3 | the literal `sort_keys=True` appears in the source | kwargs dict `"sort_keys": True` | the literal text | source grep | N | NO → **ARTEFACT** | — |
| judge #1 | 3 | observe the failing command before editing | rewrote cli.py without running it (steps 6 → 14-16) | run the broken CLI first | process rule | n/a | NO → **HIDDEN RULE** | process |
| judge #11 | 3 | name a concrete op whose misclassification shifts all aggregates | gave R/J/shift only | name an op | narration demand, and the property is false for this data | n/a | NO → **HIDDEN**, JD-7 doubtful | — |

## 4. Contrast: what the agent passed and why it was easy
- profiles_match 5, rejected_ops_match 5, config_is_flat 3, corpus_count 3, tool_round_trips 5, manifest_correct 5, report_transcript_real 5, digest 3, world-readable, trailer_once, posture_total_consistent.
- Every passed rule is **one plain sentence with the trap named in the same sentence**:
  - L7 "not a JSON string of digits"
  - L8 "last-set-wins while ignoring `unset` is wrong"
  - L23 "Default `json.dumps(obj)` breaks the manifest"
  - L22 the explicit 19-name list
- This is the same leak as our cohort DIAGNOSIS sec 0. The rule plus its trap in one sentence means the agent codes it right on the first write.
- The rejected-ops classifier (2113 rejections over 5 reason families, step 23) looks hard and still passed for the same reason.

## 5. Agent behaviour
- 46 steps, ~13.8 min, $3.96.
- Read order: ls → `cat` config_contract.md in full (step 3) → every JSON spine file → journal stats (steps 7-8) → heads of all 50 corpora (9-10) → trap scans for CR, ssv spacing, fixed-width offsets, md padding (11-13).
- It never ran the original broken CLI. At step 16 it wrote a 704-line cli.py from scratch.
- Self-tests: plan run (21), rejection counts (22-23), shift experiment exact vs strip (24-28), build.py (30), double-run determinism (40, 44 "FINAL RUN IDENTICAL").
- Every self-test used shipped data and checked against its own reading; none could reveal the spine scope.
- Final message (step 45) claims complete and verified. Reality: 45.78 on tests, mostly from artefacts.

## 6. Test design
- Expected values come from an in-test re-implementation (oracle at test time) over a fixed embedded copy of the shipped data. No reseeding.
- No partial credit: whole-file equality per check. One upstream reading (field trimming) fans out over 11 checks (29 points), which is a downstream cascade over whole documents.
- Negatives -3/-5 (hardcode marker via EVAL_SEED, nested config, fake transcript, network, credentials). None fired.
- The CLI is run as `nobody` for round-trip and transcript checks.
- 100% of weight sits on shipped-data-only checks.

## 7. Judge design
- Failed #1 and #11 grade rules not in the contract.
- Reusable patterns:
  - #13 "canonical int str(int(x)) == raw incl. non-ASCII digit families": grades whether the explanation matches the code. It is the outcome-explanation kind, which is fine.
  - #14 code quality, which satisfies JD-18.
  - #5 rerun determinism evidenced in the trajectory.
- Breaks:
  - #1 and #11 break **JD-16.1** (a constraint criterion must "Quote that sentence" from the contract).
  - #11 also risks **JD-7**: "Every criterion must be satisfied ... by the shipped oracle". The property it asks the agent to illustrate does not hold for the data.

## 8. QC safety of the levers that worked
| lever | IN-15 | TS-16 | TS-19 | TS-20 | AL-28 | overall |
|---|---|---|---|---|---|---|
| spine env scope by omission | fail-risk: the rule is not stated, only implied | n/a | risky ("learnable" only by inference from the profile rule) | ok (5 = core) | ok | **RISKY**. It becomes SAFE only if a definition elsewhere states it (e.g. "the spine is the `base` environment") while the replay section stays generic. |
| hidden validation/summary schema | fail | n/a | fail | — | cascade of aggregate_total into 2 more checks | **NOT ALLOWED** |
| strip contradiction | fail (contradiction, TS-19 line 120) | — | fail | — | stacks 29 points on one reading | **NOT ALLOWED** |
| source grep | — | TS-16 risk (an honest solution trips it) | — | — | — | **NOT ALLOWED** |
| judge #1/#11 | fail | — | — | — | — | **NOT ALLOWED** as written |

## 9. Writing style (technique only)
- "replaying only that zone's valid journal operations" (instr L10), while the spine sentence has no "only": an **asymmetric qualifier**. The filter is spoken at one site and omitted at the sibling site, so the reader must carry it over by symmetry. (This is the one lever that worked; it is borderline.)
- "`plan` prints the fully resolved policy document for one environment" (tool README): the **rule lives in tool documentation**, a third file away from the output spec.
- "Apply valid operations as events in seq order, last valid wins per key" (contract L14-27): a **generic rule whose scope is set elsewhere**.
- Counter-example (leaks): "last-set-wins while ignoring `unset` is wrong" (instr L8). It names the wrong reading and was solved first try.
