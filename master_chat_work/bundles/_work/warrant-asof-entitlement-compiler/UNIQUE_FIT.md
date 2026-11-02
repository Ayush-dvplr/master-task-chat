# Unique fit (S3), try 3

Method: `harness/conv_sweep.py` with UNIQ=1, STARTS=requested,decided,recorded,latest on the prototype reference
`proto_ref/test_output.py`. Candidate space per corpus: HR/contract day clock {site, utc, zone:<each zone in
tz_rules.json>} x grant start {requested, decided (k-th qualifying decided_at, shipped), recorded (recorded_at of
the approval that completes k qualifying approvers), latest (last qualifying decided_at)} x window {half [lo,hi),
closed}. 56 readings with 5 zones. A reading fits when the gateway simulation (reference World with config
re-settled at reviewed_at, attestation gating and SoD off) reproduces observed_state of every row. Every rival is
evaluated until its first mismatching instant; the planted reading labels every row in the build itself.

Evidence rows: `observe()` appends keep rows (own RNG `random.Random(seed*13+7)`) only where some rival disagrees
with the planted reading; `evidence kills` counts rows per rival (cap 2). Every rival in every corpus has 2.

Planted readings use start in {requested, decided} only: on the SHIPPED corpus (byte-identical, 6 real zones,
48 readings without `latest`) 2 readings fit: site/decided/half and site/recorded/half (proto/t3/uniq_old.txt,
665 s). So `recorded` is never planted; it stays a rival that evidence rows kill in every new corpus.

Final run (corpora in `proto/t3/corp2`, logs `proto/t3/kill5a.txt`, `kill5b.txt`):

| corpus | planted | rows | instants | fits | worst kill instant |
|---|---|---|---|---|---|
| C1 91019:0.05:conv | zone:Site/Dune, requested, half | 670 | 507 | 1/56 | 13 |
| C2 85041:0.05:conv | zone:Site/Dune, requested, closed (P12) | 364 | 287 | 1/56 | 13 |
| C3 93029:0.05:conv | zone:Site/Ember, requested, half | 412 | 317 | 1/56 | 8 |
| C4 96043:0.05:conv | zone:Site/Cobalt, requested, half | 1397 | 988 | 1/56 | 13 |
| C5 92023:0.05:conv | zone:Site/Brisk, requested, half | 699 | 519 | 1/56 | 7 |
| C6 98123:0.05:conv | zone:Site/Brisk, requested, closed (P12, reseeded from 98053) | 673 | 504 | 1/56 | 8 |
| C7 94031:0.05:conv | zone:Site/Arden, requested, half | 98 | 92 | 1/56 | 10 |
| C8 99061:0.05:conv | zone:Site/Arden, requested, closed (P12) | 243 | 204 | 1/56 | 11 |
| tier_a 51017:0.05:heldout | site, decided, half | 1064 | 769 | 1/56 | 14 |
| tier_b 62029:0.05:heldout | site, decided, half | 1306 | 892 | 1/56 | 14 |
| tier_c 73031:0.04:boundary | site, decided, half | 1054 | 737 | 1/56 | 14 |

Before the `latest` rival got its own evidence rows, tier_b fit 2/56 (site/decided and site/latest,
proto/t3/uniq_latest.txt); fixed in observe() (rival list now includes latest).
Pre-existing shipped ambiguity (not caused by this design): decided vs recorded (above) and a1 step 38 vD
(latest decided_at) reproduced all 2195 accepted shipped rows. Listed in OUT/QC_RISKS.md.

## Shipped after build (master ruling 2)
Measured first: latest start changes shipped dev 117 / prod 124 units, recorded start dev 135 / prod 231 units, so
4 discriminating dev rows (AT-002250..AT-002253, not_in_effect) were appended with observe()'s stream (seed 0).
Final shipped (2253 rows, 369 instants, 64 readings with 6 real zones x 4 starts x 2 windows): fits 1/64
[site, decided, half], worst-kill-instant 64 (proto/t4/uniq_ship.txt). Built tiers unchanged (proto/t4/tierdiff.txt).

## P12 (4989b35): window convention planted closed in C2, C6, C8
Verifier and oracle now route every window (membership, binding, freeze, contract cover, on-call shift, grant,
key value) through the settled window reading. C2, C6, C8 are built with window = closed; build() adds
plant_freeze_ends() for closed conv tiers only (freeze windows ending exactly on an approved ticket's begin, kept
only where the frozen state changes a profile; C2 has no eligible ticket, C6 1, C8 3). Re-run on the fixed
verifier (`p12/t3.py`, log `p12/runs/s2_uniq.txt`, same method and candidate space): each fits 1/56, the planted
closed reading only; every rival (incl. `half`) has 2 evidence kills. Half tiers (C1, C3, C4, C5, C7, tier_a/b/c) and
the shipped corpus: corpus bytes and expected outputs identical before/after (`p12/runs/identity.txt`).
Measured closed-vs-half effect (differing profile units): C2 dev 12 / prod 137, C6 membership dev 59 / prod 39 +
freeze dev 1, C8 membership dev 92 / prod 58 + freeze dev 13 / prod 1. Old oracle (all windows half except grants
and key values) loses conv_2_prod, conv_6_dev/prod, conv_8_dev/prod = 25 points (`p12/runs/score_eng0.txt`).
conv_6 reseed (P12, after the kill rows): at 98053 no start reading changed any output (p12/exp8.py: decided,
recorded, latest 0/0 units), so a start-wrong program kept conv_6. Reseeded 98123 (same zone, closed): start
decided 10/12, recorded 21/12, latest 7/1 units (p12/runs/exp9.txt); layer effects closed vs half on t7
(p12/runs/exp2_t7.txt) membership dev 13, freeze dev 8 (6 planted freeze windows), binding/cover/on-call/grant dev 1.
Unique fit on the final verifier `p12/t7.py` (p12/runs/s5_uniq.txt): rows 673, instants 504, fits 1/56
[('zone:Site/Brisk', 'requested', 'closed')], every rival 2 evidence kills, worst-kill-instant 8. The C6 figures in the P12
paragraph above (1 freeze pick, membership 59/39) are for the retired seed 98053.
