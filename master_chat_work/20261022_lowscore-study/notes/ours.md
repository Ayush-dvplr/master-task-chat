# Our 4 instructions: comparison notes (master, 22 Oct 01:25 IST)

Scores (tests-only, corrected verifier, from `master_chat_work/20261021_v0-rescore/RESCORE_REPORT.md:9-12`): emberforge 94.19% (146/155), vendor-archive 88.97% (129/145). District and schema: 84-94% overall per the brief (no per-check file read here).
Checks lost by ours (RESCORE_REPORT.md:11-12): emberforge `structure_findings_canonical_form`, `cap_and_floor_one_findings`, `quiet_rules_findings`; vendor `basic_delta`, `va1_cross_delta`, `va4_overlong_bytes`, `report_decoded_examples`. So the agent beat nearly all our composition rules; it lost on finding-code edge combinations and delta/overlong encoding.

## Shape of each instruction

| bundle | words | doc files | how rules are located | count of hidden rules stated? | trap list in instruction? |
|---|---|---|---|---|---|
| emberforge | 448 | 12 md/json docs (7 rulebooks with numbered rules V1..V9 etc., invariants, record_shapes, finding_codes, convention_register, calibration_slice) | "Read everything in that directory" (`instruction.md:3`) | yes: "Four conventions ... Exactly one draw from that register reproduces ... the calibration slice" (`:5`) | final reply must state the 4 conventions, total charge, cap-closing entries, multi-finding entries (`:13`) |
| vendor-archive | 571 | 4 md + 5 tables, named one by one (`:3`) | "Start with format_contract.md ... follow it to escape_rules.md, revision_notes.md and decoder_appendix.md, plus the tables ..." (`:3`) | yes: "fifteen rules you must work out" (`:3`) | yes, final account lists: trailer checksum coverage, frame start byte, unescape bound, dictionary/running-total state across segments, unknown extension, non-shortest integer re-encode, short-key->name via revision, four record modes, rejection order (`:13`) |
| schema-migration | 350 | 2 md + comment headers of 3 files + `rules` list of a json, all named (`:3`) | names every file AND the comment-header locations (`:3`) | yes: "54 numbered rules (K, M, N, C, P and T)" (`:3`) | partial: names every stage and the planning time-limit trap ("graphs with far too many paths to list", `:3`) |
| district-heat | 408 | 1 md (schema.md, 2627 w, numbered sections 1-8) | "the full rulebook ... is /app/data/schema.md. Treat schema.md as the authority" (`:1`) | no count | yes, bullet list of what must be right (`:9-15`) incl. "Empty groups, missing optional fields, rejected rows, exact boundaries, ties and zero denominators all have defined outcomes" (`:15`); final reply asks about pool cents, rounding inside search, waiver weights, duplicate profile rows (`:19-22`) |

## Signposting patterns in ours (candidate over-specification; to test against the 10)

1. Doc map: every instruction names the rule files, often in reading order (vendor `:3`, schema `:3`). The agent never has to find where rules live.
2. Rule count: "fifteen rules" (vendor `:3`), "54 numbered rules" (schema `:3`), "Four conventions" (emberforge `:5`). A count tells the agent when to stop looking and that every rule matters.
3. Trap list disguised as a final-reply requirement: vendor `:13` and district `:19-24` enumerate the exact edge rules the hidden tests probe (checksum coverage, non-shortest ints, waiver weights, duplicate rows). Asking the agent to explain them forces it to read and apply them.
4. Edge-case checklist in the body: district `:15` names the edge-case classes.
5. Numbered rules in docs (emberforge `V1..V9`, schema K/M/N/C/P/T, district numbered sections and an ordered 5-key objective `schema.md:171-180`): clean, enumerable, easy to tick off.
6. Generalisation limits stated precisely (emberforge "up to 48 requisitions ... within 38 seconds on 2 CPUs" `:7`; district "up to 22 sites and up to 4 offers per site ... 30 seconds" `:3`) - this tells the agent to build a test at that size.
7. Exact output file list, per-entity file names enumerated (emberforge `:9`, district `:5`).

Not over-specified: none of ours gives a procedure (step-by-step algorithm); they state end states. So "too precise" in ours = precise about WHERE and HOW MANY and WHICH TOPICS, not about HOW.

## To compare once the 10 reports are in
- Do the low scorers name their doc files / give rule counts / list trap topics in the final-reply section?
- Do their rules live in one file or are they spread with cross-file dependencies?
- Are their rules numbered/enumerable, or prose with defaults that look right?
- Do they state scale limits, or hide a size ladder?
