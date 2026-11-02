# B: wire-format-recovery: how it is built and why the agent lost points

Phase A verdict PARTLY (near ARTEFACT). All of the loss comes from an exact-key-set gate plus one preference judge criterion, and no semantic lever cost points. This file is kept short and records the design lessons, mostly as anti-patterns.

## 1. Inventory
- **Domain / archetype:** binary container codec. The agent writes `/app/decode.py` (bytes → JSON) and `/app/encode.py` (JSON → bytes, byte-exact), plus 4 artifacts in `/app/out`.
- **Files the agent sees:**
  - `SEALB-capture-log.jsonl`: 2.2 MB, 20000 hex captures. It is raw mode only by design (test_output.py L661-665: "deliberately NON-REPRESENTATIVE").
  - `SEALB-container-format.md`: 6739 B, 129 lines.
  - `SEALB-decoder-appendix.md`: 3785 B.
  - `SEALB-encoder-notes.md` 921 B, `SEALB-error-codes.md` 731 B, `SEALB-glossary.md` 858 B, `SEALB-varint-crc-primer.md` 766 B.
- **Instruction:** 558 words, 24 lines.
- **Tests:** 29 in total: 24 positive (weight 72) and 5 negative (-5, -5, -5, -5, -3). Weights 1/3/5. Every corpus is regenerated inside test_output.py from SAMPLE/CHALLENGE/EVAL seeds (L72-74).
- **Hidden inputs:** yes. EVAL_SPECS (L408-441) gives 32 captures that mix raw, delta and dict records, long keys and large magnitudes. FIELD_SPECS (L395-406) adds damaged captures for the error paths.
- **Isolated vs whole-output:** the 8 eval decode tests compare the WHOLE document (`_docs_equal`, L821-835, exact key sets). Two tests are isolated field checks: `record_count_matches_and_file_order` compares keys only, and `pre_resolution_payload_fields_present` checks only that the fields exist.
- **Weight split:** about 26/72 on labelled-sample, existence and own-artifact checks; about 46/72 on hidden generated corpora. INFERRED split from the test list in report.json.
- **Judge:** 12 criteria, batched, judge gpt-5.6-sol. Positive weight 34 (R1-R3, R6, R7, R10-R12 at w3; R4, R5 at w5 critical); R8 and R9 are negative at -5. Reward split 50/50 (reward.toml 1/144 and 1/68).

## 2. Rule map (graded rules)
| Rule | Where stated | Form | Trap explained? | Shipped data separates? |
|---|---|---|---|---|
| Header layout and order | container-format.md L28-33; appendix L11 (grammar JSON) | explicit table + JSON summary | n/a | yes (raw captures) |
| Selector bits / mode ids | container-format L40-43; appendix L11 | explicit | n/a | raw only |
| i16 sign extension | L51 "i32 LE (WIDE_VALUE=1) OR i16 LE (WIDE_VALUE=0) ... signed" | one sentence | no | yes (log has wide False 28493 records, step 8) |
| Delta = signed LEB128, running += delta | §4 L67-71 + a worked byte example ("-3 is the single byte 7d") | one plain sentence + example | example given | NO (log is raw-only) |
| Dictionary of pre-resolution payloads, forward index | §5 L75-77 | one dense sentence | no | NO |
| Error precedence magic > version > CRC | container-format L91-104; error-codes.md | explicit | n/a | yes (log has all three errors, step 7) |
| CRC coverage (header after magic + body) | L108; primer | explicit | n/a | yes |
| **Per-mode record key set** | raw: L53-57 JSON object. delta/dict: only "reported as `delta_raw`" (L71) and "reported as `dict_index`" (L77). WIDE_VALUE "(raw mode only)" (L41) refers to the bit. encoder-notes L10 "Raw records set `wide_value`" | **implied by omission** | no | NO |
| No helper modules imported | instruction L22 | one sentence | n/a | n/a |

## 3. Lever table (failed items)
| id | w | rule graded | agent's reading | correct reading | mechanism | self-test catches? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| decodes_{raw_i32,raw_i16,delta,dict,mixed,large_magnitude,long_keys,short_keys}_from_eval | 3+3+5+5+5+5+3+3 = 32 | full-document equality on hidden mixed-mode captures | every record carries `wide_value` (decode.py L110-115; step 13 prints delta record with `"wide_value": false`) | delta/dict objects omit `wide_value` | exact key-set gate on a shape shown only for raw | N: the agent's round-trip runs through its own encoder, which ignores the key (steps 10, 20) | **NO: HIDDEN RULE (implied by omission)**. Not allowed for us. | NEW: "schema gate on an unshown shape" (artefact class) |
| judge R11 | 3 | "adds no auxiliary or renamed modules" | wrote `build_artifacts.py` (step 11) and `AGENTS.md` (step 22) to produce /app/out | criterion wants no extra files | approach preference; the instruction bans only *imports* of helpers (L22) | n/a | NO (instruction does not forbid build scripts) | preference: not a lever |

Confirmation run: with the extra key removed, the agent's decoder matches all 32 eval documents (`equal_after_dropping_nonraw_wide_value 32`). The genuine semantic lever cost is therefore **0**.

