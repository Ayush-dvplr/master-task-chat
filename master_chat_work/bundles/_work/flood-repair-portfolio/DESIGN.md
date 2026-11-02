# DESIGN ed7b0c2 flood-repair-portfolio

Archetype domain-calculation, category optimization, core build, seed 558214. Written after
PREMORTEM.md; all timings are Docker `--cpus=1`, python 3.12 unless marked local.

## 1. Story and spine

A city flood-repair programme funds repairs in rounds. A book is many rounds. For each round the
programme picks the conflict-free set of repair proposals with the largest total benefit. The agent
writes `/app/out/derive_report.py DATA_DIR OUT_DIR`, runs it on the shipped book, and the same program
is run on fresh books.

Spine (per round, then per book):
1. S1 load: manifest.json gives the declared files and the fault order.
2. S2 faults: scan files in manifest order, rows in file order; first fault rejects the round (LV-FP-4).
3. S3 valuation: integer benefit per proposal from four files (LV-FP-3).
4. S4 conflicts: pairs from exclusive crews, live permits, explicit exclusions by proposal or site (LV-FP-2).
5. S5 portfolio: maximum-benefit conflict-free set, id tie-break (LV-FP-1, the core).
6. S6 projection: one portfolio per round feeds all ten documents (COUPLING G1).

## 2. Input files (all flat in /app/data; 11 files, 7 formats)

| file | format | shipped rows | holds | depends on |
|---|---|---|---|---|
| manifest.json | json | 1 object | book id, ordered list of the 10 data files | none |
| contract.md | md | ~150 lines | the whole specification (W10) | none |
| proposals.csv | csv | ~2,500 | round, proposal, site, crew, households, risk_override | sites, crews |
| segment_codes.tsv | tsv | ~2,500 | round, proposal, segment | proposals, benefits.ini |
| sites.jsonl | jsonl | ~2,400 | site, risk_class, premium | none |
| region_codes.csv | csv | ~2,400 | site, region (North/South/West/East) | sites |
| crews.tsv | tsv | ~2,100 | crew, mode (exclusive/shared) | none |
| permits.csv | csv | ~2,600 | round, permit, proposal, status (held/applied/withdrawn) | proposals |
| exclusions.json | json | ~600 entries | round, first, second (proposal id or site id) | proposals, sites |
| benefits.ini | ini | ~12 | [segment_rate] per segment, [risk_uplift] per class A-D | none |
| audit_queries.txt | txt | ~2,200 | `VALUE <round> <proposal>` and `PAIR <round> <a> <b>` lines | all |

A5: every csv/tsv/jsonl/txt >= 2,000 lines, total >= 20,000 (target ~21,500). Shipped book: ~175 small
rounds (10 to 16 proposals) plus two large rounds (120 and 160 proposals) of the hidden family, so the
honest difficulty is visible. crews.tsv carries the city-wide crew register (crews with no proposal in
the book are noise rows). Ids: fixed-width random tokens (`P` + 6 digits proposals, `S` sites, `C` crews,
`M` permits, `R` rounds), fresh in every hidden book, no meaning in any prefix (DS-4).

Chains (length >= 4):
- C1 proposal -> site (proposals.csv) -> region (region_codes.csv) -> region_<X>.json rows and sums.
- C2 proposal -> segment (segment_codes.tsv) -> rate (benefits.ini) -> benefit -> portfolio -> segment docs.
- C3 proposal -> site -> risk_class (sites.jsonl) unless risk_override -> uplift (benefits.ini) -> benefit.
- C4 exclusion naming a site -> proposals of that round at the site -> conflict pairs -> portfolio.
- C5 proposal -> crew -> mode (crews.tsv) -> conflict pairs -> portfolio -> every document.

## 3. Levers

### LV-FP-1 exact optimum (core, governing file contract.md section "Portfolio")
Rule text: "A portfolio of a round is a set of its proposals in which no two proposals conflict. The
chosen portfolio of a round is the portfolio with the largest total benefit. When several portfolios
share that total, sort each one's proposal ids in ascending text order and compare the lists position
by position; the first position where they differ decides, and the list holding the smaller id there
is chosen."
Limits (contract section "Limits"): at most 200 rounds per book, at most 160 proposals per round, at most
900 conflict records (permits.csv rows plus exclusions.json entries) per round, households 1 to 60,
segment rates 5 to 60, uplifts -10 to 30, premiums 0 to 800; the program finishes a whole book within
20 seconds; the program is one self-contained file using python3 and its standard library only.
(Final: 20 s per book, contract.md line 15; oracle worst 0.49 s in Docker --cpus=1, 0.25 s at --cpus=2.)
Reflex reading: generic exact B&B (colouring or clique-cover bound, reductions, memo, component split),
then a deadline that returns the incumbent, or greedy plus swaps.
Hidden cases: every hidden book has two large rounds (140 to 160 proposals) drawn from the triangular
lattice family with diagonal probability 0.7, benefits within +-10% of a common value, labels and rows
shuffled. Seeds were kept only after the build-time filter (WORK/baselines.py in Docker): optimum
unique, and every baseline loses at least one large round per book; per-round losses in COST_TABLE.md.
Why visible data cannot confirm: no optimum, total or selected list is shipped (W11); brute force on
the small rounds and conflict-freeness both pass for a wrong solver; the large shipped rounds only
show that a generic exact does not return (honest signal, G-3).
Interactions: the tie-break matters on small rounds with planted equal-total portfolios (AL-27) and on
the large rounds only through uniqueness (seeds whose large-round optimum count is above 1 were
rejected: h1_2, h3_3, h3_4; WORK/UNIQUENESS.md).
Measured (PREMORTEM): every generic exact TO at 10 s (and the best at 60 s, 600 s local); greedy loss
395 to 1195, 1/2-swap 169 to 453, ILS at limit 58 to 250, LP rounding 63 to 407, LP rounding plus swaps
0 to 143 (exact on one of six rounds), B&B incumbent at limit 204 to 577. Reference DP 0.08 to 0.19 s.

