# DESIGN PROPOSAL r2 (4d6dfe8): sensor-network-lsq-correlated-adjustment

Bundle tree sha before any edit: `5823ca803559` (= last QC p12_r3). QC kit HEAD 976c1666 (expected).
Agent program saved: `OUT/agent_program/derive_report.py` (sha256 5b92d37c...).
Prototype: `OUT/proto/oracle_r2.py` (flags on a scratch copy of the oracle), `fuzz.py`, `cross.py`, `shrink.py`; raw results `fuzz200_full.json`, `fuzz200_iso.json`, `shrunk_10000019.json`, `shrunk_C_coupled.json`.

Domain, slug, input families and the 31-report deliverable stay. Three new rules, one hidden extract each for its separating case. No new output file, no new column.

## 1. Reflex pre-mortem (fresh claude-opus-5, first 10 minutes)

What the a2 trajectory did and a fresh run will repeat: read `instruction.md`, then all of `schema.md` in one pass, list `/app/data`, head every file the contract names, then write one ~940-line `derive_report.py` at minute 3-10 that transliterates schema sections 1-16 in order, run it on the shipped extract, check invariants (sum of shares, dof, chi bounds), copy the four figures into the final reply. It never revisits graded logic. Every old lever failed because each rule was one sentence that named its exception, and the shipped rows separated the readings so the self-test caught any slip.

The new levers are built so the shipped extract cannot separate the readings (W5, measured: `cross.py` shipped seed, every reflex identical to the oracle), and so the natural first write is the wrong one:

| Lever | First write Opus produces | Why the shipped self-test does not catch it |
|---|---|---|
| A H7 re-entry | one `share_closure(total, legs)` function with the "fits" test at the top; the second pass is written as `share_closure(total, survivors)` (re-enters the fits branch) | shipped groups only hit fits, proportional, drop-with-survivors-over-closure, none-held and zero; no shipped group has survivors whose summed basis is at or below the closure |
| B H6 recursive chain | `centring(row) = own term + own term of marks[row.set_out_from]` (one level, as agent L313-318 reads the registry row directly) | shipped chains are depth 1 (the named marks have blank `set_out_from`) |
| C H3 defined term | groups district rollups and closure groups by the per-line `region` field (values are district names) | shipped `region` equals the kept shard's district on every record |

## 2. Levers

### A. H7 re-entry: scale closure (new `schema.md` section 8b, after current L95-102; new file `scale_closure_register.csv`)

Rule text (draft):
> `scale_closure_register.csv` gives, for each district (section 2) and epoch, a signed `closure_micrometres` and a `floor_micrometres`. The closure of a district and epoch is absorbed by the length observations of that district and epoch. The basis of a length observation is the magnitude of its `computed_nominal` in metres, rounded down to a whole number. When the summed basis of the group is at or below the closure magnitude, each length absorbs its own basis in micrometres and the rest of the closure is left unabsorbed. When the summed basis exceeds the closure magnitude, the closure magnitude is shared in whole micrometres in proportion to basis by largest remainder, a tie between two remainders going to the lower `obs_id`. A length whose share then falls below the floor absorbs nothing, and every micrometre of the closure magnitude is shared again, in proportion to basis by largest remainder, ties settled as above, across only the lengths whose share was the floor or more; when none was, every length absorbs nothing. An absorbed amount carries the sign of the closure and is subtracted, in metres, from that length's misclosure `l` (section 8) before section 10.