## 4. Contrast: what passed and why
- **Rejection and precedence tests (10 pts).** The shipped log carries all three error kinds (step 7 `Counter({'unsupported_version': 637, 'bad_magic': 588, 'trailer_crc_mismatch': 567})`), so the agent could watch each rule fire. This is the same leak as our cohort's shipped boundary rows (DIAGNOSIS cause 4).
- **Round-trips (6 pts).** These are self-consistent by construction, because decode and encode are written by the same agent.
- **Hidden-semantics rules.** Delta LEB128 sign extension, forward dictionary of payloads and the running value were all coded right on the first write (decode.py created at step 6). Each rule is one plain sentence and delta has a worked byte example. **The non-representative shipped log did NOT create difficulty**: a capable agent implements a clearly written rule correctly without ever seeing an instance. This matches our DIAGNOSIS: hiding the data while stating the rule plainly is not a lever.
- **Artifacts (12 pts).** The agent constructs its own examples, so the shape spelled out in decoder-appendix L30-55 is easy to meet.

## 5. Agent behaviour
- 24 steps, about 6 min.
- Read order: listed the files (step 2), read container-format.md fully (step 3), then the other 5 docs fully (step 4), probed the log (step 5).
- Wrote decode.py in one create (step 6) and checked it on the whole shipped log (steps 7-8). Wrote encode.py (step 9) and round-tripped 18208 captures with 0 failures (step 10).
- Built its own delta/dict/long-key examples through `build_artifacts.py` (steps 11-13). The step 13 output shows the extra key; the agent did not question it.
- Then checked determinism and error cases in /tmp (steps 15-16), fixed the encoder (steps 17-19), re-checked (steps 20-21) and wrote AGENTS.md (step 22).
- Final message (step 24) claims the codec is implemented from the spec. That is true for semantics and false against the hidden key-set gate.
- No plan was written down. The self-tests covered every mode only through the agent's own encoder, which is circular.

## 6. Test design
- Expected values come from an oracle at test time: the in-file reference encoder and `_generate_doc` with fixed seeds, and the program runs under `nobody` (L785-798).
- There is no partial credit inside a test. Each decode test needs N captures with the feature (for example delta ≥6), every one exactly equal.
- **Whole-document equality with exact key sets** is the brittle design. One extra key fails 8 tests across unrelated features. That is the opposite of isolated per-rule checks.
- Anti-cheat negatives cover: hardcoded sample answers, filename keying, reading the corpus at runtime, rebinding the stdlib, nondeterminism. None fired.
- Share of weight on shipped-data-only checks: about 36% (26/72, INFERRED).

## 7. Judge design
- R11 penalises an approach the instruction allows. JD-15 (04_Judge_QC.md L92-96) says "conduct negative penalising an approach = fail", and R11 behaves like one, so it is RISKY or a FAIL.
- R4 and R5 (critical, w5) grade the same observable as the eval decode tests. That breaks **JD-8** (L77, "no overlap with tests"), and here the two verdicts even disagree.
- **JD-18** (L99, "at least one criterion judges code quality for code-authoring tasks"): none of the 12 criteria judges code quality, so this is a FAIL.
- JD-7: the oracle can meet every criterion (INFERRED, since the solution writes only the two programs).
- Reusable pattern: R6 "validates decoder behaviour against the worked examples embedded in the shipped specification" (w3, conduct, odds-raising) passed.

## 8. QC safety
| Item | IN-15 | TS-16 | TS-19 | TS-20 | AL-28 | Verdict |
|---|---|---|---|---|---|---|
| exact key-set gate on delta/dict objects | fail: shape not stated | n/a | fail: "flag undocumented edge cases" | weights 3-5 on what is really one schema property, billed 8 times | n/a | **NOT ALLOWED** |
| judge R11 "no auxiliary modules" | fail: instruction allows helper files | n/a | n/a | n/a | n/a | **NOT ALLOWED** (as written) |
| hidden corpus with modes absent from the shipped data | stated rules | ok | ok | ok | ok | SAFE, but cost 0 points here, so it is no lever on its own |

To make the gate fair, the spec would have to print the delta and dict objects. It would then cost 0, because the agent coded the semantics correctly.

## 9. Writing style
1. "part of the task is deciding which of those files matters" (instruction L1). This invites a relevance triage, but every doc was short and the agent simply read all of them (step 4). It did not work as a lever here.
2. "The raw delta, before it is applied, is reported as `delta_raw`" (container-format L71). Naming the field in prose instead of printing the object leaves the object shape implicit. This is what produced the artefact; avoid it unless the shape is printed somewhere.
3. "the pre-resolution payload of every preceding record (`raw_value` for raw, `delta_raw` for delta, `dict_index` for dictionary records) is appended to it" (L77). One dense sentence defines a non-obvious state: the dictionary stores payloads, not resolved values. The agent still got it right, so a dense, correct statement is not a lever by itself.
4. "deliberately NON-REPRESENTATIVE" shipped corpus (test L661-665). The technique is to withhold instances and keep the rules. It cost 0 points.