### LV-FP-2 conflict derivation across files (governing section "Conflicts")
Rule text: "Two different proposals of the same round conflict when at least one of these holds: they
have the same crew and that crew's mode in crews.tsv is `exclusive` (a `shared` crew never makes a
conflict); they appear in permits.csv rows of that round with the same permit, and neither of those
two rows has status `withdrawn`; or exclusions.json has an entry for that round whose `first` names one
of them and whose `second` names the other. A name in an exclusion is a proposal id, or a site id that
stands for every proposal of that round at that site."
Reflex readings (each one source dropped): withdrawn rows counted, shared crews treated as conflicts,
site-named exclusions skipped or matched only against proposal ids, permits matched across rounds.
Hidden cases: lattice edges split across all three sources (measured shares per large round: crew
about 22%, site-named exclusions about 16%, permits about 36%, proposal-id exclusions the rest);
planted decoys: withdrawn permits and shared crews only on non-adjacent pairs. The generator asserts
the derived conflicts equal the lattice edges; every single-source mutant loses 94 to 97% (COST_TABLE).
Why visible cannot confirm: the slipped program still produces feasible-looking portfolios on its own
conflict set; only the true conflict set (never shipped as pairs) decides.

### LV-FP-3 integer valuation (governing section "Benefit")
Rule text: "The risk class of a proposal is its `risk_override` when that field is not empty, and
otherwise the `risk_class` of its site in sites.jsonl. The benefit of a proposal is households times
(the segment rate of its segment plus the risk uplift of its risk class), plus the premium of its site.
The segment rate is the `[segment_rate]` entry of benefits.ini named by the proposal's segment in
segment_codes.tsv; the risk uplift is the `[risk_uplift]` entry named by the risk class; the premium is
the `premium` of the site in sites.jsonl and is added to every proposal at that site."
Reflex readings: override ignored, uplift skipped, premium multiplied by households or added once per
site. Hidden cases: ~25% of proposals carry an override that differs from the site class; sites with 2
or 3 proposals; one class uplift negative. Override-removal probe (check_exact): blanking risk_override
changes 27 shipped rounds; mutants lose 88 to 94%.

### LV-FP-4 fault precedence (secondary stated rule, <= 25% positive weight; section "Rejected rounds")
Rule text: faults by file: proposals.csv `DUPLICATE_PROPOSAL` (an id repeated in its round) and
`INVALID_INPUT` (households not a whole number 1 to 60, unknown site, unknown crew, risk_override not
empty and not A to D); segment_codes.tsv `UNKNOWN_PROPOSAL` (proposal not in that round) and
`INVALID_INPUT` (segment not in benefits.ini); permits.csv `UNKNOWN_PROPOSAL` and `INVALID_INPUT` (status
not one of the three); exclusions.json `UNKNOWN_PROPOSAL` (name neither a proposal of the round nor the
site of one). "A round's code is that of its first fault, taking files in manifest order and rows in
file order." A round with no file fault whose any proposal has benefit below 1 is `NONPOSITIVE_BENEFIT`.
Rejected rounds have no portfolio. A declared file missing from DATA_DIR: exit non-zero, stderr
`ERROR MISSING_FILE <file name>`, nothing written. Hidden cases: rounds with two faults in different
files; hidden manifests list files in a different order than the shipped one (W7 control).

## 4. Outputs (all keys and codes written out in contract.md, DS-25)

- summary.json: book, rounds[] (round, status planned|rejected, selected sorted ids, total_benefit,
  proposals), planned_rounds, rejected_rounds, total_benefit.
- policy_audit.json: one row per audit_queries.txt line in order. VALUE rows: households, segment,
  rate, risk_class, uplift, premium, benefit, selected. PAIR rows: sources (subset of crew, permit,
  exclusion in that order), conflict, first_selected, second_selected. Rows of rejected rounds: status
  rejected only.
- data_quality.json: rejected[] (round, code) by round id; conflict_pairs and withdrawn_permit_rows over
  planned rounds.
