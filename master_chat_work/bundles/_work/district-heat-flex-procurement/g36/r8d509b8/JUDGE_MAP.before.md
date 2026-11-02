# JUDGE_MAP - district-heat-flex-procurement (P12 9a85fdc, 27 Oct 2026: R5 layout criterion deleted, R6-R12 renumbered R5-R11)

Positive 24 (R1-R4, R8-R10 w3; R5, R6, R11 w1), negative -5 (R7). Probe criteria (w3 process trajectory): R1-R4, R8-R10 = 21 of 24 (87.5%). Previous map: p12/JUDGE_MAP.before.md.

| id | requirement it serves | oracle shows it at (solve.sh stage / printed line) | test it must not overlap |
|---|---|---|---|
| R1 drawn allowance on own extract | instruction.md exact values on fresh inputs; site_allowances.tsv drawn rule | own-extract stage, extract 1: "own extract, candidate_offer_count of the later event OWN-0102: program 1, by hand 1, agrees" | allowance_ticks_mutation and *_hard read grader extracts, not the agent's own |
| R2 start order on own extract | schema.md season order by start instant | extract 2: "own extract, events that select Q-1's offer: program ['OWN-0202'], by hand ['OWN-0202'], agrees" | selection_match_hard |
| R3 composed rate above cap on own extract | schema.md rate composition and cap | extract 3: "credit_cents of OWN-0301: program 40, by hand 40, agrees" + "cap_binding_count: program 1, by hand 1, agrees" | segment_rate_adder_mutation, cap_binding_match* |
| R4 half-cent interval on own extract | schema.md half-even per interval amount | extract 4: "credit_cents of OWN-0401: program 1, by hand 1, agrees" | credit_rows_match* |
| R5 exact arithmetic | schema.md:123-124 | solve.py:20 half_up, :25 half_even (integers only) | canonical_serialization_and_integer_units grades JSON types only |
| R6 final run after last edit | instruction.md run on shipped data | solve.sh:6-7 copy then run derive_report.py; no later edit | artifact_set_exists_and_parses (presence) |
| R7 (-5) claims a check its output contradicts | instruction.md final reply | oracle claims nothing; stages print agree/DIFFER as measured | none |
| R8 grant cents recomputed outside | instruction.md exact values | self-check stage: "grant cents recomputed outside the program: agree (grant cents of 2000 event-regions recomputed)" | grants_match* |
| R9 remaining allowance recomputed outside | same | "remaining allowance recomputed outside the program: agrees (remaining allowance of every chosen offer recomputed)" | ledger_quality_match* |
| R10 credit_cents recomputed outside | same | "credit_cents recomputed outside the program: agree (credit_cents of 2000 event-regions recomputed)" | credit_rows_match* |
| R11 maintainable derive_report.py (J4) | JD-18 04:99 | solve.py named functions load :130, choose_portfolio :268, credit_cents :371, share_pool :396, holder :430, choose_all :437, build :458 | none |

The self-check stage returns 1 only when a recomputed figure differs (solve.sh:224; oracle 0). The own-extract stage only prints and ends `|| true`.
