# LEVERS (try 3, convention lever)

Lever: each corpus carries its own gateway conventions, shown only by its own `access_attestations.csv` observations.
Docs: instruction.md:1 ("they belong to each corpus ... that corpus's `access_attestations.csv`"), instruction.md:3 ("their own ... gateway conventions"), corpus_index.md:53 ("The gateway conventions belong to the corpus, and its own observations are the record of them."), time_rules.md:13 and :21, access_contract.md:26 and :40 (unchanged: each convention is the one the observations show).

| tier | seed | scale | variant | HR clock planted | grant start | window | checks (weight) |
|---|---|---|---|---|---|---|---|
| conv_1 | 91019 | 0.05 | conv | zone:Site/Dune | requested | half | dev 5, prod 5 |
| conv_2 | 85041 | 0.05 | conv | zone:Site/Dune | requested | closed | dev 5, prod 5 |
| conv_3 | 93029 | 0.05 | conv | zone:Site/Ember | requested | half | dev 5, prod 5 |
| conv_4 | 96043 | 0.05 | conv | zone:Site/Cobalt | requested | half | dev 5, prod 5 |
| conv_5 | 92023 | 0.05 | conv | zone:Site/Brisk | requested | half | dev 5, prod 5 |
| conv_6 | 98123 | 0.05 | conv | zone:Site/Brisk | requested | closed | dev 5, prod 5 |
| conv_7 | 94031 | 0.05 | conv | zone:Site/Arden | requested | half | dev 5, prod 5 |
| conv_8 | 99061 | 0.05 | conv | zone:Site/Arden | requested | closed | dev 5, prod 5 |

Lever points 80 of 155 positive (51.6%; P12 added non-lever checks: config split 3->1+3, altered config 3, contract layout 1, triangle 5->3, dev values 3->5, report transcript 3->1). P12 G02: every window is routed through the settled window in solve.py (engine inw) and in the verifier World.inw; conv_2, conv_6, conv_8 plant `closed` with `plant_freeze_ends` (closed tiers only) adding freeze windows ending at a ticket start; memberships, bindings and grants end at `as_of` (RULE_COVERAGE.md). conv_6 was reseeded 98053 -> 98123 in P12 because at 98053 no start reading changed any output (a start-wrong program kept conv_6). A window-wrong program now loses the window-sensitive parts of conv_2, conv_6 and conv_8 (P7w, p12/runs/s6_P7w.txt: all six closed-tier parts, 30 points), was 0. Old positive 72 unchanged in bodies; the reference and generator gained convention parameters with shipped defaults (`SHIPPED_CONV`), so old tiers reproduce byte-identical expected outputs.

Own RNG and program call: tier corpora come from `build(root, seed, 0.05, "conv", conv)` with fresh seeds; evidence rows come from `observe()` on its own stream `random.Random(seed * 13 + 7)`; each tier runs its own `_run_all(_conv_tier(name), name)`. One artifact per check (dev profile or prod profile).

Unique fit: every conv tier and tier_a/b/c fits exactly 1 of 56 readings (WORK/UNIQUE_FIT.md); `observe()` now asserts every rival reading is contradicted by at least one row. Shipped fitted 2/48 (decided and recorded start); 4 dev rows AT-002250..AT-002253 appended (shipped data changed), profiles unchanged.

Loss kind against a1-like programs: WRONG (dev and prod documents differ by hundreds of units; WORK/proto/t3/kill5a.txt, kill5b.txt). No timeout or crash lever.