- region_<North|South|West|East>.json and segment_<commercial|public>.json: per planned round the
  selected ids in that region or segment and their benefit sum; total.
Contract sentence: "Every reported figure of a round is computed from the one portfolio chosen for it."

## 5. Rejection paths
Missing declared file (mutation test), five fault codes, rejected rounds excluded from all totals and
listed in data_quality.json, final reply lists shipped rejected rounds (judge J6).

## 6. Test plan (tests/test_output.py; weights 5 core / 3 sub-goal / 1 existence)

Hidden books generated in tests from an embedded seeded generator (seed only in tests/), book files
pinned by sha256, expected documents computed at grade time (about 0.1 s per book); the agent program runs from a
foreign cwd (setpriv nobody) with `python3 -I -S` (master M1b: no site-packages, so an installed
solver is unreachable), wall limit = stated book limit 20 s. Expected documents come from an
independent reference in the test file (min-fill elimination), books regenerated and hash pinned.
| check | weight | n | doc family |
|---|---|---|---|
| shipped outputs exist and parse | 1 | 1 | all |
| shipped summary / policy / data_quality / regions(4) / segments(2) whole-doc exact | 3 | 5 | visible |
| hidden book k feasible (selected sets conflict-free under true conflicts) | 3 | 3 | summary |
| hidden book k selected lists exact | 5 | 3 | summary |
| hidden book k summary whole-doc exact | 5 | 3 | summary |
| hidden book k policy_audit whole-doc exact | 3 | 3 | policy |
| hidden book k data_quality whole-doc exact | 3 | 3 | dq |
| hidden book k region docs whole-doc exact | 3 | 3 | regions |
| hidden book k segment docs whole-doc exact | 3 | 3 | segments |
| G6 rate scaled by non-round factor + rows shuffled: summary exact | 5 | 1 | mutation (J9 pair) |
| G6 relocated and renamed data dir, foreign cwd: all docs exact | 3 | 1 | mutation |
| G6 rows rotated: summary exact (expected recomputed) | 3 | 1 | mutation |
| G6 declared source deleted: non-zero exit naming it | 3 | 1 | mutation |
| G6 run twice: byte-identical | 3 | 1 | mutation |
| negative: delivered program refers to /tests files | -5 | 1 | G4 cheat |
| negative_hardcoded_sample_answers: program holds >= 3 selected shipped ids or the shipped total | -3 | 1 | G4 cheat (validator 7.4 name) |
Totals: 34 checks, positive 108; hidden plus mutation share 92/108 = 85% (G3 >= 30%); whole-doc share
~80%. Messages print the first differing JSON path. One-fact-wrong score: a program right everywhere
except one selected id in one large hidden round loses that book's selected, summary, likely policy,
region and segment checks (<= 19/108) and keeps the rest; recorded in COST_TABLE.md for CL-4.

## 7. Judge plan (tests/judge.toml, batched, 9 to 11 criteria)
J2 conduct (each done by solve.sh self-check printing `check <id> ok`): recomputes every planned round's
total outside the program; checks every selected pair against conflicts derived again; recomputes every
VALUE audit row; reconciles region and segment sums with summary; certifies small-round optima with a
second exact method. J3 honesty negative -3. J4 one maintainability criterion. J6 final reply lists every
shipped rejected round by id. J9 runs the program on an altered copy and checks dependent figures move.
Details in JUDGE_MAP.md (Phase 5).

## 8. Expected loss per lever (tests channel, of 108; measured, WORK/COST_TABLE.md)
| lever | wrong reading | measured loss |
|---|---|---|
| LV-FP-1 | greedy, swaps, timed B&B or ILS, wrong tie-break | 80 to 83 (74 to 77%) |
| LV-FP-2 | one source dropped or misread | 101 to 105 (94 to 97%) |
| LV-FP-3 | one adjustment skipped | 95 to 101 (88 to 94%) |
| LV-FP-4 | order slip only | 3 to 15 (secondary, 11% planned share) |
Probability claude-opus-5 misses LV-FP-1: high unless it finds an elimination or sweep order on the
large shipped rounds (story 1); LV-FP-2/3 low (plain table rules); these give coupling, not difficulty.

## 9. Per lever, hidden input and check expected to lose (measured)
- LV-FP-1: H1 R27904/R66927, H2 R51408/R95003, H3 R13512 (+R60496 for non-LP baselines), M R70125 ->
  hN_book_optimal, hN_book_summary, hN_book_policy_audit, hN_book_regions, hN_book_segments, plus
  shipped summary/policy/regions/segments and scaled_shuffled, rotated, relocated (22 to 23 checks).
- LV-FP-2: withdrawn/shared/site-name decoys in every book -> feasible plus all of the above (29 to 31).
- LV-FP-3: overrides, multi-proposal sites, negative uplift class -> 27 to 29 checks.
- LV-FP-4: two-fault rounds, shuffled hidden manifests, boundary NONPOSITIVE rows -> shipped and hidden
  data_quality, relocated_copy (1 to 5 checks for order slips).