Second pass names amount and method; never "by the same rule"; the separating case (survivors' basis at or below the closure) is neither named nor exemplified. Entity is new (geodetic scale closure on distance legs); the mechanism family follows the master's H7 wording rule.
- Reflex reading: the pass-2 call re-enters the fits branch, so survivors absorb only their basis.
- Hidden cases (G12): every corpus plants fits, proportional (no drop), drop (survivors' basis above the closure, readings agree), none-held and zero groups; eval alone plants one SEPARATING group (closure = largest value below S with survivors' basis S' <= closure). Generator asserts each planted branch by `classify()`.
- Tests: `test_scale_closure_shipped` w3 (visible: shipped re-run, residual rows of every length with a non-zero absorbed amount); `test_scale_closure_hard` w5 (eval: residual and final-weight rows of the separating group's lengths). Coupling: the absorbed amounts shift `l`, so all six eval families (18) move.
- Measured (200 corpora, `A_full`): reflex differs 200/200, loses 6 families + owned = 23/86 = **26.7%** (one-fact-wrong, CL-4 band 25-45). Agent program alone (`A_iso`, no other lever present): differs 200/200, 18/18 family points + owned 5 = 23/86.
- Shrunk corpus (seed 10000019, every other closure zeroed, no chain, no relabel): group East epoch 3, 72 legs, closure -48837 um, floor 254, basis sum 48838, 51 survivors with basis 45719; oracle absorbs 48837, reflex 45719 (51 legs differ); reflex and agent both fail all 6 families.

### B. H6 recursive chain: set-out marks (schema section 1 L9-19 and section 4 L57-70; new file `control_mark_register.csv`, new column `set_out_from` in `station_registry.csv`)

Rule text (draft), section 1:
> `control_mark_register.csv` lists the control marks by `mark_id` with `mount`, `centring_mm` and `set_out_from`. In `station_registry.csv` and in that register, a filled `set_out_from` names the control mark the setup was transferred from; blank means none. The centring variance of a station or of a control mark is `(centring_mm / 1000)^2` square metres when its own `mount` is `tripod` and zero when it is `pillar`, plus, when its `set_out_from` is filled, the centring variance of the mark it names.

Section 4 then reads "for every station with a non-zero coefficient in its `partials`, add that station's centring variance (section 1)". The definition is self-referential; there is no depth sentence and no example.
- Reflex reading: own term plus the named mark's own term (one level).
- Hidden cases: every corpus has blank links, depth-1 links, and unreferenced deep chains among spare marks; challenge alone links busy stations into depth 2-3 chains with a pillar mark in the middle (DELTA or EAGLE -> CM07 pillar -> CM08 tripod; FICUS -> CM10 tripod -> CM11 pillar -> CM12 tripod).
- Tests: `test_centring_chain_shipped` w3 (visible: final-weight rows of lengths touching linked stations), `test_centring_chain_hard` w5 (challenge: same rows). Coupling: base weights of about half the lengths change, so all six challenge families move.
- Measured (200, `B_full`): reflex differs 200/200, 23/86 = **26.7%**; agent alone (`B_iso`) differs 200/200, 18/18 + 5.
- Shrunk corpus (seed 10000019, closures zero): links BRAVO->CM03, CIVET->CM05, DELTA->CM07, FICUS->CM10; reflex and agent fail all 6 families.

### C. H3 defined term: district (schema section 2 L21-47, section 16 L216-217)

Rule text (draft), section 2: "The district of an observation is the district of the shard that holds its kept record (`obs_source_district_north.csv` is North, and so on)." Section 16 L216 becomes "The four district rollups key on the observation's district (section 2)"; section 8b keys closures by district. `region` stays in the field list as it is now; nothing contrasts the two.
- Reflex reading: `district = record.region`.
- Hidden cases: shipped and challenge/eval: `region` equals the kept shard's district on every record (generator aligns `region` at emission); audit alone relabels 24 lengths (+6 angles) whose closure groups are proportional or drop, so moving them changes shares.
- Tests: `test_district_shipped` w3 (visible: `district_*.json` counts on the shipped re-run), `test_district_hard` w5 (audit: `district_*.json` plus residual rows of relabelled lengths). Coupling through A: relabelled lengths change closure groups, so all six audit families move.
- Measured (200, `C_full`): reflex differs 200/200, 23/86 = **26.7%**. Agent alone with no closures present (`C_iso`): only the district rollups move, 3/18; with closures present (the shipped design) it is 18/18. Shrunk (seed 10000019, 3 relabels OB00001 West->North e2, OB00358 East->South e2, OB00693 East->West e1): all 6 families; with 1-2 relabels in fits/zero groups only the rollups move, so the generator must assert at least 3 relabels land in proportional/drop groups.

### Reading the numbers
The a2 agent program predates these rules, so it differs from the oracle on every planted corpus by construction (it reads neither the new files nor the new column). The figure that predicts a fresh run is the one-lever reflex variant (the oracle with exactly that lever's wrong reading): 200/200 corpora differ for each lever and each costs 23 of 86 test points alone. No real trajectory has seen these rules yet; whether a fresh Opus takes each reflex is unmeasured until the probe.

### Independence and W5
`cross.py` over the shipped seed and 30 planted corpora: in every corpus the reflex of each non-planted lever gives the oracle's answer exactly (0 differences). On the shipped seed all three reflexes reproduce the oracle (vTPv, residuals, regions, weights).

## 3. Cost table (P' = 62 + 3 x (3 + 5) = 86)

| Row | Tests lost | Tests % |
|---|---|---|
| A alone wrong | 18 + 5 = 23 | 73.3 |
| B alone wrong | 23 | 73.3 |
| C alone wrong | 23 | 73.3 |
| any two wrong | 46 | 46.5 |
| all three wrong | 69 | 19.8 |
| agent program a2 (predicted) | fails all 3 hidden extracts and visible A/B; passes artifact 1, control 3, superseded 3, canonical 1, visible C 3 | 11/86 = 0.128 (reflex gate <= 0.20) |

Judge: keep R1-R8 (R1-R4 figures recomputed because the shipped closure changes the shipped solve: prototype vTPv 1000.2090455410 vs 1016.9199434352). Add three conduct criteria w3, own-input recompute, oracle `solve.sh` prints `check <id> ok` for each:
- R9 recomputes, outside `derive_report.py`, the absorbed closure total for one shipped district and epoch and states it;
- R10 recomputes one station's centring variance from the two registers and states it;
- R11 recomputes one district's observation count from the shards and states it.
Positive judge points 15 -> 24. A run that misses A and does none of R9-R11: tests 73.3, judge about (12)/24 = 50, overall about 61.7 (< 70). All-but-one-right rows all under 70 overall when the matching recompute is skipped.

Prediction: fresh Opus tests 70-90 if it misses one of A/B/C (A most likely, C least certain), 46 if two. TEST_DEPTH found explicit keyed sentences followed at 0% differing, so C carries the most risk of being REVEALING; A follows the only habit ever measured GENUINE; B is the untried recursive-chain shape.

## 4. Edits (Phase 2, after "go")
- `schema.md` (and `SCHEMA_MD` in `tests/test_output.py`): sections 1, 2, 4, new 8b, 15 (no change to decoy list), 16 L216.
- Generator in `tests/test_output.py`: region alignment in `_plan_duplicates`; `emit_control_marks`, `set_out_from` column; `emit_scale_closures` with branch planting and `classify` asserts; per-seed variant keys `closure_sep` (eval), `chain_deep` (challenge), `district_relabel` (audit).
- Reader/solver: `read_station_centring` recursive, `read_source_shards` sets district, `apply_scale_closure` before `adjust`.
- Six new tests and weights; reward.toml weight 0.5/86; judge R9-R11 and R1-R4 figures; `solution/solve.py` mirrors the reference and self-checks; regenerated shipped data (all files re-emitted by `python3 tests/test_output.py DIR`) and re-embedded `_SHIPPED_DATA` per rule 6; TRUTH.md, XREF.md, LEVERS.md, COST_TABLE.md, RULE_COVERAGE.md, JUDGE_MAP.md, QC_DEFENCE.md.
- Fuzz gate >= 300 corpora on the final generator; reflex gate on the a2 program with the real tests.

## Lessons for the master
- An agent program written before a rule exists always differs on it; the one-lever reflex variant is the meaningful fuzz number | no change: prompt already asks for both
- A defined-term lever that only feeds rollups costs 3/18 per extract; coupling it into a quantity every row reads (closure groups) is what lifts it to 23/86 | no change: G1 coupling already says this
